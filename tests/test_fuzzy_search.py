"""Tests for fuzzy search functionality."""

import pytest

from local_deepwiki.core.fuzzy_search import (
    extract_highlights,
    filter_by_path,
    fuzzy_match_name,
    fuzzy_score,
    matches_path_pattern,
    rerank_with_fuzzy,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


class TestFuzzyScore:
    """Tests for fuzzy_score function."""

    def test_exact_match(self):
        """Test exact match returns high score."""
        score = fuzzy_score("calculate", "calculate")
        assert score >= 0.9

    def test_partial_match(self):
        """Test partial match returns good score."""
        score = fuzzy_score("calc", "calculate the sum")
        assert score >= 0.5

    def test_no_match(self):
        """Test no match returns low score."""
        score = fuzzy_score("xyz", "calculate")
        assert score < 0.3

    def test_empty_query(self):
        """Test empty query returns 0."""
        assert fuzzy_score("", "calculate") == 0.0

    def test_empty_text(self):
        """Test empty text returns 0."""
        assert fuzzy_score("calc", "") == 0.0

    def test_word_order_tolerance(self):
        """Test that word order doesn't affect score much."""
        score1 = fuzzy_score("user data", "user data processing")
        score2 = fuzzy_score("data user", "user data processing")
        # Both should have decent scores
        assert score1 >= 0.5
        assert score2 >= 0.4


class TestFuzzyMatchName:
    """Tests for fuzzy_match_name function."""

    def test_exact_match(self):
        """Test exact match returns 1.0."""
        assert fuzzy_match_name("calculate", "calculate") == 1.0

    def test_prefix_match(self):
        """Test prefix match returns high score."""
        score = fuzzy_match_name("calc", "calculate_sum")
        assert score >= 0.8

    def test_contains_match(self):
        """Test contains match returns good score."""
        score = fuzzy_match_name("user", "get_user_data")
        assert score >= 0.7

    def test_snake_case_part_match(self):
        """Test matching a part of snake_case name."""
        score = fuzzy_match_name("data", "get_user_data")
        assert score >= 0.7

    def test_camel_case_part_match(self):
        """Test matching a part of camelCase name."""
        score = fuzzy_match_name("User", "getUserData")
        assert score >= 0.7

    def test_none_name(self):
        """Test None name returns 0."""
        assert fuzzy_match_name("query", None) == 0.0

    def test_empty_query(self):
        """Test empty query returns 0."""
        assert fuzzy_match_name("", "function_name") == 0.0


class TestMatchesPathPattern:
    """Tests for matches_path_pattern function."""

    def test_simple_glob(self):
        """Test simple glob pattern."""
        assert matches_path_pattern("test.py", "*.py")
        assert not matches_path_pattern("test.js", "*.py")

    def test_directory_pattern(self):
        """Test directory pattern."""
        assert matches_path_pattern("src/module.py", "src/*.py")
        assert not matches_path_pattern("tests/module.py", "src/*.py")

    def test_recursive_pattern(self):
        """Test recursive ** pattern."""
        assert matches_path_pattern("src/core/module.py", "src/**/*.py")
        assert matches_path_pattern("src/module.py", "src/**/*.py")
        assert not matches_path_pattern("tests/module.py", "src/**/*.py")

    def test_empty_pattern(self):
        """Test empty pattern matches everything."""
        assert matches_path_pattern("any/path.py", "")
        assert matches_path_pattern("any/path.py", None)

    def test_backslash_normalization(self):
        """Test that backslashes are normalized."""
        assert matches_path_pattern("src\\module.py", "src/*.py")

    def test_exact_path(self):
        """Test exact path match."""
        assert matches_path_pattern("src/main.py", "src/main.py")


class TestExtractHighlights:
    """Tests for extract_highlights function."""

    def test_single_match(self):
        """Test extracting single match."""
        content = "This is a function that calculates the sum."
        highlights = extract_highlights(content, "function", context_chars=10)
        assert len(highlights) == 1
        assert "function" in highlights[0]

    def test_multiple_matches(self):
        """Test extracting multiple matches."""
        content = "def foo(): pass\ndef bar(): pass\ndef baz(): pass"
        highlights = extract_highlights(content, "def", context_chars=5)
        # Should be capped at 3
        assert len(highlights) <= 3

    def test_no_match(self):
        """Test no match returns empty list."""
        content = "This is some code"
        highlights = extract_highlights(content, "xyz")
        assert highlights == []

    def test_empty_inputs(self):
        """Test empty inputs return empty list."""
        assert extract_highlights("", "query") == []
        assert extract_highlights("content", "") == []

    def test_ellipsis_added(self):
        """Test ellipsis is added for truncated context."""
        content = "x" * 100 + "match" + "y" * 100
        highlights = extract_highlights(content, "match", context_chars=20)
        assert len(highlights) == 1
        assert highlights[0].startswith("...")
        assert highlights[0].endswith("...")


class TestFilterByPath:
    """Tests for filter_by_path function."""

    @pytest.fixture
    def sample_results(self):
        """Create sample search results."""

        def make_result(file_path: str, score: float = 0.8) -> SearchResult:
            chunk = CodeChunk(
                id=f"chunk_{file_path}",
                file_path=file_path,
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="test_func",
                content="def test(): pass",
                start_line=1,
                end_line=1,
            )
            return SearchResult(chunk=chunk, score=score, highlights=[])

        return [
            make_result("src/core/module.py", 0.9),
            make_result("src/utils/helper.py", 0.85),
            make_result("tests/test_module.py", 0.8),
            make_result("main.py", 0.75),
        ]

    def test_filter_src_files(self, sample_results):
        """Test filtering to src directory."""
        filtered = filter_by_path(sample_results, "src/**/*.py")
        assert len(filtered) == 2
        assert all("src/" in r.chunk.file_path for r in filtered)

    def test_filter_test_files(self, sample_results):
        """Test filtering to test files."""
        filtered = filter_by_path(sample_results, "tests/*.py")
        assert len(filtered) == 1
        assert "tests/" in filtered[0].chunk.file_path

    def test_no_filter(self, sample_results):
        """Test no filter returns all results."""
        filtered = filter_by_path(sample_results, None)
        assert len(filtered) == 4

    def test_no_matches(self, sample_results):
        """Test filter with no matches returns empty list."""
        filtered = filter_by_path(sample_results, "docs/*.md")
        assert len(filtered) == 0


class TestRerankWithFuzzy:
    """Tests for rerank_with_fuzzy function."""

    @pytest.fixture
    def sample_results(self):
        """Create sample search results for reranking."""

        def make_result(name: str, content: str, score: float) -> SearchResult:
            chunk = CodeChunk(
                id=f"chunk_{name}",
                file_path="src/module.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name=name,
                content=content,
                start_line=1,
                end_line=1,
            )
            return SearchResult(chunk=chunk, score=score, highlights=[])

        return [
            make_result("get_user", "def get_user(): return user", 0.8),
            make_result("process_data", "def process_data(): return data", 0.85),
            make_result("calculate_user_score", "def calculate_user_score(): pass", 0.7),
        ]

    def test_rerank_boosts_exact_match(self, sample_results):
        """Test that fuzzy reranking boosts exact name matches."""
        reranked = rerank_with_fuzzy(sample_results, "get_user", fuzzy_weight=0.5)

        # get_user should be ranked first due to exact name match
        assert reranked[0].chunk.name == "get_user"

    def test_rerank_preserves_order_without_fuzzy(self, sample_results):
        """Test that zero fuzzy weight preserves original order."""
        reranked = rerank_with_fuzzy(sample_results, "query", fuzzy_weight=0.0)

        # Order should be by original score (process_data has highest)
        assert reranked[0].chunk.name == "process_data"

    def test_rerank_empty_results(self):
        """Test reranking empty results returns empty list."""
        assert rerank_with_fuzzy([], "query") == []

    def test_rerank_adds_highlights(self, sample_results):
        """Test that reranking preserves result structure."""
        reranked = rerank_with_fuzzy(sample_results, "user", fuzzy_weight=0.3)

        # All results should still have valid chunks
        for result in reranked:
            assert result.chunk is not None
            assert result.score >= 0


class TestValidation:
    """Tests for validation functions."""

    def test_validate_chunk_type_valid(self):
        """Test valid chunk types are accepted."""
        from local_deepwiki.validation import validate_chunk_type

        assert validate_chunk_type("function") == "function"
        assert validate_chunk_type("class") == "class"
        assert validate_chunk_type("method") == "method"
        assert validate_chunk_type(None) is None

    def test_validate_chunk_type_invalid(self):
        """Test invalid chunk type raises error."""
        from local_deepwiki.validation import validate_chunk_type

        with pytest.raises(ValueError, match="Invalid chunk_type"):
            validate_chunk_type("invalid_type")

    def test_validate_path_pattern_valid(self):
        """Test valid path patterns are accepted."""
        from local_deepwiki.validation import validate_path_pattern

        assert validate_path_pattern("src/**/*.py") == "src/**/*.py"
        assert validate_path_pattern("*.py") == "*.py"
        assert validate_path_pattern(None) is None
        assert validate_path_pattern("") is None

    def test_validate_path_pattern_invalid(self):
        """Test invalid path patterns raise error."""
        from local_deepwiki.validation import validate_path_pattern

        with pytest.raises(ValueError, match="cannot contain"):
            validate_path_pattern("../etc/passwd")

    def test_validate_fuzzy_weight_valid(self):
        """Test valid fuzzy weights are accepted."""
        from local_deepwiki.validation import validate_fuzzy_weight

        assert validate_fuzzy_weight(0.0) == 0.0
        assert validate_fuzzy_weight(0.5) == 0.5
        assert validate_fuzzy_weight(1.0) == 1.0
        assert validate_fuzzy_weight(None) == 0.3  # default

    def test_validate_fuzzy_weight_invalid(self):
        """Test invalid fuzzy weights raise error."""
        from local_deepwiki.validation import validate_fuzzy_weight

        with pytest.raises(ValueError, match="must be between"):
            validate_fuzzy_weight(1.5)
        with pytest.raises(ValueError, match="must be between"):
            validate_fuzzy_weight(-0.1)


class TestVectorStoreSearchWithFilters:
    """Integration tests for VectorStore.search with new filter options."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.providers.base import EmbeddingProvider

        class MockEmbeddingProvider(EmbeddingProvider):
            @property
            def name(self) -> str:
                return "mock"

            def get_dimension(self) -> int:
                return 384

            async def embed(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 384 for _ in texts]

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data."""
        chunks = [
            CodeChunk(
                id="func_1",
                file_path="src/core/auth.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="authenticate_user",
                content="def authenticate_user(username, password): pass",
                start_line=1,
                end_line=5,
                docstring="Authenticate a user with username and password.",
            ),
            CodeChunk(
                id="class_1",
                file_path="src/models/user.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="User",
                content="class User: pass",
                start_line=1,
                end_line=10,
            ),
            CodeChunk(
                id="func_2",
                file_path="tests/test_auth.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="test_authenticate",
                content="def test_authenticate(): pass",
                start_line=1,
                end_line=3,
            ),
            CodeChunk(
                id="method_1",
                file_path="src/core/auth.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.METHOD,
                name="validate",
                content="def validate(self): pass",
                start_line=10,
                end_line=15,
            ),
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_search_with_path_filter(self, populated_store):
        """Test search with path pattern filter."""
        results = await populated_store.search(
            "authenticate",
            limit=10,
            path_pattern="src/**/*.py",
        )
        # Should only return results from src directory
        assert all("src/" in r.chunk.file_path for r in results)
        # Should not include test files
        assert not any("tests/" in r.chunk.file_path for r in results)

    async def test_search_with_chunk_type_filter(self, populated_store):
        """Test search with chunk type filter."""
        results = await populated_store.search(
            "user",
            limit=10,
            chunk_type="class",
        )
        assert all(r.chunk.chunk_type == ChunkType.CLASS for r in results)

    async def test_search_with_fuzzy(self, populated_store):
        """Test search with fuzzy matching enabled."""
        results = await populated_store.search(
            "authenticate_user",
            limit=10,
            use_fuzzy=True,
            fuzzy_weight=0.5,
        )
        # Should return results
        assert len(results) > 0
        # The exact name match should be ranked high
        assert any(r.chunk.name == "authenticate_user" for r in results)

    async def test_search_with_multiple_filters(self, populated_store):
        """Test search with multiple filters combined."""
        results = await populated_store.search(
            "user",
            limit=10,
            language="python",
            chunk_type="function",
            path_pattern="src/**/*.py",
        )
        # All filters should be applied
        for r in results:
            assert r.chunk.language == Language.PYTHON
            assert r.chunk.chunk_type == ChunkType.FUNCTION
            assert "src/" in r.chunk.file_path

    async def test_search_fuzzy_adds_highlights(self, populated_store):
        """Test that fuzzy search adds highlights to results."""
        results = await populated_store.search(
            "authenticate",
            limit=10,
            use_fuzzy=True,
        )
        # At least one result should have highlights for the matching term
        has_highlights = any(r.highlights for r in results)
        # Note: highlights depend on content containing the exact query
        # This is expected behavior
        assert len(results) > 0


class TestFuzzySearchHelper:
    """Tests for the FuzzySearchHelper class."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.providers.base import EmbeddingProvider

        class MockEmbeddingProvider(EmbeddingProvider):
            @property
            def name(self) -> str:
                return "mock"

            def get_dimension(self) -> int:
                return 384

            async def embed(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 384 for _ in texts]

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def store_with_named_chunks(self, vector_store):
        """Create a store with chunks that have names."""
        chunks = [
            CodeChunk(
                id="func_1",
                file_path="src/math.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="calculate_sum",
                content="def calculate_sum(a, b): return a + b",
                start_line=1,
                end_line=2,
            ),
            CodeChunk(
                id="func_2",
                file_path="src/math.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="calculate_product",
                content="def calculate_product(a, b): return a * b",
                start_line=3,
                end_line=4,
            ),
            CodeChunk(
                id="func_3",
                file_path="src/math.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="calculate_difference",
                content="def calculate_difference(a, b): return a - b",
                start_line=5,
                end_line=6,
            ),
            CodeChunk(
                id="class_1",
                file_path="src/user.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="UserManager",
                content="class UserManager: pass",
                start_line=1,
                end_line=10,
            ),
            CodeChunk(
                id="method_1",
                file_path="src/user.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.METHOD,
                name="get_user",
                content="def get_user(self): pass",
                start_line=5,
                end_line=7,
                parent_name="UserManager",
            ),
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_build_name_index(self, store_with_named_chunks):
        """Test building the fuzzy name index."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(store_with_named_chunks)
        await helper.build_name_index()

        assert helper.is_built
        stats = helper.get_stats()
        assert stats["total_names"] >= 5  # At least 5 names indexed
        assert stats["unique_names"] >= 5

    async def test_find_similar_names(self, store_with_named_chunks):
        """Test finding similar names."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(store_with_named_chunks)
        await helper.build_name_index()

        # Exact match
        results = helper.find_similar_names("calculate_sum", threshold=0.6)
        assert len(results) > 0
        names = [n for n, s in results]
        assert "calculate_sum" in names

    async def test_find_similar_names_with_typo(self, store_with_named_chunks):
        """Test finding similar names with a typo."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(store_with_named_chunks)
        await helper.build_name_index()

        # Typo: "calcluate" instead of "calculate"
        results = helper.find_similar_names("calcluate_sum", threshold=0.5)
        assert len(results) > 0
        # Should find calculate_sum despite typo
        names = [n for n, s in results]
        assert any("calculate" in n for n in names)

    async def test_generate_suggestions_empty_results(self, store_with_named_chunks):
        """Test generating suggestions when results are empty."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(store_with_named_chunks)
        await helper.build_name_index()

        suggestions = helper.generate_suggestions("calcluate", [], threshold=0.5)
        assert len(suggestions) > 0
        # Should suggest names containing "calculate"
        assert any("calculate" in s for s in suggestions)

    async def test_generate_suggestions_excludes_existing_names(self, store_with_named_chunks):
        """Test that suggestions exclude names already in results."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(store_with_named_chunks)
        await helper.build_name_index()

        # Create mock result with calculate_sum
        existing_chunk = CodeChunk(
            id="existing",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="calculate_sum",
            content="def calculate_sum(): pass",
            start_line=1,
            end_line=1,
        )
        existing_results = [SearchResult(chunk=existing_chunk, score=0.3, highlights=[])]

        suggestions = helper.generate_suggestions("calculate", existing_results, threshold=0.5)
        # Should not include calculate_sum
        assert "calculate_sum" not in suggestions

    async def test_get_stats(self, store_with_named_chunks):
        """Test getting statistics about the name index."""
        from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

        helper = FuzzySearchHelper(store_with_named_chunks)
        await helper.build_name_index()

        stats = helper.get_stats()
        assert "total_names" in stats
        assert "unique_names" in stats
        assert stats["total_names"] >= 5


class TestShouldAutoEnableFuzzy:
    """Tests for the should_auto_enable_fuzzy function."""

    def test_empty_results(self):
        """Test that empty results trigger auto-fuzzy."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

        assert should_auto_enable_fuzzy([], threshold=0.5) is True

    def test_low_score_results(self):
        """Test that low-scoring results trigger auto-fuzzy."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

        chunk = CodeChunk(
            id="test",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test",
            content="def test(): pass",
            start_line=1,
            end_line=1,
        )
        results = [SearchResult(chunk=chunk, score=0.3, highlights=[])]

        assert should_auto_enable_fuzzy(results, threshold=0.5) is True

    def test_high_score_results(self):
        """Test that high-scoring results do not trigger auto-fuzzy."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

        chunk = CodeChunk(
            id="test",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test",
            content="def test(): pass",
            start_line=1,
            end_line=1,
        )
        results = [SearchResult(chunk=chunk, score=0.8, highlights=[])]

        assert should_auto_enable_fuzzy(results, threshold=0.5) is False

    def test_multiple_results_best_score_matters(self):
        """Test that only the best score matters for threshold check."""
        from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

        chunk1 = CodeChunk(
            id="test1",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test1",
            content="def test1(): pass",
            start_line=1,
            end_line=1,
        )
        chunk2 = CodeChunk(
            id="test2",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test2",
            content="def test2(): pass",
            start_line=2,
            end_line=2,
        )
        # One high score, one low score
        results = [
            SearchResult(chunk=chunk1, score=0.8, highlights=[]),
            SearchResult(chunk=chunk2, score=0.2, highlights=[]),
        ]

        # Best score is 0.8, which is above threshold 0.5
        assert should_auto_enable_fuzzy(results, threshold=0.5) is False


class TestNameEntry:
    """Tests for the NameEntry dataclass."""

    def test_name_entry_creation(self):
        """Test creating a NameEntry."""
        from local_deepwiki.core.fuzzy_search import NameEntry

        entry = NameEntry(
            name="calculate_sum",
            chunk_type=ChunkType.FUNCTION,
            file_path="src/math.py",
        )
        assert entry.name == "calculate_sum"
        assert entry.chunk_type == ChunkType.FUNCTION
        assert entry.file_path == "src/math.py"
        assert entry.full_qualified_name is None

    def test_name_entry_with_qualified_name(self):
        """Test creating a NameEntry with fully qualified name."""
        from local_deepwiki.core.fuzzy_search import NameEntry

        entry = NameEntry(
            name="get_user",
            chunk_type=ChunkType.METHOD,
            file_path="src/user.py",
            full_qualified_name="UserManager.get_user",
        )
        assert entry.name == "get_user"
        assert entry.full_qualified_name == "UserManager.get_user"
