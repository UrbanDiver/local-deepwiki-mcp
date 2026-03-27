"""Tests for the compare_architecture tool."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    """Run a git command in *repo*, raising on error."""
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )


def _make_git_repo_with_two_commits(tmp_path: Path) -> Path:
    """Create a minimal git repo with two commits so HEAD~1 is resolvable."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    # First commit
    (repo / "hello.py").write_text("def hello():\n    return 1\n")
    _git(repo, "add", "hello.py")
    _git(repo, "commit", "-m", "init")
    # Second commit
    (repo / "world.py").write_text("def world():\n    return 2\n")
    _git(repo, "add", "world.py")
    _git(repo, "commit", "-m", "add world")
    return repo


# ---------------------------------------------------------------------------
# Unit tests for _compute_deltas
# ---------------------------------------------------------------------------


def _make_health(score: float, grade: str) -> dict:
    return {
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": {
                "complexity": {"score": score},
                "coupling": {"score": score},
                "smells": {"score": score},
                "layers": {"score": score},
            },
        },
        "top_findings": {
            "high_severity_smells": [],
        },
    }


def test_compute_deltas_improvement() -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_deltas,
    )

    base = _make_health(70.0, "C")
    head = _make_health(85.0, "B")

    result = _compute_deltas(base, head)

    assert result["overall_delta"] == 15.0
    assert result["base_grade"] == "C"
    assert result["head_grade"] == "B"
    assert result["dimensions"]["complexity"]["trend"] == "improved"
    assert result["dimensions"]["complexity"]["delta"] == 15.0


def test_compute_deltas_degradation() -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_deltas,
    )

    base = _make_health(90.0, "A")
    head = _make_health(60.0, "C")

    result = _compute_deltas(base, head)

    assert result["overall_delta"] == -30.0
    assert result["dimensions"]["coupling"]["trend"] == "degraded"


def test_compute_deltas_unchanged() -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_deltas,
    )

    health = _make_health(80.0, "B")
    result = _compute_deltas(health, health)

    assert result["overall_delta"] == 0.0
    for dim in ("complexity", "coupling", "smells", "layers"):
        assert result["dimensions"][dim]["trend"] == "unchanged"


def test_compute_deltas_smell_counts() -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_deltas,
    )

    base = {
        "overall": {"score": 80.0, "grade": "B", "dimensions": {}},
        "top_findings": {
            "high_severity_smells": [
                {"file": "src/a.py", "line": 10, "type": "god_class"},
                {"file": "src/b.py", "line": 20, "type": "long_method"},
            ]
        },
    }
    head = {
        "overall": {"score": 80.0, "grade": "B", "dimensions": {}},
        "top_findings": {
            "high_severity_smells": [
                # resolved: (src/a.py, 10, god_class) gone
                # new: (src/c.py, 30, data_clump) added
                {"file": "src/b.py", "line": 20, "type": "long_method"},
                {"file": "src/c.py", "line": 30, "type": "data_clump"},
            ]
        },
    }

    result = _compute_deltas(base, head)

    assert result["new_high_smells"] == 1
    assert result["resolved_high_smells"] == 1


# ---------------------------------------------------------------------------
# Unit tests for _resolve_ref
# ---------------------------------------------------------------------------


def test_resolve_ref_valid(tmp_path: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_compare import _resolve_ref

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "f.py").write_text("x = 1\n")
    _git(repo, "add", "f.py")
    _git(repo, "commit", "-m", "init")

    sha = _resolve_ref(repo, "HEAD")
    assert sha is not None
    assert len(sha) >= 7  # short SHA


def test_resolve_ref_invalid(tmp_path: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_compare import _resolve_ref

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")

    sha = _resolve_ref(repo, "nonexistent-branch")
    assert sha is None


def test_resolve_ref_not_a_git_repo(tmp_path: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_compare import _resolve_ref

    result = _resolve_ref(tmp_path, "HEAD")
    assert result is None


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------


def test_compare_architecture_bad_base_ref(tmp_path: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        compare_architecture,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")

    result = compare_architecture(repo, "proj", base_ref="nonexistent-ref")
    assert result["status"] == "error"
    assert "nonexistent-ref" in result["message"]


def test_compare_architecture_bad_head_ref(tmp_path: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        compare_architecture,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "f.py").write_text("x = 1\n")
    _git(repo, "add", "f.py")
    _git(repo, "commit", "-m", "init")

    result = compare_architecture(
        repo, "proj", base_ref="HEAD", head_ref="nonexistent-ref"
    )
    assert result["status"] == "error"
    assert "nonexistent-ref" in result["message"]


# ---------------------------------------------------------------------------
# Integration test with real two-commit repo
# ---------------------------------------------------------------------------


def test_compare_architecture_two_commits(tmp_path: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        compare_architecture,
    )

    repo = _make_git_repo_with_two_commits(tmp_path)
    result = compare_architecture(repo, "test-project", base_ref="HEAD~1")

    assert result["status"] == "success"
    assert result["project_name"] == "test-project"
    assert "deltas" in result
    assert "base_ref" in result
    assert "head_ref" in result
    assert "base_health" in result
    assert "head_health" in result

    deltas = result["deltas"]
    assert "overall_delta" in deltas
    assert "base_grade" in deltas
    assert "head_grade" in deltas
    assert deltas["base_grade"] in ("A", "B", "C", "D", "F")
    assert deltas["head_grade"] in ("A", "B", "C", "D", "F")

    for dim in ("complexity", "coupling", "smells", "layers"):
        assert dim in deltas["dimensions"]
        dim_data = deltas["dimensions"][dim]
        assert "delta" in dim_data
        assert "trend" in dim_data
        assert dim_data["trend"] in ("improved", "degraded", "unchanged")


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_compare_architecture_handler(tmp_path: Path) -> None:
    """Test the MCP handler validates and dispatches correctly."""
    import json

    from local_deepwiki.handlers.analysis_architecture import (
        handle_compare_architecture,
    )

    repo = _make_git_repo_with_two_commits(tmp_path)
    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_compare_architecture(
            {"repo_path": str(repo), "base_ref": "HEAD~1", "head_ref": "HEAD"}
        )

    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "deltas" in data


@pytest.mark.asyncio
async def test_handle_compare_architecture_missing_repo() -> None:
    """Handler returns error content for nonexistent repo."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_compare_architecture,
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_compare_architecture({"repo_path": "/nonexistent/xyz"})

    assert len(result) == 1
    assert "error" in result[0].text.lower() or "not found" in result[0].text.lower()


# ---------------------------------------------------------------------------
# Unit tests for _compute_verdict
# ---------------------------------------------------------------------------


def test_compute_verdict_improved() -> None:
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
    assert "coupling" in verdict["unchanged"]
    assert "layers" in verdict["unchanged"]


def test_compute_verdict_degraded() -> None:
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


# ---------------------------------------------------------------------------
# Unit tests for _compute_coupling_diff and _compute_smell_diff
# ---------------------------------------------------------------------------


def test_compute_coupling_diff() -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_coupling_diff,
    )

    base = [
        {"module": "core", "distance": 0.8},
        {"module": "utils", "distance": 0.3},
    ]
    head = [
        {"module": "core", "distance": 0.5},
        {"module": "utils", "distance": 0.3},
        {"module": "web", "distance": 0.9},
    ]
    diff = _compute_coupling_diff(base, head)
    assert diff["base_modules"] == 2
    assert diff["head_modules"] == 3
    assert any(m["module"] == "web" for m in diff["new_high_distance"])
    assert any(m["module"] == "core" for m in diff["resolved_high_distance"])


def test_compute_smell_diff() -> None:
    from local_deepwiki.generators.analysis.architecture_compare import (
        _compute_smell_diff,
    )

    base = {
        "top_findings": {
            "high_severity_smells": [
                {"type": "long_method", "file": "a.py", "entity": "func_a"},
                {"type": "god_class", "file": "b.py", "entity": "BigB"},
            ]
        }
    }
    head = {
        "top_findings": {
            "high_severity_smells": [
                {"type": "long_method", "file": "a.py", "entity": "func_a"},
                {"type": "god_class", "file": "c.py", "entity": "BigC"},
            ]
        }
    }
    diff = _compute_smell_diff(base, head)
    new_entities = [s["entity"] for s in diff["new_smells"]]
    resolved_entities = [s["entity"] for s in diff["resolved_smells"]]
    assert "BigC" in new_entities
    assert "BigB" in resolved_entities
