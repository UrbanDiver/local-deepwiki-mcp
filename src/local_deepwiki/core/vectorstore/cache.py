"""Search caching and adaptive search depth estimation."""

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import numpy as np

from local_deepwiki.config import SearchCacheConfig
from local_deepwiki.logging import get_logger
from local_deepwiki.models import SearchResult

from .schema import SearchFeedback

if TYPE_CHECKING:
    from .store import VectorStore

logger = get_logger(__name__)

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
        # Collect updates first, then apply to avoid mutating during iteration
        updates: list[tuple[int, tuple[str, float, int, int]]] = []
        for i, (hist_query, quality, count, depth) in enumerate(self._query_history):
            if hist_query == feedback.query:
                adjustment = 0.1 if feedback.relevant else -0.1
                new_quality = max(0.0, min(1.0, quality + adjustment))
                updates.append((i, (hist_query, new_quality, count, depth)))
        for i, entry in updates:
            self._query_history[i] = entry

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

