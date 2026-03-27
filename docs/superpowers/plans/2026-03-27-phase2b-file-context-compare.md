# Phase 2b: Enhanced File Context + Compare Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `detail_level` parameter to `get_file_context` (full mode adds entities, related tests, recent commits) and `compare_architecture` (verdict line, coupling changes, smell diff).

**Architecture:** Both changes are parameter additions to existing tools following the established pattern. No new files — only modifications to existing args models, tool definitions, handlers, and generators. The `compare_architecture` generator gets three new private helper functions for verdict, coupling diff, and smell diff.

**Tech Stack:** Python 3.11+, Pydantic, tree-sitter, subprocess (git), pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-27-phase2b-file-context-compare-design.md`

---

### Task 1: Add `detail_level` to `get_file_context`

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py` (~line 308, `GetFileContextArgs`)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (`get_file_context` definition)
- Modify: `src/local_deepwiki/handlers/analysis_metadata.py` (~line 258, `handle_get_file_context`)
- Test: `tests/test_file_context_detail.py` (new file for detail-level tests)

- [ ] **Step 1: Write failing tests**

Create `tests/test_file_context_detail.py`:

```python
"""Tests for get_file_context detail_level enhancements."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_metadata.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with a Python file."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "mymod.py").write_text(
        "class MyClass:\n"
        "    def method_one(self):\n"
        "        pass\n\n"
        "def standalone_func(x):\n"
        "    return x + 1\n"
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mymod.py").write_text(
        "from src.mymod import MyClass\n\n"
        "def test_it():\n"
        "    pass\n"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    return tmp_path


def test_extract_entities_from_file(git_repo):
    """_extract_entities returns classes and functions with line numbers."""
    from local_deepwiki.handlers.analysis_metadata import _extract_entities

    entities = _extract_entities(git_repo / "src" / "mymod.py")
    names = [e["name"] for e in entities]
    assert "MyClass" in names
    assert "standalone_func" in names
    types = {e["name"]: e["type"] for e in entities}
    assert types["MyClass"] == "class"
    assert types["standalone_func"] == "function"
    # All have line numbers
    for e in entities:
        assert isinstance(e["line"], int)
        assert e["line"] > 0


def test_find_related_tests(git_repo):
    """_find_related_tests finds test files importing the module."""
    from local_deepwiki.handlers.analysis_metadata import _find_related_tests

    results = _find_related_tests(git_repo, "src/mymod.py")
    assert any("test_mymod" in r for r in results)


def test_get_recent_commits(git_repo):
    """_get_recent_commits returns commit history for a file."""
    from local_deepwiki.handlers.analysis_metadata import _get_recent_commits

    commits = _get_recent_commits(git_repo, "src/mymod.py")
    assert len(commits) >= 1
    assert "sha" in commits[0]
    assert "message" in commits[0]


def test_get_recent_commits_not_git(tmp_path):
    """_get_recent_commits returns empty list for non-git repos."""
    from local_deepwiki.handlers.analysis_metadata import _get_recent_commits

    (tmp_path / "mod.py").write_text("x = 1\n")
    commits = _get_recent_commits(tmp_path, "mod.py")
    assert commits == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_file_context_detail.py -v`
Expected: FAIL (functions not found)

- [ ] **Step 3: Add `detail_level` to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `GetFileContextArgs`:

```python
    detail_level: str = Field(
        default="standard",
        description="Output detail: standard (imports, callers, related files) or full (+ entities, tests, commits)",
    )
```

- [ ] **Step 4: Add `detail_level` to tool definition**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `get_file_context` properties:

```python
"detail_level": {
    "type": "string",
    "enum": ["standard", "full"],
    "description": "Output detail: standard (default) or full (adds entities, related tests, recent commits)",
},
```

- [ ] **Step 5: Implement helper functions and handler changes**

In `src/local_deepwiki/handlers/analysis_metadata.py`, add three private helper functions (before `handle_get_file_context`):

```python
def _extract_entities(file_path: Path) -> list[dict[str, Any]]:
    """Extract function/class names and line numbers from a Python file via tree-sitter."""
    try:
        from local_deepwiki.core.parser import parse_file

        tree = parse_file(file_path)
        if tree is None:
            return []
    except Exception:
        return []

    entities: list[dict[str, Any]] = []
    root = tree.root_node

    for node in root.children:
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                entities.append({
                    "name": name_node.text.decode("utf-8"),
                    "type": "function",
                    "line": node.start_point[0] + 1,
                })
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                entities.append({
                    "name": name_node.text.decode("utf-8"),
                    "type": "class",
                    "line": node.start_point[0] + 1,
                })

    return entities


def _find_related_tests(repo_path: Path, file_path: str) -> list[str]:
    """Find test files that import from the given module."""
    # Convert file path to possible import patterns
    module_stem = Path(file_path).stem  # e.g., "server" from "src/server.py"
    module_parts = Path(file_path).with_suffix("").parts  # e.g., ("src", "server")

    results: list[str] = []
    test_dirs = [repo_path / d for d in ("tests", "test") if (repo_path / d).is_dir()]

    for test_dir in test_dirs:
        for test_file in test_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Check if any import line references the module
            if module_stem in content and (
                f"import {module_stem}" in content
                or f"from {module_stem}" in content
                or f"from .{module_stem}" in content
                or any(
                    ".".join(module_parts[i:]) in content
                    for i in range(len(module_parts))
                )
            ):
                try:
                    results.append(str(test_file.relative_to(repo_path)))
                except ValueError:
                    results.append(str(test_file))

    return sorted(results)


def _get_recent_commits(repo_path: Path, file_path: str, limit: int = 5) -> list[dict[str, str]]:
    """Get recent git commits touching a file."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={limit}", "--format=%h %s", "--", file_path],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except (subprocess.SubprocessError, OSError):
        return []

    commits: list[dict[str, str]] = []
    for line in result.stdout.strip().splitlines():
        if " " in line:
            sha, message = line.split(" ", 1)
            commits.append({"sha": sha, "message": message})
    return commits
```

Add `import subprocess` to the imports at the top if not present.

Then in `handle_get_file_context`, after building `result_context` (after line ~313), add:

```python
    # Full detail: add entities, related tests, and recent commits
    if validated.detail_level == "full":
        full_file_path = repo_path / file_path
        result_context["entities"] = _extract_entities(full_file_path)
        result_context["related_tests"] = _find_related_tests(repo_path, file_path)
        result_context["recent_commits"] = _get_recent_commits(repo_path, file_path)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_file_context_detail.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_metadata.py tests/test_file_context_detail.py
git commit -m "feat: add detail_level to get_file_context (entities, tests, commits)"
```

---

### Task 2: Add verdict to `compare_architecture`

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/architecture_compare.py`
- Test: `tests/test_architecture_compare.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_architecture_compare.py`:

```python
# --- Verdict tests ---

def test_compute_verdict_improved() -> None:
    """Positive overall delta produces 'improved' verdict."""
    from local_deepwiki.generators.analysis.architecture_compare import _compute_verdict

    deltas = {
        "overall_delta": 5.0,
        "dimensions": {
            "complexity": {"delta": 3.0},
            "coupling": {"delta": -1.0},
            "smells": {"delta": 8.0},
            "layers": {"delta": 0.0},
        },
    }
    verdict = _compute_verdict(deltas)
    assert "improved" in verdict["summary"].lower()
    assert "complexity" in verdict["improved"]
    assert "smells" in verdict["improved"]
    assert "coupling" in verdict["unchanged"]  # -1.0 within ±2 threshold
    assert "layers" in verdict["unchanged"]


def test_compute_verdict_degraded() -> None:
    """Negative overall delta produces 'degraded' verdict."""
    from local_deepwiki.generators.analysis.architecture_compare import _compute_verdict

    deltas = {
        "overall_delta": -6.0,
        "dimensions": {
            "complexity": {"delta": -5.0},
            "coupling": {"delta": -3.0},
            "smells": {"delta": 1.0},
            "layers": {"delta": 0.0},
        },
    }
    verdict = _compute_verdict(deltas)
    assert "degraded" in verdict["summary"].lower()
    assert "complexity" in verdict["degraded"]
    assert "coupling" in verdict["degraded"]


def test_compute_verdict_no_change() -> None:
    """Small delta produces 'no significant change' verdict."""
    from local_deepwiki.generators.analysis.architecture_compare import _compute_verdict

    deltas = {
        "overall_delta": 0.5,
        "dimensions": {
            "complexity": {"delta": 1.0},
            "coupling": {"delta": -0.5},
            "smells": {"delta": 0.0},
            "layers": {"delta": 0.0},
        },
    }
    verdict = _compute_verdict(deltas)
    assert "no significant change" in verdict["summary"].lower()
    assert len(verdict["improved"]) == 0
    assert len(verdict["degraded"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_compare.py::test_compute_verdict_improved -v`
Expected: FAIL

- [ ] **Step 3: Implement verdict helper**

In `src/local_deepwiki/generators/analysis/architecture_compare.py`, add after `_compute_deltas`:

```python
_VERDICT_THRESHOLD = 2.0


def _compute_verdict(deltas: dict[str, Any]) -> dict[str, Any]:
    """Compute architecture verdict from deltas."""
    overall_delta = deltas.get("overall_delta", 0)
    dims = deltas.get("dimensions", {})

    improved: list[str] = []
    degraded: list[str] = []
    unchanged: list[str] = []

    for dim_name, dim_data in dims.items():
        delta = dim_data.get("delta", 0)
        if delta > _VERDICT_THRESHOLD:
            improved.append(dim_name)
        elif delta < -_VERDICT_THRESHOLD:
            degraded.append(dim_name)
        else:
            unchanged.append(dim_name)

    if overall_delta > _VERDICT_THRESHOLD:
        summary = f"Architecture improved (+{overall_delta})"
    elif overall_delta < -_VERDICT_THRESHOLD:
        summary = f"Architecture degraded ({overall_delta})"
    else:
        summary = f"No significant change ({overall_delta:+.1f})"

    return {
        "summary": summary,
        "improved": improved,
        "degraded": degraded,
        "unchanged": unchanged,
    }
```

Wire it into `compare_architecture()` — add after `deltas = _compute_deltas(...)`:

```python
    verdict = _compute_verdict(deltas)
```

And add to the return dict:

```python
    return {
        "status": "success",
        "project_name": project_name,
        "base_ref": {"ref": base_ref, "sha": base_sha},
        "head_ref": {"ref": head_ref, "sha": head_sha},
        "deltas": deltas,
        "verdict": verdict,
        "base_health": base_health.get("overall", {}),
        "head_health": head_health.get("overall", {}),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_architecture_compare.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/architecture_compare.py tests/test_architecture_compare.py
git commit -m "feat: add verdict to compare_architecture"
```

---

### Task 3: Add `detail_level` to `compare_architecture` (full mode)

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py` (~line 766, `CompareArchitectureArgs`)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (`compare_architecture` definition)
- Modify: `src/local_deepwiki/generators/analysis/architecture_compare.py`
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (`handle_compare_architecture`)
- Test: `tests/test_architecture_compare.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_architecture_compare.py`:

```python
# --- Detail level tests ---

def test_compute_coupling_diff() -> None:
    """Coupling diff identifies new and resolved high-distance modules."""
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_coupling_diff,
    )

    base_metrics = [
        {"module": "core", "distance": 0.8},
        {"module": "utils", "distance": 0.3},
    ]
    head_metrics = [
        {"module": "core", "distance": 0.5},  # resolved (was > 0.7, now <= 0.7)
        {"module": "utils", "distance": 0.3},
        {"module": "web", "distance": 0.9},  # new high distance
    ]
    diff = _compute_coupling_diff(base_metrics, head_metrics)
    assert diff["base_modules"] == 2
    assert diff["head_modules"] == 3
    assert any(m["module"] == "web" for m in diff["new_high_distance"])
    assert any(m["module"] == "core" for m in diff["resolved_high_distance"])


def test_compute_smell_diff() -> None:
    """Smell diff identifies new and resolved smells by (type, file, entity)."""
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_smell_diff,
    )

    base_health = {
        "top_findings": {
            "high_severity_smells": [
                {"type": "long_method", "file": "a.py", "entity": "func_a"},
                {"type": "god_class", "file": "b.py", "entity": "BigB"},
            ],
        },
    }
    head_health = {
        "top_findings": {
            "high_severity_smells": [
                {"type": "long_method", "file": "a.py", "entity": "func_a"},  # same
                {"type": "god_class", "file": "c.py", "entity": "BigC"},  # new
            ],
        },
    }
    diff = _compute_smell_diff(base_health, head_health)
    new_entities = [s["entity"] for s in diff["new_smells"]]
    resolved_entities = [s["entity"] for s in diff["resolved_smells"]]
    assert "BigC" in new_entities
    assert "BigB" in resolved_entities
    assert "func_a" not in new_entities
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_compare.py::test_compute_coupling_diff -v`
Expected: FAIL

- [ ] **Step 3: Add `detail_level` to args model**

In `src/local_deepwiki/models/tool_args.py`, add to `CompareArchitectureArgs`:

```python
    detail_level: str = Field(
        default="standard",
        description="Output detail: standard (scores + verdict) or full (+ coupling changes + smell diff)",
    )
```

- [ ] **Step 4: Add `detail_level` to tool definition**

In `src/local_deepwiki/tool_defs/analysis.py`, add to `compare_architecture` properties:

```python
"detail_level": {
    "type": "string",
    "enum": ["standard", "full"],
    "description": "Output detail: standard (default, scores + verdict) or full (adds coupling and smell diffs)",
},
```

- [ ] **Step 5: Implement coupling and smell diff helpers**

In `src/local_deepwiki/generators/analysis/architecture_compare.py`, add:

```python
_HIGH_DISTANCE_THRESHOLD = 0.7


def _compute_coupling_diff(
    base_metrics: list[dict[str, Any]],
    head_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare coupling metrics between two refs."""
    base_high = {
        m["module"]: m["distance"]
        for m in base_metrics
        if m.get("distance", 0) > _HIGH_DISTANCE_THRESHOLD
    }
    head_high = {
        m["module"]: m["distance"]
        for m in head_metrics
        if m.get("distance", 0) > _HIGH_DISTANCE_THRESHOLD
    }

    new_high = [
        {"module": mod, "distance": dist}
        for mod, dist in head_high.items()
        if mod not in base_high
    ]
    resolved_high = [
        {"module": mod, "distance": dist}
        for mod, dist in base_high.items()
        if mod not in head_high
    ]

    return {
        "base_modules": len(base_metrics),
        "head_modules": len(head_metrics),
        "new_high_distance": new_high,
        "resolved_high_distance": resolved_high,
    }


def _compute_smell_diff(
    base_health: dict[str, Any],
    head_health: dict[str, Any],
) -> dict[str, Any]:
    """Compare smells between two health reports."""
    def _smell_key(s: dict[str, Any]) -> tuple[str, str, str]:
        return (s.get("type", ""), s.get("file", ""), s.get("entity", ""))

    base_smells = base_health.get("top_findings", {}).get("high_severity_smells", [])
    head_smells = head_health.get("top_findings", {}).get("high_severity_smells", [])

    base_keys = {_smell_key(s) for s in base_smells}
    head_keys = {_smell_key(s) for s in head_smells}

    new_keys = head_keys - base_keys
    resolved_keys = base_keys - head_keys

    new_smells = [s for s in head_smells if _smell_key(s) in new_keys]
    resolved_smells = [s for s in base_smells if _smell_key(s) in resolved_keys]

    return {
        "new_smells": [{"type": s.get("type"), "file": s.get("file"), "entity": s.get("entity")} for s in new_smells],
        "resolved_smells": [{"type": s.get("type"), "file": s.get("file"), "entity": s.get("entity")} for s in resolved_smells],
    }
```

- [ ] **Step 6: Wire full detail into `compare_architecture()`**

Update `compare_architecture()` signature to accept `detail_level`:

```python
def compare_architecture(
    repo_path: Path,
    project_name: str,
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
    *,
    detail_level: str = "standard",
) -> dict[str, Any]:
```

After computing verdict and before building the return dict, add full-detail logic:

```python
    result: dict[str, Any] = {
        "status": "success",
        "project_name": project_name,
        "base_ref": {"ref": base_ref, "sha": base_sha},
        "head_ref": {"ref": head_ref, "sha": head_sha},
        "deltas": deltas,
        "verdict": verdict,
        "base_health": base_health.get("overall", {}),
        "head_health": head_health.get("overall", {}),
    }

    if detail_level == "full":
        from local_deepwiki.generators.analysis.coupling import (
            analyze_coupling_metrics,
        )

        # Run coupling analysis on both refs
        head_coupling = analyze_coupling_metrics(repo_path).get("metrics", [])

        # For base ref, use the worktree that was already created/removed earlier.
        # Re-create briefly for coupling analysis.
        tmp_base_coupling = Path(tempfile.mkdtemp(prefix="deepwiki_coupling_"))
        try:
            if _create_worktree(repo_path, base_ref, tmp_base_coupling):
                base_coupling = analyze_coupling_metrics(tmp_base_coupling).get("metrics", [])
            else:
                base_coupling = []
        finally:
            _remove_worktree(repo_path, tmp_base_coupling)

        result["coupling_changes"] = _compute_coupling_diff(base_coupling, head_coupling)
        result["smell_diff"] = _compute_smell_diff(base_health, head_health)

    return result
```

- [ ] **Step 7: Update handler to pass detail_level**

In `src/local_deepwiki/handlers/analysis_architecture.py`, update `handle_compare_architecture`:

```python
    result = compare_architecture(
        repo_path,
        project_name,
        base_ref=validated.base_ref,
        head_ref=validated.head_ref,
        detail_level=validated.detail_level,
    )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_architecture_compare.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/generators/analysis/architecture_compare.py src/local_deepwiki/handlers/analysis_architecture.py tests/test_architecture_compare.py
git commit -m "feat: add detail_level to compare_architecture (coupling diff, smell diff)"
```

---

### Task 4: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update tool descriptions**

In the Analysis & Search Tools table, update `get_file_context` description to note the detail_level parameter. No count change needed (no new tools).

In the `compare_architecture` tool entry, note the verdict and detail_level enhancements.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Phase 2b tool enhancements"
```
