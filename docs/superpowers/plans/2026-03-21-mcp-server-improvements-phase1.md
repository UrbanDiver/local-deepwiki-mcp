# MCP Server Improvements — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix output overflow, improve default sorting, consolidate redundant tools, and add a composite architecture analysis tool.

**Architecture:** All changes follow the existing pattern: args model (Pydantic) → tool definition (JSON schema) → handler (async, immutable filtering) → generator (pure function). New filtering logic goes in handlers, not generators. The composite tool adds a new narrative formatter module.

**Tech Stack:** Python 3.11+, Pydantic, FastMCP, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-21-mcp-server-improvements-design.md` (sections 1.1–1.4)

---

### Task 1: Set default `top_n` for overflow-prone tools

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:612-633` (GetCrossModuleDependenciesArgs)
- Modify: `src/local_deepwiki/models/tool_args.py:636-648` (GetCouplingMetricsArgs)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (update default descriptions)
- Test: `tests/test_module_dependencies.py`
- Test: `tests/test_coupling_metrics.py`

This is the primary fix for the 97K character overflow. Both tools currently default `top_n=None` (return everything). Change to `top_n=20`.

- [ ] **Step 1: Write failing test for cross-module deps default top_n**

```python
# In tests/test_module_dependencies.py

async def test_cross_module_deps_default_limits_modules(mock_access_control, simple_pkg):
    """Default call should return at most 20 modules (overflow prevention)."""
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(simple_pkg)}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data.get("modules", [])) <= 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_module_dependencies.py::test_cross_module_deps_default_limits_modules -v`
Expected: FAIL if simple_pkg has >20 modules, or PASS vacuously (small fixture)

- [ ] **Step 3: Change default `top_n` from `None` to `20` in args models**

In `src/local_deepwiki/models/tool_args.py`, change `GetCrossModuleDependenciesArgs.top_n`:

```python
    top_n: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Limit output to the top N modules by edge count (default: 20)",
    )
```

In `src/local_deepwiki/models/tool_args.py`, change `GetCouplingMetricsArgs.top_n`:

```python
    top_n: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Limit output to the top N modules by distance (default: 20)",
    )
```

- [ ] **Step 4: Update handler to apply top_n unconditionally**

In `handle_get_cross_module_dependencies`, the existing `if validated.top_n is not None:` guard is now always true (default=20). The logic still works correctly — no change needed to the handler since `top_n` is always an `int` now.

In `handle_get_coupling_metrics`, same — the existing `if validated.top_n is not None:` is always true. No handler change needed.

- [ ] **Step 5: Update tool definition descriptions to note default**

In `src/local_deepwiki/tool_defs/analysis.py`, update the `top_n` descriptions for both tools to mention the default of 20.

- [ ] **Step 6: Write test for coupling metrics default top_n**

```python
# In tests/test_coupling_metrics.py

async def test_coupling_metrics_default_limits_modules(mock_access_control, pkg_repo):
    """Default call should return at most 20 modules (overflow prevention)."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data.get("metrics", [])) <= 20
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_module_dependencies.py::test_cross_module_deps_default_limits_modules tests/test_coupling_metrics.py::test_coupling_metrics_default_limits_modules -v`
Expected: PASS

- [ ] **Step 8: Run full test suites for regression**

Run: `uv run pytest tests/test_module_dependencies.py tests/test_coupling_metrics.py -v`
Expected: All pass. Some existing tests that passed `top_n=None` may need updating to pass an explicit `top_n=500` if they expected unlimited results.

- [ ] **Step 9: Fix any regressions**

If existing tests fail because they relied on `top_n=None` returning all modules, update those tests to pass `top_n=500` explicitly.

- [ ] **Step 10: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py tests/test_module_dependencies.py tests/test_coupling_metrics.py
git commit -m "feat: default top_n=20 for cross-module deps and coupling metrics"
```

---

### Task 2: Add `summary_only` to `get_cross_module_dependencies`

> Note: Tasks 2-5 each add `summary_only` to one tool. These four tasks are independent and can be done in parallel.
> Task 1 (default top_n) must be completed first since Tasks 2-5 restructure the same handler filtering blocks.

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:612-633`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_cross_module_dependencies definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:254-304`
- Test: `tests/test_module_dependencies.py`

- [ ] **Step 1: Write failing test for summary_only**

```python
# In tests/test_module_dependencies.py

async def test_cross_module_deps_summary_only(mock_access_control, simple_pkg):
    """summary_only=true returns counts without full module/edge lists."""
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(simple_pkg), "summary_only": True}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "modules" not in data
    assert "edges" not in data
    assert "mermaid" not in data
    assert "stats" in data
    assert isinstance(data["stats"]["total_modules"], int)
    assert isinstance(data["stats"]["total_edges"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_module_dependencies.py::test_cross_module_deps_summary_only -v`
Expected: FAIL (summary_only not a valid parameter)

- [ ] **Step 3: Add `summary_only` field to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetCrossModuleDependenciesArgs`:

```python
    summary_only: bool = Field(
        default=False,
        description="Return only stats (module/edge counts) without full lists",
    )
```

- [ ] **Step 4: Add `summary_only` to tool definition JSON schema**

In `src/local_deepwiki/tool_defs/analysis.py`, add to the `get_cross_module_dependencies` tool's `properties`:

```python
"summary_only": {
    "type": "boolean",
    "description": "Return only stats (module/edge counts) without full lists (default: false)",
},
```

- [ ] **Step 5: Add summary_only filtering in handler**

In `src/local_deepwiki/handlers/analysis_architecture.py`, in `handle_get_cross_module_dependencies`, add after the existing `top_n` filtering block (before the logger.info call):

```python
    if validated.summary_only:
        result = {
            "status": result.get("status", "success"),
            "stats": result.get("stats", {}),
            "tool": result.get("tool", "get_cross_module_dependencies"),
        }
    elif validated.top_n is not None:
        # ... existing top_n logic stays here ...
```

Note: Move the existing `if validated.top_n` block into the `elif` branch so `summary_only` takes precedence.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_module_dependencies.py::test_cross_module_deps_summary_only -v`
Expected: PASS

- [ ] **Step 7: Write test for default top_n**

```python
async def test_cross_module_deps_default_top_n(mock_access_control, simple_pkg):
    """Default call without top_n still returns all modules (backward compat)."""
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(simple_pkg)}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "modules" in data
    assert "edges" in data
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_module_dependencies.py::test_cross_module_deps_default_top_n -v`
Expected: PASS (backward compatible — no default top_n change yet)

- [ ] **Step 9: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_module_dependencies.py
git commit -m "feat: add summary_only to get_cross_module_dependencies"
```

---

### Task 3: Add `summary_only` to `get_coupling_metrics`

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:636-648`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_coupling_metrics definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:308-349`
- Test: `tests/test_coupling_metrics.py`

- [ ] **Step 1: Write failing test for summary_only**

```python
async def test_coupling_metrics_summary_only(mock_access_control, pkg_repo):
    """summary_only=true returns stats without full metrics list."""
    result = await handle_get_coupling_metrics(
        {"repo_path": str(pkg_repo), "summary_only": True}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "metrics" not in data
    assert "stats" in data
    assert isinstance(data["stats"]["total_modules"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_coupling_metrics.py::test_coupling_metrics_summary_only -v`
Expected: FAIL

- [ ] **Step 3: Add `summary_only` field to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetCouplingMetricsArgs`:

```python
    summary_only: bool = Field(
        default=False,
        description="Return only stats without individual module metrics",
    )
```

- [ ] **Step 4: Add `summary_only` to tool definition JSON schema**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `get_coupling_metrics` properties:

```python
"summary_only": {
    "type": "boolean",
    "description": "Return only stats without individual module metrics (default: false)",
},
```

- [ ] **Step 5: Add summary_only filtering in handler**

In `handle_get_coupling_metrics`, restructure the filtering block:

```python
    if validated.summary_only:
        result = {
            "status": result.get("status", "success"),
            "stats": result.get("stats", {}),
            "tool": result.get("tool", "get_coupling_metrics"),
        }
    elif validated.top_n is not None:
        metrics = sorted(
            result.get("metrics", []),
            key=lambda m: m.get("distance", 0),
            reverse=True,
        )
        result = {**result, "metrics": metrics[: validated.top_n]}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_coupling_metrics.py::test_coupling_metrics_summary_only -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_coupling_metrics.py
git commit -m "feat: add summary_only to get_coupling_metrics"
```

---

### Task 4: Add `summary_only` to `get_hotspots`

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:588-609`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_hotspots definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:186-224`
- Test: `tests/test_hotspots.py`

- [ ] **Step 1: Write failing test for summary_only**

```python
async def test_hotspots_summary_only(mock_access_control, tmp_path):
    """summary_only=true returns stats without individual hotspot details."""
    # Create a file with a function
    (tmp_path / "mod.py").write_text("def foo(a, b):\n    return a + b\n")
    result = await handle_get_hotspots(
        {"repo_path": str(tmp_path), "summary_only": True}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "hotspots" not in data
    assert "stats" in data
    assert isinstance(data["stats"]["total_functions"], int)
    assert isinstance(data["stats"]["files_scanned"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hotspots.py::test_hotspots_summary_only -v`
Expected: FAIL

- [ ] **Step 3: Add `summary_only` field to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetHotspotsArgs`:

```python
    summary_only: bool = Field(
        default=False,
        description="Return only stats without individual hotspot details",
    )
```

- [ ] **Step 4: Add `summary_only` to tool definition JSON schema**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `get_hotspots` properties:

```python
"summary_only": {
    "type": "boolean",
    "description": "Return only stats without individual hotspot details (default: false)",
},
```

- [ ] **Step 5: Add summary_only filtering in handler**

In `handle_get_hotspots`, add after the `analyze_hotspots` call and before the logger:

```python
    if validated.summary_only:
        result = {
            "status": result.get("status", "success"),
            "stats": result.get("stats", {}),
            "tool": result.get("tool", "get_hotspots"),
        }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_hotspots.py::test_hotspots_summary_only -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_hotspots.py
git commit -m "feat: add summary_only to get_hotspots"
```

---

### Task 5: Add `summary_only` to `get_layer_dependencies`

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:576-579`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_layer_dependencies definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:38-82`
- Test: `tests/test_analysis_architecture.py`

- [ ] **Step 1: Write failing test for summary_only**

```python
async def test_layer_dependencies_summary_only(mock_access_control, tmp_path):
    """summary_only=true returns violation count without full layer details."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "core_mod.py").write_text("x = 1\n")
    result = await handle_get_layer_dependencies(
        {"repo_path": str(tmp_path), "summary_only": True}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "total_violations" in data
    assert "layer_file_counts" not in data
    assert "layer_edges" not in data
    assert "violations" not in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_analysis_architecture.py::test_layer_dependencies_summary_only -v`
Expected: FAIL

- [ ] **Step 3: Add `summary_only` field to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetLayerDependenciesArgs`:

```python
    summary_only: bool = Field(
        default=False,
        description="Return only violation count without full layer details",
    )
```

- [ ] **Step 4: Add `summary_only` to tool definition JSON schema**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `get_layer_dependencies` properties:

```python
"summary_only": {
    "type": "boolean",
    "description": "Return only violation count without full layer details (default: false)",
},
```

- [ ] **Step 5: Add summary_only filtering in handler**

In `handle_get_layer_dependencies`, add after building the result dict and before the logger:

```python
    if validated.summary_only:
        result = {
            "status": "success",
            "project_name": project_name,
            "total_violations": layer_result["total_violations"],
            "tool": "get_layer_dependencies",
        }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_analysis_architecture.py::test_layer_dependencies_summary_only -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_analysis_architecture.py
git commit -m "feat: add summary_only to get_layer_dependencies"
```

---

### Task 6: Filter leaf modules from `get_coupling_metrics` by default

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:636-648`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_coupling_metrics definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:308-349`
- Test: `tests/test_coupling_metrics.py`

- [ ] **Step 1: Write failing test for leaf filtering**

```python
async def test_coupling_metrics_excludes_leaves_by_default(mock_access_control, pkg_repo):
    """Default call excludes modules with efferent_coupling == 0 (pure leaves)."""
    result = await handle_get_coupling_metrics({"repo_path": str(pkg_repo)})
    data = json.loads(result[0].text)
    for m in data["metrics"]:
        assert m["efferent_coupling"] > 0, (
            f"Leaf module {m['module']} (Ce=0) should be excluded by default"
        )


async def test_coupling_metrics_include_leaves(mock_access_control, pkg_repo):
    """include_leaves=true restores all modules including pure leaves."""
    result = await handle_get_coupling_metrics(
        {"repo_path": str(pkg_repo), "include_leaves": True}
    )
    data = json.loads(result[0].text)
    has_leaf = any(m["efferent_coupling"] == 0 for m in data["metrics"])
    # pkg_repo should have at least one leaf module
    assert has_leaf, "Expected at least one leaf module when include_leaves=True"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_coupling_metrics.py::test_coupling_metrics_excludes_leaves_by_default tests/test_coupling_metrics.py::test_coupling_metrics_include_leaves -v`
Expected: FAIL (include_leaves not a valid parameter; leaf modules still present)

- [ ] **Step 3: Add `include_leaves` field to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetCouplingMetricsArgs`:

```python
    include_leaves: bool = Field(
        default=False,
        description="Include modules with zero efferent coupling (pure leaves)",
    )
```

- [ ] **Step 4: Add `include_leaves` to tool definition JSON schema**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `get_coupling_metrics` properties:

```python
"include_leaves": {
    "type": "boolean",
    "description": "Include modules with zero efferent coupling (default: false, excludes pure leaf modules)",
},
```

- [ ] **Step 5: Add leaf filtering in handler**

In `handle_get_coupling_metrics`, add filtering logic before the existing `top_n` block:

```python
    # Filter out pure leaf modules (Ce == 0) unless explicitly requested.
    if not validated.include_leaves:
        metrics = result.get("metrics", [])
        filtered = [m for m in metrics if m.get("efferent_coupling", 0) > 0]
        result = {
            **result,
            "metrics": filtered,
            "stats": {
                **result.get("stats", {}),
                "filtered_modules": len(metrics) - len(filtered),
            },
        }

    # Apply overflow-prevention filter (immutable — new dict, no mutation).
    if validated.summary_only:
        # ... existing summary_only logic ...
    elif validated.top_n is not None:
        # ... existing top_n logic ...
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_coupling_metrics.py::test_coupling_metrics_excludes_leaves_by_default tests/test_coupling_metrics.py::test_coupling_metrics_include_leaves -v`
Expected: PASS

- [ ] **Step 7: Run full coupling metrics test suite for regression**

Run: `uv run pytest tests/test_coupling_metrics.py -v`
Expected: All existing tests pass (some may need updating if they assumed leaves were included)

- [ ] **Step 8: Fix any regressions**

If existing tests fail because they expected leaf modules in default output, update them to either pass `include_leaves=True` or adjust assertions.

- [ ] **Step 9: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_coupling_metrics.py
git commit -m "feat: filter leaf modules from coupling metrics by default"
```

---

### Task 7: Exclude `__init__.py` re-export modules from hotspots

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/hotspots.py`
- Test: `tests/test_hotspots.py`

- [ ] **Step 1: Write failing test**

```python
def test_hotspots_excludes_init_reexport_modules(tmp_path):
    """__init__.py files that are mostly imports should be excluded.

    The __init__.py has a short function (so it WOULD appear as a hotspot
    if not filtered) PLUS enough import lines to satisfy the >80% heuristic.
    Ratio: 20 import lines + 1 __all__ + 1 def line + 1 return = 23 lines.
    Import/all lines = 21/23 = 91.3% > 80%.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    # 20 import lines + 1 __all__ line = 21 "import-like" lines
    imports = "\n".join(f"from .mod_{i} import func_{i}" for i in range(20))
    all_list = "__all__ = [" + ", ".join(f"'func_{i}'" for i in range(20)) + "]"
    # 1 function with 1 body line = 2 non-import meaningful lines
    func = "def setup(config):\n    return config"
    (pkg / "__init__.py").write_text(f"{imports}\n{all_list}\n{func}\n")
    # Create a regular module with a function (to have something non-init)
    (pkg / "mod_0.py").write_text("def func_0(a, b, c):\n    return a + b + c\n")

    from local_deepwiki.generators.analysis.hotspots import analyze_hotspots

    result = analyze_hotspots(repo_path=tmp_path, metric="complexity", top_n=50)
    files = [h["file"] for h in result.get("hotspots", [])]
    assert not any("__init__.py" in f for f in files), (
        "Re-export __init__.py should be excluded from hotspots"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hotspots.py::test_hotspots_excludes_init_reexport_modules -v`
Expected: FAIL (or PASS if __init__.py has no functions — adjust test fixture to ensure it would appear)

- [ ] **Step 3: Add re-export detection helper**

In `src/local_deepwiki/generators/analysis/hotspots.py`, add a helper function:

```python
def _is_reexport_init(file_path: Path) -> bool:
    """Check if an __init__.py file is primarily re-exports.

    Returns True if >80% of non-blank, non-comment lines are import
    statements or __all__ assignments.
    """
    if file_path.name != "__init__.py":
        return False
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False

    meaningful_lines = [
        line for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    if not meaningful_lines:
        return True  # Empty __init__.py — skip it

    import_or_all = sum(
        1 for line in meaningful_lines
        if line.strip().startswith(("import ", "from "))
        or line.strip().startswith("__all__")
    )
    return import_or_all / len(meaningful_lines) > 0.8
```

- [ ] **Step 4: Wire the filter into `analyze_hotspots`**

In the file iteration loop of `analyze_hotspots`, add a check to skip re-export `__init__.py` files:

```python
    if _is_reexport_init(full_path):
        continue
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_hotspots.py::test_hotspots_excludes_init_reexport_modules -v`
Expected: PASS

- [ ] **Step 6: Run full hotspots test suite for regression**

Run: `uv run pytest tests/test_hotspots.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/generators/analysis/hotspots.py tests/test_hotspots.py
git commit -m "feat: exclude re-export __init__.py from hotspots"
```

---

### Task 8: Add `detail_level` to `get_architecture_health`

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py:674-683`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_architecture_health definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:402-437`
- Test: `tests/test_architecture_health.py`

- [ ] **Step 1: Write failing test for detail_level=summary**

```python
async def test_architecture_health_summary_detail(mock_access_control, tmp_path):
    """detail_level=summary returns grade + dimensions + top 3 findings only."""
    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")
    result = await handle_get_architecture_health(
        {"repo_path": str(tmp_path), "detail_level": "summary"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "overall" in data
    assert "grade" in data["overall"]
    assert "dimensions" in data["overall"]
    # Summary should NOT include full top_findings or stats
    assert "stats" not in data
    # Output should be compact
    assert len(result[0].text) < 1500
```

- [ ] **Step 2: Write failing test for detail_level=full**

```python
async def test_architecture_health_full_detail(mock_access_control, tmp_path):
    """detail_level=full returns everything including file metrics."""
    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")
    result = await handle_get_architecture_health(
        {"repo_path": str(tmp_path), "detail_level": "full"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "overall" in data
    assert "top_findings" in data
    assert "stats" in data
    assert "file_metrics" in data
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_health.py::test_architecture_health_summary_detail tests/test_architecture_health.py::test_architecture_health_full_detail -v`
Expected: FAIL

- [ ] **Step 4: Add `detail_level` to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetArchitectureHealthArgs`:

```python
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~1K), standard (~4K), full (~12K with file metrics)",
    )
```

- [ ] **Step 5: Add `detail_level` to tool definition JSON schema**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `get_architecture_health` properties:

```python
"detail_level": {
    "type": "string",
    "enum": ["summary", "standard", "full"],
    "description": "Output detail level: summary (~1K chars), standard (~4K, default), full (~12K with file metrics)",
},
```

- [ ] **Step 6: Add detail_level filtering in handler**

In `handle_get_architecture_health`, after getting the result from `analyze_architecture_health`:

```python
    detail = validated.detail_level

    if detail == "summary":
        overall = result.get("overall", {})
        # Trim top_findings to top 3 per category
        findings = result.get("top_findings", {})
        trimmed_findings = {
            k: v[:3] if isinstance(v, list) else v
            for k, v in findings.items()
        }
        result = {
            "status": "success",
            "project_name": result.get("project_name", ""),
            "overall": overall,
            "top_findings": trimmed_findings,
            "tool": "get_architecture_health",
        }
    elif detail == "full":
        # Add file metrics (from the summary tool's logic)
        file_metrics = _collect_file_metrics(repo_path)
        result = {**result, "file_metrics": file_metrics}
    # "standard" — return as-is (current behavior)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_architecture_health.py::test_architecture_health_summary_detail tests/test_architecture_health.py::test_architecture_health_full_detail -v`
Expected: PASS

- [ ] **Step 8: Run full architecture health test suite for regression**

Run: `uv run pytest tests/test_architecture_health.py -v`
Expected: All pass (standard is the default, so existing tests should be unaffected)

- [ ] **Step 9: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_architecture_health.py
git commit -m "feat: add detail_level parameter to get_architecture_health"
```

---

### Task 9: Deprecate `get_architecture_summary` as alias

**Files:**
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py:138-183`
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (get_architecture_summary description)
- Test: `tests/test_analysis_architecture.py`

- [ ] **Step 1: Write test that summary delegates to health check**

```python
async def test_architecture_summary_delegates_to_health(mock_access_control, tmp_path):
    """get_architecture_summary should delegate to get_architecture_health internally."""
    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")
    result = await handle_get_architecture_summary({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    # Should now include health grade info (from delegation)
    assert "overall" in data or "layer_analysis" in data
```

- [ ] **Step 2: Run test to verify current behavior**

Run: `uv run pytest tests/test_analysis_architecture.py::test_architecture_summary_delegates_to_health -v`
Expected: Behavior check — see what currently passes

- [ ] **Step 3: Rewrite handler to delegate**

Replace `handle_get_architecture_summary` body to delegate to health check at `full` detail level:

```python
@handle_tool_errors
async def handle_get_architecture_summary(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_architecture_summary tool call.

    Deprecated: delegates to get_architecture_health with detail_level=full.
    """
    # Delegate to health check with full detail (includes file_metrics)
    health_args = {**args, "detail_level": "full"}
    return await handle_get_architecture_health(health_args)
```

- [ ] **Step 4: Update tool description to note deprecation**

In `src/local_deepwiki/tool_defs/analysis.py`, update the `get_architecture_summary` description:

```python
"description": "Deprecated: use get_architecture_health with detail_level='full' instead. ..."
```

- [ ] **Step 5: Run existing summary tests for regression**

Run: `uv run pytest tests/test_analysis_architecture.py -k "architecture_summary" -v`
Expected: May need to update assertions since output shape changes

- [ ] **Step 6: Update any failing tests**

Update test assertions to match the new delegated output format. The key change is that the response now includes `overall` grade data instead of just `layer_analysis` and `file_metrics`.

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/handlers/analysis_architecture.py src/local_deepwiki/tool_defs/analysis.py tests/test_analysis_architecture.py
git commit -m "refactor: deprecate get_architecture_summary, delegate to health check"
```

---

### Task 10: Create narrative formatter for composite analysis

**Files:**
- Create: `src/local_deepwiki/generators/analysis/architecture_report.py`
- Test: `tests/test_architecture_report.py`

- [ ] **Step 1: Write failing test for narrative formatting**

Create `tests/test_architecture_report.py`:

```python
"""Tests for the architecture report narrative formatter."""

from local_deepwiki.generators.analysis.architecture_report import (
    format_architecture_report,
)


def test_format_report_includes_executive_summary():
    """Report should start with an executive summary section."""
    health = {
        "overall": {
            "score": 76.5,
            "grade": "B",
            "dimensions": {
                "complexity": {"score": 77.7, "grade": "B"},
                "coupling": {"score": 69.1, "grade": "C"},
                "smells": {"score": 63.5, "grade": "C"},
                "layers": {"score": 100.0, "grade": "A"},
            },
        },
        "stats": {"total_lines": 72000, "total_functions": 2000, "files_scanned": 250},
        "top_findings": {
            "hotspots": [],
            "high_severity_smells": [],
            "god_classes": [],
            "layer_violations": [],
        },
    }
    deps = {"stats": {"total_modules": 379, "total_edges": 188}, "edges": []}
    report = format_architecture_report(health, deps, detail_level="standard")
    assert "## Executive Summary" in report
    assert "B" in report
    assert "76.5" in report


def test_format_report_includes_strengths():
    """Report should include a strengths section."""
    health = {
        "overall": {
            "score": 90.0,
            "grade": "A",
            "dimensions": {
                "complexity": {"score": 95.0, "grade": "A"},
                "coupling": {"score": 85.0, "grade": "B"},
                "smells": {"score": 90.0, "grade": "A"},
                "layers": {"score": 100.0, "grade": "A"},
            },
        },
        "stats": {"total_lines": 10000, "total_functions": 100, "files_scanned": 20},
        "top_findings": {
            "hotspots": [],
            "high_severity_smells": [],
            "god_classes": [],
            "layer_violations": [],
        },
    }
    deps = {"stats": {"total_modules": 50, "total_edges": 30}, "edges": []}
    report = format_architecture_report(health, deps, detail_level="standard")
    assert "## Strengths" in report


def test_format_report_includes_concerns():
    """Report should include a concerns section when issues exist."""
    health = {
        "overall": {
            "score": 60.0,
            "grade": "C",
            "dimensions": {
                "complexity": {"score": 50.0, "grade": "D"},
                "coupling": {"score": 60.0, "grade": "C"},
                "smells": {"score": 55.0, "grade": "D"},
                "layers": {"score": 100.0, "grade": "A"},
            },
        },
        "stats": {"total_lines": 50000, "total_functions": 500, "files_scanned": 100},
        "top_findings": {
            "hotspots": [
                {"function": "big_func", "file": "mod.py", "line": 1, "metric_value": 30,
                 "details": {"cyclomatic": 30, "params": 2, "length": 100, "nesting": 0}},
            ],
            "high_severity_smells": [
                {"type": "long_method", "severity": "high", "file": "mod.py",
                 "line": 1, "entity": "big_func", "description": "Too long"},
            ],
            "god_classes": [],
            "layer_violations": [],
        },
    }
    deps = {"stats": {"total_modules": 100, "total_edges": 80}, "edges": []}
    report = format_architecture_report(health, deps, detail_level="standard")
    assert "## Concerns" in report
    assert "big_func" in report


def test_format_report_summary_is_compact():
    """Summary detail level should produce <2K chars."""
    health = {
        "overall": {"score": 76.5, "grade": "B", "dimensions": {
            "complexity": {"score": 77.7, "grade": "B"},
            "coupling": {"score": 69.1, "grade": "C"},
            "smells": {"score": 63.5, "grade": "C"},
            "layers": {"score": 100.0, "grade": "A"},
        }},
        "stats": {"total_lines": 72000, "total_functions": 2000, "files_scanned": 250},
        "top_findings": {"hotspots": [], "high_severity_smells": [], "god_classes": [], "layer_violations": []},
    }
    deps = {"stats": {"total_modules": 379, "total_edges": 188}, "edges": []}
    report = format_architecture_report(health, deps, detail_level="summary")
    assert len(report) < 2000


def test_format_report_dependency_section():
    """Standard+ reports include dependency structure."""
    health = {
        "overall": {"score": 80.0, "grade": "B", "dimensions": {
            "complexity": {"score": 80.0, "grade": "B"},
            "coupling": {"score": 80.0, "grade": "B"},
            "smells": {"score": 80.0, "grade": "B"},
            "layers": {"score": 100.0, "grade": "A"},
        }},
        "stats": {"total_lines": 10000, "total_functions": 100, "files_scanned": 20},
        "top_findings": {"hotspots": [], "high_severity_smells": [], "god_classes": [], "layer_violations": []},
    }
    edges = [
        {"source": "core.vectorstore", "target": "models", "weight": 50},
        {"source": "handlers", "target": "core.vectorstore", "weight": 30},
    ]
    deps = {"stats": {"total_modules": 50, "total_edges": 30}, "edges": edges}
    report = format_architecture_report(health, deps, detail_level="standard")
    assert "## Dependency Structure" in report
    assert "core.vectorstore" in report
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_report.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Implement the narrative formatter**

Create `src/local_deepwiki/generators/analysis/architecture_report.py`:

```python
"""Narrative formatter for composite architecture analysis reports.

Converts structured health check and dependency data into a human-readable
markdown report. Template-based (no LLM calls).
"""

from __future__ import annotations

from typing import Any

# Thresholds for identifying strengths/concerns
_STRENGTH_THRESHOLD = 80
_CONCERN_THRESHOLD = 70


def format_architecture_report(
    health: dict[str, Any],
    deps: dict[str, Any],
    *,
    detail_level: str = "standard",
) -> str:
    """Format architecture analysis data into a markdown narrative report.

    Args:
        health: Output from analyze_architecture_health.
        deps: Output from analyze_cross_module_dependencies.
        detail_level: "summary", "standard", or "full".

    Returns:
        Markdown string with the formatted report.
    """
    sections: list[str] = []
    sections.append(_format_executive_summary(health))

    if detail_level == "summary":
        return "\n\n".join(sections)

    sections.append(_format_strengths(health))
    sections.append(_format_concerns(health))
    sections.append(_format_dependency_structure(deps))

    return "\n\n".join(s for s in sections if s)


def _format_executive_summary(health: dict[str, Any]) -> str:
    """Format the executive summary section."""
    overall = health.get("overall", {})
    grade = overall.get("grade", "?")
    score = overall.get("score", 0)
    stats = health.get("stats", {})
    lines = stats.get("total_lines", 0)
    functions = stats.get("total_functions", 0)
    files = stats.get("files_scanned", 0)
    dims = overall.get("dimensions", {})

    dim_table = "| Dimension | Score | Grade |\n|-----------|-------|-------|\n"
    for dim_name in ("complexity", "coupling", "smells", "layers"):
        d = dims.get(dim_name, {})
        dim_table += f"| {dim_name.title()} | {d.get('score', '?')} | {d.get('grade', '?')} |\n"

    return (
        f"## Executive Summary\n\n"
        f"**Overall: {grade} ({score}/100)** — "
        f"{lines:,} lines, {functions:,} functions across {files} files.\n\n"
        f"{dim_table}"
    )


def _format_strengths(health: dict[str, Any]) -> str:
    """Format the strengths section based on high-scoring dimensions."""
    overall = health.get("overall", {})
    dims = overall.get("dimensions", {})
    findings = health.get("top_findings", {})

    strengths: list[str] = []
    for dim_name, d in dims.items():
        if d.get("score", 0) >= _STRENGTH_THRESHOLD:
            strengths.append(f"- **{dim_name.title()}** ({d['grade']}): score {d['score']}/100")

    if not findings.get("god_classes"):
        strengths.append("- **No god classes** detected")

    if not findings.get("layer_violations"):
        strengths.append("- **Zero layer violations** — clean architectural layering")

    if not strengths:
        return ""

    return "## Strengths\n\n" + "\n".join(strengths)


def _format_concerns(health: dict[str, Any]) -> str:
    """Format the concerns section based on low-scoring dimensions and findings."""
    overall = health.get("overall", {})
    dims = overall.get("dimensions", {})
    findings = health.get("top_findings", {})

    parts: list[str] = []

    # Flag low-scoring dimensions
    for dim_name, d in dims.items():
        if d.get("score", 100) < _CONCERN_THRESHOLD:
            parts.append(f"- **{dim_name.title()}** ({d['grade']}): score {d['score']}/100")

    # List top hotspots
    hotspots = findings.get("hotspots", [])
    if hotspots:
        parts.append("\n### Complexity Hotspots\n")
        parts.append("| Function | File | CC | Lines |")
        parts.append("|----------|------|----|-------|")
        for h in hotspots[:5]:
            details = h.get("details", {})
            parts.append(
                f"| `{h['function']}` | `{h['file']}:{h['line']}` "
                f"| {details.get('cyclomatic', '?')} | {details.get('length', '?')} |"
            )

    # List high-severity smells
    smells = findings.get("high_severity_smells", [])
    if smells:
        parts.append("\n### High-Severity Design Smells\n")
        for s in smells[:5]:
            parts.append(f"- **{s['type']}** in `{s.get('file', '?')}:{s.get('line', '?')}` — {s.get('entity', '?')}")

    if not parts:
        return ""

    return "## Concerns\n\n" + "\n".join(parts)


def _format_dependency_structure(deps: dict[str, Any]) -> str:
    """Format the dependency structure section."""
    stats = deps.get("stats", {})
    edges = deps.get("edges", [])

    parts: list[str] = [
        f"**{stats.get('total_modules', 0)} modules**, "
        f"**{stats.get('total_edges', 0)} dependency edges**"
    ]

    if edges:
        # Find most-imported modules (highest in-degree by weight)
        in_degree: dict[str, int] = {}
        for e in edges:
            tgt = e.get("target", "")
            in_degree[tgt] = in_degree.get(tgt, 0) + e.get("weight", 1)

        top_hubs = sorted(in_degree.items(), key=lambda x: -x[1])[:5]
        if top_hubs:
            parts.append("\n### Most-Depended-On Modules\n")
            parts.append("| Module | Inbound Imports |")
            parts.append("|--------|----------------|")
            for mod, count in top_hubs:
                parts.append(f"| `{mod}` | {count} |")

        # Heaviest edges
        heaviest = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)[:5]
        if heaviest:
            parts.append("\n### Heaviest Dependencies\n")
            for e in heaviest:
                parts.append(
                    f"- `{e.get('source', '?')}` → `{e.get('target', '?')}` "
                    f"(weight {e.get('weight', 0)})"
                )

    return "## Dependency Structure\n\n" + "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_architecture_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/architecture_report.py tests/test_architecture_report.py
git commit -m "feat: add narrative formatter for architecture reports"
```

---

### Task 11: Create `analyze_architecture` composite tool

**Files:**
- Create: `src/local_deepwiki/generators/analysis/architecture_composite.py`
- Modify: `src/local_deepwiki/models/tool_args.py` (add AnalyzeArchitectureArgs)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (add tool definition)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (add handler)
- Modify: `src/local_deepwiki/handlers/__init__.py` (export handler)
- Modify: `src/local_deepwiki/handlers/analysis.py` (add to analysis handlers)
- Modify: `src/local_deepwiki/server.py` (register handler)
- Create: `tests/test_architecture_composite.py`

- [ ] **Step 1: Write failing test for composite tool**

Create `tests/test_architecture_composite.py`:

```python
"""Tests for the analyze_architecture composite tool."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers.analysis_architecture import handle_analyze_architecture


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def simple_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        "from .utils import helper\n\ndef main():\n    return helper()\n"
    )
    (src / "utils.py").write_text("def helper():\n    return 42\n")
    (src / "__init__.py").write_text("")
    return tmp_path


@pytest.mark.asyncio
async def test_analyze_architecture_returns_markdown(mock_access_control, simple_repo):
    """Composite tool should return a markdown narrative report."""
    result = await handle_analyze_architecture({"repo_path": str(simple_repo)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "report" in data
    assert "## Executive Summary" in data["report"]


@pytest.mark.asyncio
async def test_analyze_architecture_summary_detail(mock_access_control, simple_repo):
    """Summary detail level should produce compact output."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "detail_level": "summary"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "## Executive Summary" in data["report"]
    assert "## Concerns" not in data["report"]  # summary skips detailed sections


@pytest.mark.asyncio
async def test_analyze_architecture_standard_detail(mock_access_control, simple_repo):
    """Standard detail level should include all sections."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "detail_level": "standard"}
    )
    data = json.loads(result[0].text)
    assert "## Executive Summary" in data["report"]
    assert "## Dependency Structure" in data["report"]


@pytest.mark.asyncio
async def test_analyze_architecture_focus_complexity(mock_access_control, simple_repo):
    """Focus=complexity should only include complexity-related findings."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "focus": "complexity"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    # Dependency structure should be skipped when focusing on complexity
    assert "## Dependency Structure" not in data["report"]


@pytest.mark.asyncio
async def test_analyze_architecture_missing_repo(mock_access_control, tmp_path):
    """Should return error for missing repo."""
    result = await handle_analyze_architecture(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_analyze_architecture_output_size(mock_access_control, simple_repo):
    """Standard output should stay under 8K characters."""
    result = await handle_analyze_architecture({"repo_path": str(simple_repo)})
    assert len(result[0].text) < 8000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_composite.py -v`
Expected: FAIL (handler does not exist)

- [ ] **Step 3: Add args model**

In `src/local_deepwiki/models/tool_args.py`, add:

```python
class AnalyzeArchitectureArgs(BaseModel):
    """Arguments for the analyze_architecture composite tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~2K), standard (~6K), full (~12K)",
    )
    focus: str = Field(
        default="all",
        description="Focus area: all, complexity, coupling, or smells",
    )
```

Add `AnalyzeArchitectureArgs` to the model exports in `src/local_deepwiki/models/__init__.py`.

- [ ] **Step 4: Add tool definition**

In `src/local_deepwiki/tool_defs/analysis.py`, add:

```python
Tool(
    name="analyze_architecture",
    description="Comprehensive architecture analysis in a single call. Runs health check, dependency analysis, design smell detection, and hotspot ranking, then returns a pre-synthesized markdown narrative report. No prior indexing required.",
    inputSchema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the repository to analyze",
            },
            "detail_level": {
                "type": "string",
                "enum": ["summary", "standard", "full"],
                "description": "Output detail level: summary (~2K chars), standard (~6K, default), full (~12K)",
            },
            "focus": {
                "type": "string",
                "enum": ["all", "complexity", "coupling", "smells"],
                "description": "Focus area: all (default), complexity, coupling, or smells",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
),
```

- [ ] **Step 5: Create composite orchestrator**

Create `src/local_deepwiki/generators/analysis/architecture_composite.py`:

```python
"""Composite architecture analysis orchestrator.

Runs multiple sub-analyses and delegates to the narrative formatter.
No LLM calls — all synthesis is template-based.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.architecture_report import (
    format_architecture_report,
)


def analyze_architecture_composite(
    repo_path: Path,
    project_name: str,
    *,
    detail_level: str = "standard",
    focus: str = "all",
) -> dict[str, Any]:
    """Run composite architecture analysis and return narrative report.

    Args:
        repo_path: Path to the repository.
        project_name: Name for display.
        detail_level: "summary", "standard", or "full".
        focus: "all", "complexity", "coupling", or "smells".

    Returns:
        Dict with status, report (markdown string), and raw data.
    """
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )
    from local_deepwiki.generators.analysis.module_dependencies import (
        analyze_cross_module_dependencies,
    )

    # Adjust top_findings based on detail_level
    top_n_map = {"summary": 3, "standard": 5, "full": 10}
    top_findings = top_n_map.get(detail_level, 5)

    # Always run health check
    health = analyze_architecture_health(
        repo_path, project_name, top_findings=top_findings,
    )

    # Apply focus filter — keep only the focused dimension's findings
    if focus != "all":
        health = _apply_focus_filter(health, focus)

    # Run dependency analysis for standard+ detail (skip if focused on non-coupling)
    deps: dict[str, Any] = {"stats": {"total_modules": 0, "total_edges": 0}, "edges": []}
    if detail_level != "summary" and focus in ("all", "coupling"):
        deps = analyze_cross_module_dependencies(
            repo_path=repo_path,
            min_edge_weight=3,
        )

    report = format_architecture_report(health, deps, detail_level=detail_level)

    return {
        "status": "success",
        "project_name": project_name,
        "report": report,
        "overall": health.get("overall", {}),
        "tool": "analyze_architecture",
    }


def _apply_focus_filter(
    health: dict[str, Any], focus: str,
) -> dict[str, Any]:
    """Filter health results to only the focused dimension.

    Keeps overall scores but trims top_findings to the relevant category.
    """
    focus_to_findings = {
        "complexity": ["hotspots"],
        "coupling": [],  # coupling details come from deps, not health findings
        "smells": ["high_severity_smells", "god_classes"],
    }
    keep_keys = focus_to_findings.get(focus, [])

    findings = health.get("top_findings", {})
    filtered_findings = {
        k: v for k, v in findings.items() if k in keep_keys
    }
    return {**health, "top_findings": filtered_findings}
```

- [ ] **Step 6: Add handler**

In `src/local_deepwiki/handlers/analysis_architecture.py`, add:

```python
@handle_tool_errors
async def handle_analyze_architecture(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle analyze_architecture composite tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = AnalyzeArchitectureArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.architecture_composite import (
        analyze_architecture_composite,
    )
    from local_deepwiki.generators.manifest import get_cached_manifest

    manifest = get_cached_manifest(repo_path)
    project_name = manifest.name or repo_path.name
    result = analyze_architecture_composite(
        repo_path,
        project_name,
        detail_level=validated.detail_level,
        focus=validated.focus,
    )
    logger.info(
        "Architecture analysis: %s (%s) in %s",
        result.get("overall", {}).get("grade"),
        result.get("overall", {}).get("score"),
        repo_path,
    )
    return make_tool_text_content("analyze_architecture", result)
```

Add `AnalyzeArchitectureArgs` to the import from `local_deepwiki.models` at the top of the handler file.

- [ ] **Step 7: Register handler in server.py**

In `src/local_deepwiki/server.py`:
1. Add `handle_analyze_architecture` to the import from handlers
2. Add `"analyze_architecture": handle_analyze_architecture` to the tool handlers dict

Also update `handlers/__init__.py` and `handlers/analysis.py` to export the new handler.

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_architecture_composite.py -v`
Expected: PASS

- [ ] **Step 9: Run full test suite for regression**

Run: `uv run pytest tests/ -x --timeout=120`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add src/local_deepwiki/generators/analysis/architecture_composite.py src/local_deepwiki/generators/analysis/architecture_report.py src/local_deepwiki/models/tool_args.py src/local_deepwiki/models/__init__.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py src/local_deepwiki/handlers/__init__.py src/local_deepwiki/handlers/analysis.py src/local_deepwiki/server.py tests/test_architecture_composite.py
git commit -m "feat: add analyze_architecture composite tool"
```

---

### Task 12: Output size validation tests

**Files:**
- Create: `tests/test_output_sizes.py`

- [ ] **Step 1: Write output size tests**

Create `tests/test_output_sizes.py`:

```python
"""Automated output size tests for architecture tools.

Verifies that default parameters produce output under the specified limits.
Uses the local-deepwiki repo itself as the test subject for realistic sizes.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers.analysis_architecture import (
    handle_analyze_architecture,
    handle_get_architecture_health,
    handle_get_coupling_metrics,
    handle_get_cross_module_dependencies,
    handle_get_design_smells,
    handle_get_hotspots,
    handle_get_layer_dependencies,
)

# Use a small synthetic repo — real repo tests are too slow for CI
@pytest.fixture
def sized_repo(tmp_path: Path) -> Path:
    """Create a repo with enough structure to produce realistic output."""
    src = tmp_path / "src"
    for i in range(20):
        pkg = src / f"pkg{i}"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(f"from .mod import func{i}\n")
        body = "\n".join(f"    x{j} = {j}" for j in range(10))
        (pkg / "mod.py").write_text(
            f"def func{i}(a, b, c):\n{body}\n    return a\n"
        )
    return tmp_path


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


_8K = 8000
_4K = 4000
_1K = 1000


@pytest.mark.asyncio
async def test_hotspots_default_under_4k(mock_access_control, sized_repo):
    result = await handle_get_hotspots({"repo_path": str(sized_repo)})
    assert len(result[0].text) < _4K


@pytest.mark.asyncio
async def test_hotspots_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_hotspots(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


@pytest.mark.asyncio
async def test_coupling_default_under_4k(mock_access_control, sized_repo):
    result = await handle_get_coupling_metrics({"repo_path": str(sized_repo)})
    assert len(result[0].text) < _4K


@pytest.mark.asyncio
async def test_coupling_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_coupling_metrics(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


@pytest.mark.asyncio
async def test_layer_deps_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_layer_dependencies(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


@pytest.mark.asyncio
async def test_smells_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_design_smells(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


@pytest.mark.asyncio
async def test_health_summary_under_1500(mock_access_control, sized_repo):
    result = await handle_get_architecture_health(
        {"repo_path": str(sized_repo), "detail_level": "summary"}
    )
    assert len(result[0].text) < 1500


@pytest.mark.asyncio
async def test_analyze_architecture_standard_under_8k(mock_access_control, sized_repo):
    result = await handle_analyze_architecture({"repo_path": str(sized_repo)})
    assert len(result[0].text) < _8K
```

- [ ] **Step 2: Run output size tests**

Run: `uv run pytest tests/test_output_sizes.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_output_sizes.py
git commit -m "test: add output size validation tests for architecture tools"
```

---

### Task 13: Update CLAUDE.md and `find_tools` keywords

**Files:**
- Modify: `CLAUDE.md`
- Modify: `src/local_deepwiki/handlers/agentic_data.py`

- [ ] **Step 1: Update tool count in CLAUDE.md**

Update the MCP Server tool count tables in CLAUDE.md to reflect the new `analyze_architecture` tool. Add it to the Analysis & Search Tools section (count goes from 10 to 11).

- [ ] **Step 2: Add `analyze_architecture` to `_TOOL_KEYWORDS` in agentic_data.py**

In `src/local_deepwiki/handlers/agentic_data.py`, add an entry to `_TOOL_KEYWORDS`:

```python
"analyze_architecture": [
    "architecture", "health", "analysis", "composite", "report",
    "grade", "score", "smells", "coupling", "complexity",
],
```

- [ ] **Step 3: Run full test suite as final check**

Run: `uv run pytest tests/ -x --timeout=120`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md src/local_deepwiki/handlers/agentic_data.py
git commit -m "docs: update CLAUDE.md tool counts and find_tools keywords"
```

---

## Phase 2+ Summary (Detailed plans to follow)

### Phase 2a: Onboarding Guide + Recommendations

| Task | Description | New Files |
|------|-------------|-----------|
| 2.1 | `get_onboarding_guide` tool | `generators/analysis/onboarding.py`, handler, args, tool def |
| 2.2 | `get_recommendations` tool | `generators/analysis/recommendations.py`, handler, args, tool def |
| 2.2+ | Integrate recommendations into `analyze_architecture` output | Modify `architecture_composite.py` |
| CLI | `deepwiki onboard` subcommand | `cli/onboard_cli.py`, update `cli/main.py` |

### Phase 2b: Enhanced File Context + Comparison Enhancements

| Task | Description | New Files |
|------|-------------|-----------|
| 2.3 | Add `detail_level` to `get_file_context` | Modify existing handler + args |
| 2.4 | Add `detail_level` + verdict + coupling changes to `compare_architecture` | Modify existing handler + generator |
| CLI | `deepwiki compare` subcommand | `cli/compare_cli.py`, update `cli/main.py` |

### Phase 3a: Trend Tracking + CI Gates

| Task | Description | New Files |
|------|-------------|-----------|
| 3.1 | Health snapshot storage (JSONL) + `get_architecture_trends` tool | `core/health_history.py`, handler, args |
| 3.2 | `deepwiki check` CLI with quality gates | `cli/check_cli.py`, update `cli/main.py` |

### Phase 3b: Dashboard + Tours

| Task | Description | New Files |
|------|-------------|-----------|
| 3.3 | `/architecture` web UI route with vis.js + Chart.js | `web/routes_architecture.py`, templates |
| 3.4 | Guided tours (if validated) | `generators/tours.py`, handler, CLI |
