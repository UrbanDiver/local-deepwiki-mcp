"""Thread-safe LRU cache for parsed tree-sitter ASTs."""

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedAST:
    """A cached AST entry with metadata for validation and eviction.

    Attributes:
        tree: The tree-sitter Tree object (stored as weak reference internally).
        file_hash: SHA256 hash of the file content when parsed.
        created_at: Unix timestamp when the entry was created.
        language: The programming language of the parsed file.
        last_accessed: Unix timestamp of last access (for LRU eviction).
        estimated_size_bytes: Estimated memory size of the tree.
    """

    tree: Any  # tree_sitter.Tree - using Any to avoid import issues
    file_hash: str
    created_at: float
    language: str
    last_accessed: float = field(default_factory=time.time)
    estimated_size_bytes: int = 0


@dataclass
class ASTCacheStats:
    """Statistics for AST cache operations.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of entries evicted due to max size.
        expirations: Number of entries expired due to TTL.
        invalidations: Number of explicit invalidations.
        total_entries: Current number of entries in cache.
        estimated_memory_bytes: Estimated total memory usage.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    invalidations: int = 0
    total_entries: int = 0
    estimated_memory_bytes: int = 0

    def to_dict(self) -> dict[str, int | float]:
        """Convert stats to a dictionary.

        Returns:
            Dictionary with all statistics.
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "invalidations": self.invalidations,
            "total_entries": self.total_entries,
            "estimated_memory_bytes": self.estimated_memory_bytes,
        }


class ASTCache:
    """Thread-safe LRU cache for parsed ASTs with TTL support.

    Caches tree-sitter ASTs to avoid re-parsing unchanged files during
    incremental indexing. Uses file path + content hash as the cache key
    to ensure cache validity.

    Features:
    - TTL-based expiration
    - LRU eviction when max_entries is exceeded
    - Memory usage estimation
    - Thread-safe operations
    - Cache statistics tracking

    Example:
        cache = ASTCache(max_entries=1000, ttl_seconds=3600)

        # Try to get cached AST
        tree = cache.get(file_path, file_hash)
        if tree is None:
            # Parse the file
            tree = parser.parse(source)
            cache.set(file_path, file_hash, tree, "python")

        # Check statistics
        stats = cache.get_stats()
        print(f"Cache hit rate: {stats['hit_rate']:.2%}")
    """

    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600):
        """Initialize the AST cache.

        Args:
            max_entries: Maximum number of entries before LRU eviction.
            ttl_seconds: Time-to-live for cache entries in seconds.
        """
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, CachedAST] = {}
        self._lock = threading.RLock()
        self._stats = ASTCacheStats()

    def _make_key(self, file_path: str, file_hash: str) -> str:
        """Create a cache key from file path and hash.

        Args:
            file_path: Path to the file.
            file_hash: SHA256 hash of file content.

        Returns:
            Combined cache key string.
        """
        return f"{file_path}:{file_hash}"

    def _is_expired(self, entry: CachedAST) -> bool:
        """Check if a cache entry has expired.

        Args:
            entry: The cache entry to check.

        Returns:
            True if the entry has expired, False otherwise.
        """
        return time.time() - entry.created_at > self._ttl_seconds

    def _estimate_tree_size(self, tree: Any) -> int:
        """Estimate memory size of a tree-sitter Tree.

        This is a rough estimate based on the tree structure. Tree-sitter
        trees can be large for complex files.

        Args:
            tree: The tree-sitter Tree object.

        Returns:
            Estimated size in bytes.
        """
        try:
            # Base size for the Tree object itself
            base_size = sys.getsizeof(tree)

            # Estimate node count from root - traverse a sample
            root = tree.root_node
            if root is None:
                return base_size

            # Count nodes in a limited traversal (avoid full tree walk for performance)
            node_count = 0
            stack = [root]
            max_nodes = 10000  # Limit traversal for large trees

            while stack and node_count < max_nodes:
                node = stack.pop()
                node_count += 1
                stack.extend(node.children)

            # Estimate ~100 bytes per node (node object + text references)
            estimated_node_size = node_count * 100

            return base_size + estimated_node_size
        except (AttributeError, RecursionError, RuntimeError):
            # AttributeError: malformed tree nodes
            # RecursionError: deeply nested ASTs
            # RuntimeError: tree-sitter internal errors
            return 10000  # 10 KB default

    def _evict_lru(self) -> None:
        """Evict least recently used entries until under max_entries.

        Must be called with lock held.
        """
        while len(self._cache) >= self._max_entries:
            if not self._cache:
                break

            # Find LRU entry
            lru_key = min(
                self._cache.keys(), key=lambda k: self._cache[k].last_accessed
            )
            evicted = self._cache.pop(lru_key)
            self._stats.evictions += 1
            self._stats.estimated_memory_bytes -= evicted.estimated_size_bytes

    def get(self, file_path: str, file_hash: str) -> Any | None:
        """Get a cached AST if valid (hash matches and not expired).

        Args:
            file_path: Path to the file (used as part of cache key).
            file_hash: SHA256 hash of the file content.

        Returns:
            The cached tree-sitter Tree if found and valid, None otherwise.
        """
        key = self._make_key(file_path, file_hash)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            # Check expiration
            if self._is_expired(entry):
                self._cache.pop(key, None)
                self._stats.expirations += 1
                self._stats.misses += 1
                self._stats.estimated_memory_bytes -= entry.estimated_size_bytes
                return None

            # Update access time for LRU
            entry.last_accessed = time.time()
            self._stats.hits += 1
            return entry.tree

    def set(self, file_path: str, file_hash: str, tree: Any, language: str) -> None:
        """Cache a parsed AST.

        Args:
            file_path: Path to the file.
            file_hash: SHA256 hash of the file content.
            tree: The tree-sitter Tree object to cache.
            language: The programming language of the file.
        """
        key = self._make_key(file_path, file_hash)
        estimated_size = self._estimate_tree_size(tree)
        current_time = time.time()

        entry = CachedAST(
            tree=tree,
            file_hash=file_hash,
            created_at=current_time,
            language=language,
            last_accessed=current_time,
            estimated_size_bytes=estimated_size,
        )

        with self._lock:
            # Check if we need to evict before adding
            if key not in self._cache:
                self._evict_lru()

            # If updating existing entry, subtract old size
            old_entry = self._cache.get(key)
            if old_entry:
                self._stats.estimated_memory_bytes -= old_entry.estimated_size_bytes

            self._cache[key] = entry
            self._stats.estimated_memory_bytes += estimated_size

    def invalidate(self, file_path: str) -> None:
        """Remove all entries for a specific file from cache.

        This removes entries regardless of their hash, useful when a file
        is known to have been modified.

        Args:
            file_path: Path to the file to invalidate.
        """
        with self._lock:
            # Find all keys that start with this file path
            keys_to_remove = [
                k for k in self._cache.keys() if k.startswith(f"{file_path}:")
            ]
            for key in keys_to_remove:
                entry = self._cache.pop(key, None)
                if entry:
                    self._stats.invalidations += 1
                    self._stats.estimated_memory_bytes -= entry.estimated_size_bytes

    def clear(self) -> None:
        """Clear all cached ASTs."""
        with self._lock:
            self._cache.clear()
            self._stats.estimated_memory_bytes = 0

    def get_stats(self) -> dict[str, int | float]:
        """Return cache statistics.

        Returns:
            Dictionary with cache statistics including hits, misses,
            hit rate, evictions, expirations, invalidations, total entries,
            and estimated memory usage.
        """
        with self._lock:
            self._stats.total_entries = len(self._cache)
            return self._stats.to_dict()

    def cleanup_expired(self) -> int:
        """Remove all expired entries from the cache.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if self._is_expired(v)]
            for key in expired_keys:
                entry = self._cache.pop(key, None)
                if entry:
                    self._stats.expirations += 1
                    self._stats.estimated_memory_bytes -= entry.estimated_size_bytes
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Return current number of entries in cache."""
        with self._lock:
            return len(self._cache)
