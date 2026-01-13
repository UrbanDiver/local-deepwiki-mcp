# Local DeepWiki MCP Server

A local, privacy-focused MCP server that generates DeepWiki-style documentation for private repositories with RAG-based Q&A capabilities.

**[View PDF Documentation](docs.pdf)**

## Features

- **Multi-language code parsing** using tree-sitter (Python, TypeScript/JavaScript, Go, Rust, Java, C/C++, Swift, Ruby, PHP, Kotlin, C#)
- **AST-based chunking** that respects code structure (functions, classes, methods)
- **Semantic search** using LanceDB vector database
- **LLM-powered wiki generation** with support for Ollama (local), Anthropic, and OpenAI
- **Configurable embeddings** - local (sentence-transformers) or OpenAI
- **Incremental indexing** - only re-process changed files
- **RAG-based Q&A** - ask questions about your codebase
- **Deep Research mode** - multi-step reasoning for complex architectural questions
- **Web UI** - browse generated wiki in your browser
- **Export to HTML** - generate static HTML site for sharing
- **Export to PDF** - generate printable PDF documentation with mermaid diagrams

## Installation

### Using uv (recommended)

```bash
cd local-deepwiki-mcp
uv sync
```

### Using pip

```bash
cd local-deepwiki-mcp
pip install -e .
```

## Configuration

Create a config file at `~/.config/local-deepwiki/config.yaml`:

```yaml
embedding:
  provider: "local"  # or "openai"
  local:
    model: "all-MiniLM-L6-v2"
  openai:
    model: "text-embedding-3-small"

llm:
  provider: "ollama"  # or "anthropic" or "openai"
  ollama:
    model: "llama3.2"
    base_url: "http://localhost:11434"
  anthropic:
    model: "claude-sonnet-4-20250514"
  openai:
    model: "gpt-4o"

parsing:
  languages:
    - python
    - typescript
    - javascript
    - go
    - rust
    - java
    - c
    - cpp
  max_file_size: 1048576
  exclude_patterns:
    - "node_modules/**"
    - "venv/**"
    - ".git/**"

chunking:
  max_chunk_tokens: 512
  overlap_tokens: 50

output:
  wiki_dir: ".deepwiki"
  vector_db_name: "vectors.lance"
```

## Claude Code Integration

Add to your Claude Code MCP config (`~/.claude/claude_code_config.json`):

```json
{
  "mcpServers": {
    "local-deepwiki": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/local-deepwiki-mcp", "local-deepwiki"],
      "env": {
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

## MCP Tools

### `index_repository`

Index a repository and generate wiki documentation.

```json
{
  "repo_path": "/path/to/repo",
  "full_rebuild": false,
  "llm_provider": "ollama",
  "embedding_provider": "local"
}
```

### `ask_question`

Ask a question about the codebase using RAG.

```json
{
  "repo_path": "/path/to/repo",
  "question": "How does the authentication system work?",
  "max_context": 5
}
```

### `deep_research`

Perform deep research on complex architectural questions using multi-step reasoning. Unlike `ask_question` (single retrieval), this performs query decomposition, parallel retrieval, gap analysis, and comprehensive synthesis.

```json
{
  "repo_path": "/path/to/repo",
  "question": "How does the authentication system interact with the database layer?",
  "max_chunks": 30
}
```

Returns a detailed answer with:
- Sub-questions that were investigated
- Source references with file paths and line numbers
- Reasoning trace showing each step's duration
- Comprehensive answer with citations

Best for questions like:
- "How does data flow from API to database?"
- "What would break if we change the auth module?"
- "How are these services coupled?"

### `read_wiki_structure`

Get the wiki table of contents.

```json
{
  "wiki_path": "/path/to/repo/.deepwiki"
}
```

### `read_wiki_page`

Read a specific wiki page.

```json
{
  "wiki_path": "/path/to/repo/.deepwiki",
  "page": "modules/auth.md"
}
```

### `search_code`

Semantic search across the codebase.

```json
{
  "repo_path": "/path/to/repo",
  "query": "user authentication",
  "limit": 10,
  "language": "python"
}
```

### `export_wiki_html`

Export wiki to a static HTML site.

```json
{
  "wiki_path": "/path/to/repo/.deepwiki",
  "output_path": "./html-export"
}
```

### `export_wiki_pdf`

Export wiki to PDF format.

```json
{
  "wiki_path": "/path/to/repo/.deepwiki",
  "output_path": "./documentation.pdf",
  "single_file": true
}
```

## CLI Commands

```bash
# Run the MCP server
uv run local-deepwiki

# Serve the wiki with web UI
uv run deepwiki-serve .deepwiki --port 8080

# Watch mode - auto-reindex on file changes
uv run deepwiki-watch /path/to/repo

# Export wiki to static HTML
uv run deepwiki-export .deepwiki --output ./html-export

# Export wiki to PDF (single file)
uv run deepwiki-export-pdf .deepwiki -o documentation.pdf

# Export each page as separate PDF
uv run deepwiki-export-pdf .deepwiki --separate -o ./pdfs/
```

## Environment Variables

- `ANTHROPIC_API_KEY` - Required for Anthropic LLM provider
- `OPENAI_API_KEY` - Required for OpenAI LLM/embedding providers

## Prerequisites

For local LLM support:
- [Ollama](https://ollama.ai/) installed and running
- A model pulled (e.g., `ollama pull llama3.2`)

For PDF export:
- System libraries: `pango`, `cairo`, `gdk-pixbuf` (WeasyPrint dependencies)
  - macOS: `brew install pango`
  - Ubuntu/Debian: `apt install libpango-1.0-0 libpangocairo-1.0-0`
- Optional for mermaid diagrams: `npm install -g @mermaid-js/mermaid-cli`

## Troubleshooting

### Ollama Connection Errors

If you see "Failed to connect to Ollama":
1. Ensure Ollama is running: `ollama serve`
2. Verify the model is pulled: `ollama list`
3. Check if the default URL works: `curl http://localhost:11434/api/tags`
4. If using a custom port, update `config.yaml` with the correct `base_url`

### PDF Export Fails

**"pango not found" or similar Cairo/Pango errors:**
- macOS: `brew install pango cairo gdk-pixbuf`
- Ubuntu/Debian: `apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0`
- Fedora: `dnf install pango cairo gdk-pixbuf2`

**Mermaid diagrams not rendering in PDF:**
- Install mermaid-cli: `npm install -g @mermaid-js/mermaid-cli`
- Verify with: `mmdc --version`
- Without mermaid-cli, diagrams show as code blocks

### Memory Issues on Large Repositories

For repositories with 100k+ lines of code:
1. Increase batch size limits in config if you have more RAM
2. Use `full_rebuild: false` for incremental updates after initial indexing
3. Consider excluding large generated files via `exclude_patterns` in config

### LLM Quality Issues

If wiki content has hallucinations or low quality:
1. Switch from Ollama to Anthropic or OpenAI for better results
2. Try a larger local model (e.g., `qwen3-coder:30b` instead of `llama3.2`)
3. Ensure source files are properly parsed (check supported languages)

### Web UI Not Loading

1. Check if port 8080 is in use: `lsof -i :8080`
2. Try a different port: `uv run deepwiki-serve .deepwiki --port 8081`
3. Ensure `.deepwiki` directory exists and contains generated wiki

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
pytest

# Run the server directly
uv run local-deepwiki
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (FastMCP)                        │
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

## License

MIT
