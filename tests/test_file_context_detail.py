"""Tests for get_file_context detail_level helpers.

Tests _extract_entities, _find_related_tests, and _get_recent_commits
from the analysis_metadata handler module.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.handlers.analysis_metadata import (
    _extract_entities,
    _find_related_tests,
    _get_recent_commits,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with a Python module and a test file."""
    # Source file with a class and a function
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    module_file = src_dir / "calculator.py"
    module_file.write_text(
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "\n"
        "def multiply(x, y):\n"
        "    return x * y\n",
        encoding="utf-8",
    )

    # Test file importing the module
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    test_file = test_dir / "test_calculator.py"
    test_file.write_text(
        "from calculator import Calculator, multiply\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    calc = Calculator()\n"
        "    assert calc.add(1, 2) == 3\n"
        "\n"
        "\n"
        "def test_multiply():\n"
        "    assert multiply(3, 4) == 12\n",
        encoding="utf-8",
    )

    # Initialize git repo and commit
    subprocess.run(
        ["git", "init"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )

    return tmp_path


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------


class TestExtractEntities:
    """Tests for the _extract_entities helper."""

    def test_extracts_class_and_function(self, git_repo: Path) -> None:
        """Should find the top-level class and function with correct line numbers."""
        entities = _extract_entities(git_repo / "src" / "calculator.py")

        names = [e["name"] for e in entities]
        assert "Calculator" in names
        assert "multiply" in names

        # Verify structure
        for entity in entities:
            assert "name" in entity
            assert "type" in entity
            assert "line" in entity
            assert entity["type"] in ("function", "class")
            assert isinstance(entity["line"], int)
            assert entity["line"] >= 1

    def test_class_entity_type(self, git_repo: Path) -> None:
        """Calculator should be detected as a class."""
        entities = _extract_entities(git_repo / "src" / "calculator.py")
        class_entities = [e for e in entities if e["name"] == "Calculator"]
        assert len(class_entities) == 1
        assert class_entities[0]["type"] == "class"

    def test_function_entity_type(self, git_repo: Path) -> None:
        """multiply should be detected as a function."""
        entities = _extract_entities(git_repo / "src" / "calculator.py")
        func_entities = [e for e in entities if e["name"] == "multiply"]
        assert len(func_entities) == 1
        assert func_entities[0]["type"] == "function"

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        """Should return an empty list for a file that does not exist."""
        result = _extract_entities(tmp_path / "nonexistent.py")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        """Should return an empty list for an empty file."""
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")
        result = _extract_entities(empty)
        assert result == []

    def test_parse_failure_returns_empty(self, tmp_path: Path) -> None:
        """Should return an empty list when CodeParser raises."""
        py_file = tmp_path / "broken.py"
        py_file.write_text("def foo(): pass", encoding="utf-8")
        with patch(
            "local_deepwiki.core.parser.CodeParser",
            side_effect=RuntimeError("parse error"),
        ):
            result = _extract_entities(py_file)
        assert result == []


# ---------------------------------------------------------------------------
# _find_related_tests
# ---------------------------------------------------------------------------


class TestFindRelatedTests:
    """Tests for the _find_related_tests helper."""

    def test_finds_test_importing_module(self, git_repo: Path) -> None:
        """Should find the test file that imports calculator."""
        results = _find_related_tests(git_repo, "src/calculator.py")
        assert len(results) >= 1
        assert any("test_calculator" in r for r in results)

    def test_no_tests_for_unrelated_module(self, git_repo: Path) -> None:
        """Should return empty for a module no test file references."""
        # Create a module that no test imports
        (git_repo / "src" / "orphan.py").write_text(
            "def lonely(): pass\n", encoding="utf-8"
        )
        results = _find_related_tests(git_repo, "src/orphan.py")
        assert results == []

    def test_no_test_directory(self, tmp_path: Path) -> None:
        """Should return empty when no tests/ or test/ directory exists."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        results = _find_related_tests(tmp_path, "src/mod.py")
        assert results == []

    def test_results_are_sorted(self, git_repo: Path) -> None:
        """Returned paths should be sorted."""
        # Add a second test file
        test_dir = git_repo / "tests"
        (test_dir / "test_z_calculator.py").write_text(
            "import calculator\n", encoding="utf-8"
        )
        results = _find_related_tests(git_repo, "src/calculator.py")
        assert results == sorted(results)


# ---------------------------------------------------------------------------
# _get_recent_commits
# ---------------------------------------------------------------------------


class TestGetRecentCommits:
    """Tests for the _get_recent_commits helper."""

    def test_returns_commits_for_file(self, git_repo: Path) -> None:
        """Should return at least the initial commit."""
        commits = _get_recent_commits(git_repo, "src/calculator.py")
        assert len(commits) >= 1
        assert "sha" in commits[0]
        assert "message" in commits[0]
        assert commits[0]["message"] == "initial commit"

    def test_respects_limit(self, git_repo: Path) -> None:
        """Should not return more commits than the limit."""
        # Add a second commit
        calc = git_repo / "src" / "calculator.py"
        calc.write_text(
            calc.read_text(encoding="utf-8")
            + "\ndef subtract(a, b):\n    return a - b\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=str(git_repo),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add subtract"],
            cwd=str(git_repo),
            capture_output=True,
            check=True,
        )

        commits = _get_recent_commits(git_repo, "src/calculator.py", limit=1)
        assert len(commits) == 1
        assert commits[0]["message"] == "add subtract"

    def test_non_git_repo_returns_empty(self, tmp_path: Path) -> None:
        """Should return empty list for a directory that is not a git repo."""
        (tmp_path / "file.py").write_text("x = 1\n", encoding="utf-8")
        commits = _get_recent_commits(tmp_path, "file.py")
        assert commits == []

    def test_nonexistent_file_returns_empty(self, git_repo: Path) -> None:
        """Should return empty list when git log finds no commits for the path."""
        commits = _get_recent_commits(git_repo, "nonexistent.py")
        assert commits == []

    def test_commit_sha_format(self, git_repo: Path) -> None:
        """Short SHA should be a reasonable length (7-12 chars)."""
        commits = _get_recent_commits(git_repo, "src/calculator.py")
        assert len(commits) >= 1
        sha = commits[0]["sha"]
        assert 7 <= len(sha) <= 12
        assert sha.isalnum()
