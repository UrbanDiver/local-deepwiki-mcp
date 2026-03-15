"""LanceDB vector store for code chunk storage and retrieval.

This package provides vector storage and search capabilities for code chunks.
Split into multiple modules for maintainability while preserving backward compatibility.
"""

from __future__ import annotations

# Re-export all public names for backward compatibility
from local_deepwiki.core.vectorstore.cache import (
    AdaptiveSearcher,
    SearchCache,
    SearchCacheEntry,
)
from local_deepwiki.core.vectorstore.iterators import ChunkIterator, LazyChunkLoader
from local_deepwiki.core.vectorstore.maintenance import LazyIndexManager
from local_deepwiki.core.vectorstore.mixins.search_types import SearchRequest
from local_deepwiki.core.vectorstore.schema import (
    DEFAULT_MAX_MEMORY_MB,
    ESTIMATED_BYTES_PER_CHUNK,
    SEARCH_PROFILES,
    VALID_CHUNK_TYPES,
    VALID_LANGUAGES,
    BatchEmbeddingResult,
    ChunkBatch,
    EmbeddingProgress,
    LatencyStats,
    SearchFeedback,
    SearchProfile,
    SearchProfileConfig,
    SearchResultPage,
)
from local_deepwiki.core.vectorstore.store import VectorStore
from local_deepwiki.core.vectorstore.utils import (
    RateLimiter,
    _row_to_chunk_default,
    _sanitize_string_value,
)

__all__ = [
    # Core store
    "VectorStore",
    # Search request
    "SearchRequest",
    # Schema/data models
    "SearchResultPage",
    "ChunkBatch",
    "SearchProfile",
    "SearchProfileConfig",
    "SearchFeedback",
    "BatchEmbeddingResult",
    "EmbeddingProgress",
    "LatencyStats",
    "SEARCH_PROFILES",
    "VALID_CHUNK_TYPES",
    "VALID_LANGUAGES",
    "DEFAULT_MAX_MEMORY_MB",
    "ESTIMATED_BYTES_PER_CHUNK",
    # Cache
    "AdaptiveSearcher",
    "SearchCache",
    "SearchCacheEntry",
    # Iterators
    "ChunkIterator",
    "LazyChunkLoader",
    # Maintenance
    "LazyIndexManager",
    # Utils
    "RateLimiter",
    # Underscore-prefixed names exposed for test access only
    "_sanitize_string_value",
    "_row_to_chunk_default",
]
