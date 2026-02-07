# Module: tests

## Module Purpose

The `tests/` module contains a comprehensive test suite for Local DeepWiki with 3,956 tests across 82 test files, achieving 95% code coverage. Tests use `pytest` with `pytest-asyncio` (auto mode) and mock LLM/embedding providers to avoid external calls.

## Test Organization

### Core Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_parser.py` | `core/parser.py` | Multi-language AST parsing, tree-sitter grammars, error handling |
| `test_chunker.py` | `core/chunker.py` | Semantic chunking, function/class boundary detection |
| `test_vectorstore.py` | `core/vectorstore.py` | LanceDB operations, search, pagination, adaptive search |
| `test_vectorstore_pagination.py` | `core/vectorstore.py` | Cursor-based pagination edge cases |
| `test_indexer.py` | `core/indexer.py` | Full indexing pipeline, incremental updates, manifest |
| `test_deep_research.py` | `core/deep_research.py` | Query decomposition, gap analysis, synthesis, checkpointing |
| `test_llm_cache.py` | `core/llm_cache.py` | LRU cache operations, eviction, TTL |
| `test_rate_limiter.py` | `core/rate_limiter.py` | Token bucket algorithm, rate limiting |
| `test_secret_detector.py` | `core/secret_detector.py` | AWS keys, GitHub tokens, SSH keys, PGP, false positives |
| `test_fuzzy_search.py` | `core/fuzzy_search.py` | Fuzzy matching, "did you mean?" suggestions |
| `test_index_manager.py` | `core/index_manager.py` | Index status, schema versioning |
| `test_git_utils.py` | `core/git_utils.py` | Git operations, injection prevention |
| `test_audit.py` | `core/audit.py` | Audit logging operations |
| `test_embedding_cache.py` | `providers/embeddings/cache.py` | Embedding caching, cache invalidation |

### Generator Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_diagrams.py` | `generators/diagrams.py` | Mermaid diagram generation (class, sequence, module) |
| `test_callgraph.py` | `generators/callgraph.py` | Call graph analysis, edge detection |
| `test_glossary.py` | `generators/glossary.py` | Entity glossary generation |
| `test_inheritance.py` | `generators/inheritance.py` | Class hierarchy extraction |
| `test_coverage.py` | `generators/coverage.py` | Documentation coverage metrics |
| `test_api_docs.py` | `generators/api_docs.py` | API documentation extraction |
| `test_test_examples.py` | `generators/test_examples.py` | Test example extraction |
| `test_changelog.py` | `generators/changelog.py` | Git changelog generation |
| `test_crosslinks.py` | `generators/crosslinks.py` | Wiki cross-referencing |
| `test_see_also.py` | `generators/see_also.py` | Related page suggestions |
| `test_source_refs.py` | `generators/source_refs.py` | Source code reference links |
| `test_stale_detection.py` | `generators/stale_detection.py` | Stale page detection |
| `test_dependency_graph.py` | `generators/dependency_graph.py` | Import dependency analysis |
| `test_context_builder.py` | `generators/context_builder.py` | LLM context assembly |
| `test_manifest.py` | `generators/manifest.py` | File hash manifests |
| `test_toc.py` | `generators/toc.py` | Table of contents generation |
| `test_progress_tracker.py` | `generators/progress_tracker.py` | Progress reporting |
| `test_wiki_status.py` | `generators/wiki_status.py` | Wiki page freshness |
| `test_wiki_modules_coverage.py` | `generators/wiki_modules.py` | Module doc generation |
| `test_wiki_pages_coverage.py` | `generators/wiki_pages.py` | Page generation |
| `test_wiki_files_coverage.py` | `generators/wiki_files.py` | File doc generation |
| `test_wiki_coverage.py` | `generators/wiki.py` | Overall wiki generation |

### Provider Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_base_provider.py` | `providers/base.py` | Abstract base class contracts |
| `test_providers.py` | Provider integration | Provider factory and selection |
| `test_provider_factories.py` | Provider creation | Factory pattern tests |
| `test_provider_errors.py` | Provider error handling | Error types and recovery |
| `test_anthropic_provider.py` | `providers/llm/anthropic.py` | Anthropic API integration |
| `test_openai_provider.py` | `providers/llm/openai.py` | OpenAI API integration |
| `test_llm_providers.py` | LLM provider suite | Cross-provider compatibility |
| `test_ollama_health.py` | `providers/llm/ollama.py` | Ollama connection health |
| `test_local_embedding_provider.py` | `providers/embeddings/local.py` | sentence-transformers |
| `test_openai_embeddings.py` | `providers/embeddings/openai.py` | OpenAI embedding API |
| `test_openai_embedding_provider.py` | `providers/embeddings/openai.py` | Provider configuration |
| `test_credentials.py` | `providers/credentials.py` | API key management |

### Server & Handler Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_server.py` | `server.py` | MCP server setup, tool registration |
| `test_server_handlers.py` | `handlers.py` | Handler dispatch |
| `test_handlers_coverage.py` | `handlers.py` | Comprehensive handler testing |
| `test_server_validation.py` | `validation.py` | Input validation |
| `test_resource_limits.py` | `validation.py` | CWE-400 resource limits |
| `test_new_tools.py` | New MCP tools | Generator tool handlers |

### Security Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_access_control.py` | `security/access_control.py` | RBAC roles and permissions |
| `test_role_config.py` | `security/role_config.py` | Role configuration |
| `test_repository_access.py` | `security/repository_access.py` | Allowlist/denylist |

### Export & UI Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_html_export.py` | `export/html.py` | HTML generation, navigation |
| `test_pdf_export.py` | `export/pdf.py` | PDF generation, WeasyPrint |
| `test_streaming_export.py` | `export/streaming.py` | Streaming export |
| `test_export_init.py` | `export/__init__.py` | Export module initialization |
| `test_web.py` | `web/app.py` | Flask routes, chat, research UI |

### Other Tests

| Test File | Tests For | Key Areas |
|-----------|----------|-----------|
| `test_config.py` | `config.py` | Configuration loading, validation, overrides |
| `test_models.py` | `models.py` | Data model serialization |
| `test_events.py` | `events.py` | Event emission, handlers, priorities |
| `test_errors.py` | `errors.py` | Error hierarchy, messages |
| `test_prompts.py` | `prompts.py` | Prompt template rendering |
| `test_watcher.py` | `watcher.py` | File watching, debouncing |
| `test_plugins.py` | `plugins/` | Plugin loading, registry |
| `test_plugin_registry.py` | `plugins/registry.py` | Plugin discovery |
| `test_examples_plugin.py` | `generators/examples_plugin.py` | Examples plugin |
| `test_search.py` | `generators/search.py` | Search index |
| `test_progress.py` | `progress.py` | Progress reporting |
| `test_type_annotations.py` | Type checking | Type annotation correctness |
| `test_logging_coverage.py` | `logging.py` | Logging configuration |
| `test_config_cli.py` | `cli/config_cli.py` | Config CLI commands |
| `test_interactive_search.py` | `cli/interactive_search.py` | Interactive search UI |
| `test_cli_progress.py` | `cli_progress.py` | CLI progress bars |
| `test_integration_pipeline.py` | End-to-end | Full indexing + query pipeline |
| `test_incremental_wiki.py` | Incremental | Incremental wiki regeneration |
| `test_retry.py` | Retry logic | Exponential backoff |

## Testing Patterns

- **Mocking**: LLM and embedding providers are mocked to avoid external API calls. `AsyncMock` is used extensively for async operations.
- **pytest-asyncio**: All async tests run automatically in auto mode (no `@pytest.mark.asyncio` needed).
- **Temporary directories**: Tests use `tmp_path` fixtures for file system isolation.
- **Self-contained**: Each test file is self-contained with its own fixtures -- no shared `conftest.py`.
- **Coverage target**: 80% minimum per module, 95% achieved overall.
