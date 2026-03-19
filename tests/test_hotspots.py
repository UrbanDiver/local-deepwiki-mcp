"""Tests for get_hotspots analysis tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_get_hotspots


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def simple_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with two Python files of known complexity."""
    src = tmp_path / "module.py"
    src.write_text(
        """\
def simple(a, b):
    return a + b


def complex_func(x, y, z, w, v, u, t):
    if x > 0:
        for i in range(y):
            if i % 2 == 0:
                while z > 0:
                    z -= 1
    elif y > 0:
        for j in range(x):
            pass
    else:
        try:
            result = x / y
        except ZeroDivisionError:
            result = 0
    return result


class MyClass:
    def method_one(self, a):
        return a

    def method_two(self, a, b, c, d, e, f, g):
        if a:
            pass
        return b
"""
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


async def test_hotspots_returns_success(mock_access_control, simple_repo):
    """Handler returns a success response."""
    result = await handle_get_hotspots({"repo_path": str(simple_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"


async def test_hotspots_default_metric_complexity(mock_access_control, simple_repo):
    """Default metric is complexity; top function should have highest CC."""
    result = await handle_get_hotspots({"repo_path": str(simple_repo)})
    data = json.loads(result[0].text)
    hotspots = data["hotspots"]
    assert len(hotspots) > 0
    # First result should have highest metric_value.
    values = [h["metric_value"] for h in hotspots]
    assert values == sorted(values, reverse=True)


async def test_hotspots_metric_params(mock_access_control, simple_repo):
    """Metric=params ranks by parameter count."""
    result = await handle_get_hotspots(
        {"repo_path": str(simple_repo), "metric": "params"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    hotspots = data["hotspots"]
    # complex_func has 7 params, should be first.
    assert hotspots[0]["details"]["params"] >= 6


async def test_hotspots_metric_length(mock_access_control, simple_repo):
    """Metric=length ranks by line count."""
    result = await handle_get_hotspots(
        {"repo_path": str(simple_repo), "metric": "length"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    hotspots = data["hotspots"]
    values = [h["metric_value"] for h in hotspots]
    assert values == sorted(values, reverse=True)


async def test_hotspots_metric_nesting(mock_access_control, simple_repo):
    """Metric=nesting ranks by nesting depth."""
    result = await handle_get_hotspots(
        {"repo_path": str(simple_repo), "metric": "nesting"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    hotspots = data["hotspots"]
    values = [h["metric_value"] for h in hotspots]
    assert values == sorted(values, reverse=True)


async def test_hotspots_top_n(mock_access_control, simple_repo):
    """top_n limits the number of results."""
    result = await handle_get_hotspots({"repo_path": str(simple_repo), "top_n": 2})
    data = json.loads(result[0].text)
    assert len(data["hotspots"]) <= 2


async def test_hotspots_min_threshold(mock_access_control, simple_repo):
    """min_threshold filters out functions below the threshold."""
    result = await handle_get_hotspots(
        {"repo_path": str(simple_repo), "metric": "complexity", "min_threshold": 5}
    )
    data = json.loads(result[0].text)
    for h in data["hotspots"]:
        assert h["metric_value"] >= 5


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


async def test_hotspots_result_shape(mock_access_control, simple_repo):
    """Each hotspot contains required keys with correct types."""
    result = await handle_get_hotspots({"repo_path": str(simple_repo)})
    data = json.loads(result[0].text)
    for h in data["hotspots"]:
        assert "function" in h
        assert "file" in h
        assert "line" in h
        assert "metric_value" in h
        details = h["details"]
        assert "cyclomatic" in details
        assert "params" in details
        assert "length" in details
        assert "nesting" in details


async def test_hotspots_stats(mock_access_control, simple_repo):
    """Stats section reports total_functions, files_scanned, and metric_used."""
    result = await handle_get_hotspots(
        {"repo_path": str(simple_repo), "metric": "params"}
    )
    data = json.loads(result[0].text)
    stats = data["stats"]
    assert stats["metric_used"] == "params"
    assert stats["files_scanned"] >= 1
    assert stats["total_functions"] >= 1


# ---------------------------------------------------------------------------
# Exclude tests
# ---------------------------------------------------------------------------


async def test_hotspots_exclude_tests(mock_access_control, tmp_path):
    """Test files are excluded when exclude_tests=True."""
    (tmp_path / "test_foo.py").write_text(
        "def test_something(a, b, c, d, e, f, g):\n    pass\n"
    )
    (tmp_path / "src.py").write_text("def real_func(x):\n    return x\n")

    result_exclude = await handle_get_hotspots(
        {"repo_path": str(tmp_path), "exclude_tests": True}
    )
    data = json.loads(result_exclude[0].text)
    funcs = [h["function"] for h in data["hotspots"]]
    assert "test_something" not in funcs
    assert "real_func" in funcs


async def test_hotspots_include_tests(mock_access_control, tmp_path):
    """Test files are included when exclude_tests=False."""
    (tmp_path / "test_foo.py").write_text(
        "def test_something(a, b, c, d, e, f, g):\n    pass\n"
    )
    result = await handle_get_hotspots(
        {"repo_path": str(tmp_path), "exclude_tests": False}
    )
    data = json.loads(result[0].text)
    funcs = [h["function"] for h in data["hotspots"]]
    assert "test_something" in funcs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_hotspots_invalid_metric(mock_access_control, tmp_path):
    """An invalid metric returns an error status."""
    (tmp_path / "x.py").write_text("def f(): pass\n")
    result = await handle_get_hotspots(
        {"repo_path": str(tmp_path), "metric": "invalid_metric"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_hotspots_empty_repo(mock_access_control, tmp_path):
    """An empty repo returns zero functions."""
    result = await handle_get_hotspots({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["hotspots"] == []
    assert data["stats"]["total_functions"] == 0


async def test_hotspots_missing_repo(mock_access_control, tmp_path):
    """A non-existent repo returns an error response."""
    result = await handle_get_hotspots({"repo_path": str(tmp_path / "nonexistent")})
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_hotspots_only_non_py_files(mock_access_control, tmp_path):
    """A repo with only .txt files returns zero functions."""
    (tmp_path / "notes.txt").write_text("just text\n")
    result = await handle_get_hotspots({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["stats"]["total_functions"] == 0


async def test_hotspots_pydantic_validation(mock_access_control, tmp_path):
    """top_n=0 (below minimum) returns an error response."""
    result = await handle_get_hotspots({"repo_path": str(tmp_path), "top_n": 0})
    data = json.loads(result[0].text)
    assert data["status"] == "error"
