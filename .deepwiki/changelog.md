# Changelog

Recent changes to this repository.

## Recent Commits

### March 31, 2026

- [`71f7287`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/71f7287) chore: clean up project presentation
  - Files: `CHANGELOG.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `src/local_deepwiki/tools/__init__.py`

- [`27e3cd1`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/27e3cd1) feat: release readiness — OpenAI default, proxy support, onboarding docs
  - Files: `.gitignore`, `README.md`, `docs/PLAN-agent-improvements.md`, `docs/superpowers/plans/2026-03-19-architecture-improvements.md`, `docs/superpowers/plans/2026-03-19-architecture-tools-v2.md` (+35 more)

- [`1276e81`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1276e81) refactor: remove backward-compat shims, dead code, and duplicate functions
  - Files: `.github/actions/deepwiki-analyze/entrypoint.py`, `src/local_deepwiki/core/chunker.py`, `src/local_deepwiki/core/git_utils.py`, `src/local_deepwiki/core/graph_rag/store.py`, `src/local_deepwiki/core/indexer.py` (+38 more)

- [`14b2499`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/14b2499) fix: skip bare-word link targets in wiki link checker
  - Files: `tests/wiki_output_helpers.py`

- [`d8d0cfa`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d8d0cfa) fix: codemap wiki pages match interactive codemap parameters
  - Files: `src/local_deepwiki/config/models_wiki.py`, `src/local_deepwiki/generators/wiki/codemap_pages.py`, `src/local_deepwiki/web/templates/codemap.html`, `src/local_deepwiki/web/templates/page.html`

- [`639e476`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/639e476) refactor: extract _has_enough_outbound_calls and _validate_suggestions
  - Files: `src/local_deepwiki/generators/codemap/generator.py`

- [`1b79dfb`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1b79dfb) feat: interactive code references in chat responses
  - Files: `src/local_deepwiki/web/templates/chat.html`

- [`6087eaa`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/6087eaa) feat: add /api/code-snippet endpoint for expandable source code
  - Files: `src/local_deepwiki/web/routes_chat.py`, `tests/test_chat_code_refs.py`

- [`7da10d9`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7da10d9) docs: chat code references design spec
  - Files: `docs/superpowers/specs/2026-03-31-chat-code-references-design.md`

- [`dbabaa8`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/dbabaa8) fix: harden wiki link checker against LLM hallucination patterns
  - Files: `tests/wiki_output_helpers.py`

### March 30, 2026

- [`e56e9ca`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e56e9ca) fix: hybrid chat search + validated codemap suggestions
  - Files: `src/local_deepwiki/generators/codemap/generator.py`, `tests/test_codemap_entry_points.py`

- [`447d5b7`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/447d5b7) fix: filter leaf nodes and trivial wrappers from codemap suggestions
  - Files: `src/local_deepwiki/generators/codemap/generator.py`, `tests/test_codemap_suggestions.py`

- [`b731205`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/b731205) fix: use hybrid search in chat streaming for natural language queries
  - Files: `src/local_deepwiki/services/query_service.py`, `tests/test_query_service.py`

- [`7045100`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7045100) fix: resolve Pyright errors and harden wiki link checker
  - Files: `tests/wiki_output_helpers.py`

- [`4b1fa98`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4b1fa98) fix: add type narrowing for Optional fields in wiki pipeline
  - Files: `src/local_deepwiki/generators/wiki/generator.py`, `src/local_deepwiki/generators/wiki/pipeline.py`

- [`154b1a6`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/154b1a6) chore: remove unused [FuzzySearchHelper](files/src/local_deepwiki/core/fuzzy_search.md) and [VectorStore](files/src/local_deepwiki/core/vectorstore/store.md) imports from [SearchMixin](files/src/local_deepwiki/core/vectorstore/mixins/search.md)
  - Files: `src/local_deepwiki/core/vectorstore/mixins/search.py`

- [`8815414`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8815414) refactor: remove 18 dead delegation methods from [WikiGenerator](files/src/local_deepwiki/generators/wiki/generator.md)
  - Files: `src/local_deepwiki/generators/wiki/generator.py`, `tests/test_plugins.py`, `tests/test_wiki_generation_warnings.py`, `tests/test_wiki_incremental.py`

- [`0d1edf2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0d1edf2) refactor: extract _build_initial_pipeline_ctx from [init_generation_context](files/src/local_deepwiki/generators/wiki/pipeline.md)
  - Files: `src/local_deepwiki/generators/wiki/pipeline.py`

- [`e10b842`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e10b842) fix: _ensure_pipeline_ctx uses getattr for test-created instances
  - Files: `src/local_deepwiki/generators/wiki/generator.py`

- [`233b2ed`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/233b2ed) refactor: simplify phases.py to use ctx.pipeline_ctx, clean unused imports
  - Files: `src/local_deepwiki/core/vectorstore/mixins/search.py`, `src/local_deepwiki/generators/wiki/phases.py`

- [`22c9676`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/22c9676) refactor: build [WikiPipelineContext](files/src/local_deepwiki/generators/wiki/context.md) once, remove redundant params
  - Files: `src/local_deepwiki/generators/wiki/generator.py`, `src/local_deepwiki/generators/wiki/pipeline.py`, `tests/test_wiki_context.py`

- [`ecc1f18`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ecc1f18) refactor: [SearchMixin](files/src/local_deepwiki/core/vectorstore/mixins/search.md) builds [SearchRequest](files/src/local_deepwiki/core/vectorstore/mixins/search_types.md) before delegating to engine
  - Files: `src/local_deepwiki/core/vectorstore/mixins/search.py`, `tests/test_search_params.py`

- [`e5792b5`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e5792b5) refactor: simplify [SearchEngine](files/src/local_deepwiki/core/vectorstore/search_engine.md).search() to accept only [SearchRequest](files/src/local_deepwiki/core/vectorstore/mixins/search_types.md)
  - Files: `src/local_deepwiki/core/vectorstore/search_engine.py`, `tests/test_search_params.py`

- [`c14fae3`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c14fae3) feat: add offset and cursor fields to [SearchRequest](files/src/local_deepwiki/core/vectorstore/mixins/search_types.md)
  - Files: `src/local_deepwiki/core/vectorstore/mixins/search_types.py`, `tests/test_search_params.py`

- [`a6e9042`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/a6e9042) refactor: remove legacy kwargs from [SearchEngine](files/src/local_deepwiki/core/vectorstore/search_engine.md).__init__
  - Files: `src/local_deepwiki/core/vectorstore/search_engine.py`, `tests/test_search_params.py`

- [`063dccf`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/063dccf) refactor: architecture Grade A improvements (B 80.6 → A 91.2)

- [`1eef062`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1eef062) refactor: complete Grade A architecture improvements (B 80.6 → A 91.2)
  - Files: `src/local_deepwiki/cli/init_cli.py`, `src/local_deepwiki/cli/update_cli.py`, `src/local_deepwiki/core/__init__.py`, `src/local_deepwiki/core/audit.py`, `src/local_deepwiki/core/chunk_builders.py` (+57 more)

- [`ca3ccca`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ca3ccca) refactor: flatten deep nesting and deduplicate impact analysis helpers
  - Files: `src/local_deepwiki/config/loader.py`, `src/local_deepwiki/core/chunk_extractors.py`, `src/local_deepwiki/generators/analysis/callgraph.py`, `src/local_deepwiki/generators/diagrams/class_diagram.py`, `src/local_deepwiki/handlers/analysis_entity.py` (+1 more)

- [`c585f63`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c585f63) refactor: decompose long_method smells in [run_search](files/src/local_deepwiki/cli/interactive_search.md) and [run_generation_pipeline](files/src/local_deepwiki/generators/wiki/pipeline.md)
  - Files: `src/local_deepwiki/cli/interactive_search.py`, `src/local_deepwiki/generators/wiki/pipeline.py`

### March 29, 2026

- [`db2e827`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/db2e827) fix: add [IndexStatus](files/src/local_deepwiki/models/wiki.md) narrowing assertions in wiki phases
  - Files: `src/local_deepwiki/generators/wiki/phases.py`

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-03-31

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/core/git_utils.py:28-31`](files/src/local_deepwiki/core/git_utils.md)
- [`src/local_deepwiki/core/chunker.py:50-63`](files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/server.py:92-94`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/core/vectorstore/embedding.py:20-30`](files/src/local_deepwiki/core/vectorstore/embedding.md)
- [`src/local_deepwiki/core/graph_rag/store.py:44-411`](files/src/local_deepwiki/core/graph_rag/store.md)
- [`src/local_deepwiki/config/provider_models.py:10-20`](files/src/local_deepwiki/config/provider_models.md)
- [`src/local_deepwiki/core/indexer.py:233-263`](files/src/local_deepwiki/core/indexer.md)
- `src/local_deepwiki/providers/llm/__init__.py:16-19`
- [`src/local_deepwiki/cli/init_cli.py:30-43`](files/src/local_deepwiki/cli/init_cli.md)
- [`src/local_deepwiki/web/app.py:87-96`](files/src/local_deepwiki/web/app.md)


*Showing 10 of 263 source files.*
