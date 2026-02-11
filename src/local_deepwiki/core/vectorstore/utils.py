"""Utility functions and classes for vectorstore."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from local_deepwiki.models import CodeChunk


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_minute: int):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute.
        """
        self.rate = requests_per_minute / 60.0  # Requests per second
        self.tokens = float(requests_per_minute)
        self.max_tokens = float(requests_per_minute)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                # Wait for tokens to refill
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1.0


def _sanitize_string_value(value: str) -> str:
    """Sanitize a string value for use in LanceDB filter expressions.

    Escapes single quotes to prevent injection attacks.

    Args:
        value: The string to sanitize.

    Returns:
        Sanitized string safe for use in filter expressions.
    """
    # Escape single quotes by doubling them
    return value.replace("'", "''")


def _row_to_chunk_default(row: dict[str, Any]) -> CodeChunk:
    """Default conversion from LanceDB row to CodeChunk."""
    return CodeChunk(
        id=row["id"],
        file_path=row["file_path"],
        language=row["language"],
        chunk_type=row["chunk_type"],
        name=row["name"] or None,
        content=row["content"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        docstring=row["docstring"] or None,
        parent_name=row["parent_name"] or None,
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )
