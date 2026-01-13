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
            "children": [{"number": "1.1", "title": "Getting Started", "path": "start.md"}],
        }


class TestTableOfContents:
    """Tests for TableOfContents dataclass."""

    def test_to_json(self):
        entry = TocEntry(number="1", title="Overview", path="index.md")
        toc = TableOfContents(entries=[entry])
        json_str = toc.to_json()
        data = json.loads(json_str)
        assert data == {"entries": [{"number": "1", "title": "Overview", "path": "index.md"}]}

    def test_from_dict(self):
        data = {
            "entries": [
                {
                    "number": "1",
                    "title": "Overview",
                    "path": "index.md",
                    "children": [{"number": "1.1", "title": "Start", "path": "start.md"}],
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
        entry = TocEntry(number="1", title="Overview", path="index.md", children=[child])
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
        assert len(toc.entries) == 5  # overview, architecture, dependencies, modules, files

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
