"""Tests for rate limiting functionality."""

import asyncio
import time

import pytest

from local_deepwiki.core.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitExceeded,
    configure_rate_limiter,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self):
        """Test that default config values are sensible."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10
        assert config.wait_for_minute_limit is True
        assert config.wait_for_hour_limit is False

    def test_custom_values(self):
        """Test that custom values are applied."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_limit=5,
            wait_for_minute_limit=False,
            wait_for_hour_limit=True,
        )
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_limit == 5
        assert config.wait_for_minute_limit is False
        assert config.wait_for_hour_limit is True


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    async def test_acquire_increments_counters(self):
        """Test that acquire increments counters correctly."""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=100))

        assert limiter.state.minute_count == 0
        assert limiter.state.hour_count == 0

        await limiter.acquire()
        limiter.release()

        assert limiter.state.minute_count == 1
        assert limiter.state.hour_count == 1

    async def test_context_manager_releases_on_exit(self):
        """Test that context manager releases burst semaphore."""
        limiter = RateLimiter(RateLimitConfig(burst_limit=2))

        async with limiter:
            assert limiter.state.current_concurrent == 1

        assert limiter.state.current_concurrent == 0

    async def test_burst_limit_enforced(self):
        """Test that burst limit limits concurrent requests."""
        limiter = RateLimiter(RateLimitConfig(burst_limit=2, requests_per_minute=100))

        acquired = []

        async def acquire_slot(slot_id: int):
            await limiter.acquire()
            acquired.append(slot_id)
            await asyncio.sleep(0.1)  # Hold the slot briefly
            limiter.release()

        # Start 3 concurrent tasks, but only 2 should run at once
        tasks = [
            asyncio.create_task(acquire_slot(1)),
            asyncio.create_task(acquire_slot(2)),
            asyncio.create_task(acquire_slot(3)),
        ]

        # Give first two tasks time to acquire
        await asyncio.sleep(0.05)

        # Only 2 should have acquired at this point
        assert len(acquired) == 2

        # Wait for all to complete
        await asyncio.gather(*tasks)
        assert len(acquired) == 3

    async def test_minute_limit_raises_when_not_waiting(self):
        """Test that minute limit raises exception when wait is disabled."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=2,
                wait_for_minute_limit=False,
            )
        )

        # First two should succeed
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        # Third should fail
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire()

        assert "Minute limit exceeded" in str(exc_info.value)
        assert exc_info.value.reset_seconds > 0

    async def test_hour_limit_raises(self):
        """Test that hour limit raises exception."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=2,
            )
        )

        # First two should succeed
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        # Third should fail
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire()

        assert "Hourly limit exceeded" in str(exc_info.value)
        assert exc_info.value.reset_seconds > 0

    async def test_minute_window_resets(self):
        """Test that minute window resets after expiry."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=2,
                wait_for_minute_limit=False,
            )
        )

        # Use up the limit
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        # Manually reset the window by setting reset time in the past
        limiter._state.minute_reset = time.time() - 61

        # Should succeed now
        await limiter.acquire()
        limiter.release()

        assert limiter.state.minute_count == 1

    async def test_hour_window_resets(self):
        """Test that hour window resets after expiry."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=2,
            )
        )

        # Use up the limit
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        # Manually reset the window by setting reset time in the past
        limiter._state.hour_reset = time.time() - 3601

        # Should succeed now
        await limiter.acquire()
        limiter.release()

        assert limiter.state.hour_count == 1

    async def test_get_status(self):
        """Test that get_status returns correct information."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=1000,
                burst_limit=10,
            )
        )

        await limiter.acquire()
        limiter.release()

        status = limiter.get_status()

        assert status["minute_count"] == 1
        assert status["minute_limit"] == 60
        assert status["minute_remaining"] == 59
        assert status["hour_count"] == 1
        assert status["hour_limit"] == 1000
        assert status["hour_remaining"] == 999
        assert status["burst_limit"] == 10
        assert status["current_concurrent"] == 0
        assert 0 < status["minute_reset_in"] <= 60
        assert 0 < status["hour_reset_in"] <= 3600

    async def test_concurrent_acquire_is_safe(self):
        """Test that concurrent acquires are handled safely."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=100,
                burst_limit=10,
            )
        )

        async def make_request():
            async with limiter:
                await asyncio.sleep(0.01)

        # Run many concurrent requests
        tasks = [asyncio.create_task(make_request()) for _ in range(20)]
        await asyncio.gather(*tasks)

        assert limiter.state.minute_count == 20
        assert limiter.state.current_concurrent == 0


class TestGlobalRateLimiter:
    """Tests for global rate limiter functions."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        reset_rate_limiter()

    def teardown_method(self):
        """Reset rate limiter after each test."""
        reset_rate_limiter()

    def test_get_rate_limiter_creates_default(self):
        """Test that get_rate_limiter creates a default instance."""
        limiter = get_rate_limiter()

        assert limiter is not None
        assert limiter.config.requests_per_minute == 60

    def test_get_rate_limiter_returns_same_instance(self):
        """Test that get_rate_limiter returns the same instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_configure_rate_limiter(self):
        """Test that configure_rate_limiter applies custom config."""
        config = RateLimitConfig(requests_per_minute=30)
        configure_rate_limiter(config)

        limiter = get_rate_limiter()
        assert limiter.config.requests_per_minute == 30

    def test_reset_rate_limiter(self):
        """Test that reset_rate_limiter clears the global instance."""
        limiter1 = get_rate_limiter()
        reset_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is not limiter2


class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_exception_message(self):
        """Test that exception has correct message."""
        exc = RateLimitExceeded("Test limit exceeded", reset_seconds=30)

        assert str(exc) == "Test limit exceeded"
        assert exc.message == "Test limit exceeded"
        assert exc.reset_seconds == 30

    def test_exception_default_reset_seconds(self):
        """Test that reset_seconds defaults to 0."""
        exc = RateLimitExceeded("Test")
        assert exc.reset_seconds == 0


class TestRateLimiterWaiting:
    """Tests for rate limiter waiting behavior."""

    async def test_minute_limit_waits_when_configured(self):
        """Test that minute limit waits when wait_for_minute_limit is True."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=2,
                wait_for_minute_limit=True,
            )
        )

        # Use up the limit
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        # Manually set reset time to almost now so we wait very briefly
        limiter._state.minute_reset = time.time() - 59.9

        start = time.time()
        await limiter.acquire()
        limiter.release()
        elapsed = time.time() - start

        # Should have waited ~0.1 seconds
        assert elapsed >= 0.05  # Allow some tolerance

    async def test_hour_limit_waits_when_configured(self):
        """Test that hour limit waits when wait_for_hour_limit is True."""
        limiter = RateLimiter(
            RateLimitConfig(
                requests_per_minute=100,
                requests_per_hour=2,
                wait_for_hour_limit=True,
            )
        )

        # Use up the limit
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        # Manually set reset time to almost now so we wait very briefly
        limiter._state.hour_reset = time.time() - 3599.9

        start = time.time()
        await limiter.acquire()
        limiter.release()
        elapsed = time.time() - start

        # Should have waited ~0.1 seconds
        assert elapsed >= 0.05  # Allow some tolerance
