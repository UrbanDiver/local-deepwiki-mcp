# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Python-based Model Context Protocol (MCP) server that generates comprehensive documentation for private code repositories. The system provides multiple export formats including HTML and PDF, along with a web interface and file watching capabilities for automatic documentation updates.

## Key Features

• **MCP Server Integration** - Runs as an MCP server with stdio communication for integration with AI assistants and development tools

• **Multiple Export Formats** - Supports HTML export via `deepwiki-export` and PDF export via `deepwiki-export-pdf` commands

• **Web Interface** - Includes a Flask-based web server accessible through `deepwiki-serve` for interactive documentation browsing

• **File System Monitoring** - Provides `deepwiki-watch` functionality to automatically regenerate documentation when repository files change

• **Configurable LLM Providers** - Supports multiple LLM backends including Ollama, OpenAI, and Anthropic with customizable model configurations and embedding options

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 16 more...

## Directory Structure

```
local-deepwiki-mcp/
├── docs/
│   └── WIKI_ENHANCEMENTS.md
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
│   ├── test_coverage.py
│   ├── test_crosslinks.py
│   ├── test_deep_research.py
│   ├── test_diagrams.py
│   ├── test_export_init.py
│   ├── test_git_utils.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`