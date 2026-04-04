"""Tests for the get_architecture_health composite analysis tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def _write_simple_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture()
def simple_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo structure for testing."""
    src = tmp_path / "src"
    src.mkdir()
    _write_simple_py(
        src / "module_a.py",
        "def hello():\n    return 1\n",
    )
    _write_simple_py(
        src / "module_b.py",
        "from module_a import hello\n\ndef world():\n    return hello()\n",
    )
    return tmp_path


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    """An empty directory with no Python files."""
    return tmp_path


def test_analyze_architecture_health_returns_required_keys(simple_repo: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")

    assert result["status"] == "success"
    assert result["project_name"] == "test-project"
    assert "overall" in result
    assert "top_findings" in result
    assert "stats" in result


def test_analyze_architecture_health_overall_grade(simple_repo: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")
    overall = result["overall"]

    assert "grade" in overall
    assert overall["grade"] in ("A", "B", "C", "D", "F")
    assert "score" in overall
    assert 0 <= overall["score"] <= 100


def test_analyze_architecture_health_dimension_scores(simple_repo: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")
    dimensions = result["overall"]["dimensions"]

    for dim in ("complexity", "coupling", "smells", "layers", "churn"):
        assert dim in dimensions, f"Missing dimension: {dim}"
        score = dimensions[dim]["score"]
        assert 0 <= score <= 100, f"Score out of range for {dim}: {score}"
        assert dimensions[dim]["grade"] in ("A", "B", "C", "D", "F")


def test_analyze_architecture_health_top_findings_present(simple_repo: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")
    findings = result["top_findings"]

    assert "hotspots" in findings
    assert "high_severity_smells" in findings
    assert "god_classes" in findings
    assert "layer_violations" in findings
    assert isinstance(findings["hotspots"], list)


def test_analyze_architecture_health_top_findings_respects_limit(
    simple_repo: Path,
) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project", top_findings=3)
    findings = result["top_findings"]

    assert len(findings["hotspots"]) <= 3
    assert len(findings["high_severity_smells"]) <= 3
    assert len(findings["layer_violations"]) <= 3


def test_analyze_architecture_health_stats(simple_repo: Path) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")
    stats = result["stats"]

    assert "total_lines" in stats
    assert "total_functions" in stats
    assert "files_scanned" in stats
    assert "total_modules" in stats
    assert "total_smells" in stats
    assert isinstance(stats["total_lines"], int)
    assert stats["total_lines"] >= 0


def test_analyze_architecture_health_empty_repo_returns_grade_a(
    empty_repo: Path,
) -> None:
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(empty_repo, "empty-project")

    assert result["status"] == "success"
    # An empty repo has no smells, no violations, no hotspots -> should grade A
    assert result["overall"]["grade"] == "A"
    assert result["overall"]["score"] == 100.0


def test_analyze_architecture_health_smells_filter_src_only(
    tmp_path: Path,
) -> None:
    """Smells in test/ files should be excluded from scoring."""
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    # A large god-class-like file in tests/ should not affect score
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    big_class = "\n".join(
        [
            "class BigTestClass:",
            *[f"    def method_{i}(self): pass" for i in range(20)],
        ]
    )
    (tests_dir / "test_big.py").write_text(big_class)

    result = analyze_architecture_health(tmp_path, "test-proj")
    # src_smells filter means test file smells are excluded
    assert result["stats"]["total_smells"] == 0


@pytest.mark.asyncio
async def test_handle_get_architecture_health_handler(tmp_path: Path) -> None:
    """Test the MCP handler returns TextContent with JSON."""
    import json
    from unittest.mock import MagicMock

    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_health,
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_architecture_health({"repo_path": str(tmp_path)})

    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "overall" in data


@pytest.mark.asyncio
async def test_handle_get_architecture_health_missing_repo() -> None:
    """Handler should error when repo path does not exist."""
    from unittest.mock import MagicMock

    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_health,
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_architecture_health(
            {"repo_path": "/nonexistent/path/xyz"}
        )

    assert len(result) == 1
    assert "error" in result[0].text.lower() or "not found" in result[0].text.lower()


async def test_architecture_health_summary_detail(tmp_path):
    """detail_level=summary returns grade + dimensions without stats."""
    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")

    from unittest.mock import MagicMock, patch

    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_health,
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_architecture_health(
            {"repo_path": str(tmp_path), "detail_level": "summary"}
        )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "overall" in data
    assert "grade" in data["overall"]
    assert "dimensions" in data["overall"]
    assert "stats" not in data
    assert len(result[0].text) < 1500


def test_analyze_architecture_health_includes_next_steps(simple_repo):
    """Health output should include dynamically generated next_steps."""
    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")
    assert "next_steps" in result, "Expected next_steps field in health output"
    steps = result["next_steps"]
    assert isinstance(steps, list)
    for step in steps:
        assert "tool" in step
        assert "args" in step
        assert "reason" in step


async def test_architecture_health_full_detail(tmp_path):
    """detail_level=full returns everything including file metrics."""
    (tmp_path / "mod.py").write_text("def f():\n    return 1\n")

    from unittest.mock import MagicMock, patch

    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_architecture_health,
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None

    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_architecture_health(
            {"repo_path": str(tmp_path), "detail_level": "full"}
        )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "overall" in data
    assert "top_findings" in data
    assert "stats" in data
    assert "file_metrics" in data


def test_analyze_architecture_health_includes_churn_dimension(simple_repo):
    """Health output should include churn in dimensions after Phase 1."""
    import subprocess

    # Initialize git repo so churn analysis can run
    subprocess.run(["git", "init"], cwd=simple_repo, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=simple_repo,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=simple_repo,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=simple_repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=simple_repo, capture_output=True
    )

    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )

    result = analyze_architecture_health(simple_repo, "test-project")
    dimensions = result["overall"]["dimensions"]
    assert "churn" in dimensions
    assert 0 <= dimensions["churn"]["score"] <= 100
    assert dimensions["churn"]["grade"] in ("A", "B", "C", "D", "F")
