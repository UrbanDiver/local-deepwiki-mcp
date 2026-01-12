# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

This project provides a local MCP server that enables private repository documentation with DeepWiki-style functionality. It offers tools for exporting documentation, serving a web interface, and watching for changes in the repository. The system supports configurable chunking and embedding providers for processing code and documentation content.

## Key Features

- **MCP Server Implementation** - The [`main`](files/src/local_deepwiki/export/html.md) function in `src/local_deepwiki/server.py` demonstrates the core MCP server setup using `stdio_server` and `server.run` for handling communication protocols
- **Configurable Embedding Providers** - The `Indexer.__init__` method in `src/local_deepwiki/core/indexer.py` accepts an `embedding_provider_name` parameter that supports overriding between "local" and "openai" embedding providers
- **Web Server Interface** - The `run_server` function in `src/local_deepwiki/web/app.py` provides a web server with configurable host, port, and debug options for serving the wiki content
- **Chunking Configuration Support** - The `Chunker.__init__` method in `src/local_deepwiki/core/chunker.py` initializes with optional [`ChunkingConfig`](files/src/local_deepwiki/config.md) and defaults to global configuration values
- **Repository Path Handling** - The `Indexer.__init__` method in `src/local_deepwiki/core/indexer.py` accepts a `repo_path` parameter for specifying the repository root directory to be processed

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 11 more...

## Directory Structure

```
local-deepwiki-mcp/
├── html-export/
│   ├── files/
│   ├── modules/
│   ├── architecture.html
│   ├── dependencies.html
│   ├── index.html
│   └── search.json
├── src/
│   └── local_deepwiki/
├── tests/
│   ├── __init__.py
│   ├── test_api_docs.py
│   ├── test_callgraph.py
│   ├── test_chunker.py
│   ├── test_config.py
│   ├── test_crosslinks.py
│   ├── test_diagrams.py
│   ├── test_html_export.py
│   ├── test_incremental_wiki.py
│   ├── test_manifest.py
│   ├── test_parser.py
│   ├── test_search.py
│   ├── test_see_also.py
│   ├── test_source_refs.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`