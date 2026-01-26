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
