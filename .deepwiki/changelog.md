# Changelog

Recent changes to this repository.

## Recent Commits

### January 14, 2026

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

- [`782034d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/782034d) Update README with PDF export and other features
  - Files: `README.md`

- [`d18057e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d18057e) Switch mermaid rendering from SVG to PNG for better PDF text display
  - Files: `src/local_deepwiki/export/__init__.py`, `src/local_deepwiki/export/pdf.py`, `tests/test_pdf_export.py`

- [`5b653ae`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/5b653ae) Add mermaid CLI support for PDF diagram rendering
  - Files: `CLAUDE.md`, `src/local_deepwiki/export/__init__.py`, `src/local_deepwiki/export/pdf.py`, `tests/test_pdf_export.py`

- [`3b0bcf2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3b0bcf2) Add PDF export feature with WeasyPrint
  - Files: `CLAUDE.md`, `pyproject.toml`, `src/local_deepwiki/export/__init__.py`, `src/local_deepwiki/export/pdf.py`, `src/local_deepwiki/server.py` (+2 more)

- [`df3a83d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/df3a83d) Update CLAUDE.md with new test count and stats
  - Files: `CLAUDE.md`

- [`119be4a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/119be4a) Regenerate wiki with new features
  - Files: `.deepwiki/architecture.md`, `.deepwiki/dependencies.md`, `.deepwiki/files/index.md`, `.deepwiki/files/src/local_deepwiki/config.md`, `.deepwiki/files/src/local_deepwiki/core/parser.md` (+26 more)

- [`3714760`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3714760) Add code review documentation
  - Files: `.gitignore`, `CODE_REVIEW.md`

- [`1f3b53a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1f3b53a) Add comprehensive test coverage
  - Files: `tests/test_api_docs.py`, `tests/test_callgraph.py`, `tests/test_chunker.py`, `tests/test_config.py`, `tests/test_diagrams.py` (+18 more)

- [`264555b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/264555b) Add Jinja2 template system for web UI
  - Files: `src/local_deepwiki/web/app.py`, `src/local_deepwiki/web/templates/page.html`

- [`c568951`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c568951) Add input validation, type safety, and core improvements
  - Files: `src/local_deepwiki/config.py`, `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/core/indexer.py`, `src/local_deepwiki/core/parser.py`, `src/local_deepwiki/core/vectorstore.py` (+19 more)

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-01-14

## Relevant Source Files

The following source files were used to generate this documentation:

- [`profile_wiki.py:16-59`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/profile_wiki.py#L16-L59)
- [`tests/test_parser.py:24-123`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_parser.py#L24-L123) ([wiki](files/tests/test_parser.md))
- [`tests/test_retry.py:8-144`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_retry.py#L8-L144) ([wiki](files/tests/test_retry.md))
- [`tests/test_ollama_health.py:13-32`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_ollama_health.py#L13-L32)
- [`tests/test_server_handlers.py:15-69`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_server_handlers.py#L15-L69)
- [`tests/test_chunker.py:11-182`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_chunker.py#L11-L182)
- [`tests/test_changelog.py:18-96`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_changelog.py#L18-L96)
- [`tests/test_vectorstore.py:9-28`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_vectorstore.py#L9-L28) ([wiki](files/tests/test_vectorstore.md))
- [`tests/test_pdf_export.py:21-80`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_pdf_export.py#L21-L80) ([wiki](files/tests/test_pdf_export.md))
- [`tests/test_search.py:20-53`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/tests/test_search.py#L20-L53)


*Showing 10 of 75 source files.*
