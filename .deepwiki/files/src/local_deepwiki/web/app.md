# app.py

## File Overview

This file contains the main Flask web application for DeepWiki, providing a web interface for browsing and interacting with wiki content. It serves as the entry point for the web server and handles HTTP routes for viewing pages, searching, and chat functionality.

## Functions

### create_app

Creates and configures a Flask application instance for serving wiki content.

**Parameters:**
- `wiki_path` (str | Path): Path to the wiki directory to serve

**Returns:**
- Flask: Configured Flask application instance

**Raises:**
- ValueError: If the specified wiki path does not exist

The function sets up the global `WIKI_PATH` variable and validates that the wiki directory exists before returning the Flask app.

### run_server

Starts the DeepWiki web server with the specified configuration.

**Parameters:**
- `wiki_path` (str | Path): Path to the wiki directory to serve
- `host` (str, optional): Host address to bind to. Defaults to "127.0.0.1"
- `port` (int, optional): Port number to listen on. Defaults to 8080
- `debug` (bool, optional): Whether to run in debug mode. Defaults to False

This function creates the Flask app using create_app, logs startup information, and starts the development server.

## Route Handlers

The file contains several route handler functions that process HTTP requests:

### get_wiki_structure
Analyzes the wiki directory structure for navigation purposes.

### extract_title
Extracts page titles from markdown content.

### render_markdown
Converts markdown content to HTML for display.

### build_breadcrumb
Generates navigation breadcrumbs for wiki pages.

### index
Handles the root route for the wiki homepage.

### search_json
Provides JSON search functionality for wiki content.

### view_page
Renders individual wiki pages from markdown files.

### chat_page
Handles the chat interface route.

### api_chat
Processes chat API requests with streaming responses.

## Streaming Support

The application includes several utility functions for handling asynchronous streaming:

### stream_async_generator
Converts async generators to synchronous streams for Flask responses.

### run_async
Executes async functions in a separate thread.

### collect
Collects streaming responses for processing.

## Related Components

This file integrates with several other components of the DeepWiki system:

- **VectorStore**: Used for semantic search capabilities
- **Embedding providers**: For generating content embeddings
- **LLM providers**: For chat functionality
- **Configuration system**: Via [get_config](../config.md) for application settings
- **Logging system**: Via get_logger for application logging

## Usage Example

```python
from local_deepwiki.web.app import create_app, run_server

# Create app programmatically
app = create_app("/path/to/wiki")

# Or run server directly
run_server("/path/to/wiki", host="0.0.0.0", port=8080, debug=True)
```

The web application provides a complete interface for browsing wiki content, performing searches, and interacting with AI chat functionality through a web browser.

## API Reference

### Functions

#### `get_wiki_structure`

```python
def get_wiki_structure(wiki_path: Path) -> tuple[list, dict, list | None]
```

Get wiki pages and sections, with optional hierarchical TOC.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | - |

**Returns:** `tuple[list, dict, list | None]`


#### `extract_title`

```python
def extract_title(md_file: Path) -> str
```

Extract title from markdown file.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `md_file` | `Path` | - | - |

**Returns:** `str`


#### `render_markdown`

```python
def render_markdown(content: str) -> str
```

Render markdown to HTML.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | - |

**Returns:** `str`


#### `build_breadcrumb`

```python
def build_breadcrumb(wiki_path: Path, current_path: str) -> str
```

Build breadcrumb navigation HTML with clickable links.  For a path like 'files/src/local_deepwiki/core/chunker.md', generates: Home > Files > src > local_deepwiki > core > chunker  Each segment links to its index.md if one exists in that folder.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | - |
| `current_path` | `str` | - | - |

**Returns:** `str`


#### `index`

`@app.route("/")`

```python
def index()
```

Redirect to index.md.


#### `search_json`

`@app.route("/search.json")`

```python
def search_json()
```

Serve the search index JSON file.


#### `view_page`

`@app.route("/wiki/<path:path>")`

```python
def view_page(path: str)
```

View a wiki page.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | - | - |


#### `stream_async_generator`

```python
def stream_async_generator(async_gen_factory: Callable[[], AsyncIterator[str]]) -> Iterator[str]
```

Bridge an async generator to a sync generator using a queue.  This allows streaming async results through Flask's synchronous response handling.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `async_gen_factory` | `Callable[[], AsyncIterator[str]]` | - | A callable that returns an async iterator. |

**Returns:** `Iterator[str]`


#### `run_async`

```python
def run_async() -> None
```

**Returns:** `None`


#### `collect`

```python
async def collect() -> None
```

**Returns:** `None`


#### `format_sources`

```python
def format_sources(search_results: list[Any]) -> list[dict[str, Any]]
```

Format search results as source citations.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search_results` | `list[Any]` | - | List of [SearchResult](../models.md) objects. |

**Returns:** `list[dict[str, Any]]`


#### `build_prompt_with_history`

```python
def build_prompt_with_history(question: str, history: list[dict[str, str]], context: str) -> str
```

Build a prompt that includes conversation history for follow-up questions.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | `str` | - | The current question. |
| `history` | `list[dict[str, str]]` | - | Previous Q&A exchanges. |
| `context` | `str` | - | Code context from search results. |

**Returns:** `str`


#### `chat_page`

`@app.route("/chat")`

```python
def chat_page()
```

Render the chat interface.


#### `api_chat`

`@app.route("/api/chat", methods=["POST"])`

```python
def api_chat()
```

Handle chat Q&A with streaming response.  Expects JSON body with: - question: The user's question - history: Optional list of previous Q&A exchanges


#### `generate_response`

```python
async def generate_response() -> AsyncIterator[str]
```

Async generator that streams the chat response.

**Returns:** `AsyncIterator[str]`


#### `api_research`

`@app.route("/api/research", methods=["POST"])`

```python
def api_research()
```

Handle deep research with streaming progress updates.  Expects JSON body with: - question: The user's question


#### `run_research`

```python
async def run_research() -> AsyncIterator[str]
```

Async generator that runs deep research with progress updates.

**Returns:** `AsyncIterator[str]`


#### `on_progress`

```python
async def on_progress(progress: ResearchProgress) -> None
```


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `progress` | [`ResearchProgress`](../models.md) | - | - |

**Returns:** `None`


#### `create_app`

```python
def create_app(wiki_path: str | Path) -> Flask
```

Create Flask app with wiki path configured.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `str | Path` | - | - |

**Returns:** `Flask`


#### `run_server`

```python
def run_server(wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False)
```

Run the wiki web server.


| Parameter | Type | Default | Description |
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
    N0[VectorStore]
    N1[abort]
    N2[api_chat]
    N3[api_research]
    N4[async_gen_factory]
    N5[build_breadcrumb]
    N6[collect]
    N7[create_app]
    N8[dumps]
    N9[exception]
    N10[exists]
    N11[extract_title]
    N12[generate_response]
    N13[get_cached_llm_provider]
    N14[get_config]
    N15[get_embedding_provider]
    N16[get_vector_db_path]
    N17[get_wiki_path]
    N18[get_wiki_structure]
    N19[jsonify]
    N20[main]
    N21[put]
    N22[read_text]
    N23[render_markdown]
    N24[run_async]
    N25[run_research]
    N26[search_json]
    N27[stream_async_generator]
    N28[title]
    N29[view_page]
    N18 --> N10
    N18 --> N22
    N18 --> N11
    N18 --> N28
    N11 --> N22
    N11 --> N28
    N5 --> N28
    N5 --> N10
    N26 --> N1
    N26 --> N10
    N26 --> N19
    N26 --> N22
    N29 --> N1
    N29 --> N10
    N29 --> N22
    N29 --> N23
    N29 --> N18
    N29 --> N11
    N29 --> N5
    N27 --> N4
    N27 --> N21
    N27 --> N6
    N27 --> N8
    N24 --> N4
    N24 --> N21
    N24 --> N6
    N6 --> N4
    N6 --> N21
    N2 --> N19
    N2 --> N14
    N2 --> N16
    N2 --> N10
    N2 --> N8
    N2 --> N15
    N2 --> N0
    N2 --> N17
    N2 --> N13
    N2 --> N9
    N2 --> N27
    N12 --> N14
    N12 --> N16
    N12 --> N10
    N12 --> N8
    N12 --> N15
    N12 --> N0
    N12 --> N17
    N12 --> N13
    N12 --> N9
    N3 --> N19
    N3 --> N14
    N3 --> N16
    N3 --> N10
    N3 --> N8
    N3 --> N15
    N3 --> N0
    N3 --> N17
    N3 --> N13
    N3 --> N21
    N3 --> N9
    N3 --> N27
    N25 --> N14
    N25 --> N16
    N25 --> N10
    N25 --> N8
    N25 --> N15
    N25 --> N0
    N25 --> N17
    N25 --> N13
    N25 --> N21
    N25 --> N9
    N7 --> N10
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
```

## Relevant Source Files

- `src/local_deepwiki/web/app.py:32-67`
