# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

This project provides a local MCP server that enables private repository documentation generation and serving, similar to DeepWiki. It offers tools for indexing code repositories, generating documentation, and serving that documentation via a web interface. The system supports both local and external embedding providers for semantic search and documentation generation.

## Key Features

- **MCP Server Implementation**: The [`main`](files/src/local_deepwiki/export/html.md) function in `server.py` demonstrates the core MCP server setup using `stdio_server` and `server.run` for handling MCP protocol communication
- **Configurable Embedding Providers**: The `Indexer.__init__` method accepts an `embedding_provider_name` parameter that allows switching between "local" and "openai" embedding providers
- **Web Server for Documentation Serving**: The `run_server` function in `web/app.py` creates and runs a Flask web application to serve documentation from a specified wiki path
- **Chunking Configuration Support**: The `Chunker.__init__` method initializes with optional [`ChunkingConfig`](files/src/local_deepwiki/config.md) and uses `get_config().chunking` as default when no config is provided
- **Repository Indexing**: The `Indexer.__init__` method accepts a `repo_path` parameter to initialize indexing of code repositories for documentation generation

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 14 more...

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