# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

A local MCP server that enables private repository documentation with deepwiki-style features. It provides tools for exporting documentation as HTML or PDF, watching repository changes, and serving documentation via an API. The system supports multiple LLM providers including Ollama, OpenAI, and Anthropic for embedding and language model operations.

## Key Features

- **MCP Server Implementation**: Implements a standard input/output MCP server using `stdio_server` and `server.run` as shown in `src/local_deepwiki/server.py`
- **Ollama LLM Integration**: Supports Ollama as an LLM provider with configurable model and base URL as seen in `src/local_deepwiki/providers/llm/ollama.py`
- **Documentation Export Capabilities**: Includes HTML and PDF export functionality with command-line interfaces in `src/local_deepwiki/export/` and `src/local_deepwiki/export/pdf.py`
- **Repository Change Watching**: Features a file watcher that monitors repository changes and triggers reindexing as demonstrated in `tests/test_watcher.py`
- **Configuration Management**: Supports multiple embedding and LLM configurations through `src/local_deepwiki/config.py` with classes like [`OllamaConfig`](files/src/local_deepwiki/config.md) and [`OpenAILLMConfig`](files/src/local_deepwiki/config.md)

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