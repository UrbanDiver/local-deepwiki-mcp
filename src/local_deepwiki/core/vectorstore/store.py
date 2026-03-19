"""Core VectorStore implementation."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

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
from local_deepwiki.models import CodeChunk
from local_deepwiki.providers.base import EmbeddingProvider

from .cache import AdaptiveSearcher, SearchCache
from .maintenance import LazyIndexManager
from .mixins import LazyIndexMixin, SearchMixin, StatsMixin
from .schema import (
    BatchEmbeddingResult,
    EmbeddingProgress,
    SearchProfile,
)
from .search_engine import SearchEngine
from .utils import RateLimiter, _log_task_exception, _sanitize_string_value

logger = get_logger(__name__)


class VectorStore(SearchMixin, StatsMixin, LazyIndexMixin):
    """Vector store using LanceDB for code chunk storage and semantic search."""

    TABLE_NAME = "code_chunks"

    def __init__(
        self,
        db_path: Path,
        embedding_provider: EmbeddingProvider,
        *,
        search_cache_config: SearchCacheConfig | None = None,
        embedding_batch_config: EmbeddingBatchConfig | None = None,
        lazy_index_config: LazyIndexConfig | None = None,
        fuzzy_search_config: FuzzySearchConfig | None = None,
        default_search_profile: SearchProfile = SearchProfile.BALANCED,
        adaptive_search_enabled: bool = True,
        default_search_mode: str = "vector",
        bm25_weight: float = 0.3,
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

        # Hybrid search configuration
        self._default_search_mode = default_search_mode
        self._bm25_weight = bm25_weight

        # Initialize adaptive searcher
        self._adaptive_searcher = AdaptiveSearcher()
        self._adaptive_searcher.set_store(self)

        # Build the composition-based SearchEngine with explicit deps.
        # SearchMixin methods delegate to this instance.
        self._search_engine = SearchEngine(
            get_table=self._get_table,
            row_to_chunk=self._row_to_chunk,
            embedding_provider=self.embedding_provider,
            get_search_cache=lambda: self._search_cache,
            fuzzy_search_config=self._fuzzy_search_config,
            adaptive_searcher=self._adaptive_searcher,
            lazy_index_manager=self._lazy_index_manager,
            default_search_profile=default_search_profile,
            adaptive_search_enabled=adaptive_search_enabled,
            default_search_mode=default_search_mode,
            bm25_weight=bm25_weight,
        )

    def stabilize(self) -> None:
        """Force eager index creation and fully reopen the DB connection.

        After bulk indexing, the lazy index manager may have a pending vector
        index.  If that index is created later (triggered by a search during
        wiki generation), LanceDB's ``create_index()`` compacts data fragments
        while concurrent readers are still using the old files, producing
        "Not found" IO errors.

        This method prevents the race by:
        1. Creating the vector index eagerly (if pending) so no background
           task fires during reads.
        2. **Always** marking the index as created — even if index creation
           fails — so the lazy trigger never fires during concurrent reads.
           Searches degrade to brute-force (slower but correct).
        3. Dropping the DB connection so the next access lazily reconnects
           with a fresh on-disk snapshot.

        Safe to call multiple times (idempotent / no-op if already stable).
        """
        with self._lock:
            if self._table is None:
                return

            # Step 1: Force eager vector index creation if pending
            if self._lazy_index_manager.is_index_pending():
                try:
                    num_rows = self._table.count_rows()
                    if num_rows >= self._lazy_index_manager.config.min_rows:
                        import math

                        num_partitions = min(max(int(math.sqrt(num_rows)), 16), 256)
                        logger.info(
                            "stabilize: creating vector index eagerly "
                            "(%d rows, %d partitions)",
                            num_rows,
                            num_partitions,
                        )
                        self._table.create_index(
                            metric="L2",
                            num_partitions=num_partitions,
                            num_sub_vectors=16,
                        )
                except (RuntimeError, OSError) as exc:
                    logger.warning(
                        "stabilize: vector index creation failed (searches "
                        "will use brute-force): %s",
                        exc,
                    )

                # Always mark as created so the lazy trigger never fires
                # during concurrent reads.  Without a vector index LanceDB
                # falls back to brute-force search — slower but correct.
                self._lazy_index_manager.mark_index_created()

            # Step 2: Drop the entire DB connection so the next access
            # reconnects with a fresh handle that sees the final on-disk state.
            logger.info("stabilize: closing DB connection for fresh reconnect")
            self._table = None
            self._db = None

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
            self._search_engine.fuzzy_search_helper = None
            self._search_cache.invalidate()
            self._adaptive_searcher.reset()

    def __del__(self) -> None:
        """Safety net to release resources on garbage collection."""
        try:
            self.close()
        except Exception:  # noqa: BLE001 — destructor must not fail during interpreter shutdown when objects may already be gone
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
        exc_tb: TracebackType | None,
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
            rate_limiter=self._rate_limiter,
            progress=progress,
            semaphore=semaphore,
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
            batch_size=batch_size,
            log_progress=log_progress,
        )

    async def _batch_embed_sequential(
        self, texts: list[str], batch_size: int, log_progress: bool = False
    ) -> list[list[float]]:
        """Generate embeddings in sequential batches (legacy method)."""
        from .embedding import batch_embed_sequential

        return await batch_embed_sequential(
            texts, self.embedding_provider, batch_size, log_progress=log_progress
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

        # Eagerly create the vector index after bulk table creation.
        # Why eager even when lazy indexing is enabled: create_or_update_table
        # is always a bulk operation. If deferred, concurrent searches trigger
        # lazy index creation mid-wiki-generation, causing IO errors.
        num_rows = len(data)
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

        # Lazy path for incremental additions
        num_rows = table.count_rows()
        if (
            self._lazy_index_manager.config.enabled
            and num_rows >= self._lazy_index_manager.config.min_rows
        ):
            self._lazy_index_manager.mark_index_pending()

        return len(data)

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

    @staticmethod
    def _row_to_chunk(row: dict[str, Any]) -> CodeChunk:
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

    @staticmethod
    def _chunk_to_text(chunk: CodeChunk) -> str:
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
