"""SearchMixin — vector search, pagination, fuzzy re-ranking, and adaptive search."""

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

if TYPE_CHECKING:
    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper
    from local_deepwiki.core.vectorstore.store import VectorStore

logger = get_logger(__name__)


class SearchMixin:
    """Mixin providing search, pagination, feedback, and adaptive search methods."""

    # -- Type stubs so IDEs know about attributes set by VectorStore.__init__ --
    if TYPE_CHECKING:
        _table: Any
        _default_search_profile: SearchProfile
        _search_cache: Any
        _fuzzy_search_config: Any
        _fuzzy_search_helper: FuzzySearchHelper | None
        _adaptive_search_enabled: bool
        _adaptive_searcher: Any
        _lazy_index_manager: Any
        embedding_provider: Any

        def _get_table(self) -> Any: ...
        def _row_to_chunk(self, row: dict[str, Any]) -> Any: ...

    async def _get_fuzzy_helper(self) -> "FuzzySearchHelper":
        """Get or create the fuzzy search helper.

        Lazily initializes and builds the fuzzy search helper when first needed.
        The helper indexes all function/class/method names for fast fuzzy matching.

        Returns:
            FuzzySearchHelper instance with built name index.
        """
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        if self._fuzzy_search_helper is None:
            self._fuzzy_search_helper = FuzzySearchHelper(cast("VectorStore", self))

        # Build index if not already built
        if not self._fuzzy_search_helper.is_built:
            await self._fuzzy_search_helper.build_name_index()

        return self._fuzzy_search_helper

    # -----------------------------------------------------------------
    # Shared helpers for search() and search_paginated()
    # -----------------------------------------------------------------

    def _resolve_search_profile(
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
    def _build_search_filters(
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

    def _compute_fetch_limit(
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

    def _convert_results_to_search_results(
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

    async def _generate_suggestions(
        self,
        query: str,
        search_results: list[SearchResult],
    ) -> list[str] | None:
        """Generate 'Did you mean?' suggestions for poor-quality results."""
        fuzzy_config = self._fuzzy_search_config
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

        if not (
            fuzzy_config.enable_auto_fuzzy
            and should_auto_enable_fuzzy(
                search_results, fuzzy_config.auto_fuzzy_threshold
            )
        ):
            return None
        try:
            fuzzy_helper = await self._get_fuzzy_helper()
            suggestions = fuzzy_helper.generate_suggestions(
                query,
                search_results,
                threshold=fuzzy_config.suggestion_threshold,
                max_suggestions=fuzzy_config.max_suggestions,
            )
            if suggestions:
                logger.debug("Generated suggestions: %s", suggestions)
            return suggestions or None
        except (RuntimeError, OSError, ValueError, KeyError) as e:
            # RuntimeError: LanceDB/vector store failures
            # OSError: File system issues
            # ValueError/KeyError: Invalid fuzzy search data
            logger.warning("Failed to generate suggestions: %s", e)
            return None

    # -----------------------------------------------------------------
    # search()
    # -----------------------------------------------------------------

    async def search(
        self,
        query: str,
        limit: int = 10,
        *,
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

        Args:
            query: Search query text.
            limit: Maximum number of results.
            language: Optional language filter (e.g., "python", "typescript").
            chunk_type: Optional chunk type filter (e.g., "function", "class", "method").
            path_pattern: Optional file path pattern filter (e.g., "src/**/*.py").
            use_fuzzy: Whether to use fuzzy matching to re-rank results.
            fuzzy_weight: Weight for fuzzy score when use_fuzzy is True (0.0-1.0).
            profile: Search profile for precision/recall trade-off.
                Can be SearchProfile enum or string ("fast", "balanced", "thorough").
                If None, uses the store's default profile.
            min_similarity: Minimum similarity threshold override.
                Results below this score are filtered out.
                If None, uses the profile's default threshold.
            auto_suggest: Whether to generate "Did you mean?" suggestions when
                results are poor quality. Defaults to True.

        Returns:
            List of search results with scores. When results are poor quality
            and auto_suggest is True, the first result will include suggestions
            in the `suggestions` field.
        """
        from local_deepwiki.core.fuzzy_search import (
            extract_highlights,
            filter_by_path,
            rerank_with_fuzzy,
            should_auto_enable_fuzzy,
        )

        table = self._get_table()
        if table is None:
            logger.debug("No table found for search")
            return []

        resolved_profile, profile_config = self._resolve_search_profile(profile)
        effective_min_similarity = (
            min_similarity
            if min_similarity is not None
            else profile_config.min_similarity
        )

        logger.debug(
            "Searching for: '%s...' limit=%d profile=%s min_sim=%s",
            query[:50],
            limit,
            resolved_profile.value,
            effective_min_similarity,
        )

        query_embedding = (await self.embedding_provider.embed([query]))[0]

        # Build cache filter key (only cache-relevant filters, not path_pattern/fuzzy)
        filters = self._build_search_filters(language, chunk_type)
        cache_filters: dict[str, Any] = {
            "limit": limit,
            "profile": resolved_profile.value,
            "min_similarity": effective_min_similarity,
        }
        if language:
            cache_filters["language"] = language
        if chunk_type:
            cache_filters["chunk_type"] = chunk_type

        # Try to get cached results (only for non-fuzzy, non-path-pattern searches)
        use_cache = not use_fuzzy and not path_pattern
        if use_cache:
            cached_results = self._search_cache.get(query_embedding, cache_filters)
            if cached_results is not None:
                return cached_results

        fetch_limit = self._compute_fetch_limit(
            limit,
            profile_config,
            query,
            needs_extra=bool(path_pattern or use_fuzzy),
        )

        # Build search query
        search = table.search(query_embedding).limit(fetch_limit)
        if filters:
            search = search.where(" AND ".join(filters))

        # Execute search with latency tracking for lazy index management
        search_start = time.monotonic()
        results = search.to_list()
        search_latency_ms = (time.monotonic() - search_start) * 1000

        # Record latency for lazy index decision making
        self._lazy_index_manager.record_search_latency(search_latency_ms)

        # Check if we should trigger lazy index creation based on latency
        if self._lazy_index_manager.should_create_index():
            try:
                task = asyncio.create_task(
                    self._lazy_index_manager.schedule_index_creation()
                )
                task.add_done_callback(_log_task_exception)
            except RuntimeError:
                # No event loop running (e.g., in sync context)
                logger.debug("Cannot schedule lazy index creation: no event loop")

        search_results = self._convert_results_to_search_results(
            results,
            effective_min_similarity,
        )

        # Apply path pattern filter
        if path_pattern:
            search_results = filter_by_path(search_results, path_pattern)

        # Check if auto-fuzzy should be enabled due to poor results
        fuzzy_config = self._fuzzy_search_config
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

        # Apply fuzzy re-ranking (either explicit or auto-enabled)
        if (use_fuzzy or auto_fuzzy_enabled) and search_results:
            search_results = rerank_with_fuzzy(search_results, query, fuzzy_weight)
            for result in search_results:
                result.highlights = extract_highlights(result.chunk.content, query)

        search_results = search_results[:limit]

        # Generate "Did you mean?" suggestions if results are poor
        suggestions: list[str] | None = None
        if auto_suggest:
            suggestions = await self._generate_suggestions(query, search_results)

        # Attach suggestions to the first result
        if suggestions and search_results:
            first_result = search_results[0]
            search_results[0] = SearchResult(
                chunk=first_result.chunk,
                score=first_result.score,
                highlights=first_result.highlights,
                suggestions=suggestions,
            )
        elif suggestions and not search_results:
            logger.debug("No results found, but have suggestions: %s", suggestions)

        # Record search for adaptive learning
        if self._adaptive_search_enabled and search_results:
            avg_score = sum(r.score for r in search_results) / len(search_results)
            self._adaptive_searcher.record_search_quality(
                query, avg_score, len(search_results), fetch_limit
            )

        # Cache results (only for non-fuzzy, non-path-pattern, non-auto-fuzzy searches)
        if use_cache and not auto_fuzzy_enabled:
            self._search_cache.set(
                query, query_embedding, search_results, cache_filters
            )

        return search_results

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
        """Search for similar code chunks with pagination support.

        This method supports both offset-based and cursor-based pagination:
        - Offset-based: Use `offset` parameter (simpler, but may have stability issues)
        - Cursor-based: Use `cursor` parameter (more stable for concurrent updates)

        Args:
            query: Search query text.
            limit: Maximum number of results per page.
            offset: Starting offset for pagination (0-based).
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

        resolved_profile, profile_config = self._resolve_search_profile(profile)
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

        query_embedding = (await self.embedding_provider.embed([query]))[0]

        filters = self._build_search_filters(language, chunk_type)
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
        search_results = self._convert_results_to_search_results(
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

    def record_feedback(self, feedback: SearchFeedback) -> None:
        """Record user feedback on a search result.

        Feedback is used to improve future search results by learning which
        results are actually relevant for specific queries.

        Args:
            feedback: User feedback on a search result.
        """
        self._adaptive_searcher.record_feedback(feedback)

    @property
    def search_profile(self) -> SearchProfile:
        """Get the current default search profile.

        Returns:
            The default SearchProfile used when none is specified.
        """
        return self._default_search_profile

    @search_profile.setter
    def search_profile(self, profile: SearchProfile | str) -> None:
        """Set the default search profile.

        Args:
            profile: The search profile to use as default.
                Can be SearchProfile enum or string ("fast", "balanced", "thorough").

        Raises:
            ValueError: If the profile string is invalid.
        """
        if isinstance(profile, str):
            try:
                self._default_search_profile = SearchProfile(profile.lower())
            except ValueError as e:
                raise ValueError(
                    f"Invalid search profile: {profile}. "
                    f"Valid values: {[p.value for p in SearchProfile]}"
                ) from e
        else:
            self._default_search_profile = profile

    @property
    def adaptive_search_enabled(self) -> bool:
        """Check if adaptive search is enabled.

        Returns:
            True if adaptive search depth estimation is enabled.
        """
        return self._adaptive_search_enabled

    @adaptive_search_enabled.setter
    def adaptive_search_enabled(self, enabled: bool) -> None:
        """Enable or disable adaptive search.

        Args:
            enabled: Whether to enable adaptive search depth estimation.
        """
        self._adaptive_search_enabled = enabled

    @property
    def adaptive_search_stats(self) -> dict[str, Any]:
        """Get statistics about adaptive search performance.

        Returns:
            Dictionary with adaptive search statistics including:
            - query_history_size: Number of queries in history
            - feedback_stats: Feedback collection statistics
        """
        return {
            "query_history_size": len(self._adaptive_searcher._query_history),
            "feedback_stats": self._adaptive_searcher.get_feedback_stats(),
            "adaptive_search_enabled": self._adaptive_search_enabled,
            "default_profile": self._default_search_profile.value,
        }
