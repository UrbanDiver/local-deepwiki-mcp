# CLAUDE.md - Project Context for Claude Code

## Project Overview

**Local DeepWiki MCP Server** - A local, privacy-focused MCP server that generates DeepWiki-style documentation for private repositories with RAG-based Q&A capabilities.

## Current Status: ✅ Complete & Working

The project is fully implemented and tested. All 564 tests pass.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (Python/FastMCP)                 │
├─────────────────────────────────────────────────────────────────┤
│  Tools:                                                         │
│  - index_repository    - Generate wiki + embeddings             │
│  - ask_question        - RAG Q&A about codebase                 │
│  - deep_research       - Multi-step reasoning for complex Q&A   │
│  - read_wiki_structure - Get wiki table of contents             │
│  - read_wiki_page      - Read specific wiki page                │
│  - search_code         - Semantic code search                   │
│  - export_wiki_html    - Export wiki to static HTML             │
│  - export_wiki_pdf     - Export wiki to PDF format              │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Tree-sitter    │  │     LanceDB      │  │   LLM Provider   │
│  (Code Parsing)  │  │  (Vector Store)  │  │ (Doc Generation) │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `src/local_deepwiki/server.py` | MCP server entry point with 8 tools |
| `src/local_deepwiki/core/parser.py` | Tree-sitter multi-language code parser |
| `src/local_deepwiki/core/chunker.py` | AST-based code chunking |
| `src/local_deepwiki/core/vectorstore.py` | LanceDB vector storage |
| `src/local_deepwiki/core/indexer.py` | Indexing orchestration (incremental/full) |
| `src/local_deepwiki/core/deep_research.py` | Multi-step reasoning pipeline for complex Q&A |
| `src/local_deepwiki/generators/wiki.py` | LLM-powered wiki generation |
| `src/local_deepwiki/generators/diagrams.py` | Enhanced Mermaid diagram generation |
| `src/local_deepwiki/generators/callgraph.py` | Call graph analysis and visualization |
| `src/local_deepwiki/providers/` | LLM and embedding provider abstractions |
| `src/local_deepwiki/config.py` | Configuration management |
| `src/local_deepwiki/models.py` | Pydantic data models |
| `src/local_deepwiki/web/app.py` | Flask web UI for browsing wiki |
| `src/local_deepwiki/watcher.py` | File watcher for auto-reindexing |
| `src/local_deepwiki/export/html.py` | Static HTML export |
| `src/local_deepwiki/export/pdf.py` | PDF export with WeasyPrint |

## Tech Stack

- **Python 3.11+** with FastMCP
- **Tree-sitter** - Multi-language parsing (Python, TS/JS, Go, Rust, Java, C/C++, Swift, Ruby, PHP, Kotlin, C#)
- **LanceDB** - Embedded vector database
- **sentence-transformers** - Local embeddings
- **Ollama/Anthropic/OpenAI** - LLM providers (configurable)
- **Flask** - Web UI for browsing generated wiki

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv sync --extra dev && uv run pytest tests/ -v

# Run the MCP server directly
uv run local-deepwiki

# Serve the wiki with web UI
uv run deepwiki-serve .deepwiki --port 8080

# Watch mode - auto-reindex on file changes
uv run deepwiki-watch /path/to/repo

# Export wiki to static HTML
uv run deepwiki-export .deepwiki --output ./html-export

# Export wiki to PDF (requires pango system dependency)
uv run deepwiki-export-pdf .deepwiki -o documentation.pdf

# Export each page as separate PDF
uv run deepwiki-export-pdf .deepwiki --separate -o ./pdfs/

# For mermaid diagrams in PDF, install mermaid-cli (optional)
npm install -g @mermaid-js/mermaid-cli
```

## MCP Server Configuration

Already added to `~/.claude.json`:
```json
{
  "mcpServers": {
    "local-deepwiki": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/Users/brian/Projects/local-deepwiki-mcp", "local-deepwiki"],
      "env": {}
    }
  }
}
```

## Configuration

Config file location: `~/.config/local-deepwiki/config.yaml`

Default providers:
- **LLM**: Ollama (qwen3-coder:30b) - can switch to anthropic/openai
- **Embeddings**: Local (all-MiniLM-L6-v2) - can switch to openai

## Testing the Server

```python
# Quick test script
import asyncio
from pathlib import Path
from local_deepwiki.core.indexer import RepositoryIndexer

async def test():
    repo = Path("/path/to/repo")
    indexer = RepositoryIndexer(repo)
    status = await indexer.index(full_rebuild=True)
    print(f"Indexed {status.total_files} files, {status.total_chunks} chunks")

    results = await indexer.search("your query", limit=5)
    for r in results:
        print(f"{r['file_path']}: {r['name']}")

asyncio.run(test())
```

## Known Limitations

1. **Wiki quality depends on LLM** - Local Ollama models produce decent but sometimes hallucinated content. Use Anthropic/OpenAI for better quality.
2. **Large repos** - Very large repositories may take time to index initially.
3. **Language support** - Currently supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, Swift, Ruby, PHP, Kotlin, C#

## Future Improvements

- [x] Web UI for browsing generated wiki
- [x] File-level documentation generation
- [x] Watch mode for auto-reindexing on file changes
- [x] Swift language support
- [x] Export to HTML (static site)
- [x] Enhanced diagram generation (class diagrams with attributes/types, circular dependency detection, sequence diagrams, module overview)
- [x] Ruby language support
- [x] PHP language support
- [x] Kotlin language support
- [x] C# language support
- [x] Export to PDF (WeasyPrint)
- [x] Deep Research mode (multi-step reasoning for complex architectural questions)

## Wiki Structure

Generated wiki includes:
- **Overview** (`index.md`) - Project summary and quick start
- **Architecture** (`architecture.md`) - System design with mermaid diagrams
- **Dependencies** (`dependencies.md`) - External and internal dependencies
- **Modules** (`modules/`) - Documentation per top-level directory
- **Files** (`files/`) - Individual file documentation (up to 20 files)

## Tested On

This repo itself was used as a test case:
- 61 Python files indexed
- 733 code chunks extracted
- 27 wiki pages generated (including file-level docs)
- RAG Q&A working with Ollama (qwen3-coder:30b)
