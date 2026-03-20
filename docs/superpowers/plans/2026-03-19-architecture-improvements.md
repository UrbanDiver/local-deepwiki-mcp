# Architecture Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the local-deepwiki-mcp architecture health grade from C (60) toward B (70+) through wiki quality pages, MCP tool usability fixes, analysis accuracy improvements, and internal code quality refactoring.

**Architecture:** Four phases of improvements, each independently shippable. Phase 1 (quick wins) unblocks Phase 2 (wiki pages). Phase 3 (parameter objects) and Phase 4 (god class split, complexity reduction) are independent of Phases 1-2.

**Tech Stack:** Python 3.11+, asyncio, tree-sitter AST, LanceDB, FastMCP, Pydantic, pytest

---

## File Structure Overview

### Phase 1 — Analysis Accuracy & Tool Usability
- Modify: `src/local_deepwiki/generators/analysis/design_smells.py` (feature envy allowlist)
- Modify: `src/local_deepwiki/generators/analysis/architecture_health.py` (scoring recalibration)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (add `top_n`/`summary_only` params)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (handle new params)
- Test: `tests/test_design_smells.py`, `tests/test_architecture_health.py`, `tests/test_analysis_architecture.py`

### Phase 2 — Wiki Quality Pages
- Create: `src/local_deepwiki/generators/analysis/health_page.py`
- Create: `src/local_deepwiki/generators/analysis/hotspots_page.py`
- Create: `src/local_deepwiki/generators/analysis/smells_page.py`
- Create: `src/local_deepwiki/generators/analysis/coupling_page.py`
- Modify: `src/local_deepwiki/generators/wiki/phases.py` (register new aux pages)
- Test: `tests/test_health_page.py`, `tests/test_hotspots_page.py`, `tests/test_smells_page.py`, `tests/test_coupling_page.py`

### Phase 3 — Parameter Object Refactoring
- Create: `src/local_deepwiki/generators/wiki/context.py` (WikiPipelineContext dataclass)
- Modify: `src/local_deepwiki/generators/wiki/modules.py` (accept context object)
- Modify: `src/local_deepwiki/generators/wiki/pages.py` (accept context object)
- Modify: `src/local_deepwiki/generators/wiki/postprocessing.py` (accept context object)
- Modify: `src/local_deepwiki/generators/wiki/phases.py` (thread context through)
- Modify: `src/local_deepwiki/generators/wiki/generator.py` (construct context)
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py` (align `search_paginated` with `SearchRequest`)
- Test: existing test suites + new context tests

**Note on context objects:** `WikiPipelineContext` is a new *immutable config* object bundling parameters shared across page generators (llm, vector_store, index_status, etc.). It complements — not replaces — the existing `_GenerationContext`, which is a *mutable accumulator* for pipeline state (pages list, counters, warnings). They serve different purposes: `WikiPipelineContext` eliminates parameter lists; `_GenerationContext` tracks running state.

### Phase 4 — God Class Split & Complexity Reduction
- Create: `src/local_deepwiki/core/indexer_graph.py` (graph extraction concern)
- Create: `src/local_deepwiki/core/indexer_status.py` (state management concern)
- Modify: `src/local_deepwiki/core/indexer.py` (slim down to orchestrator)
- Modify: `src/local_deepwiki/generators/analysis/dependency_graph.py` (split `_render_module_graph`)
- Modify: `src/local_deepwiki/generators/analysis/callgraph.py` (split `_extract_generic_call`)
- Test: existing test suites for indexer + new module tests

---

## Phase 1: Analysis Accuracy & Tool Usability

### Task 1: Feature Envy False Positive Filtering

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/design_smells.py`
- Test: `tests/test_design_smells.py`

- [ ] **Step 1: Write failing test for allowlist filtering**

In `tests/test_design_smells.py`, add a test that verifies common utility objects are not flagged as feature envy:

```python
def test_feature_envy_ignores_common_utility_objects():
    """Functions calling logger/lines/parts repeatedly should not be flagged."""
    code = '''
def generate_page(data):
    logger.info("Starting generation")
    logger.debug("Processing %d items", len(data))
    logger.info("Building output")
    logger.warning("Slow generation detected")
    lines = []
    lines.append("# Title")
    lines.append("## Section")
    lines.append("Content here")
    lines.append("More content")
    return "\\n".join(lines)
'''
    smells = _analyze_code_for_smells(code, "test.py")
    feature_envy_smells = [s for s in smells if s["type"] == "feature_envy"]
    assert len(feature_envy_smells) == 0, (
        f"Expected no feature envy for logger/lines but got: {feature_envy_smells}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_design_smells.py::test_feature_envy_ignores_common_utility_objects -v`
Expected: FAIL — logger and lines calls currently trigger feature envy

- [ ] **Step 3: Add allowlist constant and filter logic**

In `design_smells.py`, add after the existing threshold constants (~line 47):

```python
_FEATURE_ENVY_IGNORED_OBJECTS: frozenset[str] = frozenset({
    "logger", "log",           # logging
    "lines", "parts", "result_lines", "sections",  # list accumulators
    "asyncio",                 # stdlib
    "re", "os", "sys", "json", "math",  # stdlib modules
    "errors", "smells", "warnings",     # collection accumulators
    "prompt_parts",            # prompt builders
})
```

In `_collect_attribute_calls()` (~line 181), extend the exclusion:

```python
if obj_name not in ("self", "cls", "super") and obj_name not in _FEATURE_ENVY_IGNORED_OBJECTS:
    objects.append(obj_name)
```

Note: Both object instances (`logger.info()`) and module-level calls (`asyncio.run()`) go through the same attribute-access AST path, so a single allowlist handles both. The allowlist is intentionally conservative — only patterns that are universally non-envious. Legitimate feature envy involving stdlib (e.g., a function that does 10 `json.loads`/`json.dumps` calls) is rare enough to accept as a false negative.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_design_smells.py -v`
Expected: ALL PASS including new test

- [ ] **Step 5: Run full smell analysis to verify reduced false positives**

Run: `uv run pytest tests/test_design_smells.py -v -k feature_envy`
Verify: no regressions in existing feature envy tests

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/generators/analysis/design_smells.py tests/test_design_smells.py
git commit -m "fix: add allowlist to filter feature envy false positives for logger/lines/stdlib"
```

---

### Task 2: MCP Tool Overflow Handling

**Files:**
- Modify: `src/local_deepwiki/tool_defs/analysis.py`
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py`
- Test: `tests/test_analysis_architecture.py`

- [ ] **Step 1: Write failing tests for new parameters**

```python
def test_get_design_smells_top_n_limits_results():
    """top_n parameter should limit total smells returned."""
    result = await handle_get_design_smells({
        "repo_path": str(repo_path),
        "top_n": 5,
    })
    data = json.loads(result[0].text)
    assert len(data["smells"]) <= 5

def test_get_design_smells_summary_only():
    """summary_only should return counts by type without individual smells."""
    result = await handle_get_design_smells({
        "repo_path": str(repo_path),
        "summary_only": True,
    })
    data = json.loads(result[0].text)
    assert "smells_by_type" in data
    assert "smells" not in data

def test_get_coupling_metrics_top_n():
    """top_n should limit modules returned."""
    result = await handle_get_coupling_metrics({
        "repo_path": str(repo_path),
        "top_n": 10,
    })
    data = json.loads(result[0].text)
    assert len(data["modules"]) <= 10

def test_get_cross_module_dependencies_top_n():
    """top_n should limit nodes returned."""
    result = await handle_get_cross_module_dependencies({
        "repo_path": str(repo_path),
        "top_n": 20,
    })
    data = json.loads(result[0].text)
    assert len(data["nodes"]) <= 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analysis_architecture.py -v -k "top_n or summary_only"`
Expected: FAIL — parameters not recognized

- [ ] **Step 3: Add `top_n` and `summary_only` to tool definitions**

In `tool_defs/analysis.py`, add to `get_design_smells` inputSchema:
```python
"top_n": {
    "type": "integer",
    "description": "Maximum number of smells to return (default: all)",
},
"summary_only": {
    "type": "boolean",
    "description": "Return only counts by type, not individual smells (default: false)",
},
```

Add to `get_coupling_metrics` and `get_cross_module_dependencies`:
```python
"top_n": {
    "type": "integer",
    "description": "Maximum number of modules/nodes to return, sorted by relevance (default: all)",
},
```

- [ ] **Step 4: Update Pydantic models in handler**

In `handlers/analysis_architecture.py`, update the args models:
```python
class GetDesignSmellsArgs(BaseModel):
    repo_path: str
    severity_threshold: str = "medium"
    exclude_tests: bool = True
    top_n: int | None = None
    summary_only: bool = False

class GetCouplingMetricsArgs(BaseModel):
    repo_path: str
    module_filter: str | None = None
    top_n: int | None = None

class GetCrossModuleDependenciesArgs(BaseModel):
    repo_path: str
    module_filter: str | None = None
    include_external: bool = False
    min_edge_weight: int = 1
    top_n: int | None = None
```

- [ ] **Step 5: Implement filtering in handlers**

In `handle_get_design_smells`, after calling `analyze_design_smells`:
```python
if args.summary_only:
    smells_by_type = {}
    for smell in result["smells"]:
        t = smell["type"]
        smells_by_type[t] = smells_by_type.get(t, 0) + 1
    return {
        **{k: v for k, v in result.items() if k != "smells"},
        "smells_by_type": smells_by_type,
        "total_smells": len(result["smells"]),
    }
if args.top_n is not None:
    result = {**result, "smells": result["smells"][:args.top_n]}
```

For coupling and cross-module deps, sort by relevance metric (distance from main sequence for coupling, edge weight for deps) and slice to `top_n`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_analysis_architecture.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_handlers_analysis_architecture.py
git commit -m "feat: add top_n and summary_only params to analytical MCP tools for overflow prevention"
```

---

### Task 3: Smells Scoring Formula Review

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/health_scoring.py`
- Test: `tests/test_architecture_health.py`

- [ ] **Step 1: Read current scoring formula**

Read `health_scoring.py` and document the current caps:
- `min(density * 8, 60)` — density cap
- `min(god_classes * 5, 25)` — god class cap

- [ ] **Step 2: Write tests for recalibrated thresholds**

The actual `score_smells` signature is `(smells: list[dict], total_lines: int) -> dict`. It computes god_class count and weighted density internally from the smells list.

```python
from local_deepwiki.generators.analysis.health_scoring import score_smells

def test_smells_score_with_one_god_class():
    """With only 1 god class (down from 6), score should differentiate from many."""
    smells = [
        {"type": "god_class", "severity": "high"},
        *[{"type": "long_method", "severity": "high"} for _ in range(20)],
    ]
    result = score_smells(smells, total_lines=70000)
    # With 1 god class and low density, should score better than current F (35.2)
    assert result["score"] > 40

def test_smells_score_with_zero_god_classes():
    """Zero god classes should contribute 0 penalty."""
    smells = [{"type": "long_method", "severity": "medium"} for _ in range(20)]
    result = score_smells(smells, total_lines=70000)
    assert result["score"] > 60
    assert result["factors"]["god_classes"] == 0

def test_smells_score_differentiates_god_class_counts():
    """Score should meaningfully differ between 0, 1, and 6 god classes."""
    base_smells = [{"type": "long_method", "severity": "medium"} for _ in range(30)]
    score_0 = score_smells(base_smells, total_lines=70000)["score"]
    score_1 = score_smells(
        [*base_smells, {"type": "god_class", "severity": "high"}],
        total_lines=70000,
    )["score"]
    score_6 = score_smells(
        [*base_smells, *[{"type": "god_class", "severity": "high"} for _ in range(6)]],
        total_lines=70000,
    )["score"]
    assert score_0 > score_1 > score_6
    # Each additional god class should have diminishing but nonzero impact
    assert (score_0 - score_1) >= 3  # first god class matters
    assert (score_1 - score_6) >= 5  # many god classes matter more
```

- [ ] **Step 3: Recalibrate the formula**

Current formula in `health_scoring.py` (lines 133-135):
```python
score -= min(density * 8, 60)  # density penalty, cap 60
score -= min(god_classes * 5, 25)  # god class penalty, cap 25
```

With only 1 god class, `min(1*5, 25) = 5` — this is already reasonable. The bottleneck is the density cap: `min(density * 8, 60)` saturates at density 7.5. With 338 smells / 71K lines, the weighted density is ~7.48, right at the cap.

Options:
- **A) Increase density multiplier range**: `min(density * 6, 50)` — widens the curve
- **B) Use logarithmic scaling**: `min(log(density+1) * 20, 55)` — diminishing returns for high density
- **C) Reduce cap to allow more range**: `min(density * 8, 50)` + allocate 10 points to new factors

Choose the option that best reflects meaningful differentiation for codebases in the 3-10 density range.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/test_architecture_health.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/health_scoring.py tests/test_architecture_health.py
git commit -m "fix: recalibrate smells scoring formula to reflect reduced god class count"
```

---

## Phase 2: Wiki Quality Pages

**Integration pattern:** All four new pages (Tasks 4-7) are registered as auxiliary pages in `phases.py:generate_auxiliary_pages`. They follow the exact same pattern as the existing inheritance/glossary/coverage/dependency-graph pages:
1. Add `(page_path, title)` to the `aux_pages` list
2. Add the generator call to the `asyncio.gather` (all run concurrently)
3. Results are zipped and passed to `_add_auxiliary_page()` which writes the `WikiPage`

These pages are pure computation — no LLM calls needed — so they're fast. They do NOT depend on Phase 3 (`WikiPipelineContext`); they take `index_status` and `repo_path` directly, matching the existing auxiliary page pattern.

**Coverage targets:** Each new page generator module should have 80%+ coverage. Overall project coverage must stay at 95%+.

### Task 4: Architecture Health Dashboard Page

**Files:**
- Create: `src/local_deepwiki/generators/analysis/health_page.py`
- Modify: `src/local_deepwiki/generators/wiki/phases.py`
- Create: `tests/test_health_page.py`

- [ ] **Step 1: Write failing test**

```python
import pytest
from local_deepwiki.generators.analysis.health_page import generate_health_page

@pytest.fixture
def mock_health_data():
    return {
        "overall": {"score": 60.0, "grade": "C", "dimensions": {
            "complexity": {"score": 67.2, "grade": "C"},
            "coupling": {"score": 44.2, "grade": "D"},
            "smells": {"score": 35.2, "grade": "F"},
            "layers": {"score": 100.0, "grade": "A"},
        }},
        "top_findings": {
            "hotspots": [{"function": "foo", "file": "a.py", "line": 1, "metric_value": 33}],
            "high_severity_smells": [],
            "god_classes": [],
            "layer_violations": [],
        },
        "stats": {"total_lines": 71000, "total_functions": 1946},
    }

def test_generate_health_page_returns_markdown(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert result is not None
    assert "# Architecture Health" in result
    assert "Grade: **C**" in result
    assert "Complexity" in result

def test_generate_health_page_includes_dimension_table(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "| Dimension |" in result
    assert "67.2" in result

def test_generate_health_page_includes_hotspots(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "foo" in result
    assert "a.py" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_health_page.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement `generate_health_page`**

Create `src/local_deepwiki/generators/analysis/health_page.py`:

```python
"""Render architecture health analysis as a wiki markdown page."""

from __future__ import annotations


def generate_health_page(health_data: dict) -> str | None:
    """Render architecture health dict as markdown. Returns None if data is empty."""
    overall = health_data.get("overall")
    if not overall:
        return None

    lines: list[str] = []
    lines.append(f"# Architecture Health")
    lines.append("")
    lines.append(f"**Overall Grade: {overall['grade']} ({overall['score']:.0f}/100)**")
    lines.append("")

    # Dimension table
    dims = overall.get("dimensions", {})
    if dims:
        lines.append("## Scores by Dimension")
        lines.append("")
        lines.append("| Dimension | Score | Grade |")
        lines.append("|-----------|-------|-------|")
        for name, dim in dims.items():
            lines.append(f"| {name.title()} | {dim['score']:.1f} | {dim['grade']} |")
        lines.append("")

    # Stats
    stats = health_data.get("stats", {})
    if stats:
        lines.append("## Codebase Stats")
        lines.append("")
        lines.append(f"- **Total lines:** {stats.get('total_lines', 0):,}")
        lines.append(f"- **Total functions:** {stats.get('total_functions', 0):,}")
        lines.append(f"- **Files scanned:** {stats.get('files_scanned', 0):,}")
        lines.append("")

    # Top findings
    findings = health_data.get("top_findings", {})

    hotspots = findings.get("hotspots", [])
    if hotspots:
        lines.append("## Complexity Hotspots")
        lines.append("")
        lines.append("| Function | File | CC | Lines | Params |")
        lines.append("|----------|------|----|-------|--------|")
        for h in hotspots[:10]:
            d = h.get("details", {})
            lines.append(
                f"| `{h['function']}` | `{h['file']}:{h['line']}` "
                f"| {d.get('cyclomatic', '')} | {d.get('length', '')} "
                f"| {d.get('params', '')} |"
            )
        lines.append("")

    god_classes = findings.get("god_classes", [])
    if god_classes:
        lines.append("## God Classes")
        lines.append("")
        for gc in god_classes:
            lines.append(f"- **{gc['entity']}** in `{gc['file']}:{gc['line']}` — {gc['description']}")
        lines.append("")

    violations = findings.get("layer_violations", [])
    if violations:
        lines.append("## Layer Violations")
        lines.append("")
        for v in violations:
            lines.append(f"- {v}")
        lines.append("")
    else:
        lines.append("## Layer Architecture")
        lines.append("")
        lines.append("No layer violations detected.")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_health_page.py -v`
Expected: ALL PASS

- [ ] **Step 5: Integrate into wiki generation pipeline**

In `phases.py` `generate_auxiliary_pages`, add to `aux_pages` list:
```python
("health.md", "Architecture Health"),
```

Add the generator call to the `asyncio.gather`:
```python
from local_deepwiki.generators.analysis.health_page import generate_health_page
from local_deepwiki.generators.analysis.architecture_health import analyze_architecture_health

# Inside generate_auxiliary_pages, alongside existing calls:
health_data = analyze_architecture_health(str(repo_path), project_name)
health_content = generate_health_page(health_data)
```

- [ ] **Step 6: Write integration test**

```python
def test_auxiliary_pages_includes_health(mock_generator_context):
    """Health page should be generated as part of auxiliary pages phase."""
    # Verify health.md appears in generated pages
    ...
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest tests/ -v -x --timeout=60`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_deepwiki/generators/analysis/health_page.py tests/test_health_page.py src/local_deepwiki/generators/wiki/phases.py
git commit -m "feat: add Architecture Health wiki page with composite grade and top findings"
```

---

### Task 5: Complexity Hotspots Page

**Files:**
- Create: `src/local_deepwiki/generators/analysis/hotspots_page.py`
- Modify: `src/local_deepwiki/generators/wiki/phases.py`
- Create: `tests/test_hotspots_page.py`

- [ ] **Step 1: Write failing test**

```python
from local_deepwiki.generators.analysis.hotspots_page import generate_hotspots_page

def test_generate_hotspots_page_returns_markdown():
    hotspots_data = {
        "hotspots": [
            {"function": "foo", "file": "a.py", "line": 10, "metric_value": 33,
             "details": {"cyclomatic": 33, "params": 4, "length": 118, "nesting": 0}},
        ],
        "stats": {"total_functions": 1946, "files_scanned": 242, "metric_used": "complexity"},
    }
    result = generate_hotspots_page(hotspots_data)
    assert "# Complexity Hotspots" in result
    assert "foo" in result
    assert "33" in result

def test_generate_hotspots_page_empty():
    result = generate_hotspots_page({"hotspots": [], "stats": {}})
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `generate_hotspots_page`**

Follow same pattern as `health_page.py`: accept dict from `analyze_hotspots()`, render markdown table ranked by cyclomatic complexity with secondary columns for params, length, nesting. Include stats summary at top.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Register in `phases.py`** alongside health page

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add Complexity Hotspots wiki page with ranked function table"
```

---

### Task 6: Design Smells Page

**Files:**
- Create: `src/local_deepwiki/generators/analysis/smells_page.py`
- Modify: `src/local_deepwiki/generators/wiki/phases.py`
- Create: `tests/test_smells_page.py`

- [ ] **Step 1: Write failing test**

```python
from local_deepwiki.generators.analysis.smells_page import generate_smells_page

def test_generate_smells_page_groups_by_type():
    smells_data = {
        "smells": [
            {"type": "god_class", "severity": "high", "file": "a.py", "line": 1,
             "entity": "Foo", "description": "25 methods", "suggestion": "Split it"},
            {"type": "long_method", "severity": "high", "file": "b.py", "line": 10,
             "entity": "bar", "description": "100 lines", "suggestion": "Extract helpers"},
        ],
        "summary": {"total": 2, "by_severity": {"high": 2}},
    }
    result = generate_smells_page(smells_data)
    assert "# Design Smells" in result
    assert "## God Class" in result
    assert "## Long Method" in result

def test_generate_smells_page_includes_severity_summary():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `generate_smells_page`**

Group smells by type, render each group as a section with a table of (entity, file, severity, description, suggestion). Include a summary table at top with counts by type and severity.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Register in `phases.py`**

Note: depends on Task 1 (feature envy filtering) for clean output.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add Design Smells wiki page grouped by smell type with suggestions"
```

---

### Task 7: Coupling Metrics Page

**Files:**
- Create: `src/local_deepwiki/generators/analysis/coupling_page.py`
- Modify: `src/local_deepwiki/generators/wiki/phases.py`
- Create: `tests/test_coupling_page.py`

- [ ] **Step 1: Write failing test**

```python
from local_deepwiki.generators.analysis.coupling_page import generate_coupling_page

def test_generate_coupling_page_includes_martin_metrics():
    coupling_data = {
        "modules": [
            {"label": "core.indexer", "Ca": 5, "Ce": 3, "I": 0.375,
             "A": 0.0, "D": 0.625},
        ],
        "summary": {"total_modules": 1, "avg_distance": 0.625},
    }
    result = generate_coupling_page(coupling_data)
    assert "# Coupling Metrics" in result
    assert "Instability" in result
    assert "core.indexer" in result

def test_generate_coupling_page_highlights_distant_modules():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement `generate_coupling_page`**

Render Martin metrics table (Ca, Ce, I, A, D) sorted by distance from main sequence. Highlight modules with D > 0.7. Include a Mermaid quadrant diagram of Instability vs Abstractness if possible. Add summary stats (total modules, avg distance, modules at risk).

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Register in `phases.py`**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add Coupling Metrics wiki page with Martin metrics and distance analysis"
```

---

## Phase 3: Parameter Object Refactoring

**Coverage targets:** No new modules created (context.py is a dataclass file). All existing tests must continue to pass. Overall 95%+ maintained.

### Task 8: WikiPipelineContext Dataclass

**Files:**
- Create: `src/local_deepwiki/generators/wiki/context.py`
- Modify: `src/local_deepwiki/generators/wiki/pages.py`
- Modify: `src/local_deepwiki/generators/wiki/modules.py`
- Modify: `src/local_deepwiki/generators/wiki/postprocessing.py`
- Modify: `src/local_deepwiki/generators/wiki/phases.py`
- Modify: `src/local_deepwiki/generators/wiki/generator.py`
- Test: existing test suites

- [ ] **Step 1: Identify shared parameter groups**

From research, the common parameter groups across wiki generators are:

Group A (shared by all page generators): `index_status`, `vector_store`, `llm`, `system_prompt`
Group B (shared by overview/architecture/dependencies): Group A + `manifest`, `repo_path`
Group C (shared by file/module docs): Group A + `status_manager`, `config`, `full_rebuild`
Group D (shared by postprocessing): `repo_path`, `wiki_path`, `vector_store`, `llm`, `status_manager`, `progress_callback`, `write_callback`

- [ ] **Step 2: Write the context dataclass**

Create `src/local_deepwiki/generators/wiki/context.py`:

```python
"""Shared context objects for wiki generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.config.models import Config, WikiConfig
    from local_deepwiki.core.index_manager import IndexStatus
    from local_deepwiki.core.vectorstore.store import VectorStore
    from local_deepwiki.generators.manifest import ProjectManifest
    from local_deepwiki.generators.wiki.status import WikiStatusManager
    from local_deepwiki.providers.base import LLMProvider


@dataclass(frozen=True, slots=True)
class WikiPipelineContext:
    """Immutable context shared across wiki page generators.

    Bundles the parameters that are threaded through nearly every
    page generation function to eliminate long parameter lists.
    """

    index_status: IndexStatus
    vector_store: VectorStore
    llm: LLMProvider
    system_prompt: str
    repo_path: Path
    wiki_path: Path
    config: Config
    wiki_config: WikiConfig
    manifest: ProjectManifest | None
    status_manager: WikiStatusManager
    full_rebuild: bool = False
    max_chunk_content_chars: int = 15000
```

- [ ] **Step 3: Write test for context construction**

```python
def test_wiki_pipeline_context_is_frozen():
    ctx = WikiPipelineContext(...)
    with pytest.raises(FrozenInstanceError):
        ctx.full_rebuild = True
```

- [ ] **Step 4: Migrate `generate_overview_page` to accept context**

Change signature from 8 params to 1:
```python
async def generate_overview_page(ctx: WikiPipelineContext) -> WikiPage:
```

Update internal references from `index_status` to `ctx.index_status`, etc.

- [ ] **Step 5: Run existing page tests to verify no regressions**

Run: `uv run pytest tests/test_wiki_pages.py -v`

- [ ] **Step 6: Migrate remaining page generators one at a time**

Each migration: update signature, update body, update callers in `phases.py`, run tests.

Order: `generate_architecture_page` → `generate_dependencies_page` → `generate_module_docs` → `generate_codemap_pages_phase` → `generate_freshness_and_finalize`

- [ ] **Step 7: Update `phases.py` to construct and pass context**

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest tests/ -v -x --timeout=120`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git commit -m "refactor: introduce WikiPipelineContext to eliminate parameter proliferation in wiki pipeline"
```

---

### Task 9: Align `search_paginated` with SearchRequest

**Goal:** Internal refactoring only — the public API signature stays the same. Currently `search()` constructs a `SearchRequest` and delegates to `search_from_request()`, but `search_paginated()` has its own separate implementation. This means filter logic is duplicated.

**Files:**
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py`
- Test: existing search tests

- [ ] **Step 1: Verify existing SearchRequest pattern**

`search()` already constructs a `SearchRequest` and delegates to `search_from_request()`. `search_paginated()` does not — it has its own implementation with 12 params. The `SearchRequest` dataclass lives in `.mixins.search_types`.

- [ ] **Step 2: Write test for parity**

```python
def test_search_paginated_respects_search_request_fields():
    """search_paginated should support the same filtering as search."""
    ...
```

- [ ] **Step 3: Refactor `search_paginated` to use SearchRequest internally**

Keep the public method signature unchanged. Internally, construct a `SearchRequest` from the params, extend it with pagination fields (offset, cursor), and delegate to a shared search implementation. This eliminates the duplicated filter logic without breaking any callers.

- [ ] **Step 4: Run tests, verify no regressions**

Run: `uv run pytest tests/test_vectorstore*.py tests/test_search*.py -v`

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor: align search_paginated with SearchRequest pattern to reduce parameter duplication"
```

---

## Phase 4: God Class Split & Complexity Reduction

**Coverage targets:** New modules (`indexer_graph.py`, `indexer_status.py`) should have 80%+ coverage. Existing indexer tests should pass without modification (backward compat via delegation). Overall 95%+ maintained.

### Task 10: Extract Graph Extraction from RepositoryIndexer

**Files:**
- Create: `src/local_deepwiki/core/indexer_graph.py`
- Modify: `src/local_deepwiki/core/indexer.py`
- Test: existing indexer tests

- [ ] **Step 1: Create `indexer_graph.py` with extracted methods**

Move these 6 methods into a new `GraphExtractor` class:
- `_extract_graph_for_file`
- `_emit_graph_start`
- `_delete_stale_graph_data`
- `_extract_and_store_graph_data`
- `_emit_graph_complete`
- `_run_graph_extraction`

The class takes `vector_store` and `event_bus` as constructor params.

- [ ] **Step 2: Create `indexer_status.py` with state management methods**

Move these 7 methods into a new `IndexStatusTracker` class:
- `_load_previous_status`
- `_collect_files_to_process`
- `_create_index_status`
- `_save_index_status`
- `_load_status`
- `_save_status`
- `get_status`

- [ ] **Step 3: Update `RepositoryIndexer` to delegate**

```python
class RepositoryIndexer:
    def __init__(self, ...):
        ...
        self._graph = GraphExtractor(self.vector_store, self._event_bus)
        self._status = IndexStatusTracker(self._wiki_path, self._index_manager)
```

The `index()` method calls `self._graph.run_graph_extraction(...)` and `self._status.save(...)` instead of `self._run_graph_extraction(...)` etc.

- [ ] **Step 4: Add `__init__.py` re-exports for backward compatibility**

Ensure any external imports of `RepositoryIndexer` still work.

- [ ] **Step 5: Run full indexer test suite**

Run: `uv run pytest tests/test_indexer*.py -v`
Expected: ALL PASS

- [ ] **Step 6: Verify god class smell is resolved**

Run the design smells analysis and confirm `RepositoryIndexer` no longer triggers:
- Method count should drop from 25 to ~12 (below 15 threshold)
- Line count should drop below 500

- [ ] **Step 7: Commit**

```bash
git commit -m "refactor: extract GraphExtractor and IndexStatusTracker from RepositoryIndexer god class"
```

---

### Task 11: Reduce Top Complexity Hotspots

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/dependency_graph.py`
- Modify: `src/local_deepwiki/generators/analysis/callgraph.py`
- Test: existing tests for each file

- [ ] **Step 1: Split `_render_module_graph` (CC=33)**

This function has 118 lines with heavy conditional branching for different node types and edge styles. Extract:
- `_render_module_node()` — single node rendering
- `_render_module_edge()` — single edge rendering
- `_compute_module_layout()` — layout/grouping logic

Target: each extracted function < CC 10.

- [ ] **Step 2: Run dependency graph tests**

Run: `uv run pytest tests/test_dependency_graph*.py -v`

- [ ] **Step 3: Split `_extract_generic_call` (CC=28)**

This function has deep nesting (level 6) with language-specific branching. Extract a dispatch table keyed by node type:

```python
_CALL_EXTRACTORS: dict[str, Callable] = {
    "call_expression": _extract_standard_call,
    "method_invocation": _extract_method_call,
    "member_expression": _extract_member_call,
    ...
}
```

- [ ] **Step 4: Run callgraph tests**

Run: `uv run pytest tests/test_callgraph*.py -v`

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor: reduce cyclomatic complexity in dependency_graph and callgraph top hotspots"
```

---

## Verification Checkpoint

After all phases, run the full architecture health check to measure improvement:

- [ ] **Run `get_architecture_health`** and compare:
  - Overall score: target 70+ (B grade)
  - Smells score: target 50+ (up from 35.2)
  - Complexity score: target 75+ (up from 67.2)
  - God classes: target 0 (down from 1)

- [ ] **Run full test suite**

```bash
uv run pytest tests/ -v --timeout=120
```
Expected: ALL PASS, 95%+ coverage maintained

- [ ] **Update memory with new health grade**

Update `memory/project_health_grade_status.md` with post-improvement scores.
