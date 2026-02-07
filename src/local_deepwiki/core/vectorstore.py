"""LanceDB vector store for code chunk storage and retrieval."""

import asyncio
import json
import math
import os
import random
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import lancedb
import numpy as np
import psutil
import pyarrow as pa
from lancedb.table import Table

from local_deepwiki.config import (
    EmbeddingBatchConfig,
    FuzzySearchConfig,
    LazyIndexConfig,
    SearchCacheConfig,
    SearchConfig,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult
from local_deepwiki.providers.base import EmbeddingProvider

logger = get_logger(__name__)


# Valid values for filtering - used to prevent injection attacks
VALID_LANGUAGES = {lang.value for lang in Language}
VALID_CHUNK_TYPES = {ct.value for ct in ChunkType}

# Default memory budget for batch operations (256 MB)
DEFAULT_MAX_MEMORY_MB = 256

# Estimated memory per chunk (based on typical chunk size)
# Includes embedding vector (~1536 floats * 4 bytes = 6KB) + content (~2KB avg) + overhead
ESTIMATED_BYTES_PER_CHUNK = 10_000  # ~10KB per chunk


@dataclass
class SearchResultPage:
    """Paginated search results with metadata.

    Attributes:
        results: List of search results for this page.
        total: Total number of matching results across all pages.
        offset: Starting offset of this page.
        limit: Maximum results per page.
        has_more: Whether there are more results after this page.
        cursor: Optional cursor for cursor-based pagination.
    """

    results: list[SearchResult]
    total: int
    offset: int
    limit: int
    has_more: bool
    cursor: str | None = None


@dataclass
class ChunkBatch:
    """A batch of chunks loaded from the store.

    Attributes:
        chunks: List of CodeChunk objects in this batch.
        batch_index: Index of this batch (0-based).
        total_batches: Estimated total number of batches.
        has_more: Whether there are more batches to load.
    """

    chunks: list[CodeChunk]
    batch_index: int
    total_batches: int
    has_more: bool


class SearchProfile(str, Enum):
    """Search profile for precision/recall trade-off.

    Profiles control how exhaustive the search is, trading off speed vs accuracy:
    - FAST: Minimal candidates, fastest response, may miss some relevant results
    - BALANCED: Default behavior, good balance of speed and recall
    - THOROUGH: Exhaustive search, best recall but slower
    """

    FAST = "fast"
    BALANCED = "balanced"
    THOROUGH = "thorough"


@dataclass
class SearchProfileConfig:
    """Configuration for a search profile.

    Attributes:
        profile: The search profile this config applies to.
        fetch_multiplier: Multiplier for nprobes/candidates fetched.
            Higher values fetch more candidates for better recall.
        rerank_candidates: How many candidates to rerank.
            More candidates = better final ranking but slower.
        use_approximate: Whether to use approximate (ANN) search.
            False means exact/exhaustive search.
        min_similarity: Minimum similarity threshold.
            Results below this threshold are filtered out.
    """

    profile: SearchProfile
    fetch_multiplier: float
    rerank_candidates: int
    use_approximate: bool
    min_similarity: float


# Pre-configured search profiles
SEARCH_PROFILES: dict[SearchProfile, SearchProfileConfig] = {
    SearchProfile.FAST: SearchProfileConfig(
        profile=SearchProfile.FAST,
        fetch_multiplier=1.0,
        rerank_candidates=10,
        use_approximate=True,
        min_similarity=0.3,
    ),
    SearchProfile.BALANCED: SearchProfileConfig(
        profile=SearchProfile.BALANCED,
        fetch_multiplier=2.0,
        rerank_candidates=50,
        use_approximate=True,
        min_similarity=0.2,
    ),
    SearchProfile.THOROUGH: SearchProfileConfig(
        profile=SearchProfile.THOROUGH,
        fetch_multiplier=5.0,
        rerank_candidates=200,
        use_approximate=False,
        min_similarity=0.1,
    ),
}


@dataclass
class SearchFeedback:
    """User feedback on search result relevance.

    Used to improve future search results by learning which results
    are actually relevant for specific queries.

    Attributes:
        query: The original search query.
        result_id: ID of the result being rated.
        relevant: Whether the user marked this result as relevant.
        timestamp: When the feedback was recorded.
    """

    query: str
    result_id: str
    relevant: bool
    timestamp: float = field(default_factory=time.time)


class AdaptiveSearcher:
    """Adaptive search depth estimator based on query characteristics and history.

    Learns from past searches to estimate optimal search depth for new queries.
    Uses query characteristics (length, complexity) and historical performance
    to adapt the search strategy.

    Attributes:
        _store: Reference to the VectorStore (set via property, not constructor).
        _query_history: Recent query history with quality metrics.
        _feedback_history: User feedback on search results.
    """

    # Maximum history size to prevent unbounded memory growth
    MAX_HISTORY_SIZE = 1000
    MAX_FEEDBACK_SIZE = 5000

    def __init__(self) -> None:
        """Initialize the adaptive searcher."""
        self._store: "VectorStore | None" = None
        # History: (query, quality_score, result_count, search_depth)
        self._query_history: deque[tuple[str, float, int, int]] = deque(
            maxlen=self.MAX_HISTORY_SIZE
        )
        self._feedback_history: deque[SearchFeedback] = deque(
            maxlen=self.MAX_FEEDBACK_SIZE
        )
        # Query complexity cache for performance
        self._complexity_cache: dict[str, float] = {}

    def set_store(self, store: "VectorStore") -> None:
        """Set the vector store reference.

        Args:
            store: The VectorStore instance this searcher is associated with.
        """
        self._store = store

    def _calculate_query_complexity(self, query: str) -> float:
        """Calculate a complexity score for a query.

        Complexity is based on:
        - Query length (longer = more complex)
        - Number of distinct terms
        - Presence of technical terms/operators

        Args:
            query: The search query text.

        Returns:
            Complexity score between 0.0 and 1.0.
        """
        if query in self._complexity_cache:
            return self._complexity_cache[query]

        # Normalize and tokenize
        words = query.lower().split()
        if not words:
            return 0.0

        # Factor 1: Query length (normalized to 0-1, saturates at 20 words)
        length_score = min(len(words) / 20.0, 1.0)

        # Factor 2: Vocabulary diversity (unique words / total words)
        unique_words = len(set(words))
        diversity_score = unique_words / len(words) if words else 0.0

        # Factor 3: Technical term presence (common programming terms)
        technical_terms = {
            "function",
            "class",
            "method",
            "async",
            "await",
            "import",
            "export",
            "interface",
            "type",
            "struct",
            "enum",
            "error",
            "exception",
            "api",
            "database",
            "query",
            "handler",
            "controller",
            "service",
            "repository",
            "middleware",
            "authentication",
            "authorization",
            "validation",
            "parse",
            "serialize",
            "deserialize",
        }
        tech_count = sum(1 for w in words if w in technical_terms)
        tech_score = min(tech_count / 3.0, 1.0)  # Saturates at 3 technical terms

        # Weighted combination
        complexity = 0.3 * length_score + 0.3 * diversity_score + 0.4 * tech_score

        # Cache the result (limit cache size)
        if len(self._complexity_cache) > 10000:
            # Clear oldest entries (simple approach)
            self._complexity_cache.clear()
        self._complexity_cache[query] = complexity

        return complexity

    def estimate_optimal_depth(self, query: str, base_limit: int = 10) -> int:
        """Estimate optimal search depth based on query characteristics.

        Uses query complexity and historical performance to determine
        how many candidates to fetch for the best results.

        Args:
            query: The search query text.
            base_limit: The base number of results requested.

        Returns:
            Recommended search depth (number of candidates to fetch).
        """
        complexity = self._calculate_query_complexity(query)

        # Base depth is the requested limit
        base_depth = base_limit

        # Complexity-based multiplier: more complex queries need deeper search
        # Range: 1.5x to 4x based on complexity
        complexity_multiplier = 1.5 + (complexity * 2.5)

        # Historical adjustment: if similar queries had poor quality, increase depth
        historical_multiplier = 1.0
        if self._query_history:
            # Look for similar queries (simple word overlap heuristic)
            query_words = set(query.lower().split())
            similar_qualities: list[float] = []

            for hist_query, quality, _, _ in self._query_history:
                hist_words = set(hist_query.lower().split())
                overlap = len(query_words & hist_words)
                if overlap >= min(2, len(query_words)):
                    similar_qualities.append(quality)

            if similar_qualities:
                avg_quality = sum(similar_qualities) / len(similar_qualities)
                # If quality was low, increase depth
                # Quality 1.0 = multiplier 1.0, quality 0.0 = multiplier 2.0
                historical_multiplier = 2.0 - avg_quality

        # Combine multipliers
        total_multiplier = complexity_multiplier * historical_multiplier

        # Calculate final depth, capped at reasonable limits
        optimal_depth = int(base_depth * total_multiplier)
        return min(max(optimal_depth, base_limit), base_limit * 10)

    def record_search_quality(
        self, query: str, quality: float, result_count: int, depth_used: int
    ) -> None:
        """Record search quality for future adaptation.

        Args:
            query: The search query that was executed.
            quality: Quality score between 0.0 (poor) and 1.0 (excellent).
            result_count: Number of results returned.
            depth_used: The search depth that was used.
        """
        quality = max(0.0, min(1.0, quality))  # Clamp to valid range
        self._query_history.append((query, quality, result_count, depth_used))
        logger.debug(
            f"Recorded search quality: query='{query[:50]}...' quality={quality:.2f} "
            f"results={result_count} depth={depth_used}"
        )

    def record_feedback(self, feedback: SearchFeedback) -> None:
        """Record user feedback to improve future searches.

        Feedback is used to update quality estimates for similar queries.

        Args:
            feedback: User feedback on a search result.
        """
        self._feedback_history.append(feedback)
        logger.debug(
            f"Recorded feedback: query='{feedback.query[:50]}...' "
            f"result={feedback.result_id} relevant={feedback.relevant}"
        )

        # Update quality estimates for matching queries in history
        # This provides indirect learning from user feedback
        for i, (hist_query, quality, count, depth) in enumerate(self._query_history):
            if hist_query == feedback.query:
                # Adjust quality based on feedback
                adjustment = 0.1 if feedback.relevant else -0.1
                new_quality = max(0.0, min(1.0, quality + adjustment))
                # Replace entry (deque doesn't support direct assignment)
                self._query_history[i] = (hist_query, new_quality, count, depth)

    def get_feedback_stats(self) -> dict[str, Any]:
        """Get statistics about collected feedback.

        Returns:
            Dictionary with feedback statistics.
        """
        if not self._feedback_history:
            return {
                "total_feedback": 0,
                "relevant_count": 0,
                "irrelevant_count": 0,
                "relevance_rate": 0.0,
            }

        relevant = sum(1 for f in self._feedback_history if f.relevant)
        total = len(self._feedback_history)

        return {
            "total_feedback": total,
            "relevant_count": relevant,
            "irrelevant_count": total - relevant,
            "relevance_rate": relevant / total if total > 0 else 0.0,
        }


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
                similarity = self._compute_similarity(
                    query_embedding, entry.query_embedding
                )

                if (
                    similarity >= self.config.similarity_threshold
                    and similarity > best_similarity
                ):
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
            key
            for key, entry in self._cache.items()
            if now - entry.created_at >= self.config.ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Evicted {len(expired_keys)} expired search cache entries")

        # Phase 2: LRU eviction if still over limit
        if len(self._cache) > self.config.max_entries:
            # Sort by created_at (oldest first)
            sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].created_at)

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
            remaining_batches = (
                self.total_batches - self.completed_batches - self.failed_batches
            )
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


def _row_to_chunk_default(row: dict[str, Any]) -> CodeChunk:
    """Default conversion from LanceDB row to CodeChunk."""
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

    def _fetch_batch(self, offset: int) -> list[dict[str, Any]]:
        """Fetch a batch of rows from the table.

        Args:
            offset: Starting offset for this batch.

        Returns:
            List of row dictionaries.
        """
        query = self._table.search()

        if self._filter_expr:
            query = query.where(self._filter_expr)

        if self._columns:
            query = query.select(self._columns)

        # LanceDB uses limit() for batch size
        # We simulate offset by fetching limit+offset and slicing
        # For large offsets, this is inefficient - consider cursor-based pagination
        if offset > 0:
            # Fetch enough rows to skip past offset
            rows = query.limit(offset + self._batch_size).to_list()
            return rows[offset : offset + self._batch_size]
        else:
            return query.limit(self._batch_size).to_list()

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
            except Exception:
                # Fallback to configured max
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


@dataclass
class LatencyStats:
    """Statistics for tracking search query latency."""

    latencies: list[float] = field(default_factory=list)
    window_size: int = 10
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, latency_ms: float) -> None:
        """Record a search latency measurement.

        Args:
            latency_ms: Latency in milliseconds.
        """
        with self._lock:
            self.latencies.append(latency_ms)
            # Keep only the most recent measurements
            if len(self.latencies) > self.window_size:
                self.latencies = self.latencies[-self.window_size :]

    def get_average(self) -> float | None:
        """Get the average latency over the recent window.

        Returns:
            Average latency in milliseconds, or None if no data.
        """
        with self._lock:
            if not self.latencies:
                return None
            return sum(self.latencies) / len(self.latencies)

    def get_count(self) -> int:
        """Get the number of recorded latencies.

        Returns:
            Number of latency measurements recorded.
        """
        with self._lock:
            return len(self.latencies)

    def clear(self) -> None:
        """Clear all recorded latencies."""
        with self._lock:
            self.latencies.clear()


class LazyIndexManager:
    """Manages deferred/lazy vector index creation for VectorStore.

    This class implements lazy index creation to improve initial indexing performance.
    Instead of creating vector indexes immediately when the table reaches the threshold,
    index creation is deferred to a background task or triggered on-demand when search
    latency exceeds a configured threshold.

    Attributes:
        config: Configuration for lazy index behavior.
    """

    def __init__(
        self,
        vectorstore: "VectorStore",
        config: LazyIndexConfig | None = None,
    ):
        """Initialize the lazy index manager.

        Args:
            vectorstore: The VectorStore instance to manage indexes for.
            config: Optional configuration. If None, uses default LazyIndexConfig.
        """
        self._vectorstore = vectorstore
        self.config = config if config is not None else LazyIndexConfig()
        self._index_pending = False
        self._index_task: asyncio.Task | None = None
        self._index_ready = asyncio.Event()
        self._latency_stats = LatencyStats(window_size=self.config.latency_window_size)
        self._lock = threading.RLock()
        self._creation_in_progress = False
        self._index_created = False
        # Callbacks for index ready event
        self._on_index_ready_callbacks: list[Callable[[], None]] = []

    def mark_index_pending(self) -> None:
        """Mark that vector index creation is pending.

        Called when the table reaches the minimum row threshold during initial
        indexing, to indicate that an index should be created in the background.
        """
        with self._lock:
            if not self._index_created:
                self._index_pending = True
                logger.debug("Vector index creation marked as pending")

    def mark_index_created(self) -> None:
        """Mark that vector index has been created.

        Called after successful index creation to update internal state.
        """
        with self._lock:
            self._index_pending = False
            self._index_created = True
            self._creation_in_progress = False
            self._index_ready.set()
            logger.debug("Vector index marked as created")

            # Invoke callbacks
            for callback in self._on_index_ready_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Index ready callback failed: {e}")

    def is_index_pending(self) -> bool:
        """Check if vector index creation is pending.

        Returns:
            True if index creation is pending but not yet started/completed.
        """
        with self._lock:
            return self._index_pending and not self._index_created

    def is_index_ready(self) -> bool:
        """Check if the vector index is ready.

        Returns:
            True if the index has been created and is ready for use.
        """
        with self._lock:
            return self._index_created

    def is_creation_in_progress(self) -> bool:
        """Check if index creation is currently in progress.

        Returns:
            True if background index creation is running.
        """
        with self._lock:
            return self._creation_in_progress

    def record_search_latency(self, latency_ms: float) -> None:
        """Record a search query latency measurement.

        Args:
            latency_ms: Search latency in milliseconds.
        """
        self._latency_stats.record(latency_ms)

    def should_create_index(self) -> bool:
        """Check if index should be created based on latency statistics.

        Returns True if:
        - Lazy indexing is enabled
        - Index hasn't been created yet
        - Index creation isn't already in progress
        - Either index is marked pending, or average latency exceeds threshold

        Returns:
            True if index creation should be triggered.
        """
        if not self.config.enabled:
            return False

        with self._lock:
            if self._index_created or self._creation_in_progress:
                return False

            # Check if explicitly pending
            if self._index_pending:
                return True

            # Check latency threshold
            avg_latency = self._latency_stats.get_average()
            if avg_latency is not None:
                # Need enough samples to make a decision
                if self._latency_stats.get_count() >= 3:
                    return avg_latency > self.config.latency_threshold_ms

            return False

    async def schedule_index_creation(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Schedule index creation as a background task.

        If index creation is already in progress or completed, this is a no-op.

        Args:
            progress_callback: Optional callback for progress updates.
                Called with status messages during index creation.
        """
        with self._lock:
            if self._index_created or self._creation_in_progress:
                logger.debug("Index already created or in progress, skipping schedule")
                return
            if self._index_task is not None and not self._index_task.done():
                logger.debug("Index creation task already scheduled")
                return

            self._creation_in_progress = True

        logger.info("Scheduling background vector index creation")

        async def _create_index_task():
            try:
                await self.create_index_now(progress_callback=progress_callback)
            except Exception as e:
                logger.error(f"Background index creation failed: {e}")
                with self._lock:
                    self._creation_in_progress = False
                raise

        self._index_task = asyncio.create_task(_create_index_task())

    async def wait_for_index(self, timeout: float | None = None) -> bool:
        """Wait for the index to be ready.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if index is ready, False if timeout occurred.
        """
        if self.is_index_ready():
            return True

        try:
            await asyncio.wait_for(self._index_ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def create_index_now(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Force immediate index creation.

        Creates the vector index synchronously (within an async context).
        This is useful when you need the index to be ready before proceeding.

        Args:
            progress_callback: Optional callback for progress updates.

        Raises:
            RuntimeError: If table doesn't exist or has insufficient rows.
        """
        table = self._vectorstore._get_table()
        if table is None:
            raise RuntimeError("Cannot create index: table does not exist")

        with self._lock:
            if self._index_created:
                logger.debug("Index already created, skipping")
                return
            self._creation_in_progress = True

        try:
            num_rows = table.count_rows()
            if num_rows < self.config.min_rows:
                logger.debug(
                    f"Skipping index creation: {num_rows} rows < {self.config.min_rows} threshold"
                )
                return

            if progress_callback:
                progress_callback(f"Creating vector index for {num_rows} rows...")

            logger.info(f"Creating vector index for {num_rows} rows")

            # Calculate optimal number of partitions
            num_partitions = min(max(int(math.sqrt(num_rows)), 16), 256)

            # Run the actual index creation
            # This is CPU-bound, so we run it in an executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: table.create_index(
                    metric="L2",
                    num_partitions=num_partitions,
                    num_sub_vectors=16,
                ),
            )

            if progress_callback:
                progress_callback("Vector index created successfully")

            logger.info(
                f"Created vector index with {num_partitions} partitions for {num_rows} vectors"
            )

            self.mark_index_created()

        except (ValueError, RuntimeError, OSError) as e:
            logger.warning(f"Could not create vector index: {e}")
            with self._lock:
                self._creation_in_progress = False
            raise

    def on_index_ready(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when the index is ready.

        If the index is already ready, the callback is invoked immediately.

        Args:
            callback: Function to call when index is ready.
        """
        with self._lock:
            if self._index_created:
                # Already ready, invoke immediately
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Index ready callback failed: {e}")
            else:
                self._on_index_ready_callbacks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the lazy index manager.

        Returns:
            Dictionary with manager statistics.
        """
        with self._lock:
            avg_latency = self._latency_stats.get_average()
            return {
                "enabled": self.config.enabled,
                "index_pending": self._index_pending,
                "index_created": self._index_created,
                "creation_in_progress": self._creation_in_progress,
                "latency_threshold_ms": self.config.latency_threshold_ms,
                "min_rows": self.config.min_rows,
                "average_latency_ms": avg_latency,
                "latency_samples": self._latency_stats.get_count(),
                "should_create_index": self.should_create_index(),
            }

    def reset(self) -> None:
        """Reset the manager state.

        Clears all state including pending flag, created flag, and latency stats.
        Useful for testing or when re-indexing from scratch.
        """
        with self._lock:
            self._index_pending = False
            self._index_created = False
            self._creation_in_progress = False
            self._index_ready.clear()
            self._latency_stats.clear()
            self._on_index_ready_callbacks.clear()
            if self._index_task is not None and not self._index_task.done():
                self._index_task.cancel()
            self._index_task = None


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

        # Handle vector index - either create immediately or mark as pending for lazy creation
        if not has_vector_index:
            try:
                num_rows = self._table.count_rows()
                if self._lazy_index_manager.config.enabled:
                    # Lazy indexing: mark as pending if table is large enough
                    if num_rows >= self._lazy_index_manager.config.min_rows:
                        self._lazy_index_manager.mark_index_pending()
                        logger.debug(
                            f"Vector index creation deferred (lazy mode): {num_rows} rows"
                        )
                else:
                    # Eager indexing: create immediately
                    self._create_vector_index(num_rows)
            except (RuntimeError, OSError) as e:
                logger.debug(f"Could not check row count for vector indexing: {e}")
        else:
            # Index already exists, mark as created in lazy manager
            self._lazy_index_manager.mark_index_created()

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

        Note: This method is used for synchronous/eager index creation.
        For lazy/deferred index creation, use the LazyIndexManager instead.

        Args:
            num_rows: Number of rows in the table (used to determine if indexing is beneficial).
        """
        if self._table is None:
            return

        # Use threshold from lazy index config if available
        min_rows_for_index = self._lazy_index_manager.config.min_rows

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

            # Mark index as created in lazy index manager
            self._lazy_index_manager.mark_index_created()

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
                        or "rate" in error_str
                        and "limit" in error_str
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
        self,
        texts: list[str],
        batch_size: int | None = None,
        log_progress: bool = False,
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
            result = await self._embed_single_batch_with_retry(
                0, batches[0], progress, semaphore
            )
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
            logger.error(
                f"Embedding failed for {len(errors)} batches:\n{error_summary}"
            )

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
                    f"Vector index creation deferred (lazy mode): {num_rows} rows. "
                    "Index will be created in background or on-demand."
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

        logger.debug(f"Adding {len(chunks)} chunks to existing table")
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
                logger.warning(f"Invalid search profile '{profile}', using default")
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
            f"Searching for: '{query[:50]}...' limit={limit} "
            f"profile={resolved_profile.value} min_sim={effective_min_similarity}"
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
            score = 1.0 - row.get("_distance", 0)  # Convert distance to similarity
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
                f"Auto-enabling fuzzy search due to poor results "
                f"(best score below {fuzzy_config.auto_fuzzy_threshold})"
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
                    logger.debug(f"Generated suggestions: {suggestions}")
            except Exception as e:
                logger.warning(f"Failed to generate suggestions: {e}")

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
            logger.debug(f"No results found, but have suggestions: {suggestions}")

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
                logger.warning(f"Invalid search profile '{profile}', using default")
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
            f"Paginated search for: '{query[:50]}...' limit={limit} offset={offset} "
            f"profile={resolved_profile.value}"
        )

        # Parse cursor if provided (format: "offset:{number}")
        if cursor:
            try:
                if cursor.startswith("offset:"):
                    offset = int(cursor[7:])
            except (ValueError, IndexError):
                logger.warning(
                    f"Invalid cursor format: {cursor}, using offset={offset}"
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
        all_results = [
            row
            for row in all_results
            if (1.0 - row.get("_distance", 0)) >= effective_min_similarity
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
            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=1.0 - row.get("_distance", 0),
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

        # Stream through table in batches
        languages: dict[str, int] = {}
        chunk_types: dict[str, int] = {}
        file_set: set[str] = set()

        # Use columnar projection to only fetch needed columns
        columns = ["language", "chunk_type", "file_path"]
        offset = 0

        while offset < total_chunks:
            # Fetch batch with only needed columns
            rows = table.search().select(columns).limit(offset + batch_size).to_list()
            # Slice to get just this batch (simulating offset)
            batch_rows = rows[offset : offset + batch_size]

            if not batch_rows:
                break

            # Process batch
            for row in batch_rows:
                lang = str(row["language"])
                ctype = str(row["chunk_type"])
                fpath = str(row["file_path"])

                languages[lang] = languages.get(lang, 0) + 1
                chunk_types[ctype] = chunk_types.get(ctype, 0) + 1
                file_set.add(fpath)

            offset += len(batch_rows)

            # Log progress for very large datasets
            if offset % 100_000 == 0:
                logger.debug(
                    f"Stats streaming progress: {offset}/{total_chunks} rows processed"
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

        # Process in batches directly instead of using ChunkIterator
        # (ChunkIterator expects full CodeChunk conversion)
        offset = 0
        total_count = table.count_rows()

        while offset < total_count:
            # Fetch batch with columnar projection
            rows = (
                table.search()
                .where("chunk_type IN ('class', 'function')")
                .select(columns)
                .limit(offset + batch_size)
                .to_list()
            )
            # Slice for this batch
            batch_rows = rows[offset : offset + batch_size]

            if not batch_rows:
                break

            # Process each row in the batch
            for row in batch_rows:
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

            offset += len(batch_rows)

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
