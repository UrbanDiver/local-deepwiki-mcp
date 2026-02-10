"""Tests for export progress reporting."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from local_deepwiki.export.html import StreamingHtmlExporter, export_to_html
from local_deepwiki.export.streaming import ExportConfig

# Try to import PDF export, skip tests if WeasyPrint not available
try:
    from local_deepwiki.export.pdf import StreamingPdfExporter, export_to_pdf

    PDF_AVAILABLE = True
except (ImportError, OSError):
    PDF_AVAILABLE = False
    StreamingPdfExporter = None
    export_to_pdf = None


@pytest.fixture
def temp_wiki(tmp_path):
    """Create a temporary wiki directory with test pages."""
    wiki_path = tmp_path / ".deepwiki"
    wiki_path.mkdir()

    # Create test pages
    for i in range(5):
        page = wiki_path / f"page{i}.md"
        page.write_text(f"# Page {i}\n\nContent for page {i}")

    # Create TOC
    toc = wiki_path / "toc.json"
    toc.write_text('{"entries": []}')

    return wiki_path


@pytest.fixture
def mock_progress_callback():
    """Create a mock progress callback."""
    return Mock()


class TestHtmlExportProgress:
    """Tests for HTML export progress reporting."""

    async def test_html_export_reports_total_at_start(
        self, temp_wiki, mock_progress_callback
    ):
        """HTML export should report total page count at start."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # First call should report start with total
        first_call = mock_progress_callback.call_args_list[0]
        current, total, message = first_call[0]
        assert current == 0
        assert total == 5  # 5 test pages
        assert "Starting HTML export" in message
        assert "5 pages" in message

    async def test_html_export_reports_each_page(
        self, temp_wiki, mock_progress_callback
    ):
        """HTML export should report progress for each page."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # Should have calls for: start + 5 pages + completion = 7 calls
        assert mock_progress_callback.call_count == 7

        # Check middle calls report correct progress
        for i in range(1, 6):  # Pages 1-5
            call_args = mock_progress_callback.call_args_list[i]
            current, total, message = call_args[0]
            assert current == i
            assert total == 5
            assert "page" in message.lower()

    async def test_html_export_reports_completion(
        self, temp_wiki, mock_progress_callback
    ):
        """HTML export should report completion."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # Last call should report completion
        last_call = mock_progress_callback.call_args_list[-1]
        current, total, message = last_call[0]
        assert current == 5
        assert total == 5
        assert "complete" in message.lower()

    async def test_html_export_works_without_callback(self, temp_wiki):
        """HTML export should work when no callback is provided (backward compat)."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        # Should not raise any errors
        result = await exporter.export(progress_callback=None)

        assert result.pages_exported == 5
        assert result.output_path == output_path

    async def test_html_export_continues_on_page_error(
        self, temp_wiki, mock_progress_callback
    ):
        """HTML export should continue and report progress even if a page fails."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        # Mock _export_wiki_page to fail on page 2
        original_export = exporter._export_wiki_page

        def mock_export(page):
            if "page2" in page.path:
                raise ValueError("Test error")
            return original_export(page)

        exporter._export_wiki_page = mock_export

        result = await exporter.export(progress_callback=mock_progress_callback)

        # Should report: start + 4 successful pages + completion = 6 calls
        # (Failed page doesn't get progress callback since export failed before that point)
        assert mock_progress_callback.call_count == 6
        assert result.pages_exported == 4  # 5 - 1 failed
        assert len(result.errors) == 1

    def test_html_export_wrapper_function(self, temp_wiki):
        """Test the export_to_html wrapper function."""
        output_path = temp_wiki.parent / "html_export"

        result = export_to_html(temp_wiki, output_path)

        assert "5 pages" in result
        assert str(output_path) in result


def _make_write_pdf_side_effect():
    """Create a side_effect for write_pdf that creates a minimal valid PDF."""

    def _write_pdf(path, **kwargs):
        Path(path).write_bytes(
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
            b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
        )

    return _write_pdf


@pytest.fixture
def _patch_pdf_html(monkeypatch):
    """Patch HTML and CSS so write_pdf creates a real file on disk."""
    from unittest.mock import MagicMock

    mock_html_cls = MagicMock()
    mock_html_instance = MagicMock()
    mock_html_instance.write_pdf.side_effect = _make_write_pdf_side_effect()
    mock_html_cls.return_value = mock_html_instance

    mock_css_cls = MagicMock()

    monkeypatch.setattr("local_deepwiki.export.pdf.HTML", mock_html_cls)
    monkeypatch.setattr("local_deepwiki.export.pdf.CSS", mock_css_cls)
    return mock_html_cls, mock_css_cls


@pytest.mark.skipif(not PDF_AVAILABLE, reason="WeasyPrint not available")
class TestPdfExportProgress:
    """Tests for PDF export progress reporting."""

    async def test_pdf_export_reports_total_at_start(
        self, _patch_pdf_html, temp_wiki, mock_progress_callback
    ):
        """PDF export should report total page count at start."""
        output_path = temp_wiki.parent / "test.pdf"
        exporter = StreamingPdfExporter(temp_wiki, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # First call should report start with total
        first_call = mock_progress_callback.call_args_list[0]
        current, total, message = first_call[0]
        assert current == 0
        assert total == 5  # 5 test pages
        assert "Starting PDF export" in message
        assert "5 pages" in message

    async def test_pdf_export_reports_each_page(
        self, _patch_pdf_html, temp_wiki, mock_progress_callback
    ):
        """PDF export should report progress for each page."""
        output_path = temp_wiki.parent / "test.pdf"
        exporter = StreamingPdfExporter(temp_wiki, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # Should have calls for: start + 5 pages + merge + completion
        assert mock_progress_callback.call_count >= 7

        # Check that page processing calls report correct progress
        page_calls = [
            c
            for c in mock_progress_callback.call_args_list
            if "processing page" in c[0][2].lower()
        ]
        assert len(page_calls) == 5

        for i, call_args in enumerate(page_calls):
            current, total, message = call_args[0]
            assert current == i + 1
            assert total == 5
            assert f"page {i + 1} of 5" in message.lower()

    async def test_pdf_export_reports_merging(
        self, _patch_pdf_html, temp_wiki, mock_progress_callback
    ):
        """PDF export should report merging phase."""
        output_path = temp_wiki.parent / "test.pdf"

        # Use smaller batch size to force merging
        config = ExportConfig(batch_size=2)
        exporter = StreamingPdfExporter(temp_wiki, output_path, config=config)

        await exporter.export(progress_callback=mock_progress_callback)

        # Look for merge message in calls
        merge_calls = [
            c
            for c in mock_progress_callback.call_args_list
            if "merging" in c[0][2].lower()
        ]
        assert len(merge_calls) >= 1

    async def test_pdf_export_reports_completion(
        self, _patch_pdf_html, temp_wiki, mock_progress_callback
    ):
        """PDF export should report completion."""
        output_path = temp_wiki.parent / "test.pdf"
        exporter = StreamingPdfExporter(temp_wiki, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # Last call should report completion
        last_call = mock_progress_callback.call_args_list[-1]
        current, total, message = last_call[0]
        assert current == 5
        assert total == 5
        assert "complete" in message.lower()

    async def test_pdf_export_works_without_callback(self, _patch_pdf_html, temp_wiki):
        """PDF export should work when no callback is provided (backward compat)."""
        output_path = temp_wiki.parent / "test.pdf"
        exporter = StreamingPdfExporter(temp_wiki, output_path)

        # Should not raise any errors
        result = await exporter.export(progress_callback=None)

        assert result.pages_exported == 5

    async def test_pdf_export_separate_reports_progress(
        self, _patch_pdf_html, temp_wiki, mock_progress_callback
    ):
        """PDF separate export should report progress for each file."""
        output_path = temp_wiki.parent / "pdfs"
        exporter = StreamingPdfExporter(temp_wiki, output_path)

        await exporter.export_separate(progress_callback=mock_progress_callback)

        # Should have calls for: start + 5 pages + completion = 7 calls
        assert mock_progress_callback.call_count == 7

        # First call: start
        first_call = mock_progress_callback.call_args_list[0]
        assert first_call[0][0] == 0  # current
        assert "separate" in first_call[0][2].lower()

        # Last call: completion
        last_call = mock_progress_callback.call_args_list[-1]
        assert last_call[0][0] == 5  # current
        assert "complete" in last_call[0][2].lower()

    def test_pdf_export_wrapper_function(self, _patch_pdf_html, temp_wiki):
        """Test the export_to_pdf wrapper function."""
        output_path = temp_wiki.parent / "test.pdf"

        result = export_to_pdf(temp_wiki, output_path, single_file=True)

        assert "pdf" in result.lower()


class TestProgressCallbackSignature:
    """Tests for progress callback signature and data."""

    async def test_callback_receives_correct_arguments(self, temp_wiki):
        """Progress callback should receive (current, total, message)."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        received_calls = []

        def callback(current, total, message):
            received_calls.append((current, total, message))

        await exporter.export(progress_callback=callback)

        # Verify all calls have correct structure
        for current, total, message in received_calls:
            assert isinstance(current, int)
            assert isinstance(total, int)
            assert isinstance(message, str)
            assert current >= 0
            assert total > 0
            assert current <= total
            assert len(message) > 0

    async def test_callback_message_includes_context(self, temp_wiki):
        """Progress messages should include helpful context."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        messages = []

        def callback(current, total, message):
            messages.append(message)

        await exporter.export(progress_callback=callback)

        # First message should mention starting
        assert any("starting" in m.lower() for m in messages)

        # Middle messages should mention pages/files
        assert any(
            "page" in m.lower() or "exported" in m.lower() for m in messages[1:-1]
        )

        # Last message should mention completion
        assert "complete" in messages[-1].lower()

    async def test_callback_counts_increase_monotonically(self, temp_wiki):
        """Current progress should increase monotonically."""
        output_path = temp_wiki.parent / "html_export"
        exporter = StreamingHtmlExporter(temp_wiki, output_path)

        counts = []

        def callback(current, total, message):
            counts.append(current)

        await exporter.export(progress_callback=callback)

        # Verify counts increase (or stay the same for merge/completion)
        for i in range(1, len(counts)):
            assert counts[i] >= counts[i - 1], "Progress should not decrease"

    @pytest.mark.skipif(not PDF_AVAILABLE, reason="WeasyPrint not available")
    async def test_pdf_callback_signature(self, _patch_pdf_html, temp_wiki):
        """PDF export callback should have same signature as HTML."""
        output_path = temp_wiki.parent / "test.pdf"
        exporter = StreamingPdfExporter(temp_wiki, output_path)

        received_calls = []

        def callback(current, total, message):
            received_calls.append((current, total, message))

        await exporter.export(progress_callback=callback)

        # Verify all calls have correct structure
        for current, total, message in received_calls:
            assert isinstance(current, int)
            assert isinstance(total, int)
            assert isinstance(message, str)
            assert current >= 0
            assert total > 0


class TestEdgeCases:
    """Tests for edge cases in progress reporting."""

    async def test_empty_wiki_progress(self, tmp_path, mock_progress_callback):
        """Progress reporting should work for empty wiki."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "html_export"
        exporter = StreamingHtmlExporter(wiki_path, output_path)

        result = await exporter.export(progress_callback=mock_progress_callback)

        assert result.pages_exported == 0
        # Should still have start and completion calls
        assert mock_progress_callback.call_count >= 2

    async def test_single_page_wiki_progress(self, tmp_path, mock_progress_callback):
        """Progress reporting should work for single-page wiki."""
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()
        (wiki_path / "page.md").write_text("# Page\n\nContent")
        (wiki_path / "toc.json").write_text('{"entries": []}')

        output_path = tmp_path / "html_export"
        exporter = StreamingHtmlExporter(wiki_path, output_path)

        await exporter.export(progress_callback=mock_progress_callback)

        # Should have: start + 1 page + completion = 3 calls
        assert mock_progress_callback.call_count == 3

        # Verify total is reported as 1
        for call in mock_progress_callback.call_args_list:
            _, total, _ = call[0]
            assert total == 1
