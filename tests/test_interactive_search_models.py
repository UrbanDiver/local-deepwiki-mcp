"""Tests for SearchFilters and SearchState data models."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from local_deepwiki.cli.interactive_search import (
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

    def test_apply_filters_resets_selection(
        self, sample_results: list[SearchResult]
    ) -> None:
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

    def test_move_selection_clamps_at_bounds(
        self, sample_results: list[SearchResult]
    ) -> None:
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
