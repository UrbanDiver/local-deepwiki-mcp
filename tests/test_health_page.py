"""Tests for the architecture health wiki page generator."""

from __future__ import annotations

import pytest

from local_deepwiki.generators.analysis.health_page import generate_health_page


@pytest.fixture
def mock_health_data():
    return {
        "overall": {
            "score": 60.0,
            "grade": "C",
            "dimensions": {
                "complexity": {"score": 67.2, "grade": "C"},
                "coupling": {"score": 44.2, "grade": "D"},
                "smells": {"score": 35.2, "grade": "F"},
                "layers": {"score": 100.0, "grade": "A"},
            },
        },
        "top_findings": {
            "hotspots": [
                {
                    "function": "foo",
                    "file": "a.py",
                    "line": 1,
                    "metric_value": 33,
                    "details": {
                        "cyclomatic": 33,
                        "params": 4,
                        "length": 118,
                        "nesting": 0,
                    },
                }
            ],
            "high_severity_smells": [],
            "god_classes": [
                {
                    "type": "god_class",
                    "severity": "high",
                    "file": "b.py",
                    "line": 49,
                    "entity": "BigClass",
                    "description": "25 methods and 816 lines",
                }
            ],
            "layer_violations": [],
        },
        "stats": {"total_lines": 71000, "total_functions": 1946, "files_scanned": 242},
    }


def test_generate_health_page_returns_markdown(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert result is not None
    assert "# Architecture Health" in result
    assert "**C**" in result or "C" in result


def test_generate_health_page_includes_dimension_table(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "| Dimension" in result
    assert "67.2" in result
    assert "44.2" in result


def test_generate_health_page_includes_hotspots(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "foo" in result
    assert "a.py" in result


def test_generate_health_page_includes_god_classes(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "BigClass" in result
    assert "b.py" in result


def test_generate_health_page_shows_clean_layers_when_no_violations(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "No layer violations" in result


def test_generate_health_page_returns_none_for_empty():
    assert generate_health_page({}) is None
    assert generate_health_page({"overall": None}) is None


def test_generate_health_page_includes_stats(mock_health_data):
    result = generate_health_page(mock_health_data)
    assert "71,000" in result or "71000" in result
    assert "1,946" in result or "1946" in result


def test_generate_health_page_includes_high_severity_smells():
    """High-severity smells should appear when present."""
    data = {
        "overall": {
            "score": 50.0,
            "grade": "D",
            "dimensions": {},
        },
        "top_findings": {
            "hotspots": [],
            "high_severity_smells": [
                {
                    "type": "long_method",
                    "severity": "high",
                    "file": "big.py",
                    "line": 10,
                    "entity": "do_everything",
                    "description": "Method has 300 lines",
                }
            ],
            "god_classes": [],
            "layer_violations": [],
        },
        "stats": {},
    }
    result = generate_health_page(data)
    assert result is not None
    assert "do_everything" in result
    assert "big.py" in result


def test_generate_health_page_shows_layer_violations():
    """Layer violations should appear when present."""
    data = {
        "overall": {
            "score": 40.0,
            "grade": "D",
            "dimensions": {},
        },
        "top_findings": {
            "hotspots": [],
            "high_severity_smells": [],
            "god_classes": [],
            "layer_violations": [
                "core/parser.py imports from handlers/indexing.py (core -> handlers)"
            ],
        },
        "stats": {},
    }
    result = generate_health_page(data)
    assert result is not None
    assert "Layer Violations" in result
    assert "core/parser.py" in result
    assert "No layer violations" not in result


def test_generate_health_page_no_dimensions():
    """Page should still render when dimensions dict is empty."""
    data = {
        "overall": {
            "score": 75.0,
            "grade": "B",
            "dimensions": {},
        },
        "top_findings": {
            "hotspots": [],
            "high_severity_smells": [],
            "god_classes": [],
            "layer_violations": [],
        },
        "stats": {},
    }
    result = generate_health_page(data)
    assert result is not None
    assert "# Architecture Health" in result
    assert "**B**" in result or "B" in result
