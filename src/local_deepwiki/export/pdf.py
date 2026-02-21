"""PDF export functionality for DeepWiki documentation."""

from __future__ import annotations

import asyncio
import base64
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import markdown

try:
    from weasyprint import CSS, HTML
except ImportError:
    CSS = None  # fallback if weasyprint not installed
    HTML = None

from local_deepwiki.export.mermaid_renderer import (
    extract_mermaid_blocks,
    is_mmdc_available,
    render_mermaid_to_png,
    render_mermaid_to_svg,
)
from local_deepwiki.export.pdf_styles import PDF_HTML_TEMPLATE, PRINT_CSS
from local_deepwiki.export.shared import extract_title as _shared_extract_title
from local_deepwiki.export.streaming import (
    ExportConfig,
    ExportResult,
    ProgressCallback,
    StreamingExporter,
    WikiPage,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


def _require_weasyprint() -> None:
    """Raise a helpful error if WeasyPrint is not installed."""
    if HTML is None:
        raise ImportError(
            "WeasyPrint is required for PDF export but is not installed.\n"
            "Install with: uv pip install weasyprint\n"
            "See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
        )


def render_markdown_for_pdf(content: str, render_mermaid: bool = True) -> str:
    """Render markdown to HTML suitable for PDF.

    Args:
        content: Markdown content.
        render_mermaid: If True, attempt to render mermaid diagrams using CLI.
            Falls back to placeholder if CLI is not available.

    Returns:
        HTML string.
    """
    processed_content = content

    # Process mermaid blocks
    if render_mermaid and is_mmdc_available():
        # Try to render mermaid diagrams to PNG (better font support than SVG)
        mermaid_blocks = extract_mermaid_blocks(content)
        for full_block, diagram_code in mermaid_blocks:
            png_bytes = render_mermaid_to_png(diagram_code)
            if png_bytes:
                # Embed PNG as base64 data URI
                b64_data = base64.b64encode(png_bytes).decode("ascii")
                img_tag = f'<img src="data:image/png;base64,{b64_data}" alt="Mermaid diagram">'
                replacement = f'<div class="mermaid-diagram">{img_tag}</div>'
                processed_content = processed_content.replace(full_block, replacement)
            else:
                # Fall back to placeholder on render failure
                replacement = (
                    '<div class="mermaid-note">'
                    "[Diagram rendering failed - view in HTML version]"
                    "</div>"
                )
                processed_content = processed_content.replace(full_block, replacement)
    else:
        # No mermaid CLI - replace with placeholder notes
        lines = processed_content.split("\n")
        in_mermaid = False
        result_lines = []

        for line in lines:
            if line.strip() == "```mermaid":
                in_mermaid = True
                result_lines.append(
                    '<div class="mermaid-note">'
                    "[Diagram not available in PDF - view in HTML version]"
                    "</div>"
                )
            elif in_mermaid and line.strip() == "```":
                in_mermaid = False
            elif not in_mermaid:
                result_lines.append(line)

        processed_content = "\n".join(result_lines)

    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
        ]
    )
    return md.convert(processed_content)


def extract_title(md_file: Path) -> str:
    """Extract title from markdown file.

    Delegates to ``shared.extract_title``.

    Args:
        md_file: Path to markdown file.

    Returns:
        Extracted title or filename-based title.
    """
    return _shared_extract_title(md_file)


class StreamingPdfExporter(StreamingExporter):
    """Memory-efficient PDF exporter using streaming page iteration.

    Processes pages in batches, writes intermediate PDFs to temp files,
    then merges them at the end. Suitable for large wikis to avoid OOM.
    """

    def __init__(
        self,
        wiki_path: Path,
        output_path: Path,
        config: ExportConfig | None = None,
        *,
        no_progress: bool = False,
    ):
        """Initialize the streaming PDF exporter.

        Args:
            wiki_path: Path to the .deepwiki directory.
            output_path: Output path for PDF file(s).
            config: Export configuration.
            no_progress: If True, disable progress bars.
        """
        super().__init__(wiki_path, output_path, config)
        self._no_progress = no_progress

    async def export(
        self, progress_callback: ProgressCallback | None = None
    ) -> ExportResult:
        """Export wiki to PDF with streaming/batched processing.

        Args:
            progress_callback: Optional callback for progress updates.

        Returns:
            ExportResult with export statistics.
        """
        start_time = time.monotonic()
        errors: list[str] = []

        logger.info(
            "Starting streaming PDF export from %s to %s",
            self.wiki_path,
            self.output_path,
        )

        # Load TOC for ordering
        await asyncio.to_thread(self.load_toc)

        # Get page count for progress
        iterator = self.get_page_iterator()
        total_pages = iterator.get_page_count()

        # Report total pages at start
        if progress_callback:
            progress_callback(
                0, total_pages, f"Starting PDF export ({total_pages} pages)"
            )

        # Determine output file
        output_file = self.output_path
        if output_file.is_dir():
            output_file = output_file / "documentation.pdf"
        await asyncio.to_thread(output_file.parent.mkdir, parents=True, exist_ok=True)

        # Process pages in batches and create intermediate PDFs
        batch_size = self.config.batch_size
        batch_num = 0
        pages_processed = 0
        temp_pdfs: list[Path] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            batch_pages: list[WikiPage] = []

            async for page in iterator:
                try:
                    batch_pages.append(page)
                    pages_processed += 1

                    if progress_callback:
                        progress_callback(
                            pages_processed,
                            total_pages,
                            f"Processing page {pages_processed} of {total_pages}: {page.path}",
                        )

                    # When batch is full, render to intermediate PDF
                    if len(batch_pages) >= batch_size:
                        batch_pdf = temp_path / f"batch_{batch_num:04d}.pdf"
                        await asyncio.to_thread(
                            self._render_batch_to_pdf,
                            batch_pages,
                            batch_pdf,
                            batch_num == 0,
                        )
                        temp_pdfs.append(batch_pdf)

                        # Release memory
                        for p in batch_pages:
                            p.release_content()
                        batch_pages = []
                        batch_num += 1

                except Exception as e:
                    error_msg = f"Failed to process {page.path}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Process remaining pages
            if batch_pages:
                batch_pdf = temp_path / f"batch_{batch_num:04d}.pdf"
                await asyncio.to_thread(
                    self._render_batch_to_pdf, batch_pages, batch_pdf, batch_num == 0
                )
                temp_pdfs.append(batch_pdf)

                for p in batch_pages:
                    p.release_content()

            # Merge all batch PDFs into final output
            if progress_callback:
                progress_callback(
                    pages_processed, total_pages, "Merging PDF batches..."
                )

            if len(temp_pdfs) == 1:
                # Only one batch, just copy it
                await asyncio.to_thread(shutil.copy, temp_pdfs[0], output_file)
            elif len(temp_pdfs) > 1:
                # Multiple batches, need to merge
                self._merge_pdfs(temp_pdfs, output_file)
            else:
                # No pages - create empty PDF
                self._create_empty_pdf(output_file)

        # Report completion
        if progress_callback:
            progress_callback(
                pages_processed,
                total_pages,
                f"PDF export complete ({pages_processed} pages)",
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "Streaming PDF export complete: %d pages in %d batches, %dms",
            pages_processed,
            len(temp_pdfs),
            duration_ms,
        )

        return ExportResult(
            pages_exported=pages_processed,
            output_path=output_file,
            duration_ms=duration_ms,
            errors=errors,
        )

    async def export_separate(
        self, progress_callback: ProgressCallback | None = None
    ) -> ExportResult:
        """Export each wiki page as a separate PDF with streaming.

        Args:
            progress_callback: Optional callback for progress updates.

        Returns:
            ExportResult with export statistics.
        """
        start_time = time.monotonic()
        errors: list[str] = []

        logger.info("Starting streaming separate PDF export from %s", self.wiki_path)

        # Determine output directory
        output_dir = self.output_path
        if output_dir.suffix == ".pdf":
            output_dir = output_dir.parent / output_dir.stem
        await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)

        # Get page count for progress
        iterator = self.get_page_iterator()
        total_pages = iterator.get_page_count()

        # Report total pages at start
        if progress_callback:
            progress_callback(
                0, total_pages, f"Starting separate PDF export ({total_pages} pages)"
            )

        exported = 0
        async for page in iterator:
            try:
                rel_path = page.metadata.relative_path
                output_file = output_dir / rel_path.with_suffix(".pdf")
                await asyncio.to_thread(
                    output_file.parent.mkdir, parents=True, exist_ok=True
                )

                await asyncio.to_thread(self._export_single_page, page, output_file)
                exported += 1

                if progress_callback:
                    progress_callback(
                        exported,
                        total_pages,
                        f"Exported page {exported} of {total_pages}: {page.path}",
                    )

                # Release content from memory
                page.release_content()

            except Exception as e:
                error_msg = f"Failed to export {page.path}: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)

        # Report completion
        if progress_callback:
            progress_callback(
                exported,
                total_pages,
                f"Separate PDF export complete ({exported} pages)",
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "Streaming separate PDF export complete: %d pages in %dms",
            exported,
            duration_ms,
        )

        return ExportResult(
            pages_exported=exported,
            output_path=output_dir,
            duration_ms=duration_ms,
            errors=errors,
        )

    def _render_batch_to_pdf(
        self, pages: list[WikiPage], output_path: Path, include_toc: bool = False
    ) -> None:
        """Render a batch of pages to a PDF file.

        Args:
            pages: List of WikiPage objects to render.
            output_path: Path for the output PDF.
            include_toc: If True, include TOC at the start (first batch only).
        """
        parts = []

        if include_toc:
            # Add title page with TOC for first batch
            parts.append("<h1>Documentation</h1>")
            parts.append("<h2>Table of Contents</h2>")
            parts.append(self._build_streaming_toc_html())
            parts.append('<div class="page-break"></div>')

        for i, page in enumerate(pages):
            content = page.content
            html_content = render_markdown_for_pdf(content)
            parts.append(html_content)

            # Add page break between pages (except last)
            if i < len(pages) - 1:
                parts.append('<div class="page-break"></div>')

        combined_content = "\n".join(parts)
        full_html = PDF_HTML_TEMPLATE.format(
            title="Documentation",
            content=combined_content,
        )

        _require_weasyprint()
        html_doc = HTML(string=full_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_path, stylesheets=[css])

    def _build_streaming_toc_html(self) -> str:
        """Build TOC HTML from loaded TOC entries."""
        parts = ['<div class="toc">']
        self._add_toc_entries_html(self._toc_entries, parts, 0)
        parts.append("</div>")
        return "\n".join(parts)

    def _add_toc_entries_html(
        self, entries: list[dict[str, Any]], parts: list[str], depth: int
    ) -> None:
        """Recursively add TOC entries to HTML parts."""
        for entry in entries:
            title = entry.get("title", "")
            indent = "  " * depth
            parts.append(f'<div class="toc-item">{indent}{title}</div>')
            if "children" in entry:
                self._add_toc_entries_html(entry["children"], parts, depth + 1)

    @staticmethod
    def _export_single_page(page: WikiPage, output_file: Path) -> None:
        """Export a single wiki page to PDF.

        Args:
            page: WikiPage object to export.
            output_file: Output PDF path.
        """
        logger.debug("Exporting page: %s", page.path)

        content = page.content
        html_content = render_markdown_for_pdf(content)

        full_html = PDF_HTML_TEMPLATE.format(
            title=page.title,
            content=html_content,
        )

        _require_weasyprint()
        html_doc = HTML(string=full_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_file, stylesheets=[css])

    @staticmethod
    def _merge_pdfs(pdf_files: list[Path], output_path: Path) -> None:
        """Merge multiple PDF files into one.

        Uses pypdf if available, otherwise concatenates using WeasyPrint.

        Args:
            pdf_files: List of PDF file paths to merge.
            output_path: Output path for merged PDF.
        """
        try:
            # Try using pypdf for efficient merging
            from pypdf import PdfWriter

            writer = PdfWriter()
            for pdf_file in pdf_files:
                writer.append(str(pdf_file))
            writer.write(str(output_path))
            writer.close()
            logger.debug("Merged %s PDFs using pypdf", len(pdf_files))

        except ImportError:
            # Fallback: Copy first PDF only — remaining batches are lost
            logger.warning(
                "pypdf not available for PDF merging. "
                "Only %d of %d PDF batches included in output. "
                "Install pypdf (`pip install pypdf`) for complete multi-batch merging.",
                1,
                len(pdf_files),
            )
            shutil.copy(pdf_files[0], output_path)

    @staticmethod
    def _create_empty_pdf(output_path: Path) -> None:
        """Create an empty PDF file.

        Args:
            output_path: Path for the output PDF.
        """
        empty_html = PDF_HTML_TEMPLATE.format(
            title="Documentation",
            content="<p>No pages to export.</p>",
        )
        _require_weasyprint()
        html_doc = HTML(string=empty_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_path, stylesheets=[css])


from local_deepwiki.export.pdf_sync import (  # noqa: E402
    PdfExporter,
    export_to_pdf,
    main,
)

# Re-export for backward compatibility
__all__ = [
    "_require_weasyprint",
    "render_markdown_for_pdf",
    "extract_title",
    "StreamingPdfExporter",
    "PdfExporter",
    "export_to_pdf",
    "main",
]


if __name__ == "__main__":
    main()
