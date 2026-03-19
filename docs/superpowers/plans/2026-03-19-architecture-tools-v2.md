# Architecture Analysis Tools v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 new composite MCP tools (`get_architecture_health`, `compare_architecture`, `get_module_health`) and extract shared source-filtering infrastructure that fixes coverage/vendored file contamination across all analysis tools.

**Architecture:** Pure static analysis (no LLM, no indexing). New tools compose existing analysis functions (`analyze_hotspots`, `analyze_coupling_metrics`, `analyze_design_smells`, `analyze_layer_dependencies`) rather than reimplementing metrics. Shared source filtering is extracted into a single module and adopted by all analysis tools.

**Tech Stack:** Python, tree-sitter (via CodeParser), git subprocess calls, Pydantic models, pytest

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `src/local_deepwiki/generators/analysis/source_filter.py` | Shared source-file filtering: test detection, skip-dir patterns, extension matching. Single source of truth. |
| `src/local_deepwiki/generators/analysis/health_scoring.py` | Health grade computation: dimension scores (0-100), letter grades (A-F), weighted aggregation. |
| `src/local_deepwiki/generators/analysis/architecture_health.py` | Composite analysis: runs hotspots + coupling + smells + layers, scores each dimension, returns graded summary. |
| `src/local_deepwiki/generators/analysis/architecture_compare.py` | Git-ref comparison: runs metrics at two refs via `git worktree`, computes deltas, returns what changed. |
| `src/local_deepwiki/generators/analysis/module_health.py` | Per-module deep dive: coupling, complexity distribution, smells, dependents for a single module. |
| `tests/test_source_filter.py` | Tests for shared filtering |
| `tests/test_health_scoring.py` | Tests for scoring/grading logic |
| `tests/test_architecture_health.py` | Tests for composite health tool |
| `tests/test_architecture_compare.py` | Tests for git comparison tool |
| `tests/test_module_health.py` | Tests for module health tool |

### Modified files

| File | Changes |
|------|---------|
| `src/local_deepwiki/generators/analysis/hotspots.py` | Replace `_is_test_file`, `_TEST_DIR_NAMES`, skip-dir logic with imports from `source_filter.py` |
| `src/local_deepwiki/generators/analysis/design_smells.py` | Same: replace duplicated filtering with `source_filter.py` imports |
| `src/local_deepwiki/generators/analysis/module_dependencies.py` | Same: replace skip-dir logic with `source_filter.py` imports |
| `src/local_deepwiki/generators/analysis/coupling.py` | Same |
| `src/local_deepwiki/handlers/analysis_architecture.py` | Replace `_collect_file_metrics` skip logic with `source_filter.py`; add 3 new handlers |
| `src/local_deepwiki/tool_defs/analysis.py` | Add 3 new `Tool()` definitions to `ANALYSIS_TOOLS` |
| `src/local_deepwiki/models/tool_args.py` | Add 3 new `Args` models |
| `src/local_deepwiki/models/__init__.py` | Re-export new models |
| `src/local_deepwiki/handlers/analysis.py` | Re-export new handlers |
| `src/local_deepwiki/handlers/__init__.py` | Add new handler imports and `__all__` entries |
| `src/local_deepwiki/server.py` | Add 3 entries to `TOOL_HANDLERS` dict |

---

## Task 1: Extract shared source filtering (`source_filter.py`)

Multiple analysis modules duplicate test-file detection (`_is_test_file`, `_TEST_DIR_NAMES`) and skip-directory patterns, each with slightly different lists. Extract into one module.

**Files:**
- Create: `src/local_deepwiki/generators/analysis/source_filter.py`
- Create: `tests/test_source_filter.py`
- Modify: `src/local_deepwiki/generators/analysis/hotspots.py`
- Modify: `src/local_deepwiki/generators/analysis/design_smells.py`
- Modify: `src/local_deepwiki/generators/analysis/module_dependencies.py`
- Modify: `src/local_deepwiki/generators/analysis/coupling.py`
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (`_collect_file_metrics`)

- [ ] **Step 1: Write the source_filter module**

```python
# src/local_deepwiki/generators/analysis/source_filter.py
"""Shared source-file filtering for analysis tools.

Centralizes test-file detection, directory skipping, and extension
matching so all analysis modules use consistent rules.
"""
from __future__ import annotations

import os
from pathlib import Path

from local_deepwiki.core.parser.languages import EXTENSION_MAP

# Directories always skipped during source scanning.
SKIP_DIRS: frozenset[str] = frozenset({
    "__pycache__", "node_modules", ".deepwiki", "dist", "build",
    "coverage_html", "coverage_openai_embeddings", "htmlcov",
    ".git", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
    "egg-info", ".eggs",
})

# Directory names that indicate test code.
TEST_DIR_NAMES: frozenset[str] = frozenset({
    "tests", "test", "__tests__", "spec",
})


def is_test_file(rel_path: Path) -> bool:
    """Return True if *rel_path* looks like a test file."""
    name = rel_path.name
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    return any(part in TEST_DIR_NAMES for part in rel_path.parts)


def should_skip_dir(dirname: str) -> bool:
    """Return True if *dirname* should be skipped during source scanning."""
    return dirname.startswith(".") or dirname in SKIP_DIRS


def iter_source_files(
    repo_path: Path,
    *,
    exclude_tests: bool = True,
    extensions: frozenset[str] | None = None,
) -> list[tuple[Path, Path]]:
    """Walk *repo_path* and yield (full_path, rel_path) for source files.

    Args:
        repo_path: Root of the repository.
        exclude_tests: Skip test files when True.
        extensions: File extensions to include (default: all tree-sitter supported).

    Returns:
        List of (absolute_path, relative_path) tuples, sorted by relative path.
    """
    if extensions is None:
        extensions = frozenset(EXTENSION_MAP.keys())

    results: list[tuple[Path, Path]] = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            full_path = Path(root) / fname
            if full_path.suffix not in extensions:
                continue
            try:
                rel_path = full_path.relative_to(repo_path)
            except ValueError:
                continue
            if exclude_tests and is_test_file(rel_path):
                continue
            results.append((full_path, rel_path))

    results.sort(key=lambda pair: pair[1])
    return results


def iter_python_files(
    repo_path: Path,
    *,
    exclude_tests: bool = False,
) -> list[tuple[Path, Path]]:
    """Walk *repo_path* and yield (full_path, rel_path) for .py files only."""
    return iter_source_files(
        repo_path,
        exclude_tests=exclude_tests,
        extensions=frozenset({".py"}),
    )
```

- [ ] **Step 2: Write tests for source_filter**

```python
# tests/test_source_filter.py
"""Tests for shared source filtering utilities."""
from __future__ import annotations

from pathlib import Path

from local_deepwiki.generators.analysis.source_filter import (
    SKIP_DIRS,
    is_test_file,
    iter_python_files,
    iter_source_files,
    should_skip_dir,
)


def test_is_test_file_by_prefix():
    assert is_test_file(Path("test_foo.py"))


def test_is_test_file_by_suffix():
    assert is_test_file(Path("foo_test.py"))


def test_is_test_file_conftest():
    assert is_test_file(Path("conftest.py"))


def test_is_test_file_in_test_dir():
    assert is_test_file(Path("tests/helpers.py"))


def test_not_test_file():
    assert not is_test_file(Path("src/server.py"))


def test_should_skip_dir_hidden():
    assert should_skip_dir(".git")


def test_should_skip_dir_pycache():
    assert should_skip_dir("__pycache__")


def test_should_skip_dir_coverage():
    assert should_skip_dir("coverage_html")


def test_should_not_skip_src():
    assert not should_skip_dir("src")


def test_iter_source_files_excludes_tests(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("x = 1")

    results = iter_source_files(tmp_path, exclude_tests=True, extensions=frozenset({".py"}))
    rel_paths = [r[1] for r in results]
    assert Path("src/main.py") in rel_paths
    assert not any("test" in str(p) for p in rel_paths)


def test_iter_source_files_includes_tests(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("x = 1")

    results = iter_source_files(tmp_path, exclude_tests=False, extensions=frozenset({".py"}))
    rel_paths = [str(r[1]) for r in results]
    assert any("test" in p for p in rel_paths)


def test_iter_source_files_skips_coverage(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "coverage_html").mkdir()
    (tmp_path / "coverage_html" / "report.js").write_text("x = 1")

    results = iter_source_files(tmp_path, exclude_tests=False)
    rel_paths = [str(r[1]) for r in results]
    assert not any("coverage_html" in p for p in rel_paths)


def test_iter_python_files(tmp_path):
    (tmp_path / "main.py").write_text("x = 1")
    (tmp_path / "main.js").write_text("x = 1")

    results = iter_python_files(tmp_path)
    assert len(results) == 1
    assert results[0][1] == Path("main.py")


def test_skip_dirs_includes_venv():
    assert "venv" in SKIP_DIRS
    assert ".venv" in SKIP_DIRS
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_source_filter.py -v`
Expected: All pass

- [ ] **Step 4: Refactor hotspots.py to use source_filter**

In `hotspots.py`, remove `_TEST_DIR_NAMES`, `_is_test_file`, and the `os.walk` loop. Replace with:
```python
from local_deepwiki.generators.analysis.source_filter import iter_source_files
```
Use `iter_source_files(repo_path, exclude_tests=exclude_tests)` instead of the manual walk.

- [ ] **Step 5: Refactor design_smells.py to use source_filter**

Same pattern: remove `_TEST_DIR_NAMES`, `_is_test_file`, manual walk. Import from `source_filter`.

- [ ] **Step 6: Refactor module_dependencies.py to use source_filter**

Replace the `os.walk` with skip-dir checks with `iter_python_files(repo_path)`.

- [ ] **Step 7: Refactor coupling.py to use source_filter**

Replace the `.rglob("*.py")` with skip-dir checks with `iter_python_files(repo_path)`.

- [ ] **Step 8: Refactor _collect_file_metrics in analysis_architecture.py**

Replace the `repo_path.rglob("*.py")` loop and its skip logic with `iter_python_files(repo_path, exclude_tests=False)`.

- [ ] **Step 9: Run all affected tests to verify no regressions**

Run: `uv run pytest tests/test_hotspots.py tests/test_design_smells.py tests/test_module_dependencies.py tests/test_coupling_metrics.py tests/test_source_filter.py -v`
Expected: All pass

- [ ] **Step 10: Commit**

```bash
git add src/local_deepwiki/generators/analysis/source_filter.py tests/test_source_filter.py \
  src/local_deepwiki/generators/analysis/hotspots.py \
  src/local_deepwiki/generators/analysis/design_smells.py \
  src/local_deepwiki/generators/analysis/module_dependencies.py \
  src/local_deepwiki/generators/analysis/coupling.py \
  src/local_deepwiki/handlers/analysis_architecture.py
git commit -m "refactor: extract shared source filtering, fix coverage/venv contamination"
```

---

## Task 2: Health scoring module (`health_scoring.py`)

Pure scoring logic with no I/O. Takes metric summaries and returns numeric scores and letter grades.

**Files:**
- Create: `src/local_deepwiki/generators/analysis/health_scoring.py`
- Create: `tests/test_health_scoring.py`

- [ ] **Step 1: Write the health_scoring module**

```python
# src/local_deepwiki/generators/analysis/health_scoring.py
"""Health scoring — converts raw architecture metrics into scores and grades.

Provides dimension-level scores (0-100) and an overall letter grade (A-F).
No I/O — pure computation on metric summaries.
"""
from __future__ import annotations

from typing import Any

# Letter grade thresholds
_GRADE_THRESHOLDS: tuple[tuple[str, int], ...] = (
    ("A", 90),
    ("B", 75),
    ("C", 60),
    ("D", 40),
    ("F", 0),
)

# Weights for overall score
_DIMENSION_WEIGHTS: dict[str, float] = {
    "complexity": 0.30,
    "coupling": 0.25,
    "smells": 0.25,
    "layers": 0.20,
}


def letter_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    for grade, threshold in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def score_complexity(hotspots: list[dict[str, Any]], total_functions: int) -> dict[str, Any]:
    """Score complexity dimension (0-100).

    Factors:
    - Max cyclomatic complexity (lower is better)
    - % of functions above CC=15 (lower is better)
    """
    if total_functions == 0:
        return {"score": 100, "grade": "A", "factors": {}}

    cc_values = [h["metric_value"] for h in hotspots if "metric_value" in h]
    max_cc = max(cc_values) if cc_values else 0
    high_cc_count = sum(1 for h in hotspots if h.get("metric_value", 0) > 15)
    high_cc_pct = (high_cc_count / total_functions) * 100 if total_functions > 0 else 0

    # Score: start at 100, deduct for high CC
    score = 100.0
    if max_cc > 50:
        score -= 30
    elif max_cc > 30:
        score -= 20
    elif max_cc > 15:
        score -= 10

    # Deduct for % of functions over CC=15
    score -= min(high_cc_pct * 5, 40)  # cap at 40 point deduction

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "max_cyclomatic": max_cc,
            "functions_over_cc15": high_cc_count,
            "pct_over_cc15": round(high_cc_pct, 1),
        },
    }


def score_coupling(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Score coupling dimension (0-100).

    Factors:
    - Average distance from main sequence (lower is better)
    - Number of highly unstable modules (I>0.8, Ce>3)
    """
    if not metrics:
        return {"score": 100, "grade": "A", "factors": {}}

    distances = [m.get("distance", 0) for m in metrics]
    avg_distance = sum(distances) / len(distances) if distances else 0
    highly_unstable = sum(
        1 for m in metrics
        if m.get("instability", 0) > 0.8 and m.get("efferent_coupling", 0) > 3
    )

    score = 100.0
    score -= min(avg_distance * 60, 50)  # avg distance penalty, cap 50
    score -= min(highly_unstable * 2, 30)  # unstable module penalty, cap 30

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "avg_distance": round(avg_distance, 3),
            "highly_unstable_modules": highly_unstable,
            "total_modules": len(metrics),
        },
    }


def score_smells(
    smells: list[dict[str, Any]],
    total_lines: int,
) -> dict[str, Any]:
    """Score design smells dimension (0-100).

    Factors:
    - Smell density: smells per 1000 lines, weighted by severity
    - God class count (high-impact)
    """
    if total_lines == 0:
        return {"score": 100, "grade": "A", "factors": {}}

    severity_weights = {"high": 3, "medium": 1, "low": 0.5}
    weighted_count = sum(
        severity_weights.get(s.get("severity", "medium"), 1)
        for s in smells
    )
    density = (weighted_count / total_lines) * 1000
    god_classes = sum(1 for s in smells if s.get("type") == "god_class")

    score = 100.0
    score -= min(density * 8, 60)  # density penalty, cap 60
    score -= min(god_classes * 5, 25)  # god class penalty, cap 25

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "total_smells": len(smells),
            "weighted_density_per_1k": round(density, 2),
            "god_classes": god_classes,
        },
    }


def score_layers(violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Score layer discipline dimension (0-100).

    Simple: 100 minus 10 per violation, floor 0.
    """
    count = len(violations)
    score = max(0.0, 100.0 - count * 10)
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "total_violations": count,
        },
    }


def compute_overall(dimension_scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compute weighted overall score from dimension scores."""
    total = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        dim_score = dimension_scores.get(dim, {}).get("score", 100)
        total += dim_score * weight

    overall = round(total, 1)
    return {
        "score": overall,
        "grade": letter_grade(overall),
        "dimensions": dimension_scores,
        "weights": _DIMENSION_WEIGHTS,
    }
```

- [ ] **Step 2: Write tests for health_scoring**

Test each scoring function with known inputs and edge cases (empty inputs, perfect scores, worst-case scores). Test `letter_grade` boundaries. Test `compute_overall` weighted averaging.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_health_scoring.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/local_deepwiki/generators/analysis/health_scoring.py tests/test_health_scoring.py
git commit -m "feat: add health scoring module for architecture grading"
```

---

## Task 3: `get_architecture_health` composite tool

Runs all analysis functions in one call, scores each dimension, returns a graded summary with top findings.

**Files:**
- Create: `src/local_deepwiki/generators/analysis/architecture_health.py`
- Create: `tests/test_architecture_health.py`
- Modify: `src/local_deepwiki/models/tool_args.py` — add `GetArchitectureHealthArgs`
- Modify: `src/local_deepwiki/models/__init__.py` — re-export
- Modify: `src/local_deepwiki/tool_defs/analysis.py` — add Tool definition
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` — add handler
- Modify: `src/local_deepwiki/handlers/analysis.py` — re-export
- Modify: `src/local_deepwiki/handlers/__init__.py` — add to imports and `__all__`
- Modify: `src/local_deepwiki/server.py` — add to `TOOL_HANDLERS`

- [ ] **Step 1: Write architecture_health.py analysis module**

```python
# src/local_deepwiki/generators/analysis/architecture_health.py
"""Composite architecture health analysis.

Runs hotspots, coupling, design smells, and layer dependency analysis
in a single pass, then scores each dimension and computes an overall
health grade.

No LLM calls — composes existing pure-analysis functions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
from local_deepwiki.generators.analysis.design_smells import analyze_design_smells
from local_deepwiki.generators.analysis.health_scoring import (
    compute_overall,
    score_complexity,
    score_coupling,
    score_layers,
    score_smells,
)
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
from local_deepwiki.generators.analysis.layer_analysis import analyze_layer_dependencies
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# How many top findings to include per category in the summary.
_TOP_FINDINGS = 5


def analyze_architecture_health(
    repo_path: Path,
    project_name: str,
    *,
    top_findings: int = _TOP_FINDINGS,
) -> dict[str, Any]:
    """Run all architecture analyses and return a scored health report.

    Args:
        repo_path: Repository root.
        project_name: Project name for display.
        top_findings: Number of top findings per category.

    Returns:
        Dict with overall grade, dimension scores, and top findings.
    """
    # Count total lines for density calculations
    total_lines = 0
    for full_path, _rel in iter_python_files(repo_path, exclude_tests=True):
        try:
            total_lines += full_path.read_text(encoding="utf-8", errors="replace").count("\n")
        except OSError:
            continue

    # Run all analyses
    hotspot_result = analyze_hotspots(repo_path, metric="complexity", top_n=50)
    coupling_result = analyze_coupling_metrics(repo_path)
    smell_result = analyze_design_smells(repo_path, severity_threshold="medium")
    layer_result = analyze_layer_dependencies(repo_path, project_name)

    # Filter smells to source-only (exclude test/generated)
    src_smells = [
        s for s in smell_result.get("smells", [])
        if s.get("file", "").startswith("src/")
    ]

    # Score each dimension
    complexity_score = score_complexity(
        hotspot_result.get("hotspots", []),
        hotspot_result.get("stats", {}).get("total_functions", 0),
    )
    coupling_score_result = score_coupling(coupling_result.get("metrics", []))
    smell_score = score_smells(src_smells, total_lines)
    layer_score = score_layers(layer_result.get("violations", []))

    dimensions = {
        "complexity": complexity_score,
        "coupling": coupling_score_result,
        "smells": smell_score,
        "layers": layer_score,
    }
    overall = compute_overall(dimensions)

    # Build top findings
    top_hotspots = hotspot_result.get("hotspots", [])[:top_findings]
    top_smells_high = [s for s in src_smells if s.get("severity") == "high"][:top_findings]
    god_classes = [s for s in src_smells if s.get("type") == "god_class"]

    logger.info(
        "Architecture health: %s (%s) for %s",
        overall["grade"],
        overall["score"],
        repo_path,
    )

    return {
        "status": "success",
        "project_name": project_name,
        "overall": overall,
        "top_findings": {
            "hotspots": top_hotspots,
            "high_severity_smells": top_smells_high,
            "god_classes": god_classes,
            "layer_violations": layer_result.get("violations", [])[:top_findings],
        },
        "stats": {
            "total_lines": total_lines,
            "total_functions": hotspot_result.get("stats", {}).get("total_functions", 0),
            "files_scanned": hotspot_result.get("stats", {}).get("files_scanned", 0),
            "total_modules": coupling_result.get("stats", {}).get("total_modules", 0),
            "total_smells": len(src_smells),
        },
    }
```

- [ ] **Step 2: Add `GetArchitectureHealthArgs` to `models/tool_args.py`**

```python
class GetArchitectureHealthArgs(BaseModel):
    """Arguments for the get_architecture_health tool."""
    repo_path: str = Field(max_length=4096, description="Path to the repository")
    top_findings: int = Field(
        default=5, ge=1, le=20,
        description="Number of top findings per category (1-20)",
    )
```

Add re-export in `models/__init__.py`.

- [ ] **Step 3: Add Tool definition to `tool_defs/analysis.py`**

```python
Tool(
    name="get_architecture_health",
    description=(
        "Comprehensive architecture health check. Runs complexity hotspot "
        "analysis, coupling metrics, design smell detection, and layer "
        "dependency analysis in a single call. Returns an overall health "
        "grade (A-F), per-dimension scores, and top findings."
        "\n\nNo prior indexing required."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the repository to analyze",
            },
            "top_findings": {
                "type": "integer",
                "description": "Number of top findings per category (default: 5, max: 20)",
            },
        },
        "required": ["repo_path"],
    },
    annotations=_READ_ONLY,
),
```

- [ ] **Step 4: Add handler to `handlers/analysis_architecture.py`**

Follow the exact pattern of `handle_get_architecture_summary`. Use `@handle_tool_errors`, validate with Pydantic, resolve repo_path, lazy-import analysis module, return `make_tool_text_content`.

- [ ] **Step 5: Wire up registrations**

Add to `handlers/analysis.py` (re-export), `handlers/__init__.py` (import + `__all__`), `server.py` (`TOOL_HANDLERS`).

- [ ] **Step 6: Write tests**

Test with a tmp_path containing sample Python files. Verify overall grade is returned, dimension scores are 0-100, top_findings are present. Test empty repo returns grade A.

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_architecture_health.py -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git commit -m "feat: add get_architecture_health composite analysis tool"
```

---

## Task 4: `compare_architecture` git-diff tool

Compares architecture metrics between two git refs. Uses `git worktree` to safely analyze the base ref without modifying the working tree.

**Files:**
- Create: `src/local_deepwiki/generators/analysis/architecture_compare.py`
- Create: `tests/test_architecture_compare.py`
- Modify: `src/local_deepwiki/models/tool_args.py` — add `CompareArchitectureArgs`
- Modify: `src/local_deepwiki/models/__init__.py` — re-export
- Modify: `src/local_deepwiki/tool_defs/analysis.py` — add Tool definition
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` — add handler
- Modify: `src/local_deepwiki/handlers/analysis.py` — re-export
- Modify: `src/local_deepwiki/handlers/__init__.py` — add to imports and `__all__`
- Modify: `src/local_deepwiki/server.py` — add to `TOOL_HANDLERS`

- [ ] **Step 1: Write architecture_compare.py**

Key design decisions:
- Use `git worktree add <tmpdir> <base_ref> --detach` to create a temporary copy at the base ref
- Run `analyze_architecture_health()` on both the current tree and the worktree
- Compute deltas (score changes, new/resolved smells, new/resolved hotspots)
- Clean up worktree with `git worktree remove`
- Falls back to error message if git worktree fails (e.g., shallow clone)

```python
# src/local_deepwiki/generators/analysis/architecture_compare.py
"""Architecture comparison between two git refs.

Uses git worktree to safely analyze a base ref without modifying
the current working tree. Returns metric deltas and new/resolved findings.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.architecture_health import (
    analyze_architecture_health,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_GIT_TIMEOUT = 30


def _create_worktree(repo_path: Path, ref: str, target_dir: Path) -> bool:
    """Create a detached git worktree at *ref* in *target_dir*."""
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(target_dir), ref],
            cwd=str(repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Failed to create worktree for %s: %s", ref, e)
        return False


def _remove_worktree(repo_path: Path, target_dir: Path) -> None:
    """Remove a git worktree and clean up."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target_dir)],
            cwd=str(repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # Belt and suspenders: remove directory if worktree removal failed
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)


def _resolve_ref(repo_path: Path, ref: str) -> str | None:
    """Resolve a git ref to a short SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", ref],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _compute_deltas(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Compute metric deltas between base and head health reports."""
    base_overall = base.get("overall", {})
    head_overall = head.get("overall", {})

    dimension_deltas = {}
    for dim in ("complexity", "coupling", "smells", "layers"):
        base_score = base_overall.get("dimensions", {}).get(dim, {}).get("score", 0)
        head_score = head_overall.get("dimensions", {}).get(dim, {}).get("score", 0)
        delta = round(head_score - base_score, 1)
        dimension_deltas[dim] = {
            "base_score": base_score,
            "head_score": head_score,
            "delta": delta,
            "trend": "improved" if delta > 0 else "degraded" if delta < 0 else "unchanged",
        }

    # New and resolved smells
    base_smells = {
        (s.get("file"), s.get("line"), s.get("type"))
        for s in base.get("top_findings", {}).get("high_severity_smells", [])
    }
    head_smells = {
        (s.get("file"), s.get("line"), s.get("type"))
        for s in head.get("top_findings", {}).get("high_severity_smells", [])
    }
    new_smell_keys = head_smells - base_smells
    resolved_smell_keys = base_smells - head_smells

    return {
        "overall_delta": round(
            head_overall.get("score", 0) - base_overall.get("score", 0), 1
        ),
        "base_grade": base_overall.get("grade", "?"),
        "head_grade": head_overall.get("grade", "?"),
        "dimensions": dimension_deltas,
        "new_high_smells": len(new_smell_keys),
        "resolved_high_smells": len(resolved_smell_keys),
    }


def compare_architecture(
    repo_path: Path,
    project_name: str,
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
) -> dict[str, Any]:
    """Compare architecture health between two git refs.

    Args:
        repo_path: Repository root (must be a git repo).
        project_name: Project name for display.
        base_ref: Git ref for the baseline (default: HEAD~1).
        head_ref: Git ref for the comparison target (default: HEAD).

    Returns:
        Dict with base/head scores, deltas, and trend indicators.
    """
    base_sha = _resolve_ref(repo_path, base_ref)
    head_sha = _resolve_ref(repo_path, head_ref)

    if not base_sha:
        return {"status": "error", "message": f"Could not resolve git ref: {base_ref}"}
    if not head_sha:
        return {"status": "error", "message": f"Could not resolve git ref: {head_ref}"}

    # Analyze HEAD (current working tree or specified ref)
    if head_ref == "HEAD":
        head_health = analyze_architecture_health(repo_path, project_name)
    else:
        tmp_head = Path(tempfile.mkdtemp(prefix="deepwiki_head_"))
        try:
            if not _create_worktree(repo_path, head_ref, tmp_head):
                return {"status": "error", "message": f"Cannot create worktree for {head_ref}"}
            head_health = analyze_architecture_health(tmp_head, project_name)
        finally:
            _remove_worktree(repo_path, tmp_head)

    # Analyze base ref via worktree
    tmp_base = Path(tempfile.mkdtemp(prefix="deepwiki_base_"))
    try:
        if not _create_worktree(repo_path, base_ref, tmp_base):
            return {"status": "error", "message": f"Cannot create worktree for {base_ref}. Is this a shallow clone?"}
        base_health = analyze_architecture_health(tmp_base, project_name)
    finally:
        _remove_worktree(repo_path, tmp_base)

    deltas = _compute_deltas(base_health, head_health)

    logger.info(
        "Architecture comparison %s..%s: %s -> %s (delta: %+.1f)",
        base_sha, head_sha,
        deltas["base_grade"], deltas["head_grade"],
        deltas["overall_delta"],
    )

    return {
        "status": "success",
        "project_name": project_name,
        "base_ref": {"ref": base_ref, "sha": base_sha},
        "head_ref": {"ref": head_ref, "sha": head_sha},
        "deltas": deltas,
        "base_health": base_health.get("overall", {}),
        "head_health": head_health.get("overall", {}),
    }
```

- [ ] **Step 2: Add `CompareArchitectureArgs` model**

```python
class CompareArchitectureArgs(BaseModel):
    """Arguments for the compare_architecture tool."""
    repo_path: str = Field(max_length=4096, description="Path to the repository (must be a git repo)")
    base_ref: str = Field(default="HEAD~1", max_length=256, description="Git ref for baseline")
    head_ref: str = Field(default="HEAD", max_length=256, description="Git ref for comparison target")
```

- [ ] **Step 3: Add Tool definition, handler, registrations**

Tool description: "Compare architecture health between two git refs. Shows which metrics improved or degraded, grade changes, and new/resolved smells. Uses git worktree for safe non-destructive analysis.\n\nNo prior indexing required."

- [ ] **Step 4: Write tests**

Test `_compute_deltas` with mock health reports. Test `_resolve_ref` with a real git repo (tmp_path with `git init`). Test `compare_architecture` integration with a small git repo that has two commits.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_architecture_compare.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add compare_architecture tool for git-based metric diffing"
```

---

## Task 5: `get_module_health` focused analysis tool

Zooms into a single module and reports its coupling, complexity distribution, smells, and dependents.

**Files:**
- Create: `src/local_deepwiki/generators/analysis/module_health.py`
- Create: `tests/test_module_health.py`
- Modify: `src/local_deepwiki/models/tool_args.py` — add `GetModuleHealthArgs`
- Modify: `src/local_deepwiki/models/__init__.py` — re-export
- Modify: `src/local_deepwiki/tool_defs/analysis.py` — add Tool definition
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` — add handler
- Modify: `src/local_deepwiki/handlers/analysis.py` — re-export
- Modify: `src/local_deepwiki/handlers/__init__.py` — add to imports and `__all__`
- Modify: `src/local_deepwiki/server.py` — add to `TOOL_HANDLERS`

- [ ] **Step 1: Write module_health.py**

Key features:
- Takes a `module_name` (e.g., `core.indexer`, `generators.wiki`)
- Filters hotspots, smells, coupling to just that module's files
- Lists which other modules depend on it (afferent) and what it depends on (efferent)
- Returns a module-level health score using the same scoring functions
- Includes a "refactoring risk" indicator based on afferent coupling (high Ca = risky to change)

```python
# src/local_deepwiki/generators/analysis/module_health.py
"""Per-module health analysis.

Zooms into a single module and reports its coupling, complexity
distribution, smells, and dependents.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics
from local_deepwiki.generators.analysis.design_smells import analyze_design_smells
from local_deepwiki.generators.analysis.health_scoring import (
    letter_grade,
    score_complexity,
    score_smells,
)
from local_deepwiki.generators.analysis.hotspots import analyze_hotspots
from local_deepwiki.generators.analysis.module_dependencies import (
    analyze_cross_module_dependencies,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


def _refactoring_risk(afferent_coupling: int) -> str:
    """Estimate risk of refactoring based on how many modules depend on this one."""
    if afferent_coupling >= 15:
        return "high"
    if afferent_coupling >= 5:
        return "medium"
    return "low"


def analyze_module_health(
    repo_path: Path,
    module_name: str,
) -> dict[str, Any]:
    """Analyze health of a single module.

    Args:
        repo_path: Repository root.
        module_name: Module identifier (e.g., 'core.indexer', 'generators.wiki').

    Returns:
        Dict with module coupling, complexity, smells, dependents, and health score.
    """
    # Run analyses filtered/scoped to this module
    hotspot_result = analyze_hotspots(repo_path, metric="complexity", top_n=100)
    smell_result = analyze_design_smells(repo_path, severity_threshold="low")
    coupling_result = analyze_coupling_metrics(repo_path, module_filter=module_name)
    deps_result = analyze_cross_module_dependencies(repo_path, module_filter=module_name)

    # Filter hotspots to this module's files
    module_path_prefix = module_name.replace(".", "/")
    module_hotspots = [
        h for h in hotspot_result.get("hotspots", [])
        if module_path_prefix in h.get("file", "")
    ]

    # Filter smells to this module's files
    module_smells = [
        s for s in smell_result.get("smells", [])
        if module_path_prefix in s.get("file", "")
    ]

    # Find this module's coupling metrics
    module_coupling = None
    for m in coupling_result.get("metrics", []):
        if m.get("module") == module_name:
            module_coupling = m
            break

    # Compute module-level scores
    total_functions = len(module_hotspots)
    complexity_score = score_complexity(module_hotspots, total_functions)

    total_lines = sum(
        h.get("details", {}).get("length", 0) for h in module_hotspots
    )
    smell_score = score_smells(module_smells, max(total_lines, 1))

    # Overall module score (simple average of complexity + smells)
    avg_score = (complexity_score["score"] + smell_score["score"]) / 2
    ca = module_coupling.get("afferent_coupling", 0) if module_coupling else 0

    # Find dependents and dependencies from the edge list
    dependents = []
    dependencies = []
    for edge in deps_result.get("edges", []):
        if edge.get("target") == module_name:
            dependents.append({"module": edge["source"], "weight": edge["weight"]})
        elif edge.get("source") == module_name:
            dependencies.append({"module": edge["target"], "weight": edge["weight"]})

    dependents.sort(key=lambda d: d["weight"], reverse=True)
    dependencies.sort(key=lambda d: d["weight"], reverse=True)

    logger.info("Module health for %s: score=%.1f", module_name, avg_score)

    return {
        "status": "success",
        "module": module_name,
        "health": {
            "score": round(avg_score, 1),
            "grade": letter_grade(avg_score),
            "complexity": complexity_score,
            "smells": smell_score,
        },
        "coupling": module_coupling or {"afferent_coupling": 0, "efferent_coupling": 0, "instability": 0, "abstractness": 0, "distance": 0},
        "refactoring_risk": _refactoring_risk(ca),
        "hotspots": module_hotspots[:10],
        "smells": module_smells,
        "dependents": dependents,
        "dependencies": dependencies,
        "stats": {
            "functions": total_functions,
            "smells_count": len(module_smells),
            "dependents_count": len(dependents),
            "dependencies_count": len(dependencies),
        },
    }
```

- [ ] **Step 2: Add `GetModuleHealthArgs` model**

```python
class GetModuleHealthArgs(BaseModel):
    """Arguments for the get_module_health tool."""
    repo_path: str = Field(max_length=4096, description="Path to the repository")
    module_name: str = Field(
        min_length=1, max_length=500,
        description="Module to analyze (e.g., 'core.indexer', 'generators.wiki')",
    )
```

- [ ] **Step 3: Add Tool definition, handler, registrations**

Tool description: "Deep health analysis of a single module. Shows complexity distribution, design smells, coupling metrics, dependents (who uses this module), dependencies (what it uses), and refactoring risk level.\n\nNo prior indexing required."

- [ ] **Step 4: Write tests**

Test with a tmp_path repo containing a module structure. Verify health score, coupling, refactoring_risk, and dependents/dependencies are returned correctly.

- [ ] **Step 5: Run tests and full suite**

Run: `uv run pytest tests/test_module_health.py -v`
Then: `uv run pytest tests/ -q` for full suite

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add get_module_health tool for per-module analysis"
```

---

## Task 6: Final verification and cleanup

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -q`
Expected: All previously-passing tests still pass + new tests pass

- [ ] **Step 2: Verify tool registration consistency**

```bash
uv run python -c "from local_deepwiki.server import _validate_tool_handler_consistency; _validate_tool_handler_consistency(); print('OK')"
```

- [ ] **Step 3: Verify new tools work end-to-end**

```bash
uv run python -c "
import asyncio, json
from unittest.mock import patch
from local_deepwiki.handlers.analysis_architecture import handle_get_architecture_health
async def main():
    with patch('local_deepwiki.handlers.analysis_architecture.get_access_controller'):
        r = await handle_get_architecture_health({'repo_path': '.'})
        data = json.loads(r[0].text)
        print(f'Health: {data[\"overall\"][\"grade\"]} ({data[\"overall\"][\"score\"]})')
asyncio.run(main())
"
```

- [ ] **Step 4: Commit final state**

```bash
git commit -m "chore: final verification of architecture tools v2"
```

---

## Execution Order

Tasks 1-2 are prerequisites. Tasks 3-5 can be done sequentially (they share registration files).

```
Task 1 (source_filter) ──→ Task 3 (architecture_health) ──→ Task 6 (verify)
Task 2 (health_scoring) ─┘  Task 4 (compare_architecture) ─┘
                             Task 5 (module_health) ────────┘
```

Tasks 1 and 2 are independent and can be done in parallel.
Tasks 3, 4, 5 must be sequential (shared registration files).

---

## Future Work (not in this plan)

- **`get_architecture_narrative`** — LLM-powered written evaluation from raw metrics. Different category (requires LLM provider). Worth adding once the data tools are solid.
- **`get_trend_report`** — Scan N git tags/commits and show metric trends over time. Computationally expensive (runs full analysis per ref). Could use cached results or sampling.
- **Agentic data integration** — Add tool keywords to `handlers/agentic_data.py` so `find_tools` and `suggest_next_actions` recommend the new tools contextually.
