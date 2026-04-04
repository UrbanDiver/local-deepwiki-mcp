"""Tests for churn analysis — git log parsing, file churn, and co-change coupling."""

from __future__ import annotations

import pytest

from local_deepwiki.generators.analysis.churn import (
    compute_co_change,
    compute_file_churn,
    parse_git_log_numstat,
)


# ---------------------------------------------------------------------------
# Task 1: parse_git_log_numstat
# ---------------------------------------------------------------------------


def test_parse_git_log_numstat_basic():
    """Parse 2 commits with multiple files each."""
    raw = (
        "abc1234\n"
        "10\t5\tsrc/foo.py\n"
        "3\t1\tsrc/bar.py\n"
        "\n"
        "def5678\n"
        "20\t10\tsrc/baz.py\n"
        "1\t0\tsrc/foo.py\n"
    )
    result = parse_git_log_numstat(raw)
    assert len(result) == 2
    assert result[0] == ("abc1234", ["src/foo.py", "src/bar.py"])
    assert result[1] == ("def5678", ["src/baz.py", "src/foo.py"])


def test_parse_git_log_numstat_empty():
    """Empty input returns empty list."""
    assert parse_git_log_numstat("") == []
    assert parse_git_log_numstat("   \n\n  ") == []


def test_parse_git_log_numstat_skips_binary():
    """Binary files (shown as -\\t-\\tpath) are skipped."""
    raw = "aaa1111\n10\t5\tsrc/code.py\n-\t-\tassets/image.png\n2\t1\tsrc/util.py\n"
    result = parse_git_log_numstat(raw)
    assert len(result) == 1
    assert result[0] == ("aaa1111", ["src/code.py", "src/util.py"])


# ---------------------------------------------------------------------------
# Task 2: compute_file_churn
# ---------------------------------------------------------------------------


def test_compute_file_churn_counts_commits():
    """Verify correct commit counts across 3 commits."""
    commits = [
        ("c1", ["a.py", "b.py"]),
        ("c2", ["b.py", "c.py"]),
        ("c3", ["a.py", "b.py", "c.py"]),
    ]
    result = compute_file_churn(commits)
    assert result == {"b.py": 3, "a.py": 2, "c.py": 2}


def test_compute_file_churn_empty():
    """Empty commits returns empty dict."""
    assert compute_file_churn([]) == {}


# ---------------------------------------------------------------------------
# Task 3: compute_co_change
# ---------------------------------------------------------------------------


def test_compute_co_change_basic():
    """Verify Jaccard values for known input."""
    # a.py and b.py both in c1, c3 -> shared=2, union=3 (c1,c2,c3) -> j=0.6667
    # a.py and c.py both in c3      -> shared=1, union=3 (c1,c2,c3) -> j=0.3333
    # b.py and c.py both in c2, c3  -> shared=2, union=3 (c1,c2,c3) -> j=0.6667
    commits = [
        ("c1", ["a.py", "b.py"]),
        ("c2", ["b.py", "c.py"]),
        ("c3", ["a.py", "b.py", "c.py"]),
    ]
    result = compute_co_change(commits, min_shared=1)
    assert len(result) == 3

    # Sorted by jaccard desc — a.py/b.py and b.py/c.py tied at 0.6667
    top = result[0]
    assert top["jaccard"] == 0.6667
    assert top["shared_commits"] == 2
    assert top["union_commits"] == 3

    bottom = result[-1]
    assert bottom["jaccard"] == 0.3333
    assert bottom["shared_commits"] == 1
    assert bottom["pair"] == ["a.py", "c.py"]


def test_compute_co_change_min_shared_filter():
    """min_shared=2 filters out pairs with only 1 shared commit."""
    commits = [
        ("c1", ["a.py", "b.py"]),
        ("c2", ["b.py", "c.py"]),
        ("c3", ["a.py", "b.py", "c.py"]),
    ]
    result = compute_co_change(commits, min_shared=2)
    # a.py/c.py only shares 1 commit — should be filtered out
    assert len(result) == 2
    pairs = [tuple(r["pair"]) for r in result]
    assert ("a.py", "c.py") not in pairs


def test_compute_co_change_empty():
    """Empty commits returns empty list."""
    assert compute_co_change([]) == []


# ---------------------------------------------------------------------------
# Task 4: compute_churn_complexity
# ---------------------------------------------------------------------------


def test_compute_churn_complexity_composite():
    """Composite score multiplies normalized churn by normalized complexity."""
    from local_deepwiki.generators.analysis.churn import compute_churn_complexity

    churn = {"src/a.py": 10, "src/b.py": 5, "src/c.py": 1}
    complexity = {"src/a.py": 20, "src/b.py": 5, "src/c.py": 15}
    result = compute_churn_complexity(churn, complexity)
    assert result[0]["file"] == "src/a.py"
    assert result[0]["churn"] == 10
    assert result[0]["complexity"] == 20
    assert result[0]["composite"] > result[1]["composite"]


def test_compute_churn_complexity_missing_complexity():
    from local_deepwiki.generators.analysis.churn import compute_churn_complexity

    churn = {"src/a.py": 10}
    complexity = {}
    result = compute_churn_complexity(churn, complexity)
    assert result[0]["complexity"] == 0
    assert result[0]["composite"] == 0.0


def test_compute_churn_complexity_empty():
    from local_deepwiki.generators.analysis.churn import compute_churn_complexity

    assert compute_churn_complexity({}, {}) == []


# ---------------------------------------------------------------------------
# Task 4: _compute_gini
# ---------------------------------------------------------------------------


def test_gini_even_distribution():
    from local_deepwiki.generators.analysis.churn import _compute_gini

    assert _compute_gini([10, 10, 10, 10]) == pytest.approx(0.0, abs=0.01)


def test_gini_concentrated():
    from local_deepwiki.generators.analysis.churn import _compute_gini

    result = _compute_gini([0, 0, 0, 100])
    assert result > 0.7


def test_gini_empty():
    from local_deepwiki.generators.analysis.churn import _compute_gini

    assert _compute_gini([]) == 0.0


# ---------------------------------------------------------------------------
# Task 4: analyze_churn orchestrator
# ---------------------------------------------------------------------------


def test_analyze_churn_with_git_repo(tmp_path):
    """analyze_churn on a real (tiny) git repo."""
    import subprocess

    from local_deepwiki.generators.analysis.churn import analyze_churn

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
    )
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=tmp_path, capture_output=True)
    (tmp_path / "a.py").write_text("x = 2\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=tmp_path, capture_output=True)
    result = analyze_churn(tmp_path)
    assert result["status"] == "success"
    assert "file_churn" in result
    assert "co_change" in result
    assert "stats" in result
    assert result["stats"]["total_commits"] >= 2


# ---------------------------------------------------------------------------
# Tasks 7-8: MCP handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_get_churn_metrics(tmp_path):
    """MCP handler returns churn data as JSON TextContent."""
    import json
    import subprocess
    from unittest.mock import MagicMock, patch

    from local_deepwiki.handlers.analysis_architecture import handle_get_churn_metrics

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True
    )
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_churn_metrics(
            {"repo_path": str(tmp_path), "window_days": 90}
        )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "file_churn" in data


@pytest.mark.asyncio
async def test_handle_get_co_change(tmp_path):
    """MCP handler for co-change returns JSON TextContent."""
    import json
    import subprocess
    from unittest.mock import MagicMock, patch

    from local_deepwiki.handlers.analysis_architecture import handle_get_co_change

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True
    )
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_co_change({"repo_path": str(tmp_path)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "co_change" in data
