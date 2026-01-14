# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Model Context Protocol (MCP) server that generates and serves documentation for private code repositories. The system provides both a web interface for browsing documentation and command-line tools for exporting documentation in various formats including HTML and PDF.

## Key Features

- **MCP Server Integration** - Implements a Model Context Protocol server with stdio communication for integration with MCP-compatible tools
- **Multiple LLM Provider Support** - Configurable support for different language model providers including Ollama, OpenAI, and Anthropic through a plugin-based architecture
- **Web Server Interface** - Built-in Flask web server for serving and browsing generated documentation with configurable host and port settings
- **Repository Indexing** - Core indexing functionality that processes repository contents with configurable embedding providers for document search and retrieval
- **Multiple Export Formats** - Command-line tools for exporting documentation to HTML and PDF formats, plus a file watcher for automated regeneration

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