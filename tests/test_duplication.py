"""Tests for duplication detection module."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# Shared duplicate block for tests
_DUPLICATE_BLOCK = """def process_data(items):
    result = []
    for item in items:
        if item.is_valid():
            transformed = item.transform()
            result.append(transformed)
    return result
"""


def test_detect_type1_clones_finds_exact_duplicates(tmp_path):
    from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    _write_py(tmp_path / "src" / "a.py", _DUPLICATE_BLOCK + "\nx = 1\n")
    _write_py(tmp_path / "src" / "b.py", _DUPLICATE_BLOCK + "\ny = 2\n")
    clones = detect_type1_clones(tmp_path, min_lines=6)
    assert len(clones) >= 1
    assert clones[0]["line_count"] >= 6
    assert len(clones[0]["instances"]) >= 2


def test_detect_type1_clones_no_duplicates(tmp_path):
    from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    _write_py(tmp_path / "src" / "a.py", "def foo():\n    return 1\n")
    _write_py(tmp_path / "src" / "b.py", "def bar():\n    return 2\n")
    clones = detect_type1_clones(tmp_path, min_lines=6)
    assert clones == []


def test_detect_type1_clones_respects_min_lines(tmp_path):
    from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    short_block = "x = 1\ny = 2\nz = 3\n"
    _write_py(tmp_path / "src" / "a.py", short_block)
    _write_py(tmp_path / "src" / "b.py", short_block)
    # min_lines=6 should not detect this 3-line block
    clones = detect_type1_clones(tmp_path, min_lines=6)
    assert clones == []
    # min_lines=3 should detect it
    clones = detect_type1_clones(tmp_path, min_lines=3)
    assert len(clones) >= 1


def test_detect_type1_clones_excludes_tests(tmp_path):
    from local_deepwiki.generators.analysis.duplication import detect_type1_clones

    _write_py(tmp_path / "src" / "a.py", _DUPLICATE_BLOCK)
    _write_py(tmp_path / "tests" / "test_a.py", _DUPLICATE_BLOCK)
    clones = detect_type1_clones(tmp_path, min_lines=6, exclude_tests=True)
    # Only one file in src, so no duplicates
    assert clones == []


def test_detect_type2_clones_finds_structural_duplicates(tmp_path):
    from local_deepwiki.generators.analysis.duplication import detect_type2_clones

    # Two functions with same structure but different names/values
    _write_py(
        tmp_path / "src" / "a.py",
        """
def process_users(users):
    result = []
    for user in users:
        if user.is_active():
            name = user.get_name()
            result.append(name)
    return result

def process_orders(orders):
    result = []
    for order in orders:
        if order.is_valid():
            total = order.get_total()
            result.append(total)
    return result
""",
    )
    clones = detect_type2_clones(tmp_path)
    assert len(clones) >= 1
    assert len(clones[0]["instances"]) >= 2


def test_detect_type2_clones_no_structural_duplicates(tmp_path):
    from local_deepwiki.generators.analysis.duplication import detect_type2_clones

    _write_py(
        tmp_path / "src" / "a.py",
        """
def simple():
    return 1

def complex_fn(x, y, z):
    if x > 0:
        for i in range(y):
            z += i
    return z
""",
    )
    clones = detect_type2_clones(tmp_path)
    # These have different structures, should not be grouped
    assert all(len(c["instances"]) < 2 for c in clones) if clones else True


def test_analyze_duplication_orchestrator(tmp_path):
    from local_deepwiki.generators.analysis.duplication import analyze_duplication

    _write_py(tmp_path / "src" / "a.py", _DUPLICATE_BLOCK + "\nx = 1\n")
    _write_py(tmp_path / "src" / "b.py", _DUPLICATE_BLOCK + "\ny = 2\n")
    result = analyze_duplication(tmp_path)
    assert result["status"] == "success"
    assert "type1_clones" in result
    assert "type2_clones" in result
    assert "stats" in result
    stats = result["stats"]
    assert "total_lines" in stats
    assert "duplicated_lines" in stats
    assert "duplication_ratio" in stats
    assert stats["duplication_ratio"] >= 0.0
    assert stats["duplication_ratio"] <= 1.0


def test_analyze_duplication_empty_repo(tmp_path):
    from local_deepwiki.generators.analysis.duplication import analyze_duplication

    result = analyze_duplication(tmp_path)
    assert result["status"] == "success"
    assert result["stats"]["total_lines"] == 0
    assert result["stats"]["duplication_ratio"] == 0.0


@pytest.mark.asyncio
async def test_handle_get_duplication_metrics(tmp_path):
    import json
    from unittest.mock import MagicMock, patch

    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_duplication_metrics,
    )

    _write_py(tmp_path / "src" / "a.py", "def foo():\n    return 1\n")
    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_duplication_metrics({"repo_path": str(tmp_path)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "type1_clones" in data
    assert "type2_clones" in data
