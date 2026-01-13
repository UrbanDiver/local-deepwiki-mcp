"""PDF export functionality for DeepWiki documentation."""

import argparse
import json
import sys
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


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


def render_markdown_for_pdf(content: str) -> str:
    """Render markdown to HTML suitable for PDF.

    Args:
        content: Markdown content.

    Returns:
        HTML string.
    """
    # Replace mermaid code blocks with a note since they can't render in PDF
    lines = content.split("\n")
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

    Args:
        md_file: Path to markdown file.

    Returns:
        Extracted title or filename-based title.
    """
    try:
        content = md_file.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("**") and line.endswith("**"):
                return line[2:-2].strip()
    except Exception as e:
        logger.debug(f"Could not extract title from {md_file}: {e}")
    return md_file.stem.replace("_", " ").replace("-", " ").title()


class PdfExporter:
    """Export wiki markdown to PDF format."""

    def __init__(self, wiki_path: Path, output_path: Path):
        """Initialize the exporter.

        Args:
            wiki_path: Path to the .deepwiki directory.
            output_path: Output path for PDF file(s).
        """
        self.wiki_path = Path(wiki_path)
        self.output_path = Path(output_path)
        self.toc_entries: list[dict] = []

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

        # Build combined HTML
        combined_html = self._build_combined_html(pages)

        # Generate PDF
        output_file = self.output_path
        if output_file.is_dir():
            output_file = output_file / "documentation.pdf"

        output_file.parent.mkdir(parents=True, exist_ok=True)

        html_doc = HTML(string=combined_html)
        css = CSS(string=PRINT_CSS)
        html_doc.write_pdf(output_file, stylesheets=[css])

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

        generated = []
        for md_file in sorted(self.wiki_path.rglob("*.md")):
            rel_path = md_file.relative_to(self.wiki_path)
            output_file = output_dir / rel_path.with_suffix(".pdf")
            output_file.parent.mkdir(parents=True, exist_ok=True)

            self._export_page(md_file, output_file)
            generated.append(output_file)

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

        # Add each page
        for i, page in enumerate(pages):
            content = page.read_text()
            html_content = render_markdown_for_pdf(content)
            parts.append(html_content)

            # Add page break between pages (except last)
            if i < len(pages) - 1:
                parts.append('<div class="page-break"></div>')

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
) -> str:
    """Export wiki to PDF format.

    Args:
        wiki_path: Path to the .deepwiki directory.
        output_path: Output path (default: wiki.pdf or wiki_pdfs/).
        single_file: If True, combine all pages into one PDF.

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

    exporter = PdfExporter(wiki_path, output_path)

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

    args = parser.parse_args()

    if not args.wiki_path.exists():
        print(f"Error: Wiki path does not exist: {args.wiki_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = export_to_pdf(
            wiki_path=args.wiki_path,
            output_path=args.output,
            single_file=not args.separate,
        )
        print(result)
        print("Open the PDF file to view the documentation.")
    except Exception as e:
        print(f"Error exporting to PDF: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
