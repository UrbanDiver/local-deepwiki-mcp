# HTML Export Module

## File Overview

The `html.py` module provides functionality for exporting DeepWiki documentation to static HTML files. It includes both a programmatic API and a command-line interface for converting markdown-based wiki content into a standalone HTML website.

## Classes

### HtmlExporter

The HtmlExporter class handles the conversion of wiki content from markdown to HTML format.

**Purpose**: Exports all wiki pages from a `.deepwiki` directory to static HTML files with proper navigation and table of contents.

**Initialization**:
- `wiki_path`: Path to the `.deepwiki` directory containing the source content
- `output_path`: Directory where HTML files will be generated

**Key Methods**:

- `export()`: Exports all wiki pages to HTML and returns the number of pages exported
- `_export_page(md_file, rel_path)`: Exports a single markdown page to HTML, taking the markdown file path and its relative path from the wiki root

**Internal Structure**:
- Maintains `toc_entries` list for table of contents data
- Loads TOC from `toc.json` if available
- Creates output directory structure as needed

## Functions

### export_to_html

```python
export_to_html(wiki_path: str | Path, output_path: str | Path | None = None) -> str
```

**Purpose**: Main entry point for programmatic HTML export.

**Parameters**:
- `wiki_path`: Path to the `.deepwiki` directory (accepts string or Path object)
- `output_path`: Optional output directory (defaults to `{wiki_path}_html`)

**Returns**: Path to the output directory as a string

### main

```python
main()
```

**Purpose**: Command-line interface entry point for HTML export.

**CLI Arguments**:
- `wiki_path`: Optional positional argument for wiki directory (defaults to `.deepwiki`)
- `--output, -o`: Optional output directory flag

## Usage Examples

### Programmatic Usage

```python
from local_deepwiki.export.html import export_to_html

# Export with default output path
output_dir = export_to_html(".deepwiki")

# Export with custom output path
output_dir = export_to_html(".deepwiki", "my_html_output")
```

### Direct Class Usage

```python
from local_deepwiki.export.html import HtmlExporter
from pathlib import Path

# Initialize exporter
exporter = HtmlExporter(
    wiki_path=Path(".deepwiki"),
    output_path=Path("html_output")
)

# Export all pages
pages_exported = exporter.export()
print(f"Exported {pages_exported} pages")
```

### Command Line Usage

```bash
# Export current directory's .deepwiki
python -m local_deepwiki.export.html

# Export specific wiki directory
python -m local_deepwiki.export.html /path/to/my/wiki

# Export with custom output directory
python -m local_deepwiki.export.html --output /path/to/output
```

## Related Components

The module integrates with several other components:

- **markdown library**: Used for converting markdown content to HTML
- **local_deepwiki.logging**: Provides logging functionality through the [`get_logger`](../logging.md) function
- **JSON files**: Reads table of contents data from `toc.json` files
- **render_markdown and extract_title functions**: Referenced in the export process but not shown in the provided code

## Dependencies

Based on the imports shown:
- `argparse`: Command-line argument parsing
- `json`: JSON file handling for TOC data
- `shutil`: File operations
- `pathlib.Path`: Path manipulation
- `markdown`: Markdown to HTML conversion
- `local_deepwiki.logging`: Internal logging system

## API Reference

### class `HtmlExporter`

Export wiki markdown to static HTML files.

**Methods:**

#### `__init__`

```python
def __init__(wiki_path: Path, output_path: Path)
```

Initialize the exporter.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | Path to the .deepwiki directory |
| `output_path` | `Path` | - | Output directory for HTML files |

#### `export`

```python
def export() -> int
```

Export all wiki pages to HTML.


---

### Functions

#### `render_markdown`

```python
def render_markdown(content: str) -> str
```

Render markdown to HTML.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | - |

**Returns:** `str`


#### `extract_title`

```python
def extract_title(md_file: Path) -> str
```

Extract title from markdown file.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `md_file` | `Path` | - | - |

**Returns:** `str`


#### `export_to_html`

```python
def export_to_html(wiki_path: str | Path, output_path: str | Path | None = None) -> str
```

Export wiki to static HTML files.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `str | Path` | - | Path to the .deepwiki directory |
| `output_path` | `str | Path | None` | `None` | Output directory (default: {wiki_path}_html) |

**Returns:** `str`


#### `main`

```python
def main()
```

CLI entry point for HTML export.



## Class Diagram

```mermaid
classDiagram
    class HtmlExporter {
        -__init__(wiki_path: Path, output_path: Path)
        +export() int
        -_export_page(md_file: Path, rel_path: Path) None
        -_render_toc(entries: list[dict], current_path: str, root_path: str) str
        -_render_toc_entry(entry: dict, current_path: str, root_path: str) str
        -_build_breadcrumb(rel_path: Path, root_path: str) str
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[ArgumentParser]
    N1[HtmlExporter]
    N2[HtmlExporter.__init__]
    N3[HtmlExporter._build_breadcrumb]
    N4[HtmlExporter._export_page]
    N5[HtmlExporter.export]
    N6[Markdown]
    N7[Path]
    N8[_build_breadcrumb]
    N9[_export_page]
    N10[_render_toc]
    N11[_render_toc_entry]
    N12[add_argument]
    N13[convert]
    N14[copy]
    N15[exists]
    N16[export]
    N17[export_to_html]
    N18[extract_title]
    N19[loads]
    N20[main]
    N21[mkdir]
    N22[parse_args]
    N23[read_text]
    N24[relative_to]
    N25[render_markdown]
    N26[resolve]
    N27[rglob]
    N28[title]
    N29[with_suffix]
    N25 --> N6
    N25 --> N13
    N18 --> N23
    N18 --> N28
    N17 --> N7
    N17 --> N1
    N17 --> N16
    N20 --> N0
    N20 --> N12
    N20 --> N22
    N20 --> N26
    N20 --> N7
    N20 --> N15
    N20 --> N17
    N2 --> N7
    N5 --> N15
    N5 --> N19
    N5 --> N23
    N5 --> N21
    N5 --> N14
    N5 --> N27
    N5 --> N24
    N5 --> N9
    N4 --> N23
    N4 --> N25
    N4 --> N18
    N4 --> N10
    N4 --> N8
    N4 --> N29
    N4 --> N21
    N3 --> N28
    N3 --> N15
    classDef func fill:#e1f5fe
    class N0,N1,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N2,N3,N4,N5 method
```

## Relevant Source Files

- `src/local_deepwiki/export/html.py:660-856`

## See Also

- [test_html_export](../../../tests/test_html_export.md) - uses this
