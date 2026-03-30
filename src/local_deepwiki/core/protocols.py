"""Protocol interfaces for core components.

Defines structural typing contracts (``typing.Protocol``) for the core
layer so that callers can depend on the interface rather than the concrete
implementation.  This raises the *abstractness* metric for the ``core``
package and improves the overall coupling score.

All protocols are ``@runtime_checkable`` so that guards and diagnostic
code can use ``isinstance`` checks.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ChunkerProtocol(Protocol):
    """Protocol defining the interface for code chunkers.

    Any object that can split a source file into semantic code chunks
    satisfies this contract.  Used for dependency injection — test stubs
    and alternative chunking strategies can be validated with
    ``isinstance(obj, ChunkerProtocol)``.
    """

    def chunk_file(self, file_path: Path, repo_root: Path) -> Iterator:
        """Extract semantic code chunks from a source file.

        Args:
            file_path: Path to the source file.
            repo_root: Root directory of the repository.

        Yields:
            CodeChunk objects for each semantic unit found.
        """
        ...


@runtime_checkable
class SecretDetectorProtocol(Protocol):
    """Protocol defining the interface for secret detection.

    Components that scan code for hardcoded credentials should accept
    this Protocol so that lightweight test doubles can be substituted
    without subclassing the concrete ``SecretDetector``.
    """

    def scan_content(
        self,
        content: str,
        file_path: str,
        start_line: int = 0,
    ) -> list:
        """Scan code content for secrets.

        Args:
            content: Code content to scan.
            file_path: Path to file (for reporting).
            start_line: Starting line number offset.

        Returns:
            List of SecretFinding objects for detected secrets.
        """
        ...


@runtime_checkable
class RateLimiterProtocol(Protocol):
    """Protocol defining the interface for rate limiters.

    Components that throttle API calls should accept this Protocol
    rather than the concrete ``RateLimiter`` class so that tests can
    supply a no-op limiter.
    """

    async def acquire(self) -> None:
        """Acquire permission to make a request.

        Blocks if rate limited, or raises ``RateLimitExceeded``
        if the limit cannot be waited for.
        """
        ...

    def release(self) -> None:
        """Release the burst semaphore after request completes."""
        ...
