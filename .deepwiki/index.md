# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Model Context Protocol (MCP) server that generates documentation for private repositories. It provides both a server interface for MCP clients and a web application for browsing generated documentation, with support for multiple LLM providers including Ollama, OpenAI, and Anthropic.

## Key Features

- **MCP Server Integration** - Implements a Model Context Protocol server with stdio communication for integration with MCP clients
- **Multiple LLM Provider Support** - Configurable support for Ollama (with local hosting), OpenAI, and Anthropic language models through dedicated provider classes
- **Repository Indexing** - Core indexer functionality that processes repository contents with configurable embedding providers (local or OpenAI)
- **Web Interface** - Built-in Flask web server for browsing and serving generated wiki documentation
- **Export Capabilities** - Multiple export formats including HTML and PDF through dedicated command-line tools

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 16 more...

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
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`