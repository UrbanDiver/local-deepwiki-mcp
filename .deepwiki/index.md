# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki-style MCP server for private repository documentation. This project provides a local server that enables intelligent, AI-powered search and documentation of code repositories using a hybrid approach combining local LLMs, embeddings, and structured data indexing. It supports both local and cloud-based LLM providers and offers a range of CLI tools for indexing, searching, and exporting documentation.

## Key Features

- **Hybrid LLM Support**: Supports both local (e.g., Ollama) and cloud (e.g., Anthropic, OpenAI) language model providers through a unified provider abstraction layer
- **AST-Aware Code Chunking**: Uses tree-sitter to split code at function and class boundaries for more precise semantic indexing and retrieval
- **Multi-Format Documentation Export**: Includes CLI tools for exporting documentation to HTML and PDF formats
- **Architecture Quality Gates**: Provides commands for checking architecture health and quality through automated analysis and reporting
- **Async Core Architecture**: All core operations are implemented using asyncio for efficient concurrent processing and responsiveness

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, nh3, ollama, openai, pandas, psutil, pydantic, pyyaml
  - Plus 18 more...

## Directory Structure

```
local-deepwiki-mcp/
├── examples/
│   ├── config-cloud.yaml
│   ├── config-hybrid.yaml
│   ├── config-local.yaml
│   └── roles.yaml
├── src/
│   └── local_deepwiki/
├── tests/
│   ├── fixtures/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_access_control.py
│   ├── test_agentic_rag.py
│   ├── test_analysis_architecture.py
│   ├── test_analyze_diff.py
│   ├── test_anthropic_provider.py
│   ├── test_api_docs.py
│   ├── test_architecture_compare.py
│   ├── test_architecture_composite.py
│   ├── test_architecture_health.py
│   ├── test_architecture_report.py
│   ├── test_architecture_trends.py
│   ├── test_ask_about_diff.py
│   ├── test_audit.py
│   ...
...
```

## Quick Start

- `deepwiki` → `local_deepwiki.cli.main:main`
- `deepwiki-config` → `local_deepwiki.cli.config_cli:main`
- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-search` → `local_deepwiki.cli.interactive_search:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`