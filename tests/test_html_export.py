"""Tests for HTML export functionality."""

import json
from pathlib import Path

import pytest

from local_deepwiki.export.html import HtmlExporter, export_to_html, extract_title, render_markdown


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
