"""Tests for source_refs module."""

import pytest

from local_deepwiki.generators.source_refs import (
    add_source_refs_sections,
    build_file_to_wiki_map,
    generate_source_refs_section,
    _format_file_entry,
    _relative_path,
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
