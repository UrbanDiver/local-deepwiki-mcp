# Complexity Hotspots

## Summary

- **Total functions scanned:** 2,389
- **Files scanned:** 269
- **Metric used:** complexity

## Top Hotspots

| Rank | Function | File | CC | Lines | Params | Nesting |
|------|----------|------|----|-------|--------|---------|
| 1 | `_compute_cognitive_complexity` | `src/local_deepwiki/generators/analysis/hotspots.py:126` | 16 | 55 | 1 | 0 |
| 2 | `_walk` | `src/local_deepwiki/generators/analysis/hotspots.py:136` | 16 | 42 | 2 | 0 |
| 3 | `_validate_wiki_settings` | `src/local_deepwiki/cli/config_validator.py:244` | 15 | 62 | 0 | 0 |
| 4 | `_get_python_docstring` | `src/local_deepwiki/core/parser/docstrings.py:67` | 15 | 20 | 2 | 0 |
| 5 | `analyze_file_coverage` | `src/local_deepwiki/generators/analysis/coverage.py:106` | 15 | 43 | 2 | 0 |
| 6 | `suggest_topics` | `src/local_deepwiki/generators/codemap/generator.py:549` | 15 | 64 | 3 | 0 |
| 7 | `_collect_relevant_lines` | `src/local_deepwiki/generators/examples/orchestrator.py:100` | 15 | 46 | 3 | 0 |
| 8 | `_collect_see_also_entries` | `src/local_deepwiki/generators/see_also.py:215` | 15 | 35 | 3 | 0 |
| 9 | `_find_related_tests` | `src/local_deepwiki/handlers/analysis_metadata.py:303` | 15 | 35 | 2 | 0 |
| 10 | `_score_entity_match` | `src/local_deepwiki/handlers/analysis_search.py:49` | 15 | 15 | 2 | 0 |
| 11 | `update` | `src/local_deepwiki/progress.py:150` | 15 | 71 | 5 | 0 |
| 12 | `validate_model` | `src/local_deepwiki/providers/llm/anthropic.py:156` | 15 | 67 | 1 | 0 |
| 13 | `_collect_inheritance_dependents` | `src/local_deepwiki/services/analysis_service.py:681` | 15 | 41 | 4 | 0 |
| 14 | `api_code_snippet` | `src/local_deepwiki/web/routes_chat.py:322` | 15 | 63 | 0 | 0 |
| 15 | `_validate_codemap_request` | `src/local_deepwiki/web/routes_codemap.py:181` | 15 | 42 | 1 | 0 |
| 16 | `_load_config` | `src/local_deepwiki/cli/config_validator.py:57` | 14 | 70 | 0 | 0 |
| 17 | `_handle_search_mode` | `src/local_deepwiki/cli/interactive_search.py:431` | 14 | 41 | 1 | 0 |
| 18 | `run_update` | `src/local_deepwiki/cli/update_cli.py:257` | 14 | 58 | 7 | 0 |
| 19 | `create_module_summary_chunk` | `src/local_deepwiki/core/chunk_builders.py:338` | 14 | 58 | 5 | 0 |
| 20 | `find_similar_names` | `src/local_deepwiki/core/fuzzy_search.py:457` | 14 | 77 | 4 | 0 |

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:98-100`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](files/src/local_deepwiki/error_factories.md)
- [`src/local_deepwiki/errors.py:53-118`](files/src/local_deepwiki/errors.md)
- [`src/local_deepwiki/watcher.py:40-46`](files/src/local_deepwiki/watcher.md)


*Showing 10 of 269 source files.*
