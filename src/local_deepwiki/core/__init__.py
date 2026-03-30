"""Core functionality for local-deepwiki."""

from __future__ import annotations

from local_deepwiki.core.protocols import (
    ChunkerProtocol,
    RateLimiterProtocol,
    SecretDetectorProtocol,
)

__all__ = [
    "ChunkerProtocol",
    "RateLimiterProtocol",
    "SecretDetectorProtocol",
]
