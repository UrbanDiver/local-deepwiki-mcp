"""Data models for interactive search CLI.

Pure data definitions: constants, filters, and state for the search interface.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

from local_deepwiki.models import SearchResult


# Language extension to Pygments lexer mapping
LANGUAGE_LEXERS = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
    "go": "go",
    "rust": "rust",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "swift": "swift",
    "ruby": "ruby",
    "php": "php",
    "kotlin": "kotlin",
    "csharp": "csharp",
}


@dataclass
class SearchFilters:
    """Filters to apply to search results."""

    language: str | None = None
    chunk_type: str | None = None  # function, class, method, etc.
    file_pattern: str | None = None
    min_similarity: float = 0.0

    def matches(self, result: SearchResult) -> bool:
        """Check if a result matches all active filters.

        Args:
            result: The search result to check.

        Returns:
            True if the result passes all filters.
        """
        # Check language filter
        if self.language and result.chunk.language.value != self.language:
            return False

        # Check chunk type filter
        if self.chunk_type and result.chunk.chunk_type.value != self.chunk_type:
            return False

        # Check file pattern filter
        if self.file_pattern:
            if not fnmatch.fnmatch(result.chunk.file_path, self.file_pattern):
                return False

        # Check minimum similarity
        if result.score < self.min_similarity:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert filters to a dictionary for display.

        Returns:
            Dictionary of active filters.
        """
        active = {}
        if self.language:
            active["language"] = self.language
        if self.chunk_type:
            active["type"] = self.chunk_type
        if self.file_pattern:
            active["path"] = self.file_pattern
        if self.min_similarity > 0:
            active["min_score"] = f"{self.min_similarity:.2f}"
        return active

    def clear(self) -> None:
        """Clear all filters."""
        self.language = None
        self.chunk_type = None
        self.file_pattern = None
        self.min_similarity = 0.0


@dataclass
class SearchState:
    """Current state of the interactive search session."""

    query: str = ""
    results: list[SearchResult] = field(default_factory=list)
    filtered_results: list[SearchResult] = field(default_factory=list)
    selected_index: int = 0
    filters: SearchFilters = field(default_factory=SearchFilters)
    show_preview: bool = False
    preview_context_lines: int = 3
    input_mode: str = (
        "search"  # search, filter_language, filter_type, filter_path, filter_score
    )
    error_message: str | None = None
    search_complete: bool = False

    def apply_filters(self) -> None:
        """Apply current filters to results."""
        self.filtered_results = [r for r in self.results if self.filters.matches(r)]
        # Reset selection if it's out of bounds
        if self.selected_index >= len(self.filtered_results):
            self.selected_index = max(0, len(self.filtered_results) - 1)

    def move_selection(self, delta: int) -> None:
        """Move the selection by delta positions.

        Args:
            delta: Number of positions to move (positive = down, negative = up).
        """
        if not self.filtered_results:
            return
        self.selected_index = max(
            0, min(len(self.filtered_results) - 1, self.selected_index + delta)
        )

    def get_selected_result(self) -> SearchResult | None:
        """Get the currently selected search result.

        Returns:
            The selected result, or None if no results.
        """
        if not self.filtered_results or self.selected_index >= len(
            self.filtered_results
        ):
            return None
        return self.filtered_results[self.selected_index]
