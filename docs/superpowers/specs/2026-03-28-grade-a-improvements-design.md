# Grade A Improvements — Design Spec

## Problem Statement

The local-deepwiki-mcp project scores B (76.5/100) on its own architecture health grading. During a self-analysis using the MCP server tools, three categories of issues were identified:

1. **MCP tool measurement gaps** — module-level coupling returns incorrect data (0 Ca/Ce for modules with 184+ inbound imports), recommendations silently skip detected data clumps, and composite/drill-down tools overlap ~60% in output.
2. **Code quality: parameter bloat** — 60 `long_parameter_list` smells across `generators/wiki/` and `core/vectorstore/`, with functions taking up to 13 parameters.
3. **Code quality: complexity hotspots** — 50 functions exceed CC 15 (max CC 23), driving both the complexity score (78.1) and smells score (62.4) down.

## Goals

- Move overall health grade from B (76.5) to A (90+)
- Fix MCP tool measurement gaps so analysis is trustworthy
- Reduce tool output redundancy so agents waste less context
- Eliminate all CC > 15 functions
- Reduce weighted smell density from 4.7 to < 2.0 per 1K lines

## Non-Goals

- Splitting large test files (deferred — separate effort)
- Changing the scoring model itself (improvements must be real code quality gains)
- Runtime/behavioral analysis (aspirational, not in scope)

## Scoring Model Reference

```
Overall = Complexity × 0.30 + Coupling × 0.25 + Smells × 0.25 + Layers × 0.20

Complexity: 100 - (max_cc penalty) - (high_cc_pct × 5, cap 40)
  max_cc > 50: -30, > 30: -20, > 15: -10

Coupling: 100 - (avg_distance × 50, cap 40) - (unstable_pct × 2, cap 25)
  unstable = instability > 0.8 AND efferent_coupling > 5

Smells: 100 - (weighted_density_per_1k × 8, cap 80) - (god_classes × 10, cap 35)
  severity weights: high=3, medium=1, low=0.5

Layers: 100 - (violations × 10)

Grades: A >= 90, B >= 75, C >= 60, D >= 40, F < 40
```

## Current State

| Dimension | Score | Grade | Key Factors |
|-----------|-------|-------|-------------|
| Complexity | 78.1 | B | max_cc=23, 50 functions over CC 15 (2.4%) |
| Coupling | 69.9 | C | avg_distance=0.42, 18 highly unstable modules (4.6%) |
| Smells | 62.4 | C | density=4.7/1K, 176 smells (91 high, 85 medium), 0 god classes |
| Layers | 100.0 | A | 0 violations |
| **Overall** | **76.5** | **B** | |

## Target State

| Dimension | Current | Target | Delta |
|-----------|---------|--------|-------|
| Complexity | 78.1 | ~100 | +21.9 (all functions below CC 15) |
| Coupling | 69.9 | ~80 | +10.1 (reduced distance and unstable modules) |
| Smells | 62.4 | ~86 | +23.6 (parameter objects + method decomposition) |
| Layers | 100.0 | 100 | 0 |
| **Overall** | **76.5** | **~91.5** | **+15.0 (B -> A)** |

---

## Design

### Phase 1: Sharpen the Tools

*Fix MCP measurement gaps and reduce output noise. No code quality changes yet — this gives us an accurate baseline.*

#### 1.1 Fix Module-Level Coupling Measurement

**Root cause:** `module_health.py:53` passes `module_filter=module_name` to `analyze_coupling_metrics()`. This restricts both source file scanning AND target resolution. When analyzing `core.vectorstore`, only files inside that module are scanned — inbound imports from other modules are never discovered, so Ca always reads 0.

**Fix:** Remove the `module_filter` argument from the coupling call in `module_health.py`. Run the full dependency graph, then extract only the requested module's metrics from the result set.

**Files:** `src/local_deepwiki/generators/analysis/module_health.py`

**Acceptance criteria:**
- `get_module_health("core.vectorstore")` returns non-zero Ca reflecting its 184+ inbound imports
- `get_module_health("generators.wiki")` returns non-zero Ca reflecting its 143+ inbound imports
- Existing tests pass (update mocks if needed)

#### 1.2 Add Missing Recommendation Types

**Data clump -> parameter object:** Detection already works in `design_smells.py` (type `"data_clump"`, severity `"low"`), but `recommendations.py` has no template for it. Data clumps are silently skipped at line 98 (`if template is None: continue`).

**Fix:** Add template to `_TEMPLATES` list in `recommendations.py`:
```python
{
    "finding_type": "data_clump",
    "category": "smells",
    "title_template": "Extract shared parameters into a parameter object for {entity}",
    "effort": "low",
    "impact": "medium",
}
```

**Dispatch table candidate:** New detection heuristic in `design_smells.py`: functions with CC > 15 AND lines < 60 are likely long if/elif chains (high branching density = CC/lines ratio). Tag as type `"dispatch_table_candidate"`.

**Fix:** Add detection in `_analyze_function()` in `design_smells.py` and template in `recommendations.py`:
```python
{
    "finding_type": "dispatch_table_candidate",
    "category": "complexity",
    "title_template": "Replace conditionals in {entity} with dispatch table",
    "effort": "medium",
    "impact": "high",
}
```

**Smarter deduplication:** When 3+ recommendations target the same file, merge them into a single compound recommendation listing all issues. Replace the current `(file, line, category)` dedup with file-level grouping for same-category findings.

**Files:** `src/local_deepwiki/generators/analysis/recommendations.py`, `src/local_deepwiki/generators/analysis/design_smells.py`

**Acceptance criteria:**
- Data clump findings produce "Extract shared parameters" recommendations
- Functions with CC > 15 and < 60 lines produce "Replace conditionals with dispatch table" recommendations
- Multiple same-file recommendations are grouped into compound entries
- `handle_api_status_error` (CC 23, 51 lines) is flagged as dispatch table candidate

#### 1.3 Reduce Composite/Drill-Down Overlap

**Problem:** `analyze_architecture` and `get_architecture_health` run identical internal analyses. Individual tools repeat the same hotspots/smells data.

**Fix:** Add a `next_steps` field to `get_architecture_health` output — a list of 3-5 suggested drill-down tool calls based on findings. Example:
```json
{
  "next_steps": [
    {"tool": "get_module_health", "args": {"module_name": "generators.wiki"}, "reason": "Lowest scoring module (F, 35/100)"},
    {"tool": "get_hotspots", "args": {"metric": "params"}, "reason": "60 long_parameter_list smells detected"},
    {"tool": "get_recommendations", "args": {"enrich": true}, "reason": "10 actionable refactoring opportunities"}
  ]
}
```

This guides agents toward the *unique* value of individual tools rather than having them re-request overlapping data.

**Files:** `src/local_deepwiki/generators/analysis/architecture_health.py`

**Acceptance criteria:**
- `get_architecture_health` includes `next_steps` in output
- Suggestions are dynamically generated based on actual findings (not hardcoded)
- Existing output structure is preserved (additive change)

---

### Phase 2: Parameter Objects

*Introduce dataclasses to consolidate repeated parameter groups. Fixes ~30 medium-severity `long_parameter_list` smells and improves coupling abstractness.*

#### 2.1 WikiGenerationContext

The existing `_GenerationContext` in `generators/wiki/generator.py` is internal and incomplete. Functions in `phases.py`, `postprocessing.py`, and `codemap_pages.py` still accept `ctx`, `index_status`, `progress_callback` as separate parameters.

**Change:** Promote `_GenerationContext` to a public dataclass in `generators/wiki/models.py` (new file). Add `index_status` and `progress_callback` as fields. Refactor all wiki generation functions to accept the context object.

**Impact:** Fixes ~12 `long_parameter_list` smells. Functions like `generate_wiki` (11 params), `run_plugin_generators` (11 params), `generate_freshness_and_finalize` (9 params) drop to 2-4 params each.

**Files:**
- `generators/wiki/models.py` (new)
- `generators/wiki/generator.py`
- `generators/wiki/phases.py`
- `generators/wiki/postprocessing.py`
- `generators/wiki/codemap_pages.py`
- `generators/wiki/plugin_runner.py`

**Acceptance criteria:**
- No wiki generation function has more than 6 parameters
- `_GenerationContext` is a frozen dataclass with all fields that were previously passed individually
- All existing wiki generation tests pass
- Backward compatibility: if any external code references the old parameter signatures, provide clear deprecation

#### 2.2 SearchRequest and VectorStoreConfig

The vectorstore search pipeline passes 10-13 parameters through 3-4 layers.

**Change:** Introduce two dataclasses in `core/vectorstore/models.py` (new file):

`SearchRequest`: `query`, `top_k`, `file_filter`, `language_filter`, `entity_type`, `reranking`, `min_score`, `search_mode`, plus optional pagination fields.

`VectorStoreConfig`: `repo_path`, `db_path`, `embedding_provider`, `embedding_model`, `batch_size`, `enable_cache`, plus other construction parameters.

Refactor the search pipeline to accept `SearchRequest` and the constructor to accept `VectorStoreConfig`.

**Impact:** Fixes ~12 `long_parameter_list` smells in `core/vectorstore/`.

**Files:**
- `core/vectorstore/models.py` (new)
- `core/vectorstore/search_engine.py`
- `core/vectorstore/search_pipeline.py`
- `core/vectorstore/mixins/search.py`
- `core/vectorstore/store.py`
- `core/vectorstore/embedding.py`

**Acceptance criteria:**
- No vectorstore function has more than 6 parameters
- `SearchRequest` is a frozen dataclass
- `VectorStoreConfig` is a frozen dataclass
- All existing vectorstore tests pass

#### 2.3 Other Parameter Objects

**`ResearchConfig`** for `DeepResearchPipeline.__init__` (13 params):
- File: `core/deep_research/pipeline.py`
- Add to existing `core/deep_research/models.py` if it exists, otherwise create

**`ImpactAnalysisRequest`** for `impact_analysis` (12 params):
- File: `services/analysis_service.py`

**Impact:** Fixes ~6 more `long_parameter_list` smells.

**Acceptance criteria:**
- No constructor or service function has more than 6 parameters
- All existing tests pass

#### 2.4 Phase 2 Score Impact

~30 `long_parameter_list` smells fixed (medium severity, weight 1). Weighted count: ~358 -> ~328. Density: 4.31/1K. Smells score: **~65.5** (up from 62.4, +3.1).

Coupling abstractness improves from ~8-10 new dataclasses. Exact coupling impact measured after Phase 1 bug fix.

---

### Phase 3: Hotspot Surgery

*Decompose all 50 functions with CC > 15. Highest-leverage phase — each fix reduces both a high-severity long_method smell (weight 3) AND lowers the complexity score.*

#### 3.1 Refactoring Patterns

Three patterns cover the majority:

**Dispatch table** (CC 20+ with < 60 lines — high branching density):
| Function | File | CC | Lines |
|----------|------|----|-------|
| `handle_api_status_error` | `providers/errors.py:202` | 23 | 51 |
| `camel_to_spaced` | `generators/crosslinks.py:30` | 22 | 36 |
| `validate_model` | `providers/llm/openai.py:127` | 21 | 79 |
| `_pom_parse_dependencies` | `generators/manifest_parsers.py:274` | 21 | 16 |

**Extract method** (CC 16-23 with > 80 lines — doing too many things):
| Function | File | CC | Lines |
|----------|------|----|-------|
| `generate_dependencies_page` | `generators/wiki/pages.py:525` | 23 | 126 |
| `generate_codemap_pages` | `generators/wiki/codemap_pages.py:159` | 22 | 136 |
| `generate_file_docs` | `generators/wiki/files.py:577` | 22 | 116 |
| `answer_question` | `services/query_service.py:46` | 22 | 137 |
| `_build_dependency_graph` | `generators/analysis/dependency_graph.py:589` | 21 | 85 |
| `_analyze_file` | `generators/analysis/design_smells.py:418` | 21 | 94 |
| `handle_batch_explain_entities` | `handlers/agentic.py:212` | 21 | 128 |
| `generate_overview_page` | `generators/wiki/pages.py:209` | 18 | 81 |
| `_extract_names_from_table` | `core/fuzzy_search.py:345` | 18 | 52 |
| `research` | `core/deep_research/pipeline.py:327` | 16 | 80 |
| `generate_file_graph` | `generators/analysis/dependency_graph.py:493` | 16 | 80 |
| And ~20 more in the CC 16-19 range | | | |

**State machine / early return** (complex parsing or traversal logic):
| Function | File | CC | Lines |
|----------|------|----|-------|
| `parse_doctest_examples` | `generators/examples/docstring.py:34` | 23 | 98 |
| `_create_file_summary_chunk` | `core/chunker.py:495` | 19 | 78 |
| `_extract_names_from_table` | `core/fuzzy_search.py:345` | 18 | 52 |
| `build_source_url` | `core/git_utils.py:307` | 18 | 42 |
| `get_directory_tree` | `generators/dir_tree.py:58` | 20 | 93 |

#### 3.2 Execution Order

Group by module to minimize context switching:

1. **`generators/wiki/`** — 12 functions (pages.py, files.py, codemap_pages.py, modules.py, pipeline.py, plugin_runner.py)
2. **`core/`** — 10 functions (chunker.py, fuzzy_search.py, git_utils.py, indexer.py, deep_research/pipeline.py, vectorstore/search_engine.py)
3. **`generators/analysis/`** — 8 functions (dependency_graph.py, design_smells.py, architecture_compare.py, coupling.py, architecture_health.py)
4. **`generators/` other** — 8 functions (crosslinks.py, dir_tree.py, search.py, codemap/generator.py, examples/docstring.py, manifest_parsers.py)
5. **`providers/`** — 3 functions (errors.py, llm/openai.py)
6. **`handlers/`** — 3 functions (agentic.py)
7. **`services/`** — 2 functions (query_service.py, analysis_service.py)
8. **`cli/`** — 4 functions (check_cli.py, config/loader.py)

#### 3.3 Acceptance Criteria

- No function in the codebase has CC > 15
- All extracted helpers are private (underscore-prefixed) unless they have independent utility
- No behavioral changes — extracted functions preserve exact same logic
- All existing tests pass after each module group
- Each module group is a separate commit for easy bisection

#### 3.4 Phase 3 Score Impact

- **Complexity:** max_cc <= 15, pct = 0% -> penalty = 0 -> score = **100** (up from 78.1)
- **Smells:** ~50 high-severity `long_method` smells resolved. Weighted count: ~178 (from ~328). Density: 2.34/1K. Score = **81.3** (up from ~65.5)

Running total after Phases 2+3:
- Complexity: 100 x 0.30 = 30.0
- Coupling: 69.9 x 0.25 = 17.475 (not yet improved)
- Smells: 81.3 x 0.25 = 20.325
- Layers: 100 x 0.20 = 20.0
- **Total: 87.8** (up from 76.5, still B but close)

---

### Phase 4: Coupling Push + Remaining Smells

*Close the gap from 87.8 to 90+. Two-pronged: improve coupling score and fix remaining long methods.*

#### 4.1 Coupling Improvement (target: 69.9 -> ~80)

Current penalties: avg_distance=0.42 (-21), unstable_pct=4.6% (-9.2).

**Re-measure after Phase 1 bug fix** to get accurate module-level data. Then:

**Reduce avg_distance (target: 0.42 -> 0.30):**
- Phase 2 parameter objects add ~8-10 new dataclasses, increasing abstractness in `core/vectorstore/`, `generators/wiki/`, `core/deep_research/`, and `services/`. This should reduce distance for those modules.
- Where modules still show high distance, add Protocol/ABC interfaces for the most-depended-on modules. Candidates: `core/vectorstore` (184 inbound), `providers/llm` (152 inbound), `models` (128 inbound).

**Reduce unstable modules (target: 18 -> ~10):**
- For each highly unstable module (I > 0.8, Ce > 5), evaluate: (a) reduce outbound imports by consolidating shared dependencies, or (b) determine if the module is correctly unstable (CLI entry points, test utilities) and should be excluded from the metric.
- If test/CLI modules inflate the unstable count, evaluate whether the coupling scorer should exclude known-unstable-by-design modules (with an opt-in flag, not silently).

**Estimated impact:** avg_distance 0.42 -> 0.30 saves 6 penalty points. unstable_pct 4.6% -> 2.5% saves 4.2 penalty points. Score: **~80** (up from 69.9).

**Files:** Determined after re-measurement. Likely: `core/vectorstore/__init__.py`, `providers/llm/base.py`, possibly `generators/analysis/coupling.py` if test exclusion is warranted.

**Acceptance criteria:**
- Coupling score reaches 78+ (verified by `get_architecture_health`)
- Any scoring changes (like test module exclusion) are opt-in, not default behavior changes
- No artificial abstractness (don't add ABCs that serve no design purpose)

#### 4.2 Remaining Long Methods (target: smells 81.3 -> ~86)

After Phase 3, ~41 high-severity `long_method` smells remain — functions that are long (>80 lines) but not complex (CC <= 15). These are sequential pipelines: lots of steps, low branching.

Fix the top ~15 by line count using extract-method. These are long but not complex — sequential pipelines that split cleanly:

| Function | File | Lines | CC |
|----------|------|-------|----|
| `run_generation_pipeline` | `wiki/pipeline.py:376` | 128 | 3 |
| `search_from_request` | `core/vectorstore/search_engine.py:505` | 121 | 15 |
| `batch_embed` | `core/vectorstore/embedding.py:298` | 112 | 10 |
| `compare_architecture` | `generators/analysis/architecture_compare.py:227` | 109 | 13 |
| `Indexer.index` | `core/indexer.py:362` | 106 | 12 |
| `search_paginated` | `core/vectorstore/search_engine.py:183` | 105 | 8 |
| `generate_single_file_doc` | `wiki/files.py:388` | 102 | 9 |
| `VectorStore.__init__` | `vectorstore/store.py:69` | 91 | 5 |
| `analyze_architecture_health` | `analysis/architecture_health.py:35` | 90 | 4 |
| `parse_files_parallel` | `core/parsing_pipeline.py:93` | 90 | 6 |
| `generate_single_module_doc` | `wiki/modules.py:203` | 86 | 4 |
| `Indexer.__init__` | `core/indexer.py:52` | 86 | 9 |
| `analyze_coupling_metrics` | `analysis/coupling.py:122` | 83 | 8 |
| `run_plugin_generators` | `wiki/plugin_runner.py:113` | 83 | 6 |
| `sort_generators_by_dependencies` | `wiki/plugin_runner.py:29` | 82 | 13 |

**Note:** All of these have CC <= 15, so they don't affect the complexity score — they only affect the smells score via `long_method` detection.

**Estimated impact:** 15 fewer high-severity smells. Weighted count: ~133 (from ~178). Density: 1.75/1K. Score = **~86** (up from 81.3).

**Acceptance criteria:**
- No function exceeds 80 lines except where decomposition would harm readability (document exceptions)
- All existing tests pass

#### 4.3 Projected Final Score

| Dimension | Start | After Ph 1-3 | After Ph 4 | Weighted |
|-----------|-------|-------------|------------|----------|
| Complexity | 78.1 | 100 | 100 | 30.0 |
| Coupling | 69.9 | 69.9 | ~80 | 20.0 |
| Smells | 62.4 | 81.3 | ~86 | 21.5 |
| Layers | 100.0 | 100 | 100 | 20.0 |
| **Overall** | **76.5** | **87.8** | **~91.5 (A)** | |

---

## Implementation Phases

| Phase | Items | Dependencies | Estimated Scope |
|-------|-------|-------------|-----------------|
| **Phase 1** | 1.1 Coupling bug fix, 1.2 Recommendation types, 1.3 Next-steps guidance | None | 3 files changed, ~100 lines |
| **Phase 2** | 2.1 WikiGenerationContext, 2.2 SearchRequest/VectorStoreConfig, 2.3 Other param objects | Phase 1 (for accurate measurement) | ~15 files changed, 3 new model files |
| **Phase 3** | 3.1-3.2 Decompose 50 CC>15 functions | Phase 2 (param objects reduce some CC) | ~40 files changed, 8 commit groups |
| **Phase 4** | 4.1 Coupling push, 4.2 Remaining long methods | Phases 1-3 | ~15-20 files, scope refined by measurement |

## Testing Strategy

- **After each phase:** Run full test suite (`uv run pytest tests/ -v`), verify health grade improvement with `deepwiki check`
- **Phase 1:** Add tests for coupling bug fix (mock full graph, verify Ca > 0), recommendation type coverage, next_steps generation
- **Phase 2:** Update existing tests that mock function signatures. Add tests for new dataclass construction and immutability.
- **Phase 3:** Each module group committed separately. Run targeted test files after each group. No behavioral changes means existing tests should pass unmodified (only mock targets may need updating if function signatures change).
- **Phase 4:** Verify final health grade with `get_architecture_health`. Run full suite.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Parameter objects break existing callers | Frozen dataclasses with defaults; update all internal callers in same commit |
| Method extraction changes behavior | Extract-only refactoring: new private helpers called from original function body |
| Coupling improvements don't reach target | Phase 4 is measurement-driven; re-assess after Phases 2-3 side effects |
| 50 CC>15 functions is a lot of refactoring | Grouped by module (8 groups); each group is independently testable and committable |
| Scoring model rewards artificial abstraction | Only add ABCs/Protocols where they serve a design purpose; document any exceptions |
| Phase 3 introduces regressions in wiki generation | Wiki generation has extensive test coverage; run wiki generation integration tests after each group |
