"""SearchMixin -- thin delegation layer over SearchEngine.

All search logic now lives in ``SearchEngine`` (composition-based, explicit
dependencies).  This mixin delegates every call to the engine instance,
creating one lazily from ``self`` attributes when ``_search_engine`` is not
set by the host class (backward compatibility for tests that instantiate a
bare ``SearchMixin``).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from local_deepwiki.logging import get_logger
from local_deepwiki.models import SearchResult

from ..schema import (
    SEARCH_PROFILES,
    VALID_CHUNK_TYPES,
    VALID_LANGUAGES,
    SearchFeedback,
    SearchProfile,
    SearchResultPage,
)
from ..utils import _log_task_exception

from .search_types import SearchRequest

if TYPE_CHECKING:
    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper
    from local_deepwiki.core.vectorstore.search_engine import SearchEngine
    from local_deepwiki.core.vectorstore.store import VectorStore

logger = get_logger(__name__)


class SearchMixin:
    """Mixin providing search, pagination, feedback, and adaptive search methods.

    Delegates to the ``SearchEngine`` at ``self._search_engine``.  If the
    engine has not been injected (e.g. in tests that create a bare
    ``SearchMixin``), one is built lazily from the ``self`` attributes that
    the old mixin pattern expected.
    """

    # -- Lazy engine accessor ------------------------------------------------

    def _get_search_engine(self) -> "SearchEngine":
        """Return the ``SearchEngine``, creating it lazily if needed."""
        engine: SearchEngine | None = getattr(self, "_search_engine", None)
        if engine is not None:
            return engine

        # Backward-compatible path: build an engine from self attributes
        from local_deepwiki.core.vectorstore.search_engine import SearchEngine
        from local_deepwiki.core.vectorstore.search_params import SearchEngineConfig

        engine = SearchEngine(
            get_table=self._get_table,  # type: ignore[attr-defined]
            row_to_chunk=self._row_to_chunk,  # type: ignore[attr-defined]
            embedding_provider=self.embedding_provider,  # type: ignore[attr-defined]
            get_search_cache=lambda: self._search_cache,  # type: ignore[attr-defined]
            fuzzy_search_config=self._fuzzy_search_config,  # type: ignore[attr-defined]
            adaptive_searcher=self._adaptive_searcher,  # type: ignore[attr-defined]
            lazy_index_manager=self._lazy_index_manager,  # type: ignore[attr-defined]
            config=SearchEngineConfig(
                default_search_profile=self._default_search_profile,  # type: ignore[attr-defined]
                adaptive_search_enabled=self._adaptive_search_enabled,  # type: ignore[attr-defined]
                default_search_mode=self._default_search_mode,  # type: ignore[attr-defined]
                bm25_weight=self._bm25_weight,  # type: ignore[attr-defined]
            ),
        )
        self._search_engine = engine  # type: ignore[attr-defined]
        return engine

    # -----------------------------------------------------------------
    # Backward-compat private helpers (used by existing tests)
    # -----------------------------------------------------------------

    def _execute_vector_search(
        self,
        table: Any,
        query_embedding: list[float],
        filters: list[str],
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        """Execute LanceDB vector search with latency tracking.

        Runs the vector search, records latency for lazy index management,
        and triggers index creation if latency thresholds are exceeded.

        Args:
            table: LanceDB table to search.
            query_embedding: Query vector.
            filters: Pre-validated LanceDB filter expressions.
            fetch_limit: Maximum raw rows to fetch.

        Returns:
            Raw LanceDB result rows.
        """
        search = table.search(query_embedding).limit(fetch_limit)
        if filters:
            search = search.where(" AND ".join(filters))

        search_start = time.monotonic()
        results = search.to_list()
        search_latency_ms = (time.monotonic() - search_start) * 1000

        self._lazy_index_manager.record_search_latency(search_latency_ms)  # type: ignore[attr-defined]

        if self._lazy_index_manager.should_create_index():  # type: ignore[attr-defined]
            try:
                task = asyncio.create_task(
                    self._lazy_index_manager.schedule_index_creation()  # type: ignore[attr-defined]
                )
                task.add_done_callback(_log_task_exception)
            except RuntimeError:
                logger.debug("Cannot schedule lazy index creation: no event loop")

        return results

    def _apply_fuzzy_reranking(
        self,
        search_results: list[SearchResult],
        query: str,
        fuzzy_weight: float,
        *,
        use_fuzzy: bool,
    ) -> tuple[list[SearchResult], bool]:
        """Apply fuzzy re-ranking if explicitly requested or auto-enabled.

        Args:
            search_results: Results from vector search.
            query: Original search query.
            fuzzy_weight: Weight for fuzzy vs vector score.
            use_fuzzy: Whether fuzzy was explicitly requested.

        Returns:
            Tuple of (possibly reranked results, whether auto-fuzzy was enabled).
        """
        from local_deepwiki.core.fuzzy_search import (
            extract_highlights,
            rerank_with_fuzzy,
            should_auto_enable_fuzzy,
        )

        fuzzy_config = self._fuzzy_search_config  # type: ignore[attr-defined]
        auto_fuzzy_enabled = False

        if (
            fuzzy_config.enable_auto_fuzzy
            and not use_fuzzy
            and should_auto_enable_fuzzy(
                search_results, fuzzy_config.auto_fuzzy_threshold
            )
        ):
            auto_fuzzy_enabled = True
            logger.debug(
                "Auto-enabling fuzzy search due to poor results (best score below %s)",
                fuzzy_config.auto_fuzzy_threshold,
            )

        if (use_fuzzy or auto_fuzzy_enabled) and search_results:
            search_results = rerank_with_fuzzy(search_results, query, fuzzy_weight)
            for result in search_results:
                result.highlights = extract_highlights(result.chunk.content, query)

        return search_results, auto_fuzzy_enabled

    def _record_and_cache(
        self,
        query: str,
        query_embedding: list[float],
        search_results: list[SearchResult],
        cache_filters: dict[str, Any],
        *,
        use_cache: bool,
        auto_fuzzy_enabled: bool,
        fetch_limit: int,
    ) -> None:
        """Record adaptive search quality and cache results.

        .. note:: This method retains its original signature for backward
           compatibility with existing tests. The ``SearchEngine`` equivalent
           (``_record_and_store_results``) uses ``SearchExecutionContext`` instead.

        Args:
            query: Original search query.
            query_embedding: Query vector (for cache key).
            search_results: Final search results.
            cache_filters: Cache key filters.
            use_cache: Whether caching is enabled for this query.
            auto_fuzzy_enabled: Whether auto-fuzzy was triggered.
            fetch_limit: Fetch limit used (for adaptive learning).
        """
        if self._adaptive_search_enabled and search_results:  # type: ignore[attr-defined]
            avg_score = sum(r.score for r in search_results) / len(search_results)
            self._adaptive_searcher.record_search_quality(  # type: ignore[attr-defined]
                query, avg_score, len(search_results), fetch_limit
            )

        if use_cache and not auto_fuzzy_enabled:
            self._search_cache.set(  # type: ignore[attr-defined]
                query, query_embedding, search_results, cache_filters
            )

    @staticmethod
    def _resolve_search_mode(search_mode: str | None, default: str) -> str:
        """Resolve the effective search mode from parameter or default."""
        mode = search_mode or default
        if mode not in ("vector", "keyword", "hybrid"):
            logger.warning("Invalid search_mode '%s', falling back to 'vector'", mode)
            return "vector"
        return mode

    def _execute_fts_search(
        self,
        table: Any,
        query: str,
        filters: list[str],
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        """Execute LanceDB full-text (BM25) search."""
        try:
            search = table.search(query, query_type="fts").limit(fetch_limit)
            if filters:
                search = search.where(" AND ".join(filters))
            return search.to_list()
        except (RuntimeError, OSError, ValueError, AttributeError) as exc:
            logger.warning("FTS search failed (falling back to empty): %s", exc)
            return []

    def _convert_fts_results(
        self,
        rows: list[dict[str, Any]],
    ) -> list[SearchResult]:
        """Convert FTS result rows to SearchResult objects with normalized scores."""
        if not rows:
            return []
        max_score = max(row.get("_score", 0.0) for row in rows)
        if max_score <= 0:
            max_score = 1.0
        results: list[SearchResult] = []
        for row in rows:
            bm25_score = row.get("_score", 0.0)
            normalized = bm25_score / max_score
            chunk = self._row_to_chunk(row)  # type: ignore[attr-defined]
            results.append(SearchResult(chunk=chunk, score=normalized, highlights=[]))
        return results

    @staticmethod
    def _reciprocal_rank_fusion(
        vector_rows: list[dict[str, Any]],
        fts_rows: list[dict[str, Any]],
        *,
        k: int = 60,
        vector_weight: float = 1.0,
        fts_weight: float = 0.3,
    ) -> list[tuple[dict[str, Any], float]]:
        """Merge vector and FTS results using Reciprocal Rank Fusion."""
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

    # -----------------------------------------------------------------
    # search()
    # -----------------------------------------------------------------

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        request: "SearchRequest | None" = None,
        search_mode: str | None = None,
        language: str | None = None,
        chunk_type: str | None = None,
        path_pattern: str | None = None,
        use_fuzzy: bool = False,
        fuzzy_weight: float = 0.3,
        profile: SearchProfile | str | None = None,
        min_similarity: float | None = None,
        auto_suggest: bool = True,
    ) -> list[SearchResult]:
        """Search for similar code chunks.

        Orchestrates the search pipeline: embed query, check cache, execute
        search (vector, keyword, or hybrid), apply filters/fuzzy/suggestions,
        record and cache.

        Accepts either individual keyword arguments (backward compatible) or
        a ``SearchRequest`` object via the ``request`` parameter. When a
        ``SearchRequest`` is provided its fields take precedence over the
        positional/keyword arguments.

        Args:
            query: Search query text.
            limit: Maximum number of results.
            request: Optional ``SearchRequest`` bundle. Fields override
                the corresponding keyword arguments.
            search_mode: Search mode override -- ``"vector"`` (semantic),
                ``"keyword"`` (BM25 full-text), or ``"hybrid"`` (both merged
                via Reciprocal Rank Fusion). Defaults to the store's
                configured ``default_search_mode``.
            language: Optional language filter (e.g., "python", "typescript").
            chunk_type: Optional chunk type filter (e.g., "function", "class", "method").
            path_pattern: Optional file path pattern filter (e.g., "src/**/*.py").
            use_fuzzy: Whether to use fuzzy matching to re-rank results.
            fuzzy_weight: Weight for fuzzy score when use_fuzzy is True (0.0-1.0).
            profile: Search profile for precision/recall trade-off.
            min_similarity: Minimum similarity threshold override.
            auto_suggest: Whether to generate "Did you mean?" suggestions.

        Returns:
            List of search results with scores.
        """
        engine = self._get_search_engine()
        if request is None:
            request = SearchRequest(
                query=query,
                limit=limit,
                search_mode=search_mode,
                language=language,
                chunk_type=chunk_type,
                path_pattern=path_pattern,
                use_fuzzy=use_fuzzy,
                fuzzy_weight=fuzzy_weight,
                profile=profile,
                min_similarity=min_similarity,
                auto_suggest=auto_suggest,
            )
        return await engine.search(request, store=self)

    # -----------------------------------------------------------------
    # search_paginated()
    # -----------------------------------------------------------------

    async def search_paginated(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        *,
        request: "SearchRequest | None" = None,
        language: str | None = None,
        chunk_type: str | None = None,
        path_pattern: str | None = None,
        use_fuzzy: bool = False,
        fuzzy_weight: float = 0.3,
        cursor: str | None = None,
        profile: SearchProfile | str | None = None,
        min_similarity: float | None = None,
    ) -> SearchResultPage:
        """Search for similar code chunks with pagination support.

        This method supports both offset-based and cursor-based pagination:
        - Offset-based: Use `offset` parameter (simpler, but may have stability issues)
        - Cursor-based: Use `cursor` parameter (more stable for concurrent updates)

        Accepts either a ``SearchRequest`` object (via ``request``) or
        individual keyword arguments.  When ``request`` is provided it takes
        precedence and the individual keyword arguments are ignored.

        Args:
            query: Search query text (ignored when ``request`` is given).
            limit: Maximum number of results per page (ignored when ``request`` is given).
            offset: Starting offset for pagination (0-based).
            request: Optional pre-built ``SearchRequest``. When provided,
                all other search parameters are ignored.
            language: Optional language filter (e.g., "python", "typescript").
            chunk_type: Optional chunk type filter (e.g., "function", "class", "method").
            path_pattern: Optional file path pattern filter (e.g., "src/**/*.py").
            use_fuzzy: Whether to use fuzzy matching to re-rank results.
            fuzzy_weight: Weight for fuzzy score when use_fuzzy is True (0.0-1.0).
            cursor: Optional cursor for cursor-based pagination (overrides offset).
            profile: Search profile for precision/recall trade-off.
                Can be SearchProfile enum or string ("fast", "balanced", "thorough").
                If None, uses the store's default profile.
            min_similarity: Minimum similarity threshold override.
                Results below this score are filtered out.
                If None, uses the profile's default threshold.

        Returns:
            SearchResultPage with results, total count, and pagination metadata.
        """
        engine = self._get_search_engine()
        if request is None:
            request = SearchRequest(
                query=query,
                limit=limit,
                offset=offset,
                cursor=cursor,
                language=language,
                chunk_type=chunk_type,
                path_pattern=path_pattern,
                use_fuzzy=use_fuzzy,
                fuzzy_weight=fuzzy_weight,
                profile=profile,
                min_similarity=min_similarity,
                auto_suggest=False,
            )
        return await engine.search_paginated(request, store=self)

    def record_feedback(self, feedback: SearchFeedback) -> None:
        """Record user feedback on a search result.

        Feedback is used to improve future search results by learning which
        results are actually relevant for specific queries.

        Args:
            feedback: User feedback on a search result.
        """
        self._get_search_engine().record_feedback(feedback)

    @property
    def search_profile(self) -> SearchProfile:
        """Get the current default search profile.

        Returns:
            The default SearchProfile used when none is specified.
        """
        return self._get_search_engine().default_search_profile

    @search_profile.setter
    def search_profile(self, profile: SearchProfile | str) -> None:
        """Set the default search profile.

        Args:
            profile: The search profile to use as default.
                Can be SearchProfile enum or string ("fast", "balanced", "thorough").

        Raises:
            ValueError: If the profile string is invalid.
        """
        engine = self._get_search_engine()
        if isinstance(profile, str):
            try:
                engine.default_search_profile = SearchProfile(profile.lower())
            except ValueError as e:
                raise ValueError(
                    f"Invalid search profile: {profile}. "
                    f"Valid values: {[p.value for p in SearchProfile]}"
                ) from e
        else:
            engine.default_search_profile = profile

    @property
    def adaptive_search_enabled(self) -> bool:
        """Check if adaptive search is enabled.

        Returns:
            True if adaptive search depth estimation is enabled.
        """
        return self._get_search_engine().adaptive_search_enabled

    @adaptive_search_enabled.setter
    def adaptive_search_enabled(self, enabled: bool) -> None:
        """Enable or disable adaptive search.

        Args:
            enabled: Whether to enable adaptive search depth estimation.
        """
        self._get_search_engine().adaptive_search_enabled = enabled

    @property
    def adaptive_search_stats(self) -> dict[str, Any]:
        """Get statistics about adaptive search performance.

        Returns:
            Dictionary with adaptive search statistics including:
            - query_history_size: Number of queries in history
            - feedback_stats: Feedback collection statistics
        """
        return self._get_search_engine().adaptive_search_stats
