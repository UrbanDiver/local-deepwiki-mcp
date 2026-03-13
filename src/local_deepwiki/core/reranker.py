"""Reranker — cross-encoder reranking for search results.

Provides a ``Reranker`` protocol and a ``CrossEncoderReranker`` that uses
sentence-transformers to re-score (query, chunk) pairs.  The cross-encoder
is lazily imported so the dependency remains optional.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from local_deepwiki.logging import get_logger
from local_deepwiki.models import SearchResult

logger = get_logger(__name__)


@runtime_checkable
class Reranker(Protocol):
    """Protocol for search result rerankers."""

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Rerank search results by relevance to query.

        Args:
            query: The search query.
            results: Search results to rerank.
            top_k: Keep only the top-k results after reranking.

        Returns:
            Reranked (and optionally truncated) results.
        """
        ...

    @property
    def model_name(self) -> str:
        """Return the model identifier for tracing."""
        ...


class CrossEncoderReranker:
    """Reranker using sentence-transformers CrossEncoder.

    The model is loaded lazily on first ``rerank()`` call so that importing
    this module does not trigger a heavy ``sentence_transformers`` import.
    """

    __slots__ = ("_model_name", "_model")

    def __init__(
        self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ) -> None:
        self._model_name = model_name
        self._model: Any = None

    def _ensure_model(self) -> Any:
        """Lazily load the CrossEncoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for cross-encoder reranking. "
                    "Install it with: pip install sentence-transformers"
                ) from exc
            self._model = CrossEncoder(self._model_name)
        return self._model

    @property
    def model_name(self) -> str:
        return self._model_name

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Rerank results using the cross-encoder model.

        Runs the model in a thread to avoid blocking the event loop.

        Args:
            query: The search query.
            results: Search results to rerank.
            top_k: Keep only the top-k results after reranking.

        Returns:
            Reranked results with updated scores.
        """
        if not results:
            return results

        model = self._ensure_model()
        pairs = [(query, r.chunk.content) for r in results]

        # Run prediction in a thread since it's CPU-bound
        scores: list[float] = await asyncio.to_thread(model.predict, pairs)

        # Build new results with cross-encoder scores
        ranked_pairs = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
        if top_k is not None:
            ranked_pairs = ranked_pairs[:top_k]

        return [
            SearchResult(
                chunk=r.chunk,
                score=float(s),
                highlights=r.highlights,
                suggestions=r.suggestions if hasattr(r, "suggestions") else None,
            )
            for r, s in ranked_pairs
        ]


def get_reranker(model_name: str | None) -> CrossEncoderReranker | None:
    """Factory: return a reranker if a model is configured, else ``None``."""
    if not model_name or not isinstance(model_name, str):
        return None
    return CrossEncoderReranker(model_name)
