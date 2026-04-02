# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP server enables private, local documentation generation and querying for code repositories using a modular, configurable architecture. It supports multiple LLM providers and offers tools for indexing, searching, and analyzing repository structure and content. The system is designed for use in development environments where privacy and local execution are priorities.

## Key Features

- **Multi-provider LLM support** — Configurable integration with providers like Anthropic, OpenAI, and Ollama through a unified abstraction layer
- **AST-aware code chunking** — Intelligent splitting of source code into semantic chunks at function and class boundaries using tree-sitter
- **Configurable architecture analysis** — Built-in tools for architecture quality gates, trend analysis, and health reporting
- **Async core architecture** — Full asynchronous implementation throughout for efficient handling of concurrent operations
- **Modular CLI and MCP server** — Supports command-line tools for indexing, searching, and serving documentation via MCP protocol

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