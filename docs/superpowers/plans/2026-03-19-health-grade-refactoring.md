# Health Grade Refactoring — D to C

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve architecture health grade from D (51.7) to C (60+) by splitting complexity hotspots, god classes, and long methods.

**Architecture:** Pure refactoring — no new features, no behavioral changes. Extract helpers from long functions, split god classes into focused collaborators. Every refactored file must pass its existing tests unchanged.

**Tech Stack:** Python, pytest

**Score targets:**
- Complexity: 56.2 → 70+ (fix max CC from 59 to <30)
- Smells: 15.0 → 35+ (fix 3 god classes + ~50 long methods)
- Coupling: 44.4 → unchanged (not addressed)
- Layers: 100 → unchanged (already perfect)
- Overall: 51.7 → 62+ (C grade)

---

## Approach

Each task follows the same pattern:
1. Read the function/class to understand its structure
2. Identify cohesive sections that can be extracted into named helpers
3. Extract helpers as private functions or new classes (preserving exact behavior)
4. Run existing tests — they must pass unchanged (no test modifications)
5. Commit

**Key rule:** These are behavior-preserving extractions. Do NOT change logic, add features, or "improve" the code beyond splitting it. The existing tests are the correctness proof.

**Parallelization:** Tasks 1-8 touch completely non-overlapping files. They can run in parallel. Task 9 depends on all others.

---

## Task 1: Core hotspots — chunk_extractors.py + complexity.py

The #1 and #7 complexity hotspots. Fixing `get_parent_classes` (CC=59) alone drops max CC to 44 and moves complexity score from D to C/B.

**Files:**
- Modify: `src/local_deepwiki/core/chunk_extractors.py`
- Modify: `src/local_deepwiki/generators/analysis/complexity.py`

**chunk_extractors.py — 3 functions to split:**

- [ ] `get_parent_classes` (line 93, CC=59, 109 lines) — Multi-language AST parent class extraction. Extract per-language handlers: `_get_python_parent_classes`, `_get_js_parent_classes`, `_get_java_parent_classes`, etc. The main function becomes a dispatcher that calls the right language handler.

- [ ] `extract_python_parameter_types` (line 204, CC=38, 107 lines) — Type annotation extraction. Extract `_extract_type_from_annotation`, `_extract_default_value`, `_extract_return_type` helpers.

- [ ] `extract_python_raised_exceptions` (line 401, CC=17, 53 lines) — Exception extraction. Extract `_extract_raise_target` helper for the AST node matching.

**complexity.py — 1 function to split:**

- [ ] `compute_complexity_metrics` (line 21, CC=34, 251 lines) — The entire module is one giant function with nested closures. Extract `_count_comment_lines`, `_estimate_cyclomatic`, `_extract_function_info`, `_walk_node` as module-level functions (they're already defined as closures — just move them out). Extract `_compute_aggregate_metrics` for the stats computation at the end.

- [ ] Run: `uv run pytest tests/test_chunker.py tests/test_parser_*.py -x -q`
- [ ] Commit: `refactor: split chunk_extractors hotspots and complexity.py closures`

---

## Task 2: CLI long methods

6 CLI functions that are too long. These are the easiest to split — they're sequential procedural code.

**Files:**
- Modify: `src/local_deepwiki/cli/config_cli.py`
- Modify: `src/local_deepwiki/cli/status_cli.py`
- Modify: `src/local_deepwiki/cli/cache_cli.py`
- Modify: `src/local_deepwiki/cli/init_cli.py`
- Modify: `src/local_deepwiki/cli/update_cli.py`
- Modify: `src/local_deepwiki/cli/interactive_search.py`

**config_cli.py:**
- [ ] `cmd_health_check` (line 216, CC=44, 345 lines) — THE largest function in the codebase. It runs ~15 health checks sequentially. Extract each check into its own function: `_check_config_file`, `_check_llm_provider`, `_check_embedding_provider`, `_check_repo_index`, `_check_dependencies`, etc. The main function becomes a loop over check functions.
- [ ] `display_config` (line 21, 85 lines) — Extract `_format_section` helper for each config section.

**status_cli.py:**
- [ ] `_scan_current_files` (line 60, CC=20, 94 lines) — Extract `_categorize_file_change` and `_compute_file_hash` helpers.
- [ ] `collect_status` (line 156, 84 lines) — Extract `_build_index_summary` and `_build_freshness_info`.
- [ ] `display_status` (line 242, CC=16, 84 lines) — Extract `_render_table_section` for each display block.

**cache_cli.py:**
- [ ] `cmd_clear` (line 209, CC=16, 46 lines) — Extract `_clear_embedding_cache` and `_clear_llm_cache`.

**init_cli.py:**
- [ ] `run_wizard` (line 243, CC=27, 127 lines) — Extract `_prompt_llm_config`, `_prompt_embedding_config`, `_prompt_wiki_config` for each wizard section.

**update_cli.py:**
- [ ] `_run_update_async` (line 96, CC=10, 93 lines) — Extract `_setup_indexer` and `_run_indexing_with_progress`.

**interactive_search.py:**
- [ ] `_handle_filter_mode` (line 452, CC=22, 73 lines) — Extract per-filter-type handlers.
- [ ] `main` (line 607, 107 lines) — Extract `_parse_args` and `_run_search_loop`.

- [ ] Run: `uv run pytest tests/test_config_cli.py tests/test_interactive_search_*.py -x -q`
- [ ] Commit: `refactor: split CLI long methods into focused helpers`

---

## Task 3: God class — RepositoryIndexer (25 methods, 904 lines)

**Files:**
- Modify: `src/local_deepwiki/core/indexer.py`

The indexer already had `_run_graph_extraction` split in the previous round. The remaining god class smell comes from 25 methods and 860+ lines.

- [ ] Extract file-processing methods into a new helper module `src/local_deepwiki/core/indexer_files.py`:
  - `_should_include_file`, `_compute_files_to_process`, `_detect_deleted_files`
  - These are pure functions that don't need `self` — they just take paths and return results

- [ ] Extract the `index` method's orchestration steps into smaller private methods:
  - `_prepare_index_run` (resolve paths, load previous status, compute files to process)
  - `_run_parsing_phase` (parse files, extract chunks)
  - `_run_embedding_phase` (embed and store chunks)
  - The `index` method becomes a thin orchestrator calling these phases in sequence.

- [ ] Run: `uv run pytest tests/test_indexer_*.py -x -q`
- [ ] Commit: `refactor: extract RepositoryIndexer file helpers, split index phases`

---

## Task 4: God class — SearchEngine (33 methods, 925 lines)

**Files:**
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py`

- [ ] Extract search pipeline execution into `src/local_deepwiki/core/vectorstore/search_pipeline.py`:
  - `run_keyword_pipeline`, `run_hybrid_pipeline`, `run_vector_pipeline`
  - `execute_vector_search`, `execute_fts_search`, `convert_fts_results`
  - `reciprocal_rank_fusion`
  - These are stateless methods that take table + params and return results

- [ ] Extract post-processing into `src/local_deepwiki/core/vectorstore/search_postprocess.py`:
  - `apply_fuzzy_reranking`, `apply_post_filters`, `attach_suggestions`, `generate_suggestions`
  - These operate on result lists and don't need the full engine

- [ ] SearchEngine becomes a thin coordinator: resolve config → dispatch pipeline → post-process → cache

- [ ] Run: `uv run pytest tests/test_vectorstore*.py tests/test_search_engine*.py -x -q`
- [ ] Commit: `refactor: extract SearchEngine pipeline and postprocessing`

---

## Task 5: God class — LazyPageGenerator (28 methods, 620 lines)

**Files:**
- Modify: `src/local_deepwiki/generators/lazy_generator.py`

- [ ] Extract page caching logic into `src/local_deepwiki/generators/lazy_cache.py`:
  - `_is_page_cached`, `_load_cached_page`, `_cache_page`, `_invalidate_page`
  - Page freshness checking and TTL logic

- [ ] Extract prefetch/drain logic into its own section or the existing `prefetch.py`:
  - `_schedule_prefetch`, `_drain_remaining_pages`, `_prefetch_batch`

- [ ] LazyPageGenerator keeps: page generation orchestration, on-demand generation, the public API

- [ ] Run: `uv run pytest tests/test_lazy_generator*.py -x -q`
- [ ] Commit: `refactor: extract LazyPageGenerator cache and prefetch logic`

---

## Task 6: Generator long methods (15 smells across 5 files)

The generators/ layer has many long functions that build markdown or do AST traversal. Split the genuine complexity; leave sequential assembly that's just long.

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/api_docs.py` (4 smells)
- Modify: `src/local_deepwiki/generators/analysis/callgraph.py` (3 smells)
- Modify: `src/local_deepwiki/generators/analysis/dependency_graph.py` (3 smells)
- Modify: `src/local_deepwiki/generators/analysis/design_smells.py` (3 smells)
- Modify: `src/local_deepwiki/generators/codemap/graph.py` (3 smells)

**api_docs.py:**
- [ ] `extract_python_parameters` (CC=25, 74 lines) — Extract `_parse_param_node` for individual parameter extraction.
- [ ] `parse_google_docstring` (CC=19, 81 lines) — Extract `_parse_docstring_section` for section parsing.
- [ ] `parse_numpy_docstring` (CC=23, 84 lines) — Same pattern as google docstring.
- [ ] `generate_api_reference_markdown` (CC=30, 115 lines) — Extract `_format_function_signature`, `_format_class_section`.

**callgraph.py:**
- [ ] `extract_call_name` (CC=38, 91 lines) — Multi-language call extraction. Extract per-language helpers like chunk_extractors: `_extract_python_call_name`, `_extract_js_call_name`.
- [ ] `_is_builtin_or_noise` (116 lines) — This is a long exclusion list. Extract into a module-level `_BUILTIN_NAMES` frozenset and simplify the function.
- [ ] `generate_call_graph_diagram` (CC=18, 83 lines) — Extract `_build_mermaid_graph` for diagram construction.

**dependency_graph.py:**
- [ ] `generate_file_graph` (CC=17, 90 lines) — Extract `_collect_file_dependencies` and `_render_file_graph_mermaid`.
- [ ] `_build_dependency_graph` (CC=21, 94 lines) — Extract `_resolve_import_target` for import resolution.
- [ ] `_render_module_graph` (CC=33, 122 lines) — Extract `_build_module_mermaid` and `_compute_module_stats`.

**design_smells.py:**
- [ ] `_analyze_file` (CC=36, 208 lines) — The biggest function in our new code! Extract each smell detector: `_detect_god_class`, `_detect_long_method`, `_detect_long_params`, `_detect_feature_envy`, `_detect_deep_nesting`. Each takes the AST data and returns a list of smells.
- [ ] `_walk_function` (100 lines) — Extract `_count_external_calls` for feature envy detection.
- [ ] `analyze_design_smells` (88 lines) — Extract `_compute_summary` for summary aggregation.

**codemap/graph.py:**
- [ ] `discover_entry_points` (CC=20, 94 lines) — Extract `_score_entry_point_candidates` and `_match_query_to_functions`.
- [ ] `_resolve_callees_for_node` (86 lines) — Extract `_resolve_cross_file_callee` for the vector search path.
- [ ] `_find_in_same_file` (CC=16, 56 lines) — Extract `_match_function_by_name` helper.

- [ ] Run: `uv run pytest tests/test_api_docs.py tests/test_callgraph.py tests/test_dependency_graph_*.py tests/test_design_smells.py tests/test_codemap*.py -x -q`
- [ ] Commit: `refactor: split generator long methods into focused helpers`

---

## Task 7: Handler and service long methods (15 smells)

Handler functions are often long because they do validation → business logic → response formatting. Extract the business logic sections.

**Files:**
- Modify: `src/local_deepwiki/handlers/agentic.py` (4 smells)
- Modify: `src/local_deepwiki/handlers/analysis_diff.py` (2 smells)
- Modify: `src/local_deepwiki/handlers/analysis_search.py` (2 smells)
- Modify: `src/local_deepwiki/handlers/analysis_metadata.py` (2 smells)
- Modify: `src/local_deepwiki/handlers/core.py` (3 smells)
- Modify: `src/local_deepwiki/services/analysis_service.py` (3 smells)
- Modify: `src/local_deepwiki/services/query_service.py` (1 smell)

**Pattern for handlers:** Extract the body logic into a private `_build_<tool>_result` function. The handler function keeps validation + error handling + response wrapping. This makes handlers under 50 lines.

- [ ] `handle_suggest_next_actions` (137 lines) — Extract `_compute_suggestions` and `_prioritize_suggestions`.
- [ ] `handle_batch_explain_entities` (125 lines) — Extract `_explain_single_entity` for the per-entity loop body.
- [ ] `handle_query_codebase` (91 lines) — Extract `_escalate_to_deep_research` for the auto-escalation path.
- [ ] `handle_find_tools` (54 lines, CC=16) — Extract `_score_tool_match` for the matching logic.
- [ ] `handle_analyze_diff` (215 lines) — Extract `_build_structured_diff` and `_build_question_diff` for the two modes.
- [ ] `handle_ask_about_diff` (177 lines) — Extract `_prepare_diff_context` and `_synthesize_diff_answer`.
- [ ] `handle_search_wiki` (111 lines) — Extract `_build_search_results` for result assembly.
- [ ] `handle_get_wiki_stats` (155 lines) — Extract `_compute_wiki_health_metrics` and `_compute_coverage_stats`.
- [ ] `handle_get_status` (115 lines) — Extract `_build_index_status` and `_build_wiki_status`.
- [ ] `handle_ask_question` (85 lines) — Extract `_prepare_rag_context`.
- [ ] `handle_export_wiki_html` (87 lines) — Extract `_validate_and_resolve_export_paths`.
- [ ] `handle_export_wiki_pdf` (91 lines) — Same pattern.
- [ ] `explain_entity` in analysis_service (81 lines) — Extract `_collect_entity_sections`.
- [ ] `impact_analysis` in analysis_service (87 lines) — Extract `_collect_impact_data`.
- [ ] `answer_question` in query_service (137 lines) — Extract `_run_rag_pipeline` and `_format_rag_answer`.

- [ ] Run: `uv run pytest tests/test_handlers_*.py tests/test_agentic*.py tests/test_analysis_*.py tests/test_explain_entity.py tests/test_impact_analysis.py -x -q`
- [ ] Commit: `refactor: split handler and service long methods`

---

## Task 8: Remaining core long methods (12 smells)

Scattered long methods in core/ and other modules.

**Files:**
- Modify: `src/local_deepwiki/core/vectorstore/embedding.py` (2 smells)
- Modify: `src/local_deepwiki/core/vectorstore/indexes.py` (1 smell)
- Modify: `src/local_deepwiki/core/git_blame.py` (2 smells)
- Modify: `src/local_deepwiki/core/fuzzy_search.py` (1 smell)
- Modify: `src/local_deepwiki/core/llm_cache.py` (2 smells)
- Modify: `src/local_deepwiki/core/agentic_rag.py` (1 smell)
- Modify: `src/local_deepwiki/core/parsing_pipeline.py` (1 smell)
- Modify: `src/local_deepwiki/core/secret_detector.py` (1 smell)
- Modify: `src/local_deepwiki/providers/retry.py` (3 smells — actually 1 function with nested decorators)

**Key splits:**
- [ ] `embed_single_batch_with_retry` (CC=20, 93 lines) — Extract `_handle_batch_error` for the error recovery logic.
- [ ] `batch_embed` (CC=21, 158 lines) — Extract `_split_into_batches` and `_merge_batch_results`.
- [ ] `ensure_indexes` (CC=26, 74 lines) — Extract `_create_fts_index` and `_create_vector_index`.
- [ ] `_parse_all_porcelain_blame` (CC=21, 63 lines) — Extract `_parse_blame_header` for header parsing.
- [ ] `_parse_line_blame_map` (CC=27, 73 lines) — Extract `_parse_blame_entry` for per-line parsing.
- [ ] `build_name_index` (CC=21, 84 lines) — Extract `_extract_names_from_table` for the table scan.
- [ ] `get` in llm_cache (CC=14, 96 lines) — Extract `_deserialize_cached_response`.
- [ ] `_maybe_evict` (CC=21, 95 lines) — Extract `_select_eviction_candidates`.
- [ ] `agentic_retrieve` (CC=15, 99 lines) — Extract `_grade_and_filter_results` and `_rewrite_query`.
- [ ] `parse_files_parallel` (156 lines) — Extract `_process_single_file` for the per-file body.
- [ ] `_should_skip_file` (143 lines) — This is mostly a long list of path checks. Extract `_SKIP_PATTERNS` as a data structure and simplify the function to a pattern match loop.
- [ ] `with_retry` in retry.py — The nested decorator/wrapper is flagged 3x but it's a single unit. Flatten the nesting by extracting `_execute_with_backoff` as a standalone async helper.

- [ ] Run: `uv run pytest tests/ -x -q` (broad — touches many modules)
- [ ] Commit: `refactor: split remaining core long methods`

---

## Task 9: Verification

- [ ] Run full test suite: `uv run pytest tests/ -q`
- [ ] Run architecture health check and compare:

```bash
uv run python -c "
import asyncio, json
from unittest.mock import patch
from local_deepwiki.handlers.analysis_architecture import handle_get_architecture_health, handle_compare_architecture
async def main():
    with patch('local_deepwiki.handlers.analysis_architecture.get_access_controller'):
        # Current health
        r = await handle_get_architecture_health({'repo_path': '.'})
        data = json.loads(r[0].text)
        o = data['overall']
        print(f'Health: {o[\"grade\"]} ({o[\"score\"]})')
        for dim, info in o['dimensions'].items():
            print(f'  {dim}: {info[\"grade\"]} ({info[\"score\"]})')
        # Compare vs before refactoring
        r2 = await handle_compare_architecture({'repo_path': '.', 'base_ref': 'HEAD~8', 'head_ref': 'HEAD'})
        d2 = json.loads(r2[0].text)
        deltas = d2.get('deltas', {})
        print(f'\\nDelta: {deltas[\"base_grade\"]} -> {deltas[\"head_grade\"]} ({deltas[\"overall_delta\"]:+.1f})')
asyncio.run(main())
"
```

- [ ] Expected: Overall grade C (60+), complexity B (70+), smells D+ (35+)
- [ ] Commit: `chore: verify health grade improvement D -> C`

---

## Execution Notes

**Parallelization:** Tasks 1-8 touch completely non-overlapping files:
- Task 1: `core/chunk_extractors.py`, `generators/analysis/complexity.py`
- Task 2: `cli/*.py`
- Task 3: `core/indexer.py` → `core/indexer_files.py`
- Task 4: `core/vectorstore/search_engine.py` → `search_pipeline.py`, `search_postprocess.py`
- Task 5: `generators/lazy_generator.py` → `generators/lazy_cache.py`
- Task 6: `generators/analysis/{api_docs,callgraph,dependency_graph,design_smells}.py`, `generators/codemap/graph.py`
- Task 7: `handlers/{agentic,analysis_diff,analysis_search,analysis_metadata,core}.py`, `services/*.py`
- Task 8: `core/{vectorstore/embedding,vectorstore/indexes,git_blame,fuzzy_search,llm_cache,agentic_rag,parsing_pipeline,secret_detector}.py`, `providers/retry.py`

All 8 can run in parallel. Task 9 runs after all complete.

**Risk:** Some refactorings may change import paths if we create new modules (Tasks 3-5). The existing tests should still pass because we keep the original module and its public API — new modules are internal helpers imported by the original.

**What we're NOT fixing:** 170 Feature Envy smells and 53 Long Parameter List smells. Feature Envy often reflects legitimate data flow patterns in a tool-oriented codebase. Long parameter lists are mostly in the handlers (where parameters come from MCP tool arguments). Fixing these would require deeper architectural changes for marginal score improvement.
