# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

This project provides a local MCP server that enables private repository documentation with DeepWiki-style capabilities. It offers tools for exporting documentation to HTML, serving a web interface for browsing, and watching for changes in the repository. The system supports configurable indexing, chunking, and embedding of code and documentation content.

## Key Features

- **MCP Server Implementation**: The [`main`](files/src/local_deepwiki/export/html.md) function in `src/local_deepwiki/server.py` demonstrates the core MCP server setup using `stdio_server` and `server.run` for handling communication protocols.

- **Configurable Indexing and Embedding**: The `src/local_deepwiki/core/indexer.py` class supports initialization with repository paths and optional embedding provider configuration, allowing selection between local and OpenAI embedding models.

- **Web Server for Documentation Browsing**: The `run_server` function in `src/local_deepwiki/web/app.py` creates and runs a Flask web application that serves documentation from a specified wiki path with customizable host, port, and debug options.

- **Chunking Configuration Support**: The `src/local_deepwiki/core/chunker.py` class initializes with optional chunking configuration and uses a [`CodeParser`](files/src/local_deepwiki/core/parser.md) for processing code content during the chunking process.

- **Global Configuration Management**: The [`get_config`](files/src/local_deepwiki/config.md) function in `src/local_deepwiki/config.py` provides access to a global configuration instance that can be loaded and reused throughout the application.

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 15 more...

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
