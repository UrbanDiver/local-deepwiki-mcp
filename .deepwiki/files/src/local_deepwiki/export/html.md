# HTML Export Module

This module provides functionality to export DeepWiki documentation to static HTML files. It converts markdown files to HTML format with proper navigation and table of contents.

## Classes

### HtmlExporter

The HtmlExporter class handles the conversion of wiki markdown files to static HTML format.

**Initialization:**
- `wiki_path`: Path to the .deepwiki directory
- `output_path`: Output directory for HTML files
- `toc_entries`: List to store table of contents entries

**Methods:**

#### export
Exports all wiki pages to HTML format.

**Returns:**
- `int`: Number of pages exported

The method loads the table of contents from `toc.json`, creates the output directory, and processes all markdown files in the wiki.

#### _export_page
Exports a single markdown page to HTML.

**Parameters:**
- `md_file`: Path to the markdown file
- `rel_path`: Relative path from wiki root

The method reads markdown content, converts it to HTML, extracts the title, and calculates relative paths for proper navigation.

## Functions

### export_to_html
Main function to export wiki to static HTML files.

**Parameters:**
- `wiki_path`: Path to the .deepwiki directory (string or Path)
- `output_path`: Output directory (optional, defaults to `{wiki_path}_html`)

**Returns:**
- `str`: Path to the output directory

**[Usage Example](../generators/test_examples.md):**
```python
from local_deepwiki.export.html import export_to_html

# Export with default output path
output_dir = export_to_html(".deepwiki")

# Export with custom output path
output_dir = export_to_html(".deepwiki", "my_html_export")
```

### main
CLI entry point for HTML export functionality.

Provides command-line interface with the following options:
- `wiki_path`: Path to the .deepwiki directory (default: ".deepwiki")
- `--output`, `-o`: Output directory (default: `{wiki_path}_html`)

## Related Components

This module depends on:
- `markdown` library for converting markdown to HTML
- `local_deepwiki.logging` for logging functionality
- Standard library modules: `argparse`, `json`, `shutil`, `pathlib`

The module references additional functions that work with markdown content:
- `render_markdown`: Converts markdown content to HTML
- `extract_title`: Extracts title from markdown files

## Usage

The module can be used both programmatically and from the command line:

**Programmatic Usage:**
```python
from pathlib import Path
from local_deepwiki.export.html import HtmlExporter

# Create exporter instance
exporter = HtmlExporter(Path(".deepwiki"), Path("output"))

# Export all pages
pages_exported = exporter.export()
```

**Command Line Usage:**
```bash
# Export with default settings
python -m local_deepwiki.export.html

# Export with custom paths
python -m local_deepwiki.export.html /path/to/.deepwiki --output /path/to/output
```

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
