# Restore B Grade — Surgical Complexity Reduction

## Problem

Architecture health regressed from B (76.5) to C (73.8) after Phases 2a/2b/3a/3b added new features. The regression is caused by new complexity hotspots, primarily `run_check` (CC=32) which raised max CC from 25 to 32.

## Goal

Restore overall health grade to B (>=75) by splitting 3 functions that are the biggest contributors to the complexity score drop. Pure refactoring — no behavioral changes.

## Score Math

Current: complexity 68.1, coupling 69.9, smells 63.5, layers 100. Overall 73.8 (C).

Weights: complexity 0.30, coupling 0.25, smells 0.25, layers 0.20.

To reach 75: need ~4 points. Reducing max CC from 32 to ~23 and cutting 3 functions from the `over_cc15` count should push complexity from 68.1 to ~72+, gaining ~1.2 on overall. Reducing total smells by ~6 (3 long_method removals + associated smell reduction) should push smells from 63.5 to ~65, gaining ~0.4. Combined: ~73.8 + 1.6 = ~75.4 (B).

## Targets

### 1. `run_check` — `cli/check_cli.py:126` (CC=32, 132 lines)

**New function from Phase 3a.** Largest single CC in the codebase.

The function has 3 clear phases: setup (validate + analyze), JSON output, and Rich table output. The Rich table branch contains most of the branching (per-metric threshold checks duplicated for display).

**Extract:**
- `_format_json_output(overall, thresholds, violations) -> str` — lines 177-188. Builds the JSON dict and returns serialized string.
- `_format_rich_table(overall, thresholds, violations, project_name, console)` — lines 190-255. Builds and prints the Rich table. The per-dimension loop (lines 232-246) and per-row status computation are the CC drivers.

**After:** `run_check` becomes ~30 lines: validate repo, load thresholds, run analysis, save snapshot, check thresholds, dispatch to formatter. Target CC ~8.

### 2. `_build_module_graph` — `generators/analysis/module_dependencies.py:91` (CC=22, 73 lines)

**New function from Phase 3a coupling metrics.** Complex nested conditionals for classifying imports as internal/external and resolving target module labels.

**Extract:**
- `_resolve_import_target(dotted, project_tops, src_module, module_filter, include_external) -> str | None` — lines 134-161. Given a dotted import string, returns the target module label or None if it should be skipped. This isolates all the internal/external classification branching.

**After:** `_build_module_graph` becomes a clean scan loop: iterate files, read source, extract imports, call `_resolve_import_target`, accumulate edges. Target CC ~10.

### 3. `generate_module_docs` — `generators/wiki/modules.py:19` (CC=25, 139 lines)

**Pre-existing function, but #2 hotspot.** Three phases: collect modules to generate, concurrent generation, index page creation. The index creation section (lines 116-155) has duplicated branching for cached vs fresh page creation.

**Extract:**
- `_collect_modules_to_generate(directories, status_manager, full_rebuild, pages) -> tuple[list[tuple[str, list[str]]], int]` — lines 58-76. Filters directories, checks regeneration status, returns modules list and skipped count.
- `_create_modules_index_page(pages, directories, index_status, status_manager, full_rebuild) -> tuple[WikiPage | None, bool]` — lines 116-155. Handles the index page creation with cache checking. Returns page and whether it was generated (vs skipped).

**After:** `generate_module_docs` becomes: group files -> collect modules -> concurrent generate -> create index. Target CC ~10.

## Files Modified

| File | Change |
|------|--------|
| `src/local_deepwiki/cli/check_cli.py` | Extract 2 helpers from `run_check` |
| `src/local_deepwiki/generators/analysis/module_dependencies.py` | Extract 1 helper from `_build_module_graph` |
| `src/local_deepwiki/generators/wiki/modules.py` | Extract 2 helpers from `generate_module_docs` |

## Constraints

- **Behavior-preserving only.** Existing tests must pass unchanged. No test modifications.
- **No new features.** No "improvements" beyond the extraction.
- **Same public API.** All extracted functions are private helpers (underscore-prefixed).
- **No new files.** Helpers stay in the same module as the parent function.

## Verification

1. `uv run pytest tests/test_check_cli.py tests/test_module_dependencies.py tests/test_wiki_modules_coverage.py -x -q` — targeted tests pass
2. `uv run pytest tests/ -q` — full suite passes (5,976 tests)
3. `uv run deepwiki check --json` — overall score >= 75, grade B

## Parallelization

All 3 targets are in non-overlapping files. They can be implemented in parallel.
