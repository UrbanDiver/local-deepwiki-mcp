# Changelog

Recent changes to this repository.

## Recent Commits

### February 06, 2026

- [`4dbba1e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4dbba1e) fix: Improve wiki accuracy, fix indexing bugs, and resolve flaky test
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+61 more)

- [`21d245e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/21d245e) feat: Add 12 new MCP tools exposing generator/core capabilities
  - Files: `src/local_deepwiki/handlers.py`, `src/local_deepwiki/models.py`, `src/local_deepwiki/server.py`, `tests/test_new_tools.py`

### January 31, 2026

- [`1468d91`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1468d91) Fix HTML export internal links and add external link handling
  - Files: `src/local_deepwiki/export/html.py`, `tests/test_html_export.py`

### January 26, 2026

- [`beb9f45`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/beb9f45) Improve dependency_graph test coverage from 85% to 99%
  - Files: `tests/test_dependency_graph.py`

- [`c3aec5d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c3aec5d) Improve fuzzy_search test coverage from 83% to 96%
  - Files: `tests/test_fuzzy_search.py`

- [`0fe815e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0fe815e) Fix test warnings about unawaited coroutines
  - Files: `pyproject.toml`, `tests/test_html_export.py`, `tests/test_interactive_search.py`, `tests/test_server.py`, `tests/test_watcher.py`

- [`b5b8d50`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b5b8d50) Add Phase 2 test coverage improvements
  - Files: `tests/test_credentials.py`, `tests/test_examples_plugin.py`, `tests/test_export_init.py`, `tests/test_local_embedding_provider.py`

- [`e6b985c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e6b985c) Add comprehensive tests for low coverage modules
  - Files: `tests/test_anthropic_provider.py`, `tests/test_interactive_search.py`, `tests/test_openai_embeddings.py`, `tests/test_openai_provider.py`, `tests/test_pdf_export.py` (+2 more)

- [`89d3399`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/89d3399) Add code quality improvements: rate limiting, test coverage, error handling r...
  - Files: `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/core/rate_limiter.py`, `src/local_deepwiki/handlers.py`, `src/local_deepwiki/providers/base.py`, `tests/test_config_cli.py` (+1 more)

- [`5717c3a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/5717c3a) Phase 4: RBAC hardening with enforcement modes, role config, and repo access ...
  - Files: `examples/roles.yaml`, `src/local_deepwiki/handlers.py`, `src/local_deepwiki/security/__init__.py`, `src/local_deepwiki/security/access_control.py`, `src/local_deepwiki/security/repository_access.py` (+3 more)

- [`7f23c3c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7f23c3c) Security fixes: Git command injection, hook script validation, export path va...
  - Files: `src/local_deepwiki/core/git_utils.py`, `src/local_deepwiki/events.py`, `src/local_deepwiki/handlers.py`, `tests/test_events.py`, `tests/test_git_utils.py`

- [`9844731`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/9844731) Phase 3: Implement input validation, audit logging, and secret detection
  - Files: `src/local_deepwiki/core/audit.py`, `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/secret_detector.py`, `src/local_deepwiki/handlers.py`, `src/local_deepwiki/validation.py` (+3 more)

- [`b416426`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b416426) Phase 2 completion: Fix RBAC async support, add tests, integrate into handlers
  - Files: `src/local_deepwiki/handlers.py`, `src/local_deepwiki/security/__init__.py`, `src/local_deepwiki/security/access_control.py`, `tests/test_access_control.py`

- [`11bcd8e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/11bcd8e) Add Phase 3 comprehensive implementation plan
  - Files: `PHASE_3_IMPLEMENTATION_PLAN.md`

- [`4eb4353`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4eb4353) Phase 2: Implement RBAC, dependency pinning, and YAML safety verification
  - Files: `.claude-flow/.gitignore`, `.claude-flow/CAPABILITIES.md`, `.claude-flow/config.yaml`, `.claude-flow/daemon-state.json`, `.claude-flow/daemon.pid` (+33 more)

- [`dc57a7b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/dc57a7b) Add low-priority enhancements: fuzzy search, config validation, [event](files/coverage_openai_embeddings/coverage_html_cb_dd2e7eb5.md) leak pr...
  - Files: `pyproject.toml`, `src/local_deepwiki/cli/__init__.py`, `src/local_deepwiki/cli/interactive_search.py`, `src/local_deepwiki/config.py`, `src/local_deepwiki/core/fuzzy_search.py` (+9 more)

- [`a64166a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/a64166a) Add seven medium-priority enhancements for scalability, visualization, and UX
  - Files: `pyproject.toml`, `src/local_deepwiki/config.py`, `src/local_deepwiki/core/vectorstore.py`, `src/local_deepwiki/export/__init__.py`, `src/local_deepwiki/export/html.py` (+25 more)

### January 25, 2026

- [`e899c6c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e899c6c) Add three high-value enhancements: parallel embeddings, research checkpointin...
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/parser.py`, `src/local_deepwiki/core/vectorstore.py` (+9 more)

- [`d7c79d3`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d7c79d3) Add three quick-win enhancements: [IndexStatusManager](files/src/local_deepwiki/core/index_manager.md), structured errors, sear...
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/core/index_manager.py`, `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/vectorstore.py`, `src/local_deepwiki/errors.py` (+8 more)

- [`b6594e4`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b6594e4) Add dependency validation and topological sort for wiki generators
  - Files: `src/local_deepwiki/generators/wiki.py`, `tests/test_plugins.py`

- [`ff77f37`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ff77f37) Add debug logging for progress token extraction failures
  - Files: `src/local_deepwiki/handlers.py`

- [`5a8c32b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/5a8c32b) Implement LRU cache eviction for LLM response cache
  - Files: `src/local_deepwiki/core/llm_cache.py`, `tests/test_llm_cache.py`

- [`8817f7b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8817f7b) Add thread safety to [VectorStore](files/src/local_deepwiki/core/vectorstore.md) lazy initialization
  - Files: `src/local_deepwiki/core/vectorstore.py`

### January 24, 2026

- [`66ce5c0`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/66ce5c0) Add integration tests for plugin system
  - Files: `tests/test_plugins.py`

- [`4e9d8f5`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4e9d8f5) Integrate plugin system into code paths
  - Files: `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/providers/embeddings/__init__.py`

- [`a0b2f83`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/a0b2f83) Integrate [event](files/coverage_openai_embeddings/coverage_html_cb_dd2e7eb5.md) system into indexer, wiki generator, and deep research
  - Files: `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/generators/wiki.py`

- [`ff98964`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ff98964) Add [event](files/coverage_openai_embeddings/coverage_html_cb_dd2e7eb5.md)/hooks system for lifecycle callbacks
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/events.py`, `tests/test_events.py`

- [`f2db999`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/f2db999) Add plugin system for extensibility
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/plugins/__init__.py`, `src/local_deepwiki/plugins/base.py`, `src/local_deepwiki/plugins/registry.py`, `tests/test_plugins.py`

- [`a142542`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/a142542) Add custom prompt template system
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/prompts.py`, `tests/test_prompts.py`

- [`f62161e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/f62161e) Add incremental wiki update enhancements
  - Files: `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/generators/wiki_status.py`, `tests/test_wiki_status.py`

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-02-06

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/models.py:11-26`](files/src/local_deepwiki/models.md)
- `tests/test_manifest.py:19-61`
- [`src/local_deepwiki/server.py:47-558`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/generators/diagrams.py:12-21`](files/src/local_deepwiki/generators/diagrams.md)
- [`src/local_deepwiki/handlers.py:695-715`](files/src/local_deepwiki/handlers.md)
- `coverage_html/coverage_html_cb_dd2e7eb5.js:11-19`
- `tests/test_provider_factories.py:21-99`
- `tests/test_streaming_export.py:48-71`
- `tests/test_parser.py:28-127`
- `tests/test_fuzzy_search.py:16-48`


*Showing 10 of 166 source files.*
