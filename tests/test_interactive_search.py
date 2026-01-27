"""Tests for the interactive search CLI module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.cli.interactive_search import (
    InteractiveSearch,
    SearchFilters,
    SearchState,
    run_search,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_chunk() -> CodeChunk:
    """Create a sample code chunk for testing."""
    return CodeChunk(
        id="test-chunk-1",
        file_path="src/utils/helpers.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name="calculate_total",
        content='def calculate_total(items):\n    """Calculate total price."""\n    return sum(i.price for i in items)',
        start_line=10,
        end_line=13,
        docstring="Calculate total price.",
    )


@pytest.fixture
def sample_results(sample_chunk: CodeChunk) -> list[SearchResult]:
    """Create sample search results for testing."""
    chunks = [
        sample_chunk,
        CodeChunk(
            id="test-chunk-2",
            file_path="src/models/item.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.CLASS,
            name="Item",
            content="class Item:\n    def __init__(self, price):\n        self.price = price",
            start_line=1,
            end_line=4,
        ),
        CodeChunk(
            id="test-chunk-3",
            file_path="src/api/handlers.ts",
            language=Language.TYPESCRIPT,
            chunk_type=ChunkType.FUNCTION,
            name="getItems",
            content="export function getItems(): Item[] {\n  return items;\n}",
            start_line=20,
            end_line=23,
        ),
        CodeChunk(
            id="test-chunk-4",
            file_path="src/utils/math.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="sum_values",
            content="def sum_values(values: list[int]) -> int:\n    return sum(values)",
            start_line=5,
            end_line=7,
        ),
    ]

    return [
        SearchResult(chunk=chunks[0], score=0.95),
        SearchResult(chunk=chunks[1], score=0.82),
        SearchResult(chunk=chunks[2], score=0.71),
        SearchResult(chunk=chunks[3], score=0.45),
    ]


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Create a mock vector store."""
    store = MagicMock()
    store.search = AsyncMock(return_value=[])
    return store


# =============================================================================
# SearchFilters Tests
# =============================================================================


class TestSearchFilters:
    """Tests for SearchFilters class."""

    def test_empty_filters_match_all(self, sample_results: list[SearchResult]) -> None:
        """Empty filters should match all results."""
        filters = SearchFilters()
        for result in sample_results:
            assert filters.matches(result) is True

    def test_language_filter(self, sample_results: list[SearchResult]) -> None:
        """Language filter should only match specified language."""
        filters = SearchFilters(language="python")

        # Python results should match
        assert filters.matches(sample_results[0]) is True  # Python function
        assert filters.matches(sample_results[1]) is True  # Python class
        assert filters.matches(sample_results[3]) is True  # Python function

        # TypeScript should not match
        assert filters.matches(sample_results[2]) is False  # TypeScript

    def test_chunk_type_filter(self, sample_results: list[SearchResult]) -> None:
        """Chunk type filter should only match specified type."""
        filters = SearchFilters(chunk_type="function")

        # Functions should match
        assert filters.matches(sample_results[0]) is True
        assert filters.matches(sample_results[2]) is True
        assert filters.matches(sample_results[3]) is True

        # Class should not match
        assert filters.matches(sample_results[1]) is False

    def test_file_pattern_filter(self, sample_results: list[SearchResult]) -> None:
        """File pattern filter should match using glob patterns."""
        # Match all Python files in utils
        filters = SearchFilters(file_pattern="src/utils/*.py")
        assert filters.matches(sample_results[0]) is True  # src/utils/helpers.py
        assert filters.matches(sample_results[1]) is False  # src/models/item.py
        assert filters.matches(sample_results[2]) is False  # src/api/handlers.ts
        assert filters.matches(sample_results[3]) is True  # src/utils/math.py

        # Match any TypeScript file
        filters = SearchFilters(file_pattern="*.ts")
        assert filters.matches(sample_results[0]) is False
        assert filters.matches(sample_results[2]) is True

    def test_min_similarity_filter(self, sample_results: list[SearchResult]) -> None:
        """Min similarity filter should exclude low-scoring results."""
        filters = SearchFilters(min_similarity=0.5)

        # High scores should match
        assert filters.matches(sample_results[0]) is True  # 0.95
        assert filters.matches(sample_results[1]) is True  # 0.82
        assert filters.matches(sample_results[2]) is True  # 0.71

        # Low score should not match
        assert filters.matches(sample_results[3]) is False  # 0.45

    def test_combined_filters(self, sample_results: list[SearchResult]) -> None:
        """Multiple filters should all be applied."""
        filters = SearchFilters(
            language="python",
            chunk_type="function",
            min_similarity=0.5,
        )

        # Only Python functions with high score
        assert filters.matches(sample_results[0]) is True  # Python function, 0.95
        assert filters.matches(sample_results[1]) is False  # Python class
        assert filters.matches(sample_results[2]) is False  # TypeScript
        assert filters.matches(sample_results[3]) is False  # Python function, 0.45

    def test_to_dict_empty(self) -> None:
        """Empty filters should return empty dict."""
        filters = SearchFilters()
        assert filters.to_dict() == {}

    def test_to_dict_with_filters(self) -> None:
        """to_dict should include all active filters."""
        filters = SearchFilters(
            language="python",
            chunk_type="function",
            file_pattern="src/*.py",
            min_similarity=0.5,
        )
        result = filters.to_dict()

        assert result["language"] == "python"
        assert result["type"] == "function"
        assert result["path"] == "src/*.py"
        assert result["min_score"] == "0.50"

    def test_clear(self) -> None:
        """Clear should reset all filters."""
        filters = SearchFilters(
            language="python",
            chunk_type="function",
            file_pattern="src/*.py",
            min_similarity=0.5,
        )
        filters.clear()

        assert filters.language is None
        assert filters.chunk_type is None
        assert filters.file_pattern is None
        assert filters.min_similarity == 0.0


# =============================================================================
# SearchState Tests
# =============================================================================


class TestSearchState:
    """Tests for SearchState class."""

    def test_initial_state(self) -> None:
        """Initial state should have sensible defaults."""
        state = SearchState()

        assert state.query == ""
        assert state.results == []
        assert state.filtered_results == []
        assert state.selected_index == 0
        assert state.show_preview is False
        assert state.input_mode == "search"
        assert state.error_message is None

    def test_apply_filters(self, sample_results: list[SearchResult]) -> None:
        """apply_filters should update filtered_results."""
        state = SearchState()
        state.results = sample_results
        state.filters = SearchFilters(language="python")

        state.apply_filters()

        # Should only have Python results
        assert len(state.filtered_results) == 3
        for result in state.filtered_results:
            assert result.chunk.language == Language.PYTHON

    def test_apply_filters_resets_selection(self, sample_results: list[SearchResult]) -> None:
        """apply_filters should reset selection if out of bounds."""
        state = SearchState()
        state.results = sample_results
        state.filtered_results = sample_results
        state.selected_index = 3  # Last result

        # Apply filter that leaves only 1 result
        state.filters = SearchFilters(chunk_type="class")
        state.apply_filters()

        assert len(state.filtered_results) == 1
        assert state.selected_index == 0  # Reset to valid index

    def test_move_selection_down(self, sample_results: list[SearchResult]) -> None:
        """move_selection should move down when delta is positive."""
        state = SearchState()
        state.filtered_results = sample_results
        state.selected_index = 0

        state.move_selection(1)
        assert state.selected_index == 1

        state.move_selection(2)
        assert state.selected_index == 3

    def test_move_selection_up(self, sample_results: list[SearchResult]) -> None:
        """move_selection should move up when delta is negative."""
        state = SearchState()
        state.filtered_results = sample_results
        state.selected_index = 3

        state.move_selection(-1)
        assert state.selected_index == 2

        state.move_selection(-2)
        assert state.selected_index == 0

    def test_move_selection_clamps_at_bounds(self, sample_results: list[SearchResult]) -> None:
        """move_selection should not go out of bounds."""
        state = SearchState()
        state.filtered_results = sample_results

        # Try to go below 0
        state.selected_index = 0
        state.move_selection(-5)
        assert state.selected_index == 0

        # Try to go above max
        state.selected_index = 3
        state.move_selection(5)
        assert state.selected_index == 3

    def test_move_selection_empty_results(self) -> None:
        """move_selection should handle empty results."""
        state = SearchState()
        state.filtered_results = []
        state.selected_index = 0

        # Should not raise
        state.move_selection(1)
        assert state.selected_index == 0

    def test_get_selected_result(self, sample_results: list[SearchResult]) -> None:
        """get_selected_result should return the selected result."""
        state = SearchState()
        state.filtered_results = sample_results
        state.selected_index = 2

        result = state.get_selected_result()
        assert result == sample_results[2]

    def test_get_selected_result_empty(self) -> None:
        """get_selected_result should return None for empty results."""
        state = SearchState()
        state.filtered_results = []

        result = state.get_selected_result()
        assert result is None


# =============================================================================
# InteractiveSearch Tests
# =============================================================================


class TestInteractiveSearch:
    """Tests for InteractiveSearch class."""

    def test_init(self, mock_vector_store: MagicMock) -> None:
        """InteractiveSearch should initialize correctly."""
        repo_path = Path("/test/repo")
        search = InteractiveSearch(mock_vector_store, repo_path)

        assert search._store == mock_vector_store
        assert search._repo_path == repo_path
        assert search._state.query == ""

    async def test_search_executes_query(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """search should execute query against vector store."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)

        search = InteractiveSearch(mock_vector_store, Path("/test"))
        await search.search("calculate total", limit=10)

        mock_vector_store.search.assert_called_once()
        assert search._state.query == "calculate total"
        assert len(search._state.results) == 4

    async def test_search_empty_query(self, mock_vector_store: MagicMock) -> None:
        """search with empty query should clear results."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        await search.search("", limit=10)

        mock_vector_store.search.assert_not_called()
        assert search._state.results == []
        assert search._state.filtered_results == []

    async def test_search_applies_filters(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """search should apply filters to results."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)

        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filters = SearchFilters(language="python")

        await search.search("test", limit=10)

        # Should filter out TypeScript result
        assert len(search._state.filtered_results) == 3

    async def test_search_handles_errors(self, mock_vector_store: MagicMock) -> None:
        """search should handle and report errors."""
        mock_vector_store.search = AsyncMock(side_effect=Exception("Test error"))

        search = InteractiveSearch(mock_vector_store, Path("/test"))
        await search.search("test", limit=10)

        assert search._state.error_message is not None
        assert "Test error" in search._state.error_message
        assert search._state.results == []

    def test_build_results_table(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """_build_results_table should create a valid Rich Table."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = sample_results

        table = search._build_results_table()

        # Should have the right columns
        assert len(table.columns) == 6
        # Should have all results as rows
        assert table.row_count == 4

    def test_build_filters_panel_empty(self, mock_vector_store: MagicMock) -> None:
        """_build_filters_panel should show 'No filters active' when empty."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        panel = search._build_filters_panel()

        assert panel.title == "Active Filters"
        # Should have dim border when no filters
        assert panel.border_style == "dim"

    def test_build_filters_panel_with_filters(self, mock_vector_store: MagicMock) -> None:
        """_build_filters_panel should show active filters."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filters = SearchFilters(language="python", min_similarity=0.5)

        panel = search._build_filters_panel()

        assert panel.border_style == "green"

    def test_build_preview_panel(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """_build_preview_panel should create syntax-highlighted preview."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filtered_results = sample_results
        search._state.selected_index = 0

        panel = search._build_preview_panel()

        assert panel is not None
        # Title should include file path
        assert "src/utils/helpers.py" in panel.title

    def test_build_preview_panel_no_selection(self, mock_vector_store: MagicMock) -> None:
        """_build_preview_panel should return None when no selection."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filtered_results = []

        panel = search._build_preview_panel()
        assert panel is None


# =============================================================================
# run_search Tests
# =============================================================================


class TestRunSearch:
    """Tests for the run_search function."""

    async def test_run_search_repo_not_found(self, tmp_path: Path) -> None:
        """run_search should handle missing repository."""
        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            await run_search(
                repo_path=tmp_path / "nonexistent",
                query="test",
                interactive=False,
            )

            # Should print error
            mock_console.print.assert_called()
            call_args = str(mock_console.print.call_args)
            assert "not found" in call_args.lower()

    async def test_run_search_not_indexed(self, tmp_path: Path) -> None:
        """run_search should handle non-indexed repository."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            await run_search(
                repo_path=repo_path,
                query="test",
                interactive=False,
            )

            # Should print error about not indexed
            mock_console.print.assert_called()
            call_args = str(mock_console.print.call_args)
            assert "not indexed" in call_args.lower()

    async def test_run_search_non_interactive_no_query(self, tmp_path: Path) -> None:
        """run_search should require query in non-interactive mode."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch("local_deepwiki.cli.interactive_search.VectorStore"):
                    await run_search(
                        repo_path=repo_path,
                        query=None,
                        interactive=False,
                    )

                    # Should print error about query required
                    mock_console.print.assert_called()
                    call_args = str(mock_console.print.call_args)
                    assert "query" in call_args.lower() and "required" in call_args.lower()


# =============================================================================
# Integration Tests (with mocked keyboard)
# =============================================================================


class TestKeyboardHandling:
    """Tests for keyboard handling (mocked)."""

    async def test_handle_search_mode_quit(self, mock_vector_store: MagicMock) -> None:
        """'q' key should signal quit."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            result = await search._handle_search_mode("q")
            assert result is False  # Should signal to quit

    async def test_handle_search_mode_navigation(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """Up/Down keys should navigate results."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filtered_results = sample_results
        search._state.selected_index = 1

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            # Down should increase index
            await search._handle_search_mode(mock_readchar.key.DOWN)
            assert search._state.selected_index == 2

            # Up should decrease index
            await search._handle_search_mode(mock_readchar.key.UP)
            assert search._state.selected_index == 1

    async def test_handle_search_mode_toggle_preview(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Enter should toggle preview mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            assert search._state.show_preview is False
            await search._handle_search_mode(mock_readchar.key.ENTER)
            assert search._state.show_preview is True

    async def test_handle_search_mode_filter_keys(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Filter keys should switch input mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            await search._handle_search_mode("l")
            assert search._state.input_mode == "filter_language"

            search._state.input_mode = "search"
            await search._handle_search_mode("t")
            assert search._state.input_mode == "filter_type"

            search._state.input_mode = "search"
            await search._handle_search_mode("f")
            assert search._state.input_mode == "filter_path"

            search._state.input_mode = "search"
            await search._handle_search_mode("s")
            assert search._state.input_mode == "filter_score"

    async def test_handle_search_mode_clear_filters(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """'c' key should clear all filters."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.results = sample_results
        search._state.filters = SearchFilters(language="python", min_similarity=0.5)
        search._state.apply_filters()

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            await search._handle_search_mode("c")

            assert search._state.filters.language is None
            assert search._state.filters.min_similarity == 0.0

    async def test_handle_search_mode_new_search_slash_key(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """'/' key should prompt for new search."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            # Mock the console input method
            search._console.input = MagicMock(return_value="new query")
            search._console.clear = MagicMock()

            result = await search._handle_search_mode("/")

            assert result is True  # Should continue running
            search._console.clear.assert_called()
            search._console.input.assert_called()
            assert search._state.query == "new query"

    async def test_handle_search_mode_new_search_empty_query(
        self, mock_vector_store: MagicMock
    ) -> None:
        """'/' key with empty input should not perform search."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "original"

        # Create a mock readchar module
        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            # Mock the console input method returning empty string
            search._console.input = MagicMock(return_value="")
            search._console.clear = MagicMock()

            await search._handle_search_mode("/")

            # Query should remain unchanged
            assert search._state.query == "original"
            mock_vector_store.search.assert_not_called()

    async def test_handle_search_mode_readchar_import_error(
        self, mock_vector_store: MagicMock
    ) -> None:
        """_handle_search_mode should return False when readchar is unavailable."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Remove readchar from sys.modules if present
        with patch.dict("sys.modules", {"readchar": None}):
            # This should handle ImportError gracefully
            result = await search._handle_search_mode("q")
            assert result is False


# =============================================================================
# Filter Mode Tests
# =============================================================================


class TestFilterModeHandling:
    """Tests for filter mode keyboard handling."""

    async def test_handle_filter_mode_escape_returns_to_search(
        self, mock_vector_store: MagicMock
    ) -> None:
        """ESC key should return to search mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_language"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            await search._handle_filter_mode(mock_readchar.key.ESCAPE)
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_language_valid(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """Valid language filter should be applied."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_language"
        search._state.query = "test"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="python")
            search._console.clear = MagicMock()
            search._console.print = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.filters.language == "python"
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_language_invalid(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Invalid language filter should set error message."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_language"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="invalid_language")
            search._console.clear = MagicMock()
            search._console.print = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.error_message is not None
            assert "Invalid language" in search._state.error_message
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_type_valid(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """Valid chunk type filter should be applied."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_type"
        search._state.query = "test"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="function")
            search._console.clear = MagicMock()
            search._console.print = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.filters.chunk_type == "function"
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_type_invalid(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Invalid chunk type should set error message."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_type"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="invalid_type")
            search._console.clear = MagicMock()
            search._console.print = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.error_message is not None
            assert "Invalid type" in search._state.error_message

    async def test_handle_filter_mode_path(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """File path pattern filter should be applied."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_path"
        search._state.query = "test"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="src/**/*.py")
            search._console.clear = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.filters.file_pattern == "src/**/*.py"
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_score_valid(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """Valid score filter should be applied."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_score"
        search._state.query = "test"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="0.5")
            search._console.clear = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.filters.min_similarity == 0.5
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_score_out_of_range(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Score outside 0.0-1.0 range should set error message."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_score"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="1.5")
            search._console.clear = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.error_message is not None
            assert "between 0.0 and 1.0" in search._state.error_message

    async def test_handle_filter_mode_score_invalid_format(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Invalid score format should set error message."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_score"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="not-a-number")
            search._console.clear = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.error_message is not None
            assert "Invalid score" in search._state.error_message

    async def test_handle_filter_mode_empty_input(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Empty input in filter mode should not change filter."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_language"

        mock_readchar = MagicMock()
        mock_readchar.key.ESCAPE = "\x1b"
        mock_readchar.key.ENTER = "\r"

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            search._console.input = MagicMock(return_value="")
            search._console.clear = MagicMock()
            search._console.print = MagicMock()

            await search._handle_filter_mode(mock_readchar.key.ENTER)

            assert search._state.filters.language is None
            assert search._state.input_mode == "search"

    async def test_handle_filter_mode_readchar_import_error(
        self, mock_vector_store: MagicMock
    ) -> None:
        """_handle_filter_mode should return when readchar is unavailable."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_language"

        # Remove readchar from sys.modules if present
        with patch.dict("sys.modules", {"readchar": None}):
            # This should handle ImportError gracefully
            await search._handle_filter_mode("\r")
            # Should remain in same mode since it returned early
            assert search._state.input_mode == "filter_language"


# =============================================================================
# Layout and Display Tests
# =============================================================================


class TestLayoutAndDisplay:
    """Tests for layout building and display methods."""

    def test_build_results_table_long_name_truncation(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Long names should be truncated with ellipsis."""
        chunk = CodeChunk(
            id="test-chunk",
            file_path="src/test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="this_is_a_very_long_function_name_that_exceeds_limit",
            content="def test(): pass",
            start_line=1,
            end_line=2,
        )
        result = SearchResult(chunk=chunk, score=0.9)

        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = [result]

        table = search._build_results_table()
        assert table.row_count == 1
        # Table should be built without error for long names

    def test_build_results_table_long_path_truncation(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Long file paths should be truncated with leading ellipsis."""
        chunk = CodeChunk(
            id="test-chunk",
            file_path="very/long/path/to/deeply/nested/directory/structure/file.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test",
            content="def test(): pass",
            start_line=1,
            end_line=2,
        )
        result = SearchResult(chunk=chunk, score=0.9)

        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = [result]

        table = search._build_results_table()
        assert table.row_count == 1
        # Table should be built without error for long paths

    def test_build_help_panel(self, mock_vector_store: MagicMock) -> None:
        """_build_help_panel should create panel with keyboard shortcuts."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        panel = search._build_help_panel()

        assert panel.title == "Keyboard Shortcuts"
        assert panel.border_style == "dim"

    def test_build_preview_panel_without_docstring(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Preview panel should work without docstring."""
        chunk = CodeChunk(
            id="test-chunk",
            file_path="src/test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test_function",
            content="def test(): pass",
            start_line=1,
            end_line=2,
            docstring=None,  # No docstring
        )
        result = SearchResult(chunk=chunk, score=0.9)

        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filtered_results = [result]
        search._state.selected_index = 0

        panel = search._build_preview_panel()
        assert panel is not None
        assert "src/test.py" in panel.title

    def test_build_input_prompt_search_mode(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Input prompt should show search mode with query."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "search"
        search._state.query = "test query"

        panel = search._build_input_prompt()
        assert panel.border_style == "cyan"

    def test_build_input_prompt_filter_language_mode(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Input prompt should show language filter mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_language"

        panel = search._build_input_prompt()
        assert panel.border_style == "yellow"

    def test_build_input_prompt_filter_type_mode(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Input prompt should show type filter mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_type"

        panel = search._build_input_prompt()
        assert panel.border_style == "yellow"

    def test_build_input_prompt_filter_path_mode(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Input prompt should show path filter mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_path"

        panel = search._build_input_prompt()
        assert panel.border_style == "yellow"

    def test_build_input_prompt_filter_score_mode(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Input prompt should show score filter mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "filter_score"

        panel = search._build_input_prompt()
        assert panel.border_style == "yellow"

    def test_build_input_prompt_unknown_mode(
        self, mock_vector_store: MagicMock
    ) -> None:
        """Input prompt should default to search style for unknown mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.input_mode = "unknown_mode"

        panel = search._build_input_prompt()
        assert panel.border_style == "cyan"

    def test_build_layout_without_preview(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """_build_layout should create results-only layout when preview is off."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = sample_results
        search._state.show_preview = False

        layout = search._build_layout()
        assert layout is not None

    def test_build_layout_with_preview(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """_build_layout should create split layout when preview is on."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = sample_results
        search._state.selected_index = 0
        search._state.show_preview = True

        layout = search._build_layout()
        assert layout is not None

    def test_build_layout_with_error_message(
        self, mock_vector_store: MagicMock
    ) -> None:
        """_build_layout should handle error messages."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.error_message = "Test error"
        search._state.show_preview = False

        layout = search._build_layout()
        assert layout is not None

    def test_display_results_with_filters(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """display_results should show results table and filter panel."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = sample_results
        search._state.filters = SearchFilters(language="python")

        # Mock console.print
        search._console.print = MagicMock()

        search.display_results()

        # Should have called print at least twice (table + filters)
        assert search._console.print.call_count >= 2

    def test_display_results_without_filters(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """display_results should show only table when no filters active."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.query = "test"
        search._state.filtered_results = sample_results
        # No filters

        # Mock console.print
        search._console.print = MagicMock()

        search.display_results()

        # Should have called print once (only table)
        assert search._console.print.call_count == 1

    def test_display_preview(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """display_preview should show detailed preview of a result."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filtered_results = sample_results

        # Mock console.print
        search._console.print = MagicMock()

        search.display_preview(sample_results[0])

        assert search._console.print.called
        assert search._state.selected_index == 0

    def test_display_preview_result_not_in_filtered(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """display_preview should handle result not in filtered list."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        # Only include some results in filtered
        search._state.filtered_results = sample_results[:2]

        # Mock console.print
        search._console.print = MagicMock()

        # Try to preview a result not in filtered list
        search.display_preview(sample_results[3])

        # Should default to index 0
        assert search._state.selected_index == 0


# =============================================================================
# Interactive Run Tests
# =============================================================================


class TestInteractiveRun:
    """Tests for the interactive run method."""

    async def test_run_without_readchar(self, mock_vector_store: MagicMock) -> None:
        """run should print message when readchar is not installed."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Mock console.print
        search._console.print = MagicMock()

        # Make readchar import fail
        with patch.dict("sys.modules", {"readchar": None}):
            # Force reimport by clearing the cached import
            import importlib
            import sys
            if "readchar" in sys.modules:
                del sys.modules["readchar"]

            await search.run()

            # Should print warning about readchar
            print_calls = [str(call) for call in search._console.print.call_args_list]
            assert any("readchar" in call for call in print_calls)

    async def test_run_with_initial_query(
        self, mock_vector_store: MagicMock, sample_results: list[SearchResult]
    ) -> None:
        """run should execute initial query if provided."""
        mock_vector_store.search = AsyncMock(return_value=sample_results)
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"
        # Make readkey return 'q' immediately to quit
        mock_readchar.readkey = MagicMock(return_value="q")

        search._console.clear = MagicMock()
        search._console.print = MagicMock()

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            await search.run(initial_query="test")

            # Search should have been called with initial query
            mock_vector_store.search.assert_called()
            assert search._state.query == "test"

    async def test_run_keyboard_interrupt(
        self, mock_vector_store: MagicMock
    ) -> None:
        """run should handle KeyboardInterrupt gracefully."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"
        # Make readkey raise KeyboardInterrupt
        mock_readchar.readkey = MagicMock(side_effect=KeyboardInterrupt)

        search._console.clear = MagicMock()
        search._console.print = MagicMock()

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            # Should not raise, should exit gracefully
            await search.run()

            # Should have cleared console and printed end message
            search._console.clear.assert_called()

    async def test_run_filter_mode_branch(
        self, mock_vector_store: MagicMock
    ) -> None:
        """run should call _handle_filter_mode when in filter mode."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))

        # Track calls to understand execution flow
        call_count = [0]

        mock_readchar = MagicMock()
        mock_readchar.key.UP = "\x1b[A"
        mock_readchar.key.DOWN = "\x1b[B"
        mock_readchar.key.ENTER = "\r"
        mock_readchar.key.ESCAPE = "\x1b"

        # First call returns 'l' to switch to filter mode, then ESC to quit
        def readkey_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return "l"  # Switch to filter_language mode
            elif call_count[0] == 2:
                return mock_readchar.key.ESCAPE  # Return to search mode
            else:
                return "q"  # Quit

        mock_readchar.readkey = MagicMock(side_effect=readkey_side_effect)

        search._console.clear = MagicMock()
        search._console.print = MagicMock()

        with patch.dict("sys.modules", {"readchar": mock_readchar}):
            await search.run()

            # Should have made multiple readkey calls
            assert mock_readchar.readkey.call_count >= 2


# =============================================================================
# run_search Function Tests
# =============================================================================


class TestRunSearchFunction:
    """Additional tests for the run_search function."""

    async def test_run_search_non_interactive_with_query(
        self, tmp_path: Path
    ) -> None:
        """run_search should execute search and display results."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await run_search(
                        repo_path=repo_path,
                        query="test query",
                        interactive=False,
                    )

                    # Search should have been called
                    mock_store.search.assert_called()

    async def test_run_search_non_interactive_with_preview(
        self, tmp_path: Path
    ) -> None:
        """run_search should show preview when requested."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        chunk = CodeChunk(
            id="test",
            file_path="test.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test",
            content="def test(): pass",
            start_line=1,
            end_line=2,
        )
        results = [SearchResult(chunk=chunk, score=0.9)]

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=results)

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await run_search(
                        repo_path=repo_path,
                        query="test",
                        interactive=False,
                        show_preview=True,
                    )

                    # Should have printed multiple times (results + preview)
                    assert mock_console.print.call_count >= 2

    async def test_run_search_interactive_with_query(
        self, tmp_path: Path
    ) -> None:
        """run_search should run interactive mode with initial query."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    with patch(
                        "local_deepwiki.cli.interactive_search.InteractiveSearch.run"
                    ) as mock_run:
                        mock_run.return_value = None

                        await run_search(
                            repo_path=repo_path,
                            query="test",
                            interactive=True,
                        )

                        # Interactive run should have been called with initial query
                        mock_run.assert_called_once_with(initial_query="test")

    async def test_run_search_interactive_without_query(
        self, tmp_path: Path
    ) -> None:
        """run_search should run interactive mode without initial query."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    with patch(
                        "local_deepwiki.cli.interactive_search.InteractiveSearch.run"
                    ) as mock_run:
                        mock_run.return_value = None

                        await run_search(
                            repo_path=repo_path,
                            query=None,
                            interactive=True,
                        )

                        # Interactive run should have been called without query
                        mock_run.assert_called_once()

    async def test_run_search_with_all_filters(
        self, tmp_path: Path
    ) -> None:
        """run_search should pass all filters to search instance."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await run_search(
                        repo_path=repo_path,
                        query="test",
                        language="python",
                        chunk_type="function",
                        file_pattern="*.py",
                        min_score=0.5,
                        limit=10,
                        interactive=False,
                    )

                    # Search should have been called
                    mock_store.search.assert_called()


# =============================================================================
# CLI Main Function Tests
# =============================================================================


class TestMainFunction:
    """Tests for the main CLI entry point."""

    def test_main_with_valid_args(self, tmp_path: Path) -> None:
        """main should parse arguments and run search."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            coro.close()
            return None

        with patch("sys.argv", ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive"]):
            with patch("local_deepwiki.cli.interactive_search.asyncio.run", side_effect=close_coro) as mock_run:
                result = main()

                assert result == 0
                mock_run.assert_called_once()

    def test_main_invalid_min_score(self, tmp_path: Path) -> None:
        """main should error on invalid min_score."""
        from local_deepwiki.cli.interactive_search import main

        with patch("sys.argv", ["deepwiki-search", str(tmp_path), "--min-score", "1.5"]):
            with patch("sys.stderr"):
                result = main()
                assert result == 1

    def test_main_non_interactive_requires_query(self, tmp_path: Path) -> None:
        """main should error when non-interactive mode lacks query."""
        from local_deepwiki.cli.interactive_search import main

        with patch("sys.argv", ["deepwiki-search", str(tmp_path), "--no-interactive"]):
            with patch("sys.stderr"):
                result = main()
                assert result == 1

    def test_main_keyboard_interrupt(self, tmp_path: Path) -> None:
        """main should handle KeyboardInterrupt."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        with patch("sys.argv", ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive"]):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=KeyboardInterrupt,
            ):
                result = main()
                assert result == 130

    def test_main_exception(self, tmp_path: Path) -> None:
        """main should handle exceptions."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro_and_raise(coro):
            """Close coroutine then raise exception."""
            coro.close()
            raise Exception("Test error")

        with patch("sys.argv", ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive"]):
            with patch(
                "local_deepwiki.cli.interactive_search.asyncio.run",
                side_effect=close_coro_and_raise,
            ):
                with patch("sys.stderr"):
                    result = main()
                    assert result == 1

    def test_main_with_preview_flag(self, tmp_path: Path) -> None:
        """main should pass preview flag correctly."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        captured_coro = []

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            captured_coro.append(coro)
            coro.close()
            return None

        with patch("sys.argv", ["deepwiki-search", str(repo_path), "-q", "test", "--no-interactive", "-p"]):
            with patch("local_deepwiki.cli.interactive_search.asyncio.run", side_effect=close_coro):
                result = main()

                assert result == 0
                # Check that run was called with a coroutine
                assert len(captured_coro) == 1

    def test_main_with_all_filter_args(self, tmp_path: Path) -> None:
        """main should parse all filter arguments."""
        from local_deepwiki.cli.interactive_search import main

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            coro.close()
            return None

        with patch(
            "sys.argv",
            [
                "deepwiki-search",
                str(repo_path),
                "-q", "test",
                "-l", "python",
                "-t", "function",
                "-f", "*.py",
                "-s", "0.5",
                "--limit", "10",
                "--no-interactive",
            ],
        ):
            with patch("local_deepwiki.cli.interactive_search.asyncio.run", side_effect=close_coro) as mock_run:
                result = main()

                assert result == 0


# =============================================================================
# Module Entry Point Tests
# =============================================================================


class TestModuleEntryPoint:
    """Tests for __name__ == '__main__' execution."""

    def test_module_can_be_imported(self) -> None:
        """Module should be importable without side effects."""
        import importlib
        import local_deepwiki.cli.interactive_search as module

        # Reimporting should work
        importlib.reload(module)

    def test_main_called_when_run_as_script(self) -> None:
        """main should be callable."""
        from local_deepwiki.cli.interactive_search import main

        assert callable(main)

    def test_module_name_main_execution(self, tmp_path: Path) -> None:
        """Test module execution via runpy to cover if __name__ == '__main__' block."""
        import subprocess
        import sys

        # Create a minimal test repo structure
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        # Run the module with arguments to make it exit quickly with error
        # (non-interactive mode without query returns error code 1)
        result = subprocess.run(
            [sys.executable, "-m", "local_deepwiki.cli.interactive_search",
             str(repo_path), "--no-interactive"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tmp_path,
        )

        # The module should have executed (entry point was called)
        # Exit code 1 means the validation ran (query required for non-interactive)
        assert result.returncode == 1
        assert "query" in result.stderr.lower() or "required" in result.stderr.lower()
