# Complexity Hotspots

## Summary

- **Total functions scanned:** 2,322
- **Files scanned:** 263
- **Metric used:** complexity

## Top Hotspots

| Rank | Function | File | CC | Lines | Params | Nesting |
|------|----------|------|----|-------|--------|---------|
| 1 | `_validate_wiki_settings` | `src/local_deepwiki/cli/config_validator.py:244` | 15 | 62 | 0 | 0 |
| 2 | `_get_python_docstring` | `src/local_deepwiki/core/parser/docstrings.py:67` | 15 | 20 | 2 | 0 |
| 3 | `analyze_file_coverage` | `src/local_deepwiki/generators/analysis/coverage.py:106` | 15 | 43 | 2 | 0 |
| 4 | `suggest_topics` | `src/local_deepwiki/generators/codemap/generator.py:549` | 15 | 64 | 3 | 0 |
| 5 | `_collect_relevant_lines` | `src/local_deepwiki/generators/examples/orchestrator.py:100` | 15 | 46 | 3 | 0 |
| 6 | `_collect_see_also_entries` | `src/local_deepwiki/generators/see_also.py:215` | 15 | 35 | 3 | 0 |
| 7 | `_find_related_tests` | `src/local_deepwiki/handlers/analysis_metadata.py:303` | 15 | 35 | 2 | 0 |
| 8 | `_score_entity_match` | `src/local_deepwiki/handlers/analysis_search.py:49` | 15 | 15 | 2 | 0 |
| 9 | `update` | `src/local_deepwiki/progress.py:150` | 15 | 71 | 5 | 0 |
| 10 | `validate_model` | `src/local_deepwiki/providers/llm/anthropic.py:156` | 15 | 67 | 1 | 0 |
| 11 | `_collect_inheritance_dependents` | `src/local_deepwiki/services/analysis_service.py:681` | 15 | 41 | 4 | 0 |
| 12 | `api_code_snippet` | `src/local_deepwiki/web/routes_chat.py:322` | 15 | 63 | 0 | 0 |
| 13 | `_validate_codemap_request` | `src/local_deepwiki/web/routes_codemap.py:181` | 15 | 42 | 1 | 0 |
| 14 | `_load_config` | `src/local_deepwiki/cli/config_validator.py:57` | 14 | 70 | 0 | 0 |
| 15 | `_handle_search_mode` | `src/local_deepwiki/cli/interactive_search.py:431` | 14 | 41 | 1 | 0 |
| 16 | `run_update` | `src/local_deepwiki/cli/update_cli.py:257` | 14 | 58 | 7 | 0 |
| 17 | `create_module_summary_chunk` | `src/local_deepwiki/core/chunk_builders.py:338` | 14 | 58 | 5 | 0 |
| 18 | `find_similar_names` | `src/local_deepwiki/core/fuzzy_search.py:457` | 14 | 77 | 4 | 0 |
| 19 | `validate` | `src/local_deepwiki/core/index_manager.py:204` | 14 | 71 | 1 | 0 |
| 20 | `render_markdown_for_pdf` | `src/local_deepwiki/export/pdf.py:51` | 14 | 62 | 2 | 0 |

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
