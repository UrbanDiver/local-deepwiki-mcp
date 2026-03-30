"""Standalone search pipeline execution functions.

These functions contain the low-level LanceDB execution logic that was
previously embedded as methods on ``SearchEngine``.  They receive all
dependencies as explicit parameters so they are easy to test in isolation.

``SearchEngine`` imports from here and delegates to these functions; external
consumers should go through ``SearchEngine`` or ``VectorStore``, not import
from this module directly.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, SearchResult

from .search_params import SearchPipelineParams
from .utils import _log_task_exception

if TYPE_CHECKING:
    from .maintenance import LazyIndexManager

logger = get_logger(__name__)

# Type alias matching the one in search_engine.py
RowToChunk = Callable[[dict[str, Any]], CodeChunk]


def execute_vector_search(
    table: Any,
    query_embedding: list[float],
    filters: list[str],
    fetch_limit: int,
    lazy_index_manager: "LazyIndexManager",
) -> list[dict[str, Any]]:
    """Execute LanceDB vector search with latency tracking.

    Args:
        table: LanceDB table to search.
        query_embedding: Query embedding vector.
        filters: List of LanceDB filter expressions to AND together.
        fetch_limit: Maximum number of rows to retrieve from LanceDB.
        lazy_index_manager: Manager for recording latency and scheduling index
            creation when high latency is detected.

    Returns:
        Raw rows returned by LanceDB.
    """
    search = table.search(query_embedding).limit(fetch_limit)
    if filters:
        search = search.where(" AND ".join(filters))

    search_start = time.monotonic()
    results = search.to_list()
    search_latency_ms = (time.monotonic() - search_start) * 1000

    lazy_index_manager.record_search_latency(search_latency_ms)

    if lazy_index_manager.should_create_index():
        try:
            task = asyncio.create_task(lazy_index_manager.schedule_index_creation())
            task.add_done_callback(_log_task_exception)
        except RuntimeError:
            logger.debug("Cannot schedule lazy index creation: no event loop")

    return results


def execute_fts_search(
    table: Any,
    query: str,
    filters: list[str],
    fetch_limit: int,
) -> list[dict[str, Any]]:
    """Execute LanceDB full-text (BM25) search.

    Args:
        table: LanceDB table to search.
        query: Text query for full-text search.
        filters: List of LanceDB filter expressions to AND together.
        fetch_limit: Maximum number of rows to retrieve from LanceDB.

    Returns:
        Raw rows returned by LanceDB, or an empty list on failure.
    """
    try:
        search = table.search(query, query_type="fts").limit(fetch_limit)
        if filters:
            search = search.where(" AND ".join(filters))
        return search.to_list()
    except (RuntimeError, OSError, ValueError, AttributeError) as exc:
        logger.warning("FTS search failed (falling back to empty): %s", exc)
        return []


def convert_fts_results(
    rows: list[dict[str, Any]],
    row_to_chunk: RowToChunk,
) -> list[SearchResult]:
    """Convert FTS result rows to SearchResult objects with normalized scores.

    Args:
        rows: Raw FTS result rows from LanceDB.
        row_to_chunk: Callable that converts a raw row dict to a ``CodeChunk``.

    Returns:
        List of ``SearchResult`` objects with BM25 scores normalised to [0, 1].
    """
    if not rows:
        return []

    max_score = max(row.get("_score", 0.0) for row in rows)
    if max_score <= 0:
        max_score = 1.0

    results: list[SearchResult] = []
    for row in rows:
        bm25_score = row.get("_score", 0.0)
        normalized = bm25_score / max_score
        chunk = row_to_chunk(row)
        results.append(SearchResult(chunk=chunk, score=normalized, highlights=[]))
    return results


def reciprocal_rank_fusion(
    vector_rows: list[dict[str, Any]],
    fts_rows: list[dict[str, Any]],
    *,
    k: int = 60,
    vector_weight: float = 1.0,
    fts_weight: float = 0.3,
) -> list[tuple[dict[str, Any], float]]:
    """Merge vector and FTS results using Reciprocal Rank Fusion.

    Args:
        vector_rows: Raw rows from vector search, ordered by descending score.
        fts_rows: Raw rows from FTS search, ordered by descending BM25 score.
        k: RRF smoothing constant (default 60).
        vector_weight: Weight applied to vector-search RRF scores.
        fts_weight: Weight applied to FTS RRF scores.

    Returns:
        List of ``(row, merged_score)`` tuples, sorted by descending merged score.
        Scores are normalised to [0, 1].
    """
    scores: dict[str, float] = {}
    docs: dict[str, dict[str, Any]] = {}

    for rank, row in enumerate(vector_rows):
        doc_id = row["id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + vector_weight / (k + rank + 1)
        docs[doc_id] = row

    for rank, row in enumerate(fts_rows):
        doc_id = row["id"]
        scores[doc_id] = scores.get(doc_id, 0.0) + fts_weight / (k + rank + 1)
        if doc_id not in docs:
            docs[doc_id] = row

    sorted_pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    max_score = sorted_pairs[0][1] if sorted_pairs else 1.0
    return [(docs[doc_id], score / max_score) for doc_id, score in sorted_pairs]


def run_keyword_pipeline(
    table: Any,
    query: str,
    filters: list[str],
    fetch_limit: int,
    row_to_chunk: RowToChunk,
) -> list[SearchResult]:
    """Execute the keyword-only (BM25) search pipeline.

    Args:
        table: LanceDB table to search.
        query: Text query for full-text search.
        filters: List of LanceDB filter expressions to AND together.
        fetch_limit: Maximum number of rows to retrieve from LanceDB.
        row_to_chunk: Callable that converts a raw row dict to a ``CodeChunk``.

    Returns:
        List of ``SearchResult`` objects.
    """
    fts_rows = execute_fts_search(table, query, filters, fetch_limit)
    return convert_fts_results(fts_rows, row_to_chunk)


def run_hybrid_pipeline(
    params: SearchPipelineParams,
) -> list[SearchResult]:
    """Execute the hybrid (vector + BM25 with RRF) search pipeline.

    Args:
        params: Immutable bundle of all pipeline parameters.

    Returns:
        List of ``SearchResult`` objects merged by RRF.
    """
    vector_rows = execute_vector_search(
        params.table,
        params.query_embedding,
        params.filters,
        params.fetch_limit,
        params.lazy_index_manager,
    )
    fts_rows = execute_fts_search(
        params.table, params.query, params.filters, params.fetch_limit
    )

    if not fts_rows:
        return _convert_vector_results(
            vector_rows, params.min_similarity, params.row_to_chunk
        )

    merged = reciprocal_rank_fusion(
        vector_rows,
        fts_rows,
        fts_weight=params.bm25_weight,
    )
    return [
        SearchResult(chunk=params.row_to_chunk(row), score=score, highlights=[])
        for row, score in merged
    ]


def run_vector_pipeline(
    params: SearchPipelineParams,
) -> list[SearchResult]:
    """Execute the vector-only (semantic) search pipeline.

    Args:
        params: Immutable bundle of all pipeline parameters.

    Returns:
        List of ``SearchResult`` objects.
    """
    raw_rows = execute_vector_search(
        params.table,
        params.query_embedding,
        params.filters,
        params.fetch_limit,
        params.lazy_index_manager,
    )
    return _convert_vector_results(raw_rows, params.min_similarity, params.row_to_chunk)


def _convert_vector_results(
    rows: list[dict[str, Any]],
    min_similarity: float,
    row_to_chunk: RowToChunk,
) -> list[SearchResult]:
    """Convert raw LanceDB vector-search rows to SearchResult objects.

    Filters out results whose cosine-similarity score is below ``min_similarity``.

    Args:
        rows: Raw rows from LanceDB vector search.
        min_similarity: Minimum cosine-similarity threshold.
        row_to_chunk: Callable that converts a raw row dict to a ``CodeChunk``.

    Returns:
        Filtered list of ``SearchResult`` objects.
    """
    results: list[SearchResult] = []
    for row in rows:
        dist = row.get("_distance", 0)
        score = 1.0 - dist * dist / 2.0
        if score < min_similarity:
            continue
        chunk = row_to_chunk(row)
        results.append(SearchResult(chunk=chunk, score=score, highlights=[]))
    return results


def dispatch_search(
    mode: str,
    params: SearchPipelineParams,
) -> list[SearchResult]:
    """Dispatch to the appropriate search pipeline based on mode.

    Args:
        mode: One of ``"vector"``, ``"keyword"``, or ``"hybrid"``.
        params: Immutable bundle of all pipeline parameters.

    Returns:
        List of ``SearchResult`` objects from the chosen pipeline.
    """
    if mode == "keyword":
        return run_keyword_pipeline(
            params.table,
            params.query,
            params.filters,
            params.fetch_limit,
            params.row_to_chunk,
        )
    if mode == "hybrid":
        return run_hybrid_pipeline(params)
    return run_vector_pipeline(params)
