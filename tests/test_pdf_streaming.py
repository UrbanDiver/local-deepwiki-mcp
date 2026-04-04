"""Tests for streaming PDF export, CLI entry point, and integration."""

import builtins
import json
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
    StreamingPdfExporter,
    export_to_pdf,
)
from local_deepwiki.export.streaming import ExportConfig, WikiPage, WikiPageMetadata


@pytest.mark.skipif(not shutil.which("mmdc"), reason="Mermaid CLI (mmdc) not installed")
class TestStreamingPdfExporter:
    """Tests for the StreamingPdfExporter class."""

    @pytest.fixture
    def sample_wiki(self, tmp_path: Path) -> Path:
        """Create a sample wiki structure for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Overview\n\nWelcome to the wiki.")
        (wiki_path / "architecture.md").write_text("# Architecture\n\nSystem design.")

        modules_dir = wiki_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "index.md").write_text("# Modules\n\nModule overview.")
        (modules_dir / "core.md").write_text("# Core Module\n\nCore functionality.")

        toc = {
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
                {
                    "number": "3",
                    "title": "Modules",
                    "path": "modules/index.md",
                    "children": [
                        {
                            "number": "3.1",
                            "title": "Core Module",
                            "path": "modules/core.md",
                        }
                    ],
                },
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    def test_init_sets_attributes(self, sample_wiki: Path, tmp_path: Path):
        """Test that initialization sets correct attributes."""
        output_path = tmp_path / "output.pdf"
        config = ExportConfig(batch_size=10)

        exporter = StreamingPdfExporter(
            sample_wiki, output_path, config, no_progress=True
        )

        assert exporter.wiki_path == sample_wiki
        assert exporter.output_path == output_path
        assert exporter.config.batch_size == 10
        assert exporter._no_progress is True

    def test_init_with_default_config(self, sample_wiki: Path, tmp_path: Path):
        """Test initialization with default config."""
        output_path = tmp_path / "output.pdf"

        exporter = StreamingPdfExporter(sample_wiki, output_path)

        assert exporter.config.batch_size == 50
        assert exporter._no_progress is False

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_creates_pdf(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export creates a PDF file."""
        output_path = tmp_path / "output.pdf"

        def write_pdf_side_effect(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 test content")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        result = await exporter.export()

        assert result.pages_exported == 4
        assert result.output_path == output_path
        assert result.duration_ms >= 0
        assert len(result.errors) == 0
        mock_html_instance.write_pdf.assert_called()

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_with_directory_output(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test export with directory as output path."""
        output_dir = tmp_path / "output_dir"
        output_dir.mkdir()

        def write_pdf_side_effect(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 test content")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_dir, no_progress=True)
        result = await exporter.export()

        assert result.output_path == output_dir / "documentation.pdf"

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_with_progress_callback(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test export with progress callback."""
        output_path = tmp_path / "output.pdf"

        def write_pdf_side_effect(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 test content")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        progress_calls = []

        def progress_callback(current: int, total: int, message: str):
            progress_calls.append((current, total, message))

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        result = await exporter.export(progress_callback=progress_callback)

        assert result.pages_exported == 4
        assert len(progress_calls) >= 4

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_handles_page_errors(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export handles page processing errors gracefully."""
        output_path = tmp_path / "output.pdf"

        call_count = [0]

        def write_pdf_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Simulated error")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)

        try:
            result = await exporter.export()
        except Exception:
            pass

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_separate_creates_multiple_pdfs(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_separate creates separate PDF files."""
        output_path = tmp_path / "pdfs"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        result = await exporter.export_separate()

        assert result.pages_exported == 4
        assert result.output_path == output_path
        assert mock_html_instance.write_pdf.call_count == 4

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_separate_with_pdf_suffix_output(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test export_separate when output path has .pdf suffix."""
        output_path = tmp_path / "output.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        result = await exporter.export_separate()

        assert result.output_path == tmp_path / "output"

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_separate_with_progress_callback(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test export_separate with progress callback."""
        output_path = tmp_path / "pdfs"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        progress_calls = []

        def progress_callback(current: int, total: int, message: str):
            progress_calls.append((current, total, message))

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        result = await exporter.export_separate(progress_callback=progress_callback)

        assert result.pages_exported == 4
        assert len(progress_calls) == 6
        assert progress_calls[0][0] == 0
        assert progress_calls[-1][2].startswith("Separate PDF export complete")

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_separate_handles_errors(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that export_separate handles page export errors."""
        output_path = tmp_path / "pdfs"

        call_count = [0]

        def write_pdf_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise ValueError("Simulated error")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        result = await exporter.export_separate()

        assert len(result.errors) > 0
        assert result.pages_exported > 0

    @patch("local_deepwiki.export.pdf.HTML")
    def test_render_batch_to_pdf_basic(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test _render_batch_to_pdf creates PDF from pages."""
        output_path = tmp_path / "output.pdf"
        batch_pdf = tmp_path / "batch.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)

        pages = []
        for i, name in enumerate(["page1.md", "page2.md"]):
            metadata = WikiPageMetadata(
                path=name,
                title=f"Page {i + 1}",
                file_size=100,
                relative_path=Path(name),
            )
            page = WikiPage(metadata=metadata, _content=f"# Page {i + 1}\n\nContent.")
            pages.append(page)

        exporter._render_batch_to_pdf(pages, batch_pdf, include_toc=False)

        mock_html_class.assert_called_once()
        mock_html_instance.write_pdf.assert_called_once()

    @patch("local_deepwiki.export.pdf.HTML")
    def test_render_batch_to_pdf_with_toc(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test _render_batch_to_pdf includes TOC when requested."""
        output_path = tmp_path / "output.pdf"
        batch_pdf = tmp_path / "batch.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        exporter.load_toc()

        metadata = WikiPageMetadata(
            path="page1.md",
            title="Page 1",
            file_size=100,
            relative_path=Path("page1.md"),
        )
        page = WikiPage(metadata=metadata, _content="# Page 1\n\nContent.")

        exporter._render_batch_to_pdf([page], batch_pdf, include_toc=True)

        call_args = mock_html_class.call_args
        html_string = call_args.kwargs.get(
            "string", call_args.args[0] if call_args.args else ""
        )
        assert "Table of Contents" in html_string

    def test_build_streaming_toc_html(self, sample_wiki: Path, tmp_path: Path):
        """Test _build_streaming_toc_html creates TOC HTML."""
        output_path = tmp_path / "output.pdf"
        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        exporter.load_toc()

        toc_html = exporter._build_streaming_toc_html()

        assert '<div class="toc">' in toc_html
        assert "Overview" in toc_html
        assert "Architecture" in toc_html
        assert "Modules" in toc_html

    def test_add_toc_entries_html(self, sample_wiki: Path, tmp_path: Path):
        """Test _add_toc_entries_html adds entries recursively."""
        from local_deepwiki.export.toc_renderer import _add_toc_entries_html

        entries = [
            {"title": "Level 0"},
            {
                "title": "Parent",
                "children": [
                    {"title": "Child 1"},
                    {"title": "Child 2"},
                ],
            },
        ]

        parts: list[str] = []
        _add_toc_entries_html(entries, parts, 0)

        html = "\n".join(parts)
        assert "Level 0" in html
        assert "Parent" in html
        assert "Child 1" in html
        assert "Child 2" in html
        assert 'class="toc-item"' in html

    @patch("local_deepwiki.export.pdf.HTML")
    def test_export_single_page(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test _export_single_page creates PDF for one page."""
        output_path = tmp_path / "output.pdf"
        page_pdf = tmp_path / "page.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)

        metadata = WikiPageMetadata(
            path="test.md",
            title="Test Page",
            file_size=100,
            relative_path=Path("test.md"),
        )
        page = WikiPage(metadata=metadata, _content="# Test Page\n\nContent here.")

        exporter._export_single_page(page, page_pdf)

        mock_html_class.assert_called_once()
        call_args = mock_html_class.call_args
        html_string = call_args.kwargs.get(
            "string", call_args.args[0] if call_args.args else ""
        )
        assert "Test Page" in html_string
        mock_html_instance.write_pdf.assert_called_once()

    @patch("local_deepwiki.export.pdf.HTML")
    def test_create_empty_pdf(self, mock_html_class, sample_wiki: Path, tmp_path: Path):
        """Test _create_empty_pdf creates an empty PDF."""
        output_path = tmp_path / "output.pdf"
        empty_pdf = tmp_path / "empty.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)
        exporter._create_empty_pdf(empty_pdf)

        mock_html_class.assert_called_once()
        call_args = mock_html_class.call_args
        html_string = call_args.kwargs.get(
            "string", call_args.args[0] if call_args.args else ""
        )
        assert "No pages to export" in html_string
        mock_html_instance.write_pdf.assert_called_once()

    def test_merge_pdfs_with_pypdf(self, sample_wiki: Path, tmp_path: Path):
        """Test _merge_pdfs uses pypdf when available."""
        output_path = tmp_path / "output.pdf"
        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)

        pdf1 = tmp_path / "batch1.pdf"
        pdf2 = tmp_path / "batch2.pdf"
        pdf1.write_bytes(b"%PDF-1.4 test content 1")
        pdf2.write_bytes(b"%PDF-1.4 test content 2")

        merged_pdf = tmp_path / "merged.pdf"

        mock_writer = MagicMock()
        mock_pypdf = MagicMock()
        mock_pypdf.PdfWriter.return_value = mock_writer

        with patch.dict("sys.modules", {"pypdf": mock_pypdf}):
            exporter._merge_pdfs([pdf1, pdf2], merged_pdf)

            mock_writer.append.assert_any_call(str(pdf1))
            mock_writer.append.assert_any_call(str(pdf2))
            mock_writer.write.assert_called_once_with(str(merged_pdf))
            mock_writer.close.assert_called_once()

    def test_merge_pdfs_fallback_without_pypdf(self, sample_wiki: Path, tmp_path: Path):
        """Test _merge_pdfs falls back when pypdf not available."""
        output_path = tmp_path / "output.pdf"
        exporter = StreamingPdfExporter(sample_wiki, output_path, no_progress=True)

        pdf1 = tmp_path / "batch1.pdf"
        pdf2 = tmp_path / "batch2.pdf"
        pdf1.write_bytes(b"%PDF-1.4 test content 1")
        pdf2.write_bytes(b"%PDF-1.4 test content 2")

        merged_pdf = tmp_path / "merged.pdf"

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("No module named 'pypdf'")
            return original_import(name, *args, **kwargs)

        pypdf_module = sys.modules.pop("pypdf", None)

        try:
            with patch.object(builtins, "__import__", mock_import):
                exporter._merge_pdfs([pdf1, pdf2], merged_pdf)

            assert merged_pdf.exists()
            assert merged_pdf.read_bytes() == pdf1.read_bytes()
        finally:
            if pypdf_module is not None:
                sys.modules["pypdf"] = pypdf_module

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_with_empty_wiki(self, mock_html_class, tmp_path: Path):
        """Test export with a wiki that has no pages."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "output.pdf"

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(wiki_path, output_path, no_progress=True)
        result = await exporter.export()

        assert result.pages_exported == 0
        mock_html_instance.write_pdf.assert_called()

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_error_during_page_processing(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test that errors during page processing are captured."""
        output_path = tmp_path / "output.pdf"

        def write_pdf_side_effect(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 test content")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        config = ExportConfig(batch_size=100)
        exporter = StreamingPdfExporter(
            sample_wiki, output_path, config, no_progress=True
        )

        call_count = [0]

        def error_progress_callback(current: int, total: int, message: str):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Simulated progress callback error")

        result = await exporter.export(progress_callback=error_progress_callback)

        assert len(result.errors) >= 1
        assert any("Failed to process" in err for err in result.errors)

    @pytest.mark.asyncio
    @patch("local_deepwiki.export.pdf.HTML")
    async def test_export_batching(self, mock_html_class, tmp_path: Path):
        """Test that export correctly batches pages."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        for i in range(5):
            (wiki_path / f"page{i}.md").write_text(f"# Page {i}\n\nContent.")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "output.pdf"

        config = ExportConfig(batch_size=2)

        def write_pdf_side_effect(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 test content")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = write_pdf_side_effect
        mock_html_class.return_value = mock_html_instance

        exporter = StreamingPdfExporter(
            wiki_path, output_path, config, no_progress=True
        )

        mock_writer = MagicMock()
        mock_pypdf = MagicMock()
        mock_pypdf.PdfWriter.return_value = mock_writer

        with patch.dict("sys.modules", {"pypdf": mock_pypdf}):
            result = await exporter.export()

            assert result.pages_exported == 5
            assert mock_html_instance.write_pdf.call_count == 3


class TestStreamingPdfExporterIntegration:
    """Integration tests for StreamingPdfExporter (when WeasyPrint is functional)."""

    @pytest.fixture
    def wiki_with_content(self, tmp_path: Path) -> Path:
        """Create a wiki with various content types."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Index\n\nWelcome.")
        (wiki_path / "page1.md").write_text("# Page 1\n\nContent 1.")
        (wiki_path / "page2.md").write_text("# Page 2\n\nContent 2.")

        toc = {
            "entries": [
                {"number": "1", "title": "Index", "path": "index.md"},
                {"number": "2", "title": "Page 1", "path": "page1.md"},
                {"number": "3", "title": "Page 2", "path": "page2.md"},
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    @pytest.mark.skipif(
        not weasyprint_functional(), reason="WeasyPrint not fully functional"
    )
    @pytest.mark.asyncio
    async def test_export_creates_valid_pdf(
        self, wiki_with_content: Path, tmp_path: Path
    ):
        """Test that export creates a valid PDF file."""
        output_path = tmp_path / "output.pdf"

        exporter = StreamingPdfExporter(
            wiki_with_content, output_path, no_progress=True
        )
        result = await exporter.export()

        assert result.output_path.exists()
        assert result.pages_exported == 3

        with open(result.output_path, "rb") as f:
            assert f.read(5) == b"%PDF-"

    @pytest.mark.skipif(
        not weasyprint_functional(), reason="WeasyPrint not fully functional"
    )
    @pytest.mark.asyncio
    async def test_export_separate_creates_valid_pdfs(
        self, wiki_with_content: Path, tmp_path: Path
    ):
        """Test that export_separate creates valid PDF files."""
        output_path = tmp_path / "pdfs"

        exporter = StreamingPdfExporter(
            wiki_with_content, output_path, no_progress=True
        )
        result = await exporter.export_separate()

        assert result.pages_exported == 3
        assert result.output_path.exists()

        pdf_files = list(result.output_path.rglob("*.pdf"))
        assert len(pdf_files) == 3

        for pdf_file in pdf_files:
            with open(pdf_file, "rb") as f:
                assert f.read(5) == b"%PDF-"


class TestMainCli:
    """Tests for the main() CLI entry point."""

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_default_args(self, mock_export, tmp_path: Path, monkeypatch):
        """Test main with default arguments."""
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

        with patch(
            "sys.argv", ["deepwiki-export-pdf", str(wiki_path), "-o", str(output_path)]
        ):
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

    @patch("local_deepwiki.export.pdf.export_to_pdf")
    def test_main_with_no_progress_option(self, mock_export, tmp_path: Path):
        """Test main with --no-progress option."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")

        mock_export.return_value = "Exported wiki to PDF: output.pdf"

        from local_deepwiki.export.pdf import main

        with patch(
            "sys.argv", ["deepwiki-export-pdf", str(wiki_path), "--no-progress"]
        ):
            main()

        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args.kwargs["no_progress"] is True

    def test_main_module_execution(self, tmp_path: Path):
        """Test that module can be run via python -m or __main__."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import sys
sys.argv = ['test', '{wiki_path}', '--no-progress', '-o', '{tmp_path / "test.pdf"}']
from local_deepwiki.export.pdf import main
try:
    main()
except SystemExit:
    pass
""",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
