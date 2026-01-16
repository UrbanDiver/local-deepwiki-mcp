# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki-style MCP server is a Python-based tool for generating private repository documentation. It provides an MCP (Model Context Protocol) server interface along with multiple export formats and a file watcher system for automated documentation updates.

## Key Features

- **MCP Server Interface** - Implements an MCP server with stdio communication for integration with AI tools and editors (as shown in the [`main`](files/src/local_deepwiki/export/pdf.md) function using `stdio_server`)

- **Multiple Export Formats** - Supports both HTML and PDF export functionality through dedicated CLI commands (`deepwiki-export` and `deepwiki-export-pdf`)

- **File Watching System** - Includes a watcher component (`deepwiki-watch`) that can monitor repository changes and trigger documentation rebuilds automatically

- **Multiple [LLM Provider](files/src/local_deepwiki/providers/base.md) Support** - Integrates with various AI providers including Ollama (with configurable models and base URLs), OpenAI, and Anthropic for content generation

- **Web Server Interface** - Provides a web-based interface through Flask (`deepwiki-serve`) for accessing and viewing generated documentation

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