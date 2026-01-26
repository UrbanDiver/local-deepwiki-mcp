"""Export functionality for DeepWiki documentation."""

from local_deepwiki.export.html import HtmlExporter, StreamingHtmlExporter, export_to_html
from local_deepwiki.export.streaming import (
    ExportConfig,
    ExportResult,
    ProgressCallback,
    StreamingExporter,
    WikiPage,
    WikiPageIterator,
    WikiPageMetadata,
)

# Lazy imports for PDF functionality (requires WeasyPrint system dependencies)
# Import these directly from export.pdf when needed


def __getattr__(name: str):
    """Lazy import PDF-related symbols to avoid WeasyPrint import errors."""
    pdf_symbols = {
        "PdfExporter",
        "StreamingPdfExporter",
        "export_to_pdf",
        "is_mmdc_available",
        "render_mermaid_to_png",
        "render_mermaid_to_svg",
    }
    if name in pdf_symbols:
        from local_deepwiki.export import pdf

        return getattr(pdf, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
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
