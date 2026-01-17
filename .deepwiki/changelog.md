# Changelog

Recent changes to this repository.

## Recent Commits

### January 16, 2026

- [`8257db4`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8257db4) Update generated wiki documentation
  - Files: `.deepwiki/changelog.md`, `.deepwiki/coverage.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md`, `.deepwiki/files/src/local_deepwiki/core/chunker.md` (+51 more)

- [`b1a939a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b1a939a) Group wiki generation modules into logical subgraphs
  - Files: `.deepwiki/dependencies.md`

- [`e2023e3`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e2023e3) Split module dependency into focused sub-diagrams
  - Files: `.deepwiki/dependencies.md`

- [`641e5d2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/641e5d2) Simplify module dependency graph for readability
  - Files: `.deepwiki/dependencies.md`

- [`c4da750`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c4da750) Improve diagram rendering and fix mermaid syntax errors
  - Files: `.deepwiki/architecture.md`, `src/local_deepwiki/generators/inheritance.py`, `src/local_deepwiki/web/templates/page.html`

- [`ce7114d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ce7114d) Update WIKI_ENHANCEMENTS.md with completion status
  - Files: `docs/WIKI_ENHANCEMENTS.md`

- [`63a61ae`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/63a61ae) Update TOC to include glossary, inheritance, changelog, and freshness pages
  - Files: `.deepwiki/toc.json`

- [`8aaf4bf`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8aaf4bf) Improve web UI search and add collapsible sidebar navigation
  - Files: `src/local_deepwiki/generators/toc.py`, `src/local_deepwiki/web/templates/page.html`

- [`8ac0de1`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8ac0de1) Add richer LLM context for wiki documentation generation
  - Files: `src/local_deepwiki/generators/context_builder.py`, `src/local_deepwiki/generators/wiki_files.py`, `tests/test_context_builder.py`, `tests/test_wiki_files_coverage.py`

- [`59bad6c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/59bad6c) Add stale documentation detection to identify outdated wiki pages
  - Files: `src/local_deepwiki/core/git_utils.py`, `src/local_deepwiki/generators/stale_detection.py`, `src/local_deepwiki/generators/wiki.py`, `tests/test_stale_detection.py`

- [`216880e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/216880e) Expand test example extraction with multiple test files and class methods
  - Files: `src/local_deepwiki/generators/test_examples.py`, `tests/test_test_examples.py`

- [`37aec0f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/37aec0f) Add git blame integration to show last modified info for code entities
  - Files: `src/local_deepwiki/core/git_utils.py`, `src/local_deepwiki/generators/wiki_files.py`, `tests/test_git_utils.py`

- [`32b5840`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/32b5840) Regenerate wiki with entity search index
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+50 more)

- [`553a2ee`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/553a2ee) Add entity-level search with type filtering and fuzzy matching
  - Files: `src/local_deepwiki/generators/search.py`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/web/templates/page.html`, `tests/test_search.py`, `tests/test_wiki_coverage.py`

- [`202b96d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/202b96d) Add exception documentation to glossary
  - Files: `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/generators/glossary.py`, `tests/test_type_annotations.py`

- [`ce066c4`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ce066c4) Add type annotation extraction and display in glossary
  - Files: `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/generators/glossary.py`, `tests/test_type_annotations.py`

- [`6e0cd5d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/6e0cd5d) Regenerate wiki with inheritance, glossary, and coverage pages
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md` (+52 more)

- [`8d2ab68`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8d2ab68) Add inheritance trees, glossary, and coverage report to wiki
  - Files: `src/local_deepwiki/generators/coverage.py`, `src/local_deepwiki/generators/glossary.py`, `src/local_deepwiki/generators/inheritance.py`, `src/local_deepwiki/generators/wiki.py`, `tests/test_coverage.py` (+3 more)

- [`ea0726d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ea0726d) Regenerate wiki with GitHub links and Used By sections
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/src/local_deepwiki/config.md`, `.deepwiki/files/src/local_deepwiki/core/chunker.md` (+44 more)

- [`62e3290`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/62e3290) Add GitHub source links and Used By sections to wiki pages
  - Files: `docs/WIKI_ENHANCEMENTS.md`, `src/local_deepwiki/generators/callgraph.py`, `src/local_deepwiki/generators/wiki_files.py`, `tests/test_wiki_files_coverage.py`

### January 15, 2026

- [`d275583`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d275583) Add inline expandable source code to wiki documentation
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+49 more)

- [`0d91a70`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0d91a70) Apply Python best practices: black, isort, mypy type fixes
  - Files: `pyproject.toml`, `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/llm_cache.py` (+45 more)

- [`c43354c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c43354c) Improve test coverage for multiple modules to 92% overall
  - Files: `tests/test_callgraph.py`, `tests/test_export_init.py`, `tests/test_git_utils.py`, `tests/test_llm_providers.py`, `tests/test_local_embedding_provider.py` (+5 more)

- [`05e5e3e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/05e5e3e) Improve web/app.py test coverage from 57% to 76%
  - Files: `tests/test_web.py`

- [`83ff230`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/83ff230) Improve manifest.py test coverage from 67% to 96%
  - Files: `tests/test_manifest.py`

- [`8eb23f8`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8eb23f8) Improve llm_cache.py test coverage from 72% to 99%
  - Files: `tests/test_llm_cache.py`, `tests/test_pdf_export.py`

- [`c2c3ab7`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c2c3ab7) Improve chunker.py test coverage from 56% to 97%
  - Files: `tests/test_chunker.py`

- [`887852b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/887852b) Improve handlers.py test coverage from 71% to 94%
  - Files: `tests/test_handlers_coverage.py`

- [`c047afd`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c047afd) Improve logging.py test coverage from 46% to 100%
  - Files: `tests/test_logging_coverage.py`

- [`bf37297`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/bf37297) Improve watcher.py test coverage from 48% to 99%
  - Files: `tests/test_watcher.py`

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-01-16

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_provider_factories.py:21-99`
- `tests/test_parser.py:24-123`
- `tests/test_retry.py:8-144`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-75`
- `tests/test_chunker.py:13-428`
- `tests/test_changelog.py:18-96`
- `tests/test_coverage.py:13-50`
- `tests/test_vectorstore.py:9-28`
- `tests/test_wiki_coverage.py:50-120`


*Showing 10 of 102 source files.*
