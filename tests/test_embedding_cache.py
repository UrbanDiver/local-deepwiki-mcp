"""Tests for EmbeddingCache and CachedEmbeddingProvider."""

import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.providers.embeddings.cache import (
    CachedEmbeddingProvider,
    EmbeddingCache,
    EmbeddingCacheConfig,
)


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self._name = "mock:test-model"
        self.embed_calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings."""
        self.embed_calls.append(texts)
        return [[float(i) for i in range(self._dimension)] for _ in texts]

    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        return self._dimension

    @property
    def name(self) -> str:
        """Get the provider name."""
        return self._name


class TestEmbeddingCacheConfig:
    """Tests for EmbeddingCacheConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EmbeddingCacheConfig()

        assert config.ttl_seconds == 604800  # 7 days
        assert config.max_entries == 100000
        assert config.batch_write_threshold == 100
        assert config.cache_dir == Path.home() / ".cache" / "local-deepwiki"

    def test_custom_config(self):
        """Test custom configuration values."""
        cache_dir = Path("/tmp/test-cache")
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=3600,
            max_entries=1000,
            batch_write_threshold=10,
        )

        assert config.cache_dir == cache_dir
        assert config.ttl_seconds == 3600
        assert config.max_entries == 1000
        assert config.batch_write_threshold == 10


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def provider(self):
        """Create a mock embedding provider."""
        return MockEmbeddingProvider()

    @pytest.fixture
    def cache(self, cache_dir, provider):
        """Create an EmbeddingCache instance."""
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=3600,
            max_entries=1000,
            batch_write_threshold=1,  # Flush immediately for testing
        )
        return EmbeddingCache(provider, config)

    def test_initialization(self, cache, cache_dir):
        """Test cache initialization."""
        assert cache._db_path == cache_dir / "embedding_cache.db"
        assert cache._db_path.exists()
        assert cache._stats == {"hits": 0, "misses": 0, "errors": 0}

    def test_database_schema(self, cache):
        """Test database schema is created correctly."""
        conn = cache._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "cache_meta" in tables
        assert "embeddings" in tables

    def test_compute_cache_key(self, cache):
        """Test cache key computation."""
        key1 = cache._compute_cache_key("hello world")
        key2 = cache._compute_cache_key("hello world")
        key3 = cache._compute_cache_key("different text")

        # Same text should produce same key
        assert key1 == key2
        # Different text should produce different key
        assert key1 != key3
        # Key should be a hex hash
        assert len(key1) == 64  # SHA256 hex length

    def test_serialize_deserialize_embedding(self, cache):
        """Test embedding serialization and deserialization."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        serialized = cache._serialize_embedding(embedding)
        deserialized = cache._deserialize_embedding(serialized)

        assert deserialized == embedding

    @pytest.mark.asyncio
    async def test_embed_miss_calls_provider(self, cache, provider):
        """Test that cache miss calls the underlying provider."""
        texts = ["hello", "world"]
        result = await cache.embed(texts)

        assert len(result) == 2
        assert provider.embed_calls == [texts]
        assert cache._stats["misses"] == 2
        assert cache._stats["hits"] == 0

    @pytest.mark.asyncio
    async def test_embed_hit_returns_cached(self, cache, provider):
        """Test that cache hit returns cached value without calling provider."""
        texts = ["hello", "world"]

        # First call - miss
        result1 = await cache.embed(texts)
        assert provider.embed_calls == [texts]

        # Second call - hit
        result2 = await cache.embed(texts)

        # Provider should not be called again
        assert provider.embed_calls == [texts]
        # Results should be the same
        assert result1 == result2
        # Stats should reflect hits
        assert cache._stats["hits"] == 2
        assert cache._stats["misses"] == 2

    @pytest.mark.asyncio
    async def test_embed_partial_hit(self, cache, provider):
        """Test cache with partial hit (some texts cached, some not)."""
        # Cache "hello"
        await cache.embed(["hello"])
        assert provider.embed_calls == [["hello"]]

        # Now request "hello" and "world" - should only call provider for "world"
        await cache.embed(["hello", "world"])

        assert provider.embed_calls == [["hello"], ["world"]]
        assert cache._stats["hits"] == 1  # "hello" was cached
        assert cache._stats["misses"] == 2  # "hello" first time + "world"

    @pytest.mark.asyncio
    async def test_embed_empty_list(self, cache, provider):
        """Test embedding an empty list."""
        result = await cache.embed([])

        assert result == []
        assert provider.embed_calls == []

    def test_get_dimension(self, cache):
        """Test get_dimension delegates to provider."""
        assert cache.get_dimension() == 384

    def test_name_property(self, cache):
        """Test name property includes cache indicator."""
        assert cache.name == "cached:mock:test-model"

    def test_stats_property(self, cache):
        """Test stats property returns a copy."""
        stats = cache.stats

        assert stats == {"hits": 0, "misses": 0, "errors": 0}
        # Should be a copy
        stats["hits"] = 100
        assert cache.stats["hits"] == 0

    @pytest.mark.asyncio
    async def test_get_entry_count(self, cache):
        """Test get_entry_count returns correct count."""
        assert cache.get_entry_count() == 0

        await cache.embed(["text1", "text2", "text3"])

        assert cache.get_entry_count() == 3

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Test clearing the cache."""
        await cache.embed(["text1", "text2"])
        assert cache.get_entry_count() == 2

        cleared = cache.clear()

        assert cleared == 2
        assert cache.get_entry_count() == 0

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache_dir, provider):
        """Test that expired entries are not returned."""
        # Create cache with 1 second TTL
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=1,
            batch_write_threshold=1,
        )
        cache = EmbeddingCache(provider, config)

        # Cache an embedding
        await cache.embed(["hello"])
        assert provider.embed_calls == [["hello"]]

        # Wait for expiration
        time.sleep(1.5)

        # Should call provider again due to expiration
        await cache.embed(["hello"])
        assert provider.embed_calls == [["hello"], ["hello"]]

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache_dir, provider):
        """Test cleanup of expired entries."""
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=1,
            batch_write_threshold=1,
        )
        cache = EmbeddingCache(provider, config)

        await cache.embed(["text1", "text2"])
        assert cache.get_entry_count() == 2

        time.sleep(1.5)

        cleaned = cache.cleanup_expired()

        assert cleaned == 2
        assert cache.get_entry_count() == 0

    @pytest.mark.asyncio
    async def test_cleanup_if_needed(self, cache_dir, provider):
        """Test cleanup when max_entries is exceeded."""
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=3600,
            max_entries=5,
            batch_write_threshold=1,
        )
        cache = EmbeddingCache(provider, config)

        # Add more than max_entries
        for i in range(10):
            await cache.embed([f"text{i}"])

        cleaned = cache.cleanup_if_needed()

        # Should have cleaned some entries
        assert cleaned > 0
        # Should be at or below 90% of max_entries
        assert cache.get_entry_count() <= 5

    @pytest.mark.asyncio
    async def test_invalidate_by_model(self, cache):
        """Test invalidating entries by model name."""
        await cache.embed(["text1", "text2"])
        assert cache.get_entry_count() == 2

        # Invalidate for the mock model
        invalidated = cache.invalidate_by_model("mock:test-model")

        assert invalidated == 2
        assert cache.get_entry_count() == 0

    @pytest.mark.asyncio
    async def test_invalidate_by_model_different_model(self, cache):
        """Test invalidating entries for different model doesn't affect ours."""
        await cache.embed(["text1", "text2"])
        assert cache.get_entry_count() == 2

        # Invalidate for different model
        invalidated = cache.invalidate_by_model("other:model")

        assert invalidated == 0
        assert cache.get_entry_count() == 2

    def test_close(self, cache):
        """Test closing the cache."""
        # Access connection to create it
        _ = cache._get_connection()
        assert cache._local.conn is not None

        cache.close()

        assert cache._local.conn is None

    @pytest.mark.asyncio
    async def test_batch_write_threshold(self, cache_dir, provider):
        """Test batch write threshold batching.

        Note: embed() always flushes pending writes at the end to ensure
        consistency, so this test verifies that batching works correctly
        by checking that all entries are persisted.
        """
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=3600,
            batch_write_threshold=5,
        )
        cache = EmbeddingCache(provider, config)

        # Add entries in separate calls
        await cache.embed(["a", "b", "c"])
        await cache.embed(["d", "e"])

        # All should be persisted
        assert cache.get_entry_count() == 5

        # Verify each entry can be retrieved (cache hits)
        provider.embed_calls.clear()
        await cache.embed(["a", "b", "c", "d", "e"])
        # Should not call provider - all cached
        assert provider.embed_calls == []
        assert cache._stats["hits"] == 5


class TestCachedEmbeddingProvider:
    """Tests for CachedEmbeddingProvider wrapper."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def provider(self):
        """Create a mock embedding provider."""
        return MockEmbeddingProvider()

    @pytest.fixture
    def cached_provider(self, cache_dir, provider):
        """Create a CachedEmbeddingProvider instance."""
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            batch_write_threshold=1,
        )
        return CachedEmbeddingProvider(provider, config)

    @pytest.mark.asyncio
    async def test_embed(self, cached_provider, provider):
        """Test embed method delegates correctly."""
        result = await cached_provider.embed(["hello", "world"])

        assert len(result) == 2
        assert provider.embed_calls == [["hello", "world"]]

    def test_get_dimension(self, cached_provider):
        """Test get_dimension delegates to underlying provider."""
        assert cached_provider.get_dimension() == 384

    def test_name_property(self, cached_provider):
        """Test name property includes cache indicator."""
        assert cached_provider.name == "cached:mock:test-model"

    def test_stats_property(self, cached_provider):
        """Test stats property."""
        stats = cached_provider.stats
        assert stats == {"hits": 0, "misses": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_get_entry_count(self, cached_provider):
        """Test get_entry_count."""
        await cached_provider.embed(["text1", "text2"])
        assert cached_provider.get_entry_count() == 2

    @pytest.mark.asyncio
    async def test_clear_cache(self, cached_provider):
        """Test clear_cache method."""
        await cached_provider.embed(["text1", "text2"])
        cleared = cached_provider.clear_cache()

        assert cleared == 2
        assert cached_provider.get_entry_count() == 0

    def test_close(self, cached_provider):
        """Test close method."""
        cached_provider.close()
        # Should not raise


class TestEmbeddingCacheIntegration:
    """Integration tests for embedding cache with real providers."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_cache_persistence_across_instances(self, cache_dir):
        """Test that cache persists across EmbeddingCache instances."""
        provider = MockEmbeddingProvider()
        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            batch_write_threshold=1,
        )

        # First instance - cache some embeddings
        cache1 = EmbeddingCache(provider, config)
        result1 = await cache1.embed(["hello"])
        cache1.close()

        # Second instance - should get cached result
        provider2 = MockEmbeddingProvider()
        cache2 = EmbeddingCache(provider2, config)
        result2 = await cache2.embed(["hello"])

        # Provider should not be called
        assert provider2.embed_calls == []
        # Results should match
        assert result1 == result2
        cache2.close()

    @pytest.mark.asyncio
    async def test_different_models_separate_caches(self, cache_dir):
        """Test that different models have separate cache entries."""
        provider1 = MockEmbeddingProvider()
        provider1._name = "model:v1"

        provider2 = MockEmbeddingProvider()
        provider2._name = "model:v2"

        config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            batch_write_threshold=1,
        )

        # Cache with model v1
        cache1 = EmbeddingCache(provider1, config)
        await cache1.embed(["hello"])
        assert provider1.embed_calls == [["hello"]]
        cache1.close()

        # Cache with model v2 - should call provider (different model)
        cache2 = EmbeddingCache(provider2, config)
        await cache2.embed(["hello"])
        assert provider2.embed_calls == [["hello"]]
        cache2.close()


class TestGetEmbeddingProviderWithCache:
    """Tests for get_embedding_provider with caching."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_get_embedding_provider_with_cache_enabled(self, cache_dir):
        """Test that get_embedding_provider returns cached provider when enabled."""
        from local_deepwiki.config import Config, config_context
        from local_deepwiki.providers.embeddings import get_embedding_provider

        config = Config()
        with config_context(config):
            provider = get_embedding_provider(enable_cache=True, cache_dir=cache_dir)

        assert "cached:" in provider.name

    def test_get_embedding_provider_with_cache_disabled(self):
        """Test that get_embedding_provider returns raw provider when disabled."""
        from local_deepwiki.config import Config, config_context
        from local_deepwiki.providers.embeddings import get_embedding_provider

        config = Config()
        with config_context(config):
            provider = get_embedding_provider(enable_cache=False)

        assert "cached:" not in provider.name
