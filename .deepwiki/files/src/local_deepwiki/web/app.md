# DeepWiki Web Application Documentation

## File Overview

This file implements a Flask-based web application for serving a local wiki built with DeepWiki. It provides functionality to render markdown pages, build navigation structures, and serve the wiki content via a web interface.

## Dependencies

- `json`: For JSON serialization
- `pathlib.Path`: For path manipulation
- `flask.Flask`, `render_template_string`, `abort`, `redirect`, `url_for`, `jsonify`: Flask web framework components
- `markdown`: For rendering markdown content to HTML
- `argparse`: For command-line argument parsing

## Functions

### `run_server(wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False)`

**Purpose**: Starts the DeepWiki web server.

**Parameters**:
- `wiki_path`: Path to the wiki directory
- `host`: Host to bind to (default: "127.0.0.1")
- `port`: Port to bind to (default: 8080)
- `debug`: Enable debug mode (default: False)

**Returns**: None

**Example**:
```python
run_server("/path/to/wiki", host="0.0.0.0", port=8080, debug=True)
```

### `create_app(wiki_path: str | Path) -> Flask`

**Purpose**: Creates and configures a Flask application instance with the specified wiki path.

**Parameters**:
- `wiki_path`: Path to the wiki directory

**Returns**: Flask application instance

**Example**:
```python
app = create_app("/path/to/wiki")
```

### `main()`

**Purpose**: Command-line entry point for running the web server.

**Parameters**: None

**Returns**: None

**Example**:
```bash
python app.py /path/to/wiki --host 0.0.0.0 --port 8080 --debug
```

### `view_page(path: str)`

**Purpose**: Renders a specific wiki page for display in the browser.

**Parameters**:
- `path`: Relative path to the wiki page

**Returns**: Rendered HTML page or HTTP error

**Example**:
```python
# This function is used internally by Flask routes
# Access via: http://localhost:8080/page/path
```

### `get_wiki_structure(wiki_path: Path)`

**Purpose**: Builds a structure of all wiki pages and their sections.

**Parameters**:
- `wiki_path`: Path to the wiki directory

**Returns**: Tuple of (pages, sections) representing the wiki structure

**Note**: This function is referenced but not shown in the provided code.

### `extract_title(file_path: Path)`

**Purpose**: Extracts the title from a markdown file.

**Parameters**:
- `file_path`: Path to the markdown file

**Returns**: Title string extracted from the file

**Note**: This function is referenced but not shown in the provided code.

### `render_markdown(content: str) -> str`

**Purpose**: Converts markdown content to HTML.

**Parameters**:
- `content`: Markdown content as string

**Returns**: HTML content as string

**Note**: This function is referenced but not shown in the provided code.

### `build_breadcrumb(path: str) -> list`

**Purpose**: Builds breadcrumb navigation for a given path.

**Parameters**:
- `path`: Path to build breadcrumb for

**Returns**: List of breadcrumb items

**Note**: This function is referenced but not shown in the provided code.

### `index()`

**Purpose**: Renders the main index page showing all wiki pages.

**Parameters**: None

**Returns**: Rendered HTML index page

**Note**: This function is referenced but not shown in the provided code.

### `search_json()`

**Purpose**: Provides JSON endpoint for wiki search functionality.

**Parameters**: None

**Returns**: JSON response with search results

**Note**: This function is referenced but not shown in the provided code.

## Usage Examples

### Running the Server

```bash
# Run with default settings
python app.py

# Run with custom path and settings
python app.py /path/to/wiki --host 0.0.0.0 --port 8080 --debug
```

### Creating an Application Instance

```python
from app import create_app

app = create_app("/path/to/wiki")
```

### Server Configuration

```python
from app import run_server

run_server(
    wiki_path="/path/to/wiki",
    host="0.0.0.0",
    port=8080,
    debug=True
)
```

## Notes

- The `WIKI_PATH` global variable is set during `create_app()` and used by `view_page()`
- All functions are designed to work within the Flask application context
- Error handling is implemented with HTTP abort codes (404 for not found, 500 for internal errors)
- The application expects markdown files with `.md` extension in the wiki directory
- Breadcrumb navigation is built dynamically based on the requested page path

## See Also

- [test_web](../../../tests/test_web.md) - uses this
- [test_search](../../../tests/test_search.md) - uses this
- [search](../generators/search.md) - shares 2 dependencies
- [vectorstore](../core/vectorstore.md) - shares 2 dependencies
- [indexer](../core/indexer.md) - shares 2 dependencies
