# local-deepwiki-mcp


Local DeepWiki-style MCP server for private repository documentation

## Description

Local DeepWiki MCP server that generates comprehensive wiki documentation for private repositories. Parses source code using tree-sitter ASTs, creates semantic embeddings stored in LanceDB, and provides RAG-based Q&A via the Model Context Protocol. Supports multiple LLM providers (Ollama, Anthropic, OpenAI) and export formats including HTML and PDF.

## Key Features

- **MCP Server** - 20 MCP tools for indexing, querying, and exporting repository documentation
- **AST-Aware Code Parsing** - Tree-sitter grammars for 13 languages with semantic chunking at function/class boundaries
- **RAG-Based Q&A** - Vector similarity search over code chunks with LLM-synthesized answers
- **Deep Research** - Multi-step reasoning pipeline with query decomposition, parallel retrieval, and gap analysis
- **Wiki Generation** - LLM-powered markdown wiki with diagrams, glossary, call graphs, and coverage reports
- **Export Capabilities** - Static HTML and PDF export with cross-linked navigation
- **Repository Watching** - File system monitoring for automatic re-indexing on changes
- **AI Provider Flexibility** - Pluggable LLM and embedding providers (Ollama, Anthropic, OpenAI, local sentence-transformers)

## Technology Stack

- **Python >=3.11**
- **Dependencies**: anthropic, flask, lancedb, markdown, mcp, ollama, openai, pandas, psutil, pydantic, pyyaml, rapidfuzz, rich, sentence-transformers, tree-sitter (13 grammars), watchdog, weasyprint

## Directory Structure

```
local-deepwiki-mcp/
├── src/
│   └── local_deepwiki/
│       ├── server.py          # MCP server entry point
│       ├── handlers.py        # Tool handler implementations
│       ├── models.py          # Pydantic data models
│       ├── config.py          # Configuration management
│       ├── validation.py      # Input validation (CWE-400)
│       ├── events.py          # Pub-sub event system
│       ├── watcher.py         # File system watcher
│       ├── core/              # Core engine
│       │   ├── parser.py      # Tree-sitter AST parsing
│       │   ├── chunker.py     # Semantic code chunking
│       │   ├── vectorstore.py # LanceDB vector storage
│       │   ├── indexer.py     # Orchestrates indexing pipeline
│       │   ├── deep_research.py # Multi-step research engine
│       │   ├── fuzzy_search.py  # Fuzzy name matching
│       │   ├── llm_cache.py   # LRU response cache
│       │   ├── rate_limiter.py # Token bucket rate limiter
│       │   ├── secret_detector.py # Credential scanning
│       │   ├── git_utils.py   # Secure git operations
│       │   └── audit.py       # Operation audit logging
│       ├── generators/        # Wiki content generators
│       │   ├── wiki.py        # Main wiki generator
│       │   ├── diagrams.py    # Mermaid diagram generation
│       │   ├── callgraph.py   # Function call graphs
│       │   ├── coverage.py    # Documentation coverage
│       │   ├── glossary.py    # Code entity glossary
│       │   ├── inheritance.py # Class hierarchy trees
│       │   └── ...            # 12 more generators
│       ├── providers/         # Pluggable backends
│       │   ├── llm/           # Ollama, Anthropic, OpenAI
│       │   └── embeddings/    # Local, OpenAI
│       ├── export/            # HTML and PDF export
│       ├── security/          # RBAC access control
│       ├── plugins/           # Plugin registry
│       ├── cli/               # CLI tools
│       └── web/               # Flask web UI
└── tests/                     # 82 test files, 3,956 tests
```

## Quick Start

- `local-deepwiki` → `local_deepwiki.server:main` (MCP server)
- `deepwiki-serve` → `local_deepwiki.web.app:main` (Web UI)
- `deepwiki-watch` → `local_deepwiki.watcher:main` (File watcher)
- `deepwiki-export` → `local_deepwiki.export.html:main` (HTML export)
- `deepwiki-export-pdf` → `local_deepwiki.export.pdf:main` (PDF export)
- `deepwiki-search` → `local_deepwiki.cli.interactive_search:main` (Interactive search)
- `deepwiki-config` → `local_deepwiki.cli.config_cli:main` (Configuration)
