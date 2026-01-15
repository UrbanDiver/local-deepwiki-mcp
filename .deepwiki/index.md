# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Model Context Protocol (MCP) server that generates documentation for private code repositories. It provides both a server interface for MCP clients and a web application for browsing generated documentation, with support for multiple LLM providers including Ollama, OpenAI, and Anthropic.

## Key Features

- **MCP Server Integration** - Runs as an MCP server with stdio communication for integration with MCP-compatible clients, as shown in the [main](files/src/local_deepwiki/export/html.md) server entry point
- **Multiple [LLM Provider](files/src/local_deepwiki/providers/base.md) Support** - Configurable support for Ollama (with local hosting at localhost:11434), OpenAI, and Anthropic providers through the [LLMConfig](files/src/local_deepwiki/config.md) system
- **Web Interface** - Built-in Flask web server (`deepwiki-serve`) that serves generated documentation at a configurable host and port
- **Repository Indexing** - Core indexer that processes repository contents with configurable embedding providers (local or OpenAI) for document search and retrieval
- **Multiple Export Formats** - Supports both HTML export (`deepwiki-export`) and PDF export (`deepwiki-export-pdf`) with a file watcher mode (`deepwiki-watch`) for continuous updates

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
│   ├── test_changelog.py
│   ├── test_chunker.py
│   ├── test_config.py
│   ├── test_crosslinks.py
│   ├── test_deep_research.py
│   ├── test_diagrams.py
│   ├── test_git_utils.py
│   ├── test_html_export.py
│   ├── test_incremental_wiki.py
│   ├── test_indexer.py
│   ├── test_llm_cache.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`