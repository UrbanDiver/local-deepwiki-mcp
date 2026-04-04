"""Tests for churn analysis — git log parsing, file churn, and co-change coupling."""

from __future__ import annotations

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
