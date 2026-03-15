"""Tests for the get_complexity_metrics MCP tool."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_get_complexity_metrics
from local_deepwiki.models import GetComplexityMetricsArgs


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_metadata.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


async def test_complexity_metrics_python_file(mock_access_control, tmp_path):
    """Parsing a Python file with functions and classes returns correct counts."""
    src = tmp_path / "example.py"
    src.write_text(
        """\
def simple_func(x, y):
    return x + y

def complex_func(a, b, c):
    if a > 0:
        for i in range(b):
            if i % 2 == 0:
                print(i)
    elif b > 0:
        while c > 0:
            c -= 1
    return a + b + c

class MyClass:
    def method(self):
        pass
"""
    )
    result = await handle_get_complexity_metrics(
        {"repo_path": str(tmp_path), "file_path": "example.py"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["language"] == "python"
    assert data["counts"]["functions"] >= 2
    assert data["counts"]["classes"] >= 1
    assert data["lines"]["total"] > 0
    assert data["lines"]["blank"] >= 0
    assert data["lines"]["code"] > 0
    assert data["complexity"]["max_cyclomatic"] > 1


async def test_complexity_metrics_empty_file(mock_access_control, tmp_path):
    """An empty Python file returns zero functions and classes."""
    src = tmp_path / "empty.py"
    src.write_text("")
    result = await handle_get_complexity_metrics(
        {"repo_path": str(tmp_path), "file_path": "empty.py"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["counts"]["functions"] == 0
    assert data["counts"]["classes"] == 0
    assert data["lines"]["total"] == 0


async def test_complexity_metrics_unsupported_type(mock_access_control, tmp_path):
    """A .txt file returns a 'not supported' message without error."""
    txt = tmp_path / "notes.txt"
    txt.write_text("just some text")
    result = await handle_get_complexity_metrics(
        {"repo_path": str(tmp_path), "file_path": "notes.txt"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "not supported" in data["message"].lower()
    assert data["metrics"] == {}


async def test_complexity_metrics_nested_functions(mock_access_control, tmp_path):
    """Functions inside nested control flow report nesting depth."""
    src = tmp_path / "nested.py"
    src.write_text(
        """\
def outer():
    if True:
        for i in range(10):
            if i > 5:
                pass

def flat():
    return 1
"""
    )
    result = await handle_get_complexity_metrics(
        {"repo_path": str(tmp_path), "file_path": "nested.py"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["complexity"]["max_nesting_depth"] >= 0
    # outer() has nested if/for/if so max nesting should be tracked
    assert data["complexity"]["max_cyclomatic"] >= 1


async def test_complexity_metrics_with_comments(mock_access_control, tmp_path):
    """Comment lines are correctly counted."""
    src = tmp_path / "commented.py"
    src.write_text(
        """\
# This is a comment
# Another comment
def foo():
    # inline comment
    return 42
"""
    )
    result = await handle_get_complexity_metrics(
        {"repo_path": str(tmp_path), "file_path": "commented.py"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["lines"]["comment"] >= 3


async def test_complexity_metrics_file_not_found(mock_access_control, tmp_path):
    """A nonexistent file returns an error response."""
    result = await handle_get_complexity_metrics(
        {"repo_path": str(tmp_path), "file_path": "no_such_file.py"}
    )
    text = result[0].text.lower()
    assert "error" in text
    assert "does not exist" in text or "not found" in text


async def test_complexity_metrics_repo_not_found(mock_access_control):
    """A nonexistent repo returns an error response."""
    result = await handle_get_complexity_metrics(
        {
            "repo_path": "/nonexistent/repo/path",
            "file_path": "file.py",
        }
    )
    text = result[0].text.lower()
    assert "error" in text
    assert "does not exist" in text or "not found" in text


async def test_complexity_metrics_path_traversal(mock_access_control, tmp_path):
    """A path traversal attempt is rejected."""
    src = tmp_path / "legit.py"
    src.write_text("x = 1\n")
    result = await handle_get_complexity_metrics(
        {
            "repo_path": str(tmp_path),
            "file_path": "../../../etc/passwd",
        }
    )
    text = result[0].text.lower()
    assert "error" in text
    assert "traversal" in text or "invalid" in text


async def test_complexity_metrics_validation_error(mock_access_control):
    """Missing required fields returns a validation error response."""
    result = await handle_get_complexity_metrics({"repo_path": "/tmp"})
    text = result[0].text.lower()
    assert "error" in text
    assert "file_path" in text or "required" in text


async def test_complexity_metrics_args_model():
    """The Pydantic model validates correctly."""
    valid = GetComplexityMetricsArgs(repo_path="/some/path", file_path="src/main.py")
    assert valid.repo_path == "/some/path"
    assert valid.file_path == "src/main.py"

    # Empty file_path should fail min_length validation
    with pytest.raises(Exception):
        GetComplexityMetricsArgs(repo_path="/some/path", file_path="")

    # Missing file_path should fail
    with pytest.raises(Exception):
        GetComplexityMetricsArgs(repo_path="/some/path")


class TestComplexityMetricsPathResolution:
    """Tests for directory path detection in get_complexity_metrics."""

    async def test_directory_path_gives_clear_error(
        self, mock_access_control, tmp_path
    ):
        """Passing a directory path returns an error mentioning 'directory'."""
        # Create a directory with some .py files inside
        sub_dir = tmp_path / "mypackage"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text("")
        (sub_dir / "alpha.py").write_text("def alpha(): pass\n")
        (sub_dir / "beta.py").write_text("def beta(): pass\n")

        result = await handle_get_complexity_metrics(
            {"repo_path": str(tmp_path), "file_path": "mypackage"}
        )
        text = result[0].text.lower()
        assert "directory" in text
        # Should suggest specific files within the directory
        assert "alpha.py" in text or "beta.py" in text

    async def test_directory_path_no_py_files(self, mock_access_control, tmp_path):
        """Passing a directory with no .py files gives a clear directory error."""
        sub_dir = tmp_path / "emptydir"
        sub_dir.mkdir()

        result = await handle_get_complexity_metrics(
            {"repo_path": str(tmp_path), "file_path": "emptydir"}
        )
        text = result[0].text.lower()
        assert "directory" in text
        assert "not a file" in text

    async def test_valid_file_path_works(self, mock_access_control, tmp_path):
        """A normal .py file path still works after the directory check."""
        src = tmp_path / "valid.py"
        src.write_text("def hello(): return 1\n")

        result = await handle_get_complexity_metrics(
            {"repo_path": str(tmp_path), "file_path": "valid.py"}
        )
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["counts"]["functions"] >= 1
