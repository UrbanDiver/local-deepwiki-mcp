# Export Module Documentation

## Module Purpose

The export module provides functionality for generating static HTML and PDF documentation from DeepWiki repository documentation. It includes streaming and standard export modes for handling both small and large wikis, with support for navigation elements like tables of contents and breadcrumbs.

## Key Classes and Functions

### StreamingHtmlExporter
A streaming exporter that processes wiki pages one at a time to manage memory usage for large wikis. It handles the conversion of markdown content to HTML, fixes internal links, and generates complete HTML pages with proper navigation elements.

### HtmlExporter
A standard exporter that can operate in either streaming or standard mode depending on the wiki size. It converts markdown files to HTML, manages navigation elements (TOC, breadcrumbs), and handles output directory management.

### StreamingPdfExporter
A streaming PDF exporter that converts wiki pages to PDF format with proper styling and navigation elements.

### PdfExporter
A standard PDF exporter that generates PDF documentation from wiki content.

### ExportConfig
Configuration class for export settings including output paths, formatting options, and export behavior.

### ExportResult
Data class containing results of an export operation including page count, duration, and any errors encountered.

### extract_title
Extracts a title from a markdown file by looking for the first heading or bold line, falling back to a derived title from the filename.

### render_toc_entry
Renders a single table of contents entry as HTML with proper nesting for child entries.

### render_toc
Renders a list of table of contents entries as HTML.

### build_breadcrumb
Generates breadcrumb navigation HTML for a given page path.

## How Components Interact

The export module uses a dual-class approach where both [`StreamingHtmlExporter`](../files/src/local_deepwiki/export/html.md) and [`HtmlExporter`](../files/src/local_deepwiki/export/html.md) inherit from [`StreamingExporter`](../files/src/local_deepwiki/export/streaming.md) base class. The [`StreamingExporter`](../files/src/local_deepwiki/export/streaming.md) provides shared functionality like TOC loading, progress tracking, and memory management for large wikis.

When exporting HTML:
1. The exporter loads the table of contents (TOC) for navigation
2. It creates output directories and copies supporting files like search.json
3. For each page, it converts markdown to HTML using [`render_markdown`](../files/src/local_deepwiki/export/html.md)
4. Internal links are fixed using [`fix_internal_links`](../files/src/local_deepwiki/export/html.md)
5. External link targets are set with [`add_external_link_targets`](../files/src/local_deepwiki/export/html.md)
6. Navigation elements (TOC, breadcrumbs) are generated using shared functions
7. Final HTML is written to output files

For PDF export, similar processing occurs but with PDF-specific styling and formatting applied.

## Usage Examples

### Exporting to HTML```python
from local_deepwiki.export.html import HtmlExporter
from pathlib import Path

# Create exporter instance
exporter = HtmlExporter(
    wiki_path=Path(".deepwiki"),
    output_path=Path("./html-export"),
    no_progress=False
)

# Perform export
pages_exported = exporter.export()
print(f"Exported {pages_exported} pages")
```
### Streaming HTML Export```python
from local_deepwiki.export.html import StreamingHtmlExporter
from pathlib import Path

# Create streaming exporter
streaming_exporter = StreamingHtmlExporter(
    wiki_path=Path(".deepwiki"),
    output_path=Path("./html-export"),
    no_progress=False
)

# Perform streaming export with progress callback
result = streaming_exporter.export()
print(f"Exported {result.pages_exported} pages in {result.duration_ms}ms")
```
### Exporting to PDF```python
from local_deepwiki.export.pdf import PdfExporter
from pathlib import Path

# Create PDF exporter
pdf_exporter = PdfExporter(
    wiki_path=Path(".deepwiki"),
    output_path=Path("./documentation.pdf")
)

# Perform export
pages_exported = pdf_exporter.export()
print(f"Exported {pages_exported} pages to PDF")
```
## Dependencies

This module depends on:
- `local_deepwiki.export.streaming` - Provides base streaming functionality and [ExportConfig](../files/src/local_deepwiki/export/streaming.md)/[ExportResult](../files/src/local_deepwiki/services/models.md) classes
- `local_deepwiki.export.shared` - Provides shared utility functions ([extract_title](../files/src/local_deepwiki/export/pdf.md), [render_toc](../files/src/local_deepwiki/export/shared.md), etc.)
- `local_deepwiki.export.html_template` - Contains the static HTML template used for rendering
- `local_deepwiki.export.pdf_styles` - PDF styling definitions
- `local_deepwiki.export.pdf_sync` - Synchronous PDF export functionality
- `local_deepwiki.export.mermaid_renderer` - Mermaid diagram rendering capabilities
- `local_deepwiki.cli_progress` - Progress bar and CLI utilities
- `local_deepwiki.logging` - Logging functionality
- Standard library modules: `argparse`, `asyncio`, `base64`, `collections`, `contextvars`, `dataclasses`, `json`, `markdown`, `pathlib`, `pydantic`, `pypdf`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `time`, `typing`

The module also imports various components from the local_deepwiki package including core functionality for handling wiki data and processing markdown content.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/export/shared.py:17-41`](../files/src/local_deepwiki/export/shared.md)
- [`src/local_deepwiki/export/html.py:97-261`](../files/src/local_deepwiki/export/html.md)
- [`src/local_deepwiki/export/pdf_sync.py:22-236`](../files/src/local_deepwiki/export/pdf_sync.md)
- [`src/local_deepwiki/export/pdf_styles.py`](../files/src/local_deepwiki/export/pdf_styles.md)
- `src/local_deepwiki/export/__init__.py:24-38`
- [`src/local_deepwiki/export/html_template.py`](../files/src/local_deepwiki/export/html_template.md)
- [`src/local_deepwiki/export/pdf.py:129-495`](../files/src/local_deepwiki/export/pdf.md)
- [`src/local_deepwiki/export/streaming.py:22-42`](../files/src/local_deepwiki/export/streaming.md)
- [`src/local_deepwiki/export/mermaid_renderer.py:30-46`](../files/src/local_deepwiki/export/mermaid_renderer.md)
