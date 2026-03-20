"""Embedding cache to prevent repeated API calls.

This module provides a caching layer for embedding providers that persists
embeddings to disk using SQLite. It uses content hashing for cache keys
and supports TTL-based expiration.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    pass  # forward reference anchor

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import EmbeddingProvider

logger = get_logger(__name__)


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / "local-deepwiki"


@dataclass(slots=True)
class EmbeddingCacheConfig:
    """Configuration for the embedding cache."""

    cache_dir: Path = field(default_factory=_default_cache_dir)
    ttl_seconds: int = 604800  # 7 days default
    max_entries: int = 100000
    batch_write_threshold: int = 100


class _CacheStorage:
    """Low-level SQLite storage helper for EmbeddingCache.

    Delegates all connection management to the owning EmbeddingCache via
    a live attribute lookup (``owner._get_connection()``) so that
    ``unittest.mock.patch.object`` patches applied to ``_get_connection``
    on the owner are always honoured.
    """

    SCHEMA_VERSION = 1

    def __init__(self, owner: EmbeddingCache) -> None:
        # Keep a reference to the owner; _get_connection is resolved at
        # call time so that test-time patches on the owner are respected.
        self._owner = owner

    def _conn(self) -> sqlite3.Connection:
        """Return the current thread's connection via the owner's factory."""
        return self._owner._get_connection()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def create_table(self) -> None:
        """Create tables and indexes if they do not already exist."""
        conn = self._conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS embeddings (
                cache_key TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                created_at REAL NOT NULL,
                ttl_seconds INTEGER NOT NULL,
                model_name TEXT NOT NULL,
                dimension INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_embeddings_created
                ON embeddings(created_at);
            CREATE INDEX IF NOT EXISTS idx_embeddings_model
                ON embeddings(model_name);
            """
        )
        cursor = conn.execute(
            "SELECT value FROM cache_meta WHERE key = 'schema_version'"
        )
        if cursor.fetchone() is None:
            conn.execute(
                "INSERT INTO cache_meta (key, value) VALUES ('schema_version', ?)",
                (str(self.SCHEMA_VERSION),),
            )
        conn.commit()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def query_one(self, cache_key: str) -> sqlite3.Row | None:
        """Return the embeddings row for *cache_key*, or None if absent."""
        cursor = self._conn().execute(
            "SELECT embedding, created_at, ttl_seconds FROM embeddings WHERE cache_key = ?",
            (cache_key,),
        )
        return cursor.fetchone()

    def count(self) -> int:
        """Return the total number of cached embeddings."""
        cursor = self._conn().execute("SELECT COUNT(*) FROM embeddings")
        row = cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def batch_insert(
        self,
        rows: list[tuple[str, bytes, float, int, str, int]],
    ) -> None:
        """Upsert *rows* of (cache_key, blob, created_at, ttl, model, dim)."""
        conn = self._conn()
        conn.executemany(
            """
            INSERT OR REPLACE INTO embeddings
                (cache_key, embedding, created_at, ttl_seconds, model_name, dimension)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Deletes
    # ------------------------------------------------------------------

    def delete_by_key(self, cache_key: str) -> None:
        """Delete a single entry by primary key."""
        conn = self._conn()
        conn.execute("DELETE FROM embeddings WHERE cache_key = ?", (cache_key,))
        conn.commit()

    def delete_all(self) -> int:
        """Delete every entry and return the prior count."""
        conn = self._conn()
        prior = self.count()
        conn.execute("DELETE FROM embeddings")
        conn.commit()
        return prior

    def delete_expired(self, now: float) -> int:
        """Delete entries whose TTL has elapsed; return the number removed."""
        conn = self._conn()
        cursor = conn.execute(
            "DELETE FROM embeddings WHERE (created_at + ttl_seconds) < ?",
            (now,),
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted

    def delete_by_model(self, model_name: str) -> int:
        """Delete all entries for *model_name*; return the number removed."""
        conn = self._conn()
        cursor = conn.execute(
            "DELETE FROM embeddings WHERE model_name = ?",
            (model_name,),
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted

    def delete_oldest(self, n: int) -> int:
        """Delete the *n* oldest entries; return the number removed."""
        conn = self._conn()
        cursor = conn.execute(
            """
            DELETE FROM embeddings WHERE cache_key IN (
                SELECT cache_key FROM embeddings
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (n,),
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Connection teardown
    # ------------------------------------------------------------------

    def close_connection(self, local: threading.local) -> None:
        """Close the thread-local connection stored in *local.conn* if present."""
        conn = getattr(local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            local.conn = None


class EmbeddingCache:
    """SQLite-based embedding cache with content hashing and TTL support.

    This class wraps an EmbeddingProvider and caches embeddings to disk.
    Cache keys are computed from the text content and model name, so the
    same text will return cached embeddings even across different runs.

    Thread-safe for concurrent access.

    Example:
        provider = OpenAIEmbeddingProvider()
        cache = EmbeddingCache(provider)

        # First call - generates embeddings via API
        embeddings = await cache.embed(["hello world"])

        # Second call - returns cached embeddings
        embeddings = await cache.embed(["hello world"])
    """

    SCHEMA_VERSION = 1
    DB_FILENAME = "embedding_cache.db"

    def __init__(
        self,
        provider: EmbeddingProvider,
        config: EmbeddingCacheConfig | None = None,
    ):
        """Initialize the embedding cache.

        Args:
            provider: The underlying embedding provider to wrap.
            config: Optional cache configuration. Uses defaults if not provided.
        """
        self._provider = provider
        self._config = config or EmbeddingCacheConfig()
        self._db_path = self._config.cache_dir / self.DB_FILENAME
        self._lock = threading.Lock()
        self._local = threading.local()
        self._stats = {"hits": 0, "misses": 0, "errors": 0}
        self._pending_writes: list[tuple[str, list[float], float, int]] = []

        # Ensure cache directory exists
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)

        # Storage helper — holds a reference to self so that patches to
        # _get_connection applied after construction are always honoured.
        self._storage = _CacheStorage(self)

        # Initialize database schema
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management (kept here so tests can patch _get_connection)
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection.

        Returns:
            SQLite connection for the current thread.
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self._db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            # Enable WAL mode for better concurrent access
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Initialize the database schema."""
        try:
            self._storage.create_table()
            logger.debug("Embedding cache initialized at %s", self._db_path)
        except (sqlite3.Error, OSError) as e:
            # sqlite3.Error: Database schema creation failures
            # OSError: File system or database file access errors
            logger.warning("Failed to initialize embedding cache: %s", e)

    # ------------------------------------------------------------------
    # Business-logic helpers
    # ------------------------------------------------------------------

    def _compute_cache_key(self, text: str) -> str:
        """Compute a cache key for the given text and model.

        The cache key is a SHA-256 hash of the text content combined with
        the model name, ensuring that different models have separate caches.

        Args:
            text: The text to compute a key for.

        Returns:
            A hex-encoded SHA-256 hash string.
        """
        # Combine text with model name to ensure model-specific caching
        combined = f"{self._provider.name}:{text}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_valid_entry(row: sqlite3.Row) -> bool:
        """Check if a cache entry is still valid (not expired).

        Args:
            row: Database row with created_at and ttl_seconds fields.

        Returns:
            True if entry is valid, False if expired.
        """
        created_at = cast(float, row["created_at"])
        ttl = cast(int, row["ttl_seconds"])
        age = time.time() - created_at
        return age < ttl

    @staticmethod
    def _serialize_embedding(embedding: list[float]) -> bytes:
        """Serialize an embedding vector to bytes for storage.

        Uses JSON for simplicity and compatibility. For higher performance
        with very large caches, consider struct.pack or numpy.

        Args:
            embedding: The embedding vector.

        Returns:
            Serialized bytes.
        """
        return json.dumps(embedding).encode("utf-8")

    @staticmethod
    def _deserialize_embedding(data: bytes) -> list[float]:
        """Deserialize an embedding vector from bytes.

        Args:
            data: Serialized embedding bytes.

        Returns:
            The embedding vector.
        """
        return cast(list[float], json.loads(data.decode("utf-8")))

    # ------------------------------------------------------------------
    # Cache read / write
    # ------------------------------------------------------------------

    def _get_cached(self, cache_key: str) -> list[float] | None:
        """Try to get a cached embedding.

        Args:
            cache_key: The cache key to look up.

        Returns:
            The cached embedding vector, or None if not found/expired.
        """
        try:
            row = self._storage.query_one(cache_key)

            if row is None:
                return None

            if not self._is_valid_entry(row):
                # Entry expired — remove it
                self._storage.delete_by_key(cache_key)
                return None

            return self._deserialize_embedding(row["embedding"])

        except sqlite3.Error as e:
            logger.debug("Cache lookup failed: %s", e)
            self._stats["errors"] += 1
            return None

    def _set_cached(
        self,
        cache_key: str,
        embedding: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        """Stage an embedding for storage (flushed in batch).

        Args:
            cache_key: The cache key.
            embedding: The embedding vector to store.
            ttl_seconds: Optional TTL override.
        """
        ttl = ttl_seconds or self._config.ttl_seconds
        now = time.time()

        # Add to pending writes
        self._pending_writes.append((cache_key, embedding, now, ttl))

        # Flush if threshold reached
        if len(self._pending_writes) >= self._config.batch_write_threshold:
            self._flush_pending_writes()

    def _flush_pending_writes(self) -> None:
        """Flush all pending writes to the database."""
        if not self._pending_writes:
            return

        with self._lock:
            writes = self._pending_writes[:]
            self._pending_writes.clear()

        if not writes:
            return

        try:
            model_name = self._provider.name
            rows = [
                (
                    key,
                    self._serialize_embedding(emb),
                    created_at,
                    ttl,
                    model_name,
                    len(emb),
                )
                for key, emb, created_at, ttl in writes
            ]
            self._storage.batch_insert(rows)
            logger.debug("Flushed %s embeddings to cache", len(writes))

        except sqlite3.Error as e:
            logger.warning("Failed to write embeddings to cache: %s", e)
            self._stats["errors"] += 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, using cache when available.

        This method checks the cache for each text and only calls the underlying
        provider for texts that are not cached. Results are then stored in the
        cache for future use.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        # Check cache for each text
        cache_keys = [self._compute_cache_key(text) for text in texts]
        results: list[list[float] | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        for i, (text, cache_key) in enumerate(zip(texts, cache_keys)):
            cached = self._get_cached(cache_key)
            if cached is not None:
                results[i] = cached
                self._stats["hits"] += 1
            else:
                texts_to_embed.append((i, text))
                self._stats["misses"] += 1

        # Log cache performance
        if texts_to_embed:
            logger.debug(
                "Embedding cache: %d/%d hits, fetching %d from provider",
                len(texts) - len(texts_to_embed),
                len(texts),
                len(texts_to_embed),
            )

        # Fetch uncached embeddings from provider
        if texts_to_embed:
            indices, uncached_texts = zip(*texts_to_embed)
            new_embeddings = await self._provider.embed(list(uncached_texts))

            # Store results and cache them
            for idx, embedding in zip(indices, new_embeddings):
                results[idx] = embedding
                cache_key = cache_keys[idx]
                self._set_cached(cache_key, embedding)

        # Ensure all pending writes are flushed
        self._flush_pending_writes()

        # All results should be filled now
        return cast(list[list[float]], results)

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        return self._provider.dimension

    @property
    def name(self) -> str:
        """Get the provider name (includes cache indicator)."""
        return f"cached:{self._provider.name}"

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, and errors counts.
        """
        return self._stats.copy()

    def get_entry_count(self) -> int:
        """Get the number of entries in the cache.

        Returns:
            Number of cache entries.
        """
        try:
            return self._storage.count()
        except sqlite3.Error:
            return 0

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        try:
            count = self._storage.delete_all()
            logger.info("Cleared %s embedding cache entries", count)
            return count
        except sqlite3.Error as e:
            logger.warning("Failed to clear embedding cache: %s", e)
            return 0

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed.
        """
        try:
            deleted = self._storage.delete_expired(time.time())
            if deleted > 0:
                logger.info("Cleaned up %s expired embedding cache entries", deleted)
            return deleted
        except sqlite3.Error as e:
            logger.warning("Failed to cleanup expired entries: %s", e)
            return 0

    def cleanup_if_needed(self) -> int:
        """Clean up cache if it exceeds max_entries.

        Removes oldest entries (by creation time) when the cache exceeds
        the configured maximum size. Also removes expired entries.

        Returns:
            Number of entries removed.
        """
        try:
            # First, remove expired entries
            expired_count = self.cleanup_expired()

            # Check current count
            count = self._storage.count()

            if count <= self._config.max_entries:
                return expired_count

            # Calculate how many to remove (remove 10% buffer)
            to_remove = count - int(self._config.max_entries * 0.9)
            deleted = self._storage.delete_oldest(to_remove)

            logger.info(
                "Cache cleanup: removed %d expired + %d oldest entries",
                expired_count,
                deleted,
            )
            return expired_count + deleted

        except sqlite3.Error as e:
            logger.warning("Cache cleanup failed: %s", e)
            return 0

    def invalidate_by_model(self, model_name: str) -> int:
        """Invalidate all cache entries for a specific model.

        Useful when switching models or when a model is updated.

        Args:
            model_name: The model name to invalidate entries for.

        Returns:
            Number of entries invalidated.
        """
        try:
            deleted = self._storage.delete_by_model(model_name)
            if deleted > 0:
                logger.info(
                    "Invalidated %d cache entries for model %s", deleted, model_name
                )
            return deleted
        except sqlite3.Error as e:
            logger.warning("Failed to invalidate model cache: %s", e)
            return 0

    def __enter__(self) -> EmbeddingCache:
        """Enter context manager."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit context manager, closing all connections."""
        self.close()

    def close(self) -> None:
        """Close all database connections.

        Should be called when the cache is no longer needed to ensure
        all pending writes are flushed and connections are closed cleanly.
        Closes thread-local connections from all threads that accessed this cache.
        """
        # Flush any pending writes
        self._flush_pending_writes()

        # Close thread-local connection if it exists in current thread
        self._storage.close_connection(self._local)

    def __del__(self) -> None:
        """Destructor to ensure connections are closed.

        Note: This is a safety net for cleanup during interpreter shutdown.
        Explicit close() calls are preferred.
        """
        try:
            self.close()
        except Exception:  # noqa: BLE001 — destructor must not fail during interpreter shutdown when objects may already be gone
            pass


class CachedEmbeddingProvider(EmbeddingProvider):
    """Embedding provider wrapper that adds caching.

    This class implements the EmbeddingProvider interface and wraps another
    provider with caching functionality. It can be used as a drop-in replacement
    for any EmbeddingProvider.

    Example:
        base_provider = OpenAIEmbeddingProvider()
        cached_provider = CachedEmbeddingProvider(base_provider)

        # Use cached_provider anywhere an EmbeddingProvider is expected
        vector_store = VectorStore(db_path, cached_provider)
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        config: EmbeddingCacheConfig | None = None,
    ):
        """Initialize the cached embedding provider.

        Args:
            provider: The underlying embedding provider to wrap.
            config: Optional cache configuration.
        """
        self._cache = EmbeddingCache(provider, config)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        return await self._cache.embed(texts)

    @property
    def dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        return self._cache.get_dimension()

    @property
    def name(self) -> str:
        """Get the provider name."""
        return self._cache.name

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return self._cache.stats

    def get_entry_count(self) -> int:
        """Get the number of entries in the cache."""
        return self._cache.get_entry_count()

    def clear_cache(self) -> int:
        """Clear all cache entries."""
        return self._cache.clear()

    def cleanup_cache(self) -> int:
        """Clean up expired and excess cache entries."""
        return self._cache.cleanup_if_needed()

    def close(self) -> None:
        """Close the cache."""
        self._cache.close()
