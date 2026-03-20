"""Shared source-file filtering for analysis tools.

Centralizes test-file detection, directory skipping, and extension
matching so all analysis modules use consistent rules.
"""

from __future__ import annotations

import os
from pathlib import Path

from local_deepwiki.core.parser.languages import EXTENSION_MAP

# Directories always skipped during source scanning.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".deepwiki",
        "dist",
        "build",
        "coverage_html",
        "coverage_openai_embeddings",
        "htmlcov",
        ".git",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "egg-info",
        ".eggs",
    }
)

# Directory names that indicate test code.
TEST_DIR_NAMES: frozenset[str] = frozenset(
    {
        "tests",
        "test",
        "__tests__",
        "spec",
    }
)


def is_test_file(rel_path: Path) -> bool:
    """Return True if *rel_path* looks like a test file."""
    name = rel_path.name
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    return any(part in TEST_DIR_NAMES for part in rel_path.parts)


def should_skip_dir(dirname: str) -> bool:
    """Return True if *dirname* should be skipped during source scanning."""
    return dirname.startswith(".") or dirname in SKIP_DIRS


def iter_source_files(
    repo_path: Path,
    *,
    exclude_tests: bool = True,
    extensions: frozenset[str] | None = None,
) -> list[tuple[Path, Path]]:
    """Walk *repo_path* and return (full_path, rel_path) pairs for source files.

    Args:
        repo_path: Root of the repository.
        exclude_tests: Skip test files when True.
        extensions: File extensions to include (default: all tree-sitter supported).

    Returns:
        List of (absolute_path, relative_path) tuples, sorted by relative path.
    """
    if extensions is None:
        extensions = frozenset(EXTENSION_MAP.keys())

    results: list[tuple[Path, Path]] = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for fname in files:
            full_path = Path(root) / fname
            if full_path.suffix not in extensions:
                continue
            try:
                rel_path = full_path.relative_to(repo_path)
            except ValueError:
                continue
            if exclude_tests and is_test_file(rel_path):
                continue
            results.append((full_path, rel_path))

    results.sort(key=lambda pair: pair[1])
    return results


def iter_python_files(
    repo_path: Path,
    *,
    exclude_tests: bool = False,
) -> list[tuple[Path, Path]]:
    """Walk *repo_path* and return (full_path, rel_path) for .py files only."""
    return iter_source_files(
        repo_path,
        exclude_tests=exclude_tests,
        extensions=frozenset({".py"}),
    )
