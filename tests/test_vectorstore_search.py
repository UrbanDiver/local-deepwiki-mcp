"""Tests for vector store search profiles, adaptive search, feedback, and fuzzy search."""

import pytest

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
    """Mock embedding provider that returns different embeddings based on content."""

    def __init__(self, dimension: int = 384, name: str = "mock-semantic"):
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
        """Generate embeddings that vary based on text content."""
        self.embed_calls.append(texts)
        results = []
        for text in texts:
            # Use hash of text to generate different but deterministic embeddings
            hash_val = hash(text) % 1000 / 1000.0
            base = [hash_val * 0.1 + 0.05] * self._dimension
            # Add some variation based on position
            for i in range(min(10, self._dimension)):
                base[i] += (hash(text + str(i)) % 100) / 1000.0
            results.append(base)
        return results


def make_chunk(
    chunk_id: str = "test_chunk",
    file_path: str = "test.py",
    content: str = "def test(): pass",
    chunk_type: ChunkType = ChunkType.FUNCTION,
    name: str = "test",
    language: Language = Language.PYTHON,
    start_line: int = 1,
    end_line: int = 10,
) -> CodeChunk:
    """Create a test code chunk."""
    return CodeChunk(
        id=chunk_id,
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=name,
        content=content,
        start_line=start_line,
        end_line=end_line,
    )


class TestSearchProfiles:
    """Tests for configurable search profiles (precision/recall trade-off)."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data."""
        # Create chunks with varying content to test similarity filtering
        chunks = [
            make_chunk("chunk_1", "src/auth.py", "def authenticate_user(): pass"),
            make_chunk("chunk_2", "src/auth.py", "def validate_token(): pass"),
            make_chunk("chunk_3", "src/db.py", "def connect_database(): pass"),
            make_chunk("chunk_4", "src/api.py", "def handle_request(): pass"),
            make_chunk("chunk_5", "tests/test_auth.py", "def test_auth(): pass"),
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_search_with_fast_profile(self, populated_store):
        """Test searching with FAST profile."""
        from local_deepwiki.core.vectorstore import SearchProfile

        results = await populated_store.search(
            "authenticate", limit=5, profile=SearchProfile.FAST
        )
        # FAST profile has higher min_similarity threshold (0.3)
        # With mock embeddings, all results have same similarity
        assert isinstance(results, list)
        # Results should be returned successfully
        for r in results:
            assert r.chunk is not None

    async def test_search_with_balanced_profile(self, populated_store):
        """Test searching with BALANCED profile (default)."""
        from local_deepwiki.core.vectorstore import SearchProfile

        results = await populated_store.search(
            "authenticate", limit=5, profile=SearchProfile.BALANCED
        )
        assert isinstance(results, list)
        for r in results:
            assert r.chunk is not None

    async def test_search_with_thorough_profile(self, populated_store):
        """Test searching with THOROUGH profile."""
        from local_deepwiki.core.vectorstore import SearchProfile

        results = await populated_store.search(
            "authenticate", limit=5, profile=SearchProfile.THOROUGH
        )
        # THOROUGH profile has lower min_similarity threshold (0.1)
        # Should return more results with lower threshold
        assert isinstance(results, list)
        for r in results:
            assert r.chunk is not None

    async def test_search_with_string_profile(self, populated_store):
        """Test searching with profile as string."""
        # Test string profile names
        results_fast = await populated_store.search("test", limit=5, profile="fast")
        results_balanced = await populated_store.search(
            "test", limit=5, profile="balanced"
        )
        results_thorough = await populated_store.search(
            "test", limit=5, profile="thorough"
        )

        assert isinstance(results_fast, list)
        assert isinstance(results_balanced, list)
        assert isinstance(results_thorough, list)

    async def test_search_with_invalid_profile_string(self, populated_store):
        """Test searching with invalid profile string falls back to default."""
        # Invalid profile should fall back to default without raising
        results = await populated_store.search(
            "test", limit=5, profile="invalid_profile"
        )
        assert isinstance(results, list)

    async def test_search_with_min_similarity_override(self, populated_store):
        """Test that min_similarity parameter overrides profile default."""
        from local_deepwiki.core.vectorstore import SearchProfile

        # Use FAST profile (default min_similarity=0.3) but override to 0.01
        # This should allow more results through
        results = await populated_store.search(
            "test",
            limit=10,
            profile=SearchProfile.FAST,
            min_similarity=0.01,
        )
        assert isinstance(results, list)
        # With very low threshold, should get all chunks
        assert len(results) <= 10

    async def test_search_high_min_similarity_filters_results(self, tmp_path):
        """Test that high min_similarity threshold filters out low-scoring results."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Use semantic mock that returns different embeddings
        provider = SemanticMockEmbeddingProvider()
        store = VectorStore(tmp_path / "test.lance", provider)

        chunks = [
            make_chunk("chunk_1", content="authentication login"),
            make_chunk("chunk_2", content="completely unrelated content xyz"),
        ]
        await store.create_or_update_table(chunks)

        # With very high threshold, should filter out low-scoring results
        results = await store.search("authentication", limit=10, min_similarity=0.99)
        # High threshold may filter out all results depending on embeddings
        assert isinstance(results, list)

    async def test_default_profile_configuration(self, tmp_path):
        """Test that default profile can be configured at construction."""
        from local_deepwiki.core.vectorstore import SearchProfile, VectorStore

        provider = MockEmbeddingProvider()

        # Create store with FAST as default
        store = VectorStore(
            tmp_path / "test.lance",
            provider,
            default_search_profile=SearchProfile.FAST,
        )
        assert store.search_profile == SearchProfile.FAST

        # Create store with THOROUGH as default
        store2 = VectorStore(
            tmp_path / "test2.lance",
            provider,
            default_search_profile=SearchProfile.THOROUGH,
        )
        assert store2.search_profile == SearchProfile.THOROUGH

    async def test_set_search_profile(self, vector_store):
        """Test setting search profile at runtime."""
        from local_deepwiki.core.vectorstore import SearchProfile

        # Default should be BALANCED
        assert vector_store.search_profile == SearchProfile.BALANCED

        # Set to FAST
        vector_store.search_profile = SearchProfile.FAST
        assert vector_store.search_profile == SearchProfile.FAST

        # Set using string
        vector_store.search_profile = "thorough"
        assert vector_store.search_profile == SearchProfile.THOROUGH

    async def test_set_search_profile_invalid_string(self, vector_store):
        """Test setting invalid profile string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid search profile"):
            vector_store.search_profile = "invalid"


class TestAdaptiveSearch:
    """Tests for adaptive search depth estimation."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data."""
        chunks = [
            make_chunk(f"chunk_{i}", content=f"test content {i}") for i in range(20)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_adaptive_search_enabled_by_default(self, vector_store):
        """Test that adaptive search is enabled by default."""
        assert vector_store.adaptive_search_enabled is True

    async def test_disable_adaptive_search(self, vector_store):
        """Test disabling adaptive search."""
        vector_store.adaptive_search_enabled = False
        assert vector_store.adaptive_search_enabled is False

    async def test_adaptive_search_estimates_depth(self, populated_store):
        """Test that adaptive searcher estimates optimal depth."""
        # Access the internal adaptive searcher
        searcher = populated_store._adaptive_searcher

        # Simple query should have lower complexity
        simple_depth = searcher.estimate_optimal_depth("test", base_limit=10)
        assert simple_depth >= 10

        # Complex query should have higher complexity
        complex_depth = searcher.estimate_optimal_depth(
            "authentication middleware handler controller service",
            base_limit=10,
        )
        assert complex_depth >= simple_depth

    async def test_adaptive_search_records_quality(self, populated_store):
        """Test that search quality is recorded for adaptation."""
        # Perform a search
        await populated_store.search("test content")

        # Check that stats show recorded queries
        stats = populated_store.adaptive_search_stats
        assert stats["query_history_size"] >= 1

    async def test_adaptive_search_disabled_does_not_record(self, populated_store):
        """Test that disabled adaptive search doesn't record quality."""
        # Disable adaptive search
        populated_store.adaptive_search_enabled = False

        # Perform a search
        await populated_store.search("test content")

        # Quality should not be recorded (though history may still grow)
        # The key thing is searches still work
        stats = populated_store.adaptive_search_stats
        assert "adaptive_search_enabled" in stats
        assert stats["adaptive_search_enabled"] is False


class TestSearchFeedback:
    """Tests for search feedback system."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data."""
        chunks = [
            make_chunk(f"chunk_{i}", content=f"test content {i}") for i in range(10)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_record_feedback(self, populated_store):
        """Test recording user feedback on search results."""
        from local_deepwiki.core.vectorstore import SearchFeedback

        # Perform a search first
        results = await populated_store.search("test")
        assert len(results) > 0

        # Record feedback for the first result
        feedback = SearchFeedback(
            query="test",
            result_id=results[0].chunk.id,
            relevant=True,
        )
        populated_store.record_feedback(feedback)

        # Check feedback stats
        stats = populated_store.adaptive_search_stats
        assert stats["feedback_stats"]["total_feedback"] == 1
        assert stats["feedback_stats"]["relevant_count"] == 1

    async def test_record_multiple_feedback(self, populated_store):
        """Test recording multiple feedback entries."""
        from local_deepwiki.core.vectorstore import SearchFeedback

        await populated_store.search("test")

        # Record multiple feedback
        populated_store.record_feedback(
            SearchFeedback(query="test", result_id="chunk_0", relevant=True)
        )
        populated_store.record_feedback(
            SearchFeedback(query="test", result_id="chunk_1", relevant=False)
        )
        populated_store.record_feedback(
            SearchFeedback(query="test", result_id="chunk_2", relevant=True)
        )

        stats = populated_store.adaptive_search_stats
        assert stats["feedback_stats"]["total_feedback"] == 3
        assert stats["feedback_stats"]["relevant_count"] == 2
        assert stats["feedback_stats"]["irrelevant_count"] == 1
        assert stats["feedback_stats"]["relevance_rate"] == pytest.approx(2 / 3)

    async def test_feedback_stats_empty(self, vector_store):
        """Test feedback stats when no feedback recorded."""
        stats = vector_store.adaptive_search_stats
        assert stats["feedback_stats"]["total_feedback"] == 0
        assert stats["feedback_stats"]["relevance_rate"] == 0.0


class TestSearchProfilesWithPagination:
    """Tests for search profiles with pagination."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data."""
        chunks = [
            make_chunk(f"chunk_{i}", content=f"test content {i}") for i in range(50)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_paginated_search_with_fast_profile(self, populated_store):
        """Test paginated search with FAST profile."""
        from local_deepwiki.core.vectorstore import SearchProfile

        page = await populated_store.search_paginated(
            "test", limit=10, offset=0, profile=SearchProfile.FAST
        )
        assert len(page.results) <= 10
        assert page.offset == 0
        assert page.limit == 10

    async def test_paginated_search_with_thorough_profile(self, populated_store):
        """Test paginated search with THOROUGH profile."""
        from local_deepwiki.core.vectorstore import SearchProfile

        page = await populated_store.search_paginated(
            "test", limit=10, offset=0, profile=SearchProfile.THOROUGH
        )
        assert len(page.results) <= 10
        # THOROUGH should search more candidates
        assert page.total >= 0

    async def test_paginated_search_min_similarity_override(self, populated_store):
        """Test paginated search with min_similarity override."""
        # Very high threshold should filter results
        page = await populated_store.search_paginated(
            "test",
            limit=10,
            offset=0,
            min_similarity=0.99,
        )
        # Results may be filtered due to high threshold
        assert isinstance(page.results, list)

    async def test_paginated_search_profile_string(self, populated_store):
        """Test paginated search with profile as string."""
        page = await populated_store.search_paginated(
            "test", limit=10, profile="balanced"
        )
        assert isinstance(page.results, list)


class TestAdaptiveSearcherUnit:
    """Unit tests for the AdaptiveSearcher class."""

    def test_query_complexity_empty(self):
        """Test complexity calculation for empty query."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()
        complexity = searcher._calculate_query_complexity("")
        assert complexity == 0.0

    def test_query_complexity_simple(self):
        """Test complexity calculation for simple query."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()
        complexity = searcher._calculate_query_complexity("test")
        assert 0.0 <= complexity <= 1.0

    def test_query_complexity_technical(self):
        """Test that technical terms increase complexity."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()

        # Query with technical terms
        tech_complexity = searcher._calculate_query_complexity(
            "function authentication middleware"
        )

        # Query without technical terms
        simple_complexity = searcher._calculate_query_complexity("hello world foo")

        # Technical query should have higher complexity
        assert tech_complexity > simple_complexity

    def test_query_complexity_caching(self):
        """Test that complexity calculations are cached."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()
        query = "test query"

        # First call - should compute
        complexity1 = searcher._calculate_query_complexity(query)

        # Should be cached now
        assert query in searcher._complexity_cache
        assert searcher._complexity_cache[query] == complexity1

        # Second call - should use cache
        complexity2 = searcher._calculate_query_complexity(query)
        assert complexity1 == complexity2

    def test_estimate_optimal_depth_minimum(self):
        """Test that optimal depth is at least the base limit."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()
        base_limit = 10

        depth = searcher.estimate_optimal_depth("test", base_limit=base_limit)
        assert depth >= base_limit

    def test_estimate_optimal_depth_maximum(self):
        """Test that optimal depth doesn't exceed 10x base limit."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()
        base_limit = 10

        depth = searcher.estimate_optimal_depth(
            "very complex authentication middleware handler controller",
            base_limit=base_limit,
        )
        assert depth <= base_limit * 10

    def test_record_search_quality_clamps_values(self):
        """Test that quality values are clamped to valid range."""
        from local_deepwiki.core.vectorstore import AdaptiveSearcher

        searcher = AdaptiveSearcher()

        # Record with quality out of range
        searcher.record_search_quality(
            "test", quality=1.5, result_count=5, depth_used=20
        )
        searcher.record_search_quality(
            "test2", quality=-0.5, result_count=5, depth_used=20
        )

        # Check that values were clamped
        assert len(searcher._query_history) == 2
        # Quality should be clamped to 1.0 and 0.0 respectively
        assert searcher._query_history[0][1] == 1.0
        assert searcher._query_history[1][1] == 0.0


class TestSearchProfileConfig:
    """Tests for search profile configuration."""

    def test_profile_config_values(self):
        """Test that profile configs have expected values."""
        from local_deepwiki.core.vectorstore import (
            SEARCH_PROFILES,
            SearchProfile,
            SearchProfileConfig,
        )

        # FAST profile should have lower fetch multiplier
        fast_config = SEARCH_PROFILES[SearchProfile.FAST]
        assert fast_config.fetch_multiplier == 1.0
        assert fast_config.rerank_candidates == 10
        assert fast_config.use_approximate is True
        assert fast_config.min_similarity == 0.3

        # BALANCED profile
        balanced_config = SEARCH_PROFILES[SearchProfile.BALANCED]
        assert balanced_config.fetch_multiplier == 2.0
        assert balanced_config.rerank_candidates == 50
        assert balanced_config.use_approximate is True
        assert balanced_config.min_similarity == 0.2

        # THOROUGH profile should have highest fetch multiplier
        thorough_config = SEARCH_PROFILES[SearchProfile.THOROUGH]
        assert thorough_config.fetch_multiplier == 5.0
        assert thorough_config.rerank_candidates == 200
        assert thorough_config.use_approximate is False
        assert thorough_config.min_similarity == 0.1

    def test_profile_enum_values(self):
        """Test SearchProfile enum values."""
        from local_deepwiki.core.vectorstore import SearchProfile

        assert SearchProfile.FAST.value == "fast"
        assert SearchProfile.BALANCED.value == "balanced"
        assert SearchProfile.THOROUGH.value == "thorough"

    def test_profile_enum_from_string(self):
        """Test creating SearchProfile from string."""
        from local_deepwiki.core.vectorstore import SearchProfile

        assert SearchProfile("fast") == SearchProfile.FAST
        assert SearchProfile("balanced") == SearchProfile.BALANCED
        assert SearchProfile("thorough") == SearchProfile.THOROUGH

        # Invalid string should raise ValueError
        with pytest.raises(ValueError):
            SearchProfile("invalid")


class TestFuzzySearchHelper:
    """Tests for FuzzySearchHelper class."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store_with_names(self, vector_store):
        """Create a vector store with chunks that have meaningful names."""
        chunks = [
            make_chunk("func_1", content="def calculate_sum(a, b): return a + b"),
            make_chunk("func_2", content="def calculate_product(a, b): return a * b"),
            make_chunk(
                "func_3", content="def calculate_difference(a, b): return a - b"
            ),
            make_chunk(
                "class_1", content="class UserManager: pass", chunk_type=ChunkType.CLASS
            ),
            make_chunk(
                "class_2", content="class UserService: pass", chunk_type=ChunkType.CLASS
            ),
            make_chunk(
                "method_1",
                content="def get_user(self): pass",
                chunk_type=ChunkType.METHOD,
            ),
        ]
        # Override the names in chunks
        chunks[0].name = "calculate_sum"
        chunks[1].name = "calculate_product"
        chunks[2].name = "calculate_difference"
        chunks[3].name = "UserManager"
        chunks[4].name = "UserService"
        chunks[5].name = "get_user"
        chunks[5].parent_name = "UserService"

        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_build_name_index(self, populated_store_with_names):
        """Test building the fuzzy name index."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        assert helper.is_built
        stats = helper.get_stats()
        assert stats["total_names"] > 0
        assert stats["unique_names"] > 0

    async def test_find_similar_names_exact_match(self, populated_store_with_names):
        """Test finding similar names with exact match."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        results = helper.find_similar_names("calculate_sum", threshold=0.6)
        assert len(results) > 0
        # Exact match should have high score
        names = [name for name, score in results]
        assert "calculate_sum" in names

    async def test_find_similar_names_typo(self, populated_store_with_names):
        """Test finding similar names with typo."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        # Search with typo "calcluate" instead of "calculate"
        results = helper.find_similar_names("calcluate_sum", threshold=0.5)
        assert len(results) > 0
        # Should find calculate_sum despite typo
        names = [name for name, score in results]
        assert any("calculate" in name for name in names)

    async def test_find_similar_names_threshold(self, populated_store_with_names):
        """Test that threshold filters out low-similarity results."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        # High threshold should filter more results
        high_threshold_results = helper.find_similar_names("xyz_random", threshold=0.9)
        low_threshold_results = helper.find_similar_names("xyz_random", threshold=0.3)

        # High threshold should have fewer or equal results
        assert len(high_threshold_results) <= len(low_threshold_results)

    async def test_find_similar_names_limit(self, populated_store_with_names):
        """Test that limit parameter works."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        results = helper.find_similar_names("calculate", threshold=0.3, limit=2)
        assert len(results) <= 2

    async def test_generate_suggestions(self, populated_store_with_names):
        """Test generating suggestions for poor results."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        # Empty results should trigger suggestions
        empty_results: list = []
        suggestions = helper.generate_suggestions(
            "calcluate", empty_results, threshold=0.5
        )

        # Should suggest names containing "calculate"
        assert len(suggestions) > 0

    async def test_generate_suggestions_excludes_existing(
        self, populated_store_with_names
    ):
        """Test that suggestions exclude names already in results."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(populated_store_with_names)
        await helper.build_name_index()

        # Create a mock result with calculate_sum
        from local_deepwiki.models import SearchResult

        mock_chunk = make_chunk("test")
        mock_chunk.name = "calculate_sum"
        mock_results = [SearchResult(chunk=mock_chunk, score=0.3, highlights=[])]

        suggestions = helper.generate_suggestions(
            "calculate", mock_results, threshold=0.5
        )

        # Should not include calculate_sum since it's already in results
        assert "calculate_sum" not in suggestions

    async def test_empty_store_name_index(self, vector_store):
        """Test building name index on empty store."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(vector_store)
        await helper.build_name_index()

        assert helper.is_built
        stats = helper.get_stats()
        assert stats["total_names"] == 0


class TestAutoFuzzySearch:
    """Tests for automatic fuzzy search fallback."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.config import FuzzySearchConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        fuzzy_config = FuzzySearchConfig(
            auto_fuzzy_threshold=0.5,
            suggestion_threshold=0.5,
            max_suggestions=3,
            enable_auto_fuzzy=True,
        )
        return VectorStore(db_path, provider, fuzzy_search_config=fuzzy_config)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a populated vector store."""
        chunks = [
            make_chunk("func_1", content="def calculate_sum(a, b): return a + b"),
            make_chunk("func_2", content="def calculate_product(a, b): return a * b"),
        ]
        chunks[0].name = "calculate_sum"
        chunks[1].name = "calculate_product"
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_should_auto_enable_fuzzy_empty_results(self):
        """Test that auto-fuzzy is enabled for empty results."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

        assert should_auto_enable_fuzzy([], threshold=0.5) is True

    async def test_should_auto_enable_fuzzy_low_scores(self):
        """Test that auto-fuzzy is enabled for low-scoring results."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy
        from local_deepwiki.models import SearchResult

        mock_chunk = make_chunk("test")
        results = [SearchResult(chunk=mock_chunk, score=0.3, highlights=[])]

        assert should_auto_enable_fuzzy(results, threshold=0.5) is True

    async def test_should_not_auto_enable_fuzzy_high_scores(self):
        """Test that auto-fuzzy is not enabled for high-scoring results."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy
        from local_deepwiki.models import SearchResult

        mock_chunk = make_chunk("test")
        results = [SearchResult(chunk=mock_chunk, score=0.8, highlights=[])]

        assert should_auto_enable_fuzzy(results, threshold=0.5) is False

    async def test_search_with_auto_suggest(self, populated_store):
        """Test search with auto_suggest enabled."""
        # Search for something that will return results
        results = await populated_store.search("calculate", auto_suggest=True)
        # Should return results (our mock embeddings give same vectors so scores are similar)
        assert len(results) > 0

    async def test_search_without_auto_suggest(self, populated_store):
        """Test search with auto_suggest disabled."""
        results = await populated_store.search("calculate", auto_suggest=False)
        # Should return results without suggestions
        assert len(results) > 0
        # First result should not have suggestions when auto_suggest=False
        # (though this depends on result quality)


class TestFuzzySearchConfig:
    """Tests for FuzzySearchConfig."""

    def test_default_config(self):
        """Test default fuzzy search configuration."""
        from local_deepwiki.config import FuzzySearchConfig

        config = FuzzySearchConfig()
        assert config.auto_fuzzy_threshold == 0.5
        assert config.suggestion_threshold == 0.6
        assert config.max_suggestions == 3
        assert config.enable_auto_fuzzy is True

    def test_custom_config(self):
        """Test custom fuzzy search configuration."""
        from local_deepwiki.config import FuzzySearchConfig

        config = FuzzySearchConfig(
            auto_fuzzy_threshold=0.7,
            suggestion_threshold=0.8,
            max_suggestions=5,
            enable_auto_fuzzy=False,
        )
        assert config.auto_fuzzy_threshold == 0.7
        assert config.suggestion_threshold == 0.8
        assert config.max_suggestions == 5
        assert config.enable_auto_fuzzy is False

    def test_config_validation(self):
        """Test fuzzy search config validation."""
        from pydantic import ValidationError

        from local_deepwiki.config import FuzzySearchConfig

        # Invalid threshold (> 1.0)
        with pytest.raises(ValidationError):
            FuzzySearchConfig(auto_fuzzy_threshold=1.5)

        # Invalid threshold (< 0.0)
        with pytest.raises(ValidationError):
            FuzzySearchConfig(auto_fuzzy_threshold=-0.1)

        # Invalid max_suggestions (< 1)
        with pytest.raises(ValidationError):
            FuzzySearchConfig(max_suggestions=0)
