"""Tests for search caching functionality.

Covers: TestSearchCache, TestSearchCacheDisabled, TestSearchCacheEviction,
TestSearchCacheTTL, TestSearchCacheSemanticSimilarity, TestSearchCacheIntegration,
TestSearchCacheClass.
"""

import math
import time

import pytest

from local_deepwiki.config import SearchCacheConfig
from local_deepwiki.models import ChunkType, CodeChunk, Language
from local_deepwiki.providers.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384, name: str = "mock"):
        self._dimension = dimension
        self._name = name
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings."""
        self.embed_calls.append(texts)
        return [[0.1] * self._dimension for _ in texts]


class SemanticMockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider that generates different embeddings based on query content.

    This allows testing semantic similarity by returning similar embeddings for
    similar queries and different embeddings for different queries.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return "semantic_mock"

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings based on text content.

        Uses a hash-based approach to generate deterministic but
        VERY different embeddings for different texts. The embeddings are
        designed so that different texts have low cosine similarity (<0.9)
        to ensure cache misses for different queries.
        """
        self.embed_calls.append(texts)
        embeddings = []
        for text in texts:
            # Create a deterministic but highly content-dependent embedding
            # Use hash to seed a pseudo-random pattern that varies significantly
            embedding = []
            text_hash = hash(text) & 0xFFFFFFFF  # Ensure positive
            for i in range(self._dimension):
                # Use different seeds and transforms to maximize variation
                seed = (text_hash * (i + 1) * 31337) & 0xFFFFFFFF
                # Use sine/cosine transforms for more varied values
                val = 0.5 + 0.5 * math.sin(seed * 0.0001 + i * 0.1)
                embedding.append(val)
            embeddings.append(embedding)
        return embeddings


def make_chunk(
    id: str,
    file_path: str = "test.py",
    content: str = "test code",
    language: Language = Language.PYTHON,
    chunk_type: ChunkType = ChunkType.FUNCTION,
) -> CodeChunk:
    """Create a test code chunk."""
    return CodeChunk(
        id=id,
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=f"test_{id}",
        content=content,
        start_line=1,
        end_line=10,
    )


class TestSearchCache:
    """Tests for search result caching functionality."""

    @pytest.fixture
    def cache_config(self):
        """Create a search cache config for testing."""
        return SearchCacheConfig(
            enabled=True,
            ttl_seconds=3600,
            max_entries=100,
            similarity_threshold=0.95,
        )

    @pytest.fixture
    def fuzzy_config(self):
        """Create a fuzzy search config with auto-fuzzy disabled for caching tests."""
        from local_deepwiki.config import FuzzySearchConfig

        return FuzzySearchConfig(
            enable_auto_fuzzy=False,  # Disable so caching works with SemanticMockEmbeddingProvider
        )

    @pytest.fixture
    def vector_store(self, tmp_path, cache_config, fuzzy_config):
        """Create a vector store with caching enabled."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        # Use semantic mock to get different embeddings for different queries
        provider = SemanticMockEmbeddingProvider()
        return VectorStore(
            db_path,
            provider,
            search_cache_config=cache_config,
            fuzzy_search_config=fuzzy_config,
        )

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data.

        Note: create_or_update_table invalidates the cache once.
        """
        chunks = [
            make_chunk("func_1", content="def calculate_sum(a, b): return a + b"),
            make_chunk("func_2", content="def calculate_product(a, b): return a * b"),
            make_chunk(
                "func_3", content="def parse_json(data): return json.loads(data)"
            ),
        ]
        await vector_store.create_or_update_table(chunks)
        # Note: invalidations count is now 1 after fixture setup
        return vector_store

    async def test_search_cache_hit(self, populated_store):
        """Test that repeated identical searches return cached results."""
        # First search - cache miss
        results1 = await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["misses"] == 1
        assert stats1["hits"] == 0

        # Second search - cache hit
        results2 = await populated_store.search("calculate")
        stats2 = populated_store.search_cache_stats
        assert stats2["misses"] == 1
        assert stats2["hits"] == 1

        # Results should be the same
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.chunk.id == r2.chunk.id

    async def test_search_cache_miss_different_query(self, populated_store):
        """Test that different queries with different embeddings result in cache misses."""
        # First search - starts with 'c'
        await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["misses"] == 1

        # Different search starting with different letter - cache miss
        # SemanticMockEmbeddingProvider generates different embeddings based on first char
        await populated_store.search("parse json")
        stats2 = populated_store.search_cache_stats
        assert stats2["misses"] == 2

    async def test_search_cache_miss_different_filters(self, populated_store):
        """Test that same query with different filters results in cache miss."""
        # Search without filters
        await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["misses"] == 1

        # Same query with language filter - cache miss
        await populated_store.search("calculate", language="python")
        stats2 = populated_store.search_cache_stats
        assert stats2["misses"] == 2

    async def test_search_cache_invalidated_on_create_or_update(self, populated_store):
        """Test that cache is invalidated when table is created/updated."""
        # Note: populated_store fixture already triggered one invalidation

        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Create/update table - should invalidate cache
        new_chunks = [make_chunk("new_1", content="def new_function(): pass")]
        await populated_store.create_or_update_table(new_chunks)

        stats2 = populated_store.search_cache_stats
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_search_cache_invalidated_on_add_chunks(self, populated_store):
        """Test that cache is invalidated when chunks are added."""
        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Add chunks - should invalidate cache
        new_chunks = [make_chunk("added_1", content="def added_function(): pass")]
        await populated_store.add_chunks(new_chunks)

        stats2 = populated_store.search_cache_stats
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_search_cache_invalidated_on_delete_chunks_by_file(
        self, populated_store
    ):
        """Test that cache is invalidated when chunks are deleted by file."""
        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Delete chunks - should invalidate cache
        await populated_store.delete_chunks_by_file("test.py")

        stats2 = populated_store.search_cache_stats
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_search_cache_invalidated_on_delete_chunks_by_files(
        self, populated_store
    ):
        """Test that cache is invalidated when chunks are deleted by files."""
        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.search_cache_stats
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Delete chunks - should invalidate cache
        await populated_store.delete_chunks_by_files(["test.py"])

        stats2 = populated_store.search_cache_stats
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_invalidate_search_cache_method(self, populated_store):
        """Test the public invalidate_search_cache method."""
        # Populate cache with different queries (different first chars = different embeddings)
        await populated_store.search("alpha query")
        await populated_store.search("beta query")
        stats1 = populated_store.search_cache_stats
        assert stats1["entries"] == 2

        # Invalidate
        count = populated_store.invalidate_search_cache()
        assert count == 2

        stats2 = populated_store.search_cache_stats
        assert stats2["entries"] == 0

    async def test_search_cache_stats(self, populated_store):
        """Test get_search_cache_stats returns correct structure."""
        stats = populated_store.search_cache_stats

        assert "enabled" in stats
        assert "entries" in stats
        assert "max_entries" in stats
        assert "ttl_seconds" in stats
        assert "similarity_threshold" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "invalidations" in stats
        assert "hit_rate" in stats

        assert stats["enabled"] is True
        assert stats["max_entries"] == 100
        assert stats["ttl_seconds"] == 3600
        assert stats["similarity_threshold"] == 0.95

    async def test_search_cache_not_used_for_fuzzy(self, populated_store):
        """Test that fuzzy searches don't use the cache."""
        # Fuzzy search
        await populated_store.search("calculate", use_fuzzy=True)
        stats = populated_store.search_cache_stats
        # Should not cache fuzzy results
        assert stats["entries"] == 0

    async def test_search_cache_not_used_for_path_pattern(self, populated_store):
        """Test that path pattern searches don't use the cache."""
        # Path pattern search
        await populated_store.search("calculate", path_pattern="src/**/*.py")
        stats = populated_store.search_cache_stats
        # Should not cache path pattern results
        assert stats["entries"] == 0


class TestSearchCacheDisabled:
    """Tests for search caching when disabled."""

    @pytest.fixture
    def disabled_config(self):
        """Create a disabled search cache config."""
        return SearchCacheConfig(enabled=False)

    @pytest.fixture
    def vector_store(self, tmp_path, disabled_config):
        """Create a vector store with caching disabled."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider, search_cache_config=disabled_config)

    async def test_cache_disabled_no_caching(self, vector_store):
        """Test that caching is skipped when disabled."""
        chunks = [make_chunk("func_1", content="def calculate(): pass")]
        await vector_store.create_or_update_table(chunks)

        # Search twice
        await vector_store.search("calculate")
        await vector_store.search("calculate")

        stats = vector_store.search_cache_stats
        assert stats["enabled"] is False
        assert stats["entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestSearchCacheEviction:
    """Tests for search cache eviction."""

    @pytest.fixture
    def vector_store_with_small_cache(self, tmp_path):
        """Create a vector store with small cache for testing eviction.

        We directly create a SearchCache with small max_entries to bypass
        the config validation that requires max_entries >= 100.
        """
        from local_deepwiki.core.vectorstore import SearchCache, VectorStore

        db_path = tmp_path / "test.lance"
        provider = SemanticMockEmbeddingProvider()

        # Create VectorStore with default config first
        store = VectorStore(db_path, provider)

        # Replace the cache with a small one for testing (bypassing validation)
        # Create a config-like object that allows small max_entries
        class SmallCacheConfig:
            enabled = True
            ttl_seconds = 3600
            max_entries = 3  # Small for testing
            similarity_threshold = 0.95

        store._search_cache = SearchCache(SmallCacheConfig())
        return store

    async def test_cache_eviction_when_over_capacity(
        self, vector_store_with_small_cache
    ):
        """Test that old entries are evicted when cache exceeds max_entries."""
        vector_store = vector_store_with_small_cache

        chunks = [
            make_chunk("func_1", content="def alpha(): pass"),
            make_chunk("func_2", content="def beta(): pass"),
            make_chunk("func_3", content="def gamma(): pass"),
            make_chunk("func_4", content="def delta(): pass"),
            make_chunk("func_5", content="def epsilon(): pass"),
        ]
        await vector_store.create_or_update_table(chunks)

        # Fill cache beyond capacity (max is 3)
        await vector_store.search("alpha")
        await vector_store.search("beta")
        await vector_store.search("gamma")
        await vector_store.search("delta")  # This should trigger eviction

        stats = vector_store.search_cache_stats
        # Should have evicted some entries (max is 3, target is 80% = 2.4 -> 2)
        assert stats["entries"] <= 3


class TestSearchCacheTTL:
    """Tests for search cache TTL expiration."""

    @pytest.fixture
    def vector_store_with_short_ttl(self, tmp_path):
        """Create a vector store with short TTL cache.

        We directly create a SearchCache with short TTL to bypass
        the config validation that requires ttl_seconds >= 60.
        """
        from local_deepwiki.core.vectorstore import SearchCache, VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()

        # Create VectorStore with default config first
        store = VectorStore(db_path, provider)

        # Replace the cache with a short TTL one for testing
        class ShortTTLConfig:
            enabled = True
            ttl_seconds = 1  # 1 second TTL for testing
            max_entries = 1000
            similarity_threshold = 0.95

        store._search_cache = SearchCache(ShortTTLConfig())
        return store

    @pytest.mark.slow
    async def test_cache_entry_expires_after_ttl(self, vector_store_with_short_ttl):
        """Test that cache entries expire after TTL."""
        vector_store = vector_store_with_short_ttl

        chunks = [make_chunk("func_1", content="def calculate(): pass")]
        await vector_store.create_or_update_table(chunks)

        # First search - cache miss
        await vector_store.search("calculate")
        stats1 = vector_store.search_cache_stats
        assert stats1["entries"] == 1

        # Wait for TTL to expire (generous buffer for CI)
        time.sleep(2.5)

        # Second search - entry expired, should be cache miss
        await vector_store.search("calculate")
        stats2 = vector_store.search_cache_stats
        # The expired entry should have been cleaned up
        assert stats2["misses"] == 2


class TestSearchCacheSemanticSimilarity:
    """Tests for semantic similarity matching in search cache."""

    @pytest.fixture
    def cache_config(self):
        """Create a cache config with lower similarity threshold for testing."""
        return SearchCacheConfig(
            enabled=True,
            ttl_seconds=3600,
            max_entries=100,
            similarity_threshold=0.9,  # Lower threshold for testing
        )

    @pytest.fixture
    def vector_store(self, tmp_path, cache_config):
        """Create a vector store with semantic caching."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()  # Identical embeddings = similarity 1.0
        return VectorStore(db_path, provider, search_cache_config=cache_config)

    async def test_semantic_cache_hit_identical_embeddings(self, vector_store):
        """Test that queries with identical embeddings result in cache hits."""
        chunks = [make_chunk("func_1", content="def calculate(): pass")]
        await vector_store.create_or_update_table(chunks)

        # First search
        await vector_store.search("query1")
        stats1 = vector_store.search_cache_stats
        assert stats1["misses"] == 1
        assert stats1["hits"] == 0

        # Second search with different text but identical embedding (from mock)
        await vector_store.search("query2")
        stats2 = vector_store.search_cache_stats
        # Mock provider returns identical embeddings, so should be a cache hit
        assert stats2["hits"] == 1


class TestSearchCacheIntegration:
    """Integration tests for search cache with VectorStore."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store with default cache config."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        # Uses default SearchCacheConfig
        return VectorStore(db_path, provider)

    async def test_default_cache_config(self, vector_store):
        """Test that default cache config is applied."""
        stats = vector_store.search_cache_stats
        assert stats["enabled"] is True
        assert stats["ttl_seconds"] == 3600  # Default 1 hour
        assert stats["max_entries"] == 1000  # Default
        assert stats["similarity_threshold"] == 0.95  # Default

    async def test_cache_survives_empty_search(self, vector_store):
        """Test that caching works even with empty results."""
        # Search empty store
        results = await vector_store.search("calculate")
        assert results == []

        stats = vector_store.search_cache_stats
        # Empty results should not be cached (no table exists)
        assert stats["entries"] == 0

    async def test_cache_with_limit_filter(self, vector_store):
        """Test that different limits result in different cache entries."""
        chunks = [
            make_chunk("func_1", content="def calculate1(): pass"),
            make_chunk("func_2", content="def calculate2(): pass"),
            make_chunk("func_3", content="def calculate3(): pass"),
        ]
        await vector_store.create_or_update_table(chunks)

        # Search with default limit
        await vector_store.search("calculate")
        stats1 = vector_store.search_cache_stats
        assert stats1["entries"] == 1

        # Search with different limit - should be cache miss
        await vector_store.search("calculate", limit=5)
        stats2 = vector_store.search_cache_stats
        assert stats2["entries"] == 2
        assert stats2["misses"] == 2


class TestSearchCacheClass:
    """Direct tests for the SearchCache class."""

    def test_compute_similarity_identical_vectors(self):
        """Test similarity computation for identical vectors."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec = [0.1, 0.2, 0.3, 0.4, 0.5]
        similarity = cache._compute_similarity(vec, vec)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_orthogonal_vectors(self):
        """Test similarity computation for orthogonal vectors."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = cache._compute_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)

    def test_compute_similarity_opposite_vectors(self):
        """Test similarity computation for opposite vectors."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec1 = [1.0, 1.0, 1.0]
        vec2 = [-1.0, -1.0, -1.0]
        similarity = cache._compute_similarity(vec1, vec2)
        assert similarity == pytest.approx(-1.0)

    def test_compute_similarity_zero_vector(self):
        """Test similarity computation with zero vector."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]
        similarity = cache._compute_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_filters_match_identical(self):
        """Test filters matching with identical filters."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        filters1 = {"language": "python", "limit": 10}
        filters2 = {"language": "python", "limit": 10}
        assert cache._filters_match(filters1, filters2) is True

    def test_filters_match_different(self):
        """Test filters matching with different filters."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        filters1 = {"language": "python", "limit": 10}
        filters2 = {"language": "typescript", "limit": 10}
        assert cache._filters_match(filters1, filters2) is False

    def test_filters_match_empty(self):
        """Test filters matching with empty filters."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        assert cache._filters_match({}, {}) is True
        assert cache._filters_match({"a": 1}, {}) is False

    def test_stats_returns_copy(self):
        """Test that stats returns a copy, not the internal dict."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        stats1 = cache.stats
        stats1["hits"] = 999

        stats2 = cache.stats
        assert stats2["hits"] == 0  # Internal stats not modified
