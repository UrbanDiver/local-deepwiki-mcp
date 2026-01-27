"""Tests for HTML export functionality."""

import json
import runpy
import sys
from pathlib import Path
from unittest import mock

import pytest

from local_deepwiki.export.html import HtmlExporter, export_to_html, extract_title, main, render_markdown


class TestRenderMarkdown:
    """Tests for markdown rendering."""

    def test_basic_markdown(self):
        """Test basic markdown conversion."""
        md = "# Hello\n\nThis is a paragraph."
        html = render_markdown(md)
        assert "<h1" in html  # h1 tag (may have id attribute)
        assert "Hello" in html
        assert "<p>" in html

    def test_code_blocks(self):
        """Test fenced code blocks."""
        md = "```python\ndef hello():\n    pass\n```"
        html = render_markdown(md)
        assert "<code" in html
        assert "def hello" in html

    def test_tables(self):
        """Test markdown tables."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = render_markdown(md)
        assert "<table>" in html
        assert "<th>" in html
        assert "<td>" in html

    def test_mermaid_blocks(self):
        """Test mermaid code blocks are preserved."""
        md = "```mermaid\ngraph TD\nA-->B\n```"
        html = render_markdown(md)
        # Should be in a code block with mermaid class
        assert "language-mermaid" in html


class TestExtractTitle:
    """Tests for title extraction."""

    def test_h1_title(self, tmp_path: Path):
        """Test extracting H1 title."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# My Title\n\nContent here.")
        assert extract_title(md_file) == "My Title"

    def test_bold_title(self, tmp_path: Path):
        """Test extracting bold title."""
        md_file = tmp_path / "test.md"
        md_file.write_text("**Bold Title**\n\nContent here.")
        assert extract_title(md_file) == "Bold Title"

    def test_fallback_to_filename(self, tmp_path: Path):
        """Test fallback to filename when no title found."""
        md_file = tmp_path / "my_test_file.md"
        md_file.write_text("Just some content without a title.")
        assert extract_title(md_file) == "My Test File"

    def test_oserror_fallback_to_filename(self, tmp_path: Path):
        """Test fallback to filename when OSError occurs (e.g., permission denied)."""
        md_file = tmp_path / "unreadable_file.md"
        # Create a file that doesn't exist to trigger OSError
        non_existent = tmp_path / "does_not_exist.md"
        assert extract_title(non_existent) == "Does Not Exist"

    def test_unicode_decode_error_fallback(self, tmp_path: Path):
        """Test fallback to filename when UnicodeDecodeError occurs."""
        md_file = tmp_path / "binary_file.md"
        # Write binary content that can't be decoded as UTF-8
        md_file.write_bytes(b"\xff\xfe\x00\x01invalid utf-8 \x80\x81\x82")
        assert extract_title(md_file) == "Binary File"


class TestHtmlExporter:
    """Tests for HtmlExporter class."""

    @pytest.fixture
    def sample_wiki(self, tmp_path: Path) -> Path:
        """Create a sample wiki structure for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create index.md
        (wiki_path / "index.md").write_text("# Overview\n\nWelcome to the wiki.")

        # Create architecture.md
        (wiki_path / "architecture.md").write_text("# Architecture\n\nSystem design.")

        # Create modules directory
        modules_dir = wiki_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "index.md").write_text("# Modules\n\nModule overview.")
        (modules_dir / "core.md").write_text("# Core Module\n\nCore functionality.")

        # Create toc.json
        toc = {
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
                {
                    "number": "3",
                    "title": "Modules",
                    "path": "modules/index.md",
                    "children": [
                        {"number": "3.1", "title": "Core Module", "path": "modules/core.md"}
                    ],
                },
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        # Create search.json
        search_index = [
            {"title": "Overview", "path": "index.md", "snippet": "Welcome to the wiki."},
            {"title": "Architecture", "path": "architecture.md", "snippet": "System design."},
        ]
        (wiki_path / "search.json").write_text(json.dumps(search_index))

        return wiki_path

    def test_export_creates_output_directory(self, sample_wiki: Path, tmp_path: Path):
        """Test that export creates the output directory."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        assert output_path.exists()
        assert output_path.is_dir()

    def test_export_creates_html_files(self, sample_wiki: Path, tmp_path: Path):
        """Test that export creates HTML files for each markdown file."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        count = exporter.export()

        assert count == 4  # index, architecture, modules/index, modules/core
        assert (output_path / "index.html").exists()
        assert (output_path / "architecture.html").exists()
        assert (output_path / "modules" / "index.html").exists()
        assert (output_path / "modules" / "core.html").exists()

    def test_export_copies_search_json(self, sample_wiki: Path, tmp_path: Path):
        """Test that export copies search.json."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        assert (output_path / "search.json").exists()

    def test_html_contains_content(self, sample_wiki: Path, tmp_path: Path):
        """Test that HTML files contain the converted content."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        html = (output_path / "index.html").read_text()
        assert "Overview" in html
        assert "Welcome to the wiki" in html
        assert "<!DOCTYPE html>" in html

    def test_html_contains_toc(self, sample_wiki: Path, tmp_path: Path):
        """Test that HTML files contain the TOC."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        html = (output_path / "index.html").read_text()
        assert "toc-number" in html
        assert "Architecture" in html
        assert "Modules" in html

    def test_html_has_relative_links(self, sample_wiki: Path, tmp_path: Path):
        """Test that HTML files use relative links."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        # Root page should have ./ relative paths
        html = (output_path / "index.html").read_text()
        assert 'href="./architecture.html"' in html

        # Nested page should have ../ relative paths
        nested_html = (output_path / "modules" / "core.html").read_text()
        assert 'href="../index.html"' in nested_html

    def test_html_has_breadcrumb_for_nested_pages(self, sample_wiki: Path, tmp_path: Path):
        """Test that nested pages have breadcrumb navigation."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        # Nested page should have breadcrumb
        nested_html = (output_path / "modules" / "core.html").read_text()
        assert "breadcrumb" in nested_html
        assert "Home" in nested_html

    def test_html_has_theme_toggle(self, sample_wiki: Path, tmp_path: Path):
        """Test that HTML files have theme toggle functionality."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(sample_wiki, output_path)
        exporter.export()

        html = (output_path / "index.html").read_text()
        assert "theme-toggle" in html
        assert "setTheme" in html
        assert "localStorage" in html


class TestExportToHtml:
    """Tests for the export_to_html convenience function."""

    @pytest.fixture
    def simple_wiki(self, tmp_path: Path) -> Path:
        """Create a simple wiki for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test\n\nHello world.")
        (wiki_path / "toc.json").write_text('{"entries": []}')
        return wiki_path

    def test_default_output_path(self, simple_wiki: Path):
        """Test that default output path is {wiki_path}_html."""
        result = export_to_html(simple_wiki)
        expected_output = simple_wiki.parent / ".deepwiki_html"

        assert "Exported 1 pages" in result
        assert expected_output.exists()

    def test_custom_output_path(self, simple_wiki: Path, tmp_path: Path):
        """Test that custom output path is used."""
        custom_output = tmp_path / "custom_html"
        result = export_to_html(simple_wiki, custom_output)

        assert "Exported 1 pages" in result
        assert custom_output.exists()
        assert (custom_output / "index.html").exists()

    def test_returns_success_message(self, simple_wiki: Path, tmp_path: Path):
        """Test that export returns a success message."""
        output_path = tmp_path / "output"
        result = export_to_html(simple_wiki, output_path)

        assert "Exported" in result
        assert "pages" in result
        assert str(output_path) in result


class TestBreadcrumbDeepNesting:
    """Tests for deeply nested breadcrumb navigation."""

    @pytest.fixture
    def deep_wiki(self, tmp_path: Path) -> Path:
        """Create a wiki with deeply nested structure (3+ levels)."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create index.md at root
        (wiki_path / "index.md").write_text("# Root\n\nRoot page.")

        # Create level1/level2/level3/deep.md (3 levels deep)
        deep_path = wiki_path / "level1" / "level2" / "level3"
        deep_path.mkdir(parents=True)
        (deep_path / "deep.md").write_text("# Deep Page\n\nDeep content.")

        # Create index files at intermediate levels
        (wiki_path / "level1").mkdir(exist_ok=True)
        (wiki_path / "level1" / "index.md").write_text("# Level 1\n\nLevel 1 page.")
        (wiki_path / "level1" / "level2").mkdir(exist_ok=True)
        (wiki_path / "level1" / "level2" / "index.md").write_text("# Level 2\n\nLevel 2 page.")

        # Create toc.json
        (wiki_path / "toc.json").write_text('{"entries": []}')

        return wiki_path

    def test_deeply_nested_breadcrumb_cumulative_path(self, deep_wiki: Path, tmp_path: Path):
        """Test that deeply nested pages build cumulative paths correctly (covers line 835)."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(deep_wiki, output_path)
        exporter.export()

        # Check the deeply nested page has proper breadcrumb with cumulative path
        deep_html = (output_path / "level1" / "level2" / "level3" / "deep.html").read_text()
        assert "breadcrumb" in deep_html
        assert "Home" in deep_html
        # The breadcrumb uses titlecased directory names: Level1, Level2, Level3
        assert "Level1" in deep_html
        assert "Level2" in deep_html
        assert "Level3" in deep_html


class TestTocEntryWithoutPath:
    """Tests for TOC entries without paths (grouping labels)."""

    @pytest.fixture
    def wiki_with_grouping_toc(self, tmp_path: Path) -> Path:
        """Create a wiki with TOC entries that have no path (grouping labels)."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create some pages
        (wiki_path / "index.md").write_text("# Home\n\nWelcome.")
        (wiki_path / "page1.md").write_text("# Page 1\n\nContent.")
        (wiki_path / "page2.md").write_text("# Page 2\n\nContent.")

        # Create toc.json with a grouping entry that has no path
        toc = {
            "entries": [
                {"number": "1", "title": "Home", "path": "index.md"},
                {
                    "number": "2",
                    "title": "Section Group",  # No path - just a grouping label
                    "children": [
                        {"number": "2.1", "title": "Page 1", "path": "page1.md"},
                        {"number": "2.2", "title": "Page 2", "path": "page2.md"},
                    ],
                },
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    def test_toc_entry_without_path_renders_as_span(self, wiki_with_grouping_toc: Path, tmp_path: Path):
        """Test that TOC entries without paths render as spans, not links (covers line 796)."""
        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(wiki_with_grouping_toc, output_path)
        exporter.export()

        html = (output_path / "index.html").read_text()
        # The grouping label should be rendered as a span, not a link
        assert "Section Group" in html
        # Should contain the toc-parent span structure for the grouping label
        assert '<span class="toc-parent">' in html


class TestMain:
    """Tests for the main() CLI entry point."""

    @pytest.fixture
    def cli_wiki(self, tmp_path: Path) -> Path:
        """Create a simple wiki for CLI testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# CLI Test\n\nHello from CLI.")
        (wiki_path / "toc.json").write_text('{"entries": []}')
        return wiki_path

    def test_main_default_args(self, cli_wiki: Path, tmp_path: Path, capsys):
        """Test main() with default arguments."""
        # Change to the temp directory so .deepwiki is found
        with mock.patch("sys.argv", ["html_export", str(cli_wiki)]):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "Exported" in captured.out
        assert "index.html" in captured.out

    def test_main_with_output_arg(self, cli_wiki: Path, tmp_path: Path, capsys):
        """Test main() with --output argument."""
        output_path = tmp_path / "custom_output"
        with mock.patch("sys.argv", ["html_export", str(cli_wiki), "--output", str(output_path)]):
            result = main()

        assert result == 0
        assert output_path.exists()
        captured = capsys.readouterr()
        assert "Exported" in captured.out

    def test_main_wiki_not_found(self, tmp_path: Path, capsys):
        """Test main() when wiki path doesn't exist."""
        non_existent = tmp_path / "non_existent_wiki"
        with mock.patch("sys.argv", ["html_export", str(non_existent)]):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "does not exist" in captured.out

    def test_main_short_output_flag(self, cli_wiki: Path, tmp_path: Path, capsys):
        """Test main() with -o short flag for output."""
        output_path = tmp_path / "short_flag_output"
        with mock.patch("sys.argv", ["html_export", str(cli_wiki), "-o", str(output_path)]):
            result = main()

        assert result == 0
        assert output_path.exists()


class TestMainEntryPoint:
    """Test for the __main__ entry point."""

    def test_main_module_entry_point(self, tmp_path: Path):
        """Test that the module can be run as __main__."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test\n\nContent.")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        # Test that main() can be called and returns an exit code
        with mock.patch("sys.argv", ["html_export", str(wiki_path)]):
            exit_code = main()
            assert exit_code == 0

    def test_module_run_as_main(self, tmp_path: Path):
        """Test the if __name__ == '__main__' block (line 918)."""
        import warnings

        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test\n\nContent.")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        # Mock sys.argv and catch the SystemExit from exit()
        with mock.patch.object(sys, "argv", ["html_export", str(wiki_path)]):
            with pytest.raises(SystemExit) as exc_info:
                # Suppress runpy warning about module already in sys.modules
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*found in sys.modules.*")
                    # Run the module as __main__ - this will call exit(main())
                    runpy.run_module("local_deepwiki.export.html", run_name="__main__", alter_sys=True)
            # exit(0) means successful execution
            assert exc_info.value.code == 0
