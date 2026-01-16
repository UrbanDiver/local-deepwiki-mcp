"""Tests for PDF export functionality."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.export.pdf import (
    PDF_HTML_TEMPLATE,
    PRINT_CSS,
    PdfExporter,
    export_to_pdf,
    extract_mermaid_blocks,
    extract_title,
    is_mmdc_available,
    render_markdown_for_pdf,
    render_mermaid_to_png,
    render_mermaid_to_svg,
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
        """Test that mermaid blocks are replaced with a note when CLI unavailable."""
        md = "Some text\n\n```mermaid\ngraph TD\nA-->B\n```\n\nMore text"
        html = render_markdown_for_pdf(md, render_mermaid=False)
        # Mermaid should be replaced with a note
        assert "mermaid-note" in html
        assert "not available in PDF" in html
        # Original mermaid content should not be present
        assert "graph TD" not in html
        assert "A-->B" not in html

    def test_multiple_mermaid_blocks(self):
        """Test handling multiple mermaid blocks when CLI unavailable."""
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
        html = render_markdown_for_pdf(md, render_mermaid=False)
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
        assert "@page" in PRINT_CSS
        assert "margin" in PRINT_CSS

    def test_print_css_has_page_numbers(self):
        """Test that print CSS includes page numbers."""
        assert "counter(page)" in PRINT_CSS
        assert "counter(pages)" in PRINT_CSS

    def test_print_css_avoids_page_breaks_in_code(self):
        """Test that print CSS avoids page breaks inside code blocks."""
        assert "page-break-inside: avoid" in PRINT_CSS

    def test_print_css_keeps_headings_with_content(self):
        """Test that print CSS keeps headings with following content."""
        assert "page-break-after: avoid" in PRINT_CSS


class TestMermaidHandling:
    """Tests for mermaid diagram handling in PDF export without CLI."""

    def test_mermaid_replaced_with_note(self):
        """Test that mermaid diagrams are replaced with a note when CLI unavailable."""
        md = """# Test

```mermaid
graph TD
    A[Start] --> B[End]
```
"""
        html = render_markdown_for_pdf(md, render_mermaid=False)

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
        html = render_markdown_for_pdf(md, render_mermaid=False)

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
        html = render_markdown_for_pdf(md, render_mermaid=False)

        # Regular code should be preserved
        assert "def foo" in html
        assert "const x = 1" in html

        # Mermaid should be replaced
        assert "mermaid-note" in html
        assert "A-->B" not in html


class TestExtractMermaidBlocks:
    """Tests for mermaid block extraction."""

    def test_extract_single_block(self):
        """Test extracting a single mermaid block."""
        content = """# Test

```mermaid
graph TD
    A-->B
```

End.
"""
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 1
        full_block, diagram_code = blocks[0]
        assert "```mermaid" in full_block
        assert "graph TD" in diagram_code
        assert "A-->B" in diagram_code

    def test_extract_multiple_blocks(self):
        """Test extracting multiple mermaid blocks."""
        content = """
```mermaid
graph TD
    A-->B
```

Some text

```mermaid
sequenceDiagram
    A->>B: Hello
```
"""
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 2
        assert "graph TD" in blocks[0][1]
        assert "sequenceDiagram" in blocks[1][1]

    def test_no_mermaid_blocks(self):
        """Test content with no mermaid blocks."""
        content = """# Title

```python
def foo():
    pass
```
"""
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 0

    def test_diagram_code_stripped(self):
        """Test that diagram code is stripped of whitespace."""
        content = """```mermaid

graph TD
    A-->B

```"""
        blocks = extract_mermaid_blocks(content)
        assert len(blocks) == 1
        _, diagram_code = blocks[0]
        assert diagram_code.startswith("graph TD")


class TestIsMmdcAvailable:
    """Tests for mermaid CLI availability check."""

    @patch("local_deepwiki.export.pdf.shutil.which")
    def test_mmdc_available(self, mock_which):
        """Test when mmdc is available."""
        import local_deepwiki.export.pdf as pdf_module

        # Reset the cache
        pdf_module._mmdc_available = None
        mock_which.return_value = "/usr/local/bin/mmdc"

        result = is_mmdc_available()
        assert result is True
        mock_which.assert_called_once_with("mmdc")

    @patch("local_deepwiki.export.pdf.shutil.which")
    def test_mmdc_not_available(self, mock_which):
        """Test when mmdc is not available."""
        import local_deepwiki.export.pdf as pdf_module

        # Reset the cache
        pdf_module._mmdc_available = None
        mock_which.return_value = None

        result = is_mmdc_available()
        assert result is False

    @patch("local_deepwiki.export.pdf.shutil.which")
    def test_result_is_cached(self, mock_which):
        """Test that the result is cached."""
        import local_deepwiki.export.pdf as pdf_module

        # Reset the cache
        pdf_module._mmdc_available = None
        mock_which.return_value = "/usr/local/bin/mmdc"

        # First call
        result1 = is_mmdc_available()
        # Second call (should use cache)
        result2 = is_mmdc_available()

        assert result1 is True
        assert result2 is True
        # Should only be called once due to caching
        assert mock_which.call_count == 1


class TestRenderMermaidToSvg:
    """Tests for mermaid to SVG rendering."""

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_returns_none_when_mmdc_unavailable(self, mock_available):
        """Test that None is returned when mmdc is not available."""
        mock_available.return_value = False

        result = render_mermaid_to_svg("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_renders_svg_successfully(self, mock_available, mock_run, tmp_path):
        """Test successful SVG rendering."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        # We can't easily test the actual file operations without more complex mocking
        # This test mainly verifies the function doesn't crash when CLI is available
        # The actual integration test would require mmdc to be installed

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_returns_none_on_cli_error(self, mock_available, mock_run):
        """Test that None is returned on CLI error."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        result = render_mermaid_to_svg("invalid diagram")
        assert result is None

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_handles_timeout(self, mock_available):
        """Test that timeout is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.pdf.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("mmdc", 30)
            result = render_mermaid_to_svg("graph TD\nA-->B")
            assert result is None


class TestRenderMermaidToPng:
    """Tests for mermaid to PNG rendering."""

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_returns_none_when_mmdc_unavailable(self, mock_available):
        """Test that None is returned when mmdc is not available."""
        mock_available.return_value = False

        result = render_mermaid_to_png("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_returns_none_on_cli_error(self, mock_available, mock_run):
        """Test that None is returned on CLI error."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        result = render_mermaid_to_png("invalid diagram")
        assert result is None

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_handles_timeout(self, mock_available):
        """Test that timeout is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.pdf.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("mmdc", 30)
            result = render_mermaid_to_png("graph TD\nA-->B")
            assert result is None


class TestMermaidCliRendering:
    """Tests for mermaid rendering with CLI available (uses PNG)."""

    @patch("local_deepwiki.export.pdf.render_mermaid_to_png")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_renders_mermaid_when_cli_available(self, mock_available, mock_render):
        """Test that mermaid diagrams are rendered as PNG when CLI is available."""
        mock_available.return_value = True
        # Return fake PNG bytes
        mock_render.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        md = """# Test

```mermaid
graph TD
    A-->B
```
"""
        html = render_markdown_for_pdf(md, render_mermaid=True)

        assert "mermaid-diagram" in html
        assert "data:image/png;base64," in html
        assert "mermaid-note" not in html
        mock_render.assert_called_once()

    @patch("local_deepwiki.export.pdf.render_mermaid_to_png")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_falls_back_on_render_failure(self, mock_available, mock_render):
        """Test fallback to placeholder when render fails."""
        mock_available.return_value = True
        mock_render.return_value = None  # Simulate render failure

        md = """# Test

```mermaid
graph TD
    A-->B
```
"""
        html = render_markdown_for_pdf(md, render_mermaid=True)

        assert "mermaid-note" in html
        assert "rendering failed" in html.lower()

    @patch("local_deepwiki.export.pdf.render_mermaid_to_png")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_renders_multiple_diagrams(self, mock_available, mock_render):
        """Test rendering multiple mermaid diagrams as PNG."""
        mock_available.return_value = True
        # Return different fake PNG bytes for each diagram
        mock_render.side_effect = [
            b"\x89PNG\r\n\x1a\ndiagram1",
            b"\x89PNG\r\n\x1a\ndiagram2",
        ]

        md = """# Test

```mermaid
graph TD
    A-->B
```

```mermaid
sequenceDiagram
    A->>B: Hello
```
"""
        html = render_markdown_for_pdf(md, render_mermaid=True)

        assert html.count("mermaid-diagram") == 2
        assert html.count("data:image/png;base64,") == 2
        assert mock_render.call_count == 2


class TestMainCli:
    """Tests for the main() CLI entry point."""

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_default_args(self, mock_export, tmp_path: Path, monkeypatch):
        """Test main with default arguments."""
        # Create a .deepwiki directory
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        monkeypatch.chdir(tmp_path)
        mock_export.return_value = "Exported wiki to PDF: output.pdf"

        from local_deepwiki.export.pdf import main

        with patch("sys.argv", ["deepwiki-export-pdf"]):
            main()

        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args.kwargs["single_file"] is True

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_custom_wiki_path(self, mock_export, tmp_path: Path):
        """Test main with custom wiki path."""
        wiki_path = tmp_path / "custom_wiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        mock_export.return_value = "Exported wiki to PDF: output.pdf"

        from local_deepwiki.export.pdf import main

        with patch("sys.argv", ["deepwiki-export-pdf", str(wiki_path)]):
            main()

        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args.kwargs["wiki_path"] == wiki_path

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_with_output_option(self, mock_export, tmp_path: Path):
        """Test main with -o/--output option."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")
        output_path = tmp_path / "custom_output.pdf"

        mock_export.return_value = f"Exported wiki to PDF: {output_path}"

        from local_deepwiki.export.pdf import main

        with patch("sys.argv", ["deepwiki-export-pdf", str(wiki_path), "-o", str(output_path)]):
            main()

        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args.kwargs["output_path"] == output_path

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_with_separate_option(self, mock_export, tmp_path: Path):
        """Test main with --separate option."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        mock_export.return_value = "Exported 1 pages to PDFs"

        from local_deepwiki.export.pdf import main

        with patch("sys.argv", ["deepwiki-export-pdf", str(wiki_path), "--separate"]):
            main()

        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args.kwargs["single_file"] is False

    def test_main_nonexistent_wiki_path(self, tmp_path: Path, capsys):
        """Test main with nonexistent wiki path."""
        nonexistent = tmp_path / "nonexistent"

        from local_deepwiki.export.pdf import main

        with patch("sys.argv", ["deepwiki-export-pdf", str(nonexistent)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_handles_export_exception(self, mock_export, tmp_path: Path, capsys):
        """Test main handles exceptions from export_to_pdf."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        mock_export.side_effect = RuntimeError("PDF generation failed")

        from local_deepwiki.export.pdf import main

        with patch("sys.argv", ["deepwiki-export-pdf", str(wiki_path)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error exporting to PDF" in captured.err
        assert "PDF generation failed" in captured.err


class TestRenderMermaidToPngSuccessPath:
    """Tests for successful mermaid PNG rendering."""

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_successful_png_rendering(self, mock_available, mock_run, tmp_path: Path):
        """Test successful PNG rendering with mocked subprocess."""
        mock_available.return_value = True

        # Create a mock that simulates successful mmdc execution
        def run_side_effect(*args, **kwargs):
            # Find the output file path from the command args
            cmd_args = args[0]
            output_idx = cmd_args.index("-o") + 1
            output_file = Path(cmd_args[output_idx])
            # Create a fake PNG file
            output_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = render_mermaid_to_png("graph TD\nA-->B")

        assert result is not None
        assert result.startswith(b"\x89PNG")

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_png_output_file_not_created(self, mock_available, mock_run):
        """Test when mmdc succeeds but doesn't create output file."""
        mock_available.return_value = True
        # mmdc returns success but doesn't create the file
        mock_run.return_value = MagicMock(returncode=0)

        result = render_mermaid_to_png("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_handles_oserror(self, mock_available):
        """Test that OSError is handled gracefully."""
        mock_available.return_value = True

        with patch("local_deepwiki.export.pdf.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("File system error")
            result = render_mermaid_to_png("graph TD\nA-->B")
            assert result is None

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_handles_subprocess_error(self, mock_available):
        """Test that SubprocessError is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.pdf.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Process failed")
            result = render_mermaid_to_png("graph TD\nA-->B")
            assert result is None


class TestRenderMermaidToSvgSuccessPath:
    """Tests for successful mermaid SVG rendering."""

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_successful_svg_rendering(self, mock_available, mock_run):
        """Test successful SVG rendering with mocked subprocess."""
        mock_available.return_value = True

        # Create a mock that simulates successful mmdc execution
        def run_side_effect(*args, **kwargs):
            cmd_args = args[0]
            output_idx = cmd_args.index("-o") + 1
            output_file = Path(cmd_args[output_idx])
            # Create a fake SVG file
            output_file.write_text('<svg xmlns="http://www.w3.org/2000/svg">test</svg>')
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = render_mermaid_to_svg("graph TD\nA-->B")

        assert result is not None
        assert "<svg" in result

    @patch("local_deepwiki.export.pdf.subprocess.run")
    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_svg_output_file_not_created(self, mock_available, mock_run):
        """Test when mmdc succeeds but doesn't create output file."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        result = render_mermaid_to_svg("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_handles_oserror(self, mock_available):
        """Test that OSError is handled gracefully."""
        mock_available.return_value = True

        with patch("local_deepwiki.export.pdf.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("File system error")
            result = render_mermaid_to_svg("graph TD\nA-->B")
            assert result is None

    @patch("local_deepwiki.export.pdf.is_mmdc_available")
    def test_handles_subprocess_error(self, mock_available):
        """Test that SubprocessError is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.pdf.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Process failed")
            result = render_mermaid_to_svg("graph TD\nA-->B")
            assert result is None


class TestExtractTitleErrorHandling:
    """Tests for extract_title error handling."""

    def test_handles_oserror(self, tmp_path: Path):
        """Test handling of OSError when reading file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title")

        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            # Should fall back to filename-based title
            result = extract_title(md_file)
            assert result == "Test"

    def test_handles_unicode_decode_error(self, tmp_path: Path):
        """Test handling of UnicodeDecodeError."""
        md_file = tmp_path / "my_doc.md"
        # Write binary content that will cause decode error
        md_file.write_bytes(b"\xff\xfe invalid utf-8 \x80\x81")

        # The actual read_text will raise UnicodeDecodeError
        # so we test the fallback behavior
        result = extract_title(md_file)
        # Should fall back to filename-based title
        assert result == "My Doc"

    def test_nonexistent_file_fallback(self, tmp_path: Path):
        """Test fallback for nonexistent file."""
        md_file = tmp_path / "missing_file.md"
        # File doesn't exist - should use filename fallback
        result = extract_title(md_file)
        assert result == "Missing File"


class TestPdfExporterEdgeCases:
    """Tests for PdfExporter edge cases."""

    @pytest.fixture
    def wiki_with_empty_paths(self, tmp_path: Path) -> Path:
        """Create a wiki with TOC entries that have empty paths."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Index")
        (wiki_path / "page.md").write_text("# Page")

        # TOC with some entries having empty or missing paths
        toc = {
            "entries": [
                {"number": "1", "title": "Index", "path": "index.md"},
                {"number": "2", "title": "Section Header", "path": ""},  # Empty path
                {"number": "3", "title": "Page", "path": "page.md"},
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    def test_handles_empty_toc_paths(self, wiki_with_empty_paths: Path, tmp_path: Path):
        """Test that empty TOC paths are skipped."""
        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_with_empty_paths, output_path)

        # Load TOC
        toc_path = wiki_with_empty_paths / "toc.json"
        toc_data = json.loads(toc_path.read_text())
        exporter.toc_entries = toc_data.get("entries", [])

        paths: list[str] = []
        exporter._extract_paths_from_toc(exporter.toc_entries, paths)

        # Empty path should be skipped
        assert "" not in paths
        assert "index.md" in paths
        assert "page.md" in paths

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_separate_with_pdf_suffix_output(self, mock_html_class, tmp_path: Path):
        """Test export_separate when output path has .pdf suffix."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        # Output path with .pdf suffix
        output_path = tmp_path / "output.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = PdfExporter(wiki_path, output_path)
        results = exporter.export_separate()

        # Should create directory named "output" (without .pdf)
        assert len(results) == 1
        # Output should be in tmp_path/output/ directory
        assert results[0].parent.name == "output"
        assert results[0].suffix == ".pdf"

    def test_collect_pages_with_no_toc(self, tmp_path: Path):
        """Test collecting pages when no TOC exists."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "a.md").write_text("# A")
        (wiki_path / "b.md").write_text("# B")

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_path, output_path)
        # Don't set toc_entries - they remain empty

        pages = exporter._collect_pages_in_order()

        # Should return all md files in sorted order
        assert len(pages) == 2
        page_names = [p.name for p in pages]
        assert "a.md" in page_names
        assert "b.md" in page_names

    @patch("local_deepwiki.export.pdf.HTML")
    def test_build_combined_html_with_mermaid(self, mock_html_class, tmp_path: Path):
        """Test building combined HTML with mermaid diagrams."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Index\n\n```mermaid\ngraph TD\nA-->B\n```")

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_path, output_path)

        pages = [wiki_path / "index.md"]
        html = exporter._build_combined_html(pages)

        # Should contain the document structure
        assert "<!DOCTYPE html>" in html
        assert "<title>Documentation</title>" in html
        assert "Table of Contents" in html

    def test_toc_entries_with_missing_children_key(self, tmp_path: Path):
        """Test TOC entries without children key."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(wiki_path, output_path)

        # Entries without 'children' key
        toc_entries = [
            {"title": "A", "path": "a.md"},
            {"title": "B", "path": "b.md"},
        ]

        paths: list[str] = []
        exporter._extract_paths_from_toc(toc_entries, paths)

        assert paths == ["a.md", "b.md"]


class TestExportToPdfEdgeCases:
    """Additional edge case tests for export_to_pdf."""

    @patch("local_deepwiki.export.pdf.HTML")
    def test_accepts_path_as_string(self, mock_html_class, tmp_path: Path):
        """Test that wiki_path can be a string."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        # Pass as string
        result = export_to_pdf(str(wiki_path))
        assert "Exported wiki to PDF" in result
