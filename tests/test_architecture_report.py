"""Tests for the architecture report narrative formatter."""

from local_deepwiki.generators.analysis.architecture_report import (
    format_architecture_report,
)


def _make_health(
    score=80.0, grade="B", hotspots=None, smells=None, god_classes=None, violations=None
):
    return {
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": {
                "complexity": {"score": score, "grade": grade},
                "coupling": {"score": score, "grade": grade},
                "smells": {"score": score, "grade": grade},
                "layers": {"score": 100.0, "grade": "A"},
            },
        },
        "stats": {"total_lines": 10000, "total_functions": 100, "files_scanned": 20},
        "top_findings": {
            "hotspots": hotspots or [],
            "high_severity_smells": smells or [],
            "god_classes": god_classes or [],
            "layer_violations": violations or [],
        },
    }


def _make_deps(modules=50, edges_count=30, edges=None):
    return {
        "stats": {"total_modules": modules, "total_edges": edges_count},
        "edges": edges or [],
    }


def test_format_report_includes_executive_summary():
    report = format_architecture_report(_make_health(76.5, "B"), _make_deps())
    assert "## Executive Summary" in report
    assert "B" in report
    assert "76.5" in report


def test_format_report_includes_strengths():
    report = format_architecture_report(_make_health(90.0, "A"), _make_deps())
    assert "## Strengths" in report


def test_format_report_includes_concerns():
    hotspots = [
        {
            "function": "big_func",
            "file": "mod.py",
            "line": 1,
            "metric_value": 30,
            "details": {"cyclomatic": 30, "params": 2, "length": 100, "nesting": 0},
        }
    ]
    report = format_architecture_report(
        _make_health(60.0, "C", hotspots=hotspots), _make_deps()
    )
    assert "## Concerns" in report
    assert "big_func" in report


def test_format_report_summary_is_compact():
    report = format_architecture_report(
        _make_health(), _make_deps(), detail_level="summary"
    )
    assert "## Executive Summary" in report
    assert "## Concerns" not in report
    assert "## Dependency Structure" not in report
    assert len(report) < 2000


def test_format_report_dependency_section():
    edges = [
        {"source": "core.vectorstore", "target": "models", "weight": 50},
        {"source": "handlers", "target": "core.vectorstore", "weight": 30},
    ]
    report = format_architecture_report(
        _make_health(), _make_deps(edges=edges), detail_level="standard"
    )
    assert "## Dependency Structure" in report
    assert "core.vectorstore" in report


def test_format_report_no_concerns_when_healthy():
    report = format_architecture_report(_make_health(95.0, "A"), _make_deps())
    # No concerns section when all dimensions are above threshold
    assert "## Concerns" not in report or "## Concerns\n\n" in report


def test_format_report_zero_layer_violations_is_strength():
    report = format_architecture_report(_make_health(), _make_deps())
    assert "Zero layer violations" in report
