"""Rate limiting for API calls.

This module provides rate limiting functionality to prevent API quota exhaustion
when making calls to LLM and embedding providers. It uses a sliding window approach
for minute and hour limits, with support for burst limiting.

Example usage:
    from local_deepwiki.core.rate_limiter import get_rate_limiter, RateLimitConfig

    # Configure rate limiter (optional, defaults are sensible)
    configure_rate_limiter(RateLimitConfig(requests_per_minute=30))

    # Use in async context
    async def make_api_call():
        await get_rate_limiter().acquire()
        return await llm_provider.generate(prompt)

    # Or use as context manager
    async def make_api_call_with_context():
        async with get_rate_limiter():
            return await llm_provider.generate(prompt)
"""

from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Sliding window durations for rate limiting
MINUTE_WINDOW_SECONDS = 60
HOUR_WINDOW_SECONDS = 3600


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and cannot wait.

    This exception is raised when the hourly rate limit is exceeded,
    as waiting for the hour window to reset would be impractical.

    Attributes:
        message: Description of the rate limit exceeded.
        reset_seconds: Seconds until the rate limit resets.
    """

    def __init__(self, message: str, reset_seconds: float = 0) -> None:
        """Initialize the rate limit exceeded exception.

        Args:
            message: Description of what limit was exceeded.
            reset_seconds: Seconds until the rate limit resets.
        """
        super().__init__(message)
        self.message = message
        self.reset_seconds = reset_seconds


@dataclass
class RateLimitConfig:
    """Rate limit configuration.

    Attributes:
        requests_per_minute: Maximum requests allowed per minute. Default: 60.
        requests_per_hour: Maximum requests allowed per hour. Default: 1000.
        burst_limit: Maximum concurrent requests allowed. Default: 10.
        wait_for_minute_limit: Whether to wait when minute limit is hit. Default: True.
        wait_for_hour_limit: Whether to wait when hour limit is hit. Default: False.
    """

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    wait_for_minute_limit: bool = True
    wait_for_hour_limit: bool = False


@dataclass
class RateLimitState:
    """Tracks rate limit state.

    Uses sliding window counters for minute and hour tracking.

    Attributes:
        minute_count: Number of requests in current minute window.
        hour_count: Number of requests in current hour window.
        minute_reset: Timestamp when minute window started.
        hour_reset: Timestamp when hour window started.
        current_concurrent: Number of currently executing requests.
    """

    minute_count: int = 0
    hour_count: int = 0
    minute_reset: float = field(default_factory=time.time)
    hour_reset: float = field(default_factory=time.time)
    current_concurrent: int = 0


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Implements rate limiting with:
    - Per-minute limits (waits if exceeded)
    - Per-hour limits (raises exception if exceeded)
    - Burst limiting (concurrent request limit)

    Thread-safe for concurrent async operations.

    Example:
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=30))

        async def make_call():
            await limiter.acquire()
            try:
                return await api_call()
            finally:
                limiter.release()  # For burst tracking

        # Or use context manager:
        async with limiter:
            return await api_call()
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize the rate limiter.

        Args:
            config: Rate limit configuration. Uses defaults if not provided.
        """
        self._config = config or RateLimitConfig()
        self._state = RateLimitState()
        self._lock = asyncio.Lock()
        self._burst_semaphore = asyncio.Semaphore(self._config.burst_limit)

    @property
    def config(self) -> RateLimitConfig:
        """Get the current rate limit configuration."""
        return self._config

    @property
    def state(self) -> RateLimitState:
        """Get the current rate limit state (for monitoring)."""
        return self._state

    def _reset_windows_if_expired(self, now: float) -> None:
        """Reset minute/hour windows if they have expired.

        Args:
            now: Current timestamp.
        """
        # Reset minute window if expired
        if now - self._state.minute_reset >= MINUTE_WINDOW_SECONDS:
            self._state.minute_count = 0
            self._state.minute_reset = now
            logger.debug("Rate limiter: minute window reset")

        # Reset hour window if expired
        if now - self._state.hour_reset >= HOUR_WINDOW_SECONDS:
            self._state.hour_count = 0
            self._state.hour_reset = now
            logger.debug("Rate limiter: hour window reset")

    async def _wait_for_minute_limit(self, now: float) -> None:
        """Wait for minute limit to reset if exceeded.

        Args:
            now: Current timestamp.

        Raises:
            RateLimitExceeded: If minute limit exceeded and not configured to wait.
        """
        if self._state.minute_count >= self._config.requests_per_minute:
            wait_time = MINUTE_WINDOW_SECONDS - (now - self._state.minute_reset)
            if wait_time > 0:
                if self._config.wait_for_minute_limit:
                    logger.info(
                        "Rate limit: minute limit reached, waiting %.1fs", wait_time
                    )
                    # Release lock while waiting to not block other operations
                    self._lock.release()
                    try:
                        await asyncio.sleep(wait_time)
                    finally:
                        await self._lock.acquire()
                    # Reset the window after waiting
                    self._state.minute_count = 0
                    self._state.minute_reset = time.time()
                else:
                    raise RateLimitExceeded(
                        f"Minute limit exceeded ({self._config.requests_per_minute}/min). "
                        f"Reset in {wait_time:.0f}s",
                        reset_seconds=wait_time,
                    )

    async def _check_hour_limit(self, now: float) -> None:
        """Check hour limit and raise if exceeded.

        Args:
            now: Current timestamp.

        Raises:
            RateLimitExceeded: If hour limit is exceeded.
        """
        if self._state.hour_count >= self._config.requests_per_hour:
            wait_time = HOUR_WINDOW_SECONDS - (now - self._state.hour_reset)
            if wait_time > 0:
                if self._config.wait_for_hour_limit:
                    logger.warning(
                        "Rate limit: hour limit reached, waiting %.0fs", wait_time
                    )
                    # Release lock while waiting
                    self._lock.release()
                    try:
                        await asyncio.sleep(wait_time)
                    finally:
                        await self._lock.acquire()
                    # Reset the window after waiting
                    self._state.hour_count = 0
                    self._state.hour_reset = time.time()
                else:
                    raise RateLimitExceeded(
                        f"Hourly limit exceeded ({self._config.requests_per_hour}/hour). "
                        f"Reset in {wait_time:.0f}s",
                        reset_seconds=wait_time,
                    )

    async def acquire(self) -> None:
        """Acquire permission to make a request.

        Blocks if rate limited (for minute limits), raises exception
        for hour limits. Also respects burst limit via semaphore.

        Raises:
            RateLimitExceeded: If hourly limit is exceeded.
        """
        # First acquire burst semaphore (limits concurrent requests)
        await self._burst_semaphore.acquire()

        async with self._lock:
            now = time.time()

            # Reset windows if expired
            self._reset_windows_if_expired(now)

            # Check and wait for minute limit
            await self._wait_for_minute_limit(now)

            # Check hour limit (raises if exceeded)
            await self._check_hour_limit(now)

            # Increment counters
            self._state.minute_count += 1
            self._state.hour_count += 1
            self._state.current_concurrent += 1

            logger.debug(
                "Rate limiter: acquired (min: %d/%d, hour: %d/%d, concurrent: %d/%d)",
                self._state.minute_count,
                self._config.requests_per_minute,
                self._state.hour_count,
                self._config.requests_per_hour,
                self._state.current_concurrent,
                self._config.burst_limit,
            )

    def release(self) -> None:
        """Release the burst semaphore after request completes.

        Should be called after the API request finishes to allow
        other requests to proceed.
        """
        self._burst_semaphore.release()
        self._state.current_concurrent = max(0, self._state.current_concurrent - 1)
        logger.debug(
            "Rate limiter: released (concurrent: %d)", self._state.current_concurrent
        )

    async def __aenter__(self) -> "RateLimiter":
        """Enter async context manager, acquiring rate limit permission."""
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager, releasing burst semaphore."""
        self.release()

    def get_status(self) -> dict:
        """Get current rate limiter status for monitoring.

        Returns:
            Dictionary with current rate limit state and configuration.
        """
        now = time.time()
        return {
            "minute_count": self._state.minute_count,
            "minute_limit": self._config.requests_per_minute,
            "minute_remaining": max(
                0, self._config.requests_per_minute - self._state.minute_count
            ),
            "minute_reset_in": max(
                0, MINUTE_WINDOW_SECONDS - (now - self._state.minute_reset)
            ),
            "hour_count": self._state.hour_count,
            "hour_limit": self._config.requests_per_hour,
            "hour_remaining": max(
                0, self._config.requests_per_hour - self._state.hour_count
            ),
            "hour_reset_in": max(
                0, HOUR_WINDOW_SECONDS - (now - self._state.hour_reset)
            ),
            "current_concurrent": self._state.current_concurrent,
            "burst_limit": self._config.burst_limit,
        }


# Global rate limiter instance
_rate_limiter_var: ContextVar[RateLimiter | None] = ContextVar(
    "rate_limiter", default=None
)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    Creates a new instance with default configuration if none exists.

    Returns:
        The global RateLimiter instance.
    """
    val = _rate_limiter_var.get()
    if val is None:
        val = RateLimiter()
        _rate_limiter_var.set(val)
    return val


def configure_rate_limiter(config: RateLimitConfig) -> None:
    """Configure the global rate limiter with custom settings.

    This should be called at application startup before any API calls.

    Args:
        config: Rate limit configuration to use.
    """
    _rate_limiter_var.set(RateLimiter(config))
    logger.info(
        "Rate limiter configured: %d/min, %d/hour, burst=%d",
        config.requests_per_minute,
        config.requests_per_hour,
        config.burst_limit,
    )


def reset_rate_limiter() -> None:
    """Reset the global rate limiter.

    Useful for testing or when reconfiguration is needed.
    """
    _rate_limiter_var.set(None)
    logger.debug("Rate limiter reset")
