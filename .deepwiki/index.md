# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

`local-deepwiki-mcp` is a local MCP server designed for private repository documentation, similar to DeepWiki. It provides tools for exporting documentation, serving it via a web interface, watching for changes, and managing configurations.

## Key Features

- **Local MCP Server**: The [`main`](files/src/local_deepwiki/export/html.md) function in `src/local_deepwiki/server.py` initializes and runs the local-deepwiki MCP server using asynchronous I/O operations.
  
- **PDF Export Functionality**: The `TestMainCli` class in `tests/test_pdf_export.py` includes methods to test various aspects of PDF export functionality, ensuring that the export process handles different scenarios correctly.

- **Configuration Management**: The `config.py` module in `src/local_deepwiki/config.py` defines configuration classes such as [`ResearchPreset`](files/src/local_deepwiki/config.md), [`LocalEmbeddingConfig`](files/src/local_deepwiki/config.md), and others, which are crucial for managing settings within the application.

- **[LLM Provider](files/src/local_deepwiki/providers/base.md) Integration**: The `__init__` method in `src/local_deepwiki/providers/llm/ollama.py` initializes an Ollama provider with specific model and base URL parameters, allowing integration of language models into the server.

- **Change Watching Mechanism**: The `TestMain` class in `tests/test_watcher.py` includes methods to test the watcher functionality, ensuring that it behaves correctly under various conditions, such as path existence checks and interrupt handling.

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
│   ├── test_context_builder.py
│   ├── test_coverage.py
│   ├── test_crosslinks.py
│   ├── test_deep_research.py
│   ├── test_diagrams.py
│   ├── test_export_init.py
│   ...
...
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`