# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Model Context Protocol (MCP) server that provides AI-powered documentation generation for private code repositories. It combines multiple LLM providers (Ollama, OpenAI, Anthropic) with embedding-based indexing to create comprehensive wiki-style documentation from your codebase.

## Key Features

- **Multiple [LLM Provider](files/src/local_deepwiki/providers/base.md) Support** - Integrates with Ollama (local), OpenAI, and Anthropic APIs for flexible AI-powered documentation generation
- **MCP Server Architecture** - Implements the Model Context Protocol for seamless integration with AI assistants and development tools
- **Web Interface** - Includes a built-in Flask web server (`deepwiki-serve`) for browsing generated documentation at configurable host and port
- **Multiple Export Formats** - Supports both HTML (`deepwiki-export`) and PDF (`deepwiki-export-pdf`) export capabilities for documentation
- **Repository Indexing** - Features a core indexer that processes repository files with configurable embedding providers for semantic search and analysis

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