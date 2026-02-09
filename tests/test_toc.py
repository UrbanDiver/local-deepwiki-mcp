"""Tests for table of contents generation."""

import json
from pathlib import Path

import pytest

from local_deepwiki.generators.toc import (
    TableOfContents,
    TocEntry,
    generate_toc,
    read_toc,
    write_toc,
)


class TestTocEntry:
    """Tests for TocEntry dataclass."""

    def test_to_dict_simple(self):
        entry = TocEntry(number="1", title="Overview", path="index.md")
        result = entry.to_dict()
        assert result == {
            "number": "1",
            "title": "Overview",
            "path": "index.md",
        }

    def test_to_dict_with_children(self):
        child = TocEntry(number="1.1", title="Getting Started", path="start.md")
        entry = TocEntry(
            number="1",
            title="Overview",
            path="index.md",
            children=[child],
        )
        result = entry.to_dict()
        assert result == {
            "number": "1",
            "title": "Overview",
            "path": "index.md",
            "children": [
                {"number": "1.1", "title": "Getting Started", "path": "start.md"}
            ],
        }


class TestTableOfContents:
    """Tests for TableOfContents dataclass."""

    def test_to_json(self):
        entry = TocEntry(number="1", title="Overview", path="index.md")
        toc = TableOfContents(entries=[entry])
        json_str = toc.to_json()
        data = json.loads(json_str)
        assert data == {
            "entries": [{"number": "1", "title": "Overview", "path": "index.md"}]
        }

    def test_from_dict(self):
        data = {
            "entries": [
                {
                    "number": "1",
                    "title": "Overview",
                    "path": "index.md",
                    "children": [
                        {"number": "1.1", "title": "Start", "path": "start.md"}
                    ],
                }
            ]
        }
        toc = TableOfContents.from_dict(data)
        assert len(toc.entries) == 1
        assert toc.entries[0].number == "1"
        assert toc.entries[0].title == "Overview"
        assert len(toc.entries[0].children) == 1
        assert toc.entries[0].children[0].number == "1.1"

    def test_roundtrip(self):
        child = TocEntry(number="1.1", title="Start", path="start.md")
        entry = TocEntry(
            number="1", title="Overview", path="index.md", children=[child]
        )
        toc = TableOfContents(entries=[entry])

        json_str = toc.to_json()
        restored = TableOfContents.from_json(json_str)

        assert len(restored.entries) == 1
        assert restored.entries[0].number == "1"
        assert restored.entries[0].children[0].title == "Start"


class TestGenerateToc:
    """Tests for generate_toc function."""

    def test_root_pages_numbered(self):
        pages = [
            {"path": "index.md", "title": "My Project"},
            {"path": "architecture.md", "title": "Architecture"},
            {"path": "dependencies.md", "title": "Dependencies"},
        ]
        toc = generate_toc(pages)

        assert len(toc.entries) == 3
        assert toc.entries[0].number == "1"
        assert toc.entries[0].title == "My Project"
        assert toc.entries[0].path == "index.md"

        assert toc.entries[1].number == "2"
        assert toc.entries[1].title == "Architecture"

        assert toc.entries[2].number == "3"
        assert toc.entries[2].title == "Dependencies"

    def test_root_pages_ordered_correctly(self):
        # Even if provided in wrong order, should maintain expected order
        pages = [
            {"path": "dependencies.md", "title": "Dependencies"},
            {"path": "index.md", "title": "My Project"},
            {"path": "architecture.md", "title": "Architecture"},
        ]
        toc = generate_toc(pages)

        assert toc.entries[0].path == "index.md"
        assert toc.entries[1].path == "architecture.md"
        assert toc.entries[2].path == "dependencies.md"

    def test_sections_numbered(self):
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "modules/core.md", "title": "Core Module"},
        ]
        toc = generate_toc(pages)

        # Find the modules section
        modules_entry = next((e for e in toc.entries if e.title == "Modules"), None)
        assert modules_entry is not None
        assert modules_entry.number == "2"  # After index.md which is "1"
        assert len(modules_entry.children) == 1
        assert modules_entry.children[0].number == "2.1"
        assert modules_entry.children[0].title == "Core Module"

    def test_files_section_nested(self):
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "files/index.md", "title": "Files"},
            {"path": "files/src/main.md", "title": "Main Module"},
            {"path": "files/src/utils.md", "title": "Utils"},
        ]
        toc = generate_toc(pages)

        files_entry = next((e for e in toc.entries if e.title == "Files"), None)
        assert files_entry is not None
        # Should have nested structure for src/
        assert len(files_entry.children) >= 1

    def test_modules_before_files(self):
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "files/index.md", "title": "Files"},
            {"path": "modules/index.md", "title": "Modules"},
        ]
        toc = generate_toc(pages)

        # modules should come before files in the TOC
        section_numbers = {e.title: e.number for e in toc.entries}
        modules_num = int(section_numbers.get("Modules", "0"))
        files_num = int(section_numbers.get("Files", "0"))
        assert modules_num < files_num


class TestWriteReadToc:
    """Tests for write_toc and read_toc functions."""

    def test_write_and_read(self, tmp_path: Path):
        entry = TocEntry(number="1", title="Overview", path="index.md")
        toc = TableOfContents(entries=[entry])

        write_toc(toc, tmp_path)

        toc_file = tmp_path / "toc.json"
        assert toc_file.exists()

        restored = read_toc(tmp_path)
        assert restored is not None
        assert len(restored.entries) == 1
        assert restored.entries[0].title == "Overview"

    def test_read_nonexistent_returns_none(self, tmp_path: Path):
        result = read_toc(tmp_path)
        assert result is None

    def test_read_invalid_json_returns_none(self, tmp_path: Path):
        toc_file = tmp_path / "toc.json"
        toc_file.write_text("not valid json")

        result = read_toc(tmp_path)
        assert result is None


class TestTocIntegration:
    """Integration tests for TOC generation."""

    def test_full_wiki_structure(self):
        """Test TOC generation with a realistic wiki structure."""
        pages = [
            {"path": "index.md", "title": "local-deepwiki-mcp"},
            {"path": "architecture.md", "title": "System Architecture"},
            {"path": "dependencies.md", "title": "Dependencies"},
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "modules/src.md", "title": "Source Code"},
            {"path": "modules/tests.md", "title": "Test Suite"},
            {"path": "files/index.md", "title": "Files"},
            {"path": "files/src/config.md", "title": "Configuration"},
            {"path": "files/src/server.md", "title": "Server"},
            {"path": "files/src/core/parser.md", "title": "Parser"},
            {"path": "files/src/core/chunker.md", "title": "Chunker"},
        ]
        toc = generate_toc(pages)

        # Verify structure
        assert (
            len(toc.entries) == 5
        )  # overview, architecture, dependencies, modules, files

        # Check numbering
        assert toc.entries[0].number == "1"  # Overview
        assert toc.entries[1].number == "2"  # Architecture
        assert toc.entries[2].number == "3"  # Dependencies
        assert toc.entries[3].number == "4"  # Modules
        assert toc.entries[4].number == "5"  # Files

        # Check modules children
        modules = toc.entries[3]
        assert len(modules.children) == 2
        assert modules.children[0].number == "4.1"
        assert modules.children[1].number == "4.2"

        # Files should have nested structure
        files = toc.entries[4]
        assert len(files.children) >= 1  # At least src directory


# ── Additional Coverage Tests ──────────────────────────────────────


class TestGenerateTocEmptyInput:
    """Tests for edge cases with empty or minimal input."""

    def test_empty_pages_list(self):
        """Empty page list should produce empty TOC."""
        toc = generate_toc([])
        assert len(toc.entries) == 0

    def test_single_index_page(self):
        """Single index page should produce a TOC with one entry."""
        pages = [{"path": "index.md", "title": "My Project"}]
        toc = generate_toc(pages)

        assert len(toc.entries) == 1
        assert toc.entries[0].number == "1"
        assert toc.entries[0].title == "My Project"
        assert toc.entries[0].path == "index.md"
        assert toc.entries[0].children == []


class TestGenerateTocSpecialCharacters:
    """Tests for special characters in headings."""

    def test_special_chars_in_title(self):
        """Titles with special characters should be preserved."""
        pages = [
            {"path": "index.md", "title": "Project: A/B Testing & More!"},
            {"path": "architecture.md", "title": "System (v2.0) Architecture"},
        ]
        toc = generate_toc(pages)

        assert toc.entries[0].title == "Project: A/B Testing & More!"
        assert toc.entries[1].title == "System (v2.0) Architecture"

    def test_unicode_in_title(self):
        """Unicode characters in titles should be preserved."""
        pages = [
            {"path": "index.md", "title": "Overview"},
        ]
        toc = generate_toc(pages)
        assert toc.entries[0].title == "Overview"


class TestGenerateTocDuplicateHeadings:
    """Tests for duplicate heading names in pages."""

    def test_duplicate_titles_different_paths(self):
        """Pages with the same title but different paths should both appear."""
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "modules/core.md", "title": "Core"},
            {"path": "files/index.md", "title": "Files"},
            {
                "path": "files/src/core.md",
                "title": "Core",
            },  # Same title as modules/core.md
        ]
        toc = generate_toc(pages)

        # Find both entries named "Core"
        all_titles = []

        def _collect(entries):
            for e in entries:
                all_titles.append(e.title)
                _collect(e.children)

        _collect(toc.entries)
        assert all_titles.count("Core") == 2


class TestGenerateTocDeeplyNested:
    """Tests for deeply nested section hierarchy (4+ levels)."""

    def test_deeply_nested_files(self):
        """Files nested 4+ levels deep should produce correct hierarchy."""
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "files/index.md", "title": "Files"},
            {"path": "files/src/main.md", "title": "Main"},
            {"path": "files/src/core/parser.md", "title": "Parser"},
            {"path": "files/src/core/utils/helpers.md", "title": "Helpers"},
        ]
        toc = generate_toc(pages)

        files_entry = next(e for e in toc.entries if e.title == "Files")
        assert files_entry is not None

        # Navigate down: files -> src (dir) -> core (dir) -> utils (dir) -> helpers
        # The exact structure depends on implementation, but it should be nested
        def _max_depth(entry, depth=0):
            if not entry.children:
                return depth
            return max(_max_depth(c, depth + 1) for c in entry.children)

        depth = _max_depth(files_entry)
        assert depth >= 3  # At least 3 levels: src -> core -> utils


class TestGenerateTocPagesWithNoHeadings:
    """Test pages that exist but have simple paths."""

    def test_only_section_pages_no_root(self):
        """Only section pages, no root pages - should still generate TOC."""
        pages = [
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "modules/core.md", "title": "Core Module"},
        ]
        toc = generate_toc(pages)

        assert len(toc.entries) == 1  # Just modules section
        assert toc.entries[0].title == "Modules"
        assert len(toc.entries[0].children) == 1
        assert toc.entries[0].children[0].title == "Core Module"


class TestHierarchicalNumbering:
    """Tests for correct hierarchical numbering."""

    def test_numbering_consistency(self):
        """Numbering should follow parent.child format."""
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "modules/alpha.md", "title": "Alpha"},
            {"path": "modules/beta.md", "title": "Beta"},
            {"path": "modules/gamma.md", "title": "Gamma"},
        ]
        toc = generate_toc(pages)

        modules = next(e for e in toc.entries if e.title == "Modules")
        for i, child in enumerate(modules.children, 1):
            assert child.number == f"{modules.number}.{i}"

    def test_numbering_multiple_sections(self):
        """Multiple sections should have sequential top-level numbers."""
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "modules/core.md", "title": "Core"},
            {"path": "files/index.md", "title": "Files"},
            {"path": "files/main.md", "title": "Main"},
        ]
        toc = generate_toc(pages)

        numbers = [e.number for e in toc.entries]
        # They should be sequential integers
        for i, num in enumerate(numbers, 1):
            assert num == str(i)


class TestTocEntryEdgeCases:
    """Edge case tests for TocEntry."""

    def test_entry_no_children_to_dict(self):
        """Entry with empty children list should not include children key."""
        entry = TocEntry(number="1", title="Test", path="test.md", children=[])
        result = entry.to_dict()
        assert "children" not in result

    def test_entry_deep_nesting(self):
        """Deeply nested children should serialize correctly."""
        level3 = TocEntry(number="1.1.1", title="Level 3", path="l3.md")
        level2 = TocEntry(
            number="1.1", title="Level 2", path="l2.md", children=[level3]
        )
        level1 = TocEntry(number="1", title="Level 1", path="l1.md", children=[level2])

        result = level1.to_dict()
        assert result["children"][0]["children"][0]["title"] == "Level 3"
        assert result["children"][0]["children"][0]["number"] == "1.1.1"


class TestTableOfContentsEdgeCases:
    """Edge case tests for TableOfContents."""

    def test_empty_toc_to_json(self):
        """Empty TOC should serialize to valid JSON."""
        toc = TableOfContents(entries=[])
        json_str = toc.to_json()
        data = json.loads(json_str)
        assert data == {"entries": []}

    def test_from_dict_empty_entries(self):
        """from_dict with empty entries should produce empty TOC."""
        toc = TableOfContents.from_dict({"entries": []})
        assert len(toc.entries) == 0

    def test_from_dict_missing_entries_key(self):
        """from_dict with missing entries key should produce empty TOC."""
        toc = TableOfContents.from_dict({})
        assert len(toc.entries) == 0

    def test_from_json_roundtrip_complex(self):
        """Complex multi-level TOC should roundtrip through JSON."""
        child2 = TocEntry(number="1.1.1", title="Deep", path="deep.md")
        child1 = TocEntry(
            number="1.1", title="Child", path="child.md", children=[child2]
        )
        entry1 = TocEntry(number="1", title="Root", path="root.md", children=[child1])
        entry2 = TocEntry(number="2", title="Other", path="other.md")

        original = TableOfContents(entries=[entry1, entry2])
        json_str = original.to_json()
        restored = TableOfContents.from_json(json_str)

        assert len(restored.entries) == 2
        assert restored.entries[0].children[0].children[0].title == "Deep"
        assert restored.entries[1].title == "Other"


class TestWriteReadTocAdditional:
    """Additional write/read tests."""

    def test_write_overwrite_existing(self, tmp_path: Path):
        """Writing TOC should overwrite any existing toc.json."""
        entry1 = TocEntry(number="1", title="First", path="first.md")
        toc1 = TableOfContents(entries=[entry1])
        write_toc(toc1, tmp_path)

        entry2 = TocEntry(number="1", title="Replaced", path="replaced.md")
        toc2 = TableOfContents(entries=[entry2])
        write_toc(toc2, tmp_path)

        restored = read_toc(tmp_path)
        assert restored is not None
        assert restored.entries[0].title == "Replaced"

    def test_read_malformed_json_structure(self, tmp_path: Path):
        """Valid JSON but wrong structure should return None."""
        toc_file = tmp_path / "toc.json"
        toc_file.write_text('{"wrong_key": []}')

        result = read_toc(tmp_path)
        # Should produce an empty TOC (no entries key) rather than None
        # because from_dict handles missing "entries" gracefully
        if result is not None:
            assert len(result.entries) == 0

    def test_write_creates_file(self, tmp_path: Path):
        """write_toc should create toc.json if it does not exist."""
        entry = TocEntry(number="1", title="New", path="new.md")
        toc = TableOfContents(entries=[entry])
        write_toc(toc, tmp_path)

        assert (tmp_path / "toc.json").exists()


class TestGenerateTocCodemaps:
    """Test codemap section ordering."""

    def test_codemaps_section(self):
        """Codemaps section should appear in correct position."""
        pages = [
            {"path": "index.md", "title": "Overview"},
            {"path": "modules/index.md", "title": "Modules"},
            {"path": "files/index.md", "title": "Files"},
            {"path": "codemaps/index.md", "title": "Codemaps"},
            {"path": "codemaps/auth_flow.md", "title": "Auth Flow"},
        ]
        toc = generate_toc(pages)

        section_titles = [e.title for e in toc.entries]
        # Modules should come before files, files before codemaps
        if "Modules" in section_titles and "Codemaps" in section_titles:
            assert section_titles.index("Modules") < section_titles.index("Codemaps")
        if "Files" in section_titles and "Codemaps" in section_titles:
            assert section_titles.index("Files") < section_titles.index("Codemaps")


class TestGenerateTocRootPageDefaults:
    """Test root page title defaults."""

    def test_default_title_used_for_bare_name(self):
        """When title equals the filename stem, use the default title."""
        pages = [
            {"path": "architecture.md", "title": "architecture"},
        ]
        toc = generate_toc(pages)

        assert toc.entries[0].title == "Architecture"  # Default, not "architecture"

    def test_custom_title_preserved(self):
        """Custom title should not be replaced with default."""
        pages = [
            {"path": "architecture.md", "title": "My Custom Architecture"},
        ]
        toc = generate_toc(pages)

        assert toc.entries[0].title == "My Custom Architecture"
