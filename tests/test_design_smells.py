"""Tests for get_design_smells analysis tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_get_design_smells


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
def god_class_file(tmp_path: Path) -> Path:
    """Create a file with a God Class (>15 methods AND >500 lines)."""
    # 20 methods, each with 25 lines of body -> 20 * 27 lines ~ 540 total.
    method_body = "\n".join(f"        x_{j} = {j}" for j in range(25))
    methods = "\n\n".join(
        f"    def method_{i}(self):\n{method_body}\n        return {i}"
        for i in range(20)
    )
    content = f"class GodClass:\n{methods}\n"
    path = tmp_path / "god_class.py"
    path.write_text(content)
    return tmp_path


@pytest.fixture
def long_method_file(tmp_path: Path) -> Path:
    """Create a file with a Long Method (>80 lines)."""
    # Build a function with 85 lines.
    body = "\n".join(f"    x{i} = {i}" for i in range(85))
    content = f"def long_function(a):\n{body}\n    return a\n"
    path = tmp_path / "long_method.py"
    path.write_text(content)
    return tmp_path


@pytest.fixture
def long_param_file(tmp_path: Path) -> Path:
    """Create a file with a Long Parameter List (>6 params)."""
    content = "def many_params(a, b, c, d, e, f, g, h):\n    return a\n"
    path = tmp_path / "long_params.py"
    path.write_text(content)
    return tmp_path


@pytest.fixture
def large_file(tmp_path: Path) -> Path:
    """Create a file with >800 lines."""
    lines = "\n".join(f"x{i} = {i}" for i in range(810))
    path = tmp_path / "large.py"
    path.write_text(lines)
    return tmp_path


@pytest.fixture
def deep_nesting_file(tmp_path: Path) -> Path:
    """Create a file with deep nesting (>4 levels, i.e. 5+ control structures)."""
    content = """\
def deeply_nested(a, b, c, d, e, f):
    if a:
        for i in range(b):
            if i > 0:
                while c > 0:
                    if d:
                        for j in range(e):
                            return f
                    c -= 1
    return 0
"""
    path = tmp_path / "deep_nest.py"
    path.write_text(content)
    return tmp_path


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


async def test_design_smells_success(mock_access_control, tmp_path):
    """Handler returns success for an empty repo."""
    result = await handle_get_design_smells({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"


async def test_design_smells_empty_repo(mock_access_control, tmp_path):
    """Empty repo returns zero smells."""
    result = await handle_get_design_smells({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["smells"] == []
    assert data["summary"]["total"] == 0


async def test_design_smells_result_shape(mock_access_control, large_file):
    """Result has smells list and summary dict."""
    result = await handle_get_design_smells({"repo_path": str(large_file)})
    data = json.loads(result[0].text)
    assert "smells" in data
    assert "summary" in data
    summary = data["summary"]
    assert "total" in summary
    assert "by_severity" in summary
    assert "by_type" in summary


async def test_design_smells_smell_shape(mock_access_control, long_param_file):
    """Each smell entry has required keys."""
    result = await handle_get_design_smells(
        {"repo_path": str(long_param_file), "severity_threshold": "low"}
    )
    data = json.loads(result[0].text)
    required_keys = {
        "type",
        "severity",
        "file",
        "line",
        "entity",
        "description",
        "suggestion",
    }
    for smell in data["smells"]:
        assert required_keys <= set(smell.keys()), f"Missing keys in {smell}"


# ---------------------------------------------------------------------------
# Individual smell detection
# ---------------------------------------------------------------------------


async def test_detects_large_file(mock_access_control, large_file):
    """Large file (>800 lines) is detected as a 'large_file' smell."""
    result = await handle_get_design_smells(
        {"repo_path": str(large_file), "severity_threshold": "medium"}
    )
    data = json.loads(result[0].text)
    types = [s["type"] for s in data["smells"]]
    assert "large_file" in types


async def test_detects_long_method(mock_access_control, long_method_file):
    """Long method (>80 lines) is detected as 'long_method'."""
    result = await handle_get_design_smells(
        {"repo_path": str(long_method_file), "severity_threshold": "high"}
    )
    data = json.loads(result[0].text)
    types = [s["type"] for s in data["smells"]]
    assert "long_method" in types


async def test_detects_long_parameter_list(mock_access_control, long_param_file):
    """Function with >6 params is detected as 'long_parameter_list'."""
    result = await handle_get_design_smells(
        {"repo_path": str(long_param_file), "severity_threshold": "medium"}
    )
    data = json.loads(result[0].text)
    types = [s["type"] for s in data["smells"]]
    assert "long_parameter_list" in types


async def test_detects_deep_nesting(mock_access_control, deep_nesting_file):
    """Function with >4 nesting levels is detected as 'deep_nesting'."""
    result = await handle_get_design_smells(
        {"repo_path": str(deep_nesting_file), "severity_threshold": "medium"}
    )
    data = json.loads(result[0].text)
    types = [s["type"] for s in data["smells"]]
    assert "deep_nesting" in types


async def test_detects_god_class(mock_access_control, god_class_file):
    """God class (>15 methods AND >500 lines) is detected."""
    result = await handle_get_design_smells(
        {"repo_path": str(god_class_file), "severity_threshold": "high"}
    )
    data = json.loads(result[0].text)
    types = [s["type"] for s in data["smells"]]
    assert "god_class" in types


# ---------------------------------------------------------------------------
# Severity threshold filtering
# ---------------------------------------------------------------------------


async def test_severity_threshold_high_only(mock_access_control, long_param_file):
    """When threshold=high, medium smells (long_parameter_list) are excluded."""
    result = await handle_get_design_smells(
        {"repo_path": str(long_param_file), "severity_threshold": "high"}
    )
    data = json.loads(result[0].text)
    for smell in data["smells"]:
        assert smell["severity"] == "high", (
            f"Expected only high smells but got: {smell['severity']}"
        )


async def test_severity_threshold_low_includes_all(
    mock_access_control, long_param_file
):
    """When threshold=low, all severities are included."""
    result_low = await handle_get_design_smells(
        {"repo_path": str(long_param_file), "severity_threshold": "low"}
    )
    result_high = await handle_get_design_smells(
        {"repo_path": str(long_param_file), "severity_threshold": "high"}
    )
    data_low = json.loads(result_low[0].text)
    data_high = json.loads(result_high[0].text)
    assert data_low["summary"]["total"] >= data_high["summary"]["total"]


async def test_severity_threshold_invalid(mock_access_control, tmp_path):
    """An invalid severity_threshold returns an error status."""
    (tmp_path / "x.py").write_text("def f(): pass\n")
    result = await handle_get_design_smells(
        {"repo_path": str(tmp_path), "severity_threshold": "critical"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# Sorted output
# ---------------------------------------------------------------------------


async def test_smells_sorted_by_severity(mock_access_control, long_method_file):
    """Smells are sorted with higher severity first."""
    result = await handle_get_design_smells(
        {"repo_path": str(long_method_file), "severity_threshold": "low"}
    )
    data = json.loads(result[0].text)
    severity_order = {"high": 2, "medium": 1, "low": 0}
    values = [severity_order[s["severity"]] for s in data["smells"]]
    assert values == sorted(values, reverse=True)


# ---------------------------------------------------------------------------
# Exclude tests
# ---------------------------------------------------------------------------


async def test_exclude_tests_true(mock_access_control, tmp_path):
    """Test files are excluded when exclude_tests=True."""
    # Create a test file that would trigger long_parameter_list.
    test_file = tmp_path / "test_foo.py"
    test_file.write_text("def test_many_params(a, b, c, d, e, f, g, h):\n    pass\n")
    result = await handle_get_design_smells(
        {"repo_path": str(tmp_path), "exclude_tests": True}
    )
    data = json.loads(result[0].text)
    files_with_smells = [s["file"] for s in data["smells"]]
    assert not any("test_foo" in f for f in files_with_smells)


async def test_exclude_tests_false(mock_access_control, tmp_path):
    """Test files are included when exclude_tests=False."""
    test_file = tmp_path / "test_foo.py"
    test_file.write_text("def test_many_params(a, b, c, d, e, f, g, h):\n    pass\n")
    result = await handle_get_design_smells(
        {
            "repo_path": str(tmp_path),
            "exclude_tests": False,
            "severity_threshold": "low",
        }
    )
    data = json.loads(result[0].text)
    files_with_smells = [s["file"] for s in data["smells"]]
    assert any("test_foo" in f for f in files_with_smells)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


async def test_summary_counts(mock_access_control, long_param_file):
    """Summary total equals len(smells)."""
    result = await handle_get_design_smells(
        {"repo_path": str(long_param_file), "severity_threshold": "low"}
    )
    data = json.loads(result[0].text)
    assert data["summary"]["total"] == len(data["smells"])


async def test_summary_by_severity_keys(mock_access_control, tmp_path):
    """by_severity always has high, medium, low keys."""
    result = await handle_get_design_smells({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    by_sev = data["summary"]["by_severity"]
    assert "high" in by_sev
    assert "medium" in by_sev
    assert "low" in by_sev


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


async def test_design_smells_missing_repo(mock_access_control, tmp_path):
    """Non-existent repo returns an error response."""
    result = await handle_get_design_smells(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_feature_envy_ignores_common_utility_objects(
    mock_access_control, tmp_path
):
    """Functions calling logger/lines/parts repeatedly should not be flagged."""
    code = """\
def generate_page(data):
    logger.info("Starting generation")
    logger.debug("Processing %d items", len(data))
    logger.info("Building output")
    logger.warning("Slow generation detected")
    lines = []
    lines.append("# Title")
    lines.append("## Section")
    lines.append("Content here")
    lines.append("More content")
    return "\\n".join(lines)
"""
    (tmp_path / "utility_calls.py").write_text(code)
    result = await handle_get_design_smells(
        {"repo_path": str(tmp_path), "severity_threshold": "low"}
    )
    data = json.loads(result[0].text)
    feature_envy_smells = [s for s in data["smells"] if s["type"] == "feature_envy"]
    assert len(feature_envy_smells) == 0, (
        f"Expected no feature envy for logger/lines but got: {feature_envy_smells}"
    )


async def test_design_smells_data_clump_detection(mock_access_control, tmp_path):
    """Data clump is detected when 3+ functions share 3+ identical parameter names."""
    content = """\
def func_a(config, logger, timeout):
    pass


def func_b(config, logger, timeout):
    pass


def func_c(config, logger, timeout):
    pass
"""
    (tmp_path / "clumps.py").write_text(content)
    result = await handle_get_design_smells(
        {"repo_path": str(tmp_path), "severity_threshold": "low"}
    )
    data = json.loads(result[0].text)
    types = [s["type"] for s in data["smells"]]
    assert "data_clump" in types


def test_detects_dispatch_table_candidate(tmp_path):
    """Function with high CC but low line count should be flagged as dispatch candidate."""
    from local_deepwiki.generators.analysis.design_smells import analyze_design_smells

    code = """
def handle_status(code: int) -> str:
    if code == 200:
        return "ok"
    elif code == 201:
        return "created"
    elif code == 204:
        return "no content"
    elif code == 301:
        return "moved"
    elif code == 302:
        return "found"
    elif code == 400:
        return "bad request"
    elif code == 401:
        return "unauthorized"
    elif code == 403:
        return "forbidden"
    elif code == 404:
        return "not found"
    elif code == 405:
        return "method not allowed"
    elif code == 408:
        return "timeout"
    elif code == 409:
        return "conflict"
    elif code == 422:
        return "unprocessable"
    elif code == 429:
        return "rate limited"
    elif code == 500:
        return "server error"
    elif code == 502:
        return "bad gateway"
    elif code == 503:
        return "unavailable"
    else:
        return "unknown"
"""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "handler.py").write_text(code)
    result = analyze_design_smells(tmp_path, severity_threshold="medium")
    smell_types = [s["type"] for s in result["smells"]]
    assert "dispatch_table_candidate" in smell_types, (
        f"Expected dispatch_table_candidate smell, got types: {smell_types}"
    )
