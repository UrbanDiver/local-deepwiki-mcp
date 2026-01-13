# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

This project provides a local MCP server that enables private repository documentation generation and serving, similar to DeepWiki. It supports both local and cloud-based LLM providers for processing repository content and generating documentation. The system can be run as a web server or as a command-line tool for exporting documentation.

## Key Features

- **MCP Server Implementation**: The [`main`](files/src/local_deepwiki/watcher.md) function in `src/local_deepwiki/server.py` demonstrates the core MCP server setup using `stdio_server` and `server.run` for handling MCP protocol communication
- **Ollama LLM Integration**: The [`OllamaConfig`](files/src/local_deepwiki/config.md) and `OllamaProvider` classes in `src/local_deepwiki/providers/llm/ollama.py` show support for local LLM inference through Ollama API
- **Repository Indexing**: The `Indexer` class in `src/local_deepwiki/core/indexer.py` provides repository indexing capabilities with configurable embedding providers
- **Web Server Interface**: The `run_server` function in `src/local_deepwiki/web/app.py` enables serving documentation via a web interface with configurable host, port, and debug options
- **Configuration Management**: The [`Config`](files/src/local_deepwiki/config.md) class in `src/local_deepwiki/config.py` provides structured configuration handling with support for multiple embedding and LLM providers

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
│   ├── test_indexer.py
│   ├── test_manifest.py
│   ├── test_models.py
│   ├── test_ollama_health.py
│   ├── test_parser.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`