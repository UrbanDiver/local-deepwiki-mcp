# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki-MCP is a private documentation solution that enables local development of AI-powered code assistants using the MCP (Model Control Protocol). It provides tools for generating, searching, and serving repository documentation with support for multiple AI providers including OpenAI, Anthropic, and Ollama. The system supports both interactive search and automated documentation generation workflows.

## Key Features

- **Multi-Provider AI Support**: Integrates with OpenAI, Anthropic, and Ollama APIs for flexible AI assistant deployment
- **[Interactive Search](files/src/local_deepwiki/cli/interactive_search.md) Interface**: Provides command-line search functionality for exploring repository documentation
- **Documentation Export Capabilities**: Supports exporting documentation in HTML and PDF formats
- **MCP Server Implementation**: Implements Model Control Protocol server for AI assistant communication
- **Repository Watching**: Includes file watching functionality for automatic documentation updates

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, psutil, pydantic, pyyaml, rapidfuzz
  - Plus 18 more...

## Directory Structure

```
local-deepwiki-mcp/
├── agents/
│   ├── architect.yaml
│   ├── coder.yaml
│   ├── reviewer.yaml
│   ├── security-architect.yaml
│   └── tester.yaml
├── coverage_html/
│   ├── class_index.html
│   ├── coverage_html_cb_dd2e7eb5.js
│   ├── favicon_32_cb_c827f16f.png
│   ├── function_index.html
│   ├── index.html
│   ├── keybd_closed_cb_900cfef5.png
│   ├── status.json
│   ├── style_cb_9ff733b0.css
│   └── z_dc20ba85d2cbeecd_openai_py.html
├── coverage_openai_embeddings/
│   ├── class_index.html
│   ├── coverage_html_cb_dd2e7eb5.js
│   ├── favicon_32_cb_c827f16f.png
│   ├── function_index.html
│   ├── index.html
│   ├── keybd_closed_cb_900cfef5.png
│   ├── status.json
│   ...
...
```

## Quick Start

- `deepwiki-config` → `local_deepwiki.cli.config_cli:main`
- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-search` → `local_deepwiki.cli.interactive_search:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`