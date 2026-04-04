# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP server enables private, local documentation generation and management for software repositories. It provides an intelligent, AI-powered wiki system that indexes codebases and generates contextual documentation. The project supports both local and hybrid deployment models with flexible configuration options.

## Key Features

- **AI-powered documentation generation** - Creates contextual wiki content using LLM providers (Anthropic, OpenAI, Ollama) with support for multiple programming languages including Python, TypeScript, JavaScript, Go, Rust, and more
- **Async architecture with provider abstraction** - All core operations use asyncio and implement provider abstraction for LLM and embedding services through base classes in `providers/base.py`
- **AST-aware code chunking** - Splits code into meaningful chunks at function and class boundaries using tree-sitter for more accurate documentation generation
- **Multi-model configuration support** - Supports configuration hierarchy with CLI args > env vars > config file > defaults, plus multiple example configs for local, cloud, and hybrid deployment
- **Comprehensive testing framework** - Includes pytest-based tests with async support, mocking of LLM/embedding providers, and shared test fixtures for consistent development workflows

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, nh3, ollama, openai, pandas, psutil, pydantic, pyyaml
  - Plus 19 more...

## Directory Structure

```
local-deepwiki-mcp/
├── docs/
│   ├── internal/
│   ├── plans/
│   ├── superpowers/
│   ├── plan-dual-audience-wiki-content.md
│   └── plan-lazy-wiki-generation.md
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
│   ├── test_agentic_workflows.py
│   ├── test_analysis_architecture.py
│   ├── test_analyze_diff.py
│   ├── test_anthropic_provider.py
│   ├── test_api_docs.py
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