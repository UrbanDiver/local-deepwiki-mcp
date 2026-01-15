# Changelog

Recent changes to this repository.

## Recent Commits

### January 14, 2026

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

- [`43b1ef2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/43b1ef2) Refactor: Extract step methods from [DeepResearchPipeline](files/src/local_deepwiki/core/deep_research.md).research()
  - Files: `src/local_deepwiki/core/deep_research.py`

- [`e90b8f7`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e90b8f7) Refactor: Add [handle_tool_errors](files/src/local_deepwiki/handlers.md) [decorator](files/src/local_deepwiki/providers/base.md) for consistent error handling
  - Files: `src/local_deepwiki/server.py`

- [`7172b23`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7172b23) Refactor: Use dispatch dictionary for tool handlers
  - Files: `src/local_deepwiki/server.py`

- [`51c0806`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/51c0806) Refactor: Extract _row_to_chunk() helper in [VectorStore](files/src/local_deepwiki/core/vectorstore.md)
  - Files: `src/local_deepwiki/core/vectorstore.py`

- [`5fee5a2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/5fee5a2) Regenerate wiki documentation with all file pages
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+71 more)

- [`8945a3d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8945a3d) Add chat_llm_provider config for web chat/research endpoints
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/web/app.py`, `src/local_deepwiki/web/templates/chat.html`, `tests/test_config.py`

- [`1d64f39`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1d64f39) Increase max_file_docs from 20 to 75
  - Files: `src/local_deepwiki/config.py`

- [`5f52f84`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/5f52f84) Fix source refs to link all existing wiki pages
  - Files: `src/local_deepwiki/generators/source_refs.py`, `src/local_deepwiki/generators/wiki.py`

- [`42a9a7b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/42a9a7b) Fix dependencies page: local links, source file priority, clean graph
  - Files: `src/local_deepwiki/generators/diagrams.py`, `src/local_deepwiki/generators/source_refs.py`, `src/local_deepwiki/generators/wiki.py`

- [`e25671f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e25671f) Mark Enhanced Import/Dependency Graphs as complete
  - Files: `WIKI_IMPROVEMENTS.md`

- [`c652a2a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c652a2a) Add enhanced dependency graph with subgraphs, clickable links, and external deps
  - Files: `src/local_deepwiki/generators/diagrams.py`, `src/local_deepwiki/generators/wiki.py`, `tests/test_diagrams.py`

- [`4ce879f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4ce879f) Fix Component Diagram Mermaid syntax error
  - Files: `.deepwiki/architecture.md`

- [`4cdd653`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4cdd653) Add workflow sequence diagrams to architecture documentation
  - Files: `.deepwiki/architecture.md`

- [`36faa4d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/36faa4d) Document cloud provider option for GitHub repos in CLAUDE.md
  - Files: `CLAUDE.md`

- [`1b6c406`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1b6c406) Regenerate wiki documentation using Claude Sonnet
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md` (+31 more)

- [`52202b9`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/52202b9) Add automatic cloud provider switching for GitHub repos
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/core/git_utils.py`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/server.py`, `tests/test_config.py` (+1 more)

- [`2d4aa85`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/2d4aa85) Parallelize file docs generation for faster wiki builds
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/providers/llm/ollama.py`, `tests/test_ollama_health.py`, `tests/test_provider_errors.py`

- [`d387d4f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d387d4f) Add provider-specific prompt templates for LLM optimization
  - Files: `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/config.py`, `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/generators/wiki.py`, `src/local_deepwiki/server.py` (+1 more)

- [`7096531`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7096531) Add cancellation support for deep research operations
  - Files: `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/models.py`, `src/local_deepwiki/server.py`, `tests/test_deep_research.py`

- [`400c6b8`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/400c6b8) Add quick/thorough research presets for deep research
  - Files: `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/config.py`, `src/local_deepwiki/server.py`, `tests/test_config.py`

- [`4048ed9`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4048ed9) Add workflow sequence diagrams to architecture documentation
  - Files: `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/generators/diagrams.py`, `src/local_deepwiki/generators/wiki.py`, `tests/test_diagrams.py`

- [`4f4c411`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4f4c411) Add conversational chat interface to web UI
  - Files: `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/web/app.py`, `src/local_deepwiki/web/templates/chat.html`, `src/local_deepwiki/web/templates/page.html`, `tests/test_web.py`

- [`ac906d4`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ac906d4) Add LLM response caching with embedding similarity
  - Files: `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/config.py`, `src/local_deepwiki/core/llm_cache.py`, `src/local_deepwiki/providers/llm/__init__.py`, `src/local_deepwiki/providers/llm/cached.py` (+2 more)

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-01-14

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_parser.py:24-123`
- `tests/test_retry.py:8-144`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- `tests/test_changelog.py:18-96`
- `tests/test_vectorstore.py:9-28`
- `tests/test_pdf_export.py:21-80`
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`


*Showing 10 of 76 source files.*
