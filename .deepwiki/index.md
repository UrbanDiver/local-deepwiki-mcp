# Local DeepWiki MCP

A local, privacy-focused MCP server that generates DeepWiki-style documentation for private repositories with RAG-based Q&A capabilities.

## Description

Local DeepWiki MCP automatically generates comprehensive wiki documentation for codebases by parsing source files with tree-sitter, extracting semantic code chunks, generating embeddings for vector search, and using LLMs to create human-readable documentation. All processing happens locally for privacy.

## Key Features

- **Automatic Wiki Generation**: Creates module docs, file docs, architecture diagrams, and dependency graphs
- **RAG-based Q&A**: Ask natural language questions about your codebase with semantic search
- **Multi-Language Support**: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, Swift
- **Incremental Updates**: Only regenerates documentation for changed files
- **Cross-linking**: Automatic linking between related classes, functions, and modules
- **Web UI**: Flask-based interface for browsing generated documentation
- **Local & Private**: All processing runs locally - no code leaves your machine

## Technology Stack

- **Python 3.11+** with FastMCP for MCP server implementation
- **Tree-sitter**: Multi-language AST parsing for accurate code understanding
- **LanceDB**: Embedded vector database for semantic search
- **sentence-transformers**: Local embeddings with all-MiniLM-L6-v2
- **Ollama/Anthropic/OpenAI**: Configurable LLM providers for documentation generation
- **Flask**: Web UI for browsing generated wiki
- **Pydantic**: Data validation and models

## Directory Structure

```
local-deepwiki-mcp/
├── src/local_deepwiki/
│   ├── core/              # Core indexing components
│   │   ├── parser.py      # Tree-sitter multi-language parser
│   │   ├── chunker.py     # AST-based code chunking
│   │   ├── vectorstore.py # LanceDB vector storage
│   │   └── indexer.py     # Indexing orchestration
│   ├── generators/        # Documentation generators
│   │   ├── wiki.py        # LLM-powered wiki generation
│   │   ├── crosslinks.py  # Cross-reference linking
│   │   └── api_docs.py    # API reference generation
│   ├── providers/         # LLM and embedding providers
│   ├── web/               # Flask web UI
│   ├── server.py          # MCP server entry point
│   ├── config.py          # Configuration management
│   └── models.py          # Pydantic data models
└── tests/                 # Test suite
```

## Quick Start Guide

### Installation

```bash
# Clone and install
git clone https://github.com/your-repo/local-deepwiki-mcp.git
cd local-deepwiki-mcp
uv sync
```

### MCP Tools

The server exposes 5 MCP tools:

- **index_repository**: Parse files, generate embeddings, create wiki documentation
- **ask_question**: RAG Q&A about the codebase
- **read_wiki_structure**: Get wiki table of contents
- **read_wiki_page**: Read specific wiki page
- **search_code**: Semantic code search

### Basic Usage

```python
import asyncio
from pathlib import Path
from local_deepwiki.core.indexer import RepositoryIndexer

async def main():
    repo = Path("/path/to/repo")
    indexer = RepositoryIndexer(repo)

    # Index repository and generate wiki
    status = await indexer.index(full_rebuild=True)
    print(f"Indexed {status.total_files} files, {status.total_chunks} chunks")

    # Search the codebase
    results = await indexer.search("authentication logic", limit=5)
    for r in results:
        print(f"{r['file_path']}: {r['name']}")

asyncio.run(main())
```

### Web UI

```bash
# Serve the generated wiki
uv run deepwiki-serve .deepwiki --port 8080
```

### Configuration

Config file: `~/.config/local-deepwiki/config.yaml`

```yaml
llm:
  provider: ollama  # or anthropic, openai
  ollama:
    model: qwen3-coder:30b
    base_url: http://localhost:11434

embedding:
  provider: local  # or openai
  local:
    model: all-MiniLM-L6-v2
```

## Generated Wiki Structure

- **Overview** (`index.md`) - Project summary and quick start
- **Architecture** (`architecture.md`) - System design with mermaid diagrams
- **Dependencies** (`dependencies.md`) - External and internal dependencies
- **Modules** (`modules/`) - Documentation per top-level directory
- **Files** (`files/`) - Individual file documentation with API references

## See Also

- [System Architecture](architecture.md) - Detailed architecture documentation
- [Dependencies](dependencies.md) - Dependency analysis
- [Source Files](files/index.md) - File-level documentation
