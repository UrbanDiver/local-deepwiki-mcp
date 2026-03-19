"""Tests for UI rendering, display, and formatting in InteractiveSearch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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

    def test_build_input_prompt_search_mode(self, mock_vector_store: MagicMock) -> None:
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
