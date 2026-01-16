# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP is a Model Context Protocol (MCP) server that generates comprehensive documentation for private code repositories. The system provides multiple interfaces including a web server, file watcher for automatic updates, and export capabilities to HTML and PDF formats, all designed to create DeepWiki-style documentation locally.

## Key Features

- **MCP Server Integration** - Implements a Model Context Protocol server with stdio communication for AI assistant integration, as shown in the [main](files/src/local_deepwiki/export/html.md) server entry point
- **Multiple [LLM Provider](files/src/local_deepwiki/providers/base.md) Support** - Integrates with various AI providers including Ollama (with configurable models and base URLs), Anthropic, and OpenAI through dedicated provider classes
- **Flexible Export Options** - Offers multiple export formats through dedicated CLI commands (`deepwiki-export` for HTML and `deepwiki-export-pdf` for PDF generation)
- **Real-time File Watching** - Includes a watcher service (`deepwiki-watch`) that can monitor repository changes and trigger documentation updates, with options for full rebuilds and skipping initial indexing
- **Configurable Documentation Generation** - Uses YAML-based configuration with research presets, embedding configurations, and parsing controls to customize documentation output

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
│   ├── test_export_init.py
│   ├── test_git_utils.py
│   ├── test_handlers_coverage.py
│   ├── test_html_export.py
│   ├── test_incremental_wiki.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`