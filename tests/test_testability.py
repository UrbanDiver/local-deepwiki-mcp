"""Tests for testability metrics module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# _is_test_file
# ---------------------------------------------------------------------------


def test_is_test_file_test_prefix():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("test_foo.py") is True


def test_is_test_file_test_suffix():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("foo_test.py") is True


def test_is_test_file_spec_suffix():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("foo_spec.py") is True


def test_is_test_file_in_tests_dir():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("tests/helpers.py") is True


def test_is_test_file_in_test_dir():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("test/helpers.py") is True


def test_is_test_file_in_dunder_tests_dir():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("__tests__/helpers.py") is True


def test_is_test_file_regular_source():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("src/module.py") is False


def test_is_test_file_conftest():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    # conftest.py in tests/ dir is a test file by directory
    assert _is_test_file("tests/conftest.py") is True


def test_is_test_file_nested_test_prefix():
    from local_deepwiki.generators.analysis.testability import _is_test_file

    assert _is_test_file("src/test_utils.py") is True


# ---------------------------------------------------------------------------
# _count_assertions
# ---------------------------------------------------------------------------


def test_count_assertions_assert_keyword():
    from local_deepwiki.generators.analysis.testability import _count_assertions

    content = "assert x == 1\nassert y > 2\n"
    assert _count_assertions(content) == 2


def test_count_assertions_assert_paren():
    from local_deepwiki.generators.analysis.testability import _count_assertions

    content = "assert(x == 1)\n"
    assert _count_assertions(content) == 1


def test_count_assertions_unittest_methods():
    from local_deepwiki.generators.analysis.testability import _count_assertions

    content = (
        "self.assertEqual(a, b)\n"
        "self.assertTrue(x)\n"
        "self.assertFalse(y)\n"
        "self.assertIn(a, b)\n"
        "self.assertRaises(Err)\n"
    )
    assert _count_assertions(content) == 5


def test_count_assertions_no_assertions():
    from local_deepwiki.generators.analysis.testability import _count_assertions

    content = "x = 1\ny = 2\nprint(x + y)\n"
    assert _count_assertions(content) == 0


def test_count_assertions_comment_not_counted():
    from local_deepwiki.generators.analysis.testability import _count_assertions

    # Lines starting with # won't start with "assert" after strip
    content = "# assert x == 1\n"
    assert _count_assertions(content) == 0


def test_count_assertions_mixed():
    from local_deepwiki.generators.analysis.testability import _count_assertions

    content = "assert x == 1\nprint('hello')\nself.assertEqual(1, 1)\ny = 3\n"
    assert _count_assertions(content) == 2


# ---------------------------------------------------------------------------
# analyze_testability — basic
# ---------------------------------------------------------------------------


def test_analyze_testability_basic(tmp_path):
    from local_deepwiki.generators.analysis.testability import analyze_testability

    _write_py(tmp_path / "src" / "module.py", "def foo():\n    return 1\n")
    _write_py(
        tmp_path / "tests" / "test_module.py",
        "from src.module import foo\n\ndef test_foo():\n    assert foo() == 1\n",
    )

    result = analyze_testability(tmp_path)
    assert result["status"] == "success"
    assert len(result["test_files"]) == 1
    assert result["stats"]["total_source_files"] >= 1
    assert result["stats"]["total_test_files"] == 1
    assert result["stats"]["total_assertions"] == 1
    assert result["stats"]["test_to_code_ratio"] > 0


def test_analyze_testability_no_tests(tmp_path):
    from local_deepwiki.generators.analysis.testability import analyze_testability

    _write_py(tmp_path / "src" / "module.py", "def foo():\n    return 1\n")

    result = analyze_testability(tmp_path)
    assert result["status"] == "success"
    assert result["stats"]["total_test_files"] == 0
    assert result["stats"]["test_to_code_ratio"] == 0.0
    assert result["stats"]["total_assertions"] == 0
    assert result["stats"]["avg_assertions_per_test"] == 0.0


def test_analyze_testability_empty_repo(tmp_path):
    from local_deepwiki.generators.analysis.testability import analyze_testability

    result = analyze_testability(tmp_path)
    assert result["status"] == "success"
    assert result["stats"]["total_source_files"] == 0
    assert result["stats"]["total_test_files"] == 0
    assert result["stats"]["test_to_code_ratio"] == 0.0
    assert result["stats"]["untested_file_pct"] == 0.0


def test_analyze_testability_match_test_to_source(tmp_path):
    from local_deepwiki.generators.analysis.testability import analyze_testability

    _write_py(tmp_path / "src" / "parser.py", "def parse(): pass\n")
    _write_py(
        tmp_path / "tests" / "test_parser.py",
        "def test_parse():\n    assert True\n",
    )

    result = analyze_testability(tmp_path)
    matched = [tf for tf in result["test_files"] if tf["matches_source"] is not None]
    assert len(matched) >= 1
    assert matched[0]["matches_source"].endswith("parser.py")


def test_analyze_testability_untested_files(tmp_path):
    from local_deepwiki.generators.analysis.testability import analyze_testability

    _write_py(tmp_path / "src" / "module_a.py", "def a(): pass\n")
    _write_py(tmp_path / "src" / "module_b.py", "def b(): pass\n")
    _write_py(
        tmp_path / "tests" / "test_module_a.py",
        "def test_a():\n    assert True\n",
    )

    result = analyze_testability(tmp_path)
    untested = result["untested_files"]
    # module_b.py should be untested
    assert any("module_b.py" in f for f in untested)
    assert result["stats"]["untested_file_count"] >= 1


def test_analyze_testability_skips_hidden_dirs(tmp_path):
    from local_deepwiki.generators.analysis.testability import analyze_testability

    _write_py(tmp_path / ".venv" / "lib.py", "x = 1\n")
    _write_py(tmp_path / "src" / "module.py", "def foo(): pass\n")

    result = analyze_testability(tmp_path)
    # .venv should be excluded
    all_files = [tf["file"] for tf in result["test_files"]] + result["untested_files"]
    assert not any(".venv" in f for f in all_files)


# ---------------------------------------------------------------------------
# Handler (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_get_testability_metrics(tmp_path):
    from local_deepwiki.handlers.analysis_architecture import (
        handle_get_testability_metrics,
    )

    _write_py(tmp_path / "src" / "a.py", "def foo():\n    return 1\n")
    _write_py(
        tmp_path / "tests" / "test_a.py",
        "def test_foo():\n    assert True\n",
    )

    mock_controller = MagicMock()
    mock_controller.require_permission.return_value = None
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller",
        return_value=mock_controller,
    ):
        result = await handle_get_testability_metrics({"repo_path": str(tmp_path)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "test_files" in data
    assert "stats" in data
