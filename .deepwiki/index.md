# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Python-based documentation system that provides an MCP (Model Context Protocol) server for generating and serving private repository documentation. The system includes multiple export formats, a web interface, and file watching capabilities for automatic documentation updates.

## Key Features

- **MCP Server Integration** - Runs as an MCP server with stdio communication for integration with AI tools and editors
- **Multiple Export Formats** - Supports HTML export via `deepwiki-export` and PDF export via `deepwiki-export-pdf` commands
- **Web Interface** - Includes a Flask-based web server accessible through the `deepwiki-serve` command
- **File Watching** - Automatic documentation regeneration with `deepwiki-watch` when repository files change
- **Multi-Provider LLM Support** - Configurable integration with Ollama, OpenAI, and Anthropic language models for documentation generation

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
│   ├── test_crosslinks.py
│   ├── test_deep_research.py
│   ├── test_diagrams.py
│   ├── test_export_init.py
│   ├── test_git_utils.py
│   ├── test_handlers_coverage.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`