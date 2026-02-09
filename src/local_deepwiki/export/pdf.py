"""PDF export functionality for DeepWiki documentation."""

import argparse
import asyncio
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import markdown
from weasyprint import CSS, HTML

from local_deepwiki.cli_progress import create_progress
from local_deepwiki.export.streaming import (
    ExportConfig,
    ExportResult,
    ProgressCallback,
    StreamingExporter,
    WikiPage,
    WikiPageIterator,
)
from local_deepwiki.export.shared import extract_title as _shared_extract_title
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Default timeout for mermaid CLI rendering (seconds)
MERMAID_RENDER_TIMEOUT = 30

# Cache for mermaid CLI availability check
_mmdc_available: bool | None = None


def is_mmdc_available() -> bool:
    """Check if mermaid-cli (mmdc) is available on the system.

    Returns:
        True if mmdc is available, False otherwise.
    """
    global _mmdc_available
    if _mmdc_available is not None:
        return _mmdc_available

    _mmdc_available = shutil.which("mmdc") is not None
    if _mmdc_available:
        logger.debug("Mermaid CLI (mmdc) is available")
    else:
        logger.debug("Mermaid CLI (mmdc) not found - diagrams will use placeholder")
    return _mmdc_available


def render_mermaid_to_png(
    diagram_code: str, timeout: int = MERMAID_RENDER_TIMEOUT
) -> bytes | None:
    """Render a mermaid diagram to PNG using mermaid-cli.

    Args:
        diagram_code: The mermaid diagram code.
        timeout: Timeout in seconds for the mmdc command.

    Returns:
        PNG bytes if successful, None if rendering failed.
    """
    if not is_mmdc_available():
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_file = tmp_path / "diagram.mmd"
            output_file = tmp_path / "diagram.png"

            # Write diagram to temp file
            input_file.write_text(diagram_code)

            # Run mmdc to generate PNG (embeds fonts as pixels)
            result = subprocess.run(
                [
                    "mmdc",
                    "-i",
                    str(input_file),
                    "-o",
                    str(output_file),
                    "-b",
                    "white",  # White background for PDF
                    "-s",
                    "2",  # Scale 2x for better quality
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.warning(f"Mermaid CLI failed: {result.stderr}")
                return None

            if not output_file.exists():
                logger.warning("Mermaid CLI did not produce output file")
                return None

            return output_file.read_bytes()

    except subprocess.TimeoutExpired:
        logger.warning(f"Mermaid CLI timed out after {timeout}s")
        return None
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        # SubprocessError: Process execution failures
        # OSError: File system or process spawning issues
        # ValueError: Invalid diagram code
        logger.warning(f"Error rendering mermaid diagram: {e}")
        return None


def render_mermaid_to_svg(
    diagram_code: str, timeout: int = MERMAID_RENDER_TIMEOUT
) -> str | None:
    """Render a mermaid diagram to SVG using mermaid-cli.

    Note: SVG may have font issues in PDF. Use render_mermaid_to_png for PDF export.

    Args:
        diagram_code: The mermaid diagram code.
        timeout: Timeout in seconds for the mmdc command.

    Returns:
        SVG string if successful, None if rendering failed.
    """
    if not is_mmdc_available():
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_file = tmp_path / "diagram.mmd"
            output_file = tmp_path / "diagram.svg"

            # Write diagram to temp file
            input_file.write_text(diagram_code)

            # Run mmdc to generate SVG
            result = subprocess.run(
                [
                    "mmdc",
                    "-i",
                    str(input_file),
                    "-o",
                    str(output_file),
                    "-b",
                    "transparent",  # Transparent background
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.warning(f"Mermaid CLI failed: {result.stderr}")
                return None

            if not output_file.exists():
                logger.warning("Mermaid CLI did not produce output file")
                return None

            svg_content = output_file.read_text()
            return svg_content

    except subprocess.TimeoutExpired:
        logger.warning(f"Mermaid CLI timed out after {timeout}s")
        return None
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        # SubprocessError: Process execution failures
        # OSError: File system or process spawning issues
        # ValueError: Invalid diagram code
        logger.warning(f"Error rendering mermaid diagram: {e}")
        return None


def extract_mermaid_blocks(content: str) -> list[tuple[str, str]]:
    """Extract mermaid code blocks from markdown content.

    Args:
        content: Markdown content.

    Returns:
        List of (full_match, diagram_code) tuples.
    """
    # Match ```mermaid ... ``` blocks
    pattern = r"```mermaid\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    blocks = []
    for match in matches:
        full_block = f"```mermaid\n{match}```"
        diagram_code = match.strip()
        blocks.append((full_block, diagram_code))

    return blocks


# Print-optimized CSS for PDF output
PRINT_CSS = """
@page {
    size: letter;
    margin: 1in 0.75in;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 10pt;
        color: #666;
    }
    @top-center {
        content: string(doctitle);
        font-size: 10pt;
        color: #666;
    }
}

@page :first {
    @top-center {
        content: none;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1f2328;
    background: white;
    max-width: 100%;
}

h1 {
    string-set: doctitle content();
    font-size: 24pt;
    font-weight: 600;
    color: #1f2328;
    margin: 0 0 0.5em 0;
    padding-bottom: 0.3em;
    border-bottom: 1px solid #d0d7de;
    page-break-after: avoid;
}

h2 {
    font-size: 18pt;
    font-weight: 600;
    color: #1f2328;
    margin: 1.5em 0 0.5em 0;
    padding-bottom: 0.2em;
    border-bottom: 1px solid #d0d7de;
    page-break-after: avoid;
}

h3 {
    font-size: 14pt;
    font-weight: 600;
    color: #1f2328;
    margin: 1.2em 0 0.4em 0;
    page-break-after: avoid;
}

h4, h5, h6 {
    font-size: 12pt;
    font-weight: 600;
    color: #1f2328;
    margin: 1em 0 0.3em 0;
    page-break-after: avoid;
}

p {
    margin: 0.8em 0;
    orphans: 3;
    widows: 3;
}

a {
    color: #0969da;
    text-decoration: none;
}

code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 9pt;
    background: #f6f8fa;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}

pre {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 9pt;
    background: #f6f8fa;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    line-height: 1.45;
    page-break-inside: avoid;
    margin: 1em 0;
}

pre code {
    background: none;
    padding: 0;
    border-radius: 0;
}

blockquote {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 4px solid #d0d7de;
    color: #656d76;
    background: #f6f8fa;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    page-break-inside: avoid;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 8px 12px;
    text-align: left;
}

th {
    background: #f6f8fa;
    font-weight: 600;
}

tr:nth-child(even) {
    background: #f6f8fa;
}

ul, ol {
    margin: 0.8em 0;
    padding-left: 2em;
}

li {
    margin: 0.3em 0;
}

hr {
    border: none;
    border-top: 1px solid #d0d7de;
    margin: 2em 0;
}

img {
    max-width: 100%;
    height: auto;
}

.page-break {
    page-break-before: always;
}

.toc-title {
    font-size: 18pt;
    font-weight: 600;
    margin-bottom: 1em;
}

.toc-item {
    margin: 0.3em 0;
}

.toc-item a {
    color: #1f2328;
}

.toc-section {
    margin-left: 1.5em;
}

.mermaid-note {
    background: #fff8c5;
    border: 1px solid #d4a72c;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 10pt;
    color: #6e5a00;
    margin: 1em 0;
}

.mermaid-diagram {
    margin: 1em 0;
    text-align: center;
    page-break-inside: avoid;
}

.mermaid-diagram svg {
    max-width: 100%;
    height: auto;
}
"""

# HTML template for PDF generation
PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
{content}
</body>
</html>
"""


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
    return cast(str, md.convert(processed_content))


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
            f"Starting streaming PDF export from {self.wiki_path} to {self.output_path}"
        )

        # Load TOC for ordering
        self.load_toc()

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
        output_file.parent.mkdir(parents=True, exist_ok=True)

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
                        self._render_batch_to_pdf(
                            batch_pages, batch_pdf, batch_num == 0
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
                self._render_batch_to_pdf(batch_pages, batch_pdf, batch_num == 0)
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
                shutil.copy(temp_pdfs[0], output_file)
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
            f"Streaming PDF export complete: {pages_processed} pages "
            f"in {len(temp_pdfs)} batches, {duration_ms}ms"
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

        logger.info(f"Starting streaming separate PDF export from {self.wiki_path}")

        # Determine output directory
        output_dir = self.output_path
        if output_dir.suffix == ".pdf":
            output_dir = output_dir.parent / output_dir.stem
        output_dir.mkdir(parents=True, exist_ok=True)

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
                output_file.parent.mkdir(parents=True, exist_ok=True)

                self._export_single_page(page, output_file)
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
            f"Streaming separate PDF export complete: {exported} pages in {duration_ms}ms"
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

    def _export_single_page(self, page: WikiPage, output_file: Path) -> None:
        """Export a single wiki page to PDF.

        Args:
            page: WikiPage object to export.
            output_file: Output PDF path.
        """
        logger.debug(f"Exporting page: {page.path}")

        content = page.content
        html_content = render_markdown_for_pdf(content)

        full_html = PDF_HTML_TEMPLATE.format(
            title=page.title,
            content=html_content,
        )

        html_doc = HTML(string=full_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_file, stylesheets=[css])

    def _merge_pdfs(self, pdf_files: list[Path], output_path: Path) -> None:
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
            logger.debug(f"Merged {len(pdf_files)} PDFs using pypdf")

        except ImportError:
            # Fallback: Copy first PDF and log warning about potential issues
            logger.warning(
                "pypdf not available for PDF merging. "
                "Install pypdf for better multi-batch support. "
                "Using first batch only."
            )
            shutil.copy(pdf_files[0], output_path)

    def _create_empty_pdf(self, output_path: Path) -> None:
        """Create an empty PDF file.

        Args:
            output_path: Path for the output PDF.
        """
        empty_html = PDF_HTML_TEMPLATE.format(
            title="Documentation",
            content="<p>No pages to export.</p>",
        )
        html_doc = HTML(string=empty_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_path, stylesheets=[css])


class PdfExporter:
    """Export wiki markdown to PDF format.

    This is the synchronous wrapper class that maintains backwards compatibility.
    For large wikis, use StreamingPdfExporter directly for async streaming export.
    """

    def __init__(
        self,
        wiki_path: Path,
        output_path: Path,
        *,
        no_progress: bool = False,
    ):
        """Initialize the exporter.

        Args:
            wiki_path: Path to the .deepwiki directory.
            output_path: Output path for PDF file(s).
            no_progress: If True, disable progress bars.
        """
        self.wiki_path = Path(wiki_path)
        self.output_path = Path(output_path)
        self.toc_entries: list[dict] = []
        self._no_progress = no_progress

    def export_single(self) -> Path:
        """Export all wiki pages to a single PDF.

        Returns:
            Path to the generated PDF file.
        """
        logger.info(f"Starting PDF export from {self.wiki_path}")

        # Load TOC for ordering
        toc_path = self.wiki_path / "toc.json"
        if toc_path.exists():
            toc_data = json.loads(toc_path.read_text())
            self.toc_entries = toc_data.get("entries", [])
            logger.debug(f"Loaded {len(self.toc_entries)} TOC entries")

        # Collect all pages in TOC order
        pages = self._collect_pages_in_order()
        logger.info(f"Found {len(pages)} pages to export")

        # Build combined HTML with progress
        combined_html = self._build_combined_html(pages)

        # Generate PDF
        output_file = self.output_path
        if output_file.is_dir():
            output_file = output_file / "documentation.pdf"

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with create_progress(disable=self._no_progress) as progress:
            task = progress.add_task("Generating PDF", total=1)
            progress.update(task, description="Writing PDF file")
            html_doc = HTML(string=combined_html)
            css = CSS(string=PRINT_CSS)
            html_doc.write_pdf(output_file, stylesheets=[css])
            progress.update(task, advance=1)

        logger.info(f"Generated PDF: {output_file}")
        return output_file

    def export_separate(self) -> list[Path]:
        """Export each wiki page as a separate PDF.

        Returns:
            List of paths to generated PDF files.
        """
        logger.info(f"Starting separate PDF export from {self.wiki_path}")

        output_dir = self.output_path
        if output_dir.suffix == ".pdf":
            output_dir = output_dir.parent / output_dir.stem

        output_dir.mkdir(parents=True, exist_ok=True)

        # Collect all markdown files
        md_files = sorted(self.wiki_path.rglob("*.md"))

        generated = []
        with create_progress(disable=self._no_progress) as progress:
            task = progress.add_task("Exporting PDFs", total=len(md_files))
            for md_file in md_files:
                rel_path = md_file.relative_to(self.wiki_path)
                progress.update(task, description=f"Exporting {rel_path.name}")
                output_file = output_dir / rel_path.with_suffix(".pdf")
                output_file.parent.mkdir(parents=True, exist_ok=True)

                self._export_page(md_file, output_file)
                generated.append(output_file)
                progress.update(task, advance=1)

        logger.info(f"Generated {len(generated)} PDF files")
        return generated

    def _collect_pages_in_order(self) -> list[Path]:
        """Collect markdown files in TOC order.

        Returns:
            List of markdown file paths.
        """
        ordered_paths: list[str] = []
        self._extract_paths_from_toc(self.toc_entries, ordered_paths)

        # Convert to full paths
        pages = []
        for rel_path in ordered_paths:
            full_path = self.wiki_path / rel_path
            if full_path.exists():
                pages.append(full_path)

        # Add any files not in TOC
        all_files = set(self.wiki_path.rglob("*.md"))
        toc_files = set(pages)
        for f in sorted(all_files - toc_files):
            pages.append(f)

        return pages

    def _extract_paths_from_toc(self, entries: list[dict], paths: list[str]) -> None:
        """Recursively extract paths from TOC entries.

        Args:
            entries: TOC entries.
            paths: List to append paths to.
        """
        for entry in entries:
            if "path" in entry and entry["path"]:  # Skip empty paths
                paths.append(entry["path"])
            if "children" in entry:
                self._extract_paths_from_toc(entry["children"], paths)

    def _build_combined_html(self, pages: list[Path]) -> str:
        """Build combined HTML from all pages.

        Args:
            pages: List of markdown file paths.

        Returns:
            Combined HTML string.
        """
        parts = []

        # Add title page
        parts.append("<h1>Documentation</h1>")
        parts.append("<h2>Table of Contents</h2>")
        parts.append(self._build_toc_html(pages))
        parts.append('<div class="page-break"></div>')

        # Add each page with progress tracking
        with create_progress(disable=self._no_progress) as progress:
            task = progress.add_task("Processing pages", total=len(pages))
            for i, page in enumerate(pages):
                progress.update(task, description=f"Processing {page.name}")
                content = page.read_text()
                html_content = render_markdown_for_pdf(content)
                parts.append(html_content)

                # Add page break between pages (except last)
                if i < len(pages) - 1:
                    parts.append('<div class="page-break"></div>')
                progress.update(task, advance=1)

        combined_content = "\n".join(parts)
        return PDF_HTML_TEMPLATE.format(
            title="Documentation",
            content=combined_content,
        )

    def _build_toc_html(self, pages: list[Path]) -> str:
        """Build table of contents HTML.

        Args:
            pages: List of markdown file paths.

        Returns:
            HTML string for TOC.
        """
        parts = ['<div class="toc">']
        for page in pages:
            title = extract_title(page)
            rel_path = page.relative_to(self.wiki_path)
            indent = "  " * (len(rel_path.parts) - 1)
            parts.append(f'<div class="toc-item">{indent}{title}</div>')
        parts.append("</div>")
        return "\n".join(parts)

    def _export_page(self, md_file: Path, output_file: Path) -> None:
        """Export a single page to PDF.

        Args:
            md_file: Path to markdown file.
            output_file: Output PDF path.
        """
        logger.debug(f"Exporting page: {md_file.name}")

        content = md_file.read_text()
        html_content = render_markdown_for_pdf(content)
        title = extract_title(md_file)

        full_html = PDF_HTML_TEMPLATE.format(
            title=title,
            content=html_content,
        )

        html_doc = HTML(string=full_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_file, stylesheets=[css])


def export_to_pdf(
    wiki_path: Path | str,
    output_path: Path | str | None = None,
    single_file: bool = True,
    *,
    no_progress: bool = False,
) -> str:
    """Export wiki to PDF format.

    Args:
        wiki_path: Path to the .deepwiki directory.
        output_path: Output path (default: wiki.pdf or wiki_pdfs/).
        single_file: If True, combine all pages into one PDF.
        no_progress: If True, disable progress bars.

    Returns:
        Success message with output path.
    """
    wiki_path = Path(wiki_path)

    if not wiki_path.exists():
        raise ValueError(f"Wiki path does not exist: {wiki_path}")

    if output_path is None:
        if single_file:
            output_path = wiki_path.parent / f"{wiki_path.stem}.pdf"
        else:
            output_path = wiki_path.parent / f"{wiki_path.stem}_pdfs"
    else:
        output_path = Path(output_path)

    exporter = PdfExporter(wiki_path, output_path, no_progress=no_progress)

    if single_file:
        result = exporter.export_single()
        return f"Exported wiki to PDF: {result}"
    else:
        results = exporter.export_separate()
        return f"Exported {len(results)} pages to PDFs in: {output_path}"


def main() -> None:
    """CLI entry point for PDF export."""
    parser = argparse.ArgumentParser(
        description="Export DeepWiki documentation to PDF format"
    )
    parser.add_argument(
        "wiki_path",
        type=Path,
        nargs="?",
        default=Path(".deepwiki"),
        help="Path to the .deepwiki directory (default: .deepwiki)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: wiki.pdf for single, wiki_pdfs/ for separate)",
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="Export each page as a separate PDF instead of combining",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars (for non-interactive use)",
    )

    args = parser.parse_args()

    if not args.wiki_path.exists():
        print(f"Error: Wiki path does not exist: {args.wiki_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = export_to_pdf(
            wiki_path=args.wiki_path,
            output_path=args.output,
            single_file=not args.separate,
            no_progress=args.no_progress,
        )
        print(result)
        print("Open the PDF file to view the documentation.")
    except Exception as e:  # noqa: BLE001
        # Broad catch is intentional: CLI top-level error handler
        print(f"Error exporting to PDF: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
