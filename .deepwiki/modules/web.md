# Module: web

## Module Purpose

The `web` module provides the Flask-based web interface and API endpoints for the Local DeepWiki MCP Server. It exposes a browser-based UI with chat, research, and codemap capabilities that allow users to interact with indexed codebases. The module handles HTTP routing, SSE streaming for real-time updates, and integrates with core components like vector stores, LLM providers, and query services.

## Key Classes and Functions

### `WebProviders` (NamedTuple)
A named tuple containing shared providers used across web route handlers:
- `vector_store`: Vector store instance for codebase embeddings
- `llm`: LLM provider for generating responses
- `config`: Configuration object

### `get_wiki_path()` (function)
Retrieves the current WIKI_PATH from Flask app configuration or falls back to a module-level global. Used by route handlers to determine where wiki data is stored.

### `create_providers()` (function)
Creates and returns a [`WebProviders`](../files/src/local_deepwiki/web/utils.md) tuple containing:
- A configured [`VectorStore`](../files/src/local_deepwiki/core/vectorstore/store.md) instance
- An LLM provider
- The application configuration

Used by codemap, research, and chat routes to initialize shared components.

### `create_query_service()` (function)
Creates a [`QueryService`](../files/src/local_deepwiki/services/query_service.md) instance using providers created via `create_providers()`. Provides query capabilities for the web UI.

### `api_research()` (function)
Handles deep research requests over an indexed codebase via Server-Sent Events (SSE). Accepts a question and streams progress updates, final results, and errors back to the client.

### `codemap_page()` (function)
Renders the interactive codemap visualization page. Shows an onboarding page if the wiki hasn't been indexed yet.

### `api_codemap_overview()` (function)
Returns a module-level architecture overview as JSON, including modules, edges, and summary.

### `api_codemap_topics()` (function)
Returns suggested codemap topics based on the indexed repository's call graph hubs.

### `api_codemap()` (function)
Handles codemap generation requests with streaming progress updates. Supports different focus modes (execution_flow, data_flow, dependency_chain) and caching.

## How Components Interact

1. **Route Handlers**: Web endpoints ([`api_research`](../files/src/local_deepwiki/web/routes_research.md), [`api_codemap`](../files/src/local_deepwiki/web/routes_codemap.md), etc.) use `get_wiki_path()` to locate the wiki directory.
2. **Provider Creation**: Each route handler calls `create_providers()` to get shared [`VectorStore`](../files/src/local_deepwiki/core/vectorstore/store.md), [`LLMProvider`](../files/src/local_deepwiki/providers/base.md), and [`Config`](../files/src/local_deepwiki/config/models.md) instances.
3. **[Query Service](../files/src/local_deepwiki/services/query_service.md)**: Routes may call `create_query_service()` to get a configured [`QueryService`](../files/src/local_deepwiki/services/query_service.md) for more complex queries.
4. **Streaming Responses**: SSE endpoints like [`api_research`](../files/src/local_deepwiki/web/routes_research.md) and [`api_codemap`](../files/src/local_deepwiki/web/routes_codemap.md) use `stream_async_generator()` from `routes_chat.py` to send data incrementally.
5. **Caching**: Codemap routes utilize caching functions ([`read_cache`](../files/src/local_deepwiki/generators/codemap/cache.md), [`write_cache`](../files/src/local_deepwiki/generators/codemap/cache.md)) in `generators.codemap.cache`.
6. **Async Operations**: All web endpoints that perform heavy computation (research, codemap generation) are async and run using `asyncio`.

## Usage Examples

### Starting the Web Server```bash
uv run deepwiki serve .deepwiki --port 8080
```
### Making a Research Request```python
import requests

response = requests.post(
    "http://localhost:8080/api/research",
    json={"question": "How does the authentication flow work?"},
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```
### Generating a Codemap```python
import requests

response = requests.post(
    "http://localhost:8080/api/codemap",
    json={
        "query": "user login process",
        "focus": "execution_flow",
        "max_depth": 3,
        "max_nodes": 20
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```
## Dependencies

- `flask` - Web framework for routing and HTTP handling
- `local_deepwiki.config` - Configuration management
- `local_deepwiki.core.vectorstore` - Vector database operations
- `local_deepwiki.providers.base` - LLM provider base classes
- `local_deepwiki.services.query_service` - Query execution service
- `local_deepwiki.web.routes_chat` - SSE streaming utilities
- `local_deepwiki.generators.codemap` - Codemap generation components
- `local_deepwiki.core.deep_research` - Deep research pipeline
- `local_deepwiki.logging` - Logging utilities
- `local_deepwiki.errors` - Error handling utilities

The module also depends on components from the core package like [`VectorStore`](../files/src/local_deepwiki/core/vectorstore/store.md), [`QueryService`](../files/src/local_deepwiki/services/query_service.md), and various LLM providers, as well as web UI templates defined in the project's template directories.

## Relevant Source Files

The following source files were used to generate this documentation:

- `src/local_deepwiki/web/__init__.py`
- [`src/local_deepwiki/web/utils.py:15-20`](../files/src/local_deepwiki/web/utils.md)
- [`src/local_deepwiki/web/routes_research.py:30-183`](../files/src/local_deepwiki/web/routes_research.md)
- [`src/local_deepwiki/web/routes_codemap.py:37-49`](../files/src/local_deepwiki/web/routes_codemap.md)
- [`src/local_deepwiki/web/app.py:84-110`](../files/src/local_deepwiki/web/app.md)
- [`src/local_deepwiki/web/routes_chat.py:29-78`](../files/src/local_deepwiki/web/routes_chat.md)
