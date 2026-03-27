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

# Initialize configuration (interactive wizard)
uv run deepwiki init

# Initialize with auto-detected defaults (CI/CD friendly)
uv run deepwiki init --non-interactive

# Overwrite existing config in CI/CD
uv run deepwiki init --non-interactive --force

# Run the MCP server
uv run local-deepwiki

# Index repo and regenerate wiki
uv run deepwiki update

# Preview what would change without indexing
uv run deepwiki update --dry-run

# Force full rebuild
uv run deepwiki update --full-rebuild

# Show index health dashboard
uv run deepwiki status
uv run deepwiki status --json --verbose

# Serve the wiki with web UI
uv run deepwiki serve .deepwiki --port 8080

# Watch mode - auto-reindex on file changes
uv run deepwiki watch /path/to/repo

# Export wiki to static HTML
uv run deepwiki export .deepwiki --output ./html-export

# Export wiki to PDF
uv run deepwiki export-pdf .deepwiki -o documentation.pdf

# Interactive code search
uv run deepwiki search

# Configuration management
uv run deepwiki config show
uv run deepwiki config validate
uv run deepwiki config health-check
uv run deepwiki config profile list

# Cache management
uv run deepwiki cache stats
uv run deepwiki cache clear --llm --embedding
uv run deepwiki cache cleanup
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MCP Server (Python/FastMCP)                    │
├─────────────────────────────────────────────────────────────────────┤
│  Core Tools (8):                                                    │
│    index_repository, ask_question, deep_research,                   │
│    read_wiki_structure, read_wiki_page, search_code,                │
│    export_wiki_html, export_wiki_pdf                                │
│                                                                     │
│  Generator Tools (12):                                              │
│    get_diagrams, get_call_graph, get_glossary, get_inheritance,     │
│    get_coverage, get_changelog, get_api_docs, get_test_examples,    │
│    detect_stale_docs, detect_secrets, get_index_status,             │
│    list_indexed_repos                                               │
│                                                                     │
│  Analysis & Search Tools (11):                                      │
│    search_wiki, fuzzy_search, get_file_context, explain_entity,     │
│    impact_analysis, get_complexity_metrics, analyze_diff,           │
│    ask_about_diff, get_project_manifest, get_wiki_stats,            │
│    analyze_architecture                                              │
│                                                                     │
│  Codemap Tools (2):                                                 │
│    generate_codemap, suggest_codemap_topics                         │
│                                                                     │
│  Research & Progress Tools (4):                                     │
│    list_research_checkpoints, cancel_research,                      │
│    resume_research, get_operation_progress                          │
│                                                                     │
│  Agentic Tools (5):                                                 │
│    suggest_next_actions, run_workflow,                               │
│    batch_explain_entities, query_codebase, find_tools               │
│                                                                     │
│  Web Server Tools (2):                                              │
│    serve_wiki, stop_wiki_server                                     │
└─────────────────────────────────────────────────────────────────────┘
           │                    │                    │
           v                    v                    v
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
| Chunker | `core/chunker.py` | AST-based semantic code chunking (delegates to `chunk_extractors`) |
| Chunk Extractors | `core/chunk_extractors.py` | Constants (`FUNCTION_NODE_TYPES`, etc.) and standalone AST extraction functions |
| VectorStore | `core/vectorstore.py` | LanceDB vector storage and retrieval |
| Indexer | `core/indexer.py` | Orchestrates parsing, chunking, embedding, wiki generation |
| Deep Research | `core/deep_research.py` | Multi-step reasoning pipeline with query decomposition |
| Secret Detector | `core/secret_detector.py` | Hardcoded credential scanning |
| LLM Cache | `core/llm_cache.py` | LRU response cache for LLM calls |
| Rate Limiter | `core/rate_limiter.py` | API rate limiting with token bucket |
| Fuzzy Search | `core/fuzzy_search.py` | Fuzzy name matching for search suggestions |
| Index Manager | `core/index_manager.py` | IndexStatus tracking with schema versioning |
| Git Utils | `core/git_utils.py` | Secure git operations, path validation, remote URL functions |
| Git Blame | `core/git_blame.py` | Git blame dataclasses (`BlameInfo`, `EntityBlameInfo`) and blame functions |
| Audit Logger | `core/audit.py` | Operation audit logging |
| Events | `events.py` | Pub-sub event system with lifecycle hooks |
| Validation | `validation.py` | Input validation with resource limits (CWE-400) |
| Handlers: Indexing | `handlers/indexing.py` | Repository indexing handler (`handle_index_repository`) and pipeline |
| Handlers: Agentic Data | `handlers/agentic_data.py` | Tool keywords, workflow presets, and suggestion constants |
| Handlers: Agentic Workflows | `handlers/agentic_workflows.py` | Workflow runner functions (onboarding, security audit, full analysis) |
| Web UI | `web/app.py` | Flask-based wiki browser with chat, research, and codemap |
| Web Chat | `web/routes_chat.py` | RAG Q&A chat blueprint with SSE streaming |
| Web Research | `web/routes_research.py` | Deep research blueprint with progress tracking |
| Web Codemap | `web/routes_codemap.py` | Interactive codemap explorer blueprint |

### Generators

Organized into 4 subpackages plus root utilities:

#### `generators/wiki/` — Wiki Documentation

| Component | File | Purpose |
|-----------|------|---------|
| Generator | `wiki/generator.py` | LLM-powered markdown wiki generation (`WikiGenerator`, `generate_wiki`) |
| Files | `wiki/files.py` | File-level documentation generation |
| Modules | `wiki/modules.py` | Module-level documentation generation |
| Pages | `wiki/pages.py` | Specific documentation page generators (overview, architecture, etc.) |
| Phases | `wiki/phases.py` | Generation phase orchestration (summary, auxiliary, changelog) |
| Plugin Runner | `wiki/plugin_runner.py` | Executes registered wiki generator plugins |
| Postprocessing | `wiki/postprocessing.py` | Post-generation content cleanup and enrichment |
| Source Formatter | `wiki/source_formatter.py` | Source code formatting for wiki pages |
| Status | `wiki/status.py` | Incremental update status management |
| Utils | `wiki/utils.py` | Shared wiki generation utilities |
| Codemap Pages | `wiki/codemap_pages.py` | Codemap-specific wiki page generation |

#### `generators/codemap/` — Codemap Generation

| Component | File | Purpose |
|-----------|------|---------|
| Generator | `codemap/generator.py` | Cross-file execution-flow maps with Mermaid diagrams and LLM narrative |
| Models | `codemap/models.py` | Data structures and constants (`CodemapNode`, `CodemapEdge`, `CodemapResult`) |
| Graph | `codemap/graph.py` | BFS traversal, entry point discovery, cross-file graph building |
| Viz | `codemap/viz.py` | Mermaid diagram generation from codemap graphs |
| Cache | `codemap/cache.py` | Persistent caching layer for codemap results |

#### `generators/analysis/` — Code Analysis

| Component | File | Purpose |
|-----------|------|---------|
| API Docs | `analysis/api_docs.py` | Parameter and return type extraction |
| Call Graph | `analysis/callgraph.py` | Function call graph analysis |
| Complexity | `analysis/complexity.py` | Cyclomatic complexity and nesting depth via tree-sitter AST |
| Coverage | `analysis/coverage.py` | Documentation coverage analysis |
| Dependency Graph | `analysis/dependency_graph.py` | `DependencyGraphGenerator` class and page generation |
| Dependency Graph Data | `analysis/dependency_graph_data.py` | Import patterns, dataclasses (`DependencyNode/Edge/Graph`), utility functions |
| Glossary | `analysis/glossary.py` | Searchable code entity glossary |
| Inheritance | `analysis/inheritance.py` | Class hierarchy tree generation |
| Stale Detection | `analysis/stale_detection.py` | Detects outdated wiki pages |

#### `generators/examples/` — Example Extraction

| Component | File | Purpose |
|-----------|------|---------|
| Orchestrator | `examples/orchestrator.py` | Test-file-based example extraction and orchestration |
| Discovery | `examples/discovery.py` | Test file discovery and function detection |
| Docstring | `examples/docstring.py` | Docstring example parsing (doctest and Google-style) |
| Extractor | `examples/extractor.py` | `CodeExampleExtractor` class and markdown formatting |
| Plugin | `examples/plugin.py` | Wiki plugin aggregating code examples from tests |

#### `generators/diagrams/` — Diagram Generation (subpackage)

Mermaid diagram generation (class, dependency, module, sequence, language_pie).

#### `generators/` Root Utilities

| Component | File | Purpose |
|-----------|------|---------|
| Changelog | `changelog.py` | Git-based changelog generation |
| Context Builder | `context_builder.py` | Rich LLM context from imports, callers, related files |
| Crosslinks | `crosslinks.py` | Cross-reference linking between wiki pages |
| Dir Tree | `dir_tree.py` | Directory tree generation with gitignore support |
| Lazy Generator | `lazy_generator.py` | On-demand wiki page generation for missing pages |
| LLMs.txt | `llms_txt.py` | LLMs.txt format output for AI consumption |
| Manifest | `manifest.py` | Manifest dataclasses, cache, and `parse_manifest` orchestrator |
| Manifest Parsers | `manifest_parsers.py` | Language-specific parsers (pyproject.toml, package.json, Cargo.toml, etc.) |
| Prefetch | `prefetch.py` | Prefetches vector search results for wiki generation |
| Progress Tracker | `progress_tracker.py` | Live progress tracking for wiki generation |
| Search Index | `search.py` | JSON search index for client-side full-text search |
| See Also | `see_also.py` | Related page suggestions |
| Source Refs | `source_refs.py` | Source code reference links |
| TOC | `toc.py` | Table of contents generation with hierarchical numbering |

### CLI

| Component | File | Purpose |
|-----------|------|---------|
| Interactive Search | `cli/interactive_search.py` | `InteractiveSearch` TUI class, `run_search`, `main` |
| Search Models | `cli/search_models.py` | `LANGUAGE_LEXERS`, `SearchFilters`, `SearchState` dataclasses |

### Export

| Component | File | Purpose |
|-----------|------|---------|
| PDF (Streaming) | `export/pdf.py` | `StreamingPdfExporter`, `render_markdown_for_pdf`, `extract_title` |
| PDF (Sync) | `export/pdf_sync.py` | `PdfExporter` (legacy sync exporter), `export_to_pdf`, CLI `main` |

### Codemap Tools

| Tool | Purpose | Requires Indexing? |
|------|---------|-------------------|
| `generate_codemap` | Windsurf-style execution-flow map: Mermaid diagram + narrative trace for "How does X work?" queries | Yes |
| `suggest_codemap_topics` | Discover interesting entry points from call graph hubs, core modules, and entry patterns | Yes |

Key features:
- Cross-file BFS traversal resolves calls across file boundaries via vector search
- Deterministic Mermaid diagrams with subgraphs per file, color-coded nodes (entry/cross-file/leaf)
- LLM narrative with numbered step-by-step trace and `file:line` references
- Three focus modes: `execution_flow` (calls), `data_flow` (transformations), `dependency_chain` (imports)
- Configurable depth (1-10) and node limit (5-60)

Key workflow chains:
- `suggest_codemap_topics` -> `generate_codemap` (discover flows, then trace them)
- `generate_codemap` -> `explain_entity` (trace a flow, then deep-dive on a specific entity)
- `generate_codemap` -> `impact_analysis` (trace a flow, then assess change blast radius)

### Analysis & Search Tools

| Tool | Purpose | Requires Indexing? |
|------|---------|-------------------|
| `search_wiki` | Full-text search across wiki pages and code entities | Yes |
| `fuzzy_search` | Levenshtein-based name matching ("Did you mean?") | Yes |
| `get_file_context` | Imports, callers, related files for a source file | Yes |
| `explain_entity` | Composite: glossary + call graph + inheritance + tests + API docs | Yes |
| `impact_analysis` | Blast radius analysis with reverse call graph and risk level | Yes |
| `get_complexity_metrics` | Cyclomatic complexity, nesting depth via tree-sitter AST | No |
| `analyze_diff` | Map git diff to affected wiki pages and entities | No (degrades gracefully) |
| `ask_about_diff` | RAG-based Q&A about code changes (git diff + vector search + LLM) | No (degrades gracefully) |
| `get_project_manifest` | Parsed metadata from pyproject.toml, package.json, etc. | No |
| `get_wiki_stats` | Wiki health dashboard: index, pages, coverage, status | Yes |

Key workflow chains:
- `fuzzy_search` -> `explain_entity` (find entity, then get full explanation)
- `analyze_diff` -> `impact_analysis` (see what changed, then assess blast radius)
- `analyze_diff` -> `ask_about_diff` (structural view, then natural-language Q&A)
- `search_wiki` -> `get_file_context` (find a file, then explore its role)

### Provider Abstraction

The `providers/` directory contains pluggable backends:
- **LLM**: `ollama.py`, `anthropic.py`, `openai.py` - All implement `LLMProvider` base class
- **Embeddings**: `local.py` (sentence-transformers), `openai.py` - All implement `EmbeddingProvider`

- **Caching**: `llm/cached.py` - Transparent caching wrapper for any LLM provider
- **Credentials**: `credentials.py` - Secure API key management from env vars/config
- **Embedding Cache**: `embeddings/cache.py` - SQLite-based embedding cache with TTL

Provider selection is config-driven (`~/.config/local-deepwiki/config.yaml`) or per-request.

### Data Flow

1. **Indexing**: Files -> Tree-sitter AST -> Semantic chunks -> Embeddings -> LanceDB + LLM -> Wiki markdown
2. **Query (ask_question)**: Question -> Embedding -> Vector search -> Top-k chunks -> LLM synthesis
3. **Deep Research**: Question -> Sub-question decomposition -> Parallel retrieval -> Gap analysis -> Synthesis (supports checkpointing/resume via `list_research_checkpoints`, `resume_research`, `cancel_research`)
4. **Codemap**: Query -> Vector search entry points -> Cross-file BFS call graph -> Mermaid diagram + LLM narrative

## Security

- **RBAC**: Role-based access control (`security/access_control.py`) with admin, editor, viewer, and guest roles. Supports enforced, permissive, and disabled modes.
- **Repository Access Control**: Allowlist/denylist for repository paths (`security/repository_access.py`).
- **Role Configuration**: YAML-driven role assignment with pattern matching (`security/role_config.py`).
- **Secret Detection**: Scans for hardcoded credentials before indexing via `core/secret_detector.py`.
- **Path Traversal Prevention**: 6 layers of path validation across handlers, git_utils, validation, web, vectorstore, and events.
- **Input Validation**: `validation.py` enforces `ResourceLimits` (MAX_QUERY_LENGTH=5000, MAX_REPO_SIZE=1GB, MAX_FILES=50000, MAX_FILE_SIZE=50MB) to mitigate denial-of-service (CWE-400).
- **Audit Logging**: All operations logged via `core/audit.py` for traceability.
- **Error Sanitization**: `errors.py` provides structured error hierarchy with `sanitize_error_message` to avoid leaking internal paths or secrets.
- **Credential Management**: `providers/credentials.py` loads API keys from env vars/config without storing in memory.

## Plugin System

The `plugins/` directory provides extensibility through three plugin interfaces:
- **LanguageParserPlugin** - Custom language parsing support
- **WikiGeneratorPlugin** - Custom wiki output formats
- **EmbeddingProviderPlugin** - Custom embedding backends

Plugins are discovered via a registry with entry point support.

## Event System

The `events.py` module implements a pub-sub event system:
- **Event types**: `index.*`, `wiki.*`, `research.*`, `error`, `warning`
- **Handler priorities**: Ordered execution of event handlers
- **Auto-deregistration**: Handlers can be one-shot
- **Lifecycle hooks**: Tie into indexing, generation, and query pipelines

## Key Design Decisions

- **Async throughout**: All core operations use asyncio for concurrent LLM/embedding calls
- **Incremental indexing**: File hashes tracked in manifest to only re-process changed files
- **AST-aware chunking**: Code is split at function/class boundaries, not arbitrary token limits
- **Config hierarchy**: CLI args -> env vars -> config file -> defaults
- **Frozen Pydantic config models**: Immutable configuration objects prevent accidental mutation
- **Plugin system**: Extensible architecture for parsers, generators, and embedding providers
- **Event-driven lifecycle hooks**: Decoupled components communicate via pub-sub events
- **RBAC with configurable enforcement**: Access control can be enforced, permissive, or disabled
- **LRU caching for LLM responses**: Avoids redundant LLM calls for identical prompts
- **Parallel file parsing**: ThreadPoolExecutor for concurrent tree-sitter parsing

## Testing Notes

- 5,128 tests across 141 test files with 95% coverage
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`)
- Most tests mock LLM/embedding providers to avoid external calls
- Test files follow pattern `test_<module>.py`
- Shared `conftest.py` provides factory functions; most test files are otherwise self-contained

## Supported Languages

Python, TypeScript/TSX, JavaScript, Go, Rust, Java, C, C++, Swift, Ruby, PHP, Kotlin, C#

All use tree-sitter grammars from `tree-sitter-<language>` packages.
