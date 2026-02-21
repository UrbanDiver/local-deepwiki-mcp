"""Synchronous PDF export functionality for DeepWiki documentation.

Contains the legacy PdfExporter class, export_to_pdf convenience function,
and CLI main entry point.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from local_deepwiki.cli_progress import create_progress
from local_deepwiki.export import pdf as _pdf_module
from local_deepwiki.export.pdf_styles import PDF_HTML_TEMPLATE, PRINT_CSS
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


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
        logger.info("Starting PDF export from %s", self.wiki_path)

        # Load TOC for ordering
        toc_path = self.wiki_path / "toc.json"
        if toc_path.exists():
            toc_data = json.loads(toc_path.read_text())
            self.toc_entries = toc_data.get("entries", [])
            logger.debug("Loaded %s TOC entries", len(self.toc_entries))

        # Collect all pages in TOC order
        pages = self._collect_pages_in_order()
        logger.info("Found %s pages to export", len(pages))

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
            _pdf_module._require_weasyprint()
            html_doc = _pdf_module.HTML(string=combined_html)
            css = _pdf_module.CSS(string=PRINT_CSS)
            html_doc.write_pdf(output_file, stylesheets=[css])
            progress.update(task, advance=1)

        logger.info("Generated PDF: %s", output_file)
        return output_file

    def export_separate(self) -> list[Path]:
        """Export each wiki page as a separate PDF.

        Returns:
            List of paths to generated PDF files.
        """
        logger.info("Starting separate PDF export from %s", self.wiki_path)

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

        logger.info("Generated %s PDF files", len(generated))
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
                html_content = _pdf_module.render_markdown_for_pdf(content)
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
            title = _pdf_module.extract_title(page)
            rel_path = page.relative_to(self.wiki_path)
            indent = "  " * (len(rel_path.parts) - 1)
            parts.append(f'<div class="toc-item">{indent}{title}</div>')
        parts.append("</div>")
        return "\n".join(parts)

    @staticmethod
    def _export_page(md_file: Path, output_file: Path) -> None:
        """Export a single page to PDF.

        Args:
            md_file: Path to markdown file.
            output_file: Output PDF path.
        """
        logger.debug("Exporting page: %s", md_file.name)

        content = md_file.read_text()
        html_content = _pdf_module.render_markdown_for_pdf(content)
        title = _pdf_module.extract_title(md_file)

        full_html = PDF_HTML_TEMPLATE.format(
            title=title,
            content=html_content,
        )

        _pdf_module._require_weasyprint()
        html_doc = _pdf_module.HTML(string=full_html)
        css = _pdf_module.CSS(string=PRINT_CSS)
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
        # Use _pdf_module.export_to_pdf so that mocking
        # local_deepwiki.export.pdf.export_to_pdf in tests works correctly.
        result = _pdf_module.export_to_pdf(
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
