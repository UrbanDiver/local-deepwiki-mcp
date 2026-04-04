"""Tests for maintainability index module."""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# _compute_halstead
# ---------------------------------------------------------------------------


def test_compute_halstead_simple_function(tmp_path):
    """Halstead metrics on a simple function have operators and operands."""
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.generators.analysis.maintainability import _compute_halstead

    py_file = tmp_path / "add.py"
    py_file.write_text("def add(a, b):\n    return a + b\n")

    parser = CodeParser()
    result = parser.parse_file(py_file)
    assert result is not None

    root, _lang, src = result
    # Find the function node
    func_node = None
    for child in root.children:
        if child.type == "function_definition":
            func_node = child
            break
    assert func_node is not None

    halstead = _compute_halstead(func_node, src)
    assert halstead["n1"] > 0, "Should have unique operators"
    assert halstead["n2"] > 0, "Should have unique operands"
    assert halstead["N1"] > 0, "Should have total operators"
    assert halstead["N2"] > 0, "Should have total operands"
    assert halstead["volume"] > 0, "Volume should be positive"


def test_compute_halstead_empty_function(tmp_path):
    """Halstead on a minimal function (pass body) still computes."""
    from local_deepwiki.core.parser.code_parser import CodeParser
    from local_deepwiki.generators.analysis.maintainability import _compute_halstead

    py_file = tmp_path / "noop.py"
    py_file.write_text("def noop():\n    pass\n")

    parser = CodeParser()
    result = parser.parse_file(py_file)
    assert result is not None

    root, _lang, src = result
    func_node = None
    for child in root.children:
        if child.type == "function_definition":
            func_node = child
            break
    assert func_node is not None

    halstead = _compute_halstead(func_node, src)
    # Even a minimal function has some tokens
    assert halstead["volume"] >= 0


# ---------------------------------------------------------------------------
# _compute_mi
# ---------------------------------------------------------------------------


def test_compute_mi_known_values():
    """MI with known inputs produces expected range."""
    from local_deepwiki.generators.analysis.maintainability import _compute_mi

    # A small function with low volume, low CC, few LOC should have high MI
    mi = _compute_mi(halstead_volume=50, cc=2, loc=5)
    assert 50 < mi <= 100, f"Expected high MI for simple function, got {mi}"


def test_compute_mi_zero_volume():
    """MI returns 100 when Halstead volume is zero."""
    from local_deepwiki.generators.analysis.maintainability import _compute_mi

    mi = _compute_mi(halstead_volume=0, cc=5, loc=10)
    assert mi == 100.0


def test_compute_mi_zero_loc():
    """MI returns 100 when LOC is zero."""
    from local_deepwiki.generators.analysis.maintainability import _compute_mi

    mi = _compute_mi(halstead_volume=100, cc=5, loc=0)
    assert mi == 100.0


def test_compute_mi_large_values():
    """MI with large values clamps to 0-100."""
    from local_deepwiki.generators.analysis.maintainability import _compute_mi

    mi = _compute_mi(halstead_volume=100000, cc=50, loc=500)
    assert 0.0 <= mi <= 100.0


def test_compute_mi_formula_consistency():
    """Verify MI formula produces expected result for known input."""
    from local_deepwiki.generators.analysis.maintainability import _compute_mi

    # Manual calculation: HV=100, CC=5, LOC=20
    # raw = 171 - 5.2*ln(100) - 0.23*5 - 16.2*ln(20)
    # raw = 171 - 5.2*4.605 - 1.15 - 16.2*2.996
    # raw = 171 - 23.946 - 1.15 - 48.535 = 97.369
    # MI = max(0, 97.369 * 100 / 171) = 56.94
    expected_raw = 171 - 5.2 * math.log(100) - 0.23 * 5 - 16.2 * math.log(20)
    expected_mi = max(0.0, min(100.0, expected_raw * 100 / 171))

    mi = _compute_mi(halstead_volume=100, cc=5, loc=20)
    assert mi == pytest.approx(expected_mi, rel=0.001)


# ---------------------------------------------------------------------------
# analyze_maintainability
# ---------------------------------------------------------------------------


def test_analyze_maintainability_basic(tmp_path):
    """Analyze a repo with a simple function."""
    from local_deepwiki.generators.analysis.maintainability import (
        analyze_maintainability,
    )

    _write_py(
        tmp_path / "src" / "module.py",
        "def hello():\n    return 1\n",
    )

    result = analyze_maintainability(tmp_path)
    assert result["status"] == "success"
    assert len(result["functions"]) >= 1
    assert result["stats"]["total_functions"] >= 1
    assert result["stats"]["avg_mi"] > 0
    assert result["stats"]["min_mi"] >= 0

    func = result["functions"][0]
    assert "function" in func
    assert "file" in func
    assert "line" in func
    assert "mi" in func
    assert "halstead_volume" in func
    assert "cc" in func
    assert "loc" in func


def test_analyze_maintainability_empty_repo(tmp_path):
    """Empty repo returns success with no functions."""
    from local_deepwiki.generators.analysis.maintainability import (
        analyze_maintainability,
    )

    result = analyze_maintainability(tmp_path)
    assert result["status"] == "success"
    assert result["functions"] == []
    assert result["stats"]["total_functions"] == 0
    assert result["stats"]["avg_mi"] == 100.0
    assert result["stats"]["min_mi"] == 100.0
    assert result["stats"]["low_mi_functions"] == 0
    assert result["stats"]["low_mi_pct"] == 0.0


def test_analyze_maintainability_sorted_ascending(tmp_path):
    """Functions should be sorted by MI ascending (worst first)."""
    from local_deepwiki.generators.analysis.maintainability import (
        analyze_maintainability,
    )

    # Simple function (high MI) and complex function (lower MI)
    _write_py(
        tmp_path / "src" / "simple.py",
        "def simple():\n    return 1\n",
    )
    complex_body = "\n".join(
        [
            "def complex_func(a, b, c, d, e):",
            "    result = 0",
            "    for i in range(a):",
            "        if b > 0:",
            "            for j in range(c):",
            "                if d > 0:",
            "                    result += i * j",
            "                elif e > 0:",
            "                    result -= i",
            "                else:",
            "                    result += 1",
            "        else:",
            "            result = b + c + d + e",
            "    return result",
        ]
    )
    _write_py(tmp_path / "src" / "complex.py", complex_body)

    result = analyze_maintainability(tmp_path)
    functions = result["functions"]
    assert len(functions) >= 2
    # Verify sorted ascending by MI
    for i in range(len(functions) - 1):
        assert functions[i]["mi"] <= functions[i + 1]["mi"]


def test_analyze_maintainability_excludes_tests(tmp_path):
    """Test files should be excluded when exclude_tests=True."""
    from local_deepwiki.generators.analysis.maintainability import (
        analyze_maintainability,
    )

    _write_py(
        tmp_path / "src" / "module.py",
        "def source_func():\n    return 1\n",
    )
    _write_py(
        tmp_path / "tests" / "test_module.py",
        "def test_func():\n    assert True\n",
    )

    result = analyze_maintainability(tmp_path, exclude_tests=True)
    files = {f["file"] for f in result["functions"]}
    assert not any("test_" in f for f in files)


def test_analyze_maintainability_top_n(tmp_path):
    """top_n limits the number of returned functions."""
    from local_deepwiki.generators.analysis.maintainability import (
        analyze_maintainability,
    )

    # Create multiple functions
    funcs = "\n".join(f"def func_{i}():\n    return {i}\n" for i in range(10))
    _write_py(tmp_path / "src" / "many.py", funcs)

    result = analyze_maintainability(tmp_path, top_n=3)
    assert len(result["functions"]) <= 3
    # Total should still count all
    assert result["stats"]["total_functions"] >= 10


# ---------------------------------------------------------------------------
# Handler (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_get_maintainability_metrics(tmp_path):
    """Handler returns TextContent with JSON."""
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_maintainability_metrics,
    )

    _write_py(
        tmp_path / "src" / "a.py",
        "def foo():\n    return 1\n",
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_maintainability_metrics({"repo_path": str(tmp_path)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "functions" in data
    assert "stats" in data
