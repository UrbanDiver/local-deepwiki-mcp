"""SearchEngine -- composition-based search with explicit dependencies.

Extracts the search logic previously embedded in ``SearchMixin`` into a
standalone class that receives all dependencies via its constructor.  This
eliminates the implicit coupling through shared ``self`` attributes that
is inherent in the mixin pattern.

``SearchMixin`` is retained as a thin backward-compatible delegation layer
so that ``VectorStore`` keeps its existing public API.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, SearchResult

from .mixins.search_types import SearchRequest
from .schema import (
    SEARCH_PROFILES,
    VALID_CHUNK_TYPES,
    VALID_LANGUAGES,
    SearchFeedback,
    SearchProfile,
    SearchResultPage,
)
from .search_pipeline import (
    dispatch_search as _dispatch_search,
    execute_fts_search as _execute_fts_search,
    execute_vector_search as _execute_vector_search,
    convert_fts_results as _convert_fts_results,
    reciprocal_rank_fusion as _reciprocal_rank_fusion,
    run_keyword_pipeline as _run_keyword_pipeline,
    run_hybrid_pipeline as _run_hybrid_pipeline,
    run_vector_pipeline as _run_vector_pipeline,
)
from .search_postprocess import (
    apply_fuzzy_reranking as _apply_fuzzy_reranking,
    apply_post_filters as _apply_post_filters,
    attach_suggestions as _attach_suggestions,
    generate_suggestions as _generate_suggestions,
)

if TYPE_CHECKING:
    from local_deepwiki.config import FuzzySearchConfig
    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper
    from local_deepwiki.providers.base import EmbeddingProvider

    from .cache import AdaptiveSearcher, SearchCache
    from .maintenance import LazyIndexManager

logger = get_logger(__name__)

# Type alias for the row-to-chunk conversion callable
RowToChunk = Callable[[dict[str, Any]], CodeChunk]


class SearchEngine:
    """Composition-based search engine with explicit dependency injection.

    All collaborators (table, embedding provider, caches, etc.) are passed
    in via the constructor rather than accessed through ``self`` on a host
    class.  This makes the dependencies explicit, testable in isolation,
    and free of the maintenance burden that the mixin TYPE_CHECKING stubs
    imposed.

    Args:
        get_table: Callable that returns the LanceDB table (or None).
        row_to_chunk: Callable that converts a raw LanceDB row dict to a
            ``CodeChunk``.
        embedding_provider: Provider for generating query embeddings.
        get_search_cache: Callable returning the current ``SearchCache``.
            Using a callable (rather than a direct reference) allows the
            host to swap the cache at runtime (e.g. in tests that replace
            ``VectorStore._search_cache``) without breaking the engine.
        fuzzy_search_config: Fuzzy search configuration.
        adaptive_searcher: Adaptive search depth estimator.
        lazy_index_manager: Lazy vector index lifecycle manager.
        default_search_profile: Default search profile enum.
        adaptive_search_enabled: Whether adaptive depth estimation is on.
        default_search_mode: Default search mode (``"vector"``,
            ``"keyword"``, or ``"hybrid"``).
        bm25_weight: Weight for BM25 scores in hybrid search RRF merge.
    """

    def __init__(
        self,
        *,
        get_table: Callable[[], Any | None],
        row_to_chunk: RowToChunk,
        embedding_provider: "EmbeddingProvider",
        get_search_cache: Callable[[], "SearchCache"],
        fuzzy_search_config: "FuzzySearchConfig",
        adaptive_searcher: "AdaptiveSearcher",
        lazy_index_manager: "LazyIndexManager",
        default_search_profile: SearchProfile = SearchProfile.BALANCED,
        adaptive_search_enabled: bool = True,
        default_search_mode: str = "vector",
        bm25_weight: float = 0.3,
    ) -> None:
        self._get_table = get_table
        self._row_to_chunk = row_to_chunk
        self._embedding_provider = embedding_provider
        self._get_search_cache = get_search_cache
        self._fuzzy_search_config = fuzzy_search_config
        self._adaptive_searcher = adaptive_searcher
        self._lazy_index_manager = lazy_index_manager
        self._default_search_profile = default_search_profile
        self._adaptive_search_enabled = adaptive_search_enabled
        self._default_search_mode = default_search_mode
        self._bm25_weight = bm25_weight

        # Lazily initialized fuzzy search helper
        self._fuzzy_search_helper: "FuzzySearchHelper | None" = None

    # -- property accessors for mutable config ---------------------------------

    @property
    def default_search_profile(self) -> SearchProfile:
        return self._default_search_profile

    @default_search_profile.setter
    def default_search_profile(self, value: SearchProfile) -> None:
        self._default_search_profile = value

    @property
    def adaptive_search_enabled(self) -> bool:
        return self._adaptive_search_enabled

    @adaptive_search_enabled.setter
    def adaptive_search_enabled(self, value: bool) -> None:
        self._adaptive_search_enabled = value

    @property
    def fuzzy_search_helper(self) -> "FuzzySearchHelper | None":
        return self._fuzzy_search_helper

    @fuzzy_search_helper.setter
    def fuzzy_search_helper(self, value: "FuzzySearchHelper | None") -> None:
        self._fuzzy_search_helper = value

    # -----------------------------------------------------------------
    # Fuzzy helper (lazy init)
    # -----------------------------------------------------------------

    async def get_fuzzy_helper(self, store: Any) -> "FuzzySearchHelper":
        """Get or create the fuzzy search helper.

        Args:
            store: The VectorStore instance (needed by FuzzySearchHelper).

        Returns:
            FuzzySearchHelper instance with built name index.
        """
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        if self._fuzzy_search_helper is None:
            self._fuzzy_search_helper = FuzzySearchHelper(store)

        if not self._fuzzy_search_helper.is_built:
            await self._fuzzy_search_helper.build_name_index()

        return self._fuzzy_search_helper

    # -----------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------

    def resolve_search_profile(
        self, profile: SearchProfile | str | None
    ) -> tuple[SearchProfile, Any]:
        """Resolve a profile argument to a ``(SearchProfile, ProfileConfig)`` pair."""
        if profile is None:
            resolved = self._default_search_profile
        elif isinstance(profile, str):
            try:
                resolved = SearchProfile(profile.lower())
            except ValueError:
                logger.warning("Invalid search profile '%s', using default", profile)
                resolved = self._default_search_profile
        else:
            resolved = profile
        return resolved, SEARCH_PROFILES[resolved]

    @staticmethod
    def build_search_filters(
        language: str | None,
        chunk_type: str | None,
    ) -> list[str]:
        """Validate filter values and return LanceDB filter expressions."""
        filters: list[str] = []
        if language:
            if language not in VALID_LANGUAGES:
                raise ValueError(f"Invalid language filter: {language}")
            filters.append(f"language = '{language}'")
        if chunk_type:
            if chunk_type not in VALID_CHUNK_TYPES:
                raise ValueError(f"Invalid chunk_type filter: {chunk_type}")
            filters.append(f"chunk_type = '{chunk_type}'")
        return filters

    def compute_fetch_limit(
        self,
        limit: int,
        profile_config: Any,
        query: str,
        *,
        needs_extra: bool = False,
    ) -> int:
        """Return how many raw rows to fetch from LanceDB."""
        base_multiplier = profile_config.fetch_multiplier
        if needs_extra:
            base_multiplier = max(base_multiplier, 3.0)

        if self._adaptive_search_enabled:
            adaptive_depth = self._adaptive_searcher.estimate_optimal_depth(
                query, limit
            )
            fetch_limit = max(int(limit * base_multiplier), adaptive_depth)
        else:
            fetch_limit = int(limit * base_multiplier)

        return min(fetch_limit, profile_config.rerank_candidates)

    def convert_results_to_search_results(
        self,
        rows: list[dict[str, Any]],
        min_similarity: float,
    ) -> list[SearchResult]:
        """Convert raw LanceDB rows to ``SearchResult`` objects with score filtering."""
        results: list[SearchResult] = []
        for row in rows:
            dist = row.get("_distance", 0)
            score = 1.0 - dist * dist / 2.0
            if score < min_similarity:
                continue
            chunk = self._row_to_chunk(row)
            results.append(SearchResult(chunk=chunk, score=score, highlights=[]))
        return results

    async def generate_suggestions(
        self,
        query: str,
        search_results: list[SearchResult],
        store: Any,
    ) -> list[str] | None:
        """Generate 'Did you mean?' suggestions for poor-quality results.

        Args:
            query: Original search query.
            search_results: Current search results.
            store: The VectorStore instance (needed by FuzzySearchHelper).
        """
        return await _generate_suggestions(
            query,
            search_results,
            store,
            self._fuzzy_search_config,
            self.get_fuzzy_helper,
        )

    # -----------------------------------------------------------------
    # Auto-adjust search limit based on repo size
    # -----------------------------------------------------------------

    def auto_search_limit(self, requested_limit: int) -> int:
        """Adjust search limit based on repo size for better recall."""
        if requested_limit > 0:
            return requested_limit
        try:
            table = self._get_table()
            total = table.count_rows() if table else 0
        except Exception:
            return 10
        if total > 200_000:
            return 40
        if total > 50_000:
            return 20
        return 10

    # -----------------------------------------------------------------
    # Search mode resolution
    # -----------------------------------------------------------------

    @staticmethod
    def resolve_search_mode(search_mode: str | None, default: str) -> str:
        """Resolve the effective search mode from parameter or default."""
        mode = search_mode or default
        if mode not in ("vector", "keyword", "hybrid"):
            logger.warning("Invalid search_mode '%s', falling back to 'vector'", mode)
            return "vector"
        return mode

    # -----------------------------------------------------------------
    # Low-level search execution
    # -----------------------------------------------------------------

    def execute_vector_search(
        self,
        table: Any,
        query_embedding: list[float],
        filters: list[str],
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        """Execute LanceDB vector search with latency tracking."""
        return _execute_vector_search(
            table, query_embedding, filters, fetch_limit, self._lazy_index_manager
        )

    def execute_fts_search(
        self,
        table: Any,
        query: str,
        filters: list[str],
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        """Execute LanceDB full-text (BM25) search."""
        return _execute_fts_search(table, query, filters, fetch_limit)

    def convert_fts_results(
        self,
        rows: list[dict[str, Any]],
    ) -> list[SearchResult]:
        """Convert FTS result rows to SearchResult objects with normalized scores."""
        return _convert_fts_results(rows, self._row_to_chunk)

    @staticmethod
    def reciprocal_rank_fusion(
        vector_rows: list[dict[str, Any]],
        fts_rows: list[dict[str, Any]],
        *,
        k: int = 60,
        vector_weight: float = 1.0,
        fts_weight: float = 0.3,
    ) -> list[tuple[dict[str, Any], float]]:
        """Merge vector and FTS results using Reciprocal Rank Fusion."""
        return _reciprocal_rank_fusion(
            vector_rows,
            fts_rows,
            k=k,
            vector_weight=vector_weight,
            fts_weight=fts_weight,
        )

    def apply_fuzzy_reranking(
        self,
        search_results: list[SearchResult],
        query: str,
        fuzzy_weight: float,
        *,
        use_fuzzy: bool,
    ) -> tuple[list[SearchResult], bool]:
        """Apply fuzzy re-ranking if explicitly requested or auto-enabled."""
        return _apply_fuzzy_reranking(
            search_results,
            query,
            fuzzy_weight,
            use_fuzzy=use_fuzzy,
            fuzzy_config=self._fuzzy_search_config,
        )

    def record_and_cache(
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
        """Record adaptive search quality and cache results."""
        if self._adaptive_search_enabled and search_results:
            avg_score = sum(r.score for r in search_results) / len(search_results)
            self._adaptive_searcher.record_search_quality(
                query, avg_score, len(search_results), fetch_limit
            )

        if use_cache and not auto_fuzzy_enabled:
            self._get_search_cache().set(
                query, query_embedding, search_results, cache_filters
            )

    # -----------------------------------------------------------------
    # Pipeline stages
    # -----------------------------------------------------------------

    def run_keyword_pipeline(
        self,
        table: Any,
        query: str,
        filters: list[str],
        fetch_limit: int,
    ) -> list[SearchResult]:
        """Execute the keyword-only (BM25) search pipeline."""
        return _run_keyword_pipeline(
            table, query, filters, fetch_limit, self._row_to_chunk
        )

    def run_hybrid_pipeline(
        self,
        table: Any,
        query: str,
        query_embedding: list[float],
        filters: list[str],
        fetch_limit: int,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Execute the hybrid (vector + BM25 with RRF) search pipeline."""
        return _run_hybrid_pipeline(
            table,
            query,
            query_embedding,
            filters,
            fetch_limit,
            min_similarity,
            self._bm25_weight,
            self._row_to_chunk,
            self._lazy_index_manager,
        )

    def run_vector_pipeline(
        self,
        table: Any,
        query_embedding: list[float],
        filters: list[str],
        fetch_limit: int,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Execute the vector-only (semantic) search pipeline."""
        return _run_vector_pipeline(
            table,
            query_embedding,
            filters,
            fetch_limit,
            min_similarity,
            self._row_to_chunk,
            self._lazy_index_manager,
        )

    @staticmethod
    def apply_post_filters(
        results: list[SearchResult],
        path_pattern: str | None,
    ) -> list[SearchResult]:
        """Apply post-retrieval filters (path pattern) to search results."""
        return _apply_post_filters(results, path_pattern)

    async def attach_suggestions(
        self,
        query: str,
        search_results: list[SearchResult],
        store: Any,
    ) -> list[SearchResult]:
        """Generate and attach 'Did you mean?' suggestions to the first result."""
        return await _attach_suggestions(
            query,
            search_results,
            store,
            self._fuzzy_search_config,
            self.get_fuzzy_helper,
        )

    # -----------------------------------------------------------------
    # Cache filter builder
    # -----------------------------------------------------------------

    @staticmethod
    def build_cache_filters(
        limit: int,
        resolved_profile: SearchProfile,
        effective_min_similarity: float,
        effective_mode: str,
        language: str | None,
        chunk_type: str | None,
    ) -> dict[str, Any]:
        """Build the cache key filter dictionary."""
        cache_filters: dict[str, Any] = {
            "limit": limit,
            "profile": resolved_profile.value,
            "min_similarity": effective_min_similarity,
            "search_mode": effective_mode,
        }
        if language:
            cache_filters["language"] = language
        if chunk_type:
            cache_filters["chunk_type"] = chunk_type
        return cache_filters

    def dispatch_search(
        self,
        mode: str,
        table: Any,
        query: str,
        query_embedding: list[float],
        filters: list[str],
        fetch_limit: int,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Dispatch to the appropriate search pipeline based on mode."""
        return _dispatch_search(
            mode,
            table,
            query,
            query_embedding,
            filters,
            fetch_limit,
            min_similarity,
            self._bm25_weight,
            self._row_to_chunk,
            self._lazy_index_manager,
        )

    # -----------------------------------------------------------------
    # search_from_request() -- SearchRequest-based entry point
    # -----------------------------------------------------------------

    async def search_from_request(
        self,
        request: SearchRequest,
        store: Any = None,
    ) -> list[SearchResult]:
        """Search for similar code chunks using a ``SearchRequest`` value object.

        This is the canonical entry point for the search pipeline.  The raw
        ``search()`` method constructs a ``SearchRequest`` internally and
        delegates here so that all search logic is driven from a single,
        immutable parameter bundle.

        Args:
            request: Immutable bundle of all search parameters.
            store: The VectorStore instance (needed for fuzzy helper init).

        Returns:
            List of search results with scores.
        """
        table = self._get_table()
        if table is None:
            logger.debug("No table found for search")
            return []

        # Resolve configuration
        effective_mode = self.resolve_search_mode(
            request.search_mode, self._default_search_mode
        )
        resolved_profile, profile_config = self.resolve_search_profile(request.profile)
        effective_min_similarity = (
            request.min_similarity
            if request.min_similarity is not None
            else profile_config.min_similarity
        )

        logger.debug(
            "Searching for: '%s...' limit=%d mode=%s profile=%s min_sim=%s",
            request.query[:50],
            request.limit,
            effective_mode,
            resolved_profile.value,
            effective_min_similarity,
        )

        filters = self.build_search_filters(request.language, request.chunk_type)

        # Compute embedding (needed for vector/hybrid mode and cache)
        needs_embedding = effective_mode != "keyword"
        query_embedding: list[float] = []
        if needs_embedding:
            query_embedding = (await self._embedding_provider.embed([request.query]))[0]

        # Check cache
        cache_filters = self.build_cache_filters(
            request.limit,
            resolved_profile,
            effective_min_similarity,
            effective_mode,
            request.language,
            request.chunk_type,
        )
        use_cache = (
            not request.use_fuzzy and not request.path_pattern and needs_embedding
        )
        if use_cache:
            cached_results = self._get_search_cache().get(
                query_embedding, cache_filters
            )
            if cached_results is not None:
                return cached_results

        fetch_limit = self.compute_fetch_limit(
            request.limit,
            profile_config,
            request.query,
            needs_extra=bool(request.path_pattern or request.use_fuzzy),
        )

        # Execute search pipeline based on mode
        search_results = self.dispatch_search(
            effective_mode,
            table,
            request.query,
            query_embedding,
            filters,
            fetch_limit,
            effective_min_similarity,
        )

        # Post-processing: path filter, fuzzy rerank, truncate, suggestions
        search_results = self.apply_post_filters(search_results, request.path_pattern)

        search_results, auto_fuzzy_enabled = self.apply_fuzzy_reranking(
            search_results,
            request.query,
            request.fuzzy_weight,
            use_fuzzy=request.use_fuzzy,
        )
        search_results = search_results[: request.limit]

        if request.auto_suggest:
            search_results = await self.attach_suggestions(
                request.query, search_results, store
            )

        self.record_and_cache(
            request.query,
            query_embedding,
            search_results,
            cache_filters,
            use_cache=use_cache,
            auto_fuzzy_enabled=auto_fuzzy_enabled,
            fetch_limit=fetch_limit,
        )

        return search_results

    # -----------------------------------------------------------------
    # search() -- main orchestrator (delegates to search_from_request)
    # -----------------------------------------------------------------

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
        search_mode: str | None = None,
        language: str | None = None,
        chunk_type: str | None = None,
        path_pattern: str | None = None,
        use_fuzzy: bool = False,
        fuzzy_weight: float = 0.3,
        profile: SearchProfile | str | None = None,
        min_similarity: float | None = None,
        auto_suggest: bool = True,
        store: Any = None,
    ) -> list[SearchResult]:
        """Search for similar code chunks.

        Constructs a ``SearchRequest`` from the provided arguments and
        delegates to ``search_from_request``.  All search logic lives in
        ``search_from_request``; this method exists for backward compatibility
        with callers that pass raw keyword arguments.

        Args:
            query: Search query text.
            limit: Maximum number of results.
            search_mode: Search mode override.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.
            path_pattern: Optional file path pattern filter.
            use_fuzzy: Whether to use fuzzy matching to re-rank results.
            fuzzy_weight: Weight for fuzzy score when use_fuzzy is True.
            profile: Search profile for precision/recall trade-off.
            min_similarity: Minimum similarity threshold override.
            auto_suggest: Whether to generate "Did you mean?" suggestions.
            store: The VectorStore instance (needed for fuzzy helper init).

        Returns:
            List of search results with scores.
        """
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
        return await self.search_from_request(request, store=store)

    # -----------------------------------------------------------------
    # search_paginated()
    # -----------------------------------------------------------------

    async def search_paginated(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        *,
        language: str | None = None,
        chunk_type: str | None = None,
        path_pattern: str | None = None,
        use_fuzzy: bool = False,
        fuzzy_weight: float = 0.3,
        cursor: str | None = None,
        profile: SearchProfile | str | None = None,
        min_similarity: float | None = None,
    ) -> SearchResultPage:
        """Search for similar code chunks with pagination support."""
        from local_deepwiki.core.fuzzy_search import (
            extract_highlights,
            filter_by_path,
            rerank_with_fuzzy,
        )

        table = self._get_table()
        if table is None:
            logger.debug("No table found for search")
            return SearchResultPage(
                results=[],
                total=0,
                offset=offset,
                limit=limit,
                has_more=False,
            )

        resolved_profile, profile_config = self.resolve_search_profile(profile)
        effective_min_similarity = (
            min_similarity
            if min_similarity is not None
            else profile_config.min_similarity
        )

        logger.debug(
            "Paginated search for: '%s...' limit=%d offset=%d profile=%s",
            query[:50],
            limit,
            offset,
            resolved_profile.value,
        )

        # Parse cursor if provided (format: "offset:{number}")
        if cursor:
            try:
                if cursor.startswith("offset:"):
                    offset = int(cursor[7:])
            except (ValueError, IndexError):
                logger.warning(
                    "Invalid cursor format: %s, using offset=%d", cursor, offset
                )

        query_embedding = (await self._embedding_provider.embed([query]))[0]

        filters = self.build_search_filters(language, chunk_type)
        filter_expr = " AND ".join(filters) if filters else None

        # Fetch extra candidates for total count estimation
        base_count_limit = int(1000 * profile_config.fetch_multiplier)
        count_limit = offset + limit + base_count_limit
        count_search = table.search(query_embedding).limit(count_limit)
        if filter_expr:
            count_search = count_search.where(filter_expr)
        all_results = count_search.to_list()

        # Apply similarity threshold filtering
        all_results = [
            row
            for row in all_results
            if (1.0 - row.get("_distance", 0) ** 2 / 2.0) >= effective_min_similarity
        ]
        total_estimate = len(all_results)

        # Apply path pattern filter for accurate count
        if path_pattern:
            filtered_results = []
            for row in all_results:
                chunk = self._row_to_chunk(row)
                if filter_by_path(
                    [SearchResult(chunk=chunk, score=0, highlights=[])], path_pattern
                ):
                    filtered_results.append(row)
            all_results = filtered_results
            total_estimate = len(all_results)

        # Apply pagination and convert
        paginated_rows = all_results[offset : offset + limit]
        search_results = self.convert_results_to_search_results(
            paginated_rows,
            effective_min_similarity,
        )

        # Apply fuzzy re-ranking if requested
        if use_fuzzy and search_results:
            search_results = rerank_with_fuzzy(search_results, query, fuzzy_weight)
            for result in search_results:
                result.highlights = extract_highlights(result.chunk.content, query)

        has_more = offset + limit < total_estimate
        next_cursor = f"offset:{offset + limit}" if has_more else None

        return SearchResultPage(
            results=search_results,
            total=total_estimate,
            offset=offset,
            limit=limit,
            has_more=has_more,
            cursor=next_cursor,
        )

    # -----------------------------------------------------------------
    # Feedback and stats
    # -----------------------------------------------------------------

    def record_feedback(self, feedback: SearchFeedback) -> None:
        """Record user feedback on a search result."""
        self._adaptive_searcher.record_feedback(feedback)

    @property
    def adaptive_search_stats(self) -> dict[str, Any]:
        """Get statistics about adaptive search performance."""
        return {
            "query_history_size": len(self._adaptive_searcher._query_history),
            "feedback_stats": self._adaptive_searcher.get_feedback_stats(),
            "adaptive_search_enabled": self._adaptive_search_enabled,
            "default_profile": self._default_search_profile.value,
        }
