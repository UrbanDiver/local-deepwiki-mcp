# CLAUDE.md - Project Context for Claude Code

## Project Overview

**Local DeepWiki MCP Server** - A local, privacy-focused MCP server that generates DeepWiki-style documentation for private repositories with RAG-based Q&A capabilities.

## Current Status: ✅ Complete & Working

The project is fully implemented and tested. All 29 tests pass.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (Python/FastMCP)                 │
├─────────────────────────────────────────────────────────────────┤
│  Tools:                                                         │
│  - index_repository    - Generate wiki + embeddings             │
│  - ask_question        - RAG Q&A about codebase                 │
│  - read_wiki_structure - Get wiki table of contents             │
│  - read_wiki_page      - Read specific wiki page                │
│  - search_code         - Semantic code search                   │
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
| `src/local_deepwiki/server.py` | MCP server entry point with 5 tools |
| `src/local_deepwiki/core/parser.py` | Tree-sitter multi-language code parser |
| `src/local_deepwiki/core/chunker.py` | AST-based code chunking |
| `src/local_deepwiki/core/vectorstore.py` | LanceDB vector storage |
| `src/local_deepwiki/core/indexer.py` | Indexing orchestration (incremental/full) |
| `src/local_deepwiki/generators/wiki.py` | LLM-powered wiki generation |
| `src/local_deepwiki/providers/` | LLM and embedding provider abstractions |
| `src/local_deepwiki/config.py` | Configuration management |
| `src/local_deepwiki/models.py` | Pydantic data models |
| `src/local_deepwiki/web/app.py` | Flask web UI for browsing wiki |

## Tech Stack

- **Python 3.11+** with FastMCP
- **Tree-sitter** - Multi-language parsing (Python, TS/JS, Go, Rust, Java, C/C++)
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
- **LLM**: Ollama (llama3.2) - can switch to anthropic/openai
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
3. **Language support** - Currently supports: Python, TypeScript, JavaScript, Go, Rust, Java, C, C++

## Future Improvements

- [x] Web UI for browsing generated wiki
- [ ] Watch mode for auto-reindexing on file changes
- [ ] Support for more languages (Ruby, PHP, Kotlin, Swift)
- [ ] Better diagram generation
- [ ] Export to other formats (HTML, PDF)

## Tested On

This repo itself was used as a test case:
- 26 Python files indexed
- 159 code chunks extracted
- Wiki generated with 6 pages
- RAG Q&A working with Ollama
