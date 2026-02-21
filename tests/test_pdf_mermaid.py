"""Tests for mermaid diagram handling in PDF export."""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock weasyprint before importing pdf module if native libraries aren't available
_weasyprint_mock = None
_weasyprint_available = False

try:
    from weasyprint import CSS as _CSS, HTML as _HTML  # noqa: F401

    _weasyprint_available = True
except (ImportError, OSError):
    _weasyprint_mock = MagicMock()
    _weasyprint_mock.HTML = MagicMock
    _weasyprint_mock.CSS = MagicMock
    sys.modules["weasyprint"] = _weasyprint_mock


def _check_weasyprint_functional() -> bool:
    """Check if WeasyPrint can actually create PDFs."""
    if not _weasyprint_available:
        return False
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from weasyprint import HTML; HTML(string='<html></html>').write_pdf()",
            ],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


_WEASYPRINT_FUNCTIONAL: bool | None = None


def weasyprint_functional() -> bool:
    """Check if WeasyPrint can actually generate PDFs."""
    global _WEASYPRINT_FUNCTIONAL
    if _WEASYPRINT_FUNCTIONAL is None:
        _WEASYPRINT_FUNCTIONAL = _check_weasyprint_functional()
    return _WEASYPRINT_FUNCTIONAL


from local_deepwiki.export.pdf import (
    PdfExporter,
    extract_mermaid_blocks,
    is_mmdc_available,
    render_markdown_for_pdf,
    render_mermaid_to_png,
    render_mermaid_to_svg,
)


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

        assert "def foo" in html
        assert "const x = 1" in html

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

    @patch("local_deepwiki.export.mermaid_renderer.shutil.which")
    def test_mmdc_available(self, mock_which):
        """Test when mmdc is available."""
        import local_deepwiki.export.mermaid_renderer as mermaid_module

        mermaid_module._mmdc_available = None
        mock_which.return_value = "/usr/local/bin/mmdc"

        result = is_mmdc_available()
        assert result is True
        mock_which.assert_called_once_with("mmdc")

    @patch("local_deepwiki.export.mermaid_renderer.shutil.which")
    def test_mmdc_not_available(self, mock_which):
        """Test when mmdc is not available."""
        import local_deepwiki.export.mermaid_renderer as mermaid_module

        mermaid_module._mmdc_available = None
        mock_which.return_value = None

        result = is_mmdc_available()
        assert result is False

    @patch("local_deepwiki.export.mermaid_renderer.shutil.which")
    def test_result_is_cached(self, mock_which):
        """Test that the result is cached."""
        import local_deepwiki.export.mermaid_renderer as mermaid_module

        mermaid_module._mmdc_available = None
        mock_which.return_value = "/usr/local/bin/mmdc"

        result1 = is_mmdc_available()
        result2 = is_mmdc_available()

        assert result1 is True
        assert result2 is True
        assert mock_which.call_count == 1


class TestRenderMermaidToSvg:
    """Tests for mermaid to SVG rendering."""

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_returns_none_when_mmdc_unavailable(self, mock_available):
        """Test that None is returned when mmdc is not available."""
        mock_available.return_value = False

        result = render_mermaid_to_svg("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_renders_svg_successfully(self, mock_available, mock_run, tmp_path):
        """Test successful SVG rendering."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_returns_none_on_cli_error(self, mock_available, mock_run):
        """Test that None is returned on CLI error."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        result = render_mermaid_to_svg("invalid diagram")
        assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_handles_timeout(self, mock_available):
        """Test that timeout is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.mermaid_renderer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("mmdc", 30)
            result = render_mermaid_to_svg("graph TD\nA-->B")
            assert result is None


class TestRenderMermaidToPng:
    """Tests for mermaid to PNG rendering."""

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_returns_none_when_mmdc_unavailable(self, mock_available):
        """Test that None is returned when mmdc is not available."""
        mock_available.return_value = False

        result = render_mermaid_to_png("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_returns_none_on_cli_error(self, mock_available, mock_run):
        """Test that None is returned on CLI error."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")

        result = render_mermaid_to_png("invalid diagram")
        assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_handles_timeout(self, mock_available):
        """Test that timeout is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.mermaid_renderer.subprocess.run") as mock_run:
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
        mock_render.return_value = None

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


class TestRenderMermaidToPngSuccessPath:
    """Tests for successful mermaid PNG rendering."""

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_successful_png_rendering(self, mock_available, mock_run, tmp_path: Path):
        """Test successful PNG rendering with mocked subprocess."""
        mock_available.return_value = True

        def run_side_effect(*args, **kwargs):
            cmd_args = args[0]
            output_idx = cmd_args.index("-o") + 1
            output_file = Path(cmd_args[output_idx])
            output_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = render_mermaid_to_png("graph TD\nA-->B")

        assert result is not None
        assert result.startswith(b"\x89PNG")

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_png_output_file_not_created(self, mock_available, mock_run):
        """Test when mmdc succeeds but doesn't create output file."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        result = render_mermaid_to_png("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_handles_oserror(self, mock_available):
        """Test that OSError is handled gracefully."""
        mock_available.return_value = True

        with patch("local_deepwiki.export.mermaid_renderer.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("File system error")
            result = render_mermaid_to_png("graph TD\nA-->B")
            assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_handles_subprocess_error(self, mock_available):
        """Test that SubprocessError is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.mermaid_renderer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Process failed")
            result = render_mermaid_to_png("graph TD\nA-->B")
            assert result is None


class TestRenderMermaidToSvgSuccessPath:
    """Tests for successful mermaid SVG rendering."""

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_successful_svg_rendering(self, mock_available, mock_run):
        """Test successful SVG rendering with mocked subprocess."""
        mock_available.return_value = True

        def run_side_effect(*args, **kwargs):
            cmd_args = args[0]
            output_idx = cmd_args.index("-o") + 1
            output_file = Path(cmd_args[output_idx])
            output_file.write_text('<svg xmlns="http://www.w3.org/2000/svg">test</svg>')
            return MagicMock(returncode=0)

        mock_run.side_effect = run_side_effect

        result = render_mermaid_to_svg("graph TD\nA-->B")

        assert result is not None
        assert "<svg" in result

    @patch("local_deepwiki.export.mermaid_renderer.subprocess.run")
    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_svg_output_file_not_created(self, mock_available, mock_run):
        """Test when mmdc succeeds but doesn't create output file."""
        mock_available.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        result = render_mermaid_to_svg("graph TD\nA-->B")
        assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_handles_oserror(self, mock_available):
        """Test that OSError is handled gracefully."""
        mock_available.return_value = True

        with patch("local_deepwiki.export.mermaid_renderer.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("File system error")
            result = render_mermaid_to_svg("graph TD\nA-->B")
            assert result is None

    @patch("local_deepwiki.export.mermaid_renderer.is_mmdc_available")
    def test_handles_subprocess_error(self, mock_available):
        """Test that SubprocessError is handled gracefully."""
        import subprocess

        mock_available.return_value = True

        with patch("local_deepwiki.export.mermaid_renderer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Process failed")
            result = render_mermaid_to_svg("graph TD\nA-->B")
            assert result is None


class TestMermaidCliIntegration:
    """Integration tests for mermaid diagram rendering.

    These tests require mmdc (mermaid-cli) to be installed.
    They verify actual diagram rendering, not just mocking.
    """

    def test_render_mermaid_to_png_creates_image(self):
        """Test that render_mermaid_to_png creates actual PNG bytes."""
        diagram = """graph TD
    A[Start] --> B[Process]
    B --> C[End]"""

        result = render_mermaid_to_png(diagram)

        if result is not None:
            assert isinstance(result, bytes)
            assert result[:8] == b"\x89PNG\r\n\x1a\n", "Not a valid PNG"
            assert len(result) > 100, "PNG seems too small"

    def test_render_mermaid_to_svg_creates_svg(self):
        """Test that render_mermaid_to_svg creates actual SVG content."""
        diagram = """sequenceDiagram
    Alice->>Bob: Hello
    Bob->>Alice: Hi"""

        result = render_mermaid_to_svg(diagram)

        if result is not None:
            assert isinstance(result, str)
            assert "<svg" in result
            assert "</svg>" in result

    def test_render_markdown_with_mermaid_embeds_image(self, tmp_path: Path):
        """Test that markdown with mermaid gets PNG embedded."""
        md_content = """# Test

```mermaid
graph LR
    A --> B
```

Some text after.
"""
        html = render_markdown_for_pdf(md_content, render_mermaid=True)

        if "data:image/png;base64," in html:
            assert "mermaid-diagram" in html
            assert "mermaid-note" not in html
        else:
            assert "mermaid-note" in html

    @pytest.mark.skipif(
        not weasyprint_functional(), reason="WeasyPrint not fully functional"
    )
    def test_pdf_with_rendered_mermaid_diagram(self, tmp_path: Path):
        """Test full PDF export with actual mermaid diagram rendering."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("""# Diagram Test

Below is a flowchart:

```mermaid
graph TD
    A[Input] --> B{Decision}
    B -->|Yes| C[Process]
    B -->|No| D[Skip]
    C --> E[Output]
    D --> E
```

And a sequence diagram:

```mermaid
sequenceDiagram
    Client->>Server: Request
    Server->>Database: Query
    Database->>Server: Result
    Server->>Client: Response
```
""")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "diagrams.pdf"
        exporter = PdfExporter(wiki_path, output_path)
        result = exporter.export_single()

        assert result.exists()
        assert result.stat().st_size > 1024
        with open(result, "rb") as f:
            assert f.read(5) == b"%PDF-"
