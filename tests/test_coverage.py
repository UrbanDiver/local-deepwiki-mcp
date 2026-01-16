"""Tests for documentation coverage analysis."""

import pytest

from local_deepwiki.generators.coverage import (
    CoverageStats,
    FileCoverage,
    _get_coverage_emoji,
    _has_meaningful_docstring,
)


class TestCoverageStats:
    """Tests for CoverageStats dataclass."""

    def test_total_entities(self):
        """Test total_entities property."""
        stats = CoverageStats(
            total_classes=5,
            total_functions=10,
            total_methods=15,
        )
        assert stats.total_entities == 30

    def test_documented_entities(self):
        """Test documented_entities property."""
        stats = CoverageStats(
            documented_classes=3,
            documented_functions=8,
            documented_methods=12,
        )
        assert stats.documented_entities == 23

    def test_coverage_percent(self):
        """Test coverage_percent property."""
        stats = CoverageStats(
            total_classes=10,
            documented_classes=10,
            total_functions=10,
            documented_functions=5,
            total_methods=10,
            documented_methods=5,
        )
        # 20/30 = 66.67%
        assert 66.6 < stats.coverage_percent < 66.7

    def test_coverage_percent_empty(self):
        """Test coverage_percent with no entities."""
        stats = CoverageStats()
        assert stats.coverage_percent == 100.0


class TestFileCoverage:
    """Tests for FileCoverage dataclass."""

    def test_creates_with_defaults(self):
        """Test creating FileCoverage with defaults."""
        fc = FileCoverage(file_path="test.py")
        assert fc.file_path == "test.py"
        assert fc.stats.total_entities == 0
        assert fc.undocumented == []


class TestHasMeaningfulDocstring:
    """Tests for _has_meaningful_docstring function."""

    def test_returns_false_for_none(self):
        """Test returns False for None docstring."""
        assert _has_meaningful_docstring(None) is False

    def test_returns_false_for_empty(self):
        """Test returns False for empty string."""
        assert _has_meaningful_docstring("") is False

    def test_returns_false_for_short(self):
        """Test returns False for very short docstrings."""
        assert _has_meaningful_docstring("hi") is False
        assert _has_meaningful_docstring("test") is False

    def test_returns_true_for_meaningful(self):
        """Test returns True for meaningful docstrings."""
        assert _has_meaningful_docstring("This is a proper docstring.") is True
        assert _has_meaningful_docstring("Calculate the sum of two numbers.") is True

    def test_returns_false_for_placeholder(self):
        """Test returns False for placeholder docstrings."""
        assert _has_meaningful_docstring("TODO") is False
        assert _has_meaningful_docstring("FIXME") is False
        assert _has_meaningful_docstring("...") is False
        assert _has_meaningful_docstring("pass") is False


class TestGetCoverageEmoji:
    """Tests for _get_coverage_emoji function."""

    def test_green_for_high_coverage(self):
        """Test green emoji for 90%+ coverage."""
        assert _get_coverage_emoji(100) == "🟢"
        assert _get_coverage_emoji(95) == "🟢"
        assert _get_coverage_emoji(90) == "🟢"

    def test_yellow_for_good_coverage(self):
        """Test yellow emoji for 70-89% coverage."""
        assert _get_coverage_emoji(89) == "🟡"
        assert _get_coverage_emoji(75) == "🟡"
        assert _get_coverage_emoji(70) == "🟡"

    def test_orange_for_medium_coverage(self):
        """Test orange emoji for 50-69% coverage."""
        assert _get_coverage_emoji(69) == "🟠"
        assert _get_coverage_emoji(55) == "🟠"
        assert _get_coverage_emoji(50) == "🟠"

    def test_red_for_low_coverage(self):
        """Test red emoji for <50% coverage."""
        assert _get_coverage_emoji(49) == "🔴"
        assert _get_coverage_emoji(25) == "🔴"
        assert _get_coverage_emoji(0) == "🔴"
