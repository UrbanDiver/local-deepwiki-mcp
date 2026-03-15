"""Foundation types: protocols and core enums."""

from __future__ import annotations

from collections.abc import Awaitable
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from local_deepwiki.models.chunks import CodeChunk
    from local_deepwiki.models.research import ResearchProgress
    from local_deepwiki.models.wiki import WikiPage


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks are used to report progress during long-running
    operations like indexing and wiki generation.
    """

    def __call__(self, msg: str, current: int, total: int, /) -> None:
        """Report progress.

        Args:
            msg: Description of current operation.
            current: Current step number.
            total: Total number of steps.
        """
        ...


@runtime_checkable
class CancellationChecker(Protocol):
    """Check whether an operation has been cancelled.

    Returns True if the operation should stop.
    """

    def __call__(self) -> bool: ...


@runtime_checkable
class ProgressReporter(Protocol):
    """Report progress for a research operation.

    Called with a ``ResearchProgress`` instance during long-running
    research pipelines.
    """

    def __call__(self, progress: "ResearchProgress", /) -> Awaitable[None]: ...


@runtime_checkable
class LogCallback(Protocol):
    """Log a message string.

    Used for lightweight progress or status callbacks that accept a
    single human-readable message.
    """

    def __call__(self, message: str, /) -> None: ...


@runtime_checkable
class PageGenerator(Protocol):
    """Generate a wiki page on demand.

    Returns a coroutine that produces a ``WikiPage``.
    """

    def __call__(self) -> Awaitable["WikiPage"]: ...


@runtime_checkable
class RowMapper(Protocol):
    """Map a dictionary row to a ``CodeChunk``.

    Used by vector store iterators to convert raw LanceDB rows into
    typed ``CodeChunk`` objects.
    """

    def __call__(self, row: dict, /) -> "CodeChunk": ...


class Language(StrEnum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    SWIFT = "swift"
    RUBY = "ruby"
    PHP = "php"
    KOTLIN = "kotlin"
    CSHARP = "csharp"


class ChunkType(StrEnum):
    """Types of code chunks."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    COMMENT = "comment"
    OTHER = "other"
    FILE_SUMMARY = "file_summary"
    MODULE_SUMMARY = "module_summary"
