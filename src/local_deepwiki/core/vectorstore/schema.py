"""Schema definitions for vectorstore."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from local_deepwiki.models import ChunkType, Language, SearchResult

if TYPE_CHECKING:
    from local_deepwiki.models import CodeChunk

# Valid values for filtering - used to prevent injection attacks
VALID_LANGUAGES = frozenset(lang.value for lang in Language)
VALID_CHUNK_TYPES = frozenset(ct.value for ct in ChunkType)

# Default memory budget for batch operations (256 MB)
DEFAULT_MAX_MEMORY_MB = 256

# Estimated memory per chunk (based on typical chunk size)
# Includes embedding vector (~1536 floats * 4 bytes = 6KB) + content (~2KB avg) + overhead
ESTIMATED_BYTES_PER_CHUNK = 10_000  # ~10KB per chunk


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class ChunkBatch:
    """A batch of chunks loaded from the store.

    Attributes:
        chunks: List of CodeChunk objects in this batch.
        batch_index: Index of this batch (0-based).
        total_batches: Estimated total number of batches.
        has_more: Whether there are more batches to load.
    """

    chunks: list["CodeChunk"]
    batch_index: int
    total_batches: int
    has_more: bool


class SearchProfile(StrEnum):
    """Search profile for precision/recall trade-off.

    Profiles control how exhaustive the search is, trading off speed vs accuracy:
    - FAST: Minimal candidates, fastest response, may miss some relevant results
    - BALANCED: Default behavior, good balance of speed and recall
    - THOROUGH: Exhaustive search, best recall but slower
    """

    FAST = "fast"
    BALANCED = "balanced"
    THOROUGH = "thorough"


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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
        from local_deepwiki.logging import get_logger

        logger = get_logger(__name__)

        with self._lock:
            completed = self.completed_batches
            failed = self.failed_batches
            total = self.total_batches
            elapsed = self.elapsed_seconds

        # Calculate outside lock to avoid deadlock
        progress_pct = (completed + failed) / total * 100 if total > 0 else 0
        if completed > 0:
            avg_time_per_batch = elapsed / completed
            remaining_batches = total - completed - failed
            eta = avg_time_per_batch * remaining_batches
            eta_str = f", ETA: {eta:.1f}s"
        else:
            eta_str = ""

        logger.info(
            "Embedding progress: %d/%d batches (%.1f%%)%s",
            completed,
            total,
            progress_pct,
            eta_str,
        )


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
