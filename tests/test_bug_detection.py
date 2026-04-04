"""Tests for the bug detection orchestrator."""

from __future__ import annotations

from pathlib import Path

from local_deepwiki.generators.analysis.bug_detection import analyze_bugs


def test_analyze_bugs_empty_repo(tmp_path: Path):
    result = analyze_bugs(tmp_path)
    assert result["status"] == "success"
    assert result["total_findings"] == 0
    assert result["files_scanned"] == 0


def test_analyze_bugs_finds_mutable_default(tmp_path: Path):
    (tmp_path / "example.py").write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path)
    assert result["status"] == "success"
    assert result["total_findings"] >= 1
    assert "mutable-default-argument" in [f["pattern"] for f in result["findings"]]


def test_analyze_bugs_min_confidence_filter(tmp_path: Path):
    (tmp_path / "example.py").write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path, min_confidence="high")
    for finding in result["findings"]:
        assert finding["confidence"] == "high"


def test_analyze_bugs_language_filter(tmp_path: Path):
    (tmp_path / "example.py").write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path, languages=["go"])
    assert result["total_findings"] == 0


def test_analyze_bugs_file_path_scope(tmp_path: Path):
    (tmp_path / "a.py").write_text("def f(x=[]):\n    pass\n")
    (tmp_path / "b.py").write_text("def g(x={}):\n    pass\n")
    result = analyze_bugs(tmp_path, file_path="a.py")
    assert result["files_scanned"] == 1


def test_analyze_bugs_exclude_tests(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("def f(x=[]):\n    pass\n")
    (tmp_path / "main.py").write_text("def g():\n    pass\n")
    result_with = analyze_bugs(tmp_path, exclude_tests=True)
    result_without = analyze_bugs(tmp_path, exclude_tests=False)
    assert result_with["files_scanned"] <= result_without["files_scanned"]


def test_analyze_bugs_top_n_limit(tmp_path: Path):
    lines = [f"def f{i}(x=[]):\n    pass\n" for i in range(20)]
    (tmp_path / "example.py").write_text("\n".join(lines))
    result = analyze_bugs(tmp_path, top_n=5)
    assert result["returned"] <= 5
    assert result["total_findings"] >= 5


def test_analyze_bugs_response_shape(tmp_path: Path):
    (tmp_path / "example.py").write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path)
    for key in (
        "status",
        "total_findings",
        "returned",
        "by_confidence",
        "by_pattern",
        "findings",
        "patterns_checked",
        "files_scanned",
    ):
        assert key in result


def test_analyze_bugs_invalid_confidence(tmp_path: Path):
    result = analyze_bugs(tmp_path, min_confidence="invalid")
    assert result["status"] == "error"
