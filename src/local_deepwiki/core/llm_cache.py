"""LLM response cache using LanceDB for vector similarity search."""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any, cast

import lancedb
from lancedb.table import Table

from local_deepwiki.config import LLMCacheConfig
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import EmbeddingProvider

logger = get_logger(__name__)


class LLMCache:
    """Vector-based cache for LLM responses with exact and similarity matching.

    Uses a hybrid approach:
    1. Fast path: Exact SHA256 hash match on (system_prompt + prompt)
    2. Slow path: Embedding similarity search for semantic matches

    Cache entries expire based on TTL and are evicted using LRU when max_entries is reached.
    """

    TABLE_NAME = "llm_cache"

    def __init__(
        self,
        cache_path: Path,
        embedding_provider: EmbeddingProvider,
        config: LLMCacheConfig,
    ):
        """Initialize the LLM cache.

        Args:
            cache_path: Path to the LanceDB cache database.
            embedding_provider: Provider for generating prompt embeddings.
            config: Cache configuration.
        """
        self.cache_path = cache_path
        self.embedding_provider = embedding_provider
        # Store a defensive copy to prevent external mutation
        self.config = config.model_copy(deep=True)
        self._db: lancedb.DBConnection | None = None
        self._table: Table | None = None
        self._stats = {"hits": 0, "misses": 0, "skipped": 0}

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()

    @staticmethod
    def _compute_hash(system_prompt: str | None, prompt: str) -> str:
        """Compute exact match hash for fast lookup.

        Args:
            system_prompt: System prompt used.
            prompt: User prompt.

        Returns:
            SHA256 hash of the combined prompts.
        """
        combined = f"{system_prompt or ''}\n---\n{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _connect(self) -> lancedb.DBConnection:
        """Get or create database connection."""
        if self._db is None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self.cache_path))
        return self._db

    def _get_table(self) -> Table | None:
        """Get the cache table if it exists."""
        if self._table is None:
            db = self._connect()
            if self.TABLE_NAME in db.list_tables().tables:
                self._table = db.open_table(self.TABLE_NAME)
        return self._table

    def _ensure_table(self, embedding_dim: int) -> Table | None:
        """Ensure the cache table exists with proper schema.

        Args:
            embedding_dim: Dimension of embedding vectors (unused, kept for API compat).

        Returns:
            The cache table if it exists, None otherwise.
            Table is created on first insert via get_or_cache().
        """
        if self._table is not None:
            return self._table

        db = self._connect()
        if self.TABLE_NAME in db.list_tables().tables:
            self._table = db.open_table(self.TABLE_NAME)
            return self._table

        # Table doesn't exist yet - will be created on first insert
        logger.debug("LLM cache table does not exist yet at %s", self.cache_path)
        return None

    def _is_valid_entry(self, entry: dict[str, Any]) -> bool:
        """Check if a cache entry is still valid (not expired).

        Args:
            entry: Cache entry record.

        Returns:
            True if entry is valid, False if expired.
        """
        created_at = cast(float, entry.get("created_at", 0))
        ttl = cast(float, entry.get("ttl_seconds", self.config.ttl_seconds))
        age = time.time() - created_at
        return age < ttl

    async def _exact_hash_lookup(
        self, table: Table, exact_hash: str
    ) -> dict[str, Any] | None:
        """Try an exact hash lookup. Returns the entry dict on hit, or None."""
        try:
            results = (
                table.search().where(f"exact_hash = '{exact_hash}'").limit(1).to_list()
            )
            if results and self._is_valid_entry(results[0]):
                return results[0]
        except (KeyError, ValueError, RuntimeError, OSError) as e:
            logger.debug("Exact hash lookup failed: %s", e)
        return None

    async def _similarity_lookup(
        self, table: Table, prompt: str, model_name: str
    ) -> dict[str, Any] | None:
        """Try a vector similarity lookup. Returns the first valid matching entry, or None."""
        try:
            query_embedding = (await self.embedding_provider.embed([prompt]))[0]
            similar_results = table.search(query_embedding).limit(5).to_list()
            for result in similar_results:
                similarity = 1.0 - result.get("_distance", 1.0)
                if similarity >= self.config.similarity_threshold:
                    if result.get(
                        "model_name", ""
                    ) == model_name and self._is_valid_entry(result):
                        logger.debug(
                            "Cache similarity hit: similarity=%.3f, entry=%s...",
                            similarity,
                            result["id"][:8],
                        )
                        return result
        except (KeyError, ValueError, RuntimeError, OSError) as e:
            logger.debug("Similarity search failed: %s", e)
        return None

    async def _deserialize_cached_response(
        self,
        entry: dict[str, Any],
        label: str,
    ) -> str:
        """Record a hit for *entry* and return its response string."""
        self._stats["hits"] += 1
        logger.debug("Cache %s hit: id=%s...", label, str(entry.get("id", ""))[:8])
        await self._record_hit(entry["id"], entry)
        return cast(str, entry["response"])

    async def get(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        model_name: str = "",
    ) -> str | None:
        """Try to get a cached response.

        Strategy:
        1. Skip if temperature too high (non-deterministic)
        2. Try exact hash match (fast path)
        3. If no exact match, try embedding similarity search (slow path)
        4. Return None if no suitable cache hit

        Args:
            prompt: User prompt.
            system_prompt: System prompt.
            temperature: LLM temperature used.
            model_name: Name of the LLM model.

        Returns:
            Cached response if found and valid, None otherwise.
        """
        if temperature > self.config.max_cacheable_temperature:
            self._stats["skipped"] += 1
            logger.debug(
                "Cache skip: temperature %s > max %s",
                temperature,
                self.config.max_cacheable_temperature,
            )
            return None

        table = self._get_table()
        if table is None:
            self._stats["misses"] += 1
            return None

        exact_hash = self._compute_hash(system_prompt, prompt)

        entry = await self._exact_hash_lookup(table, exact_hash)
        if entry is not None:
            return await self._deserialize_cached_response(entry, "exact")

        entry = await self._similarity_lookup(table, prompt, model_name)
        if entry is not None:
            return await self._deserialize_cached_response(entry, "similarity")

        self._stats["misses"] += 1
        return None

    async def set(
        self,
        prompt: str,
        response: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        model_name: str = "",
        ttl_seconds: int | None = None,
    ) -> None:
        """Cache an LLM response.

        Args:
            prompt: User prompt.
            response: LLM response to cache.
            system_prompt: System prompt used.
            temperature: LLM temperature used.
            model_name: Name of the LLM model.
            ttl_seconds: Optional TTL override for this entry.
        """
        # Skip if temperature too high
        if temperature > self.config.max_cacheable_temperature:
            logger.debug("Cache skip set: temperature %s > max", temperature)
            return

        try:
            exact_hash = self._compute_hash(system_prompt, prompt)
            prompt_embedding = (await self.embedding_provider.embed([prompt]))[0]
            now = time.time()

            entry_id = str(uuid.uuid4())
            record = {
                "id": entry_id,
                "exact_hash": exact_hash,
                "vector": prompt_embedding,
                "system_prompt": system_prompt or "",
                "prompt": prompt,
                "response": response,
                "temperature": temperature,
                "model_name": model_name,
                "created_at": now,
                "hit_count": 0,
                "last_hit_at": now,
                "ttl_seconds": ttl_seconds or self.config.ttl_seconds,
            }

            db = self._connect()
            if self.TABLE_NAME in db.list_tables().tables:
                table = db.open_table(self.TABLE_NAME)
                table.add([record])
                self._table = table
            else:
                # Create table with first record
                self._table = db.create_table(self.TABLE_NAME, [record])
                # Create index on exact_hash for fast lookups
                try:
                    self._table.create_scalar_index("exact_hash")
                    logger.debug("Created scalar index on exact_hash")
                except (ValueError, RuntimeError, OSError) as e:
                    # ValueError: Index already exists
                    # RuntimeError: Column type not supported
                    # OSError: Storage issues
                    logger.debug("Could not create index: %s", e)

            logger.debug(
                "Cached response: id=%s..., hash=%s...", entry_id[:8], exact_hash[:12]
            )

            # Check if we need to evict old entries
            await self._maybe_evict()

        except (ValueError, RuntimeError, OSError) as e:
            # ValueError: Invalid data format or embedding failure
            # RuntimeError: Database operation failure
            # OSError: File system or storage issues
            logger.warning("Failed to cache response: %s", e)

    async def _record_hit(self, entry_id: str, entry: dict[str, Any]) -> None:
        """Record a cache hit for an entry.

        Updates hit_count and last_hit_at for LRU tracking.
        Since LanceDB doesn't support UPDATE, we delete and re-add the entry.
        The caller passes the already-fetched entry to avoid a redundant query.

        Args:
            entry_id: ID of the cache entry.
            entry: The full cache entry dict (already fetched by get()).
        """
        try:
            table = self._get_table()
            if table is None:
                return

            # Create updated record from the already-fetched entry
            updated_record = {
                "id": entry["id"],
                "exact_hash": entry["exact_hash"],
                "vector": entry["vector"],
                "system_prompt": entry["system_prompt"],
                "prompt": entry["prompt"],
                "response": entry["response"],
                "temperature": entry["temperature"],
                "model_name": entry["model_name"],
                "created_at": entry["created_at"],
                "hit_count": entry.get("hit_count", 0) + 1,
                "last_hit_at": time.time(),
                "ttl_seconds": entry.get("ttl_seconds", self.config.ttl_seconds),
            }

            # Delete old and add updated (LanceDB doesn't support UPDATE)
            table.delete(f"id = '{entry_id}'")
            table.add([updated_record])

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            # KeyError: Entry not found or missing fields
            # ValueError: Invalid query
            # RuntimeError: Database operation failure
            # OSError: Storage issues
            logger.debug("Failed to record hit: %s", e)

    def _delete_entries(self, table: Table, entry_ids: list[str]) -> tuple[int, int]:
        """Delete entries from the table by ID.

        Returns:
            Tuple of (deleted_count, failed_count).
        """
        deleted = 0
        failed = 0
        for entry_id in entry_ids:
            try:
                table.delete(f"id = '{entry_id}'")
                deleted += 1
            except (ValueError, RuntimeError, OSError):
                failed += 1
        return deleted, failed

    def _select_eviction_candidates(
        self,
        all_entries: list[dict[str, Any]],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Partition entries into expired IDs and valid entries for LRU eviction.

        Args:
            all_entries: All fetched entries with eviction-relevant columns.

        Returns:
            Tuple of (expired_ids, valid_entries_sorted_lru).
        """
        expired_ids: list[str] = []
        valid_entries: list[dict[str, Any]] = []
        for entry in all_entries:
            if not self._is_valid_entry(entry):
                expired_ids.append(entry["id"])
            else:
                valid_entries.append(entry)
        # Pre-sort valid entries by LRU order so callers need not sort again
        valid_entries = sorted(
            valid_entries,
            key=lambda e: e.get("last_hit_at", e.get("created_at", 0)),
        )
        return expired_ids, valid_entries

    async def _maybe_evict(self) -> None:
        """Evict old entries if cache exceeds max_entries.

        Uses a two-phase eviction strategy:
        1. First, remove all expired entries (TTL-based)
        2. If still over limit, remove oldest entries by last_hit_at (LRU)

        Eviction is triggered when entry count exceeds max_entries.
        """
        try:
            table = self._get_table()
            if table is None:
                return

            count = table.count_rows()
            if count <= self.config.max_entries:
                return

            logger.info(
                "Cache has %d entries (max: %d), evicting...",
                count,
                self.config.max_entries,
            )

            eviction_columns = ["id", "created_at", "ttl_seconds", "last_hit_at"]
            fetch_limit = min(count, self.config.max_entries * 2)
            all_entries = (
                table.search().select(eviction_columns).limit(fetch_limit).to_list()
            )

            expired_ids, valid_entries = self._select_eviction_candidates(all_entries)

            # Phase 1: delete expired entries
            deleted_count = 0
            if expired_ids:
                deleted_count, failed_count = self._delete_entries(table, expired_ids)
                logger.info("Evicted %s expired cache entries", deleted_count)
                if failed_count:
                    logger.warning(
                        "Failed to evict %d of %d expired entries",
                        failed_count,
                        len(expired_ids),
                    )

            # Phase 2: LRU eviction if still over limit
            remaining_count = count - deleted_count
            if remaining_count > self.config.max_entries and valid_entries:
                target_count = int(self.config.max_entries * 0.8)
                to_evict = remaining_count - target_count
                if to_evict > 0:
                    lru_deleted, lru_failed = self._delete_entries(
                        table, [e["id"] for e in valid_entries[:to_evict]]
                    )
                    logger.info("Evicted %s LRU cache entries", lru_deleted)
                    if lru_failed:
                        logger.warning(
                            "Failed to evict %d of %d LRU entries",
                            lru_failed,
                            to_evict,
                        )

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            logger.warning("Eviction failed: %s", e)

    async def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        try:
            db = self._connect()
            if self.TABLE_NAME in db.list_tables().tables:
                table = db.open_table(self.TABLE_NAME)
                count = cast(int, table.count_rows())
                db.drop_table(self.TABLE_NAME)
                self._table = None
                logger.info("Cleared %s cache entries", count)
                return count
            return 0
        except (RuntimeError, OSError) as e:
            # RuntimeError: Database operation failure
            # OSError: Storage or file system issues
            logger.warning("Failed to clear cache: %s", e)
            return 0

    def get_entry_count(self) -> int:
        """Get the number of entries in the cache.

        Returns:
            Number of cache entries.
        """
        try:
            table = self._get_table()
            if table is None:
                return 0
            return cast(int, table.count_rows())
        except (RuntimeError, OSError):
            # RuntimeError: Database query failure
            # OSError: Storage access issues
            return 0
