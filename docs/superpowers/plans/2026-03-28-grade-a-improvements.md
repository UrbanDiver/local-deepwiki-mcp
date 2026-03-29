# Grade A Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move architecture health grade from B (76.5) to A (90+) by fixing MCP tool measurement gaps, introducing parameter objects, and decomposing all CC > 15 functions.

**Architecture:** Fix-Measure-Fix loop. Phase 1 fixes MCP tools for accurate measurement. Phase 2 introduces parameter objects to reduce smell density. Phase 3 decomposes 50 complexity hotspots. Phase 4 pushes coupling score and fixes remaining long methods.

**Tech Stack:** Python 3.11+, tree-sitter AST analysis, frozen dataclasses, pytest

**Spec:** `docs/superpowers/specs/2026-03-28-grade-a-improvements-design.md`

---

## Pre-Existing Context

Two context objects already exist and are partially adopted:
- **`WikiPipelineContext`** in `src/local_deepwiki/generators/wiki/context.py` — frozen dataclass with 12 fields (index_status, vector_store, llm, etc.). Used by `postprocessing.py`, `codemap_pages.py`, `pages.py`, `modules.py`. NOT used by `phases.py` functions which still take `(ctx: _GenerationContext, generator: WikiGenerator, index_status, progress_callback)`.
- **`SearchRequest`** in `src/local_deepwiki/core/vectorstore/mixins/search_types.py` — frozen dataclass with 11 fields. Used by `search_engine.py`'s `search_from_request()`. NOT used by the public `search()` (13 params) or `search_paginated()` (12 params) which still take individual args.

The `_GenerationContext` in `generator.py` tracks **mutable state** (pages list, counters, warnings) and is separate from `WikiPipelineContext` (immutable config/resources). Both will remain; Phase 2 makes `phases.py` use `WikiPipelineContext` directly instead of receiving its fields as separate params.

---

## Phase 1: Sharpen the Tools

### Task 1: Fix Module-Level Coupling Measurement

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/module_health.py:53`
- Test: `tests/test_module_health.py`

- [ ] **Step 1: Write failing test for non-zero afferent coupling**

Add to `tests/test_module_health.py`:

```python
def test_analyze_module_health_coupling_reflects_inbound_imports(module_repo):
    """Module with known inbound imports should show non-zero Ca."""
    # module_repo has core/ importing from web/ — core.module_a is imported by web.
    result = analyze_module_health(module_repo, "core")
    coupling = result["coupling"]
    # With the full graph, core should have afferent coupling > 0
    # because web/ imports from core/.
    assert coupling["afferent_coupling"] > 0 or coupling["efferent_coupling"] > 0, (
        "Module-level coupling should reflect cross-module imports, "
        f"got Ca={coupling['afferent_coupling']}, Ce={coupling['efferent_coupling']}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_module_health.py::test_analyze_module_health_coupling_reflects_inbound_imports -v`

Expected: FAIL — coupling shows 0/0 due to the `module_filter` bug.

- [ ] **Step 3: Fix the coupling call in module_health.py**

In `src/local_deepwiki/generators/analysis/module_health.py`, change line 53 from:

```python
    coupling_result = analyze_coupling_metrics(repo_path, module_filter=module_name)
```

to:

```python
    coupling_result = analyze_coupling_metrics(repo_path)
```

This runs the full dependency graph so all inbound/outbound edges are discovered. The existing filter on lines 74-78 already extracts the specific module's metrics from the result set.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_module_health.py -v`

Expected: All 16 existing tests + 1 new test PASS.

- [ ] **Step 5: Verify with MCP tool**

Run: `uv run python -c "from pathlib import Path; from local_deepwiki.generators.analysis.module_health import analyze_module_health; r = analyze_module_health(Path('.'), 'core.vectorstore'); print(f'Ca={r[\"coupling\"][\"afferent_coupling\"]}, Ce={r[\"coupling\"][\"efferent_coupling\"]}')"`

Expected: Non-zero Ca value.

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/generators/analysis/module_health.py tests/test_module_health.py
git commit -m "fix: remove module_filter from coupling call in module_health

The module_filter parameter restricted both source and target scanning,
causing afferent coupling to always read 0. Running the full graph and
extracting the target module's metrics gives correct Ca/Ce values."
```

---

### Task 2: Add Missing Recommendation Types

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/design_smells.py:481-496`
- Modify: `src/local_deepwiki/generators/analysis/recommendations.py:28-74, 205-216`
- Test: `tests/test_design_smells.py`
- Test: `tests/test_recommendations.py`

#### 2a: Data clump template

- [ ] **Step 1: Write failing test for data clump recommendation**

Add to `tests/test_recommendations.py`:

```python
def test_recommendations_from_data_clump():
    """Data clump findings should produce parameter object recommendations."""
    health_data = _make_health_data()
    health_data["top_findings"]["high_severity_smells"].append(
        {
            "type": "data_clump",
            "severity": "low",
            "file": "src/generators/wiki/generator.py",
            "line": 1,
            "entity": "func_a, func_b, func_c",
            "description": "3 functions share parameters: x, y, z",
        }
    )
    result = generate_recommendations(Path("/fake"), health_data=health_data)
    titles = [r["title"] for r in result["recommendations"]]
    assert any("parameter object" in t.lower() for t in titles), (
        f"Expected a parameter object recommendation, got: {titles}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_recommendations.py::test_recommendations_from_data_clump -v`

Expected: FAIL — no template matches `data_clump`.

- [ ] **Step 3: Add data clump template to recommendations.py**

In `src/local_deepwiki/generators/analysis/recommendations.py`, add to the `_TEMPLATES` list after the `deep_nesting` entry (after line 70):

```python
    {
        "finding_type": "data_clump",
        "category": "smells",
        "title_template": "Extract shared parameters into a parameter object for {entity}",
        "effort": "low",
        "impact": "medium",
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_recommendations.py::test_recommendations_from_data_clump -v`

Expected: PASS.

#### 2b: Dispatch table candidate detection

- [ ] **Step 5: Write failing test for dispatch table detection**

Add to `tests/test_design_smells.py`:

```python
def test_detects_dispatch_table_candidate(tmp_path):
    """Function with high CC but low line count should be flagged as dispatch candidate."""
    # Create a file with a short function that has many if/elif branches
    code = '''
def handle_status(code: int) -> str:
    if code == 200:
        return "ok"
    elif code == 201:
        return "created"
    elif code == 204:
        return "no content"
    elif code == 301:
        return "moved"
    elif code == 302:
        return "found"
    elif code == 400:
        return "bad request"
    elif code == 401:
        return "unauthorized"
    elif code == 403:
        return "forbidden"
    elif code == 404:
        return "not found"
    elif code == 405:
        return "method not allowed"
    elif code == 408:
        return "timeout"
    elif code == 409:
        return "conflict"
    elif code == 422:
        return "unprocessable"
    elif code == 429:
        return "rate limited"
    elif code == 500:
        return "server error"
    elif code == 502:
        return "bad gateway"
    elif code == 503:
        return "unavailable"
    else:
        return "unknown"
'''
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "handler.py").write_text(code)
    result = analyze_design_smells(tmp_path, severity_threshold="medium")
    smell_types = [s["type"] for s in result["smells"]]
    assert "dispatch_table_candidate" in smell_types, (
        f"Expected dispatch_table_candidate smell, got types: {smell_types}"
    )
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_design_smells.py::test_detects_dispatch_table_candidate -v`

Expected: FAIL — no detector for `dispatch_table_candidate`.

- [ ] **Step 7: Add dispatch table detection to design_smells.py**

In `src/local_deepwiki/generators/analysis/design_smells.py`, add a new constant near the other thresholds (around line 100):

```python
_DISPATCH_TABLE_CC_THRESHOLD = 15
_DISPATCH_TABLE_MAX_LINES = 60
```

Add the detector function before `_analyze_file`:

```python
def _detect_dispatch_table_candidate(
    func_node: Any,
    func_name: str,
    rel_path: Path,
    threshold_level: int,
) -> dict[str, Any] | None:
    """Flag functions with high CC but low line count as dispatch table candidates.

    High branching density (CC/lines) suggests a long if/elif chain that could
    be replaced with a dictionary dispatch table.
    """
    if _SEVERITY_ORDER[SEVERITY_MEDIUM] < threshold_level:
        return None
    func_lines = func_node.end_point[0] - func_node.start_point[0] + 1
    cyclomatic = _estimate_cyclomatic(func_node)
    if (
        cyclomatic > _DISPATCH_TABLE_CC_THRESHOLD
        and func_lines < _DISPATCH_TABLE_MAX_LINES
    ):
        return {
            "type": "dispatch_table_candidate",
            "severity": SEVERITY_MEDIUM,
            "file": str(rel_path),
            "line": func_node.start_point[0] + 1,
            "entity": func_name,
            "description": (
                f"Function has cyclomatic complexity {cyclomatic} in only "
                f"{func_lines} lines (high branching density suggests "
                f"an if/elif chain)"
            ),
            "suggestion": (
                "Replace conditional chain with a dictionary dispatch table "
                "or mapping."
            ),
        }
    return None
```

Then in the `_walk_root` function inside `_analyze_file`, add the call after the feature_envy detection (after line 496):

```python
            smell = _detect_dispatch_table_candidate(
                node, func_name, rel_path, threshold_level
            )
            if smell:
                smells.append(smell)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_design_smells.py::test_detects_dispatch_table_candidate -v`

Expected: PASS.

- [ ] **Step 9: Add dispatch table template to recommendations.py**

Add to the `_TEMPLATES` list in `recommendations.py`:

```python
    {
        "finding_type": "dispatch_table_candidate",
        "category": "complexity",
        "title_template": "Replace conditionals in {entity} with dispatch table",
        "effort": "medium",
        "impact": "high",
    },
```

#### 2c: Smarter deduplication

- [ ] **Step 10: Write failing test for file-level grouping**

Add to `tests/test_recommendations.py`:

```python
def test_recommendations_groups_same_file_same_category():
    """Multiple same-file same-category findings should merge into one compound entry."""
    health_data = _make_health_data()
    # Add 3 long_method smells in the same file
    for i, name in enumerate(["func_a", "func_b", "func_c"]):
        health_data["top_findings"]["high_severity_smells"].append(
            {
                "type": "long_method",
                "severity": "high",
                "file": "src/big_module.py",
                "line": 10 + i * 50,
                "entity": name,
                "description": f"Function has 100 lines",
            }
        )
    result = generate_recommendations(Path("/fake"), health_data=health_data)
    big_module_recs = [
        r for r in result["recommendations"] if r["file"] == "src/big_module.py"
    ]
    # Should be grouped into fewer entries than the 3 individual smells
    assert len(big_module_recs) < 3, (
        f"Expected grouped recommendations, got {len(big_module_recs)} separate entries"
    )
```

- [ ] **Step 11: Run test to verify it fails**

Run: `uv run pytest tests/test_recommendations.py::test_recommendations_groups_same_file_same_category -v`

Expected: FAIL — current dedup keeps all 3 (different line numbers).

- [ ] **Step 12: Implement file-level grouping in recommendations.py**

Replace the `_deduplicate` function in `src/local_deepwiki/generators/analysis/recommendations.py`:

```python
def _deduplicate(
    recs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicates and group related recommendations.

    1. Exact dedup by (file, line, category).
    2. When 3+ recommendations target the same (file, category), merge into
       a single compound entry listing all entities.
    """
    # Pass 1: exact dedup
    seen: set[tuple[str, int, str]] = set()
    unique: list[dict[str, Any]] = []
    for rec in recs:
        key = (rec["file"], rec["line"], rec["category"])
        if key not in seen:
            seen.add(key)
            unique.append(rec)

    # Pass 2: group by (file, category) when 3+ entries
    from collections import defaultdict

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    ungroupable: list[dict[str, Any]] = []

    for rec in unique:
        file_path = rec.get("file", "")
        if file_path:
            groups[(file_path, rec["category"])].append(rec)
        else:
            ungroupable.append(rec)

    result: list[dict[str, Any]] = list(ungroupable)
    for (_file, _cat), group in groups.items():
        if len(group) >= 3:
            entities = [r.get("title", "") for r in group]
            best = max(group, key=lambda r: r["priority"])
            result.append(
                {
                    **best,
                    "title": f"Refactor {_file} ({len(group)} issues)",
                    "description": "; ".join(entities),
                }
            )
        else:
            result.extend(group)

    return result
```

- [ ] **Step 13: Run all recommendation tests**

Run: `uv run pytest tests/test_recommendations.py -v`

Expected: All tests PASS (including existing dedup test — verify it still works).

- [ ] **Step 14: Run all design smells tests**

Run: `uv run pytest tests/test_design_smells.py -v`

Expected: All 20 existing + 1 new test PASS.

- [ ] **Step 15: Commit**

```bash
git add src/local_deepwiki/generators/analysis/design_smells.py src/local_deepwiki/generators/analysis/recommendations.py tests/test_design_smells.py tests/test_recommendations.py
git commit -m "feat: add data clump and dispatch table recommendation types

- Wire data_clump smell type to 'extract parameter object' template
- Add dispatch_table_candidate detection (CC > 15, lines < 60)
- Group 3+ same-file same-category recommendations into compound entries"
```

---

### Task 3: Add next_steps to Architecture Health Output

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/architecture_health.py:105-124`
- Test: `tests/test_architecture_health.py`

- [ ] **Step 1: Write failing test for next_steps field**

Add to `tests/test_architecture_health.py`:

```python
def test_analyze_architecture_health_includes_next_steps(simple_repo):
    """Health output should include dynamically generated next_steps."""
    result = analyze_architecture_health(simple_repo, "test-project")
    assert "next_steps" in result, "Expected next_steps field in health output"
    steps = result["next_steps"]
    assert isinstance(steps, list)
    # Each step should have tool, args, and reason
    for step in steps:
        assert "tool" in step
        assert "args" in step
        assert "reason" in step
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_architecture_health.py::test_analyze_architecture_health_includes_next_steps -v`

Expected: FAIL — no `next_steps` key in output.

- [ ] **Step 3: Add next_steps generation to architecture_health.py**

Add a helper function before `analyze_architecture_health`:

```python
def _generate_next_steps(
    overall: dict[str, Any],
    top_findings: dict[str, Any],
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate suggested drill-down tool calls based on findings."""
    steps: list[dict[str, Any]] = []

    # Suggest module health for the worst dimension
    dimensions = overall.get("dimensions", {})
    worst_dim = min(dimensions, key=lambda d: dimensions[d].get("score", 100))
    worst_score = dimensions[worst_dim].get("score", 100)
    if worst_score < 75:
        if worst_dim == "smells":
            steps.append(
                {
                    "tool": "get_design_smells",
                    "args": {"severity_threshold": "high"},
                    "reason": f"Smells dimension scored {worst_score:.0f}/100",
                }
            )
        elif worst_dim == "coupling":
            steps.append(
                {
                    "tool": "get_coupling_metrics",
                    "args": {},
                    "reason": f"Coupling dimension scored {worst_score:.0f}/100",
                }
            )

    # Suggest hotspot drill-down if complexity hotspots found
    hotspot_count = len(top_findings.get("hotspots", []))
    if hotspot_count > 0:
        steps.append(
            {
                "tool": "get_hotspots",
                "args": {"metric": "complexity", "top_n": 20},
                "reason": f"{hotspot_count} complexity hotspots detected",
            }
        )

    # Suggest recommendations
    total_smells = stats.get("total_smells", 0)
    if total_smells > 10:
        steps.append(
            {
                "tool": "get_recommendations",
                "args": {"enrich": True},
                "reason": f"{total_smells} design smells found — get prioritized action items",
            }
        )

    # Suggest param hotspots if many smells
    if total_smells > 50:
        steps.append(
            {
                "tool": "get_hotspots",
                "args": {"metric": "params", "top_n": 10},
                "reason": "High smell count — check for parameter bloat",
            }
        )

    return steps[:5]  # Cap at 5 suggestions
```

Then in the return dict of `analyze_architecture_health` (line 105), add the `next_steps` field:

```python
    next_steps = _generate_next_steps(overall, top_findings_dict, stats_dict)
```

Where `top_findings_dict` and `stats_dict` are the dicts being built for the return value. Restructure the return to build the sub-dicts first:

Replace lines 105-124 with:

```python
    top_findings_dict = {
        "hotspots": top_hotspots,
        "high_severity_smells": top_smells_high,
        "god_classes": god_classes,
        "layer_violations": layer_result.get("violations", [])[:top_findings],
    }
    stats_dict = {
        "total_lines": total_lines,
        "total_functions": hotspot_result.get("stats", {}).get(
            "total_functions", 0
        ),
        "files_scanned": hotspot_result.get("stats", {}).get("files_scanned", 0),
        "total_modules": coupling_result.get("stats", {}).get("total_modules", 0),
        "total_smells": len(src_smells),
    }
    next_steps = _generate_next_steps(overall, top_findings_dict, stats_dict)

    return {
        "status": "success",
        "project_name": project_name,
        "overall": overall,
        "top_findings": top_findings_dict,
        "stats": stats_dict,
        "next_steps": next_steps,
    }
```

- [ ] **Step 4: Run all architecture health tests**

Run: `uv run pytest tests/test_architecture_health.py -v`

Expected: All 12 existing + 1 new test PASS.

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/architecture_health.py tests/test_architecture_health.py
git commit -m "feat: add next_steps guidance to architecture health output

Dynamically generates 3-5 suggested drill-down tool calls based on
findings, guiding agents toward unique value of individual tools."
```

- [ ] **Step 6: Run full test suite and record baseline health score**

```bash
uv run pytest tests/ -x -q
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.architecture_health import analyze_architecture_health
r = analyze_architecture_health(Path('.'), 'local-deepwiki')
o = r['overall']
print(f'Overall: {o[\"grade\"]} ({o[\"score\"]})')
for dim, data in o['dimensions'].items():
    print(f'  {dim}: {data[\"grade\"]} ({data[\"score\"]})')
"
```

Record the scores in the commit message for Phase 1 completion.

---

## Phase 2: Parameter Objects

### Task 4: Reduce phases.py Parameter Lists

The `phases.py` functions take `(ctx: _GenerationContext, generator: WikiGenerator, index_status: IndexStatus, progress_callback: ProgressCallback | None)` — four params where two are redundant. The `_GenerationContext` already tracks mutable state; add `index_status` and `progress_callback` to it so each phase function only needs `(ctx, generator)`.

Note: `WikiGenerator` does NOT have a `pipeline_ctx` attribute. `WikiPipelineContext` is used by `postprocessing.py`, `modules.py`, `pages.py`, and `codemap_pages.py` but NOT by `phases.py`. The simplest fix is to enrich `_GenerationContext` rather than bridge the two context systems.

**Files:**
- Modify: `src/local_deepwiki/generators/wiki/generator.py:82-111` — add fields to `_GenerationContext`
- Modify: `src/local_deepwiki/generators/wiki/phases.py` — update 4 function signatures
- Modify: `src/local_deepwiki/generators/wiki/generator.py` — update callers
- Test: existing wiki generation tests

- [ ] **Step 1: Add index_status and progress_callback to _GenerationContext**

In `src/local_deepwiki/generators/wiki/generator.py`, update the `_GenerationContext` class (line 82):

```python
class _GenerationContext:
    """Internal context for tracking wiki generation state."""

    __slots__ = (
        "pages",
        "pages_generated",
        "pages_skipped",
        "all_source_files",
        "full_rebuild",
        "warnings",
        "index_status",
        "progress_callback",
    )

    def __init__(
        self,
        pages: list["WikiPage"],
        pages_generated: int,
        pages_skipped: int,
        all_source_files: list[str],
        full_rebuild: bool,
        index_status: "IndexStatus | None" = None,
        progress_callback: "ProgressCallback | None" = None,
    ):
        self.pages = pages
        self.pages_generated = pages_generated
        self.pages_skipped = pages_skipped
        self.all_source_files = all_source_files
        self.full_rebuild = full_rebuild
        self.warnings: list[str] = []
        self.index_status = index_status
        self.progress_callback = progress_callback
```

- [ ] **Step 2: Update _GenerationContext construction sites to pass index_status and progress_callback**

Search for where `_GenerationContext(` is called in `generator.py` and add the new arguments. There should be 1-2 construction sites.

- [ ] **Step 3: Refactor phases.py function signatures**

Update the 4 main phase functions in `src/local_deepwiki/generators/wiki/phases.py`:

For `generate_summary_pages` (line 151), change from:
```python
async def generate_summary_pages(
    ctx: _GenerationContext,
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
```
to:
```python
async def generate_summary_pages(
    ctx: _GenerationContext,
    generator: WikiGenerator,
) -> None:
```

Inside the function body, replace `index_status` with `ctx.index_status` and `progress_callback` with `ctx.progress_callback`.

Apply the same pattern to:
- `generate_dependencies_page_phase` (line 207)
- `generate_changelog_phase` (line 268)
- `generate_auxiliary_pages` (line 532)

- [ ] **Step 4: Update callers in generator.py**

In `src/local_deepwiki/generators/wiki/generator.py`, update calls to the refactored phase functions to remove the `index_status` and `progress_callback` arguments.

- [ ] **Step 5: Run wiki generation tests**

Run: `uv run pytest tests/ -k "wiki" -x -q`

Expected: All wiki-related tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/generators/wiki/generator.py src/local_deepwiki/generators/wiki/phases.py
git commit -m "refactor: add index_status and progress_callback to _GenerationContext

Reduces phases.py function signatures from 4 params to 2 by storing
index_status and progress_callback on the generation context."
```

---

### Task 5: Extend SearchRequest Usage to Public API

The `SearchRequest` dataclass already exists. The `search_from_request()` method already accepts it. The public `search()` and `search_paginated()` methods need to delegate to it more directly, reducing their parameter lists.

**Files:**
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py` — simplify `search()` and `search_paginated()`
- Modify: `src/local_deepwiki/core/vectorstore/search_pipeline.py` — refactor `dispatch_search()` and pipelines
- Modify: `src/local_deepwiki/core/vectorstore/mixins/search.py` — same pattern
- Test: existing vectorstore tests

- [ ] **Step 1: Refactor dispatch_search to accept SearchRequest**

In `src/local_deepwiki/core/vectorstore/search_pipeline.py`, change `dispatch_search` (line 297) from 10 individual params to:

```python
def dispatch_search(
    request: SearchRequest,
    table: Any,
    query_embedding: list[float],
    filters: list[str],
    fetch_limit: int,
    min_similarity: float,
    bm25_weight: float,
    row_to_chunk: RowToChunk,
    lazy_index_manager: "LazyIndexManager",
) -> list[SearchResult]:
```

Note: The `mode` parameter was the first arg. It now comes from `request.search_mode`. But many of these params are computed/resolved values, not raw request fields. Only consolidate the params that come from user input; leave computed params as-is.

**Approach:** For search_pipeline.py, the functions accept pre-computed values (table, query_embedding, filters, fetch_limit) which aren't part of the SearchRequest. The real parameter bloat is in the _public_ `search()` and `search_paginated()` methods which accept raw user params and could accept a `SearchRequest` instead.

The SearchMixin.search() (line 275) already accepts `request: SearchRequest | None = None`. The fix is:
1. Make `SearchRequest` the primary input path
2. Keep individual params for backward compatibility but mark them as deprecated
3. Construct `SearchRequest` from individual params at the entry point

- [ ] **Step 2: Simplify SearchEngine.search() to delegate to SearchRequest**

In `src/local_deepwiki/core/vectorstore/search_engine.py`, the `search()` method (line 631) takes 13 params. Refactor to:

```python
async def search(
    self,
    query: str,
    limit: int = 10,
    *,
    request: SearchRequest | None = None,
    **kwargs: Any,
) -> list[SearchResult]:
    """Search for code chunks.

    Accepts either a ``SearchRequest`` object or individual keyword arguments.
    When ``request`` is provided, it takes precedence.
    """
    if request is None:
        request = SearchRequest(
            query=query,
            limit=limit,
            search_mode=kwargs.get("search_mode"),
            language=kwargs.get("language"),
            chunk_type=kwargs.get("chunk_type"),
            path_pattern=kwargs.get("path_pattern"),
            use_fuzzy=kwargs.get("use_fuzzy", False),
            fuzzy_weight=kwargs.get("fuzzy_weight", 0.3),
            profile=kwargs.get("profile"),
            min_similarity=kwargs.get("min_similarity"),
            auto_suggest=kwargs.get("auto_suggest", True),
        )
    return await self.search_from_request(request, store=kwargs.get("store"))
```

Apply the same pattern to `search_paginated()` (line 690).

- [ ] **Step 3: Run vectorstore tests**

Run: `uv run pytest tests/ -k "vectorstore or search" -x -q`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/local_deepwiki/core/vectorstore/search_engine.py src/local_deepwiki/core/vectorstore/mixins/search.py
git commit -m "refactor: make SearchRequest the primary search API input

search() and search_paginated() now accept SearchRequest directly.
Individual params kept for backward compat but delegate to SearchRequest."
```

---

### Task 6: Add ResearchConfig and ImpactAnalysisRequest

**Files:**
- Create: `src/local_deepwiki/core/deep_research/config.py`
- Modify: `src/local_deepwiki/core/deep_research/pipeline.py`
- Modify: `src/local_deepwiki/services/analysis_service.py`
- Test: existing deep_research and analysis_service tests

- [ ] **Step 1: Create ResearchConfig dataclass**

Create `src/local_deepwiki/core/deep_research/config.py`:

```python
"""Configuration dataclass for the deep research pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    """Immutable configuration for DeepResearchPipeline.

    Consolidates the 12 keyword arguments of ``__init__`` into a single object.
    """

    max_sub_questions: int = 4
    chunks_per_subquestion: int = 5
    max_total_chunks: int = 30
    max_follow_up_queries: int = 3
    synthesis_temperature: float = 0.5
    synthesis_max_tokens: int = 4096
    decomposition_prompt: str | None = None
    gap_analysis_prompt: str | None = None
    synthesis_prompt: str | None = None
    repo_path: Path | None = None
```

- [ ] **Step 2: Refactor DeepResearchPipeline.__init__ to accept ResearchConfig**

In `src/local_deepwiki/core/deep_research/pipeline.py`, change `__init__` (line 70) to:

```python
def __init__(
    self,
    vector_store: VectorStore,
    llm_provider: LLMProvider,
    *,
    config: ResearchConfig | None = None,
    **kwargs: Any,
) -> None:
```

Inside the method, use `config` fields if provided, else fall back to `kwargs` for backward compat:

```python
    if config is None:
        config = ResearchConfig(**{
            k: v for k, v in kwargs.items()
            if k in ResearchConfig.__dataclass_fields__
        })
    self.max_sub_questions = config.max_sub_questions
    # ... etc for all fields
```

- [ ] **Step 3: Run deep research tests**

Run: `uv run pytest tests/ -k "deep_research or research" -x -q`

Expected: All tests PASS.

- [ ] **Step 4: Create ImpactAnalysisRequest dataclass**

In `src/local_deepwiki/services/analysis_service.py`, add before the class definition:

```python
@dataclass(frozen=True, slots=True)
class ImpactAnalysisRequest:
    """Parameters for impact analysis."""

    file_path: str
    full_file: Path
    repo_path: Path
    index_status: Any
    wiki_path: Path
    vector_store: VectorStore | None
    entity_name: str | None = None
    include_reverse_calls: bool = True
    include_inheritance: bool = True
    include_dependents: bool = True
    include_wiki_pages: bool = True
```

Refactor `impact_analysis` (line 127) to accept `request: ImpactAnalysisRequest | None = None` with fallback to individual params for backward compat.

- [ ] **Step 5: Run analysis service tests**

Run: `uv run pytest tests/ -k "impact_analysis" -x -q`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/core/deep_research/config.py src/local_deepwiki/core/deep_research/pipeline.py src/local_deepwiki/services/analysis_service.py
git commit -m "refactor: introduce ResearchConfig and ImpactAnalysisRequest

Consolidates long parameter lists into frozen dataclasses.
Individual kwargs kept for backward compatibility."
```

- [ ] **Step 7: Measure health score after Phase 2**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.architecture_health import analyze_architecture_health
r = analyze_architecture_health(Path('.'), 'local-deepwiki')
o = r['overall']
print(f'Overall: {o[\"grade\"]} ({o[\"score\"]})')
for dim, data in o['dimensions'].items():
    print(f'  {dim}: {data[\"grade\"]} ({data[\"score\"]})')
"
```

Record the scores.

---

## Phase 3: Hotspot Surgery

### Task 7: Enumerate Current CC > 15 Functions

Before decomposing, get the authoritative list from the MCP tool since the function list in the spec may be stale.

- [ ] **Step 1: Generate the full hotspot list**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
r = analyze_hotspots(Path('.'), metric='complexity', top_n=100, exclude_tests=True, min_threshold=16)
for h in r['hotspots']:
    d = h['details']
    print(f'CC={d[\"cyclomatic\"]:2d}  lines={d[\"length\"]:3d}  {h[\"file\"]}:{h[\"line\"]}  {h[\"function\"]}')
print(f'Total: {len(r[\"hotspots\"])} functions with CC > 15')
"
```

- [ ] **Step 2: Save the list to a tracking file**

Save the output to `docs/superpowers/plans/2026-03-28-cc15-hotspots.txt` for reference during the refactoring.

- [ ] **Step 3: Commit the tracking file**

```bash
git add docs/superpowers/plans/2026-03-28-cc15-hotspots.txt
git commit -m "docs: snapshot CC > 15 hotspot list for Phase 3 tracking"
```

---

### Task 8: Refactor generators/wiki/ Functions (Group 1)

**Pattern:** For each function, apply the appropriate refactoring strategy:
- **Dispatch table:** Replace if/elif chains with dict mappings
- **Extract method:** Pull sequential blocks into private helper functions
- **State machine:** Extract per-state handlers

**Target functions** (enumerate from Task 7 output — these are the expected ones):
- `generate_dependencies_page` (CC 23, 126 lines) — extract method
- `generate_codemap_pages` (CC 22, 136 lines) — extract method
- `generate_file_docs` (CC 22, 116 lines) — extract method
- `generate_overview_page` (CC 18, 81 lines) — extract method
- `_build_component_diagram` (CC 19, 67 lines) — extract method
- `generate_architecture_page` (CC ~4, 92 lines) — extract method (long but low CC)
- Plus any others from Task 7 output in `generators/wiki/`

**Workflow per function:**

- [ ] **Step 1: Read the function and identify extraction points**

Read the full function. Identify 2-4 logical sections that can be extracted into private helpers.

- [ ] **Step 2: Extract helpers without changing behavior**

For each extraction:
1. Create a new private function with the extracted code
2. Replace the original code with a call to the new function
3. Ensure the same values are passed in and returned

Example for `generate_dependencies_page` in `pages.py:525`:

```python
# Before: one 126-line function
async def generate_dependencies_page(ctx, manifest, config):
    # ... 126 lines of mixed logic

# After: orchestrator + helpers
def _build_dependency_sections(manifest: ProjectManifest) -> str:
    """Build markdown sections from manifest dependencies."""
    # extracted code here

def _build_dependency_diagram(manifest: ProjectManifest) -> str:
    """Build Mermaid dependency diagram."""
    # extracted code here

async def generate_dependencies_page(ctx, manifest, config):
    sections = _build_dependency_sections(manifest)
    diagram = _build_dependency_diagram(manifest)
    # ... remaining orchestration
```

- [ ] **Step 3: Run wiki tests after each function**

Run: `uv run pytest tests/ -k "wiki" -x -q`

- [ ] **Step 4: Verify CC is below 15**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.complexity import get_file_complexity
r = get_file_complexity(Path('.'), 'src/local_deepwiki/generators/wiki/pages.py')
for f in r.get('functions', []):
    if f['cyclomatic_complexity'] > 15:
        print(f'STILL HIGH: {f[\"name\"]} CC={f[\"cyclomatic_complexity\"]}')
print('Done')
"
```

- [ ] **Step 5: Commit the group**

```bash
git commit -m "refactor: decompose CC > 15 functions in generators/wiki/

Extracted helpers from generate_dependencies_page, generate_codemap_pages,
generate_file_docs, generate_overview_page, _build_component_diagram.
All functions now below CC 15."
```

---

### Task 9: Refactor core/ Functions (Group 2)

**Target functions:**
- `_create_file_summary_chunk` in `chunker.py` (CC 19, 78 lines) — state machine
- `_extract_names_from_table` in `fuzzy_search.py` (CC 18, 52 lines) — state machine
- `build_source_url` in `git_utils.py` (CC 18, 42 lines) — dispatch table (URL schemes)
- `research` in `deep_research/pipeline.py` (CC 16, 80 lines) — extract method

**Follow the same workflow as Task 8:** Read, extract helpers, run tests, verify CC, commit.

```bash
git commit -m "refactor: decompose CC > 15 functions in core/

Extracted helpers from _create_file_summary_chunk, _extract_names_from_table,
build_source_url, and research pipeline. All functions now below CC 15."
```

---

### Task 10: Refactor generators/analysis/ Functions (Group 3)

**Target functions:**
- `_build_dependency_graph` in `dependency_graph.py` (CC 21, 85 lines) — extract method
- `_analyze_file` in `design_smells.py` (CC 21, 94 lines) — extract method
- `generate_file_graph` in `dependency_graph.py` (CC 16, 80 lines) — extract method
- `compare_architecture` in `architecture_compare.py` (CC 13, 109 lines) — extract method

**Follow the same workflow as Task 8.**

```bash
git commit -m "refactor: decompose CC > 15 functions in generators/analysis/

Extracted helpers from _build_dependency_graph, _analyze_file,
generate_file_graph, and compare_architecture. All functions now below CC 15."
```

---

### Task 11: Refactor generators/ Other Functions (Group 4)

**Target functions:**
- `parse_doctest_examples` in `examples/docstring.py` (CC 23, 98 lines) — state machine
- `camel_to_spaced` in `crosslinks.py` (CC 22, 36 lines) — dispatch table or simplify regex
- `_rank_functions_by_connections` in `codemap/generator.py` (CC 22, 48 lines) — extract method
- `get_directory_tree` in `dir_tree.py` (CC 20, 93 lines) — extract method
- `generate_entity_entries` in `search.py` (CC 20, 88 lines) — extract method
- `_pom_parse_dependencies` in `manifest_parsers.py` (CC 21, 16 lines) — dispatch table

**Follow the same workflow as Task 8.**

```bash
git commit -m "refactor: decompose CC > 15 functions in generators/

Extracted helpers from parse_doctest_examples, camel_to_spaced,
_rank_functions_by_connections, get_directory_tree, generate_entity_entries,
and _pom_parse_dependencies. All functions now below CC 15."
```

---

### Task 12: Refactor providers/, handlers/, services/, cli/ (Groups 5-8)

**Target functions:**
- `handle_api_status_error` in `providers/errors.py` (CC 23, 51 lines) — dispatch table
- `validate_model` in `providers/llm/openai.py` (CC 21, 79 lines) — dispatch table
- `handle_batch_explain_entities` in `handlers/agentic.py` (CC 21, 128 lines) — extract method
- `answer_question` in `services/query_service.py` (CC 22, 137 lines) — extract method
- `_format_rich_table` in `cli/check_cli.py` (CC 17, 73 lines) — extract method
- `run_check` in `cli/check_cli.py` (CC 16, 55 lines) — extract method
- `_validate_wiki_config` in `config/loader.py` (CC 16, 30 lines) — extract method
- `extract_python_parameter_types` in `core/chunk_extractors.py` (CC 16, 51 lines) — extract method

**Example dispatch table refactoring** for `handle_api_status_error`:

```python
# Before: long if/elif chain
def handle_api_status_error(status_code, response):
    if status_code == 400:
        ...
    elif status_code == 401:
        ...
    # ... 20+ branches

# After: dispatch table
_STATUS_HANDLERS: dict[int, Callable] = {
    400: _handle_bad_request,
    401: _handle_unauthorized,
    403: _handle_forbidden,
    404: _handle_not_found,
    # ...
}

def handle_api_status_error(status_code, response):
    handler = _STATUS_HANDLERS.get(status_code, _handle_unknown)
    return handler(response)
```

**Follow the same workflow as Task 8 for each group, then commit each group separately.**

- [ ] **Step 1: Refactor providers/ (errors.py, llm/openai.py)**

```bash
git commit -m "refactor: decompose CC > 15 functions in providers/

Replaced if/elif chains with dispatch tables in handle_api_status_error
and validate_model. Both functions now below CC 15."
```

- [ ] **Step 2: Refactor handlers/ (agentic.py)**

```bash
git commit -m "refactor: decompose CC > 15 functions in handlers/

Extracted helpers from handle_batch_explain_entities. Function now below CC 15."
```

- [ ] **Step 3: Refactor services/ (query_service.py)**

```bash
git commit -m "refactor: decompose CC > 15 functions in services/

Extracted helpers from answer_question. Function now below CC 15."
```

- [ ] **Step 4: Refactor cli/ and config/ (check_cli.py, loader.py, chunk_extractors.py)**

```bash
git commit -m "refactor: decompose CC > 15 functions in cli/ and config/

Extracted helpers from _format_rich_table, run_check, _validate_wiki_config,
and extract_python_parameter_types. All functions now below CC 15."
```

- [ ] **Step 5: Verify zero CC > 15 functions remain**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
r = analyze_hotspots(Path('.'), metric='complexity', top_n=10, exclude_tests=True, min_threshold=16)
remaining = len(r['hotspots'])
print(f'Functions with CC > 15: {remaining}')
assert remaining == 0, f'Still {remaining} functions with CC > 15!'
"
```

- [ ] **Step 6: Measure health score after Phase 3**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.architecture_health import analyze_architecture_health
r = analyze_architecture_health(Path('.'), 'local-deepwiki')
o = r['overall']
print(f'Overall: {o[\"grade\"]} ({o[\"score\"]})')
for dim, data in o['dimensions'].items():
    print(f'  {dim}: {data[\"grade\"]} ({data[\"score\"]})')
"
```

Expected: Complexity ~100, Smells improved. Overall in the high 80s.

---

## Phase 4: Coupling Push + Remaining Smells

### Task 13: Measure and Target Coupling Improvements

Phase 4 is measurement-driven. After Phases 1-3, re-measure coupling to see where we stand and identify specific targets.

- [ ] **Step 1: Get accurate coupling data**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
r = analyze_coupling_metrics(Path('.'))
stats = r['stats']
print(f'Avg instability: {stats[\"avg_instability\"]:.3f}')
print(f'Avg abstractness: {stats[\"avg_abstractness\"]:.4f}')
print()
# Show highly unstable production modules (not tests/CLI)
for m in r['metrics']:
    if m['instability'] > 0.8 and m['efferent_coupling'] > 5:
        if not m['module'].startswith('tests.'):
            print(f'  UNSTABLE: {m[\"module\"]} I={m[\"instability\"]:.2f} Ce={m[\"efferent_coupling\"]} D={m[\"distance\"]:.3f}')
"
```

- [ ] **Step 2: Identify where Protocols/ABCs would serve a real design purpose**

Check if the most-depended-on modules already have abstract base classes:

```bash
uv run python -c "
import ast, sys
from pathlib import Path
for mod in ['providers/base.py', 'providers/llm/base.py', 'providers/embeddings/base.py']:
    p = Path('src/local_deepwiki') / mod
    if p.exists():
        tree = ast.parse(p.read_text())
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        print(f'{mod}: {classes}')
"
```

- [ ] **Step 3: Add justified Protocols where missing**

Only add Protocols/ABCs that serve a real purpose (DI, contract definition, isinstance checks). Do NOT add artificial abstractions just to improve the score.

- [ ] **Step 4: Reduce Ce in highly unstable production modules**

For each unstable module identified in Step 1, look for:
- Imports that could be lazy (behind TYPE_CHECKING)
- Shared dependencies that could be consolidated into a common facade
- Circular or unnecessary cross-module imports

- [ ] **Step 5: Commit coupling improvements**

```bash
git commit -m "refactor: improve coupling metrics via justified abstractions

Added Protocol interfaces where they serve real design purposes.
Reduced efferent coupling in [list specific modules]."
```

---

### Task 14: Fix Remaining Long Methods (> 80 lines, CC <= 15)

- [ ] **Step 1: Get the list of remaining long methods**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.design_smells import analyze_design_smells
r = analyze_design_smells(Path('.'), severity_threshold='high', exclude_tests=True)
long_methods = [s for s in r['smells'] if s['type'] == 'long_method']
for s in sorted(long_methods, key=lambda x: -int(x['description'].split()[2])):
    print(f'{s[\"file\"]}:{s[\"line\"]}  {s[\"entity\"]}  {s[\"description\"]}')
print(f'Total remaining: {len(long_methods)}')
"
```

- [ ] **Step 2: Decompose the top 15 by line count**

Apply extract-method pattern to each. These are sequential pipelines (low CC, high line count) so they split cleanly into phase/step helpers.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -x -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: decompose remaining long methods (> 80 lines)

Extracted helpers from [list functions]. All production functions
now under 80 lines or documented as exceptions."
```

---

### Task 15: Final Verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 2: Measure final health score**

```bash
uv run python -c "
from pathlib import Path
from local_deepwiki.generators.analysis.architecture_health import analyze_architecture_health
r = analyze_architecture_health(Path('.'), 'local-deepwiki')
o = r['overall']
print(f'FINAL: {o[\"grade\"]} ({o[\"score\"]})')
for dim, data in o['dimensions'].items():
    print(f'  {dim}: {data[\"grade\"]} ({data[\"score\"]})')
print()
if o['score'] >= 90:
    print('TARGET ACHIEVED: Grade A!')
else:
    print(f'Gap to A: {90 - o[\"score\"]:.1f} points')
    # Show which dimensions need work
    for dim, data in o['dimensions'].items():
        if data['score'] < 85:
            print(f'  {dim} needs +{85 - data[\"score\"]:.1f} pts')
"
```

- [ ] **Step 3: Update CLAUDE.md**

Update the architecture tables in CLAUDE.md to reflect:
- New model files created (Phase 2)
- New recommendation types (Phase 1)
- Updated tool behavior (next_steps in health output)
- Any new constants or thresholds added

- [ ] **Step 4: Commit CLAUDE.md update**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Grade A improvements

Updated architecture tables, tool descriptions, and component lists
to reflect Phase 1-4 changes."
```
