"""Retry decorator with exponential backoff for async provider calls."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from functools import wraps
from typing import Any

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.errors import (
    ProviderConnectionError,
    ProviderRateLimitError,
)

__all__ = [
    "RETRYABLE_EXCEPTIONS",
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

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.warning(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            max_attempts,
                            e,
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)), max_delay
                    )
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        "%s attempt %d failed: %s. Retrying in %.2fs...",
                        func.__name__,
                        attempt,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                except Exception as e:  # noqa: BLE001 - Intentional broad catch for API resilience: different providers (Anthropic, OpenAI, Ollama) raise different exception types for rate limits and server errors. We inspect error messages to detect retryable conditions and re-raise immediately if not recognized.
                    error_str = str(e).lower()
                    if "rate" in error_str and "limit" in error_str:
                        last_exception = e
                        if attempt == max_attempts:
                            logger.warning(
                                "%s rate limited after %d attempts",
                                func.__name__,
                                max_attempts,
                            )
                            raise

                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            "%s rate limited. Retrying in %.2fs...",
                            func.__name__,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    elif (
                        "overloaded" in error_str
                        or "503" in error_str
                        or "502" in error_str
                    ):
                        # Server overloaded - retry with backoff
                        last_exception = e
                        if attempt == max_attempts:
                            raise

                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            "%s server overloaded. Retrying in %.2fs...",
                            func.__name__,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        # Non-retryable error
                        raise

            # Should not reach here, but just in case
            if last_exception:  # pragma: no cover
                raise last_exception  # pragma: no cover
            raise RuntimeError(f"{func.__name__} failed unexpectedly")

        return wrapper

    return decorator
