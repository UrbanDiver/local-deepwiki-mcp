# DeepWiki Web Application

## File Overview

This file implements a Flask-based web server for serving a local wiki documentation system. It provides functionality to render markdown files as HTML pages, organize wiki structure, and serve content through a web interface.

## Dependencies

- `flask`: Web framework for creating the server
- `markdown`: Markdown to HTML conversion
- `argparse`: Command-line argument parsing
- `pathlib.Path`: File system path manipulation

## Functions

### `run_server(wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False)`

**Purpose**: Starts the DeepWiki web server with specified configuration.

**Parameters**:
- `wiki_path`: Path to the wiki directory
- `host`: Host address to bind to (default: "127.0.0.1")
- `port`: Port number to bind to (default: 8080)
- `debug`: Enable debug mode (default: False)

**Usage**:
```python
run_server("/path/to/wiki", host="0.0.0.0", port=8080, debug=True)
```

### `create_app(wiki_path: str | Path) -> Flask`

**Purpose**: Creates and configures a Flask application with the specified wiki path.

**Parameters**:
- `wiki_path`: Path to the wiki directory

**Returns**: Configured Flask application instance

**Usage**:
```python
app = create_app("/path/to/wiki")
```

### `main()`

**Purpose**: Command-line entry point for running the server.

**Parameters**: None

**Usage**:
```bash
python app.py /path/to/wiki --host 0.0.0.0 --port 8080 --debug
```

### `view_page(path: str)`

**Purpose**: Renders a specific wiki page as HTML.

**Parameters**:
- `path`: Relative path to the markdown file

**Returns**: Rendered HTML page

**Usage**:
```python
# Called internally by Flask routes
```

### `get_wiki_structure(wiki_path: Path)`

**Purpose**: Analyzes the wiki directory structure to build navigation information.

**Parameters**:
- `wiki_path`: Path to the wiki directory

**Returns**: Tuple of (pages, sections) for navigation

### `extract_title(file_path: Path)`

**Purpose**: Extracts the title from a markdown file.

**Parameters**:
- `file_path`: Path to the markdown file

**Returns**: Title string extracted from the file

### `render_markdown(content: str)`

**Purpose**: Converts markdown content to HTML.

**Parameters**:
- `content`: Markdown text content

**Returns**: HTML formatted content

### `index()`

**Purpose**: Renders the main index page showing all wiki pages.

**Parameters**: None

**Returns**: Rendered HTML index page

## Usage Examples

### Starting the Server

```python
# Using CLI
python app.py /path/to/.deepwiki --host 0.0.0.0 --port 8080

# Using Python API
from src.local_deepwiki.web.app import run_server
run_server("/path/to/wiki", host="0.0.0.0", port=8080, debug=True)
```

### Creating a Custom App

```python
from src.local_deepwiki.web.app import create_app
from pathlib import Path

app = create_app(Path("/path/to/wiki"))
# Configure additional routes or settings as needed
```

## Key Features

- **Markdown Rendering**: Converts markdown files to HTML with proper formatting
- **Directory Navigation**: Builds navigation structure from wiki directory
- **Error Handling**: Proper HTTP error responses for missing pages or server issues
- **CLI Interface**: Command-line interface for easy server startup
- **Breadcrumbs**: Navigation breadcrumbs for page hierarchy
- **Debug Mode**: Support for Flask debug mode with detailed error reporting

## Notes

The application expects a `.deepwiki` directory structure containing markdown files. The `WIKI_PATH` global variable is used to store the configured wiki path for all routes and functions.