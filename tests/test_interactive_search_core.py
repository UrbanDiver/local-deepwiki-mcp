"""Tests for core InteractiveSearch functionality, keyboard handling, and filter modes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.cli.interactive_search import (
    InteractiveSearch,
    SearchFilters,
    SearchState,
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
# InteractiveSearch Core Tests
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
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("Test error"))

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

    def test_build_filters_panel_with_filters(
        self, mock_vector_store: MagicMock
    ) -> None:
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

    def test_build_preview_panel_no_selection(
        self, mock_vector_store: MagicMock
    ) -> None:
        """_build_preview_panel should return None when no selection."""
        search = InteractiveSearch(mock_vector_store, Path("/test"))
        search._state.filtered_results = []

        panel = search._build_preview_panel()
        assert panel is None


# =============================================================================
# Keyboard Handling Tests
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

    async def test_run_keyboard_interrupt(self, mock_vector_store: MagicMock) -> None:
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

    async def test_run_filter_mode_branch(self, mock_vector_store: MagicMock) -> None:
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
