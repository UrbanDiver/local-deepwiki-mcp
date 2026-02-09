"""Tests for export.shared module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from local_deepwiki.export.shared import (
    build_breadcrumb,
    extract_title,
    render_toc,
    render_toc_entry,
)


class TestExtractTitle:
    """Tests for extract_title function."""

    def test_extract_from_h1_heading(self, tmp_path):
        """Test extracting title from # heading."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Main Title\n\nContent here")

        title = extract_title(md_file)
        assert title == "Main Title"

    def test_extract_from_bold_line(self, tmp_path):
        """Test extracting title from **bold** line."""
        md_file = tmp_path / "test.md"
        md_file.write_text("**Bold Title**\n\nContent here")

        title = extract_title(md_file)
        assert title == "Bold Title"

    def test_extract_with_whitespace(self, tmp_path):
        """Test extracting title with surrounding whitespace."""
        md_file = tmp_path / "test.md"
        md_file.write_text("  #  Spaced Title  \n\nContent")

        title = extract_title(md_file)
        assert title == "Spaced Title"

    def test_extract_first_heading(self, tmp_path):
        """Test that first heading is extracted, not later ones."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# First Title\n\n## Second Title\n\nContent")

        title = extract_title(md_file)
        assert title == "First Title"

    def test_fallback_to_filename(self, tmp_path):
        """Test fallback to filename when no heading found."""
        md_file = tmp_path / "my_test_file.md"
        md_file.write_text("Just some content without headings")

        title = extract_title(md_file)
        assert title == "My Test File"

    def test_fallback_with_hyphens(self, tmp_path):
        """Test filename fallback replaces hyphens."""
        md_file = tmp_path / "my-test-file.md"
        md_file.write_text("Content")

        title = extract_title(md_file)
        assert title == "My Test File"

    def test_empty_file(self, tmp_path):
        """Test extracting title from empty file."""
        md_file = tmp_path / "empty.md"
        md_file.write_text("")

        title = extract_title(md_file)
        assert title == "Empty"

    def test_file_read_error(self, tmp_path):
        """Test handling of file read errors."""
        md_file = tmp_path / "error_file.md"

        # Mock read_text to raise OSError
        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            title = extract_title(md_file)
            # Should fallback to filename
            assert title == "Error File"

    def test_unicode_decode_error(self, tmp_path):
        """Test handling of unicode decode errors."""
        md_file = tmp_path / "binary.md"
        md_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8

        title = extract_title(md_file)
        # Should fallback to filename
        assert title == "Binary"

    def test_heading_with_special_chars(self, tmp_path):
        """Test extracting title with special characters."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title with: special! chars?")

        title = extract_title(md_file)
        assert title == "Title with: special! chars?"

    def test_bold_incomplete(self, tmp_path):
        """Test that incomplete bold syntax is not matched."""
        md_file = tmp_path / "test.md"
        md_file.write_text("**Not closed\n\nContent")

        title = extract_title(md_file)
        assert title == "Test"  # Falls back to filename

    def test_multiple_bold_lines(self, tmp_path):
        """Test that first bold line is used."""
        md_file = tmp_path / "test.md"
        md_file.write_text("**First Bold**\n\n**Second Bold**")

        title = extract_title(md_file)
        assert title == "First Bold"

    def test_heading_after_content(self, tmp_path):
        """Test that heading is found even after blank lines."""
        md_file = tmp_path / "test.md"
        md_file.write_text("\n\n\n# Late Title\n\nContent")

        title = extract_title(md_file)
        assert title == "Late Title"


class TestRenderTocEntry:
    """Tests for render_toc_entry function."""

    def test_simple_entry_with_path(self):
        """Test rendering a simple entry with a path."""
        entry = {
            "number": "1",
            "title": "Introduction",
            "path": "index.md",
            "children": [],
        }

        html = render_toc_entry(entry, current_path="", root_path="")

        assert '<a href="index.html"' in html
        assert "Introduction" in html
        assert '<span class="toc-number">1</span>' in html

    def test_entry_with_active_class(self):
        """Test that active class is added for current page."""
        entry = {
            "number": "1",
            "title": "Current Page",
            "path": "current.md",
            "children": [],
        }

        html = render_toc_entry(entry, current_path="current.md", root_path="")

        assert 'class="active"' in html

    def test_entry_without_active_class(self):
        """Test that active class is not added for other pages."""
        entry = {
            "number": "1",
            "title": "Other Page",
            "path": "other.md",
            "children": [],
        }

        html = render_toc_entry(entry, current_path="current.md", root_path="")

        assert 'class="active"' not in html

    def test_entry_with_root_path(self):
        """Test rendering with root path prefix."""
        entry = {
            "number": "1",
            "title": "Page",
            "path": "page.md",
            "children": [],
        }

        html = render_toc_entry(entry, current_path="", root_path="../")

        assert 'href="../page.html"' in html

    def test_entry_without_path(self):
        """Test rendering entry without path (grouping label)."""
        entry = {
            "number": "1",
            "title": "Section",
            "children": [],
        }

        html = render_toc_entry(entry, current_path="", root_path="")

        assert "<a href=" not in html
        assert "Section" in html
        assert '<span class="toc-parent">' in html

    def test_entry_with_children(self):
        """Test rendering entry with nested children."""
        entry = {
            "number": "1",
            "title": "Parent",
            "path": "parent.md",
            "children": [
                {"number": "1.1", "title": "Child", "path": "child.md", "children": []},
            ],
        }

        html = render_toc_entry(entry, current_path="", root_path="")

        assert "Parent" in html
        assert "Child" in html
        assert '<div class="toc-nested">' in html

    def test_entry_with_deep_nesting(self):
        """Test rendering deeply nested entries."""
        entry = {
            "number": "1",
            "title": "Level 1",
            "path": "l1.md",
            "children": [
                {
                    "number": "1.1",
                    "title": "Level 2",
                    "path": "l2.md",
                    "children": [
                        {
                            "number": "1.1.1",
                            "title": "Level 3",
                            "path": "l3.md",
                            "children": [],
                        },
                    ],
                },
            ],
        }

        html = render_toc_entry(entry, current_path="", root_path="")

        assert "Level 1" in html
        assert "Level 2" in html
        assert "Level 3" in html
        assert html.count('<div class="toc-nested">') == 2

    def test_parent_class_added(self):
        """Test that toc-parent class is added when entry has children."""
        entry = {
            "number": "1",
            "title": "Parent",
            "path": "parent.md",
            "children": [
                {"number": "1.1", "title": "Child", "path": "child.md", "children": []},
            ],
        }

        html = render_toc_entry(entry, current_path="", root_path="")

        assert 'class="toc-item toc-parent"' in html


class TestRenderToc:
    """Tests for render_toc function."""

    def test_empty_toc(self):
        """Test rendering empty TOC."""
        html = render_toc([], current_path="", root_path="")
        assert html == ""

    def test_single_entry(self):
        """Test rendering TOC with single entry."""
        entries = [
            {"number": "1", "title": "Page", "path": "page.md", "children": []},
        ]

        html = render_toc(entries, current_path="", root_path="")

        assert "Page" in html
        assert "page.html" in html

    def test_multiple_entries(self):
        """Test rendering TOC with multiple entries."""
        entries = [
            {"number": "1", "title": "Page 1", "path": "page1.md", "children": []},
            {"number": "2", "title": "Page 2", "path": "page2.md", "children": []},
            {"number": "3", "title": "Page 3", "path": "page3.md", "children": []},
        ]

        html = render_toc(entries, current_path="", root_path="")

        assert "Page 1" in html
        assert "Page 2" in html
        assert "Page 3" in html

    def test_hierarchical_toc(self):
        """Test rendering hierarchical TOC."""
        entries = [
            {
                "number": "1",
                "title": "Section 1",
                "path": "s1.md",
                "children": [
                    {
                        "number": "1.1",
                        "title": "Sub 1.1",
                        "path": "s1-1.md",
                        "children": [],
                    },
                    {
                        "number": "1.2",
                        "title": "Sub 1.2",
                        "path": "s1-2.md",
                        "children": [],
                    },
                ],
            },
            {
                "number": "2",
                "title": "Section 2",
                "path": "s2.md",
                "children": [],
            },
        ]

        html = render_toc(entries, current_path="", root_path="")

        assert "Section 1" in html
        assert "Sub 1.1" in html
        assert "Sub 1.2" in html
        assert "Section 2" in html


class TestBuildBreadcrumb:
    """Tests for build_breadcrumb function."""

    def test_root_page_no_breadcrumb(self, tmp_path):
        """Test that root pages don't get breadcrumbs."""
        rel_path = Path("index.md")
        breadcrumb = build_breadcrumb(rel_path, "", tmp_path)

        assert breadcrumb == ""

    def test_single_level_page(self, tmp_path):
        """Test breadcrumb for a single-level nested page."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "Home" in breadcrumb
        assert "Auth" in breadcrumb

    def test_breadcrumb_with_root_path(self, tmp_path):
        """Test breadcrumb with root path prefix."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "../", wiki_path)

        assert 'href="../index.html"' in breadcrumb

    def test_breadcrumb_with_index_in_folder(self, tmp_path):
        """Test breadcrumb when folder has index.md."""
        rel_path = Path("modules/auth/service.md")
        wiki_path = tmp_path
        (wiki_path / "modules" / "auth").mkdir(parents=True)
        (wiki_path / "modules" / "index.md").touch()
        (wiki_path / "modules" / "auth" / "index.md").touch()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "Home" in breadcrumb
        assert "Modules" in breadcrumb
        assert "Auth" in breadcrumb
        assert "Service" in breadcrumb
        # Should have links for folders with index.md
        assert "modules/index.html" in breadcrumb
        assert "modules/auth/index.html" in breadcrumb

    def test_breadcrumb_without_folder_index(self, tmp_path):
        """Test breadcrumb when folder doesn't have index.md."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        # Modules should not be a link
        assert "<a href=" in breadcrumb  # Home link
        assert "Modules" in breadcrumb
        # But Modules should not have a link since no index.md
        assert "modules/index.html" not in breadcrumb

    def test_breadcrumb_deep_nesting(self, tmp_path):
        """Test breadcrumb with deep nesting."""
        rel_path = Path("a/b/c/d/page.md")
        wiki_path = tmp_path
        (wiki_path / "a" / "b" / "c" / "d").mkdir(parents=True)

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "Home" in breadcrumb
        assert "A" in breadcrumb
        assert "B" in breadcrumb
        assert "C" in breadcrumb
        assert "D" in breadcrumb
        assert "Page" in breadcrumb

    def test_breadcrumb_current_page_styling(self, tmp_path):
        """Test that current page has special styling."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert '<span class="current">Auth</span>' in breadcrumb

    def test_breadcrumb_separator(self, tmp_path):
        """Test that breadcrumb has separators."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "&rsaquo;" in breadcrumb

    def test_breadcrumb_title_casing(self, tmp_path):
        """Test that breadcrumb items are title-cased."""
        rel_path = Path("my_module/my_page.md")
        wiki_path = tmp_path
        (wiki_path / "my_module").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "My Module" in breadcrumb
        assert "My Page" in breadcrumb

    def test_breadcrumb_hyphen_replacement(self, tmp_path):
        """Test that hyphens are replaced with spaces."""
        rel_path = Path("my-module/my-page.md")
        wiki_path = tmp_path
        (wiki_path / "my-module").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "My Module" in breadcrumb
        assert "My Page" in breadcrumb

    def test_breadcrumb_removes_md_extension(self, tmp_path):
        """Test that .md extension is removed from current page."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert "Auth" in breadcrumb
        assert "Auth.md" not in breadcrumb

    def test_breadcrumb_wrapping_div(self, tmp_path):
        """Test that breadcrumb is wrapped in proper div."""
        rel_path = Path("modules/auth.md")
        wiki_path = tmp_path
        (wiki_path / "modules").mkdir()

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        assert '<div class="breadcrumb">' in breadcrumb
        assert breadcrumb.endswith("</div>")

    def test_breadcrumb_multiple_levels_with_mixed_indices(self, tmp_path):
        """Test breadcrumb with some folders having index.md and others not."""
        rel_path = Path("a/b/c/page.md")
        wiki_path = tmp_path
        (wiki_path / "a" / "b" / "c").mkdir(parents=True)
        (wiki_path / "a" / "index.md").touch()  # Only a has index
        # b and c don't have index.md

        breadcrumb = build_breadcrumb(rel_path, "", wiki_path)

        # A should be a link, B and C should not
        assert "a/index.html" in breadcrumb
        assert "b/index.html" not in breadcrumb
        assert "c/index.html" not in breadcrumb
