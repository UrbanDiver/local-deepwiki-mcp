# Local DeepWiki MCP Server

A local, privacy-focused MCP server that generates DeepWiki-style documentation for private repositories with RAG-based Q&A capabilities.

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

Run the init wizard to generate a config file automatically:

```bash
deepwiki init                    # Interactive wizard
deepwiki init --non-interactive  # Auto-detect defaults (CI/CD)
```

Or create one manually at `~/.config/local-deepwiki/config.yaml`:

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
    model: "qwen3-coder:30b"
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

## MCP Tools (40 tools)

The server exposes **40 MCP tools** across 6 categories. Below are the most commonly used tools with examples, followed by the full tool reference.

### Core Tools

#### `index_repository`

Index a repository and generate wiki documentation.

```json
{
  "repo_path": "/path/to/repo",
  "full_rebuild": false,
  "llm_provider": "ollama",
  "embedding_provider": "local"
}
```

#### `ask_question`

Ask a question about the codebase using RAG.

```json
{
  "repo_path": "/path/to/repo",
  "question": "How does the authentication system work?",
  "max_context": 5
}
```

#### `deep_research`

Multi-step reasoning for complex architectural questions. Performs query decomposition, parallel retrieval, gap analysis, and comprehensive synthesis.

```json
{
  "repo_path": "/path/to/repo",
  "question": "How does the authentication system interact with the database layer?",
  "max_chunks": 30
}
```

| Tool | Description |
|------|-------------|
| `index_repository` | Index a repository and generate wiki documentation |
| `ask_question` | RAG-based Q&A about the codebase |
| `deep_research` | Multi-step reasoning with query decomposition and synthesis |
| `read_wiki_structure` | Get the wiki table of contents |
| `read_wiki_page` | Read a specific wiki page |
| `search_code` | Semantic search across the codebase |
| `export_wiki_html` | Export wiki to a static HTML site |
| `export_wiki_pdf` | Export wiki to PDF with mermaid diagram rendering |

### Generator Tools (12)

| Tool | Description |
|------|-------------|
| `get_diagrams` | Generate Mermaid diagrams (class, dependency, module, sequence) |
| `get_call_graph` | Function call graph analysis |
| `get_glossary` | Searchable code entity glossary |
| `get_inheritance` | Class hierarchy tree |
| `get_coverage` | Documentation coverage analysis |
| `get_changelog` | Git-based changelog generation |
| `get_api_docs` | Parameter and return type extraction |
| `get_test_examples` | Extract test examples for entities |
| `detect_stale_docs` | Detect outdated wiki pages |
| `detect_secrets` | Scan for hardcoded credentials |
| `get_index_status` | Repository index status and health |
| `list_indexed_repos` | List all indexed repositories |

### Analysis & Search Tools (10)

| Tool | Description |
|------|-------------|
| `search_wiki` | Full-text search across wiki pages and code entities |
| `fuzzy_search` | Levenshtein-based name matching ("Did you mean?") |
| `get_file_context` | Imports, callers, and related files for a source file |
| `explain_entity` | Composite: glossary + call graph + inheritance + tests + API docs |
| `impact_analysis` | Blast radius analysis with reverse call graph and risk level |
| `get_complexity_metrics` | Cyclomatic complexity and nesting depth via tree-sitter AST |
| `analyze_diff` | Map git diff to affected wiki pages and entities |
| `ask_about_diff` | RAG-based Q&A about code changes |
| `get_project_manifest` | Parsed metadata from pyproject.toml, package.json, etc. |
| `get_wiki_stats` | Wiki health dashboard: index, pages, coverage, status |

### Codemap Tools (2)

| Tool | Description |
|------|-------------|
| `generate_codemap` | Cross-file execution-flow maps with Mermaid diagrams and LLM narrative |
| `suggest_codemap_topics` | Discover interesting entry points from call graph hubs |

### Research & Progress Tools (4)

| Tool | Description |
|------|-------------|
| `list_research_checkpoints` | List saved deep research checkpoints |
| `resume_research` | Resume a previously checkpointed research session |
| `cancel_research` | Cancel an in-progress research operation |
| `get_operation_progress` | Check progress of long-running operations |

### Agentic Tools (4)

| Tool | Description |
|------|-------------|
| `suggest_next_actions` | Context-aware suggestions for next tools to use based on recent actions |
| `run_workflow` | Run predefined multi-step workflows (e.g., full analysis, quick review) |
| `batch_explain_entities` | Batch version of `explain_entity` for multiple entities at once |
| `query_codebase` | Agentic RAG: grades chunk relevance, rewrites queries for better results |

## CLI Commands

All commands are subcommands of the unified `deepwiki` CLI. Legacy entry points (`deepwiki-serve`, `deepwiki-export`, etc.) still work for backwards compatibility.

| Command | Description |
|---------|-------------|
| `deepwiki init` | Interactive setup wizard for configuration |
| `deepwiki status` | Show index health, freshness, and wiki coverage |
| `deepwiki update` | Index repo and regenerate wiki (incremental) |
| `deepwiki mcp` | Start the MCP server (for IDE integration) |
| `deepwiki serve` | Serve wiki with web UI |
| `deepwiki watch` | Watch mode - auto-reindex on file changes |
| `deepwiki export` | Export wiki to static HTML |
| `deepwiki export-pdf` | Export wiki to PDF |
| `deepwiki config` | Configuration management (validate, show, health-check, profile) |
| `deepwiki search` | Interactive fuzzy code search |
| `deepwiki cache` | Cache management (stats, clear, cleanup) |

```bash
# Setup
deepwiki init                                   # Interactive wizard
deepwiki init --non-interactive                  # Auto-detect defaults (CI/CD)
deepwiki init --non-interactive --force          # Overwrite existing config

# Indexing & status
deepwiki update                                  # Index repo and regenerate wiki
deepwiki update --full-rebuild                   # Force full rebuild
deepwiki update --dry-run                        # Preview what would change
deepwiki status                                  # Show index health dashboard
deepwiki status --json                           # Machine-readable output
deepwiki status --verbose                        # Detailed file-level info

# MCP server
deepwiki mcp                                     # Start MCP server (stdio)

# Web UI & export
deepwiki serve .deepwiki --port 8080             # Browse wiki in browser
deepwiki export .deepwiki --output ./html-export # Export to static HTML
deepwiki export-pdf .deepwiki -o docs.pdf        # Export to single PDF
deepwiki export-pdf .deepwiki --separate -o dir/ # Export each page as PDF

# Configuration
deepwiki config show                             # Show effective configuration
deepwiki config show --raw                       # Show raw YAML
deepwiki config validate                         # Check config for errors
deepwiki config health-check                     # Verify provider connectivity
deepwiki config profile list                     # List saved config profiles
deepwiki config profile save dev                 # Save current config as profile
deepwiki config profile use prod                 # Switch to a profile

# Utilities
deepwiki search                                  # Interactive fuzzy code search
deepwiki watch /path/to/repo                     # Auto-reindex on file changes
deepwiki cache stats                             # Show cache hit rates and sizes
deepwiki cache clear --llm --embedding           # Clear caches
deepwiki cache cleanup                           # Remove expired entries
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
2. Try a different port: `deepwiki serve .deepwiki --port 8081`
3. Ensure `.deepwiki` directory exists and contains generated wiki

## Example Configurations

The `examples/` directory contains sample configuration files:

- `config-local.yaml` - Fully local setup with Ollama and sentence-transformers
- `config-cloud.yaml` - Cloud-based setup using Anthropic/OpenAI
- `config-hybrid.yaml` - Local embeddings with cloud LLM
- `roles.yaml` - RBAC role configuration example

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
