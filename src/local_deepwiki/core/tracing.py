"""RAG Tracing — structured observability for the RAG pipeline.

Records timing, chunk counts, scores, and model info at each pipeline stage
(retrieval → reranking → agentic RAG → context → LLM generation) so that
answer provenance can be inspected when ``debug=True``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RAGTrace:
    """Records one RAG pipeline execution for debugging.

    Mutable during pipeline execution, then serialised via ``to_dict()``.
    Only non-default fields are included in the output to keep payloads lean.
    """

    query: str = ""
    start_time: float = field(default_factory=time.monotonic)

    # -- Retrieval phase --
    retrieval_chunks: int = 0
    retrieval_scores: list[float] = field(default_factory=list)
    retrieval_time_ms: float = 0.0
    search_mode: str = "vector"

    # -- Reranking phase (optional) --
    reranking_enabled: bool = False
    reranking_model: str = ""
    reranking_time_ms: float = 0.0
    reranked_scores: list[float] = field(default_factory=list)

    # -- Agentic RAG phase (optional) --
    agentic_rag_enabled: bool = False
    agentic_rewritten_query: str | None = None
    agentic_time_ms: float = 0.0

    # -- Context construction --
    context_chunks_used: int = 0
    context_total_chars: int = 0

    # -- LLM generation --
    llm_model: str = ""
    llm_time_ms: float = 0.0

    # -- Total --
    total_time_ms: float = 0.0

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def finish(self) -> None:
        """Stamp ``total_time_ms`` from ``start_time``."""
        self.total_time_ms = (time.monotonic() - self.start_time) * 1000

    def record_retrieval(
        self,
        results: list[Any],
        elapsed_ms: float,
        *,
        search_mode: str = "vector",
    ) -> None:
        """Record retrieval phase metrics."""
        self.retrieval_chunks = len(results)
        self.retrieval_scores = [
            round(r.score, 4) for r in results if hasattr(r, "score")
        ]
        self.retrieval_time_ms = round(elapsed_ms, 2)
        self.search_mode = search_mode

    def record_reranking(
        self,
        results: list[Any],
        elapsed_ms: float,
        model: str,
    ) -> None:
        """Record reranking phase metrics."""
        self.reranking_enabled = True
        self.reranking_model = model
        self.reranking_time_ms = round(elapsed_ms, 2)
        self.reranked_scores = [
            round(r.score, 4) for r in results if hasattr(r, "score")
        ]

    def record_context(self, chunks_used: int, total_chars: int) -> None:
        """Record context construction metrics."""
        self.context_chunks_used = chunks_used
        self.context_total_chars = total_chars

    def record_llm(self, elapsed_ms: float, model: str = "") -> None:
        """Record LLM generation metrics."""
        self.llm_time_ms = round(elapsed_ms, 2)
        self.llm_model = model

    def to_dict(self) -> dict[str, Any]:
        """Serialise to dict, omitting default/zero/empty values."""
        self.finish()
        result: dict[str, Any] = {}
        # Always include query and total
        result["query"] = self.query
        result["total_time_ms"] = round(self.total_time_ms, 2)

        # Retrieval (always present)
        result["retrieval"] = {
            "chunks": self.retrieval_chunks,
            "scores": self.retrieval_scores,
            "time_ms": self.retrieval_time_ms,
            "mode": self.search_mode,
        }

        # Reranking (only if enabled)
        if self.reranking_enabled:
            result["reranking"] = {
                "model": self.reranking_model,
                "time_ms": self.reranking_time_ms,
                "scores": self.reranked_scores,
            }

        # Agentic RAG (only if enabled)
        if self.agentic_rag_enabled:
            agentic: dict[str, Any] = {"time_ms": self.agentic_time_ms}
            if self.agentic_rewritten_query:
                agentic["rewritten_query"] = self.agentic_rewritten_query
            result["agentic_rag"] = agentic

        # Context
        if self.context_chunks_used > 0:
            result["context"] = {
                "chunks_used": self.context_chunks_used,
                "total_chars": self.context_total_chars,
            }

        # LLM
        if self.llm_time_ms > 0:
            llm: dict[str, Any] = {"time_ms": self.llm_time_ms}
            if self.llm_model:
                llm["model"] = self.llm_model
            result["llm"] = llm

        return result
