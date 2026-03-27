# Phase 3a: Health Trend Tracking + CI Quality Gates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JSONL-based health snapshot storage, a `deepwiki check` CLI for CI quality gates, a `get_architecture_trends` MCP tool, and auto-snapshot in `deepwiki update`.

**Architecture:** Three independent units: (1) `core/health_history.py` storage layer with save/load/get_latest, (2) `cli/check_cli.py` CLI that reads thresholds from pyproject.toml and exits 0/1/2, (3) MCP handler for trends. The storage layer is shared by all three consumers (check CLI, update CLI, MCP tool). No new dependencies — uses `tomllib` (stdlib) and JSONL.

**Tech Stack:** Python 3.11+, tomllib, Pydantic, FastMCP, Rich, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-27-phase3a-trends-check-design.md`

---

### Task 1: Create health history storage layer

**Files:**
- Create: `src/local_deepwiki/core/health_history.py`
- Create: `tests/test_health_history.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_health_history.py
"""Tests for the health history JSONL storage layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_health_data(score=61.4, grade="C"):
    """Build minimal health_data matching analyze_architecture_health output."""
    return {
        "status": "success",
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": {
                "complexity": {"score": 77.5, "grade": "B", "factors": {}},
                "coupling": {"score": 44.4, "grade": "D", "factors": {}},
                "smells": {"score": 28.3, "grade": "F", "factors": {}},
                "layers": {"score": 100.0, "grade": "A", "factors": {}},
            },
            "weights": {"complexity": 0.3, "coupling": 0.25},
        },
    }


def test_save_snapshot_creates_file(tmp_path):
    """save_snapshot creates JSONL file with correct shape."""
    from local_deepwiki.core.health_history import save_snapshot

    save_snapshot(tmp_path, _make_health_data())
    history_file = tmp_path / "health-history.jsonl"
    assert history_file.exists()
    snapshot = json.loads(history_file.read_text().strip())
    assert snapshot["score"] == 61.4
    assert snapshot["grade"] == "C"
    assert "timestamp" in snapshot
    assert "git_ref" in snapshot
    # Dimensions should be stripped of factors/weights
    assert "factors" not in snapshot["dimensions"]["complexity"]
    assert "weights" not in snapshot


def test_save_snapshot_appends(tmp_path):
    """save_snapshot appends, doesn't overwrite."""
    from local_deepwiki.core.health_history import save_snapshot

    save_snapshot(tmp_path, _make_health_data(score=60, grade="C"))
    save_snapshot(tmp_path, _make_health_data(score=70, grade="B"))
    lines = (tmp_path / "health-history.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["score"] == 60
    assert json.loads(lines[1])["score"] == 70


def test_save_snapshot_missing_overall(tmp_path):
    """save_snapshot is a no-op when health_data has no 'overall' key."""
    from local_deepwiki.core.health_history import save_snapshot

    save_snapshot(tmp_path, {"status": "error"})
    assert not (tmp_path / "health-history.jsonl").exists()


def test_load_snapshots_empty(tmp_path):
    """load_snapshots returns empty list when no file exists."""
    from local_deepwiki.core.health_history import load_snapshots

    assert load_snapshots(tmp_path) == []


def test_load_snapshots_returns_all(tmp_path):
    """load_snapshots returns all snapshots in chronological order."""
    from local_deepwiki.core.health_history import save_snapshot, load_snapshots

    save_snapshot(tmp_path, _make_health_data(score=60, grade="C"))
    save_snapshot(tmp_path, _make_health_data(score=70, grade="B"))
    snapshots = load_snapshots(tmp_path)
    assert len(snapshots) == 2
    assert snapshots[0]["score"] == 60
    assert snapshots[1]["score"] == 70


def test_load_snapshots_since_filter(tmp_path):
    """load_snapshots with since filters correctly."""
    from local_deepwiki.core.health_history import load_snapshots

    history_file = tmp_path / "health-history.jsonl"
    history_file.write_text(
        '{"timestamp":"2026-03-01T10:00:00Z","score":60,"grade":"C","dimensions":{}}\n'
        '{"timestamp":"2026-03-15T10:00:00Z","score":65,"grade":"C","dimensions":{}}\n'
        '{"timestamp":"2026-03-25T10:00:00Z","score":70,"grade":"B","dimensions":{}}\n'
    )
    snapshots = load_snapshots(tmp_path, since="2026-03-10")
    assert len(snapshots) == 2
    assert snapshots[0]["score"] == 65


def test_load_snapshots_skips_malformed(tmp_path):
    """load_snapshots skips malformed lines without crashing."""
    from local_deepwiki.core.health_history import load_snapshots

    history_file = tmp_path / "health-history.jsonl"
    history_file.write_text(
        '{"timestamp":"2026-03-01T10:00:00Z","score":60,"grade":"C","dimensions":{}}\n'
        'this is not json\n'
        '{"timestamp":"2026-03-25T10:00:00Z","score":70,"grade":"B","dimensions":{}}\n'
    )
    snapshots = load_snapshots(tmp_path)
    assert len(snapshots) == 2


def test_get_latest(tmp_path):
    """get_latest returns most recent snapshot."""
    from local_deepwiki.core.health_history import save_snapshot, get_latest

    save_snapshot(tmp_path, _make_health_data(score=60, grade="C"))
    save_snapshot(tmp_path, _make_health_data(score=70, grade="B"))
    latest = get_latest(tmp_path)
    assert latest is not None
    assert latest["score"] == 70


def test_get_latest_no_history(tmp_path):
    """get_latest returns None when no history."""
    from local_deepwiki.core.health_history import get_latest

    assert get_latest(tmp_path) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_health_history.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement health history storage**

Create `src/local_deepwiki/core/health_history.py`:

```python
"""Health history JSONL storage for architecture trend tracking.

Append-only storage at .deepwiki/health-history.jsonl. Each line is one
JSON object with timestamp, git ref, overall score/grade, and per-dimension
scores.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_HISTORY_FILENAME = "health-history.jsonl"


def save_snapshot(wiki_path: Path, health_data: dict[str, Any]) -> None:
    """Extract and append a health snapshot to the JSONL history file.

    No-op if health_data is missing the 'overall' key.
    """
    overall = health_data.get("overall")
    if overall is None:
        return

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_ref": _get_short_git_ref(wiki_path),
        "score": overall["score"],
        "grade": overall["grade"],
        "dimensions": {
            name: {"score": dim["score"], "grade": dim["grade"]}
            for name, dim in overall.get("dimensions", {}).items()
        },
    }

    history_file = wiki_path / _HISTORY_FILENAME
    wiki_path.mkdir(parents=True, exist_ok=True)
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")

    logger.debug("Health snapshot saved: %s (%s)", overall["grade"], overall["score"])


def load_snapshots(
    wiki_path: Path,
    *,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """Load snapshots from JSONL file, optionally filtered by timestamp.

    Args:
        wiki_path: Path to .deepwiki directory.
        since: ISO date/datetime string. Only snapshots at or after this
            timestamp are included. Comparison is string-based (ISO sorts
            lexicographically).

    Returns:
        List of snapshot dicts sorted by timestamp ascending.
        Empty list if file doesn't exist.
    """
    history_file = wiki_path / _HISTORY_FILENAME
    if not history_file.exists():
        return []

    snapshots: list[dict[str, Any]] = []
    for line in history_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            snapshot = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed JSONL line: %s", line[:80])
            continue
        if since and snapshot.get("timestamp", "") < since:
            continue
        snapshots.append(snapshot)

    snapshots.sort(key=lambda s: s.get("timestamp", ""))
    return snapshots


def get_latest(wiki_path: Path) -> dict[str, Any] | None:
    """Return the most recent snapshot, or None if no history."""
    snapshots = load_snapshots(wiki_path)
    return snapshots[-1] if snapshots else None


def _get_short_git_ref(wiki_path: Path) -> str:
    """Get short git ref, falling back to 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(wiki_path.parent) if wiki_path.exists() else ".",
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_health_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/core/health_history.py tests/test_health_history.py
git commit -m "feat: add health history JSONL storage layer"
```

---

### Task 2: Create `deepwiki check` CLI

**Files:**
- Create: `src/local_deepwiki/cli/check_cli.py`
- Modify: `src/local_deepwiki/cli/main.py` (add to SUBCOMMANDS)
- Create: `tests/test_check_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_check_cli.py
"""Tests for the deepwiki check CLI quality gate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_health_result(score=61.4, grade="C", dimensions=None):
    """Build a health result matching analyze_architecture_health output."""
    dims = dimensions or {
        "complexity": {"score": 77.5, "grade": "B", "factors": {}},
        "coupling": {"score": 44.4, "grade": "D", "factors": {}},
        "smells": {"score": 28.3, "grade": "F", "factors": {}},
        "layers": {"score": 100.0, "grade": "A", "factors": {}},
    }
    return {
        "status": "success",
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": dims,
        },
        "stats": {"total_lines": 10000},
    }


@pytest.fixture
def repo_with_pyproject(tmp_path):
    """Create a repo with pyproject.toml containing check thresholds."""
    (tmp_path / "mod.py").write_text("x = 1\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.deepwiki.check]\n"
        'min_grade = "C"\n'
        "min_score = 50\n"
        "min_complexity = 40\n"
        "min_coupling = 40\n"
        "min_smells = 40\n"
        "min_layers = 40\n"
    )
    return tmp_path


def test_check_exit_0_all_pass(repo_with_pyproject):
    """Exit 0 when all thresholds pass."""
    from local_deepwiki.cli.check_cli import run_check

    health = _make_health_result(
        score=80, grade="B",
        dimensions={
            "complexity": {"score": 80, "grade": "B", "factors": {}},
            "coupling": {"score": 70, "grade": "B", "factors": {}},
            "smells": {"score": 60, "grade": "C", "factors": {}},
            "layers": {"score": 100, "grade": "A", "factors": {}},
        },
    )
    with patch(
        "local_deepwiki.cli.check_cli.analyze_architecture_health",
        return_value=health,
    ):
        result = run_check(repo_with_pyproject)
    assert result == 0


def test_check_exit_1_grade_below(repo_with_pyproject):
    """Exit 1 when overall grade is below min_grade."""
    from local_deepwiki.cli.check_cli import run_check

    health = _make_health_result(score=45, grade="D")
    with patch(
        "local_deepwiki.cli.check_cli.analyze_architecture_health",
        return_value=health,
    ):
        result = run_check(repo_with_pyproject)
    assert result == 1


def test_check_exit_1_dimension_below(repo_with_pyproject):
    """Exit 1 when a dimension score is below its threshold."""
    from local_deepwiki.cli.check_cli import run_check

    health = _make_health_result(score=70, grade="B")
    with patch(
        "local_deepwiki.cli.check_cli.analyze_architecture_health",
        return_value=health,
    ):
        result = run_check(repo_with_pyproject)
    # smells=28.3 < min_smells=40 → FAIL
    assert result == 1


def test_check_exit_0_no_config(tmp_path):
    """Exit 0 when no pyproject.toml exists (no thresholds = pass)."""
    from local_deepwiki.cli.check_cli import run_check

    (tmp_path / "mod.py").write_text("x = 1\n")
    health = _make_health_result(score=30, grade="F")
    with patch(
        "local_deepwiki.cli.check_cli.analyze_architecture_health",
        return_value=health,
    ):
        result = run_check(tmp_path)
    assert result == 0


def test_check_exit_2_missing_repo(tmp_path):
    """Exit 2 when repo path doesn't exist."""
    from local_deepwiki.cli.check_cli import run_check

    result = run_check(tmp_path / "nonexistent")
    assert result == 2


def test_check_json_output(repo_with_pyproject, capsys):
    """--json flag produces valid JSON with violations array."""
    from local_deepwiki.cli.check_cli import run_check

    health = _make_health_result(score=70, grade="B")
    with patch(
        "local_deepwiki.cli.check_cli.analyze_architecture_health",
        return_value=health,
    ):
        run_check(repo_with_pyproject, json_output=True)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] in ("pass", "fail")
    assert "violations" in data


def test_check_saves_snapshot(repo_with_pyproject):
    """Check saves a health snapshot as side effect."""
    from local_deepwiki.cli.check_cli import run_check

    health = _make_health_result(score=80, grade="B",
        dimensions={
            "complexity": {"score": 80, "grade": "B", "factors": {}},
            "coupling": {"score": 70, "grade": "B", "factors": {}},
            "smells": {"score": 60, "grade": "C", "factors": {}},
            "layers": {"score": 100, "grade": "A", "factors": {}},
        },
    )
    with patch(
        "local_deepwiki.cli.check_cli.analyze_architecture_health",
        return_value=health,
    ):
        run_check(repo_with_pyproject)
    wiki_path = repo_with_pyproject / ".deepwiki"
    assert (wiki_path / "health-history.jsonl").exists()


def test_check_grade_comparison():
    """Grade comparison is ordinal: A > B > C > D > F."""
    from local_deepwiki.cli.check_cli import _grade_passes

    assert _grade_passes("A", "C") is True
    assert _grade_passes("B", "C") is True
    assert _grade_passes("C", "C") is True
    assert _grade_passes("D", "C") is False
    assert _grade_passes("F", "C") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_check_cli.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement check CLI**

Create `src/local_deepwiki/cli/check_cli.py`:

```python
"""CLI quality gate: deepwiki check.

Runs architecture health analysis, compares against thresholds from
pyproject.toml, and exits with 0 (pass), 1 (fail), or 2 (error).
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from local_deepwiki.generators.analysis.architecture_health import (
    analyze_architecture_health,
)
from local_deepwiki.generators.manifest import get_cached_manifest
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
_DIMENSION_KEYS = ("complexity", "coupling", "smells", "layers")


def _grade_passes(actual: str, min_grade: str) -> bool:
    """Check if actual grade is at or above min_grade."""
    return _GRADE_ORDER.get(actual, -1) >= _GRADE_ORDER.get(min_grade, -1)


def _load_thresholds(repo_path: Path) -> dict[str, Any]:
    """Load check thresholds from pyproject.toml."""
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        return data.get("tool", {}).get("deepwiki", {}).get("check", {})
    except Exception:
        return {}


def _check_thresholds(
    health_data: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare health scores against thresholds, return list of violations."""
    violations: list[dict[str, Any]] = []
    overall = health_data.get("overall", {})
    dims = overall.get("dimensions", {})

    # Check overall grade
    min_grade = thresholds.get("min_grade")
    if min_grade and not _grade_passes(overall.get("grade", "F"), min_grade):
        violations.append({
            "dimension": "overall",
            "type": "grade",
            "grade": overall.get("grade", "?"),
            "min_grade": min_grade,
        })

    # Check overall score
    min_score = thresholds.get("min_score")
    if min_score is not None and overall.get("score", 0) < min_score:
        violations.append({
            "dimension": "overall",
            "type": "score",
            "score": overall.get("score", 0),
            "threshold": min_score,
        })

    # Check per-dimension scores
    for dim in _DIMENSION_KEYS:
        threshold_key = f"min_{dim}"
        threshold = thresholds.get(threshold_key)
        if threshold is not None:
            dim_score = dims.get(dim, {}).get("score", 0)
            if dim_score < threshold:
                violations.append({
                    "dimension": dim,
                    "type": "score",
                    "score": dim_score,
                    "threshold": threshold,
                })

    return violations


def run_check(
    repo_path: Path,
    *,
    json_output: bool = False,
    console: Console | None = None,
) -> int:
    """Run the quality gate check. Returns exit code 0, 1, or 2."""
    console = console or Console(stderr=True)
    repo_path = repo_path.resolve()

    if not repo_path.is_dir():
        if json_output:
            print(json.dumps({"status": "error", "message": "Repository not found"}))
        else:
            console.print(f"[red]Not a directory: {repo_path}[/red]")
        return 2

    thresholds = _load_thresholds(repo_path)

    try:
        manifest = get_cached_manifest(repo_path)
        project_name = manifest.name or repo_path.name
        health = analyze_architecture_health(repo_path, project_name)
    except Exception as e:
        if json_output:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Analysis failed: {e}[/red]")
        return 2

    # Save snapshot (non-critical)
    try:
        from local_deepwiki.core.health_history import save_snapshot

        wiki_path = repo_path / ".deepwiki"
        save_snapshot(wiki_path, health)
    except Exception:
        pass

    violations = _check_thresholds(health, thresholds)
    overall = health.get("overall", {})
    dims = overall.get("dimensions", {})

    if json_output:
        output = {
            "status": "fail" if violations else "pass",
            "overall": {"score": overall.get("score"), "grade": overall.get("grade")},
            "dimensions": {
                name: {"score": d.get("score"), "grade": d.get("grade")}
                for name, d in dims.items()
            },
            "violations": violations,
        }
        print(json.dumps(output, indent=2))
    else:
        _print_table(console, project_name, overall, dims, thresholds, violations)

    return 1 if violations else 0


def _print_table(
    console: Console,
    project_name: str,
    overall: dict[str, Any],
    dims: dict[str, Any],
    thresholds: dict[str, Any],
    violations: list[dict[str, Any]],
) -> None:
    """Print a rich table with pass/fail per dimension."""
    console.print(f"\n[bold]Architecture Health Check — {project_name}[/bold]\n")
    console.print(
        f"Overall: {overall.get('grade', '?')} "
        f"({overall.get('score', '?')}/100)\n"
    )

    table = Table(show_header=True)
    table.add_column("Dimension")
    table.add_column("Score", justify="right")
    table.add_column("Grade")
    table.add_column("Threshold", justify="right")
    table.add_column("Status")

    violated_dims = {v["dimension"] for v in violations}

    for dim in _DIMENSION_KEYS:
        d = dims.get(dim, {})
        threshold_key = f"min_{dim}"
        threshold = thresholds.get(threshold_key)
        threshold_str = str(threshold) if threshold is not None else "—"
        status = (
            "[red]FAIL[/red]" if dim in violated_dims else "[green]PASS[/green]"
        )
        table.add_row(
            dim.title(),
            f"{d.get('score', '?')}",
            d.get("grade", "?"),
            threshold_str,
            status,
        )

    console.print(table)

    if violations:
        reasons = []
        for v in violations:
            if v["type"] == "grade":
                reasons.append(
                    f"{v['dimension']} grade {v['grade']} below {v['min_grade']}"
                )
            else:
                reasons.append(
                    f"{v['dimension']} score {v['score']} below threshold {v['threshold']}"
                )
        console.print(f"\n[red]Result: FAIL ({'; '.join(reasons)})[/red]")
    else:
        console.print("\n[green]Result: PASS[/green]")


def main() -> int:
    """Main entry point for ``deepwiki check``."""
    parser = argparse.ArgumentParser(
        prog="deepwiki check",
        description="Run architecture quality gate",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository path (default: current directory)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output results as JSON (for CI parsing)",
    )
    args = parser.parse_args()
    return run_check(Path(args.repo_path), json_output=args.json_output)
```

- [ ] **Step 4: Register in CLI dispatcher**

In `src/local_deepwiki/cli/main.py`, add to `SUBCOMMANDS`:

```python
"check": ("local_deepwiki.cli.check_cli", "main", "Run architecture quality gate"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_check_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/cli/check_cli.py src/local_deepwiki/cli/main.py tests/test_check_cli.py
git commit -m "feat: add deepwiki check CLI quality gate"
```

---

### Task 3: Create `get_architecture_trends` MCP tool

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py` (add `GetArchitectureTrendsArgs`)
- Modify: `src/local_deepwiki/models/__init__.py` (export)
- Modify: `src/local_deepwiki/tool_defs/analysis.py` (add tool def)
- Modify: `src/local_deepwiki/handlers/analysis_architecture.py` (add handler)
- Modify: `src/local_deepwiki/handlers/analysis.py` (export)
- Modify: `src/local_deepwiki/handlers/__init__.py` (export)
- Modify: `src/local_deepwiki/server.py` (register)
- Create: `tests/test_architecture_trends.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_architecture_trends.py
"""Tests for the get_architecture_trends MCP tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.core.health_history import save_snapshot


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


def _make_health(score, grade):
    return {
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": {
                "complexity": {"score": 80, "grade": "B"},
                "coupling": {"score": 50, "grade": "D"},
                "smells": {"score": 40, "grade": "D"},
                "layers": {"score": 100, "grade": "A"},
            },
        },
    }


@pytest.fixture
def repo_with_history(tmp_path):
    """Create repo with .deepwiki and 3 snapshots."""
    wiki = tmp_path / ".deepwiki"
    wiki.mkdir()
    history = wiki / "health-history.jsonl"
    history.write_text(
        '{"timestamp":"2026-03-01T10:00:00Z","git_ref":"aaa","score":55,"grade":"D","dimensions":{}}\n'
        '{"timestamp":"2026-03-15T10:00:00Z","git_ref":"bbb","score":62,"grade":"C","dimensions":{}}\n'
        '{"timestamp":"2026-03-25T10:00:00Z","git_ref":"ccc","score":70,"grade":"B","dimensions":{}}\n'
    )
    return tmp_path


async def test_trends_returns_snapshots(mock_access_control, repo_with_history):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_trends,
    )

    result = await handle_get_architecture_trends(
        {"repo_path": str(repo_with_history), "since": "2026-01-01"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data["snapshots"]) == 3
    assert data["summary"]["snapshot_count"] == 3


async def test_trends_since_filter(mock_access_control, repo_with_history):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_trends,
    )

    result = await handle_get_architecture_trends(
        {"repo_path": str(repo_with_history), "since": "2026-03-10"}
    )
    data = json.loads(result[0].text)
    assert len(data["snapshots"]) == 2


async def test_trends_no_history(mock_access_control, tmp_path):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_trends,
    )

    (tmp_path / ".deepwiki").mkdir()
    result = await handle_get_architecture_trends(
        {"repo_path": str(tmp_path), "since": "2026-01-01"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["snapshots"] == []
    assert data["summary"] is None


async def test_trends_missing_repo(mock_access_control, tmp_path):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_trends,
    )

    result = await handle_get_architecture_trends(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_trends_score_change(mock_access_control, repo_with_history):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_trends,
    )

    result = await handle_get_architecture_trends(
        {"repo_path": str(repo_with_history), "since": "2026-01-01"}
    )
    data = json.loads(result[0].text)
    # score_change = last (70) - first (55) = 15
    assert data["summary"]["score_change"] == 15
    assert data["summary"]["current_grade"] == "B"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_architecture_trends.py -v`
Expected: FAIL

- [ ] **Step 3: Add args model**

In `src/local_deepwiki/models/tool_args.py`, add after `GetRecommendationsArgs`:

```python
class GetArchitectureTrendsArgs(BaseModel):
    """Arguments for the get_architecture_trends tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    since: str | None = Field(
        default=None,
        description="ISO date to filter from (e.g., '2026-03-01'). Default: last 30 days",
    )
```

Export from `models/__init__.py`.

- [ ] **Step 4: Add tool definition**

In `src/local_deepwiki/tool_defs/analysis.py`, add the tool definition from the spec (Section 3.4).

- [ ] **Step 5: Add handler**

In `src/local_deepwiki/handlers/analysis_architecture.py`:

1. Add `GetArchitectureTrendsArgs` to model imports.

2. Add handler:

```python
@handle_tool_errors
async def handle_get_architecture_trends(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_architecture_trends tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetArchitectureTrendsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from datetime import datetime, timedelta, timezone

    from local_deepwiki.core.health_history import load_snapshots

    wiki_path = repo_path / ".deepwiki"
    since = validated.since
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    snapshots = load_snapshots(wiki_path, since=since)

    summary = None
    if snapshots:
        summary = {
            "snapshot_count": len(snapshots),
            "date_range": {
                "from": snapshots[0].get("timestamp", ""),
                "to": snapshots[-1].get("timestamp", ""),
            },
            "score_change": snapshots[-1].get("score", 0) - snapshots[0].get("score", 0),
            "current_grade": snapshots[-1].get("grade", "?"),
        }

    result = {
        "status": "success",
        "snapshots": snapshots,
        "summary": summary,
        "tool": "get_architecture_trends",
    }

    logger.info(
        "Architecture trends: %d snapshots since %s in %s",
        len(snapshots),
        since,
        repo_path,
    )
    return make_tool_text_content("get_architecture_trends", result)
```

- [ ] **Step 6: Export and register**

Add `handle_get_architecture_trends` to `handlers/analysis.py`, `handlers/__init__.py`, and `server.py` (same pattern as other handlers).

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_architecture_trends.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/models/__init__.py src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/analysis_architecture.py src/local_deepwiki/handlers/analysis.py src/local_deepwiki/handlers/__init__.py src/local_deepwiki/server.py tests/test_architecture_trends.py
git commit -m "feat: add get_architecture_trends MCP tool"
```

---

### Task 4: Add auto-snapshot to `deepwiki update`

**Files:**
- Modify: `src/local_deepwiki/cli/update_cli.py`

- [ ] **Step 1: Add snapshot save to run_update**

In `src/local_deepwiki/cli/update_cli.py`, in the `run_update` function, after the `asyncio.run()` call returns successfully (after line 286, before the `except KeyboardInterrupt`), add:

```python
        # Save health snapshot for trend tracking (non-critical)
        try:
            from local_deepwiki.core.health_history import save_snapshot
            from local_deepwiki.generators.analysis.architecture_health import (
                analyze_architecture_health,
            )
            from local_deepwiki.generators.manifest import get_cached_manifest

            manifest = get_cached_manifest(repo_path)
            project_name = manifest.name or repo_path.name
            health = analyze_architecture_health(repo_path, project_name)
            save_snapshot(effective_wiki_path, health)
        except Exception:
            pass  # Non-critical
```

The insertion point is right after `return asyncio.run(...)` — but since that's a return statement, the snapshot needs to be saved inside a wrapper. Actually, looking at the code more carefully, `asyncio.run()` returns the exit code directly. To save the snapshot on success, capture the return value:

Change:
```python
    try:
        return asyncio.run(
            _run_update_async(...)
        )
```

To:
```python
    try:
        exit_code = asyncio.run(
            _run_update_async(...)
        )
        if exit_code == 0:
            # Save health snapshot for trend tracking (non-critical)
            try:
                from local_deepwiki.core.health_history import save_snapshot
                from local_deepwiki.generators.analysis.architecture_health import (
                    analyze_architecture_health,
                )
                from local_deepwiki.generators.manifest import get_cached_manifest

                manifest = get_cached_manifest(repo_path)
                project_name = manifest.name or repo_path.name
                health = analyze_architecture_health(repo_path, project_name)
                save_snapshot(effective_wiki_path, health)
            except Exception:
                pass
        return exit_code
```

- [ ] **Step 2: Run existing update tests for regression**

Run: `uv run pytest tests/test_cli_update.py -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/local_deepwiki/cli/update_cli.py
git commit -m "feat: auto-save health snapshot on deepwiki update"
```

---

### Task 5: Add tool keywords and update CLAUDE.md

**Files:**
- Modify: `src/local_deepwiki/handlers/agentic_data.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add tool keywords**

In `src/local_deepwiki/handlers/agentic_data.py`, add to `_TOOL_KEYWORDS`:

```python
"get_architecture_trends": [
    "trend",
    "history",
    "health",
    "score",
    "grade",
    "snapshot",
    "over time",
],
```

- [ ] **Step 2: Update CLAUDE.md**

1. Update Analysis & Search Tools count from 13 to 14 in the ASCII diagram. Add `get_architecture_trends` to the tool listing.

2. Add to the Analysis & Search Tools table:
```
| `get_architecture_trends` | Health score history with trend summary | No (reads saved history) |
```

3. Add `deepwiki check` to the Commands section:
```bash
# Run architecture quality gate
uv run deepwiki check
uv run deepwiki check --json
```

4. Add workflow chain:
```
- `get_architecture_trends` -> `analyze_architecture` (see history, then get current details)
```

- [ ] **Step 3: Run full regression**

Run: `uv run pytest tests/test_health_history.py tests/test_check_cli.py tests/test_architecture_trends.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/local_deepwiki/handlers/agentic_data.py CLAUDE.md
git commit -m "docs: add tool keywords and update CLAUDE.md for Phase 3a"
```
