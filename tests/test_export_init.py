"""Tests for export module lazy imports."""

import pytest


class TestExportLazyImports:
    """Tests for lazy import functionality in export/__init__.py."""

    def test_lazy_import_pdf_exporter(self):
        """Test lazy import of PdfExporter."""
        from local_deepwiki import export

        # Access should trigger lazy import
        assert hasattr(export, "PdfExporter")
        exporter_class = export.PdfExporter
        assert exporter_class is not None

    def test_lazy_import_export_to_pdf(self):
        """Test lazy import of export_to_pdf."""
        from local_deepwiki import export

        assert hasattr(export, "export_to_pdf")
        func = export.export_to_pdf
        assert callable(func)

    def test_lazy_import_is_mmdc_available(self):
        """Test lazy import of is_mmdc_available."""
        from local_deepwiki import export

        assert hasattr(export, "is_mmdc_available")
        func = export.is_mmdc_available
        assert callable(func)

    def test_lazy_import_render_mermaid_to_png(self):
        """Test lazy import of render_mermaid_to_png."""
        from local_deepwiki import export

        assert hasattr(export, "render_mermaid_to_png")
        func = export.render_mermaid_to_png
        assert callable(func)

    def test_lazy_import_render_mermaid_to_svg(self):
        """Test lazy import of render_mermaid_to_svg."""
        from local_deepwiki import export

        assert hasattr(export, "render_mermaid_to_svg")
        func = export.render_mermaid_to_svg
        assert callable(func)

    def test_unknown_attribute_raises_error(self):
        """Test that unknown attribute raises AttributeError."""
        from local_deepwiki import export

        with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
            _ = export.nonexistent

    def test_html_exporter_direct_import(self):
        """Test that HtmlExporter is directly available (not lazy)."""
        from local_deepwiki.export import HtmlExporter

        assert HtmlExporter is not None

    def test_export_to_html_direct_import(self):
        """Test that export_to_html is directly available (not lazy)."""
        from local_deepwiki.export import export_to_html

        assert callable(export_to_html)

    def test_all_exports_listed(self):
        """Test that __all__ contains expected exports."""
        from local_deepwiki import export

        expected = [
            "HtmlExporter",
            "export_to_html",
            "PdfExporter",
            "export_to_pdf",
            "is_mmdc_available",
            "render_mermaid_to_png",
            "render_mermaid_to_svg",
        ]
        for name in expected:
            assert name in export.__all__
