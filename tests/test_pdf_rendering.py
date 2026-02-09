"""Tests for PDF rendering: markdown conversion, title extraction, and print CSS."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock weasyprint before importing pdf module if native libraries aren't available
# This allows tests to run even without libgobject/pango installed
_weasyprint_mock = None
_weasyprint_available = False

try:
    from weasyprint import CSS as _CSS, HTML as _HTML  # noqa: F401

    _weasyprint_available = True
except (ImportError, OSError):
    # Create mock classes for weasyprint
    _weasyprint_mock = MagicMock()
    _weasyprint_mock.HTML = MagicMock
    _weasyprint_mock.CSS = MagicMock
    sys.modules["weasyprint"] = _weasyprint_mock

from local_deepwiki.export.pdf import (
    PRINT_CSS,
    extract_title,
    render_markdown_for_pdf,
)

import pytest
from unittest.mock import patch


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
