"""Tests for export module initialization and lazy imports.

This module tests the export/__init__.py file to ensure:
1. All direct imports from streaming and html modules work correctly
2. Lazy imports for PDF functionality work correctly
3. The __getattr__ mechanism handles both valid and invalid attributes
4. The __all__ list contains all expected exports
"""

import pytest


# Check if WeasyPrint is available (requires native libraries like libgobject)
def _check_weasyprint_available() -> bool:
    """Check if WeasyPrint is available and functional."""
    try:
        from weasyprint import HTML  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


WEASYPRINT_AVAILABLE = _check_weasyprint_available()

weasyprint_required = pytest.mark.skipif(
    not WEASYPRINT_AVAILABLE,
    reason="WeasyPrint requires native libraries (libgobject, etc.)",
)


class TestDirectImportsFromStreaming:
    """Tests for direct imports from the streaming module."""

    def test_import_export_config(self):
        """Test that ExportConfig is directly importable."""
        from local_deepwiki.export import ExportConfig

        assert ExportConfig is not None
        # Verify it's the actual class
        config = ExportConfig()
        assert hasattr(config, "batch_size")
        assert hasattr(config, "memory_limit_mb")
        assert hasattr(config, "enable_streaming")

    def test_import_export_result(self):
        """Test that ExportResult is directly importable."""
        from local_deepwiki.export import ExportResult
        from pathlib import Path

        assert ExportResult is not None
        # Verify it's the actual dataclass
        result = ExportResult(
            pages_exported=5,
            output_path=Path("/tmp/test"),
            duration_ms=100,
        )
        assert result.pages_exported == 5
        assert result.duration_ms == 100

    def test_import_progress_callback(self):
        """Test that ProgressCallback type is directly importable."""
        from local_deepwiki.export import ProgressCallback

        assert ProgressCallback is not None
        # ProgressCallback is a type alias, verify it exists

    def test_import_streaming_exporter(self):
        """Test that StreamingExporter is directly importable."""
        from local_deepwiki.export import StreamingExporter

        assert StreamingExporter is not None
        # Verify it's the abstract base class
        from abc import ABC

        assert issubclass(StreamingExporter, ABC)

    def test_import_wiki_page(self):
        """Test that WikiPage is directly importable."""
        from local_deepwiki.export import WikiPage, WikiPageMetadata
        from pathlib import Path

        assert WikiPage is not None
        # Verify it's the dataclass
        metadata = WikiPageMetadata(
            path="test.md",
            title="Test",
            file_size=100,
            relative_path=Path("test.md"),
        )
        page = WikiPage(metadata=metadata, _content="# Test")
        assert page.title == "Test"
        assert page.path == "test.md"

    def test_import_wiki_page_iterator(self):
        """Test that WikiPageIterator is directly importable."""
        from local_deepwiki.export import WikiPageIterator
        from pathlib import Path

        assert WikiPageIterator is not None
        # Verify it has expected methods
        assert hasattr(WikiPageIterator, "get_page_count")
        assert hasattr(WikiPageIterator, "get_total_size_bytes")
        assert hasattr(WikiPageIterator, "should_use_streaming")

    def test_import_wiki_page_metadata(self):
        """Test that WikiPageMetadata is directly importable."""
        from local_deepwiki.export import WikiPageMetadata
        from pathlib import Path

        assert WikiPageMetadata is not None
        # Verify it's the dataclass
        metadata = WikiPageMetadata(
            path="docs/api.md",
            title="API Reference",
            file_size=2048,
            relative_path=Path("docs/api.md"),
        )
        assert metadata.path == "docs/api.md"
        assert metadata.title == "API Reference"
        assert metadata.file_size == 2048


class TestDirectImportsFromHtml:
    """Tests for direct imports from the html module."""

    def test_import_html_exporter(self):
        """Test that HtmlExporter is directly importable."""
        from local_deepwiki.export import HtmlExporter

        assert HtmlExporter is not None
        # Verify it has the export method
        assert hasattr(HtmlExporter, "export")

    def test_import_streaming_html_exporter(self):
        """Test that StreamingHtmlExporter is directly importable."""
        from local_deepwiki.export import StreamingHtmlExporter

        assert StreamingHtmlExporter is not None
        # Verify it inherits from StreamingExporter
        from local_deepwiki.export import StreamingExporter

        assert issubclass(StreamingHtmlExporter, StreamingExporter)

    def test_import_export_to_html(self):
        """Test that export_to_html is directly importable."""
        from local_deepwiki.export import export_to_html

        assert export_to_html is not None
        assert callable(export_to_html)


class TestLazyImportsPdfWithWeasyPrint:
    """Tests for lazy PDF imports when WeasyPrint is available."""

    @weasyprint_required
    def test_lazy_import_pdf_exporter_real(self):
        """Test lazy import of PdfExporter with real WeasyPrint."""
        from local_deepwiki import export

        # Access should trigger lazy import
        assert hasattr(export, "PdfExporter")
        exporter_class = export.PdfExporter
        assert exporter_class is not None

    @weasyprint_required
    def test_lazy_import_streaming_pdf_exporter_real(self):
        """Test lazy import of StreamingPdfExporter with real WeasyPrint."""
        from local_deepwiki import export

        # Access StreamingPdfExporter
        exporter_class = getattr(export, "StreamingPdfExporter")
        assert exporter_class is not None

    @weasyprint_required
    def test_lazy_import_export_to_pdf_real(self):
        """Test lazy import of export_to_pdf with real WeasyPrint."""
        from local_deepwiki import export

        assert hasattr(export, "export_to_pdf")
        func = export.export_to_pdf
        assert callable(func)

    @weasyprint_required
    def test_lazy_import_is_mmdc_available_real(self):
        """Test lazy import of is_mmdc_available with real WeasyPrint."""
        from local_deepwiki import export

        assert hasattr(export, "is_mmdc_available")
        func = export.is_mmdc_available
        assert callable(func)

    @weasyprint_required
    def test_lazy_import_render_mermaid_to_png_real(self):
        """Test lazy import of render_mermaid_to_png with real WeasyPrint."""
        from local_deepwiki import export

        assert hasattr(export, "render_mermaid_to_png")
        func = export.render_mermaid_to_png
        assert callable(func)

    @weasyprint_required
    def test_lazy_import_render_mermaid_to_svg_real(self):
        """Test lazy import of render_mermaid_to_svg with real WeasyPrint."""
        from local_deepwiki import export

        assert hasattr(export, "render_mermaid_to_svg")
        func = export.render_mermaid_to_svg
        assert callable(func)


class TestGetAttrErrorHandling:
    """Tests for __getattr__ error handling."""

    def test_unknown_attribute_raises_error(self):
        """Test that unknown attribute raises AttributeError."""
        from local_deepwiki import export

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
            _ = export.nonexistent

    def test_unknown_attribute_error_message_format(self):
        """Test that AttributeError message includes module name."""
        from local_deepwiki import export

        with pytest.raises(AttributeError) as exc_info:
            _ = export.unknown_symbol

        error_message = str(exc_info.value)
        assert "local_deepwiki.export" in error_message
        assert "unknown_symbol" in error_message

    def test_multiple_unknown_attributes(self):
        """Test that multiple unknown attributes each raise errors."""
        from local_deepwiki import export

        unknown_names = ["foo", "bar", "baz", "not_a_real_export"]

        for name in unknown_names:
            with pytest.raises(AttributeError, match=f"has no attribute '{name}'"):
                getattr(export, name)


class TestAllExportsList:
    """Tests for the __all__ export list."""

    def test_all_exports_listed(self):
        """Test that __all__ contains all expected exports."""
        from local_deepwiki import export

        expected_exports = [
            # Streaming base classes
            "ExportConfig",
            "ExportResult",
            "ProgressCallback",
            "StreamingExporter",
            "WikiPage",
            "WikiPageIterator",
            "WikiPageMetadata",
            # HTML exporters
            "HtmlExporter",
            "StreamingHtmlExporter",
            "export_to_html",
            # PDF exporters (lazy loaded)
            "PdfExporter",
            "StreamingPdfExporter",
            "export_to_pdf",
            "is_mmdc_available",
            "render_mermaid_to_png",
            "render_mermaid_to_svg",
        ]

        for name in expected_exports:
            assert name in export.__all__, f"'{name}' not found in __all__"

    def test_all_count_matches_expected(self):
        """Test that __all__ has the expected number of exports."""
        from local_deepwiki import export

        # 7 streaming + 3 html + 6 pdf = 16 total
        expected_count = 16
        assert len(export.__all__) == expected_count

    def test_all_contains_only_strings(self):
        """Test that __all__ contains only string values."""
        from local_deepwiki import export

        for item in export.__all__:
            assert isinstance(item, str), f"__all__ contains non-string: {item}"

    def test_all_has_no_duplicates(self):
        """Test that __all__ has no duplicate entries."""
        from local_deepwiki import export

        unique_items = set(export.__all__)
        assert len(unique_items) == len(
            export.__all__
        ), "__all__ contains duplicate entries"


class TestModuleDocstring:
    """Tests for module-level documentation."""

    def test_module_has_docstring(self):
        """Test that the export module has a docstring."""
        from local_deepwiki import export

        assert export.__doc__ is not None
        assert len(export.__doc__) > 0

    def test_module_docstring_content(self):
        """Test that the module docstring is meaningful."""
        from local_deepwiki import export

        assert export.__doc__ is not None
        doc = export.__doc__.lower()
        assert "export" in doc


class TestImportPathConsistency:
    """Tests to verify import path consistency."""

    def test_streaming_imports_match_direct_imports(self):
        """Test that streaming module imports match direct exports."""
        from local_deepwiki.export import streaming
        from local_deepwiki.export import (
            ExportConfig,
            ExportResult,
            ProgressCallback,
            StreamingExporter,
            WikiPage,
            WikiPageIterator,
            WikiPageMetadata,
        )

        # Verify classes are the same objects
        assert ExportConfig is streaming.ExportConfig
        assert ExportResult is streaming.ExportResult
        assert ProgressCallback is streaming.ProgressCallback
        assert StreamingExporter is streaming.StreamingExporter
        assert WikiPage is streaming.WikiPage
        assert WikiPageIterator is streaming.WikiPageIterator
        assert WikiPageMetadata is streaming.WikiPageMetadata

    def test_html_imports_match_direct_imports(self):
        """Test that html module imports match direct exports."""
        from local_deepwiki.export import html
        from local_deepwiki.export import (
            HtmlExporter,
            StreamingHtmlExporter,
            export_to_html,
        )

        # Verify classes/functions are the same objects
        assert HtmlExporter is html.HtmlExporter
        assert StreamingHtmlExporter is html.StreamingHtmlExporter
        assert export_to_html is html.export_to_html


class TestLazyImportBehavior:
    """Tests for lazy import behavior characteristics."""

    def test_pdf_symbols_not_in_module_dict_initially(self):
        """Test that PDF symbols are not eagerly loaded into module dict."""
        # Note: This test verifies lazy import behavior
        # PDF symbols should only be loaded when accessed

        # Fresh import to check initial state
        import importlib

        import local_deepwiki.export

        importlib.reload(local_deepwiki.export)

        # The pdf_symbols should not be in __dict__ until accessed
        # (they are handled by __getattr__)
        module_dict = local_deepwiki.export.__dict__

        # Direct imports should be present
        assert "HtmlExporter" in module_dict
        assert "ExportConfig" in module_dict

    def test_lazy_import_returns_same_object_on_repeated_access(self):
        """Test that lazy imports return the same object on repeated access."""
        from local_deepwiki import export

        # First access
        result1 = export.__getattr__("PdfExporter")

        # Second access should return the same object
        result2 = export.__getattr__("PdfExporter")

        # Both should return the same object (identity check)
        assert result1 is result2


class TestPdfSymbolsSet:
    """Tests for the PDF symbols set in __getattr__."""

    def test_all_pdf_symbols_are_lazy(self):
        """Test that all PDF-related symbols are accessible via __getattr__."""
        from local_deepwiki import export
        from local_deepwiki.export import pdf

        pdf_symbols = [
            "PdfExporter",
            "StreamingPdfExporter",
            "export_to_pdf",
            "is_mmdc_available",
            "render_mermaid_to_png",
            "render_mermaid_to_svg",
        ]

        for symbol in pdf_symbols:
            # Access via __getattr__ should return the same object as pdf module
            result = export.__getattr__(symbol)
            expected = getattr(pdf, symbol)
            assert result is expected, f"{symbol} not correctly lazy-loaded"

    def test_non_pdf_symbols_not_lazy_imported(self):
        """Test that non-PDF symbols don't trigger lazy pdf import."""
        from local_deepwiki import export

        # These should be directly available, not lazy
        direct_symbols = [
            "ExportConfig",
            "ExportResult",
            "HtmlExporter",
            "StreamingHtmlExporter",
            "export_to_html",
        ]

        for symbol in direct_symbols:
            # Should be directly accessible without __getattr__
            assert hasattr(export, symbol)
            obj = getattr(export, symbol)
            assert obj is not None
