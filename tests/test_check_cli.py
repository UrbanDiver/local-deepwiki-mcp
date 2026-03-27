"""Tests for the ``deepwiki check`` CLI quality gate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.cli.check_cli import (
    _check_thresholds,
    _grade_passes,
    _load_thresholds,
    run_check,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_health_result(
    score: float,
    grade: str,
    dimensions: dict | None = None,
) -> dict:
    """Return a health data dict matching ``analyze_architecture_health`` shape."""
    if dimensions is None:
        dimensions = {
            "complexity": {"score": score, "grade": grade, "factors": {}},
            "coupling": {"score": score, "grade": grade, "factors": {}},
            "smells": {"score": score, "grade": grade, "factors": {}},
            "layers": {"score": score, "grade": grade, "factors": {}},
        }
    return {
        "status": "success",
        "project_name": "test-project",
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": dimensions,
            "weights": {
                "complexity": 0.30,
                "coupling": 0.25,
                "smells": 0.25,
                "layers": 0.20,
            },
        },
        "top_findings": {
            "hotspots": [],
            "high_severity_smells": [],
            "god_classes": [],
            "layer_violations": [],
        },
        "stats": {
            "total_lines": 5000,
            "total_functions": 200,
            "files_scanned": 30,
            "total_modules": 10,
            "total_smells": 3,
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PYPROJECT_CONTENT = """\
[tool.deepwiki.check]
min_grade = "C"
min_score = 50
min_complexity = 40
min_coupling = 40
min_smells = 40
min_layers = 40
"""


@pytest.fixture()
def repo_with_pyproject(tmp_path: Path) -> Path:
    """Create a temporary repo directory with a pyproject.toml containing thresholds."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(_PYPROJECT_CONTENT, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_exit_0_all_pass(
    mock_manifest, mock_analyze, repo_with_pyproject: Path
) -> None:
    """All metrics above thresholds -> exit 0."""
    mock_manifest.return_value.name = "test-project"
    mock_analyze.return_value = _make_health_result(75.0, "B")

    result = run_check(repo_with_pyproject)

    assert result == 0
    mock_analyze.assert_called_once()


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_exit_1_grade_below(
    mock_manifest, mock_analyze, repo_with_pyproject: Path
) -> None:
    """Grade D with min_grade C -> exit 1."""
    mock_manifest.return_value.name = "test-project"
    mock_analyze.return_value = _make_health_result(35.0, "D")

    result = run_check(repo_with_pyproject)

    assert result == 1


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_exit_1_dimension_below(
    mock_manifest, mock_analyze, repo_with_pyproject: Path
) -> None:
    """smells=28.3 < min_smells=40 -> exit 1."""
    mock_manifest.return_value.name = "test-project"
    dimensions = {
        "complexity": {"score": 80.0, "grade": "B", "factors": {}},
        "coupling": {"score": 70.0, "grade": "B", "factors": {}},
        "smells": {"score": 28.3, "grade": "F", "factors": {}},
        "layers": {"score": 90.0, "grade": "A", "factors": {}},
    }
    mock_analyze.return_value = _make_health_result(65.0, "C", dimensions)

    result = run_check(repo_with_pyproject)

    assert result == 1


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_exit_0_no_config(mock_manifest, mock_analyze, tmp_path: Path) -> None:
    """No pyproject.toml -> no thresholds -> exit 0."""
    mock_manifest.return_value.name = "test-project"
    mock_analyze.return_value = _make_health_result(30.0, "D")

    result = run_check(tmp_path)

    assert result == 0


def test_check_exit_2_missing_repo(tmp_path: Path) -> None:
    """Nonexistent path -> exit 2."""
    nonexistent = tmp_path / "does-not-exist"
    result = run_check(nonexistent)
    assert result == 2


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_json_output(
    mock_manifest, mock_analyze, repo_with_pyproject: Path, capsys
) -> None:
    """JSON output includes violations and passes flag."""
    mock_manifest.return_value.name = "test-project"
    dimensions = {
        "complexity": {"score": 80.0, "grade": "B", "factors": {}},
        "coupling": {"score": 70.0, "grade": "B", "factors": {}},
        "smells": {"score": 28.3, "grade": "F", "factors": {}},
        "layers": {"score": 90.0, "grade": "A", "factors": {}},
    }
    mock_analyze.return_value = _make_health_result(65.0, "C", dimensions)

    from rich.console import Console

    console = Console(file=open("/dev/null", "w"))  # noqa: SIM115

    # Use a real console that writes to stdout for capsys
    import io

    buf = io.StringIO()
    console = Console(file=buf, no_color=True)

    result = run_check(
        repo_with_pyproject,
        json_output=True,
        console=console,
    )

    assert result == 1
    output = buf.getvalue()
    data = json.loads(output)
    assert data["passed"] is False
    assert len(data["violations"]) >= 1
    assert data["grade"] == "C"
    assert data["score"] == 65.0
    # Check that smells violation is present
    smell_violations = [v for v in data["violations"] if v["field"] == "min_smells"]
    assert len(smell_violations) == 1
    assert smell_violations[0]["actual"] == 28.3


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_saves_snapshot(
    mock_manifest, mock_analyze, repo_with_pyproject: Path
) -> None:
    """Verify that a health snapshot is saved to .deepwiki/."""
    mock_manifest.return_value.name = "test-project"
    mock_analyze.return_value = _make_health_result(75.0, "B")

    result = run_check(repo_with_pyproject)

    assert result == 0
    history_file = repo_with_pyproject / ".deepwiki" / "health-history.jsonl"
    assert history_file.exists()
    lines = history_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    snapshot = json.loads(lines[0])
    assert snapshot["score"] == 75.0
    assert snapshot["grade"] == "B"


def test_check_grade_comparison() -> None:
    """Test _grade_passes with various grade combinations."""
    # Same grade passes
    assert _grade_passes("A", "A") is True
    assert _grade_passes("C", "C") is True
    assert _grade_passes("F", "F") is True

    # Higher grade passes
    assert _grade_passes("A", "C") is True
    assert _grade_passes("B", "D") is True
    assert _grade_passes("A", "F") is True

    # Lower grade fails
    assert _grade_passes("D", "C") is False
    assert _grade_passes("F", "A") is False
    assert _grade_passes("C", "B") is False


# ---------------------------------------------------------------------------
# Unit tests for internal functions
# ---------------------------------------------------------------------------


def test_load_thresholds_missing_file(tmp_path: Path) -> None:
    """No pyproject.toml -> empty dict."""
    assert _load_thresholds(tmp_path) == {}


def test_load_thresholds_no_section(tmp_path: Path) -> None:
    """pyproject.toml without [tool.deepwiki.check] -> empty dict."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'foo'\n", encoding="utf-8"
    )
    assert _load_thresholds(tmp_path) == {}


def test_load_thresholds_valid(repo_with_pyproject: Path) -> None:
    """Valid [tool.deepwiki.check] section is parsed."""
    thresholds = _load_thresholds(repo_with_pyproject)
    assert thresholds["min_grade"] == "C"
    assert thresholds["min_score"] == 50
    assert thresholds["min_complexity"] == 40


def test_check_thresholds_no_violations() -> None:
    """Health data that passes all thresholds returns empty violations."""
    health = _make_health_result(80.0, "B")
    thresholds = {"min_grade": "C", "min_score": 50}
    violations = _check_thresholds(health, thresholds)
    assert violations == []


def test_check_thresholds_multiple_violations() -> None:
    """Multiple threshold failures return multiple violations."""
    dimensions = {
        "complexity": {"score": 30.0, "grade": "D", "factors": {}},
        "coupling": {"score": 20.0, "grade": "F", "factors": {}},
        "smells": {"score": 80.0, "grade": "B", "factors": {}},
        "layers": {"score": 90.0, "grade": "A", "factors": {}},
    }
    health = _make_health_result(35.0, "D", dimensions)
    thresholds = {
        "min_grade": "C",
        "min_score": 50,
        "min_complexity": 40,
        "min_coupling": 40,
    }
    violations = _check_thresholds(health, thresholds)
    fields = {v["field"] for v in violations}
    assert "grade" in fields
    assert "score" in fields
    assert "min_complexity" in fields
    assert "min_coupling" in fields
    assert len(violations) == 4


@patch("local_deepwiki.cli.check_cli.analyze_architecture_health")
@patch("local_deepwiki.cli.check_cli.get_cached_manifest")
def test_check_exit_2_analysis_failure(
    mock_manifest, mock_analyze, tmp_path: Path
) -> None:
    """Analysis exception -> exit 2."""
    mock_manifest.return_value.name = "test-project"
    mock_analyze.side_effect = RuntimeError("Tree-sitter not available")

    result = run_check(tmp_path)

    assert result == 2
