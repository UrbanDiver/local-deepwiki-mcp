"""Core VectorStore implementation."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

import lancedb
from lancedb.table import Table

from local_deepwiki.config import (
    EmbeddingBatchConfig,
    FuzzySearchConfig,
    LazyIndexConfig,
    SearchCacheConfig,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, SearchResult
from local_deepwiki.providers.base import EmbeddingProvider

from .cache import AdaptiveSearcher, SearchCache
from .iterators import ChunkIterator, LazyChunkLoader
from .maintenance import LazyIndexManager
from .schema import (
    DEFAULT_MAX_MEMORY_MB,
    ESTIMATED_BYTES_PER_CHUNK,
    SEARCH_PROFILES,
    VALID_CHUNK_TYPES,
    VALID_LANGUAGES,
    BatchEmbeddingResult,
    EmbeddingProgress,
    SearchFeedback,
    SearchProfile,
    SearchResultPage,
)
from .utils import RateLimiter, _row_to_chunk_default, _sanitize_string_value

logger = get_logger(__name__)


class VectorStore:
    """Vector store using LanceDB for code chunk storage and semantic search."""

    TABLE_NAME = "code_chunks"

    def __init__(
        self,
        db_path: Path,
        embedding_provider: EmbeddingProvider,
        search_cache_config: SearchCacheConfig | None = None,
        embedding_batch_config: EmbeddingBatchConfig | None = None,
        lazy_index_config: LazyIndexConfig | None = None,
        fuzzy_search_config: FuzzySearchConfig | None = None,
        default_search_profile: SearchProfile = SearchProfile.BALANCED,
        adaptive_search_enabled: bool = True,
    ):
        """Initialize the vector store.

        Args:
            db_path: Path to the LanceDB database directory.
            embedding_provider: Provider for generating embeddings.
            search_cache_config: Optional search cache configuration.
                If None, uses default SearchCacheConfig.
            embedding_batch_config: Optional embedding batch configuration.
                If None, uses default EmbeddingBatchConfig.
            lazy_index_config: Optional lazy index configuration.
                If None, uses default LazyIndexConfig (lazy indexing enabled).
            fuzzy_search_config: Optional fuzzy search configuration.
                If None, uses default FuzzySearchConfig.
            default_search_profile: Default search profile for precision/recall trade-off.
                Defaults to SearchProfile.BALANCED.
            adaptive_search_enabled: Whether to enable adaptive search depth estimation.
                When enabled, search depth adjusts based on query complexity and history.
        """
        self.db_path = db_path
        self.embedding_provider = embedding_provider
        self._db: lancedb.DBConnection | None = None
        self._table: Table | None = None
        self._lock = threading.RLock()  # Reentrant lock for nested calls

        # Initialize search cache
        if search_cache_config is None:
            search_cache_config = SearchCacheConfig()
        self._search_cache = SearchCache(search_cache_config)

        # Initialize embedding batch config
        if embedding_batch_config is None:
            embedding_batch_config = EmbeddingBatchConfig()
        self._embedding_batch_config = embedding_batch_config

        # Rate limiter (created on-demand if rate limiting is configured)
        self._rate_limiter: RateLimiter | None = None
        if embedding_batch_config.rate_limit_rpm is not None:
            self._rate_limiter = RateLimiter(embedding_batch_config.rate_limit_rpm)

        # Initialize lazy index manager
        self._lazy_index_manager = LazyIndexManager(self, lazy_index_config)

        # Initialize fuzzy search config
        if fuzzy_search_config is None:
            fuzzy_search_config = FuzzySearchConfig()
        self._fuzzy_search_config = fuzzy_search_config

        # Fuzzy search helper (lazy initialized when first needed)
        self._fuzzy_search_helper: "FuzzySearchHelper | None" = None

        # Search profile configuration
        self._default_search_profile = default_search_profile
        self._adaptive_search_enabled = adaptive_search_enabled

        # Initialize adaptive searcher
        self._adaptive_searcher = AdaptiveSearcher()
        self._adaptive_searcher.set_store(self)

    def close(self) -> None:
        """Close the vector store and release all resources.

        Clears internal references to the database connection, table, and
        fuzzy search helper. Invalidates the search cache and resets the
        adaptive searcher state. Safe to call multiple times (idempotent).

        After closing, the VectorStore can still be used -- the lazy
        ``_connect()`` method will re-establish the connection on next access.
        """
        with self._lock:
            self._table = None
            self._db = None
            self._fuzzy_search_helper = None
            self._search_cache.invalidate()
            self._adaptive_searcher.reset()

    def __del__(self) -> None:
        """Safety net to release resources on garbage collection."""
        try:
            self.close()
        except Exception:
            # Keep broad catch: destructor must not fail during interpreter shutdown
            # when objects may already be gone
            pass

    async def __aenter__(self) -> "VectorStore":
        """Enter the async context manager.

        Returns:
            This VectorStore instance.
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the async context manager, closing the store."""
        self.close()

    def _connect(self) -> lancedb.DBConnection:
        """Get or create database connection.

        Thread-safe lazy initialization of the database connection.
        """
        if self._db is None:
            with self._lock:
                # Double-check after acquiring lock to avoid race condition
                if self._db is None:
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    self._db = lancedb.connect(str(self.db_path))
        return self._db

    def _get_table(self) -> Table | None:
        """Get the chunks table if it exists.

        Thread-safe lazy initialization of the table reference.
        """
        if self._table is None:
            with self._lock:
                # Double-check after acquiring lock to avoid race condition
                if self._table is None:
                    db = self._connect()
                    if self.TABLE_NAME in db.list_tables().tables:
                        self._table = db.open_table(self.TABLE_NAME)
                        # Ensure indexes exist (may have been created by older code version)
                        self._ensure_indexes()
        return self._table

    async def _get_fuzzy_helper(self) -> "FuzzySearchHelper":
        """Get or create the fuzzy search helper.

        Lazily initializes and builds the fuzzy search helper when first needed.
        The helper indexes all function/class/method names for fast fuzzy matching.

        Returns:
            FuzzySearchHelper instance with built name index.
        """
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        if self._fuzzy_search_helper is None:
            self._fuzzy_search_helper = FuzzySearchHelper(self)

        # Build index if not already built
        if not self._fuzzy_search_helper.is_built:
            await self._fuzzy_search_helper.build_name_index()

        return self._fuzzy_search_helper

    def _ensure_indexes(self) -> None:
        """Ensure all indexes exist, creating them if needed."""
        if self._table is not None:
            from .indexes import ensure_indexes

            ensure_indexes(self._table, self._lazy_index_manager)

    def _create_index_safe(self, column: str) -> None:
        """Safely create a scalar index on a column."""
        if self._table is not None:
            from .indexes import create_index_safe

            create_index_safe(self._table, column)

    def _create_scalar_indexes(self) -> None:
        """Create scalar indexes for efficient lookups."""
        if self._table is not None:
            from .indexes import create_scalar_indexes

            create_scalar_indexes(self._table)

    def _create_vector_index(self, num_rows: int) -> None:
        """Create a vector index for faster semantic search."""
        if self._table is not None:
            from .indexes import create_vector_index

            create_vector_index(self._table, num_rows, self._lazy_index_manager)

    def _is_local_provider(self) -> bool:
        """Check if the embedding provider is local (sentence-transformers)."""
        from .embedding import is_local_provider

        return is_local_provider(self.embedding_provider)

    def _get_optimal_batch_config(self) -> tuple[int, int]:
        """Get optimal batch size and concurrency based on provider type."""
        from .embedding import get_optimal_batch_config

        return get_optimal_batch_config(
            self._embedding_batch_config, self.embedding_provider
        )

    async def _embed_single_batch_with_retry(
        self,
        batch_index: int,
        texts: list[str],
        progress: EmbeddingProgress,
        semaphore: asyncio.Semaphore,
    ) -> BatchEmbeddingResult:
        """Embed a single batch with retry logic and rate limiting."""
        from .embedding import embed_single_batch_with_retry

        return await embed_single_batch_with_retry(
            batch_index,
            texts,
            self.embedding_provider,
            self._embedding_batch_config,
            self._rate_limiter,
            progress,
            semaphore,
        )

    async def _batch_embed(
        self,
        texts: list[str],
        batch_size: int | None = None,
        log_progress: bool = False,
    ) -> list[list[float]]:
        """Generate embeddings in parallel batches."""
        from .embedding import batch_embed

        return await batch_embed(
            texts,
            self.embedding_provider,
            self._embedding_batch_config,
            self._rate_limiter,
            batch_size,
            log_progress,
        )

    async def _batch_embed_sequential(
        self, texts: list[str], batch_size: int, log_progress: bool = False
    ) -> list[list[float]]:
        """Generate embeddings in sequential batches (legacy method)."""
        from .embedding import batch_embed_sequential

        return await batch_embed_sequential(
            texts, self.embedding_provider, batch_size, log_progress
        )

    async def create_or_update_table(
        self, chunks: list[CodeChunk], embedding_batch_size: int = 100
    ) -> int:
        """Create or update the vector table with code chunks.

        Args:
            chunks: List of code chunks to store.
            embedding_batch_size: Batch size for embedding generation to avoid OOM.

        Returns:
            Number of chunks stored.
        """
        if not chunks:
            logger.debug("No chunks to store, skipping table creation")
            return 0

        logger.info("Creating/updating vector table with %s chunks", len(chunks))
        db = self._connect()

        # Generate embeddings in batches to avoid OOM and API limits
        texts = [self._chunk_to_text(chunk) for chunk in chunks]
        embeddings = await self._batch_embed(
            texts, embedding_batch_size, log_progress=True
        )

        # Prepare data for LanceDB
        data = [
            chunk.to_vector_record(vector=embedding)
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # Reset lazy index manager state since we're creating a fresh table
        self._lazy_index_manager.reset()

        # Drop existing table and create new one (thread-safe)
        with self._lock:
            if self.TABLE_NAME in db.list_tables().tables:
                db.drop_table(self.TABLE_NAME)

            self._table = db.create_table(self.TABLE_NAME, data)

        # Invalidate search cache since index has changed
        self._search_cache.invalidate()

        # Create scalar indexes for efficient lookups
        self._create_scalar_indexes()

        # Handle vector index creation based on lazy index config
        num_rows = len(data)
        if self._lazy_index_manager.config.enabled:
            # Lazy indexing: mark as pending if table is large enough
            if num_rows >= self._lazy_index_manager.config.min_rows:
                self._lazy_index_manager.mark_index_pending()
                logger.info(
                    "Vector index creation deferred (lazy mode): %d rows. "
                    "Index will be created in background or on-demand.",
                    num_rows,
                )
        else:
            # Eager indexing: create immediately
            self._create_vector_index(num_rows)

        return len(data)

    async def add_chunks(
        self, chunks: list[CodeChunk], embedding_batch_size: int = 100
    ) -> int:
        """Add chunks to existing table.

        Args:
            chunks: List of code chunks to add.
            embedding_batch_size: Batch size for embedding generation to avoid OOM.

        Returns:
            Number of chunks added.
        """
        if not chunks:
            return 0

        logger.debug("Adding %s chunks to existing table", len(chunks))
        table = self._get_table()
        if table is None:
            return await self.create_or_update_table(chunks, embedding_batch_size)

        # Generate embeddings in batches to avoid OOM and API limits
        texts = [self._chunk_to_text(chunk) for chunk in chunks]
        embeddings = await self._batch_embed(texts, embedding_batch_size)

        # Prepare data
        data = [
            chunk.to_vector_record(vector=embedding)
            for chunk, embedding in zip(chunks, embeddings)
        ]

        table.add(data)

        # Invalidate search cache since index has changed
        self._search_cache.invalidate()

        # Mark vector index as needing rebuild after data changes
        num_rows = table.count_rows()
        if (
            self._lazy_index_manager.config.enabled
            and num_rows >= self._lazy_index_manager.config.min_rows
        ):
            self._lazy_index_manager.mark_index_pending()

        return len(data)

    async def search(
        self,
        query: str,
        limit: int = 10,
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

        # Resolve search profile
        if profile is None:
            resolved_profile = self._default_search_profile
        elif isinstance(profile, str):
            try:
                resolved_profile = SearchProfile(profile.lower())
            except ValueError:
                logger.warning("Invalid search profile '%s', using default", profile)
                resolved_profile = self._default_search_profile
        else:
            resolved_profile = profile

        profile_config = SEARCH_PROFILES[resolved_profile]

        # Resolve minimum similarity threshold
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

        # Generate query embedding
        query_embedding = (await self.embedding_provider.embed([query]))[0]

        # Build cache filter key (only cache-relevant filters, not path_pattern/fuzzy)
        cache_filters: dict[str, Any] = {
            "limit": limit,
            "profile": resolved_profile.value,
            "min_similarity": effective_min_similarity,
        }
        if language:
            if language not in VALID_LANGUAGES:
                raise ValueError(f"Invalid language filter: {language}")
            cache_filters["language"] = language
        if chunk_type:
            if chunk_type not in VALID_CHUNK_TYPES:
                raise ValueError(f"Invalid chunk_type filter: {chunk_type}")
            cache_filters["chunk_type"] = chunk_type

        # Try to get cached results (only for non-fuzzy, non-path-pattern searches)
        # Fuzzy and path_pattern modify results after retrieval, so we can't cache them directly
        use_cache = not use_fuzzy and not path_pattern
        if use_cache:
            cached_results = self._search_cache.get(query_embedding, cache_filters)
            if cached_results is not None:
                return cached_results

        # Calculate fetch limit based on profile and adaptive search
        base_fetch_multiplier = profile_config.fetch_multiplier
        if path_pattern or use_fuzzy:
            # Need more candidates for post-filtering
            base_fetch_multiplier = max(base_fetch_multiplier, 3.0)

        # Use adaptive search depth if enabled
        if self._adaptive_search_enabled:
            adaptive_depth = self._adaptive_searcher.estimate_optimal_depth(
                query, limit
            )
            fetch_limit = max(
                int(limit * base_fetch_multiplier),
                adaptive_depth,
            )
        else:
            fetch_limit = int(limit * base_fetch_multiplier)

        # Cap fetch limit based on rerank candidates from profile
        fetch_limit = min(fetch_limit, profile_config.rerank_candidates)

        # Build search query
        search = table.search(query_embedding).limit(fetch_limit)

        # Apply filters with validation to prevent injection
        filters = []
        if language:
            filters.append(f"language = '{language}'")
        if chunk_type:
            filters.append(f"chunk_type = '{chunk_type}'")

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
            # Schedule background index creation (non-blocking)
            try:
                asyncio.create_task(self._lazy_index_manager.schedule_index_creation())
            except RuntimeError:
                # No event loop running (e.g., in sync context)
                logger.debug("Cannot schedule lazy index creation: no event loop")

        # Convert to SearchResult objects and apply similarity threshold
        search_results = []
        for row in results:
            # LanceDB returns L2 distance. For normalized vectors (norm=1),
            # L2 distance d relates to cosine similarity s by: s = 1 - d^2/2.
            # L2 range [0, 2] maps to cosine similarity [1, -1].
            dist = row.get("_distance", 0)
            score = 1.0 - dist * dist / 2.0
            # Apply minimum similarity threshold
            if score < effective_min_similarity:
                continue
            chunk = self._row_to_chunk(row)
            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=score,
                    highlights=[],
                )
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

            # Add highlights for fuzzy matches
            for result in search_results:
                result.highlights = extract_highlights(result.chunk.content, query)

        # Limit results to requested amount
        search_results = search_results[:limit]

        # Generate "Did you mean?" suggestions if results are poor and auto_suggest is enabled
        suggestions: list[str] | None = None
        if (
            auto_suggest
            and fuzzy_config.enable_auto_fuzzy
            and should_auto_enable_fuzzy(
                search_results, fuzzy_config.auto_fuzzy_threshold
            )
        ):
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
            except (RuntimeError, OSError, ValueError, KeyError) as e:
                # RuntimeError: LanceDB/vector store failures
                # OSError: File system issues
                # ValueError/KeyError: Invalid fuzzy search data
                logger.warning("Failed to generate suggestions: %s", e)

        # Attach suggestions to the first result if we have any
        if suggestions and search_results:
            # Create a new SearchResult with suggestions attached
            first_result = search_results[0]
            search_results[0] = SearchResult(
                chunk=first_result.chunk,
                score=first_result.score,
                highlights=first_result.highlights,
                suggestions=suggestions,
            )
        elif suggestions and not search_results:
            # Create a placeholder result with suggestions when no results found
            # This allows the caller to show "Did you mean?" even with empty results
            # We don't add a fake result, but we can log for now
            logger.debug("No results found, but have suggestions: %s", suggestions)

        # Record search for adaptive learning
        if self._adaptive_search_enabled and search_results:
            # Estimate quality based on score distribution
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

    async def search_paginated(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
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

        # Resolve search profile
        if profile is None:
            resolved_profile = self._default_search_profile
        elif isinstance(profile, str):
            try:
                resolved_profile = SearchProfile(profile.lower())
            except ValueError:
                logger.warning("Invalid search profile '%s', using default", profile)
                resolved_profile = self._default_search_profile
        else:
            resolved_profile = profile

        profile_config = SEARCH_PROFILES[resolved_profile]

        # Resolve minimum similarity threshold
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

        # Generate query embedding
        query_embedding = (await self.embedding_provider.embed([query]))[0]

        # Build filter expressions
        filters = []
        if language:
            if language not in VALID_LANGUAGES:
                raise ValueError(f"Invalid language filter: {language}")
            filters.append(f"language = '{language}'")
        if chunk_type:
            if chunk_type not in VALID_CHUNK_TYPES:
                raise ValueError(f"Invalid chunk_type filter: {chunk_type}")
            filters.append(f"chunk_type = '{chunk_type}'")

        filter_expr = " AND ".join(filters) if filters else None

        # For total count, we need to fetch more results (expensive but accurate)
        # In production, you might want to cache this or use approximate counts
        # Profile affects how many candidates we consider
        base_count_limit = int(1000 * profile_config.fetch_multiplier)
        count_limit = offset + limit + base_count_limit
        count_search = table.search(query_embedding).limit(count_limit)
        if filter_expr:
            count_search = count_search.where(filter_expr)
        all_results = count_search.to_list()

        # Apply similarity threshold filtering
        # Use same L2-to-cosine conversion as search(): s = 1 - d^2/2
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

        # Apply pagination
        paginated_results = all_results[offset : offset + limit]

        # Convert to SearchResult objects
        search_results = []
        for row in paginated_results:
            chunk = self._row_to_chunk(row)
            dist = row.get("_distance", 0)
            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=1.0 - dist * dist / 2.0,
                    highlights=[],
                )
            )

        # Apply fuzzy re-ranking if requested
        if use_fuzzy and search_results:
            search_results = rerank_with_fuzzy(search_results, query, fuzzy_weight)
            for result in search_results:
                result.highlights = extract_highlights(result.chunk.content, query)

        # Determine if there are more results
        has_more = offset + limit < total_estimate

        # Generate cursor for next page
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

    def get_search_profile(self) -> SearchProfile:
        """Get the current default search profile.

        Returns:
            The default SearchProfile used when none is specified.
        """
        return self._default_search_profile

    def set_search_profile(self, profile: SearchProfile | str) -> None:
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
            except ValueError:
                raise ValueError(
                    f"Invalid search profile: {profile}. "
                    f"Valid values: {[p.value for p in SearchProfile]}"
                )
        else:
            self._default_search_profile = profile

    def get_adaptive_search_enabled(self) -> bool:
        """Check if adaptive search is enabled.

        Returns:
            True if adaptive search depth estimation is enabled.
        """
        return self._adaptive_search_enabled

    def set_adaptive_search_enabled(self, enabled: bool) -> None:
        """Enable or disable adaptive search.

        Args:
            enabled: Whether to enable adaptive search depth estimation.
        """
        self._adaptive_search_enabled = enabled

    def get_adaptive_search_stats(self) -> dict[str, Any]:
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

    async def get_chunk_by_id(self, chunk_id: str) -> CodeChunk | None:
        """Get a specific chunk by ID.

        Args:
            chunk_id: The chunk ID.

        Returns:
            The CodeChunk or None if not found.
        """
        table = self._get_table()
        if table is None:
            return None

        safe_id = _sanitize_string_value(chunk_id)
        results = table.search().where(f"id = '{safe_id}'").limit(1).to_list()
        if not results:
            return None

        return self._row_to_chunk(results[0])

    async def get_chunks_by_file(self, file_path: str) -> list[CodeChunk]:
        """Get all chunks for a specific file.

        Args:
            file_path: The file path.

        Returns:
            List of CodeChunks for the file.
        """
        table = self._get_table()
        if table is None:
            return []

        safe_path = _sanitize_string_value(file_path)
        results = table.search().where(f"file_path = '{safe_path}'").to_list()
        return [self._row_to_chunk(row) for row in results]

    def get_all_chunks(
        self,
        batch_size: int | None = None,
        language: str | None = None,
        chunk_type: str | None = None,
    ) -> Iterator[CodeChunk]:
        """Lazily iterate over all chunks in the vector store.

        Delegates to LazyChunkLoader for memory-efficient batch iteration.

        Args:
            batch_size: Batch size for loading. If None, uses optimal size.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.

        Yields:
            CodeChunk objects.
        """
        loader = LazyChunkLoader(self)
        yield from loader.get_all_chunks(
            batch_size=batch_size,
            language=language,
            chunk_type=chunk_type,
        )

    async def delete_chunks_by_file(self, file_path: str) -> int:
        """Delete all chunks for a specific file.

        Args:
            file_path: The file path.

        Returns:
            Number of chunks deleted (estimated, may be 0 if table doesn't exist).
        """
        table = self._get_table()
        if table is None:
            return 0

        # Sanitize path to prevent injection
        safe_path = _sanitize_string_value(file_path)

        # Delete matching rows directly without pre-counting
        # LanceDB delete is idempotent - no error if no rows match
        table.delete(f"file_path = '{safe_path}'")

        # Invalidate search cache since index has changed
        self._search_cache.invalidate()

        # Return 0 since we don't know exact count without expensive query
        # Callers that need counts should use get_chunks_by_file first
        return 0

    async def delete_chunks_by_files(self, file_paths: list[str]) -> int:
        """Delete all chunks for multiple files in a single batch operation.

        This is more efficient than calling delete_chunks_by_file in a loop
        as it constructs a single filter expression for all files.

        Args:
            file_paths: List of file paths to delete chunks for.

        Returns:
            Number of file paths processed (not chunk count).
        """
        if not file_paths:
            return 0

        table = self._get_table()
        if table is None:
            return 0

        # Build a single OR filter for all file paths
        # Sanitize each path to prevent injection
        safe_paths = [_sanitize_string_value(path) for path in file_paths]

        # Use IN clause for efficiency: file_path IN ('path1', 'path2', ...)
        # LanceDB supports SQL-like syntax
        paths_list = ", ".join(f"'{path}'" for path in safe_paths)
        filter_expr = f"file_path IN ({paths_list})"

        # Single delete operation for all matching files
        table.delete(filter_expr)

        # Invalidate search cache since index has changed
        self._search_cache.invalidate()

        logger.debug("Batch deleted chunks for %s files", len(file_paths))
        return len(file_paths)

    def get_main_definition_lines(self) -> dict[str, tuple[int, int]]:
        """Get line range of main definition (first class or function) per file.

        Uses a single LanceDB query for memory-efficient access instead of
        loading the entire table into a DataFrame.

        Returns:
            Dict mapping file_path to (start_line, end_line) tuple.
        """
        table = self._get_table()
        if table is None:
            return {}

        # Single query for both classes and functions
        rows = (
            table.search()
            .where("chunk_type IN ('class', 'function')")
            .select(["file_path", "start_line", "end_line", "chunk_type"])
            .limit(10000)
            .to_list()
        )

        result: dict[str, tuple[int, int]] = {}
        result_types: dict[str, str] = {}  # Track chunk type for priority

        for row in rows:
            file_path = str(row["file_path"])
            chunk_type = str(row["chunk_type"])
            start_line = int(row["start_line"])
            end_line = int(row["end_line"])

            if file_path not in result:
                # First definition for this file
                result[file_path] = (start_line, end_line)
                result_types[file_path] = chunk_type
            elif chunk_type == "class" and result_types[file_path] == "function":
                # Class takes priority over function if it starts earlier
                if start_line < result[file_path][0]:
                    result[file_path] = (start_line, end_line)
                    result_types[file_path] = chunk_type
            elif chunk_type == result_types[file_path]:
                # Same type - keep the one that starts earlier
                if start_line < result[file_path][0]:
                    result[file_path] = (start_line, end_line)

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the vector store.

        Uses PyArrow for memory-efficient aggregation instead of loading
        the entire table into pandas.

        Returns:
            Dictionary with store statistics.
        """
        import pyarrow.compute as pc

        table = self._get_table()
        if table is None:
            return {"total_chunks": 0, "languages": {}, "chunk_types": {}, "files": 0}

        # Use count_rows() for total - doesn't load data
        total_chunks = table.count_rows()

        # Use arrow for efficient aggregation
        arrow_table = table.to_arrow()

        # Count by language
        lang_counts = pc.value_counts(arrow_table.column("language"))
        languages = {
            str(k): int(v)
            for k, v in zip(lang_counts.field("values"), lang_counts.field("counts"))
        }

        # Count by chunk type
        type_counts = pc.value_counts(arrow_table.column("chunk_type"))
        chunk_types = {
            str(k): int(v)
            for k, v in zip(type_counts.field("values"), type_counts.field("counts"))
        }

        # Count unique files
        unique_files = pc.unique(arrow_table.column("file_path"))

        return {
            "total_chunks": total_chunks,
            "languages": languages,
            "chunk_types": chunk_types,
            "files": len(unique_files),
        }

    def get_stats_streaming(self, batch_size: int = 10000) -> dict[str, Any]:
        """Get statistics about the vector store using streaming aggregation.

        This method processes data in batches to avoid loading all rows into memory.
        Suitable for very large datasets (1M+ chunks) where get_stats() might OOM.

        Args:
            batch_size: Number of rows to process per batch.

        Returns:
            Dictionary with store statistics.
        """
        import pyarrow.compute as pc

        table = self._get_table()
        if table is None:
            return {"total_chunks": 0, "languages": {}, "chunk_types": {}, "files": 0}

        # Use count_rows() for total - doesn't load data
        total_chunks = table.count_rows()

        if total_chunks == 0:
            return {"total_chunks": 0, "languages": {}, "chunk_types": {}, "files": 0}

        # For small tables, use the regular method
        if total_chunks <= batch_size:
            return self.get_stats()

        # Fetch all rows once with columnar projection (avoids O(n^2) offset re-fetching)
        languages: dict[str, int] = {}
        chunk_types: dict[str, int] = {}
        file_set: set[str] = set()

        columns = ["language", "chunk_type", "file_path"]
        all_rows = table.search().select(columns).limit(total_chunks).to_list()

        for i, row in enumerate(all_rows):
            lang = str(row["language"])
            ctype = str(row["chunk_type"])
            fpath = str(row["file_path"])

            languages[lang] = languages.get(lang, 0) + 1
            chunk_types[ctype] = chunk_types.get(ctype, 0) + 1
            file_set.add(fpath)

            if (i + 1) % 100_000 == 0:
                logger.debug(
                    "Stats streaming progress: %d/%d rows processed",
                    i + 1,
                    total_chunks,
                )

        return {
            "total_chunks": total_chunks,
            "languages": languages,
            "chunk_types": chunk_types,
            "files": len(file_set),
        }

    def get_main_definition_lines_lazy(
        self,
        batch_size: int = 5000,
    ) -> Iterator[tuple[str, tuple[int, int]]]:
        """Lazily get line range of main definition per file.

        This method returns an iterator instead of a full dict, suitable for
        very large repositories where loading all definitions might cause memory issues.

        Args:
            batch_size: Number of rows to process per batch.

        Yields:
            Tuples of (file_path, (start_line, end_line)).
        """
        table = self._get_table()
        if table is None:
            return

        # Use columnar projection for efficiency
        columns = ["file_path", "start_line", "end_line", "chunk_type"]

        # Track results per file as we iterate
        result: dict[str, tuple[int, int]] = {}
        result_types: dict[str, str] = {}

        # Fetch all matching rows once (avoids O(n^2) offset re-fetching)
        total_count = table.count_rows()
        all_rows = (
            table.search()
            .where("chunk_type IN ('class', 'function')")
            .select(columns)
            .limit(total_count)
            .to_list()
        )

        for row in all_rows:
            file_path = str(row["file_path"])
            chunk_type = str(row["chunk_type"])
            start_line = int(row["start_line"])
            end_line = int(row["end_line"])

            if file_path not in result:
                result[file_path] = (start_line, end_line)
                result_types[file_path] = chunk_type
            elif chunk_type == "class" and result_types[file_path] == "function":
                if start_line < result[file_path][0]:
                    result[file_path] = (start_line, end_line)
                    result_types[file_path] = chunk_type
            elif chunk_type == result_types[file_path]:
                if start_line < result[file_path][0]:
                    result[file_path] = (start_line, end_line)

        # Yield all results
        for file_path, lines in result.items():
            yield file_path, lines

    def get_lazy_chunk_loader(
        self,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
    ) -> LazyChunkLoader:
        """Get a LazyChunkLoader for memory-efficient chunk iteration.

        Args:
            max_memory_mb: Maximum memory budget in MB for batch operations.

        Returns:
            LazyChunkLoader instance configured for this store.
        """
        return LazyChunkLoader(self, max_memory_mb=max_memory_mb)

    def get_chunk_iterator(
        self,
        batch_size: int = 1000,
        language: str | None = None,
        chunk_type: str | None = None,
    ) -> ChunkIterator | None:
        """Get a ChunkIterator for batch iteration over chunks.

        Args:
            batch_size: Number of chunks per batch.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.

        Returns:
            ChunkIterator instance, or None if no table exists.
        """
        table = self._get_table()
        if table is None:
            return None

        # Build filter expression
        filters = []
        if language:
            if language not in VALID_LANGUAGES:
                raise ValueError(f"Invalid language filter: {language}")
            filters.append(f"language = '{language}'")
        if chunk_type:
            if chunk_type not in VALID_CHUNK_TYPES:
                raise ValueError(f"Invalid chunk_type filter: {chunk_type}")
            filters.append(f"chunk_type = '{chunk_type}'")

        filter_expr = " AND ".join(filters) if filters else None

        return ChunkIterator(
            table=table,
            batch_size=batch_size,
            filter_expr=filter_expr,
            row_to_chunk_fn=self._row_to_chunk,
        )

    def _row_to_chunk(self, row: dict[str, Any]) -> CodeChunk:
        """Convert a LanceDB row to a CodeChunk object.

        Args:
            row: Dictionary from LanceDB query result.

        Returns:
            CodeChunk object.
        """
        return CodeChunk(
            id=row["id"],
            file_path=row["file_path"],
            language=row["language"],
            chunk_type=row["chunk_type"],
            name=row["name"] or None,
            content=row["content"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            docstring=row["docstring"] or None,
            parent_name=row["parent_name"] or None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _chunk_to_text(self, chunk: CodeChunk) -> str:
        """Convert a chunk to text for embedding.

        Args:
            chunk: The code chunk.

        Returns:
            Text representation for embedding.
        """
        parts = []

        # Add context about the chunk
        if chunk.name:
            parts.append(f"{chunk.chunk_type.value}: {chunk.name}")

        if chunk.parent_name:
            parts.append(f"in {chunk.parent_name}")

        parts.append(f"({chunk.language.value})")

        # Add docstring if present
        if chunk.docstring:
            parts.append(f"\n{chunk.docstring}")

        # Add the actual code
        parts.append(f"\n{chunk.content}")

        return " ".join(parts)

    def invalidate_search_cache(self) -> int:
        """Invalidate all search cache entries.

        Call this when the index is updated externally or when you want
        to force fresh search results.

        Returns:
            Number of cache entries invalidated.
        """
        return self._search_cache.invalidate()

    def get_search_cache_stats(self) -> dict[str, Any]:
        """Get search cache statistics.

        Returns:
            Dictionary with cache statistics including:
            - enabled: Whether caching is enabled
            - entries: Current number of cached entries
            - max_entries: Maximum allowed entries
            - ttl_seconds: Cache entry TTL
            - similarity_threshold: Minimum similarity for cache hit
            - hits: Number of cache hits
            - misses: Number of cache misses
            - invalidations: Number of cache invalidations
            - hit_rate: Cache hit rate (0.0-1.0)
        """
        return self._search_cache.get_stats()

    def get_embedding_batch_config(self) -> dict[str, Any]:
        """Get embedding batch configuration.

        Returns:
            Dictionary with batch configuration including:
            - batch_size: Texts per batch
            - concurrency: Parallel batch limit
            - rate_limit_rpm: Rate limit (requests per minute)
            - retry_max_attempts: Maximum retry attempts
            - retry_base_delay: Base delay for retries
            - is_local_provider: Whether using local embeddings
            - optimal_batch_size: Calculated optimal batch size
            - optimal_concurrency: Calculated optimal concurrency
        """
        optimal_batch_size, optimal_concurrency = self._get_optimal_batch_config()
        return {
            "batch_size": self._embedding_batch_config.batch_size,
            "concurrency": self._embedding_batch_config.concurrency,
            "rate_limit_rpm": self._embedding_batch_config.rate_limit_rpm,
            "retry_max_attempts": self._embedding_batch_config.retry_max_attempts,
            "retry_base_delay": self._embedding_batch_config.retry_base_delay,
            "is_local_provider": self._is_local_provider(),
            "optimal_batch_size": optimal_batch_size,
            "optimal_concurrency": optimal_concurrency,
        }

    # ---- Lazy Index Manager Methods ----

    @property
    def lazy_index_manager(self) -> LazyIndexManager:
        """Get the lazy index manager.

        Returns:
            The LazyIndexManager instance for this vector store.
        """
        return self._lazy_index_manager

    def get_lazy_index_stats(self) -> dict[str, Any]:
        """Get statistics about lazy index creation.

        Returns:
            Dictionary with lazy index statistics including:
            - enabled: Whether lazy indexing is enabled
            - index_pending: Whether index creation is pending
            - index_created: Whether index has been created
            - creation_in_progress: Whether creation is currently running
            - latency_threshold_ms: Latency threshold for triggering creation
            - min_rows: Minimum rows for index creation
            - average_latency_ms: Average search latency
            - latency_samples: Number of latency samples
            - should_create_index: Whether index should be created now
        """
        return self._lazy_index_manager.get_stats()

    async def schedule_lazy_index_creation(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Schedule vector index creation as a background task.

        This is useful for triggering index creation after initial indexing
        completes. If index creation is already in progress or completed,
        this is a no-op.

        Args:
            progress_callback: Optional callback for progress updates.
        """
        await self._lazy_index_manager.schedule_index_creation(progress_callback)

    async def wait_for_vector_index(self, timeout: float | None = None) -> bool:
        """Wait for the vector index to be ready.

        Useful when you need to ensure the index is available before
        performing searches that require it.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if index is ready, False if timeout occurred.
        """
        return await self._lazy_index_manager.wait_for_index(timeout)

    async def create_vector_index_now(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Force immediate vector index creation.

        Creates the vector index synchronously. This is useful when you
        need the index to be ready before proceeding with searches.

        Args:
            progress_callback: Optional callback for progress updates.

        Raises:
            RuntimeError: If table doesn't exist or has insufficient rows.
        """
        await self._lazy_index_manager.create_index_now(progress_callback)

    def is_vector_index_ready(self) -> bool:
        """Check if the vector index is ready.

        Returns:
            True if the index has been created and is ready for use.
        """
        return self._lazy_index_manager.is_index_ready()

    def on_vector_index_ready(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when the vector index is ready.

        If the index is already ready, the callback is invoked immediately.

        Args:
            callback: Function to call when index is ready.
        """
        self._lazy_index_manager.on_index_ready(callback)
