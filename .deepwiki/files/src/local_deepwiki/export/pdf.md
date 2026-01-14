# PDF Export Module

This module provides functionality for exporting DeepWiki documentation to PDF format. It supports both single-file and separate-file PDF generation with Mermaid diagram rendering capabilities.

## Classes

### PdfExporter

The PdfExporter class handles the conversion of wiki markdown files to PDF format.

**Attributes:**
- `wiki_path`: Path to the .deepwiki directory
- `output_path`: Output path for PDF file(s)
- `toc_entries`: List of table of contents entries for page ordering

**Methods:**

#### `__init__(wiki_path: Path, output_path: Path)`

Initialize the exporter with source and destination paths.

**Parameters:**
- `wiki_path`: Path to the .deepwiki directory
- `output_path`: Output path for PDF file(s)

#### `export_single() -> Path`

Export all wiki pages to a single combined PDF file. The method loads the table of contents for proper page ordering and collects all pages accordingly.

**Returns:**
- Path to the generated PDF file

#### `export_separate() -> list[Path]`

Export each wiki page as a separate PDF file. Creates an output directory if the output path has a .pdf extension.

**Returns:**
- List of paths to generated PDF files

## Functions

### `export_to_pdf(wiki_path: Path | str, output_path: Path | str | None = None, single_file: bool = True) -> str`

Main export function that provides a convenient interface for PDF generation.

**Parameters:**
- `wiki_path`: Path to the .deepwiki directory
- `output_path`: Output path (defaults to wiki.pdf or wiki_pdfs/ based on single_file parameter)
- `single_file`: If True, combine all pages into one PDF; if False, create separate PDFs

**Returns:**
- Success message with output path

**Raises:**
- `ValueError`: If the wiki path does not exist

### `main() -> None`

CLI entry point for PDF export functionality. Sets up argument parsing for command-line usage with support for:
- Wiki path specification (defaults to `.deepwiki`)
- Output path customization via `-o`/`--output` flag
- Separate file export mode

## Usage Examples

### Programmatic Usage

```python
from pathlib import Path
from local_deepwiki.export.pdf import PdfExporter, export_to_pdf

# Using the convenience function
result = export_to_pdf(
    wiki_path=".deepwiki",
    output_path="documentation.pdf",
    single_file=True
)

# Using the class directly
exporter = PdfExporter(
    wiki_path=Path(".deepwiki"),
    output_path=Path("output.pdf")
)
pdf_path = exporter.export_single()
```

### Command Line Usage

```bash
# Export to single PDF (default behavior)
python -m local_deepwiki.export.pdf .deepwiki

# Export each page separately
python -m local_deepwiki.export.pdf .deepwiki --separate

# Specify custom output path
python -m local_deepwiki.export.pdf .deepwiki -o custom_docs.pdf
```

## Dependencies

The module imports several standard library modules including `argparse`, `json`, `pathlib`, and `subprocess`, as well as the `markdown` library for processing markdown content. It also includes utility functions for Mermaid diagram rendering and markdown processing specific to PDF output.

## API Reference

### class `PdfExporter`

Export wiki markdown to PDF format.

**Methods:**

#### `__init__`

```python
def __init__(wiki_path: Path, output_path: Path)
```

Initialize the exporter.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | Path to the .deepwiki directory. |
| `output_path` | `Path` | - | Output path for PDF file(s). |

#### `export_single`

```python
def export_single() -> Path
```

Export all wiki pages to a single PDF.

#### `export_separate`

```python
def export_separate() -> list[Path]
```

Export each wiki page as a separate PDF.


---

### Functions

#### `is_mmdc_available`

```python
def is_mmdc_available() -> bool
```

Check if mermaid-cli (mmdc) is available on the system.

**Returns:** `bool`


#### `render_mermaid_to_png`

```python
def render_mermaid_to_png(diagram_code: str, timeout: int = 30) -> bytes | None
```

Render a mermaid diagram to PNG using mermaid-cli.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `diagram_code` | `str` | - | The mermaid diagram code. |
| `timeout` | `int` | `30` | Timeout in seconds for the mmdc command. |

**Returns:** `bytes | None`


#### `render_mermaid_to_svg`

```python
def render_mermaid_to_svg(diagram_code: str, timeout: int = 30) -> str | None
```

Render a mermaid diagram to SVG using mermaid-cli.  Note: SVG may have font issues in PDF. Use render_mermaid_to_png for PDF export.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `diagram_code` | `str` | - | The mermaid diagram code. |
| `timeout` | `int` | `30` | Timeout in seconds for the mmdc command. |

**Returns:** `str | None`


#### `extract_mermaid_blocks`

```python
def extract_mermaid_blocks(content: str) -> list[tuple[str, str]]
```

Extract mermaid code blocks from markdown content.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Markdown content. |

**Returns:** `list[tuple[str, str]]`


#### `render_markdown_for_pdf`

```python
def render_markdown_for_pdf(content: str, render_mermaid: bool = True) -> str
```

Render markdown to HTML suitable for PDF.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Markdown content. |
| `render_mermaid` | `bool` | `True` | If True, attempt to render mermaid diagrams using CLI. Falls back to placeholder if CLI is not available. |

**Returns:** `str`


#### `extract_title`

```python
def extract_title(md_file: Path) -> str
```

Extract title from markdown file.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `md_file` | `Path` | - | Path to markdown file. |

**Returns:** `str`


#### `export_to_pdf`

```python
def export_to_pdf(wiki_path: Path | str, output_path: Path | str | None = None, single_file: bool = True) -> str
```

Export wiki to PDF format.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path | str` | - | Path to the .deepwiki directory. |
| `output_path` | `Path | str | None` | `None` | Output path (default: wiki.pdf or wiki_pdfs/). |
| `single_file` | `bool` | `True` | If True, combine all pages into one PDF. |

**Returns:** `str`


#### `main`

```python
def main() -> None
```

CLI entry point for PDF export.

**Returns:** `None`



## Class Diagram

```mermaid
classDiagram
    class PdfExporter {
        -__init__(wiki_path: Path, output_path: Path)
        +export_single() Path
        +export_separate() list[Path]
        -_collect_pages_in_order() list[Path]
        -_extract_paths_from_toc(entries: list[dict], paths: list[str]) None
        -_build_combined_html(pages: list[Path]) str
        -_build_toc_html(pages: list[Path]) str
        -_export_page(md_file: Path, output_file: Path) None
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CSS]
    N1[HTML]
    N2[Path]
    N3[PdfExporter._build_combined...]
    N4[PdfExporter._build_toc_html]
    N5[PdfExporter._collect_pages_...]
    N6[PdfExporter._export_page]
    N7[PdfExporter.export_separate]
    N8[PdfExporter.export_single]
    N9[TemporaryDirectory]
    N10[_extract_paths_from_toc]
    N11[exists]
    N12[export_to_pdf]
    N13[extract_mermaid_blocks]
    N14[extract_title]
    N15[findall]
    N16[is_mmdc_available]
    N17[main]
    N18[mkdir]
    N19[read_bytes]
    N20[read_text]
    N21[relative_to]
    N22[render_markdown_for_pdf]
    N23[render_mermaid_to_png]
    N24[render_mermaid_to_svg]
    N25[rglob]
    N26[run]
    N27[which]
    N28[write_pdf]
    N29[write_text]
    N16 --> N27
    N23 --> N16
    N23 --> N9
    N23 --> N2
    N23 --> N29
    N23 --> N26
    N23 --> N11
    N23 --> N19
    N24 --> N16
    N24 --> N9
    N24 --> N2
    N24 --> N29
    N24 --> N26
    N24 --> N11
    N24 --> N20
    N13 --> N15
    N22 --> N16
    N22 --> N13
    N22 --> N23
    N14 --> N20
    N12 --> N2
    N12 --> N11
    N17 --> N2
    N17 --> N11
    N17 --> N12
    N8 --> N11
    N8 --> N20
    N8 --> N18
    N8 --> N1
    N8 --> N0
    N8 --> N28
    N7 --> N18
    N7 --> N25
    N7 --> N21
    N5 --> N10
    N5 --> N11
    N5 --> N25
    N3 --> N20
    N3 --> N22
    N4 --> N14
    N4 --> N21
    N6 --> N20
    N6 --> N22
    N6 --> N14
    N6 --> N1
    N6 --> N0
    N6 --> N28
    classDef func fill:#e1f5fe
    class N0,N1,N2,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N3,N4,N5,N6,N7,N8 method
```

## Relevant Source Files

- `src/local_deepwiki/export/pdf.py:480-664`

## See Also

- [test_pdf_export](../../../tests/test_pdf_export.md) - uses this
- [server](../server.md) - uses this
- [manifest](../generators/manifest.md) - shares 4 dependencies
- [vectorstore](../core/vectorstore.md) - shares 3 dependencies
