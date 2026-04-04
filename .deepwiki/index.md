# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki-style MCP server for private repository documentation. This project provides a local infrastructure for indexing and querying code repositories using LLM-powered tools, with support for both local and cloud-based language model providers. It enables developers to create, maintain, and search documentation directly from their codebase.

## Key Features

- **Async-native architecture** - All core operations use asyncio for efficient concurrent processing
- **AST-aware code chunking** - Code is split at function and class boundaries using tree-sitter for more precise semantic indexing
- **Multi-provider LLM support** - Supports local (Ollama), cloud (Anthropic, OpenAI) and hybrid configurations through provider abstraction
- **Comprehensive testing framework** - Uses pytest-asyncio with shared test factories and mocking for LLM/embedding providers
- **Multi-language codebase support** - Processes Python, TypeScript/TSX, JavaScript, Go, Rust, Java, C, C++, Objective-C, Swift, Ruby, PHP, Kotlin, and C# codebases

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, nh3, ollama, openai, pandas, psutil, pydantic, pyyaml
  - Plus 19 more...

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