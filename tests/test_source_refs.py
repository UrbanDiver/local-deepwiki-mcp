"""Tests for source_refs module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.generators.source_refs import (
    _format_file_entry,
    _relative_path,
    _strip_existing_source_refs,
    add_source_refs_sections,
    build_file_to_wiki_map,
    generate_source_refs_section,
)
from local_deepwiki.models import WikiPage, WikiPageStatus


class TestBuildFileToWikiMap:
    """Tests for build_file_to_wiki_map function."""

    def test_builds_correct_mapping(self):
        """Test that file paths are correctly mapped to wiki paths."""
        pages = [
            WikiPage(
                path="files/src/local_deepwiki/core/chunker.md",
                title="chunker",
                content="",
                generated_at=0,
            ),
            WikiPage(
                path="files/src/local_deepwiki/models.md",
                title="models",
                content="",
                generated_at=0,
            ),
            WikiPage(
                path="index.md",  # Should be ignored
                title="Overview",
                content="",
                generated_at=0,
            ),
        ]

        result = build_file_to_wiki_map(pages)

        assert result == {
            "src/local_deepwiki/core/chunker.py": "files/src/local_deepwiki/core/chunker.md",
            "src/local_deepwiki/models.py": "files/src/local_deepwiki/models.md",
        }

    def test_empty_pages(self):
        """Test with empty pages list."""
        result = build_file_to_wiki_map([])
        assert result == {}

    def test_with_wiki_path_scans_existing_files(self):
        """Test that wiki_path is scanned for existing file pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            # Create files directory structure
            files_dir = wiki_path / "files" / "src" / "module"
            files_dir.mkdir(parents=True)

            # Create existing wiki pages
            (files_dir / "parser.md").write_text("# Parser")
            (files_dir / "utils.md").write_text("# Utils")
            # Create an index file that should be skipped
            (files_dir / "index.md").write_text("# Index")

            # Pass empty pages list but with wiki_path
            result = build_file_to_wiki_map([], wiki_path=wiki_path)

            assert "src/module/parser.py" in result
            assert result["src/module/parser.py"] == "files/src/module/parser.md"
            assert "src/module/utils.py" in result
            assert result["src/module/utils.py"] == "files/src/module/utils.md"
            # Index files should be skipped
            assert "src/module/index.py" not in result

    def test_with_wiki_path_prioritizes_pages_list(self):
        """Test that pages list takes priority over scanned files."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="",
                generated_at=0,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            files_dir = wiki_path / "files" / "src"
            files_dir.mkdir(parents=True)
            # Create the same file on disk
            (files_dir / "parser.md").write_text("# Parser from disk")

            result = build_file_to_wiki_map(pages, wiki_path=wiki_path)

            # Should have entry from pages list (which was set first)
            assert result["src/parser.py"] == "files/src/parser.md"

    def test_with_wiki_path_nonexistent_directory(self):
        """Test with wiki_path that doesn't exist."""
        result = build_file_to_wiki_map([], wiki_path=Path("/nonexistent/path"))
        assert result == {}

    def test_with_wiki_path_no_files_directory(self):
        """Test with wiki_path that has no files subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            # Don't create files directory
            result = build_file_to_wiki_map([], wiki_path=wiki_path)
            assert result == {}


class TestRelativePath:
    """Tests for _relative_path function."""

    def test_same_directory(self):
        """Test relative path in same directory."""
        result = _relative_path(
            "files/src/local_deepwiki/core/chunker.md",
            "files/src/local_deepwiki/core/parser.md",
        )
        assert result == "parser.md"

    def test_parent_directory(self):
        """Test relative path to parent directory."""
        result = _relative_path(
            "files/src/local_deepwiki/core/chunker.md",
            "files/src/local_deepwiki/models.md",
        )
        assert result == "../models.md"

    def test_sibling_directory(self):
        """Test relative path to sibling directory."""
        result = _relative_path(
            "files/src/local_deepwiki/core/chunker.md",
            "files/src/local_deepwiki/generators/wiki.md",
        )
        assert result == "../generators/wiki.md"

    def test_root_to_nested(self):
        """Test relative path from root to nested."""
        result = _relative_path(
            "index.md",
            "files/src/local_deepwiki/models.md",
        )
        assert result == "files/src/local_deepwiki/models.md"


class TestGenerateSourceRefsSection:
    """Tests for generate_source_refs_section function."""

    def test_single_file_with_wiki_link(self):
        """Test generating section for single file with wiki page."""
        file_to_wiki = {
            "src/local_deepwiki/core/parser.py": "files/src/local_deepwiki/core/parser.md",
        }

        result = generate_source_refs_section(
            source_files=["src/local_deepwiki/core/parser.py"],
            current_wiki_path="files/src/local_deepwiki/core/chunker.md",
            file_to_wiki=file_to_wiki,
        )

        assert result is not None
        assert "## Relevant Source Files" in result
        assert "[`src/local_deepwiki/core/parser.py`](parser.md)" in result

    def test_single_file_no_wiki_page(self):
        """Test generating section for file without wiki page."""
        result = generate_source_refs_section(
            source_files=["src/utils.py"],
            current_wiki_path="files/src/main.md",
            file_to_wiki={},
        )

        assert result is not None
        assert "## Relevant Source Files" in result
        assert "`src/utils.py`" in result
        # Should not have a link
        assert "](src/utils.py)" not in result

    def test_multiple_files(self):
        """Test generating section for multiple files."""
        file_to_wiki = {
            "src/parser.py": "files/src/parser.md",
            "src/models.py": "files/src/models.md",
        }

        result = generate_source_refs_section(
            source_files=["src/parser.py", "src/models.py"],
            current_wiki_path="modules/src.md",
            file_to_wiki=file_to_wiki,
        )

        assert result is not None
        assert "## Relevant Source Files" in result
        assert "The following source files were used" in result
        assert "`src/parser.py`" in result
        assert "`src/models.py`" in result

    def test_empty_source_files(self):
        """Test that empty source files returns None."""
        result = generate_source_refs_section(
            source_files=[],
            current_wiki_path="index.md",
            file_to_wiki={},
        )

        assert result is None

    def test_max_items_limit(self):
        """Test that max_items limits the output."""
        source_files = [f"src/file{i}.py" for i in range(20)]

        result = generate_source_refs_section(
            source_files=source_files,
            current_wiki_path="index.md",
            file_to_wiki={},
            max_items=5,
        )

        assert result is not None
        assert "Showing 5 of 20 source files" in result
        # Count occurrences of file paths
        assert result.count("`src/file") == 5

    def test_skips_self_reference(self):
        """Test that current page is not linked to itself."""
        file_to_wiki = {
            "src/parser.py": "files/src/parser.md",
        }

        result = generate_source_refs_section(
            source_files=["src/parser.py"],
            current_wiki_path="files/src/parser.md",  # Same as wiki path
            file_to_wiki=file_to_wiki,
        )

        # Should still show the file, but without self-link
        assert result is not None
        assert "`src/parser.py`" in result
        # Should not have a link (no relative path)
        assert "](parser.md)" not in result


class TestAddSourceRefsSections:
    """Tests for add_source_refs_sections function."""

    def test_adds_sections_to_file_pages(self):
        """Test that sections are added to file documentation pages."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="# Parser\n\nContent here.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "files/src/parser.md": WikiPageStatus(
                path="files/src/parser.md",
                source_files=["src/parser.py"],
                source_hashes={"src/parser.py": "abc123"},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 1
        assert "## Relevant Source Files" in result[0].content
        assert "`src/parser.py`" in result[0].content

    def test_skips_index_pages(self):
        """Test that index pages are not modified."""
        pages = [
            WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview\n\nContent.",
                generated_at=0,
            ),
            WikiPage(
                path="files/index.md",
                title="Files",
                content="# Files\n\nFile listing.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "index.md": WikiPageStatus(
                path="index.md",
                source_files=["src/a.py", "src/b.py"],
                source_hashes={},
                content_hash="xyz",
                generated_at=0,
            ),
            "files/index.md": WikiPageStatus(
                path="files/index.md",
                source_files=["src/a.py"],
                source_hashes={},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 2
        # Neither should have Relevant Source Files section
        assert "## Relevant Source Files" not in result[0].content
        assert "## Relevant Source Files" not in result[1].content

    def test_inserts_before_see_also(self):
        """Test that section is inserted before See Also."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="# Parser\n\nContent here.\n\n## See Also\n\n- [chunker](chunker.md)",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "files/src/parser.md": WikiPageStatus(
                path="files/src/parser.md",
                source_files=["src/parser.py"],
                source_hashes={},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        content = result[0].content
        source_refs_pos = content.find("## Relevant Source Files")
        see_also_pos = content.find("## See Also")

        assert source_refs_pos < see_also_pos

    def test_handles_missing_status(self):
        """Test that pages without status are passed through."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="# Parser",
                generated_at=0,
            ),
        ]

        result = add_source_refs_sections(pages, {})

        assert len(result) == 1
        assert result[0].content == "# Parser"

    def test_adds_section_to_module_pages(self):
        """Test that sections are added to module pages."""
        pages = [
            WikiPage(
                path="modules/src.md",
                title="src module",
                content="# src Module\n\nContent.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "modules/src.md": WikiPageStatus(
                path="modules/src.md",
                source_files=["src/parser.py", "src/models.py", "src/config.py"],
                source_hashes={},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 1
        assert "## Relevant Source Files" in result[0].content
        assert "The following source files were used" in result[0].content
        assert "`src/parser.py`" in result[0].content
        assert "`src/models.py`" in result[0].content

    def test_adds_section_to_architecture_page(self):
        """Test that sections are added to architecture page."""
        pages = [
            WikiPage(
                path="architecture.md",
                title="Architecture",
                content="# Architecture\n\nContent.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "architecture.md": WikiPageStatus(
                path="architecture.md",
                source_files=["src/a.py", "src/b.py"],
                source_hashes={},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 1
        assert "## Relevant Source Files" in result[0].content


class TestStripExistingSourceRefs:
    """Tests for _strip_existing_source_refs function."""

    def test_no_source_refs_section(self):
        """Test content without source refs section is unchanged."""
        content = "# Title\n\nSome content here.\n\n## See Also\n\n- Link"
        result = _strip_existing_source_refs(content)
        assert result == content

    def test_strips_single_source_refs_section(self):
        """Test stripping a single source refs section."""
        content = """# Title

Some content.

## Relevant Source Files

- `src/parser.py`

## See Also

- Link"""
        result = _strip_existing_source_refs(content)
        assert "## Relevant Source Files" not in result
        assert "## See Also" in result
        assert "Some content." in result

    def test_strips_section_at_end(self):
        """Test stripping source refs section at end of content."""
        content = """# Title

Some content.

## Relevant Source Files

- `src/parser.py`
- `src/utils.py`"""
        result = _strip_existing_source_refs(content)
        assert "## Relevant Source Files" not in result
        assert "Some content." in result
        assert "`src/parser.py`" not in result

    def test_strips_multiple_source_refs_sections(self):
        """Test stripping multiple source refs sections (edge case)."""
        content = """# Title

First content.

## Relevant Source Files

- `src/first.py`

## Middle Section

Middle content.

## Relevant Source Files

- `src/second.py`

## See Also

- Final link"""
        result = _strip_existing_source_refs(content)
        # Both source refs sections should be removed
        assert result.count("## Relevant Source Files") == 0
        assert "## Middle Section" in result
        assert "## See Also" in result
        assert "First content." in result

    def test_preserves_surrounding_content(self):
        """Test that content before and after is preserved."""
        content = """# Title

Intro paragraph.

## Overview

Overview content.

## Relevant Source Files

- `src/parser.py`

## See Also

- [Link](url)"""
        result = _strip_existing_source_refs(content)
        assert "# Title" in result
        assert "Intro paragraph." in result
        assert "## Overview" in result
        assert "Overview content." in result
        assert "## See Also" in result
        assert "[Link](url)" in result
        assert "## Relevant Source Files" not in result


class TestFormatFileEntry:
    """Tests for _format_file_entry function."""

    def test_without_line_info(self):
        """Test formatting without line info."""
        result = _format_file_entry(
            file_path="src/parser.py",
            wiki_path=None,
            current_wiki_path="files/src/chunker.md",
            line_info=None,
        )
        assert result == "- `src/parser.py`"

    def test_with_line_info(self):
        """Test formatting with line info shows start-end range."""
        result = _format_file_entry(
            file_path="src/parser.py",
            wiki_path=None,
            current_wiki_path="files/src/chunker.md",
            line_info={"start_line": 42, "end_line": 150},
        )
        assert result == "- `src/parser.py:42-150`"

    def test_with_line_info_and_wiki_link(self):
        """Test formatting with line info and wiki link."""
        result = _format_file_entry(
            file_path="src/parser.py",
            wiki_path="files/src/parser.md",
            current_wiki_path="files/src/chunker.md",
            line_info={"start_line": 15, "end_line": 200},
        )
        assert result == "- [`src/parser.py:15-200`](parser.md)"

    def test_skips_self_link_with_line_info(self):
        """Test that self-reference doesn't include link even with line info."""
        result = _format_file_entry(
            file_path="src/parser.py",
            wiki_path="files/src/parser.md",
            current_wiki_path="files/src/parser.md",  # Same as wiki_path
            line_info={"start_line": 1, "end_line": 50},
        )
        # Should have line info but no link
        assert result == "- `src/parser.py:1-50`"
        assert "](parser.md)" not in result


class TestGenerateSourceRefsSectionWithLineInfo:
    """Tests for generate_source_refs_section with line info."""

    def test_single_file_with_line_info(self):
        """Test single file displays line numbers."""
        result = generate_source_refs_section(
            source_files=["src/parser.py"],
            current_wiki_path="files/src/chunker.md",
            file_to_wiki={},
            file_line_info={"src/parser.py": {"start_line": 42, "end_line": 150}},
        )

        assert result is not None
        assert "`src/parser.py:42-150`" in result

    def test_multiple_files_with_line_info(self):
        """Test multiple files each display their line numbers."""
        result = generate_source_refs_section(
            source_files=["src/parser.py", "src/models.py"],
            current_wiki_path="modules/src.md",
            file_to_wiki={},
            file_line_info={
                "src/parser.py": {"start_line": 10, "end_line": 100},
                "src/models.py": {"start_line": 5, "end_line": 50},
            },
        )

        assert result is not None
        assert "`src/parser.py:10-100`" in result
        assert "`src/models.py:5-50`" in result

    def test_partial_line_info(self):
        """Test that files without line info fallback gracefully."""
        result = generate_source_refs_section(
            source_files=["src/parser.py", "src/models.py"],
            current_wiki_path="modules/src.md",
            file_to_wiki={},
            file_line_info={
                "src/parser.py": {"start_line": 10, "end_line": 100},
                # src/models.py has no line info
            },
        )

        assert result is not None
        assert "`src/parser.py:10-100`" in result
        # models.py should appear without line numbers
        assert "`src/models.py`" in result
        assert "src/models.py:" not in result  # No colon (no line numbers)


class TestAddSourceRefsSectionsWithLineInfo:
    """Tests for add_source_refs_sections with line info in status."""

    def test_passes_line_info_to_section_generator(self):
        """Test that line info from status is used in generated section."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="# Parser\n\nContent here.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "files/src/parser.md": WikiPageStatus(
                path="files/src/parser.md",
                source_files=["src/parser.py"],
                source_hashes={"src/parser.py": "abc123"},
                source_line_info={"src/parser.py": {"start_line": 25, "end_line": 180}},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 1
        assert "## Relevant Source Files" in result[0].content
        assert "`src/parser.py:25-180`" in result[0].content

    def test_handles_empty_line_info(self):
        """Test that empty line info works (fallback to no line numbers)."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="# Parser\n\nContent.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "files/src/parser.md": WikiPageStatus(
                path="files/src/parser.md",
                source_files=["src/parser.py"],
                source_hashes={},
                source_line_info={},  # Empty
                content_hash="xyz",
                generated_at=0,
            ),
        }

        result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 1
        assert "## Relevant Source Files" in result[0].content
        assert "`src/parser.py`" in result[0].content
        # Should not have line numbers
        assert "src/parser.py:" not in result[0].content

    def test_page_unchanged_when_source_refs_none(self):
        """Test that page is unchanged when generate_source_refs_section returns None."""
        pages = [
            WikiPage(
                path="files/src/parser.md",
                title="parser",
                content="# Parser\n\nOriginal content.",
                generated_at=0,
            ),
        ]

        page_statuses = {
            "files/src/parser.md": WikiPageStatus(
                path="files/src/parser.md",
                source_files=["src/parser.py"],
                source_hashes={},
                content_hash="xyz",
                generated_at=0,
            ),
        }

        # Mock generate_source_refs_section to return None
        with patch(
            "local_deepwiki.generators.source_refs.generate_source_refs_section",
            return_value=None,
        ):
            result = add_source_refs_sections(pages, page_statuses)

        assert len(result) == 1
        assert result[0].content == "# Parser\n\nOriginal content."

    def test_with_wiki_path_parameter(self):
        """Test add_source_refs_sections with wiki_path to find existing pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            files_dir = wiki_path / "files" / "src"
            files_dir.mkdir(parents=True)
            # Create an existing wiki page on disk
            (files_dir / "utils.md").write_text("# Utils")

            pages = [
                WikiPage(
                    path="files/src/parser.md",
                    title="parser",
                    content="# Parser\n\nContent.",
                    generated_at=0,
                ),
            ]

            page_statuses = {
                "files/src/parser.md": WikiPageStatus(
                    path="files/src/parser.md",
                    source_files=["src/parser.py", "src/utils.py"],
                    source_hashes={},
                    content_hash="xyz",
                    generated_at=0,
                ),
            }

            result = add_source_refs_sections(pages, page_statuses, wiki_path=wiki_path)

            assert len(result) == 1
            content = result[0].content
            assert "## Relevant Source Files" in content
            # utils.py should have a link since it exists on disk
            assert "[`src/utils.py`](utils.md)" in content
