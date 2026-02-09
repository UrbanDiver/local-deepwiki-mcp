"""Iterators for efficient chunk loading."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any, Callable, TYPE_CHECKING

import psutil
from lancedb.table import Table

from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk

from .schema import ChunkBatch, VALID_LANGUAGES, VALID_CHUNK_TYPES, DEFAULT_MAX_MEMORY_MB, ESTIMATED_BYTES_PER_CHUNK
from .utils import _row_to_chunk_default, _sanitize_string_value

if TYPE_CHECKING:
    from .store import VectorStore

logger = get_logger(__name__)

class ChunkIterator:
    """Memory-efficient iterator over all chunks in a vector store table.

    Loads chunks in batches to avoid OOM when dealing with large datasets (1M+ chunks).
    Supports both sync and async iteration.

    Example:
        ```python
        iterator = ChunkIterator(table, batch_size=1000)

        # Count without loading all data
        total = iterator.count()

        # Iterate synchronously
        for chunk in iterator:
            process(chunk)

        # Iterate asynchronously
        async for chunk in iterator:
            await process(chunk)

        # Iterate in batches
        for batch in iterator.batches():
            process_batch(batch.chunks)
        ```
    """

    def __init__(
        self,
        table: Table,
        batch_size: int = 1000,
        columns: list[str] | None = None,
        filter_expr: str | None = None,
        row_to_chunk_fn: Callable[[dict[str, Any]], CodeChunk] | None = None,
    ):
        """Initialize the chunk iterator.

        Args:
            table: LanceDB table to iterate over.
            batch_size: Number of rows to load per batch.
            columns: Specific columns to fetch (None = all columns).
            filter_expr: Optional filter expression (e.g., "language = 'python'").
            row_to_chunk_fn: Function to convert a row dict to CodeChunk.
        """
        self._table = table
        self._batch_size = batch_size
        self._columns = columns
        self._filter_expr = filter_expr
        self._row_to_chunk_fn = row_to_chunk_fn or _row_to_chunk_default
        self._offset = 0
        self._total_count: int | None = None
        self._cached_rows: list[dict[str, Any]] | None = None

    def count(self) -> int:
        """Return total count of chunks without loading all data.

        Uses LanceDB's count_rows() which is O(1) and doesn't load row data.

        Returns:
            Total number of chunks in the table.
        """
        if self._total_count is None:
            if self._filter_expr:
                # For filtered counts, we need to run a query
                # This is more expensive but still doesn't load full row data
                query = self._table.search().where(self._filter_expr)
                query = query.select(["id"])  # Only fetch ID for count
                results = query.limit(10_000_000).to_list()  # Large limit for count
                self._total_count = len(results)
            else:
                self._total_count = self._table.count_rows()
        return self._total_count

    def reset(self) -> None:
        """Reset the iterator to the beginning."""
        self._offset = 0
        self._cached_rows = None

    def _ensure_cached_rows(self) -> list[dict[str, Any]]:
        """Fetch and cache all matching rows on first access.

        LanceDB lacks native offset support, so repeated limit+offset
        fetches are O(n^2). Instead, fetch all rows once and slice from
        the cached list for O(n) total iteration.

        Returns:
            Cached list of all matching row dictionaries.
        """
        if self._cached_rows is not None:
            return self._cached_rows

        query = self._table.search()

        if self._filter_expr:
            query = query.where(self._filter_expr)

        if self._columns:
            query = query.select(self._columns)

        total = self.count()
        self._cached_rows = query.limit(total).to_list() if total > 0 else []
        return self._cached_rows

    def _fetch_batch(self, offset: int) -> list[dict[str, Any]]:
        """Fetch a batch of rows from the cached result set.

        Args:
            offset: Starting offset for this batch.

        Returns:
            List of row dictionaries.
        """
        all_rows = self._ensure_cached_rows()
        return all_rows[offset : offset + self._batch_size]

    def __iter__(self) -> Iterator[CodeChunk]:
        """Iterate over all chunks in batches.

        Yields:
            CodeChunk objects one at a time.
        """
        self.reset()
        total = self.count()

        while self._offset < total:
            rows = self._fetch_batch(self._offset)
            if not rows:
                break

            for row in rows:
                yield self._row_to_chunk_fn(row)

            self._offset += len(rows)

    async def __aiter__(self) -> AsyncIterator[CodeChunk]:
        """Async iterate over all chunks in batches.

        Yields:
            CodeChunk objects one at a time.
        """
        self.reset()
        total = self.count()

        while self._offset < total:
            # Run the blocking fetch in a thread pool
            rows = await asyncio.to_thread(self._fetch_batch, self._offset)
            if not rows:
                break

            for row in rows:
                yield self._row_to_chunk_fn(row)

            self._offset += len(rows)
            # Yield control to allow other async operations
            await asyncio.sleep(0)

    def batches(self) -> Iterator[ChunkBatch]:
        """Iterate over chunks in batches.

        More efficient for bulk operations as it avoids per-chunk overhead.

        Yields:
            ChunkBatch objects containing lists of chunks.
        """
        self.reset()
        total = self.count()
        total_batches = (
            (total + self._batch_size - 1) // self._batch_size if total > 0 else 0
        )
        batch_index = 0

        while self._offset < total:
            rows = self._fetch_batch(self._offset)
            if not rows:
                break

            chunks = [self._row_to_chunk_fn(row) for row in rows]
            self._offset += len(rows)
            has_more = self._offset < total

            yield ChunkBatch(
                chunks=chunks,
                batch_index=batch_index,
                total_batches=total_batches,
                has_more=has_more,
            )
            batch_index += 1

    async def async_batches(self) -> AsyncIterator[ChunkBatch]:
        """Async iterate over chunks in batches.

        Yields:
            ChunkBatch objects containing lists of chunks.
        """
        self.reset()
        total = self.count()
        total_batches = (
            (total + self._batch_size - 1) // self._batch_size if total > 0 else 0
        )
        batch_index = 0

        while self._offset < total:
            rows = await asyncio.to_thread(self._fetch_batch, self._offset)
            if not rows:
                break

            chunks = [self._row_to_chunk_fn(row) for row in rows]
            self._offset += len(rows)
            has_more = self._offset < total

            yield ChunkBatch(
                chunks=chunks,
                batch_index=batch_index,
                total_batches=total_batches,
                has_more=has_more,
            )
            batch_index += 1
            await asyncio.sleep(0)


class LazyChunkLoader:
    """Lazy loader for code chunks with memory-aware batch sizing.

    Provides memory-efficient access to chunks from a VectorStore without
    loading all data into memory at once.

    Example:
        ```python
        loader = LazyChunkLoader(vector_store, max_memory_mb=512)

        # Get chunks for a specific file (lazy)
        for chunk in loader.get_chunks_by_file("src/main.py"):
            process(chunk)

        # Get all chunks in memory-aware batches
        for chunk in loader.get_all_chunks():
            process(chunk)

        # Get batch size based on available memory
        batch_size = loader.calculate_optimal_batch_size()
        ```
    """

    def __init__(
        self,
        store: "VectorStore",
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
    ):
        """Initialize the lazy chunk loader.

        Args:
            store: VectorStore instance to load chunks from.
            max_memory_mb: Maximum memory budget in MB for batch operations.
        """
        self._store = store
        self._max_memory_mb = max_memory_mb
        self._optimal_batch_size: int | None = None

    @property
    def max_memory_bytes(self) -> int:
        """Maximum memory budget in bytes."""
        return self._max_memory_mb * 1024 * 1024

    def calculate_optimal_batch_size(
        self,
        available_memory_mb: int | None = None,
        bytes_per_chunk: int = ESTIMATED_BYTES_PER_CHUNK,
    ) -> int:
        """Calculate optimal batch size based on available memory.

        Args:
            available_memory_mb: Available memory in MB. If None, auto-detects.
            bytes_per_chunk: Estimated bytes per chunk.

        Returns:
            Optimal batch size that fits within memory constraints.
        """
        if available_memory_mb is None:
            # Auto-detect available memory
            try:
                mem_info = psutil.virtual_memory()
                # Use at most 25% of available memory or max_memory_mb, whichever is smaller
                available_memory_mb = min(
                    int(mem_info.available / (1024 * 1024) * 0.25),
                    self._max_memory_mb,
                )
            except (ImportError, OSError, AttributeError):
                # ImportError: psutil not installed
                # OSError: Permission or OS-level issue
                # AttributeError: psutil API change
                available_memory_mb = self._max_memory_mb

        available_bytes = available_memory_mb * 1024 * 1024
        batch_size = max(100, available_bytes // bytes_per_chunk)

        # Cap at reasonable limits
        return min(batch_size, 10_000)

    def get_chunks_by_file(
        self,
        file_path: str,
        batch_size: int | None = None,
    ) -> Iterator[CodeChunk]:
        """Lazily load chunks for a specific file.

        Args:
            file_path: Path to the file to get chunks for.
            batch_size: Batch size for loading. If None, uses optimal size.

        Yields:
            CodeChunk objects for the specified file.
        """
        table = self._store._get_table()
        if table is None:
            return

        if batch_size is None:
            batch_size = self.calculate_optimal_batch_size()

        safe_path = _sanitize_string_value(file_path)
        filter_expr = f"file_path = '{safe_path}'"

        iterator = ChunkIterator(
            table=table,
            batch_size=batch_size,
            filter_expr=filter_expr,
            row_to_chunk_fn=self._store._row_to_chunk,
        )

        yield from iterator

    async def async_get_chunks_by_file(
        self,
        file_path: str,
        batch_size: int | None = None,
    ) -> AsyncIterator[CodeChunk]:
        """Async lazily load chunks for a specific file.

        Args:
            file_path: Path to the file to get chunks for.
            batch_size: Batch size for loading. If None, uses optimal size.

        Yields:
            CodeChunk objects for the specified file.
        """
        table = self._store._get_table()
        if table is None:
            return

        if batch_size is None:
            batch_size = self.calculate_optimal_batch_size()

        safe_path = _sanitize_string_value(file_path)
        filter_expr = f"file_path = '{safe_path}'"

        iterator = ChunkIterator(
            table=table,
            batch_size=batch_size,
            filter_expr=filter_expr,
            row_to_chunk_fn=self._store._row_to_chunk,
        )

        async for chunk in iterator:
            yield chunk

    def get_all_chunks(
        self,
        batch_size: int | None = None,
        language: str | None = None,
        chunk_type: str | None = None,
    ) -> Iterator[CodeChunk]:
        """Lazily iterate over all chunks.

        Args:
            batch_size: Batch size for loading. If None, uses optimal size.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.

        Yields:
            CodeChunk objects.
        """
        table = self._store._get_table()
        if table is None:
            return

        if batch_size is None:
            batch_size = self.calculate_optimal_batch_size()

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

        iterator = ChunkIterator(
            table=table,
            batch_size=batch_size,
            filter_expr=filter_expr,
            row_to_chunk_fn=self._store._row_to_chunk,
        )

        yield from iterator

    async def async_get_all_chunks(
        self,
        batch_size: int | None = None,
        language: str | None = None,
        chunk_type: str | None = None,
    ) -> AsyncIterator[CodeChunk]:
        """Async lazily iterate over all chunks.

        Args:
            batch_size: Batch size for loading. If None, uses optimal size.
            language: Optional language filter.
            chunk_type: Optional chunk type filter.

        Yields:
            CodeChunk objects.
        """
        table = self._store._get_table()
        if table is None:
            return

        if batch_size is None:
            batch_size = self.calculate_optimal_batch_size()

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

        iterator = ChunkIterator(
            table=table,
            batch_size=batch_size,
            filter_expr=filter_expr,
            row_to_chunk_fn=self._store._row_to_chunk,
        )

        async for chunk in iterator:
            yield chunk

    def count_chunks(
        self,
        language: str | None = None,
        chunk_type: str | None = None,
    ) -> int:
        """Count chunks without loading them into memory.

        Args:
            language: Optional language filter.
            chunk_type: Optional chunk type filter.

        Returns:
            Total count of matching chunks.
        """
        table = self._store._get_table()
        if table is None:
            return 0

        if not language and not chunk_type:
            return table.count_rows()

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

        iterator = ChunkIterator(
            table=table,
            batch_size=1,
            filter_expr=filter_expr,
        )

        return iterator.count()

