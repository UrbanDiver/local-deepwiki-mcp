"""Foundation types: protocols and core enums."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks are used to report progress during long-running
    operations like indexing and wiki generation.
    """

    def __call__(self, msg: str, current: int, total: int) -> None:
        """Report progress.

        Args:
            msg: Description of current operation.
            current: Current step number.
            total: Total number of steps.
        """
        ...


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
