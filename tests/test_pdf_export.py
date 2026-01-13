"""Tests for PDF export functionality."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.export.pdf import (
    PdfExporter,
    export_to_pdf,
    extract_title,
    render_markdown_for_pdf,
)


class TestRenderMarkdownForPdf:
    """Tests for PDF-specific markdown rendering."""

    def test_basic_markdown(self):
        """Test basic markdown conversion."""
        md = "# Hello\n\nThis is a paragraph."
        html = render_markdown_for_pdf(md)
        assert "<h1" in html
        assert "Hello" in html
        assert "<p>" in html

    def test_code_blocks(self):
        """Test fenced code blocks."""
        md = "```python\ndef hello():\n    pass\n```"
        html = render_markdown_for_pdf(md)
        assert "<code" in html
        assert "def hello" in html

    def test_tables(self):
        """Test markdown tables."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = render_markdown_for_pdf(md)
        assert "<table>" in html
        assert "<th>" in html
        assert "<td>" in html

    def test_mermaid_blocks_replaced_with_note(self):
        """Test that mermaid blocks are replaced with a note."""
        md = "Some text\n\n```mermaid\ngraph TD\nA-->B\n```\n\nMore text"
        html = render_markdown_for_pdf(md)
        # Mermaid should be replaced with a note
        assert "mermaid-note" in html
        assert "not available in PDF" in html
        # Original mermaid content should not be present
        assert "graph TD" not in html
        assert "A-->B" not in html

    def test_multiple_mermaid_blocks(self):
        """Test handling multiple mermaid blocks."""
        md = """# Title

```mermaid
graph TD
A-->B
```

Some content

```mermaid
sequenceDiagram
A->>B: Hello
```

End content
"""
        html = render_markdown_for_pdf(md)
        # Both should be replaced
        assert html.count("mermaid-note") == 2
        assert "graph TD" not in html
        assert "sequenceDiagram" not in html


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

    def test_h1_with_leading_whitespace(self, tmp_path: Path):
        """Test extracting H1 title with leading whitespace."""
        md_file = tmp_path / "test.md"
        md_file.write_text("\n\n# Title With Whitespace\n\nContent.")
        assert extract_title(md_file) == "Title With Whitespace"


class TestPdfExporter:
    """Tests for PdfExporter class."""

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

        return wiki_path

    def test_collect_pages_in_order(self, sample_wiki: Path, tmp_path: Path):
        """Test that pages are collected in TOC order."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(sample_wiki, output_path)

        # Load TOC
        toc_path = sample_wiki / "toc.json"
        toc_data = json.loads(toc_path.read_text())
        exporter.toc_entries = toc_data.get("entries", [])

        pages = exporter._collect_pages_in_order()

        # Should be in TOC order
        assert len(pages) == 4
        assert pages[0].name == "index.md"
        assert pages[1].name == "architecture.md"
        # modules/index.md and modules/core.md should follow

    def test_extract_paths_from_toc(self, sample_wiki: Path, tmp_path: Path):
        """Test extracting paths from nested TOC."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(sample_wiki, output_path)

        toc_entries = [
            {"title": "A", "path": "a.md"},
            {
                "title": "B",
                "path": "b.md",
                "children": [
                    {"title": "B1", "path": "b/b1.md"},
                    {"title": "B2", "path": "b/b2.md"},
                ],
            },
        ]

        paths: list[str] = []
        exporter._extract_paths_from_toc(toc_entries, paths)

        assert paths == ["a.md", "b.md", "b/b1.md", "b/b2.md"]

    def test_build_toc_html(self, sample_wiki: Path, tmp_path: Path):
        """Test building TOC HTML."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(sample_wiki, output_path)

        pages = [
            sample_wiki / "index.md",
            sample_wiki / "architecture.md",
        ]

        toc_html = exporter._build_toc_html(pages)

        assert '<div class="toc">' in toc_html
        assert '<div class="toc-item">' in toc_html
        assert "Overview" in toc_html
        assert "Architecture" in toc_html

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_single_creates_pdf(self, mock_html_class, sample_wiki: Path, tmp_path: Path):
        """Test that export_single creates a PDF file."""
        output_path = tmp_path / "output.pdf"

        # Mock WeasyPrint
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_path)
        result = exporter.export_single()

        assert result == output_path
        mock_html_class.assert_called_once()
        mock_html_instance.write_pdf.assert_called_once()

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_single_with_directory_output(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test export_single with directory as output path."""
        output_dir = tmp_path / "output_dir"
        output_dir.mkdir()

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_dir)
        result = exporter.export_single()

        # Should create documentation.pdf in the directory
        assert result == output_dir / "documentation.pdf"

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_separate_creates_multiple_pdfs(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_separate creates multiple PDF files."""
        output_path = tmp_path / "pdfs"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_path)
        results = exporter.export_separate()

        # Should create 4 PDFs (one per markdown file)
        assert len(results) == 4
        # Each export should call write_pdf
        assert mock_html_instance.write_pdf.call_count == 4

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_separate_preserves_directory_structure(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_separate preserves directory structure."""
        output_path = tmp_path / "pdfs"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(sample_wiki, output_path)
        results = exporter.export_separate()

        # Check paths preserve structure
        result_names = [p.name for p in results]
        assert "index.pdf" in result_names
        assert "architecture.pdf" in result_names
        assert "core.pdf" in result_names

        # Check nested directory is created
        assert any("modules" in str(p) for p in results)


class TestExportToPdf:
    """Tests for the export_to_pdf convenience function."""

    @pytest.fixture
    def simple_wiki(self, tmp_path: Path) -> Path:
        """Create a simple wiki for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test\n\nHello world.")
        (wiki_path / "toc.json").write_text('{"entries": []}')
        return wiki_path

    def test_raises_for_nonexistent_wiki(self, tmp_path: Path):
        """Test that export raises for nonexistent wiki path."""
        with pytest.raises(ValueError, match="does not exist"):
            export_to_pdf(tmp_path / "nonexistent")

    @patch("local_deepwiki.export.pdf.HTML")
    def test_default_output_path_single(self, mock_html_class, simple_wiki: Path):
        """Test default output path for single file mode."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        result = export_to_pdf(simple_wiki, single_file=True)

        assert "Exported wiki to PDF" in result
        expected_path = simple_wiki.parent / ".deepwiki.pdf"
        assert str(expected_path) in result

    @patch("local_deepwiki.export.pdf.HTML")
    def test_default_output_path_separate(self, mock_html_class, simple_wiki: Path):
        """Test default output path for separate file mode."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        result = export_to_pdf(simple_wiki, single_file=False)

        assert "Exported 1 pages to PDFs" in result
        expected_path = simple_wiki.parent / ".deepwiki_pdfs"
        assert str(expected_path) in result

    @patch("local_deepwiki.export.pdf.HTML")
    def test_custom_output_path(self, mock_html_class, simple_wiki: Path, tmp_path: Path):
        """Test custom output path."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        custom_output = tmp_path / "custom.pdf"
        result = export_to_pdf(simple_wiki, custom_output)

        assert "Exported wiki to PDF" in result
        assert str(custom_output) in result

    @patch("local_deepwiki.export.pdf.HTML")
    def test_string_paths_accepted(self, mock_html_class, simple_wiki: Path, tmp_path: Path):
        """Test that string paths are accepted."""
        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        custom_output = tmp_path / "output.pdf"
        result = export_to_pdf(str(simple_wiki), str(custom_output))

        assert "Exported wiki to PDF" in result


class TestPrintCss:
    """Tests for print CSS content."""

    def test_print_css_has_page_rules(self):
        """Test that print CSS has @page rules."""
        from local_deepwiki.export.pdf import PRINT_CSS

        assert "@page" in PRINT_CSS
        assert "margin" in PRINT_CSS

    def test_print_css_has_page_numbers(self):
        """Test that print CSS includes page numbers."""
        from local_deepwiki.export.pdf import PRINT_CSS

        assert "counter(page)" in PRINT_CSS
        assert "counter(pages)" in PRINT_CSS

    def test_print_css_avoids_page_breaks_in_code(self):
        """Test that print CSS avoids page breaks inside code blocks."""
        from local_deepwiki.export.pdf import PRINT_CSS

        assert "page-break-inside: avoid" in PRINT_CSS

    def test_print_css_keeps_headings_with_content(self):
        """Test that print CSS keeps headings with following content."""
        from local_deepwiki.export.pdf import PRINT_CSS

        assert "page-break-after: avoid" in PRINT_CSS


class TestMermaidHandling:
    """Tests for mermaid diagram handling in PDF export."""

    def test_mermaid_replaced_with_note(self):
        """Test that mermaid diagrams are replaced with a note."""
        md = """# Test

```mermaid
graph TD
    A[Start] --> B[End]
```
"""
        html = render_markdown_for_pdf(md)

        assert "mermaid-note" in html
        assert "not available in PDF" in html
        assert "view in html version" in html.lower()

    def test_regular_code_blocks_preserved(self):
        """Test that regular code blocks are preserved."""
        md = """# Test

```python
def hello():
    print("Hello")
```
"""
        html = render_markdown_for_pdf(md)

        assert "def hello" in html
        # Quotes are HTML-encoded to &quot;
        assert "print(" in html and "Hello" in html
        assert "mermaid-note" not in html

    def test_mixed_code_blocks(self):
        """Test document with both mermaid and regular code blocks."""
        md = """# Test

```python
def foo():
    pass
```

```mermaid
graph TD
    A-->B
```

```javascript
const x = 1;
```
"""
        html = render_markdown_for_pdf(md)

        # Regular code should be preserved
        assert "def foo" in html
        assert "const x = 1" in html

        # Mermaid should be replaced
        assert "mermaid-note" in html
        assert "A-->B" not in html
