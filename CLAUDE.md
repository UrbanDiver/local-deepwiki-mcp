# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Local DeepWiki MCP Server** - A local, privacy-focused MCP server that generates DeepWiki-style documentation for private repositories with RAG-based Q&A capabilities.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_parser.py -v

# Run a specific test
uv run pytest tests/test_parser.py::test_function_name -v

# Run tests with dev dependencies (if not already synced)
uv sync --extra dev && uv run pytest tests/ -v

# Linting and formatting
uv run black src/ tests/
uv run isort src/ tests/
uv run mypy src/

# Run the MCP server
uv run local-deepwiki

# Serve the wiki with web UI
uv run deepwiki-serve .deepwiki --port 8080

# Watch mode - auto-reindex on file changes
uv run deepwiki-watch /path/to/repo

# Export wiki to static HTML
uv run deepwiki-export .deepwiki --output ./html-export

# Export wiki to PDF
uv run deepwiki-export-pdf .deepwiki -o documentation.pdf
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (Python/FastMCP)                 │
├─────────────────────────────────────────────────────────────────┤
│  Tools: index_repository, ask_question, deep_research,         │
│         read_wiki_structure, read_wiki_page, search_code,       │
│         export_wiki_html, export_wiki_pdf                       │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Tree-sitter    │  │     LanceDB      │  │   LLM Provider   │
│  (Code Parsing)  │  │  (Vector Store)  │  │ (Doc Generation) │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| MCP Server | `server.py` | Entry point, tool definitions delegated to `handlers.py` |
| Parser | `core/parser.py` | Tree-sitter multi-language AST parsing |
| Chunker | `core/chunker.py` | AST-based semantic code chunking |
| VectorStore | `core/vectorstore.py` | LanceDB vector storage and retrieval |
| Indexer | `core/indexer.py` | Orchestrates parsing → chunking → embedding → wiki generation |
| Deep Research | `core/deep_research.py` | Multi-step reasoning pipeline with query decomposition |
| Wiki Generator | `generators/wiki.py` | LLM-powered markdown wiki generation |
| Diagrams | `generators/diagrams.py` | Mermaid diagram generation (class, sequence, module) |
| Call Graph | `generators/callgraph.py` | Function call graph analysis |

### Provider Abstraction

The `providers/` directory contains pluggable backends:
- **LLM**: `ollama.py`, `anthropic.py`, `openai.py` - All implement `LLMProvider` base class
- **Embeddings**: `local.py` (sentence-transformers), `openai.py` - All implement `EmbeddingProvider`

Provider selection is config-driven (`~/.config/local-deepwiki/config.yaml`) or per-request.

### Data Flow

1. **Indexing**: Files → Tree-sitter AST → Semantic chunks → Embeddings → LanceDB + LLM → Wiki markdown
2. **Query (ask_question)**: Question → Embedding → Vector search → Top-k chunks → LLM synthesis
3. **Deep Research**: Question → Sub-question decomposition → Parallel retrieval → Gap analysis → Synthesis

## Key Design Decisions

- **Async throughout**: All core operations use asyncio for concurrent LLM/embedding calls
- **Incremental indexing**: File hashes tracked in manifest to only re-process changed files
- **AST-aware chunking**: Code is split at function/class boundaries, not arbitrary token limits
- **Config hierarchy**: CLI args → env vars → config file → defaults

## Testing Notes

- Tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`)
- Most tests mock LLM/embedding providers to avoid external calls
- Test files follow pattern `test_<module>.py`

## Supported Languages

Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, Swift, Ruby, PHP, Kotlin, C#

All use tree-sitter grammars from `tree-sitter-<language>` packages.
