"""LanceDB vector store for code chunk storage and retrieval."""

import asyncio
import json
import math
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import lancedb
import numpy as np
from lancedb.table import Table

from local_deepwiki.config import EmbeddingBatchConfig, SearchCacheConfig
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult
from local_deepwiki.providers.base import EmbeddingProvider

logger = get_logger(__name__)


# Valid values for filtering - used to prevent injection attacks
VALID_LANGUAGES = {lang.value for lang in Language}
VALID_CHUNK_TYPES = {ct.value for ct in ChunkType}


@dataclass
class SearchCacheEntry:
    """A cached search result entry."""

    query_text: str
    query_embedding: list[float]
    results: list[SearchResult]
    created_at: float
    filters: dict[str, Any] = field(default_factory=dict)


class SearchCache:
    """In-memory cache for search results with semantic deduplication.

    Uses embedding similarity to find cached results for semantically similar queries.
    Entries expire based on TTL and are evicted using LRU when max_entries is reached.
    """

    def __init__(self, config: SearchCacheConfig):
        """Initialize the search cache.

        Args:
            config: Cache configuration.
        """
        self.config = config
        self._cache: dict[str, SearchCacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "invalidations": 0}

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()

    def _compute_similarity(
        self, embedding1: list[float], embedding2: list[float]
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Cosine similarity score (0.0 to 1.0).
        """
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)

        # Compute cosine similarity
        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _is_valid_entry(self, entry: SearchCacheEntry) -> bool:
        """Check if a cache entry is still valid (not expired).

        Args:
            entry: Cache entry to check.

        Returns:
            True if entry is valid, False if expired.
        """
        age = time.time() - entry.created_at
        return age < self.config.ttl_seconds

    def _filters_match(
        self, cached_filters: dict[str, Any], query_filters: dict[str, Any]
    ) -> bool:
        """Check if cached filters match the query filters.

        Args:
            cached_filters: Filters from cached entry.
            query_filters: Filters from current query.

        Returns:
            True if filters match, False otherwise.
        """
        # Both must have the same keys and values
        return cached_filters == query_filters

    def get(
        self,
        query_embedding: list[float],
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult] | None:
        """Try to get cached results for a semantically similar query.

        Args:
            query_embedding: Embedding of the search query.
            filters: Optional filters applied to the search (language, chunk_type, etc.)

        Returns:
            Cached search results if found and valid, None otherwise.
        """
        if not self.config.enabled:
            return None

        filters = filters or {}

        with self._lock:
            best_match: SearchCacheEntry | None = None
            best_similarity = 0.0

            # Find the most similar valid cached query
            expired_keys: list[str] = []
            for key, entry in self._cache.items():
                if not self._is_valid_entry(entry):
                    expired_keys.append(key)
                    continue

                # Check if filters match
                if not self._filters_match(entry.filters, filters):
                    continue

                # Compute similarity
                similarity = self._compute_similarity(query_embedding, entry.query_embedding)

                if similarity >= self.config.similarity_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = entry

            # Clean up expired entries
            for key in expired_keys:
                del self._cache[key]

            if best_match is not None:
                self._stats["hits"] += 1
                logger.debug(
                    f"Search cache hit: similarity={best_similarity:.3f}, "
                    f"query='{best_match.query_text[:50]}...'"
                )
                return best_match.results

            self._stats["misses"] += 1
            return None

    def set(
        self,
        query_text: str,
        query_embedding: list[float],
        results: list[SearchResult],
        filters: dict[str, Any] | None = None,
    ) -> None:
        """Cache search results for a query.

        Args:
            query_text: Original query text.
            query_embedding: Embedding of the query.
            results: Search results to cache.
            filters: Optional filters applied to the search.
        """
        if not self.config.enabled:
            return

        filters = filters or {}

        with self._lock:
            # Create a unique key based on query text and filters
            filter_str = json.dumps(filters, sort_keys=True)
            cache_key = f"{query_text}:{filter_str}"

            entry = SearchCacheEntry(
                query_text=query_text,
                query_embedding=query_embedding,
                results=results,
                created_at=time.time(),
                filters=filters,
            )

            self._cache[cache_key] = entry

            logger.debug(
                f"Cached search results: query='{query_text[:50]}...', "
                f"results={len(results)}"
            )

            # Evict if over capacity
            self._maybe_evict()

    def _maybe_evict(self) -> None:
        """Evict old entries if cache exceeds max_entries.

        Uses a two-phase eviction strategy:
        1. First, remove all expired entries (TTL-based)
        2. If still over limit, remove oldest entries (LRU)
        """
        if len(self._cache) <= self.config.max_entries:
            return

        logger.debug(
            f"Search cache has {len(self._cache)} entries "
            f"(max: {self.config.max_entries}), evicting..."
        )

        # Phase 1: Remove expired entries
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry.created_at >= self.config.ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Evicted {len(expired_keys)} expired search cache entries")

        # Phase 2: LRU eviction if still over limit
        if len(self._cache) > self.config.max_entries:
            # Sort by created_at (oldest first)
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].created_at
            )

            # Calculate how many to remove (with 20% buffer)
            target_count = int(self.config.max_entries * 0.8)
            to_remove = len(self._cache) - target_count

            for key, _ in sorted_entries[:to_remove]:
                del self._cache[key]

            logger.debug(f"Evicted {to_remove} LRU search cache entries")

    def invalidate(self) -> int:
        """Invalidate all cache entries.

        Called when the index is updated (new chunks added/removed).

        Returns:
            Number of entries invalidated.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats["invalidations"] += 1
            if count > 0:
                logger.debug(f"Invalidated {count} search cache entries")
            return count

    def get_stats(self) -> dict[str, Any]:
        """Get detailed cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        with self._lock:
            return {
                "enabled": self.config.enabled,
                "entries": len(self._cache),
                "max_entries": self.config.max_entries,
                "ttl_seconds": self.config.ttl_seconds,
                "similarity_threshold": self.config.similarity_threshold,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "invalidations": self._stats["invalidations"],
                "hit_rate": (
                    self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                    if (self._stats["hits"] + self._stats["misses"]) > 0
                    else 0.0
                ),
            }


@dataclass
class BatchEmbeddingResult:
    """Result of a batch embedding operation."""

    batch_index: int
    embeddings: list[list[float]] | None
    error: Exception | None = None
    retry_count: int = 0


@dataclass
class EmbeddingProgress:
    """Progress tracker for embedding operations."""

    total_texts: int
    total_batches: int
    completed_batches: int = 0
    failed_batches: int = 0
    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, success: bool = True) -> None:
        """Update progress after a batch completes."""
        with self._lock:
            if success:
                self.completed_batches += 1
            else:
                self.failed_batches += 1

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def estimated_remaining_seconds(self) -> float | None:
        """Estimate remaining time based on current progress."""
        with self._lock:
            if self.completed_batches == 0:
                return None
            avg_time_per_batch = self.elapsed_seconds / self.completed_batches
            remaining_batches = self.total_batches - self.completed_batches - self.failed_batches
            return avg_time_per_batch * remaining_batches

    def log_progress(self) -> None:
        """Log current progress."""
        with self._lock:
            completed = self.completed_batches
            failed = self.failed_batches
            total = self.total_batches
            elapsed = self.elapsed_seconds

        # Calculate outside lock to avoid deadlock with estimated_remaining_seconds
        progress_pct = (completed + failed) / total * 100 if total > 0 else 0
        if completed > 0:
            avg_time_per_batch = elapsed / completed
            remaining_batches = total - completed - failed
            eta = avg_time_per_batch * remaining_batches
            eta_str = f", ETA: {eta:.1f}s"
        else:
            eta_str = ""

        logger.info(
            f"Embedding progress: {completed}/{total} batches "
            f"({progress_pct:.1f}%){eta_str}"
        )


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_minute: int):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute.
        """
        self.rate = requests_per_minute / 60.0  # Requests per second
        self.tokens = float(requests_per_minute)
        self.max_tokens = float(requests_per_minute)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                # Wait for tokens to refill
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
                self.last_update = time.monotonic()
            else:
                self.tokens -= 1.0


def _sanitize_string_value(value: str) -> str:
    """Sanitize a string value for use in LanceDB filter expressions.

    Escapes single quotes to prevent injection attacks.

    Args:
        value: The string to sanitize.

    Returns:
        Sanitized string safe for use in filter expressions.
    """
    # Escape single quotes by doubling them
    return value.replace("'", "''")


class VectorStore:
    """Vector store using LanceDB for code chunk storage and semantic search."""

    TABLE_NAME = "code_chunks"

    def __init__(
        self,
        db_path: Path,
        embedding_provider: EmbeddingProvider,
        search_cache_config: SearchCacheConfig | None = None,
        embedding_batch_config: EmbeddingBatchConfig | None = None,
    ):
        """Initialize the vector store.

        Args:
            db_path: Path to the LanceDB database directory.
            embedding_provider: Provider for generating embeddings.
            search_cache_config: Optional search cache configuration.
                If None, uses default SearchCacheConfig.
            embedding_batch_config: Optional embedding batch configuration.
                If None, uses default EmbeddingBatchConfig.
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
        """Ensure all indexes exist, creating them if needed.

        This is called when opening an existing table to ensure indexes
        are present even if the table was created by an older version.
        Creates both scalar indexes (for lookups) and vector indexes (for search).
        """
        if self._table is None:
            return

        # Check existing indexes
        try:
            indices = self._table.list_indices()
            # Handle both dict-style and object-style index configs (LanceDB version compat)
            existing_indexes = set()
            has_vector_index = False
            for idx in indices:
                name = getattr(idx, "name", None) or (
                    idx.get("name") if isinstance(idx, dict) else None
                )
                if name:
                    existing_indexes.add(name)
                # Check for vector index (name contains "vector" or type is IVF/ANN)
                idx_type = getattr(idx, "index_type", None) or (
                    idx.get("index_type") if isinstance(idx, dict) else None
                )
                if idx_type and "ivf" in str(idx_type).lower():
                    has_vector_index = True
        except (KeyError, TypeError, RuntimeError, AttributeError) as e:
            # Index info structure varies between LanceDB versions
            # RuntimeError: Table may not support listing indices
            logger.debug(f"Could not list existing indexes: {e}")
            existing_indexes = set()
            has_vector_index = False

        # Create missing scalar indexes
        if "id_idx" not in existing_indexes:
            self._create_index_safe("id")
        if "file_path_idx" not in existing_indexes:
            self._create_index_safe("file_path")

        # Create vector index if missing and table is large enough
        if not has_vector_index:
            try:
                num_rows = self._table.count_rows()
                self._create_vector_index(num_rows)
            except (RuntimeError, OSError) as e:
                logger.debug(f"Could not check row count for vector indexing: {e}")

    def _create_index_safe(self, column: str) -> None:
        """Safely create a scalar index on a column.

        Args:
            column: The column name to index.
        """
        if self._table is None:
            return

        try:
            self._table.create_scalar_index(column)
            logger.debug(f"Created scalar index on '{column}' column")
        except (ValueError, RuntimeError, OSError) as e:
            # ValueError: Index already exists or invalid column
            # RuntimeError: Column type not supported for indexing
            # OSError: Underlying storage issues
            logger.debug(f"Could not create index on '{column}': {e}")

    def _create_scalar_indexes(self) -> None:
        """Create scalar indexes for efficient lookups.

        Creates indexes on 'id' and 'file_path' columns to optimize
        get_chunk_by_id() and get_chunks_by_file() operations.
        """
        self._create_index_safe("id")
        self._create_index_safe("file_path")

    def _create_vector_index(self, num_rows: int) -> None:
        """Create a vector index for faster semantic search.

        Uses IVF-PQ index for approximate nearest neighbor search,
        which provides 5-10x speedup on large datasets (10k+ vectors).

        Args:
            num_rows: Number of rows in the table (used to determine if indexing is beneficial).
        """
        if self._table is None:
            return

        # Only create vector index for tables with enough rows to benefit
        # IVF-PQ has overhead that isn't worth it for small tables
        min_rows_for_index = 1000
        if num_rows < min_rows_for_index:
            logger.debug(
                f"Skipping vector index creation: {num_rows} rows < {min_rows_for_index} threshold"
            )
            return

        try:
            # Calculate optimal number of partitions based on table size
            # Rule of thumb: sqrt(n) partitions, capped at reasonable values
            num_partitions = min(max(int(math.sqrt(num_rows)), 16), 256)

            # Create IVF-PQ index on the vector column
            # - metric: L2 (Euclidean distance) matches our similarity scoring
            # - num_partitions: number of IVF clusters
            # - num_sub_vectors: for PQ compression (higher = more accurate but slower)
            self._table.create_index(
                metric="L2",
                num_partitions=num_partitions,
                num_sub_vectors=16,  # Good balance of speed vs accuracy
            )
            logger.info(
                f"Created vector index with {num_partitions} partitions for {num_rows} vectors"
            )
        except (ValueError, RuntimeError, OSError) as e:
            # ValueError: Index already exists or invalid params
            # RuntimeError: Index creation failed
            # OSError: Storage issues
            logger.debug(f"Could not create vector index: {e}")

    def _is_local_provider(self) -> bool:
        """Check if the embedding provider is local (sentence-transformers).

        Returns:
            True if provider is local, False for API-based providers.
        """
        provider_name = self.embedding_provider.name.lower()
        return provider_name.startswith("local:") or "sentence" in provider_name

    def _get_optimal_batch_config(self) -> tuple[int, int]:
        """Get optimal batch size and concurrency based on provider type.

        Returns:
            Tuple of (batch_size, concurrency).
        """
        config = self._embedding_batch_config
        is_local = self._is_local_provider()

        # Use configured values, but adjust defaults based on provider type
        batch_size = config.batch_size
        concurrency = config.concurrency

        # For local providers, can use larger batches and higher concurrency
        if is_local:
            # Local models benefit from larger batches for GPU/CPU efficiency
            batch_size = max(batch_size, 100)
            concurrency = max(concurrency, 4)
        else:
            # API providers should use smaller batches to avoid rate limits
            batch_size = min(batch_size, 50)
            # Lower concurrency for APIs to avoid overwhelming the service
            concurrency = min(concurrency, 4)

        return batch_size, concurrency

    async def _embed_single_batch_with_retry(
        self,
        batch_index: int,
        texts: list[str],
        progress: EmbeddingProgress,
        semaphore: asyncio.Semaphore,
    ) -> BatchEmbeddingResult:
        """Embed a single batch with retry logic and rate limiting.

        Args:
            batch_index: Index of this batch for ordering results.
            texts: Texts to embed in this batch.
            progress: Progress tracker to update.
            semaphore: Semaphore for concurrency control.

        Returns:
            BatchEmbeddingResult with embeddings or error.
        """
        config = self._embedding_batch_config
        retry_count = 0

        async with semaphore:
            while retry_count < config.retry_max_attempts:
                try:
                    # Apply rate limiting if configured
                    if self._rate_limiter is not None:
                        await self._rate_limiter.acquire()

                    # Generate embeddings
                    embeddings = await self.embedding_provider.embed(texts)
                    progress.update(success=True)

                    return BatchEmbeddingResult(
                        batch_index=batch_index,
                        embeddings=embeddings,
                        retry_count=retry_count,
                    )

                except Exception as e:
                    retry_count += 1
                    error_str = str(e).lower()

                    # Check if this is a retryable error
                    is_retryable = (
                        isinstance(e, (ConnectionError, TimeoutError, OSError))
                        or "rate" in error_str and "limit" in error_str
                        or "overloaded" in error_str
                        or "503" in error_str
                        or "502" in error_str
                        or "timeout" in error_str
                    )

                    if not is_retryable or retry_count >= config.retry_max_attempts:
                        logger.warning(
                            f"Batch {batch_index} failed after {retry_count} attempts: {e}"
                        )
                        progress.update(success=False)
                        return BatchEmbeddingResult(
                            batch_index=batch_index,
                            embeddings=None,
                            error=e,
                            retry_count=retry_count,
                        )

                    # Calculate backoff delay with jitter
                    delay = config.retry_base_delay * (2 ** (retry_count - 1))
                    delay = delay * (0.5 + random.random())  # Add jitter
                    logger.warning(
                        f"Batch {batch_index} failed (attempt {retry_count}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

        # Should not reach here
        progress.update(success=False)
        return BatchEmbeddingResult(
            batch_index=batch_index,
            embeddings=None,
            error=RuntimeError("Unexpected: exhausted retries without returning"),
            retry_count=retry_count,
        )

    async def _batch_embed(
        self, texts: list[str], batch_size: int | None = None, log_progress: bool = False
    ) -> list[list[float]]:
        """Generate embeddings in parallel batches.

        Uses concurrent batch processing for faster embedding generation.
        For local providers, uses higher concurrency. For API providers,
        respects rate limits and uses lower concurrency.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts to embed per batch. If None, uses config default.
            log_progress: Whether to log batch progress.

        Returns:
            List of embedding vectors in the same order as input texts.

        Raises:
            RuntimeError: If any batches fail after all retry attempts.
        """
        if not texts:
            return []

        # Get optimal config based on provider type
        optimal_batch_size, optimal_concurrency = self._get_optimal_batch_config()
        batch_size = batch_size or optimal_batch_size

        # Split texts into batches
        batches: list[list[str]] = []
        for i in range(0, len(texts), batch_size):
            batches.append(texts[i : i + batch_size])

        total_batches = len(batches)

        # For single batch, still use retry logic but without parallel overhead
        if total_batches == 1:
            progress = EmbeddingProgress(total_texts=len(texts), total_batches=1)
            semaphore = asyncio.Semaphore(1)
            result = await self._embed_single_batch_with_retry(0, batches[0], progress, semaphore)
            if result.error is not None:
                raise RuntimeError(f"Failed to embed batch: {result.error}")
            if log_progress:
                logger.debug(f"Embedded 1/1 batches ({len(texts)} texts)")
            return result.embeddings or []

        # Create progress tracker
        progress = EmbeddingProgress(
            total_texts=len(texts),
            total_batches=total_batches,
        )

        if log_progress:
            logger.info(
                f"Starting parallel embedding: {len(texts)} texts in {total_batches} batches "
                f"(batch_size={batch_size}, concurrency={optimal_concurrency})"
            )

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(optimal_concurrency)

        # Create tasks for all batches
        tasks = [
            self._embed_single_batch_with_retry(i, batch, progress, semaphore)
            for i, batch in enumerate(batches)
        ]

        # Execute all tasks concurrently
        results: list[BatchEmbeddingResult] = await asyncio.gather(*tasks)

        # Log final progress
        if log_progress:
            progress.log_progress()

        # Sort results by batch index to maintain order
        results.sort(key=lambda r: r.batch_index)

        # Check for failures and collect errors
        errors: list[tuple[int, Exception]] = []
        all_embeddings: list[list[float]] = []

        for result in results:
            if result.error is not None:
                errors.append((result.batch_index, result.error))
            elif result.embeddings is not None:
                all_embeddings.extend(result.embeddings)

        # If there were failures, report them
        if errors:
            error_msgs = [f"Batch {idx}: {err}" for idx, err in errors]
            error_summary = "\n".join(error_msgs)
            logger.error(f"Embedding failed for {len(errors)} batches:\n{error_summary}")

            # Raise an exception with details about the failures
            raise RuntimeError(
                f"Failed to embed {len(errors)} out of {total_batches} batches. "
                f"First error: {errors[0][1]}"
            )

        if log_progress:
            elapsed = progress.elapsed_seconds
            rate = len(texts) / elapsed if elapsed > 0 else 0
            logger.info(
                f"Embedding complete: {len(texts)} texts in {elapsed:.2f}s ({rate:.1f} texts/sec)"
            )

        return all_embeddings

    async def _batch_embed_sequential(
        self, texts: list[str], batch_size: int, log_progress: bool = False
    ) -> list[list[float]]:
        """Generate embeddings in sequential batches (legacy method).

        This is the original sequential implementation, kept for backward
        compatibility and testing purposes.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts to embed per batch.
            log_progress: Whether to log batch progress.

        Returns:
            List of embedding vectors.
        """
        embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self.embedding_provider.embed(batch)
            embeddings.extend(batch_embeddings)
            if log_progress and len(texts) > batch_size:
                logger.debug(
                    f"Embedded batch {i // batch_size + 1}/"
                    f"{(len(texts) + batch_size - 1) // batch_size}"
                )
        return embeddings

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

        logger.info(f"Creating/updating vector table with {len(chunks)} chunks")
        db = self._connect()

        # Generate embeddings in batches to avoid OOM and API limits
        texts = [self._chunk_to_text(chunk) for chunk in chunks]
        embeddings = await self._batch_embed(texts, embedding_batch_size, log_progress=True)

        # Prepare data for LanceDB
        data = [
            chunk.to_vector_record(vector=embedding) for chunk, embedding in zip(chunks, embeddings)
        ]

        # Drop existing table and create new one (thread-safe)
        with self._lock:
            if self.TABLE_NAME in db.list_tables().tables:
                db.drop_table(self.TABLE_NAME)

            self._table = db.create_table(self.TABLE_NAME, data)

        # Invalidate search cache since index has changed
        self._search_cache.invalidate()

        # Create scalar indexes for efficient lookups
        self._create_scalar_indexes()

        # Create vector index for faster semantic search on large datasets
        self._create_vector_index(len(data))

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

        logger.debug(f"Adding {len(chunks)} chunks to existing table")
        table = self._get_table()
        if table is None:
            return await self.create_or_update_table(chunks, embedding_batch_size)

        # Generate embeddings in batches to avoid OOM and API limits
        texts = [self._chunk_to_text(chunk) for chunk in chunks]
        embeddings = await self._batch_embed(texts, embedding_batch_size)

        # Prepare data
        data = [
            chunk.to_vector_record(vector=embedding) for chunk, embedding in zip(chunks, embeddings)
        ]

        table.add(data)

        # Invalidate search cache since index has changed
        self._search_cache.invalidate()

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

        Returns:
            List of search results with scores.
        """
        from local_deepwiki.core.fuzzy_search import (
            extract_highlights,
            filter_by_path,
            rerank_with_fuzzy,
        )

        table = self._get_table()
        if table is None:
            logger.debug("No table found for search")
            return []

        logger.debug(f"Searching for: '{query[:50]}...' limit={limit}")

        # Generate query embedding
        query_embedding = (await self.embedding_provider.embed([query]))[0]

        # Build cache filter key (only cache-relevant filters, not path_pattern/fuzzy)
        cache_filters: dict[str, Any] = {"limit": limit}
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

        # Fetch more results if using path filter or fuzzy (we'll filter/rerank after)
        fetch_limit = limit * 3 if (path_pattern or use_fuzzy) else limit

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

        # Execute search
        results = search.to_list()

        # Convert to SearchResult objects
        search_results = []
        for row in results:
            chunk = self._row_to_chunk(row)
            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=1.0 - row.get("_distance", 0),  # Convert distance to similarity
                    highlights=[],
                )
            )

        # Apply path pattern filter
        if path_pattern:
            search_results = filter_by_path(search_results, path_pattern)

        # Apply fuzzy re-ranking
        if use_fuzzy and search_results:
            search_results = rerank_with_fuzzy(search_results, query, fuzzy_weight)

            # Add highlights for fuzzy matches
            for result in search_results:
                result.highlights = extract_highlights(result.chunk.content, query)

        # Limit results to requested amount
        search_results = search_results[:limit]

        # Cache results (only for non-fuzzy, non-path-pattern searches)
        if use_cache:
            self._search_cache.set(query, query_embedding, search_results, cache_filters)

        return search_results

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

        logger.debug(f"Batch deleted chunks for {len(file_paths)} files")
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
