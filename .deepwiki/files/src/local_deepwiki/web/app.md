# DeepWiki Web Application

## File Overview

This file defines the web application for DeepWiki, a documentation system that serves markdown files as a searchable wiki. The module provides the core Flask application setup, routing, and server execution logic. It integrates with the local DeepWiki directory structure to render markdown pages, provide search functionality, and build navigation breadcrumbs.

The file works with the core DeepWiki data structures and serves as the entry point for running the web server. It depends on the local .deepwiki directory structure and integrates with the markdown rendering pipeline to display documentation content.

## Functions

### run_server

```python
def run_server(wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False):
    """Run the wiki web server."""
```

Starts the Flask web server for the DeepWiki application.

**Parameters:**
- `wiki_path` (str | Path): Path to the .deepwiki directory containing documentation
- `host` (str): Host address to bind the server to (default: "127.0.0.1")
- `port` (int): Port number to bind the server to (default: 8080)
- `debug` (bool): Enable Flask debug mode (default: False)

**Usage:**
```python
run_server("/path/to/wiki", host="0.0.0.0", port=8080, debug=True)
```

### create_app

```python
def create_app(wiki_path: str | Path) -> Flask:
    """Create Flask app with wiki path configured."""
```

Creates and configures a Flask application instance with the specified wiki path.

**Parameters:**
- `wiki_path` (str | Path): Path to the .deepwiki directory

**Returns:**
- Flask: Configured Flask application instance

**Usage:**
```python
app = create_app("/path/to/wiki")
```

### main

```python
def main():
    """CLI entry point."""
```

Command-line interface entry point for starting the DeepWiki server.

**Parameters:**
None (uses command-line arguments)

**Usage:**
```bash
python app.py /path/to/wiki
python app.py --host 0.0.0.0 --port 8080 --debug
```

## Usage Examples

### Starting the Server

```bash
# Start server with default settings
python app.py

# Start server with custom wiki path
python app.py /path/to/my/wiki

# Start server with custom host and port
python app.py --host 0.0.0.0 --port 8080

# Start server in debug mode
python app.py --debug
```

### Programmatic Usage

```python
from src.local_deepwiki.web.app import create_app, run_server

# Create app instance
app = create_app("/path/to/wiki")

# Run server
run_server("/path/to/wiki", host="0.0.0.0", port=8080, debug=True)
```

## Related Components

This module works with the core DeepWiki directory structure and integrates with the markdown rendering pipeline. It depends on the local .deepwiki directory format and provides the web interface for browsing documentation. The application uses the [WikiGenerator](../generators/wiki.md) class to understand the wiki structure and build navigation elements. It also works with the search functionality that indexes markdown content for fast retrieval.

## API Reference

### Functions

#### `get_wiki_structure`

```python
def get_wiki_structure(wiki_path: Path) -> tuple[list, dict]
```

Get wiki pages and sections.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | - |

**Returns:** `tuple[list, dict]`


#### `extract_title`

```python
def extract_title(md_file: Path) -> str
```

Extract title from markdown file.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `md_file` | `Path` | - | - |

**Returns:** `str`


#### `render_markdown`

```python
def render_markdown(content: str) -> str
```

Render markdown to HTML.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | - |

**Returns:** `str`


#### `build_breadcrumb`

```python
def build_breadcrumb(wiki_path: Path, current_path: str) -> str
```

Build breadcrumb navigation HTML with clickable links.  For a path like 'files/src/local_deepwiki/core/chunker.md', generates: Home > Files > src > local_deepwiki > core > chunker  Each segment links to its index.md if one exists in that folder.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | - |
| `current_path` | `str` | - | - |

**Returns:** `str`


#### `index`

`@app.route('/')`

```python
def index()
```

Redirect to index.md.


#### `search_json`

`@app.route('/search.json')`

```python
def search_json()
```

Serve the search index JSON file.


#### `view_page`

`@app.route('/wiki/<path:path>')`

```python
def view_page(path: str)
```

View a wiki page.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | - | - |


#### `create_app`

```python
def create_app(wiki_path: str | Path) -> Flask
```

Create Flask app with wiki path configured.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `str | Path` | - | - |

**Returns:** `Flask`


#### `run_server`

```python
def run_server(wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False)
```

Run the wiki web server.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `str | Path` | - | - |
| `host` | `str` | `"127.0.0.1"` | - |
| `port` | `int` | `8080` | - |
| `debug` | `bool` | `False` | - |


#### `main`

```python
def main()
```

CLI entry point.



## Call Graph

```mermaid
flowchart TD
    N0[ArgumentParser]
    N1[Markdown]
    N2[Path]
    N3[ValueError]
    N4[abort]
    N5[add_argument]
    N6[build_breadcrumb]
    N7[convert]
    N8[create_app]
    N9[exists]
    N10[extract_title]
    N11[get_wiki_structure]
    N12[glob]
    N13[index]
    N14[is_dir]
    N15[is_file]
    N16[iterdir]
    N17[jsonify]
    N18[loads]
    N19[main]
    N20[read_text]
    N21[redirect]
    N22[render_markdown]
    N23[render_template_string]
    N24[run]
    N25[run_server]
    N26[search_json]
    N27[title]
    N28[url_for]
    N29[view_page]
    N11 --> N12
    N11 --> N10
    N11 --> N16
    N11 --> N14
    N11 --> N27
    N10 --> N20
    N10 --> N27
    N22 --> N1
    N22 --> N7
    N6 --> N27
    N6 --> N9
    N13 --> N21
    N13 --> N28
    N26 --> N4
    N26 --> N9
    N26 --> N17
    N26 --> N18
    N26 --> N20
    N29 --> N4
    N29 --> N9
    N29 --> N15
    N29 --> N20
    N29 --> N22
    N29 --> N11
    N29 --> N10
    N29 --> N6
    N29 --> N23
    N8 --> N2
    N8 --> N9
    N8 --> N3
    N25 --> N8
    N25 --> N24
    N19 --> N0
    N19 --> N5
    N19 --> N2
    N19 --> N25
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
```

## See Also

- [test_manifest](../../../tests/test_manifest.md) - shares 2 dependencies
- [vectorstore](../core/vectorstore.md) - shares 2 dependencies
