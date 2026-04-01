# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP server enables private, local repository documentation with AI-powered querying and analysis. It supports multiple LLM providers including Anthropic, Ollama, and OpenAI, and offers both local and hybrid indexing strategies. The system provides architecture analysis, diff-aware querying, and agentic RAG capabilities for understanding codebases.

## Key Features

- **Multi-provider LLM support** - Integrates with Anthropic, Ollama, and OpenAI through a unified provider abstraction layer
- **AST-aware code chunking** - Splits code into semantic chunks at function and class boundaries using tree-sitter parsing
- **Architecture analysis and reporting** - Provides comprehensive architecture health checks, trends analysis, and quality gate enforcement
- **Diff-aware querying** - Enables querying about code changes and differences through specialized analysis functions
- **Configurable indexing strategies** - Supports local, cloud, and hybrid indexing configurations through YAML-based configuration files

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