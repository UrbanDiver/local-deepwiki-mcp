"""Service layer return type dataclasses.

Frozen dataclasses defining return types for service methods,
providing a clean contract between service and handler layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceEntry:
    """A single source reference from a RAG query result."""

    file: str
    lines: str
    chunk_type: str
    score: float
    wiki_resource: str | None = None


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Result of a RAG query (ask_question).

    Attributes:
        answer: The LLM-synthesized answer.
        sources: Source code references that informed the answer.
        agentic_metadata: Optional metadata from agentic RAG pipeline.
        trace: Reserved for Phase 5 RAG tracing.
    """

    answer: str
    sources: tuple[SourceEntry, ...]
    agentic_metadata: dict[str, Any] | None = None
    trace: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Result of a wiki export operation (HTML or PDF)."""

    output_path: str
    pages_exported: int
    format: str  # "html" or "pdf"


@dataclass(frozen=True, slots=True)
class IndexPipelineResult:
    """Result of the indexing pipeline."""

    files_indexed: int
    chunks_created: int
    wiki_pages_generated: int
    generation_mode: str
    wiki_path: str = ""
    languages: dict[str, int] = field(default_factory=dict)
    messages: tuple[str, ...] = ()
    operation_id: str = ""
