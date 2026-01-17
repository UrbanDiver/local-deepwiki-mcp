# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki-style MCP server is a documentation generation tool that creates comprehensive wikis for private code repositories. It provides both command-line utilities and a web interface for generating, serving, and monitoring documentation, with support for PDF export and real-time file watching capabilities.

## Key Features

• **MCP Server Integration** - Runs as an MCP (Model Context Protocol) server with stdio communication, as shown in the [main](files/src/local_deepwiki/export/pdf.md) server entry point
• **Multiple Export Formats** - Supports both HTML and PDF export through dedicated command-line tools (`deepwiki-export` and `deepwiki-export-pdf`)
• **Web Interface** - Includes a web application server (`deepwiki-serve`) for interactive documentation browsing
• **File System Monitoring** - Features a watcher service (`deepwiki-watch`) that can monitor repository changes and trigger documentation updates
• **Multiple [LLM Provider](files/src/local_deepwiki/providers/base.md) Support** - Integrates with various LLM providers including Ollama, OpenAI, and Anthropic for documentation generation, with configurable embedding and research presets

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, pydantic, pyyaml, rich, sentence-transformers
  - Plus 16 more...

## Directory Structure

```
local-deepwiki-mcp/
├── src/local_deepwiki/
│   ├── core/                    # Core processing modules
│   │   ├── chunker.py           # AST-based code chunking
│   │   ├── deep_research.py     # Multi-step reasoning pipeline
│   │   ├── git_utils.py         # Git integration utilities
│   │   ├── indexer.py           # Repository indexing orchestration
│   │   ├── llm_cache.py         # LLM response caching
│   │   ├── parser.py            # Tree-sitter code parsing
│   │   └── vectorstore.py       # LanceDB vector storage
│   ├── generators/              # Wiki content generators
│   │   ├── api_docs.py          # API documentation extraction
│   │   ├── callgraph.py         # Function call graph analysis
│   │   ├── context_builder.py   # Rich LLM context building
│   │   ├── crosslinks.py        # Cross-reference linking
│   │   ├── diagrams.py          # Mermaid diagram generation
│   │   ├── glossary.py          # Term glossary generation
│   │   ├── inheritance.py       # Class hierarchy analysis
│   │   ├── wiki.py              # Main wiki generator
│   │   └── ...                  # Additional generators
│   ├── providers/               # Pluggable backends
│   │   ├── llm/                 # LLM providers
│   │   │   ├── anthropic.py     # Anthropic Claude
│   │   │   ├── ollama.py        # Local Ollama
│   │   │   └── openai.py        # OpenAI GPT
│   │   └── embeddings/          # Embedding providers
│   │       ├── local.py         # Sentence-transformers
│   │       └── openai.py        # OpenAI embeddings
│   ├── export/                  # Export functionality
│   │   ├── html.py              # Static HTML export
│   │   └── pdf.py               # PDF export
│   ├── web/                     # Web UI
│   │   └── app.py               # Flask web server
│   ├── config.py                # Configuration management
│   ├── handlers.py              # MCP tool handlers
│   ├── models.py                # Pydantic data models
│   ├── server.py                # MCP server entry point
│   └── watcher.py               # File change watcher
├── tests/                       # Test suite (50+ test files)
├── docs/                        # Documentation
└── pyproject.toml               # Project configuration
```

## Quick Start

- `deepwiki-export` → `local_deepwiki.export.html:main`
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main`
- `deepwiki-serve` → `local_deepwiki.web.app:main`
- `deepwiki-watch` → `local_deepwiki.watcher:main`
- `local-deepwiki` → `local_deepwiki.server:main`