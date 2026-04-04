# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP server enables private, local documentation generation and management for code repositories. It supports agentic workflows, RAG-based search, and multi-provider LLM integration to create and maintain up-to-date wiki content. The system is designed for both local and hybrid deployment models with support for various programming languages.

## Key Features

- **Multi-Provider LLM Support**: Integrates with Claude, Ollama, and OpenAI through a unified provider abstraction layer
- **AST-Aware Code Chunking**: Splits code into meaningful chunks at function and class boundaries using tree-sitter for better context retention
- **Agentic RAG Workflows**: Supports automated documentation generation and updates through agentic workflows and Retrieval-Augmented Generation
- **Configurable Deployment Models**: Offers local, cloud, and hybrid deployment configurations via YAML-based configuration files
- **[Language](files/src/local_deepwiki/models/foundation.md)-Agnostic Processing**: Supports documentation generation for Python, TypeScript/TSX, JavaScript, Go, Rust, Java, and 15+ other programming languages

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, LanceDB, markdown, mcp, nh3, ollama, openai, pandas, psutil, pydantic, pyyaml
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