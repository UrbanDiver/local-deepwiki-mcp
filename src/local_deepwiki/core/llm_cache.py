"""LLM response cache using LanceDB for vector similarity search."""

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

    def _compute_hash(self, system_prompt: str | None, prompt: str) -> str:
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
        logger.debug(f"LLM cache table does not exist yet at {self.cache_path}")
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
        # Skip if temperature too high (non-deterministic responses)
        if temperature > self.config.max_cacheable_temperature:
            self._stats["skipped"] += 1
            logger.debug(
                f"Cache skip: temperature {temperature} > max {self.config.max_cacheable_temperature}"
            )
            return None

        table = self._get_table()
        if table is None:
            self._stats["misses"] += 1
            return None

        exact_hash = self._compute_hash(system_prompt, prompt)

        # Fast path: exact hash match
        try:
            # LanceDB filter query for exact hash
            exact_results = (
                table.search().where(f"exact_hash = '{exact_hash}'").limit(1).to_list()
            )

            if exact_results:
                entry = exact_results[0]
                if self._is_valid_entry(entry):
                    self._stats["hits"] += 1
                    logger.debug(f"Cache exact hit: hash={exact_hash[:12]}...")
                    # Update hit tracking (pass entry to avoid re-fetch)
                    await self._record_hit(entry["id"], entry)
                    return cast(str, entry["response"])
        except (KeyError, ValueError, RuntimeError, OSError) as e:
            # KeyError: Missing field in result
            # ValueError: Invalid query or filter expression
            # RuntimeError: LanceDB query execution error
            # OSError: Database file access issues
            logger.debug(f"Exact hash lookup failed: {e}")

        # Slow path: embedding similarity search
        try:
            query_embedding = (await self.embedding_provider.embed([prompt]))[0]

            # Search for similar prompts with same model
            similar_results = table.search(query_embedding).limit(5).to_list()

            for result in similar_results:
                # Calculate similarity from distance
                similarity = 1.0 - result.get("_distance", 1.0)

                if similarity >= self.config.similarity_threshold:
                    # Check model match and validity
                    if result.get(
                        "model_name", ""
                    ) == model_name and self._is_valid_entry(result):
                        self._stats["hits"] += 1
                        logger.debug(
                            f"Cache similarity hit: similarity={similarity:.3f}, "
                            f"entry={result['id'][:8]}..."
                        )
                        await self._record_hit(result["id"], result)
                        return cast(str, result["response"])
        except (KeyError, ValueError, RuntimeError, OSError) as e:
            # KeyError: Missing field in search result
            # ValueError: Invalid embedding or search parameters
            # RuntimeError: Vector search execution error
            # OSError: Database access issues
            logger.debug(f"Similarity search failed: {e}")

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
            logger.debug(f"Cache skip set: temperature {temperature} > max")
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
                    logger.debug(f"Could not create index: {e}")

            logger.debug(
                f"Cached response: id={entry_id[:8]}..., hash={exact_hash[:12]}..."
            )

            # Check if we need to evict old entries
            await self._maybe_evict()

        except (ValueError, RuntimeError, OSError) as e:
            # ValueError: Invalid data format or embedding failure
            # RuntimeError: Database operation failure
            # OSError: File system or storage issues
            logger.warning(f"Failed to cache response: {e}")

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
            logger.debug(f"Failed to record hit: {e}")

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

            # Count entries
            count = table.count_rows()
            if count <= self.config.max_entries:
                return

            logger.info(
                f"Cache has {count} entries (max: {self.config.max_entries}), evicting..."
            )

            # Fetch only eviction-relevant columns (skip large vector/response fields)
            eviction_columns = ["id", "created_at", "ttl_seconds", "last_hit_at"]
            fetch_limit = min(count, self.config.max_entries * 2)
            all_entries = (
                table.search().select(eviction_columns).limit(fetch_limit).to_list()
            )

            # Phase 1: Identify and delete expired entries
            expired_ids = []
            valid_entries = []
            for entry in all_entries:
                if not self._is_valid_entry(entry):
                    expired_ids.append(entry["id"])
                else:
                    valid_entries.append(entry)

            deleted_count = 0
            failed_count = 0
            if expired_ids:
                for entry_id in expired_ids:
                    try:
                        table.delete(f"id = '{entry_id}'")
                        deleted_count += 1
                    except (ValueError, RuntimeError, OSError):
                        failed_count += 1

                logger.info(f"Evicted {deleted_count} expired cache entries")
                if failed_count:
                    logger.warning(
                        f"Failed to evict {failed_count} of {len(expired_ids)} expired entries"
                    )

            # Phase 2: LRU eviction if still over limit
            remaining_count = count - deleted_count
            if remaining_count > self.config.max_entries:
                # Calculate how many to evict (remove 20% buffer to avoid frequent eviction)
                target_count = int(self.config.max_entries * 0.8)
                to_evict = remaining_count - target_count

                if to_evict > 0 and valid_entries:
                    # Sort by last_hit_at (oldest first = LRU)
                    valid_entries.sort(
                        key=lambda e: e.get("last_hit_at", e.get("created_at", 0))
                    )

                    # Delete oldest entries
                    lru_deleted = 0
                    lru_failed = 0
                    for entry in valid_entries[:to_evict]:
                        try:
                            table.delete(f"id = '{entry['id']}'")
                            lru_deleted += 1
                        except (ValueError, RuntimeError, OSError):
                            lru_failed += 1

                    logger.info(f"Evicted {lru_deleted} LRU cache entries")
                    if lru_failed:
                        logger.warning(
                            f"Failed to evict {lru_failed} of {to_evict} LRU entries"
                        )

        except (KeyError, ValueError, RuntimeError, OSError) as e:
            # KeyError: Missing fields in entries
            # ValueError: Invalid query during eviction
            # RuntimeError: Database operation failure
            # OSError: Storage issues
            logger.warning(f"Eviction failed: {e}")

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
                logger.info(f"Cleared {count} cache entries")
                return count
            return 0
        except (RuntimeError, OSError) as e:
            # RuntimeError: Database operation failure
            # OSError: Storage or file system issues
            logger.warning(f"Failed to clear cache: {e}")
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
