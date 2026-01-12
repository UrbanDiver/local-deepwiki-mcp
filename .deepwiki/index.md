# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

This project provides a local MCP (Model Control Protocol) server that enables private repository documentation with DeepWiki-style capabilities. It offers both a web server interface and a file watching functionality to continuously update documentation. The system supports configurable embedding providers and chunking strategies for processing code repositories.

## Key Features

- **MCP Server Implementation**: The `main` function in `server.py` demonstrates the core MCP server setup using `stdio_server` and `server.run` to handle communication protocols
- **Configurable Embedding Providers**: The `Indexer.__init__` method in `indexer.py` accepts an `embedding_provider_name` parameter that can be set to "local" or "openai" for different embedding capabilities
- **Web Server Interface**: The `run_server` function in `web/app.py` provides a web interface for serving documentation with customizable host, port, and debug options
- **Chunking Configuration**: The `Chunker.__init__` method in `chunker.py` initializes with optional `ChunkingConfig` and uses a `CodeParser` for processing code content
- **Configuration Management**: The `get_config` function in `config.py` provides global configuration access with lazy loading of the `Config.load()` method

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 11 more...

## Directory Structure

```
local-deepwiki-mcp/
├── src/
│   └── local_deepwiki/
├── tests/
│   ├── __init__.py
│   ├── test_api_docs.py
│   ├── test_callgraph.py
│   ├── test_chunker.py
│   ├── test_config.py
│   ├── test_crosslinks.py
│   ├── test_incremental_wiki.py
│   ├── test_manifest.py
│   ├── test_parser.py
│   ├── test_search.py
│   ├── test_see_also.py
│   ├── test_source_refs.py
│   ├── test_toc.py
│   ├── test_watcher.py
│   └── test_web.py
├── CLAUDE.md
├── README.md
├── TODO.md
├── WIKI_IMPROVEMENTS.md
├── pyproject.toml
└── uv.lock
```

## Quick Start

- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`