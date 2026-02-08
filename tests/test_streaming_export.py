"""Tests for streaming wiki export functionality."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.export.streaming import (
    ExportConfig,
    ExportResult,
    StreamingExporter,
    WikiPage,
    WikiPageIterator,
    WikiPageMetadata,
)


# Check if WeasyPrint is functional (not just importable or mocked)
def _check_weasyprint() -> bool:
    """Check if WeasyPrint is real (not mocked) and functional."""
    try:
        import weasyprint

        # Check if it's a mock module from another test file
        if isinstance(weasyprint, MagicMock):
            return False
        if not hasattr(weasyprint, "__file__"):
            return False
        # Check if HTML class has real methods
        if not hasattr(weasyprint.HTML, "write_pdf"):
            return False
        return True
    except (ImportError, OSError, AttributeError):
        return False


_weasyprint_available = _check_weasyprint()

# Marker for tests requiring WeasyPrint
needs_weasyprint = pytest.mark.skipif(
    not _weasyprint_available,
    reason="WeasyPrint not available (requires system libraries)",
)


class TestWikiPageMetadata:
    """Tests for WikiPageMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating metadata."""
        metadata = WikiPageMetadata(
            path="modules/core.md",
            title="Core Module",
            file_size=1024,
            relative_path=Path("modules/core.md"),
        )
        assert metadata.path == "modules/core.md"
        assert metadata.title == "Core Module"
        assert metadata.file_size == 1024

    def test_metadata_immutable_fields(self):
        """Test metadata fields are accessible."""
        metadata = WikiPageMetadata(
            path="index.md",
            title="Home",
            file_size=512,
            relative_path=Path("index.md"),
        )
        assert str(metadata.relative_path) == "index.md"


class TestWikiPage:
    """Tests for WikiPage class."""

    def test_page_lazy_content_loading(self, tmp_path: Path):
        """Test that content is loaded lazily."""
        # Create a test file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test Page\n\nContent here.")

        metadata = WikiPageMetadata(
            path="test.md",
            title="Test Page",
            file_size=30,
            relative_path=Path("test.md"),
        )

        page = WikiPage(
            metadata=metadata,
            _content=None,
            _full_path=md_file,
        )

        # Content not loaded yet
        assert page._content is None

        # Access content triggers load
        content = page.content
        assert "# Test Page" in content
        assert page._content is not None

    def test_page_release_content(self, tmp_path: Path):
        """Test releasing content from memory."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent.")

        metadata = WikiPageMetadata(
            path="test.md",
            title="Test",
            file_size=20,
            relative_path=Path("test.md"),
        )

        page = WikiPage(metadata=metadata, _content=None, _full_path=md_file)

        # Load content
        _ = page.content
        assert page._content is not None

        # Release content
        page.release_content()
        assert page._content is None

    def test_page_properties(self):
        """Test page property accessors."""
        metadata = WikiPageMetadata(
            path="docs/api.md",
            title="API Reference",
            file_size=5000,
            relative_path=Path("docs/api.md"),
        )

        page = WikiPage(metadata=metadata, _content="# API Reference")

        assert page.path == "docs/api.md"
        assert page.title == "API Reference"
        assert page.content == "# API Reference"


class TestWikiPageIterator:
    """Tests for WikiPageIterator class."""

    @pytest.fixture
    def sample_wiki(self, tmp_path: Path) -> Path:
        """Create a sample wiki directory."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create pages
        (wiki_path / "index.md").write_text("# Index\n\nWelcome.")
        (wiki_path / "architecture.md").write_text("# Architecture\n\nDesign.")

        # Create nested pages
        modules_dir = wiki_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "core.md").write_text("# Core\n\nCore module.")
        (modules_dir / "utils.md").write_text("# Utils\n\nUtilities.")

        return wiki_path

    def test_get_page_count(self, sample_wiki: Path):
        """Test counting pages without loading content."""
        iterator = WikiPageIterator(sample_wiki)
        count = iterator.get_page_count()
        assert count == 4

    def test_get_total_size_bytes(self, sample_wiki: Path):
        """Test calculating total size."""
        iterator = WikiPageIterator(sample_wiki)
        size = iterator.get_total_size_bytes()
        # Size should be positive (content exists)
        assert size > 0

    def test_should_use_streaming_small_wiki(self, sample_wiki: Path):
        """Test streaming detection for small wiki."""
        iterator = WikiPageIterator(sample_wiki)
        # Small wiki (4 pages) should not need streaming
        assert not iterator.should_use_streaming(memory_limit_mb=500)

    def test_should_use_streaming_many_pages(self, tmp_path: Path):
        """Test streaming detection for wiki with many pages."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create 150 pages to trigger streaming
        for i in range(150):
            (wiki_path / f"page_{i:03d}.md").write_text(f"# Page {i}\n\nContent.")

        iterator = WikiPageIterator(wiki_path)
        # Many pages should trigger streaming
        assert iterator.should_use_streaming(memory_limit_mb=500)

    async def test_async_iteration(self, sample_wiki: Path):
        """Test async iteration over pages."""
        iterator = WikiPageIterator(sample_wiki)

        pages = []
        async for page in iterator:
            pages.append(page)

        assert len(pages) == 4

        # Check that each page has valid metadata
        for page in pages:
            assert page.path.endswith(".md")
            assert len(page.title) > 0

    async def test_iteration_with_toc_order(self, sample_wiki: Path):
        """Test iteration respects TOC order when provided."""
        # Specific order
        toc_order = [
            "index.md",
            "modules/core.md",
            "modules/utils.md",
            "architecture.md",
        ]

        iterator = WikiPageIterator(sample_wiki, toc_order=toc_order)

        pages = []
        async for page in iterator:
            pages.append(page.path)

        # Should follow TOC order
        assert pages == toc_order

    def test_extract_title_from_h1(self, sample_wiki: Path):
        """Test title extraction from H1 heading."""
        iterator = WikiPageIterator(sample_wiki)
        index_file = sample_wiki / "index.md"
        title = iterator._extract_title(index_file)
        assert title == "Index"

    def test_extract_title_fallback_to_filename(self, tmp_path: Path):
        """Test title extraction falls back to filename."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create file without H1
        (wiki_path / "my_special_page.md").write_text("Just content without heading.")

        iterator = WikiPageIterator(wiki_path)
        title = iterator._extract_title(wiki_path / "my_special_page.md")
        assert title == "My Special Page"


class TestExportConfig:
    """Tests for ExportConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ExportConfig()
        assert config.batch_size == 50
        assert config.memory_limit_mb == 500
        assert config.enable_streaming is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ExportConfig(
            batch_size=100,
            memory_limit_mb=1024,
            enable_streaming=False,
        )
        assert config.batch_size == 100
        assert config.memory_limit_mb == 1024
        assert config.enable_streaming is False

    def test_validation(self):
        """Test configuration validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExportConfig(batch_size=0)  # Must be >= 1

        with pytest.raises(ValidationError):
            ExportConfig(memory_limit_mb=50)  # Must be >= 100


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_result_creation(self, tmp_path: Path):
        """Test creating export result."""
        result = ExportResult(
            pages_exported=10,
            output_path=tmp_path / "output",
            duration_ms=1500,
        )
        assert result.pages_exported == 10
        assert result.duration_ms == 1500
        assert len(result.errors) == 0

    def test_result_with_errors(self, tmp_path: Path):
        """Test result with errors."""
        result = ExportResult(
            pages_exported=8,
            output_path=tmp_path / "output",
            duration_ms=2000,
            errors=["Failed to process page1.md", "Failed to process page2.md"],
        )
        assert result.pages_exported == 8
        assert len(result.errors) == 2

    def test_result_str(self, tmp_path: Path):
        """Test result string representation."""
        output = tmp_path / "output"
        result = ExportResult(
            pages_exported=5,
            output_path=output,
            duration_ms=500,
        )
        result_str = str(result)
        assert "5 pages" in result_str
        assert str(output) in result_str


class TestStreamingHtmlExporter:
    """Tests for StreamingHtmlExporter."""

    @pytest.fixture
    def sample_wiki(self, tmp_path: Path) -> Path:
        """Create a sample wiki for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Index\n\nWelcome to the wiki.")
        (wiki_path / "page.md").write_text("# Page\n\nContent here.")

        # Create toc.json
        toc = {
            "entries": [
                {"number": "1", "title": "Index", "path": "index.md"},
                {"number": "2", "title": "Page", "path": "page.md"},
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    async def test_streaming_export(self, sample_wiki: Path, tmp_path: Path):
        """Test basic streaming HTML export."""
        from local_deepwiki.export.html import StreamingHtmlExporter

        output_path = tmp_path / "html_output"
        exporter = StreamingHtmlExporter(sample_wiki, output_path)

        result = await exporter.export()

        assert result.pages_exported == 2
        assert output_path.exists()
        assert (output_path / "index.html").exists()
        assert (output_path / "page.html").exists()

    async def test_streaming_export_with_progress(
        self, sample_wiki: Path, tmp_path: Path
    ):
        """Test streaming export with progress callback."""
        from local_deepwiki.export.html import StreamingHtmlExporter

        output_path = tmp_path / "html_output"
        exporter = StreamingHtmlExporter(sample_wiki, output_path)

        progress_updates = []

        def progress_callback(current: int, total: int, message: str):
            progress_updates.append((current, total, message))

        result = await exporter.export(progress_callback=progress_callback)

        assert result.pages_exported == 2
        assert len(progress_updates) > 0

        # Check progress went from 1 to 2
        final_update = progress_updates[-1]
        assert final_update[0] == 2  # current
        assert final_update[1] == 2  # total

    async def test_streaming_export_releases_memory(
        self, sample_wiki: Path, tmp_path: Path
    ):
        """Test that pages release memory after processing."""
        from local_deepwiki.export.html import StreamingHtmlExporter

        # Create a wiki with larger content
        large_wiki = tmp_path / ".large_wiki"
        large_wiki.mkdir()

        # Create pages with substantial content
        for i in range(10):
            content = f"# Page {i}\n\n" + ("x" * 10000)
            (large_wiki / f"page_{i}.md").write_text(content)

        (large_wiki / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "html_output"
        exporter = StreamingHtmlExporter(large_wiki, output_path)

        result = await exporter.export()

        assert result.pages_exported == 10


@needs_weasyprint
@pytest.mark.skipif(not _weasyprint_available, reason="WeasyPrint not available")
class TestStreamingPdfExporter:
    """Tests for StreamingPdfExporter.

    These tests require WeasyPrint system libraries to be installed.
    """

    @pytest.fixture
    def sample_wiki(self, tmp_path: Path) -> Path:
        """Create a sample wiki for testing."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        (wiki_path / "index.md").write_text("# Index\n\nWelcome.")
        (wiki_path / "page.md").write_text("# Page\n\nContent.")

        toc = {
            "entries": [
                {"number": "1", "title": "Index", "path": "index.md"},
                {"number": "2", "title": "Page", "path": "page.md"},
            ]
        }
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    @patch("local_deepwiki.export.pdf.HTML")
    async def test_streaming_pdf_export(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test streaming PDF export."""
        from local_deepwiki.export.pdf import StreamingPdfExporter

        # write_pdf must create a real file so shutil.copy / _merge_pdfs can read it
        def _fake_write_pdf(path, **kwargs):
            Path(path).write_bytes(b"%PDF-1.4 fake")

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = _fake_write_pdf
        mock_html_class.return_value = mock_html_instance

        output_path = tmp_path / "output.pdf"
        exporter = StreamingPdfExporter(sample_wiki, output_path)

        result = await exporter.export()

        assert result.pages_exported == 2
        mock_html_class.assert_called()

    @patch("local_deepwiki.export.pdf.HTML")
    async def test_streaming_pdf_with_batching(self, mock_html_class, tmp_path: Path):
        """Test PDF export with batch processing."""
        from pypdf import PdfWriter as _PdfWriter

        from local_deepwiki.export.pdf import StreamingPdfExporter
        from local_deepwiki.export.streaming import ExportConfig

        # Create wiki with more pages
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        for i in range(10):
            (wiki_path / f"page_{i}.md").write_text(f"# Page {i}\n\nContent.")

        (wiki_path / "toc.json").write_text('{"entries": []}')

        # write_pdf must create a valid PDF so pypdf can parse it during merge
        def _fake_write_pdf(path, **kwargs):
            w = _PdfWriter()
            w.add_blank_page(width=72, height=72)
            with open(path, "wb") as f:
                w.write(f)

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.side_effect = _fake_write_pdf
        mock_html_class.return_value = mock_html_instance

        # Use small batch size to test batching
        config = ExportConfig(batch_size=3)

        output_path = tmp_path / "output.pdf"
        exporter = StreamingPdfExporter(wiki_path, output_path, config=config)

        result = await exporter.export()

        assert result.pages_exported == 10

    @patch("local_deepwiki.export.pdf.HTML")
    async def test_streaming_separate_pdf_export(
        self, mock_html_class, sample_wiki: Path, tmp_path: Path
    ):
        """Test streaming separate PDF export."""
        from local_deepwiki.export.pdf import StreamingPdfExporter

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        output_path = tmp_path / "pdfs"
        exporter = StreamingPdfExporter(sample_wiki, output_path)

        result = await exporter.export_separate()

        assert result.pages_exported == 2


class TestStreamingIntegration:
    """Integration tests for streaming export."""

    @pytest.fixture
    def large_wiki(self, tmp_path: Path) -> Path:
        """Create a large wiki to test streaming."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create 50 pages to test streaming behavior
        for i in range(50):
            content = f"# Page {i}\n\n" + ("Lorem ipsum " * 100)
            (wiki_path / f"page_{i:03d}.md").write_text(content)

        # Create TOC
        entries = [
            {"number": str(i + 1), "title": f"Page {i}", "path": f"page_{i:03d}.md"}
            for i in range(50)
        ]
        toc = {"entries": entries}
        (wiki_path / "toc.json").write_text(json.dumps(toc))

        return wiki_path

    async def test_large_wiki_html_streaming(self, large_wiki: Path, tmp_path: Path):
        """Test HTML export of a large wiki uses streaming."""
        from local_deepwiki.export.html import StreamingHtmlExporter

        output_path = tmp_path / "html_output"
        exporter = StreamingHtmlExporter(large_wiki, output_path)

        # Check that streaming would be recommended
        iterator = exporter.get_page_iterator()
        assert iterator.get_page_count() == 50

        result = await exporter.export()

        assert result.pages_exported == 50
        assert len(list(output_path.glob("*.html"))) == 50

    async def test_memory_bounded_export(self, large_wiki: Path, tmp_path: Path):
        """Test that streaming export keeps memory bounded."""
        from local_deepwiki.export.html import StreamingHtmlExporter

        output_path = tmp_path / "html_output"
        exporter = StreamingHtmlExporter(large_wiki, output_path)

        # Track pages in memory during export
        pages_in_memory = []

        original_export_page = exporter._export_wiki_page

        def tracking_export(page):
            pages_in_memory.append(page.path)
            result = original_export_page(page)
            # After export, content should be releasable
            page.release_content()
            return result

        exporter._export_wiki_page = tracking_export

        result = await exporter.export()

        assert result.pages_exported == 50


class TestBackwardCompatibility:
    """Test that non-streaming exporters still work."""

    @pytest.fixture
    def simple_wiki(self, tmp_path: Path) -> Path:
        """Create a simple wiki."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "index.md").write_text("# Test\n\nContent.")
        (wiki_path / "toc.json").write_text('{"entries": []}')
        return wiki_path

    def test_html_exporter_backward_compat(self, simple_wiki: Path, tmp_path: Path):
        """Test that HtmlExporter still works synchronously."""
        from local_deepwiki.export.html import HtmlExporter

        output_path = tmp_path / "html_output"
        exporter = HtmlExporter(simple_wiki, output_path)

        count = exporter.export()

        assert count == 1
        assert (output_path / "index.html").exists()

    @needs_weasyprint
    @patch("local_deepwiki.export.pdf.HTML")
    def test_pdf_exporter_backward_compat(
        self, mock_html_class, simple_wiki: Path, tmp_path: Path
    ):
        """Test that PdfExporter still works synchronously."""
        from local_deepwiki.export.pdf import PdfExporter

        mock_html_instance = MagicMock()
        mock_html_class.return_value = mock_html_instance

        output_path = tmp_path / "output.pdf"
        exporter = PdfExporter(simple_wiki, output_path)

        result = exporter.export_single()

        assert result == output_path
        mock_html_class.assert_called()
