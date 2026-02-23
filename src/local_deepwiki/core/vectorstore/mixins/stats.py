"""StatsMixin — chunk retrieval, statistics, caching, and iteration helpers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk

from ..iterators import ChunkIterator, LazyChunkLoader
from ..schema import (
    DEFAULT_MAX_MEMORY_MB,
    VALID_CHUNK_TYPES,
    VALID_LANGUAGES,
)
from ..utils import _sanitize_string_value

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore.store import VectorStore

logger = get_logger(__name__)


class StatsMixin:
    """Mixin providing chunk retrieval, statistics, cache, and iteration methods."""

    # -- Type stubs so IDEs know about attributes set by VectorStore.__init__ --
    if TYPE_CHECKING:
        _table: Any
        _search_cache: Any
        _embedding_batch_config: Any
        embedding_provider: Any

        def _get_table(self) -> Any: ...
        def _row_to_chunk(self, row: dict[str, Any]) -> CodeChunk: ...
        def _is_local_provider(self) -> bool: ...
        def _get_optimal_batch_config(self) -> tuple[int, int]: ...

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
        loader = LazyChunkLoader(cast("VectorStore", self))
        yield from loader.get_all_chunks(
            batch_size=batch_size,
            language=language,
            chunk_type=chunk_type,
        )

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

    @property
    def stats(self) -> dict[str, Any]:
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
        table = self._get_table()
        if table is None:
            return {"total_chunks": 0, "languages": {}, "chunk_types": {}, "files": 0}

        # Use count_rows() for total - doesn't load data
        total_chunks = table.count_rows()

        if total_chunks == 0:
            return {"total_chunks": 0, "languages": {}, "chunk_types": {}, "files": 0}

        # For small tables, use the regular method
        if total_chunks <= batch_size:
            return self.stats

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
        return LazyChunkLoader(cast("VectorStore", self), max_memory_mb=max_memory_mb)

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

    def invalidate_search_cache(self) -> int:
        """Invalidate all search cache entries.

        Call this when the index is updated externally or when you want
        to force fresh search results.

        Returns:
            Number of cache entries invalidated.
        """
        return self._search_cache.invalidate()

    @property
    def search_cache_stats(self) -> dict[str, Any]:
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

    @property
    def embedding_batch_config(self) -> dict[str, Any]:
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
