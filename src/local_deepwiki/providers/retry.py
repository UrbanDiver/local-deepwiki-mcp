"""Retry decorator with exponential backoff for async provider calls."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.errors import (
    ProviderConnectionError,
    ProviderRateLimitError,
)

__all__ = [
    "RETRYABLE_EXCEPTIONS",
    "RetryConfig",
    "with_retry",
]

logger = get_logger(__name__)


# Exception types that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Covers network-related OS errors
    ProviderConnectionError,
    ProviderRateLimitError,
)


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Immutable retry/backoff configuration.

    Bundles the retry parameters shared across the internal helper functions
    (_retry_known_error, _handle_retryable_exception, _handle_generic_exception,
    _execute_with_backoff) to avoid long parameter lists.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


def _calc_delay(
    base_delay: float,
    exponential_base: float,
    attempt: int,
    max_delay: float,
    jitter: bool,
) -> float:
    """Compute the backoff delay for a given attempt number."""
    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
    return delay * (0.5 + random.random()) if jitter else delay


def _classify_generic_error(e: Exception) -> tuple[bool, bool]:
    """Classify a generic exception as rate-limit and/or server-overload.

    Returns:
        (is_rate_limit, is_overloaded) boolean tuple.
    """
    error_str = str(e).lower()
    is_rate_limit = "rate" in error_str and "limit" in error_str
    is_overloaded = (
        "overloaded" in error_str or "503" in error_str or "502" in error_str
    )
    return is_rate_limit, is_overloaded


async def _retry_known_error(
    func: Callable[..., Any],
    e: Exception,
    attempt: int,
    cfg: RetryConfig,
    label: str,
) -> None:
    """Log and sleep before the next retry attempt for a known retryable error."""
    delay = _calc_delay(
        cfg.base_delay, cfg.exponential_base, attempt, cfg.max_delay, cfg.jitter
    )
    logger.warning(
        "%s attempt %d failed: %s. Retrying in %.2fs...",
        func.__name__,
        attempt,
        e,
        delay,
    )
    await asyncio.sleep(delay)


async def _handle_retryable_exception(
    func: Callable[..., Any],
    e: Exception,
    attempt: int,
    cfg: RetryConfig,
) -> None:
    """Handle a known retryable exception: log and sleep before next attempt."""
    if attempt == cfg.max_attempts:
        logger.warning(
            "%s failed after %d attempts: %s", func.__name__, cfg.max_attempts, e
        )
        raise
    await _retry_known_error(
        func,
        e,
        attempt,
        cfg,
        "failed",
    )


async def _handle_generic_exception(
    func: Callable[..., Any],
    e: Exception,
    attempt: int,
    cfg: RetryConfig,
) -> None:
    """Handle an unclassified exception: re-raise if not retryable, else sleep."""
    is_rate_limit, is_overloaded = _classify_generic_error(e)
    if not (is_rate_limit or is_overloaded):
        raise
    if attempt == cfg.max_attempts:
        if is_rate_limit:
            logger.warning(
                "%s rate limited after %d attempts", func.__name__, cfg.max_attempts
            )
        raise
    label = "rate limited" if is_rate_limit else "server overloaded"
    delay = _calc_delay(
        cfg.base_delay, cfg.exponential_base, attempt, cfg.max_delay, cfg.jitter
    )
    logger.warning("%s %s. Retrying in %.2fs...", func.__name__, label, delay)
    await asyncio.sleep(delay)


async def _execute_with_backoff(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    cfg: RetryConfig,
) -> Any:
    """Execute *func* with retry/backoff logic.

    Handles three categories of errors:
    - ``RETRYABLE_EXCEPTIONS``: network/connection errors — retry with backoff.
    - Rate-limit / server-overload messages in generic exceptions — retry with backoff.
    - Everything else — re-raise immediately.

    Args:
        func: The async callable to invoke.
        args: Positional arguments.
        kwargs: Keyword arguments.
        cfg: Retry configuration (max_attempts, delays, jitter, etc.).

    Returns:
        Return value of *func* on success.

    Raises:
        The last exception after exhausting retries, or the first non-retryable error.
    """
    last_exception: Exception | None = None

    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            await _handle_retryable_exception(func, e, attempt, cfg)

        except Exception as e:  # noqa: BLE001 - Intentional broad catch for API resilience: different providers (Anthropic, OpenAI, Ollama) raise different exception types for rate limits and server errors. We inspect error messages to detect retryable conditions and re-raise immediately if not recognized.
            last_exception = e
            await _handle_generic_exception(func, e, attempt, cfg)

    # Should not reach here, but just in case
    if last_exception:  # pragma: no cover
        raise last_exception  # pragma: no cover
    raise RuntimeError(f"{func.__name__} failed unexpectedly")  # pragma: no cover


def with_retry(
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for adding retry logic with exponential backoff to async functions.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        exponential_base: Base for exponential backoff calculation.
        jitter: Whether to add random jitter to delays.

    Returns:
        Decorated function with retry logic.
    """
    cfg = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await _execute_with_backoff(func, args, kwargs, cfg)

        return wrapper

    return decorator
