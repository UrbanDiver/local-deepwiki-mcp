# Changelog

Recent changes to this repository.

## Recent Commits

### January 14, 2026

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

### January 13, 2026

- [`7c7e68d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7c7e68d) Update docs for streaming deep research
  - Files: `CLAUDE.md`, `WIKI_IMPROVEMENTS.md`

- [`28ab9b8`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/28ab9b8) Add streaming progress updates to deep research
  - Files: `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/models.py`, `src/local_deepwiki/server.py`, `tests/test_deep_research.py`

- [`f10b833`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/f10b833) Update docs for configurable deep research
  - Files: `CLAUDE.md`, `WIKI_IMPROVEMENTS.md`

- [`cd866df`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/cd866df) Add configurable deep research parameters
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/server.py`, `tests/test_config.py`

- [`15e7e64`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/15e7e64) Add changelog wiki page from git history
  - Files: `CLAUDE.md`, `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/generators/changelog.py`, `src/local_deepwiki/generators/wiki.py`, `tests/test_changelog.py`

- [`2708dc5`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/2708dc5) Add GitHub/GitLab links to source file references
  - Files: `CLAUDE.md`, `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/core/git_utils.py`, `src/local_deepwiki/generators/source_refs.py`, `src/local_deepwiki/generators/wiki.py` (+1 more)

- [`e579b0a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e579b0a) Add usage examples from test files to wiki documentation
  - Files: `CLAUDE.md`, `WIKI_IMPROVEMENTS.md`, `src/local_deepwiki/generators/test_examples.py`, `src/local_deepwiki/generators/wiki.py`, `tests/test_test_examples.py`

- [`c010b5b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c010b5b) Add new feature ideas to WIKI_IMPROVEMENTS.md
  - Files: `WIKI_IMPROVEMENTS.md`

- [`d15def0`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d15def0) Add deep_research tool to README documentation
  - Files: `README.md`

- [`2d97082`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/2d97082) Add Deep Research mode for multi-step reasoning
  - Files: `CLAUDE.md`, `TODO.md`, `src/local_deepwiki/core/deep_research.py`, `src/local_deepwiki/models.py`, `src/local_deepwiki/server.py` (+1 more)

- [`e441e6b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e441e6b) Update documentation to reflect current project state
  - Files: `CLAUDE.md`, `README.md`, `TODO.md`, `WIKI_IMPROVEMENTS.md`

- [`b2b1759`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b2b1759) Add PDF documentation link to README
  - Files: `README.md`

- [`fb681bb`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/fb681bb) Add generated PDF documentation
  - Files: `docs.pdf`

- [`9e05ee2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/9e05ee2) Regenerate wiki with PDF export documentation
  - Files: `.deepwiki/architecture.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md`, `.deepwiki/files/src/local_deepwiki/core/parser.md` (+26 more)

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-01-14

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/config.py:14-19`](files/src/local_deepwiki/config.md)
- [`tests/test_parser.py:24-123`](files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](files/tests/test_retry.md)
- [`tests/test_ollama_health.py:16-19`](files/tests/test_ollama_health.md)
- [`tests/test_server_handlers.py:15-69`](files/tests/test_server_handlers.md)
- [`tests/test_chunker.py:11-182`](files/tests/test_chunker.md)
- [`tests/test_changelog.py:18-96`](files/tests/test_changelog.md)
- [`tests/test_vectorstore.py:9-28`](files/tests/test_vectorstore.md)
- [`tests/test_pdf_export.py:21-80`](files/tests/test_pdf_export.md)
- [`tests/test_search.py:20-53`](files/tests/test_search.md)


*Showing 10 of 74 source files.*
