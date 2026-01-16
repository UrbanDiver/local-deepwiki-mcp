"""Tests for glossary generation."""

import pytest

from local_deepwiki.generators.glossary import (
    EntityEntry,
    _get_brief_description,
    _get_wiki_link,
    group_entities_by_letter,
)


class TestEntityEntry:
    """Tests for EntityEntry dataclass."""

    def test_creates_function_entry(self):
        """Test creating a function entry."""
        entry = EntityEntry(
            name="my_function",
            entity_type="function",
            file_path="src/module.py",
        )
        assert entry.name == "my_function"
        assert entry.entity_type == "function"
        assert entry.parent_name is None

    def test_creates_method_entry_with_parent(self):
        """Test creating a method entry with parent class."""
        entry = EntityEntry(
            name="my_method",
            entity_type="method",
            file_path="src/module.py",
            parent_name="MyClass",
            docstring="A method docstring.",
        )
        assert entry.parent_name == "MyClass"
        assert entry.docstring == "A method docstring."


class TestGroupEntitiesByLetter:
    """Tests for group_entities_by_letter function."""

    def test_groups_alphabetically(self):
        """Test that entities are grouped by first letter."""
        entities = [
            EntityEntry("apple", "function", "a.py"),
            EntityEntry("apricot", "function", "a.py"),
            EntityEntry("banana", "class", "b.py"),
        ]
        grouped = group_entities_by_letter(entities)
        assert "A" in grouped
        assert "B" in grouped
        assert len(grouped["A"]) == 2
        assert len(grouped["B"]) == 1

    def test_case_insensitive_grouping(self):
        """Test that grouping is case-insensitive."""
        entities = [
            EntityEntry("Apple", "function", "a.py"),
            EntityEntry("apple", "function", "a.py"),
        ]
        grouped = group_entities_by_letter(entities)
        assert "A" in grouped
        assert len(grouped["A"]) == 2

    def test_non_alpha_grouped_under_hash(self):
        """Test that non-alphabetic names are grouped under #."""
        entities = [
            EntityEntry("_private", "function", "a.py"),
            EntityEntry("123func", "function", "a.py"),
            EntityEntry("__init__", "method", "a.py"),
        ]
        grouped = group_entities_by_letter(entities)
        assert "#" in grouped
        assert len(grouped["#"]) == 3

    def test_empty_list(self):
        """Test with empty entity list."""
        grouped = group_entities_by_letter([])
        assert grouped == {}


class TestGetWikiLink:
    """Tests for _get_wiki_link function."""

    def test_simple_path(self):
        """Test simple file path conversion."""
        result = _get_wiki_link("src/module.py")
        assert result == "files/src/module.md"

    def test_nested_path(self):
        """Test nested file path conversion."""
        result = _get_wiki_link("src/package/subpackage/module.py")
        assert result == "files/src/package/subpackage/module.md"


class TestGetBriefDescription:
    """Tests for _get_brief_description function."""

    def test_returns_empty_for_none(self):
        """Test returns empty string for None docstring."""
        assert _get_brief_description(None) == ""

    def test_returns_first_line(self):
        """Test returns first line of docstring."""
        docstring = "This is the first line.\n\nMore details here."
        result = _get_brief_description(docstring)
        assert result == "This is the first line."

    def test_truncates_long_description(self):
        """Test truncates descriptions longer than max_length."""
        docstring = "This is a very long description that should be truncated for display."
        result = _get_brief_description(docstring, max_length=30)
        assert len(result) == 30
        assert result.endswith("...")

    def test_filters_out_args_section(self):
        """Test filters out docstrings starting with Args:."""
        docstring = "Args: param1, param2"
        result = _get_brief_description(docstring)
        assert result == ""

    def test_filters_out_returns_section(self):
        """Test filters out docstrings starting with Returns:."""
        docstring = "Returns: Some value"
        result = _get_brief_description(docstring)
        assert result == ""
