"""Tests for retry logic in providers."""

import pytest

from local_deepwiki.providers.base import RETRYABLE_EXCEPTIONS, with_retry


class TestWithRetry:
    """Tests for the with_retry decorator."""

    async def test_succeeds_on_first_attempt(self):
        """Test that successful calls work normally."""
        call_count = 0

        @with_retry(max_attempts=3)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    async def test_retries_on_connection_error(self):
        """Test that connection errors trigger retry."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection refused")
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3

    async def test_retries_on_timeout_error(self):
        """Test that timeout errors trigger retry."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def timeout_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Request timed out")
            return "success"

        result = await timeout_func()
        assert result == "success"
        assert call_count == 2

    async def test_gives_up_after_max_attempts(self):
        """Test that function gives up after max attempts."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection refused")

        with pytest.raises(ConnectionError):
            await always_fails()

        assert call_count == 3

    async def test_does_not_retry_non_retryable_errors(self):
        """Test that non-retryable errors are raised immediately."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def value_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid value")

        with pytest.raises(ValueError):
            await value_error_func()

        assert call_count == 1

    async def test_retries_on_rate_limit(self):
        """Test that rate limit errors trigger retry."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Rate limit exceeded")
            return "success"

        result = await rate_limited_func()
        assert result == "success"
        assert call_count == 2

    async def test_retries_on_server_overload(self):
        """Test that 503 errors trigger retry."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def overloaded_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("503 Service Unavailable")
            return "success"

        result = await overloaded_func()
        assert result == "success"
        assert call_count == 2

    async def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @with_retry(max_attempts=3)
        async def documented_func():
            """This is a docstring."""
            return "success"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring."

    async def test_custom_max_attempts(self):
        """Test that max_attempts parameter is respected."""
        call_count = 0

        @with_retry(max_attempts=5, base_delay=0.01)
        async def func_with_custom_attempts():
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise ConnectionError("Connection refused")
            return "success"

        result = await func_with_custom_attempts()
        assert result == "success"
        assert call_count == 5


class TestRetryableExceptions:
    """Tests for the RETRYABLE_EXCEPTIONS tuple."""

    def test_includes_connection_error(self):
        """Test that ConnectionError is retryable."""
        assert ConnectionError in RETRYABLE_EXCEPTIONS

    def test_includes_timeout_error(self):
        """Test that TimeoutError is retryable."""
        assert TimeoutError in RETRYABLE_EXCEPTIONS

    def test_includes_os_error(self):
        """Test that OSError is retryable."""
        assert OSError in RETRYABLE_EXCEPTIONS
