# Changelog

Recent changes to this repository.

## Recent Commits

### January 16, 2026

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

- [`b89dc25`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b89dc25) Fix: Use lazy imports for PDF exports to avoid WeasyPrint dependency errors
  - Files: `src/local_deepwiki/export/__init__.py`

- [`593e921`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/593e921) Add comprehensive tests for wiki_modules.py and wiki_files.py
  - Files: `tests/test_wiki_files_coverage.py`, `tests/test_wiki_modules_coverage.py`

- [`fa3c469`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/fa3c469) Add comprehensive tests for wiki_pages.py (9% -> 100% coverage)
  - Files: `tests/test_wiki_pages_coverage.py`

### January 14, 2026

- [`bb4b13f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/bb4b13f) Add comprehensive tests for wiki.py (16% -> 85% coverage)
  - Files: `tests/test_wiki_coverage.py`

- [`e9d6602`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e9d6602) Add comprehensive tests for handlers.py (19% -> 64% coverage)
  - Files: `tests/test_handlers_coverage.py`

- [`4dcfc94`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4dcfc94) Add pytest-cov dev dependency for test coverage reporting
  - Files: `pyproject.toml`, `uv.lock`

- [`65d50b1`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/65d50b1) Fix remaining pyright type errors
  - Files: `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/core/llm_cache.py`, `src/local_deepwiki/core/vectorstore.py`, `src/local_deepwiki/generators/wiki.py`

- [`8078321`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8078321) Fix ruff and pyright code quality issues
  - Files: `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/llm_cache.py`, `src/local_deepwiki/generators/callgraph.py`, `src/local_deepwiki/generators/diagrams.py`, `src/local_deepwiki/generators/wiki_files.py` (+6 more)

- [`815ed5f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/815ed5f) Fix remaining generic exceptions with specific types and noqa comments
  - Files: `src/local_deepwiki/export/html.py`, `src/local_deepwiki/export/pdf.py`, `src/local_deepwiki/generators/manifest.py`, `src/local_deepwiki/generators/test_examples.py`, `src/local_deepwiki/providers/llm/ollama.py` (+2 more)

- [`39e8c73`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/39e8c73) Replace generic except Exception with specific exception types
  - Files: `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/llm_cache.py`, `src/local_deepwiki/core/vectorstore.py`, `src/local_deepwiki/generators/wiki_status.py`, `src/local_deepwiki/handlers.py` (+1 more)

- [`3defaaa`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3defaaa) Refactor: Extract validation and wiki submodules for cleaner architecture
  - Files: `CLAUDE.md`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/generators/wiki_files.py`, `src/local_deepwiki/generators/wiki_modules.py`, `src/local_deepwiki/generators/wiki_status.py` (+4 more)

- [`10625ea`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/10625ea) Regenerate wiki with TypeScript/TSX parsing support
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+42 more)

- [`55d665c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/55d665c) Fix TypeScript/TSX parsing by handling module-specific language functions
  - Files: `src/local_deepwiki/core/parser.py`, `src/local_deepwiki/models.py`, `tests/test_parser.py`

- [`63a29fc`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/63a29fc) Remove remaining test file documentation from wiki
  - Files: `.deepwiki/files/tests/test_api_docs.md`, `.deepwiki/files/tests/test_config.md`, `.deepwiki/files/tests/test_crosslinks.md`, `.deepwiki/files/tests/test_deep_research.md`, `.deepwiki/files/tests/test_diagrams.md` (+6 more)

- [`a6c6582`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/a6c6582) Regenerate wiki with all source files, exclude test files
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+73 more)

- [`c87800e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c87800e) Fix wiki file docs to exclude test files, include all source files
  - Files: `src/local_deepwiki/generators/wiki.py`

- [`b8f8b68`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b8f8b68) Refactor: Extract page generators from wiki.py to wiki_pages.py
  - Files: `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/generators/wiki_pages.py`

- [`8457af3`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8457af3) Refactor: Split server.py into server.py and handlers.py
  - Files: `src/local_deepwiki/handlers.py`, `src/local_deepwiki/server.py`, `tests/test_deep_research.py`, `tests/test_server_handlers.py`, `tests/test_server_validation.py`

- [`1ef3ff4`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1ef3ff4) Refactor: Replace nested conditionals in [get_docstring](files/src/local_deepwiki/core/parser.md) with dispatch dictionary
  - Files: `src/local_deepwiki/core/parser.py`

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
- `tests/test_vectorstore.py:9-28`
- `tests/test_wiki_coverage.py:50-120`
- `tests/test_pdf_export.py:23-82`


*Showing 10 of 91 source files.*
