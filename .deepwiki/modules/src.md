# Module: src

## Module Purpose

The `src/local_deepwiki` module contains the entire application source code for Local DeepWiki -- a privacy-focused MCP server that generates comprehensive documentation wikis from code repositories using tree-sitter parsing, vector search, and LLM-powered content generation.

## Package Structure

### `core/` -- Core Pipeline

The foundational components that power indexing, parsing, chunking, and search.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`parser.py`](../files/src/local_deepwiki/core/parser.md) | `CodeParser` | Multi-language AST parsing via tree-sitter (13 languages) |
| [`chunker.py`](../files/src/local_deepwiki/core/chunker.md) | `CodeChunker` | AST-aware semantic code chunking at function/class boundaries |
| [`vectorstore.py`](../files/src/local_deepwiki/core/vectorstore.md) | `VectorStore`, `AdaptiveSearcher` | LanceDB vector storage, similarity search, pagination, caching |
| [`indexer.py`](../files/src/local_deepwiki/core/indexer.md) | `RepositoryIndexer` | Orchestrates parsing, chunking, embedding, storage, and wiki generation |
| [`deep_research.py`](../files/src/local_deepwiki/core/deep_research.md) | `DeepResearchPipeline` | Multi-step reasoning with query decomposition, gap analysis, synthesis |
| [`llm_cache.py`](../files/src/local_deepwiki/core/llm_cache.md) | `LLMCache` | LRU response cache for LLM calls |
| [`rate_limiter.py`](../files/src/local_deepwiki/core/rate_limiter.md) | `RateLimiter` | Token bucket rate limiting for API calls |
| [`secret_detector.py`](../files/src/local_deepwiki/core/secret_detector.md) | `SecretDetector` | Hardcoded credential scanning (AWS, GitHub, SSH, PGP, etc.) |
| [`fuzzy_search.py`](../files/src/local_deepwiki/core/fuzzy_search.md) | `FuzzySearchHelper` | "Did you mean?" suggestions for search queries |
| [`index_manager.py`](../files/src/local_deepwiki/core/index_manager.md) | `IndexManager` | IndexStatus tracking with schema versioning |
| [`git_utils.py`](../files/src/local_deepwiki/core/git_utils.md) | `get_recent_commits`, `get_file_last_modified` | Secure git operations with injection prevention |
| [`audit.py`](../files/src/local_deepwiki/core/audit.md) | `AuditLogger` | Operation audit logging for traceability |

### `generators/` -- Wiki Generation

Specialized generators that produce different sections of the wiki documentation.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`wiki.py`](../files/src/local_deepwiki/generators/wiki.md) | `WikiGenerator` | Main orchestrator -- runs 10-phase wiki generation pipeline |
| [`wiki_files.py`](../files/src/local_deepwiki/generators/wiki_files.md) | `generate_file_pages` | Per-file documentation with source refs and call graphs |
| [`wiki_modules.py`](../files/src/local_deepwiki/generators/wiki_modules.md) | `generate_module_docs` | Module-level documentation grouped by directory |
| [`wiki_pages.py`](../files/src/local_deepwiki/generators/wiki_pages.md) | `generate_wiki_pages` | Individual wiki page generation |
| [`diagrams.py`](../files/src/local_deepwiki/generators/diagrams.md) | `DiagramGenerator` | Mermaid diagrams (class, sequence, module, dependency) |
| [`callgraph.py`](../files/src/local_deepwiki/generators/callgraph.md) | `CallGraphGenerator` | Function call graph analysis |
| [`glossary.py`](../files/src/local_deepwiki/generators/glossary.md) | `GlossaryGenerator` | Searchable code entity glossary with type signatures |
| [`inheritance.py`](../files/src/local_deepwiki/generators/inheritance.md) | `InheritanceGenerator` | Class hierarchy tree generation |
| [`coverage.py`](../files/src/local_deepwiki/generators/coverage.md) | `CoverageAnalyzer` | Documentation coverage analysis per file and entity type |
| [`api_docs.py`](../files/src/local_deepwiki/generators/api_docs.md) | `ApiDocGenerator` | Parameter and return type extraction |
| [`test_examples.py`](../files/src/local_deepwiki/generators/test_examples.md) | `CodeExampleExtractor` | Test example extraction linked to source entities |
| [`changelog.py`](../files/src/local_deepwiki/generators/changelog.md) | `generate_changelog` | Git-based changelog generation |
| [`crosslinks.py`](../files/src/local_deepwiki/generators/crosslinks.md) | `CrossLinker` | Cross-reference linking between wiki pages |
| [`see_also.py`](../files/src/local_deepwiki/generators/see_also.md) | `SeeAlsoGenerator` | Related page suggestions |
| [`source_refs.py`](../files/src/local_deepwiki/generators/source_refs.md) | `add_source_refs_sections` | Source code reference links in wiki pages |
| [`stale_detection.py`](../files/src/local_deepwiki/generators/stale_detection.md) | `StaleDetector` | Detects outdated wiki pages |
| [`manifest.py`](../files/src/local_deepwiki/generators/manifest.md) | `ProjectManifest` | File hash manifest for incremental generation |
| [`context_builder.py`](../files/src/local_deepwiki/generators/context_builder.md) | `ContextBuilder` | Assembles context for LLM prompts |
| [`search.py`](../files/src/local_deepwiki/generators/search.md) | `SearchIndexGenerator` | Search index JSON generation |
| [`toc.py`](../files/src/local_deepwiki/generators/toc.md) | `TocGenerator` | Table of contents generation |
| [`dependency_graph.py`](../files/src/local_deepwiki/generators/dependency_graph.md) | `DependencyGraphGenerator` | Import-based dependency analysis |
| [`wiki_status.py`](../files/src/local_deepwiki/generators/wiki_status.md) | `WikiStatusManager` | Wiki page freshness tracking |
| [`progress_tracker.py`](../files/src/local_deepwiki/generators/progress_tracker.md) | `ProgressTracker` | Generation progress reporting |
| [`examples_plugin.py`](../files/src/local_deepwiki/generators/examples_plugin.md) | `ExamplesPlugin` | Plugin interface for code examples |

### `providers/` -- LLM & Embedding Backends

Pluggable provider abstraction for AI model integration.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`base.py`](../files/src/local_deepwiki/providers/base.md) | `LLMProvider`, `EmbeddingProvider` | Abstract base classes defining the provider interface |
| [`credentials.py`](../files/src/local_deepwiki/providers/credentials.md) | `CredentialManager` | API key management from env vars and config |
| [`llm/ollama.py`](../files/src/local_deepwiki/providers/llm/ollama.md) | `OllamaProvider` | Local Ollama LLM integration |
| [`llm/anthropic.py`](../files/src/local_deepwiki/providers/llm/anthropic.md) | `AnthropicProvider` | Anthropic Claude API integration |
| [`llm/openai.py`](../files/src/local_deepwiki/providers/llm/openai.md) | `OpenAILLMProvider` | OpenAI GPT API integration |
| [`llm/cached.py`](../files/src/local_deepwiki/providers/llm/cached.md) | `CachingLLMProvider` | LLM response caching wrapper |
| [`embeddings/local.py`](../files/src/local_deepwiki/providers/embeddings/local.md) | `LocalEmbeddingProvider` | Local sentence-transformers (all-MiniLM-L6-v2) |
| [`embeddings/openai.py`](../files/src/local_deepwiki/providers/embeddings/openai.md) | `OpenAIEmbeddingProvider` | OpenAI text-embedding-3-small |
| [`embeddings/cache.py`](../files/src/local_deepwiki/providers/embeddings/cache.md) | `CachedEmbeddingProvider` | Embedding response caching |

### `security/` -- Access Control & Validation

Multi-layer security subsystem.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`access_control.py`](../files/src/local_deepwiki/security/access_control.md) | `AccessController` | RBAC with admin, editor, viewer, guest roles |
| [`repository_access.py`](../files/src/local_deepwiki/security/repository_access.md) | `RepositoryAccessController` | Repository allowlist/denylist enforcement |
| [`role_config.py`](../files/src/local_deepwiki/security/role_config.md) | `RoleConfig` | Role-based permission configuration |

### `export/` -- Static Output

Wiki export to distributable formats.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`html.py`](../files/src/local_deepwiki/export/html.md) | `HtmlExporter` | Static HTML export with navigation and styling |
| [`pdf.py`](../files/src/local_deepwiki/export/pdf.md) | `PdfExporter` | PDF export via WeasyPrint |
| [`streaming.py`](../files/src/local_deepwiki/export/streaming.md) | `StreamingExporter` | Streaming export for large wikis |

### `plugins/` -- Extensibility

Plugin system for custom parsers, generators, and providers.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`base.py`](../files/src/local_deepwiki/plugins/base.md) | `LanguageParserPlugin`, `WikiGeneratorPlugin`, `EmbeddingProviderPlugin` | Abstract plugin interfaces |
| [`registry.py`](../files/src/local_deepwiki/plugins/registry.md) | `PluginRegistry` | Plugin discovery and lifecycle management |

### `cli/` -- Command-Line Tools

CLI utilities for configuration and interactive search.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`config_cli.py`](../files/src/local_deepwiki/cli/config_cli.md) | `ConfigCLI` | Configuration management CLI (view, validate, reset) |
| [`interactive_search.py`](../files/src/local_deepwiki/cli/interactive_search.md) | `InteractiveSearch` | Terminal-based interactive search interface |

### `web/` -- Web Interface

Browser-based wiki viewer.

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`app.py`](../files/src/local_deepwiki/web/app.md) | Flask app | Wiki browser with chat and deep research UI |

### Top-Level Modules

| File | Class/Function | Purpose |
|------|---------------|---------|
| [`server.py`](../files/src/local_deepwiki/server.md) | `create_server` | MCP server entry point and tool registration |
| [`handlers.py`](../files/src/local_deepwiki/handlers.md) | `handle_*` functions | All MCP tool handler implementations |
| [`config.py`](../files/src/local_deepwiki/config.md) | `DeepWikiConfig` | Frozen Pydantic configuration with provider, parsing, and generation settings |
| [`models.py`](../files/src/local_deepwiki/models.md) | `CodeChunk`, `IndexStatus`, `WikiPage` | Core data models |
| [`validation.py`](../files/src/local_deepwiki/validation.md) | `validate_*` functions | Input validation with CWE-400 resource limits |
| [`events.py`](../files/src/local_deepwiki/events.md) | `EventEmitter` | Pub-sub event system with lifecycle hooks |
| [`errors.py`](../files/src/local_deepwiki/errors.md) | `DeepWikiError` hierarchy | Structured error types (Indexing, Provider, Research, Export, Validation) |
| [`prompts.py`](../files/src/local_deepwiki/prompts.md) | Prompt templates | LLM prompt templates for wiki generation |
| [`watcher.py`](../files/src/local_deepwiki/watcher.md) | `FileWatcher` | File system watcher for auto-reindexing |
| [`progress.py`](../files/src/local_deepwiki/progress.md) | `ProgressReporter` | Progress reporting for long-running operations |
| [`cli_progress.py`](../files/src/local_deepwiki/cli_progress.md) | CLI progress bars | Rich progress bars for CLI operations |
| [`logging.py`](../files/src/local_deepwiki/logging.md) | `setup_logging` | Structured logging configuration |

## How Components Interact

The application follows a pipeline architecture:

1. **Entry**: `server.py` registers MCP tools and delegates to `handlers.py`
2. **Indexing**: `handlers.py` -> `RepositoryIndexer` -> `CodeParser` -> `CodeChunker` -> `EmbeddingProvider` -> `VectorStore` -> `WikiGenerator`
3. **Querying**: `handlers.py` -> `EmbeddingProvider` -> `VectorStore` (search) -> `LLMProvider` (synthesis)
4. **Research**: `handlers.py` -> `DeepResearchPipeline` -> decomposition + parallel retrieval + synthesis
5. **Export**: `handlers.py` -> `HtmlExporter` or `PdfExporter` -> static files

Cross-cutting concerns (`security/`, `events.py`, `validation.py`, `core/audit.py`) are woven through all paths via middleware-style checks in handlers.

## Dependencies

- **Internal**: All packages import from `models.py` and `config.py`. The `generators/` package depends on `core/` for vector search. The `providers/` package is consumed by both `core/` and `generators/`.
- **External**: tree-sitter (13 grammars), LanceDB, sentence-transformers, pydantic, rich, Flask, WeasyPrint, httpx, tiktoken
