"""Testability metrics: test-to-code ratio, test coverage mapping, assertion density.

Uses file naming conventions to discover test files and match them to source.
No LLM calls -- pure computation on file structure.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_TEST_FILE_RE = re.compile(r"(^test_.*\.py$|.*_test\.py$|.*_spec\.py$)")
_TEST_DIR_RE = re.compile(r"(^|/)(__tests__|tests?)/")


def _is_test_file(rel_path: str) -> bool:
    """Return True if a relative path looks like a test file.

    Matches filenames like ``test_*.py``, ``*_test.py``, ``*_spec.py``
    or paths containing ``/tests/``, ``/test/``, or ``/__tests__/``.
    """
    filename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
    if _TEST_FILE_RE.match(filename):
        return True
    if _TEST_DIR_RE.search(rel_path):
        return True
    return False


def _match_test_to_source(
    test_path: str,
    source_files: set[str],
) -> str | None:
    """Heuristic matching: map a test file to its likely source file.

    Given ``tests/test_foo.py``, look for ``src/**/foo.py`` in *source_files*.
    Tries stripping ``test_`` prefix and ``_test`` / ``_spec`` suffix from the
    filename stem.
    """
    filename = test_path.rsplit("/", 1)[-1] if "/" in test_path else test_path
    stem = filename.removesuffix(".py")

    # Build candidate stems
    candidates: list[str] = []
    if stem.startswith("test_"):
        candidates.append(stem[5:])
    if stem.endswith("_test"):
        candidates.append(stem[:-5])
    if stem.endswith("_spec"):
        candidates.append(stem[:-5])

    for candidate in candidates:
        target = f"{candidate}.py"
        for src in source_files:
            if src.endswith(f"/{target}") or src == target:
                return src

    return None


def _count_assertions(content: str) -> int:
    """Count assertion statements in a file.

    Counts lines containing:
    - ``assert `` (Python assert keyword)
    - ``.assert`` (pytest/unittest methods like assertEqual, assertTrue)
    - ``self.assert`` (unittest assertion methods)
    """
    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert ") or stripped.startswith("assert("):
            count += 1
        elif ".assert" in stripped:
            count += 1
    return count


def analyze_testability(
    repo_path: Path | str,
    *,
    exclude_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze testability metrics for a repository.

    Walks all Python files, classifies them as test or source, computes
    test-to-code ratio, matches test files to source, counts assertions,
    and identifies untested modules.

    Args:
        repo_path: Repository root directory.
        exclude_patterns: Optional glob patterns to exclude.

    Returns:
        Dict with status, test_files, untested_files, and stats.
    """
    repo_path = Path(repo_path)

    test_files: list[dict[str, Any]] = []
    source_files_set: set[str] = set()
    source_lines = 0
    test_lines = 0
    total_assertions = 0

    # Collect all Python files
    all_py: list[tuple[Path, str]] = []
    for py_file in sorted(repo_path.rglob("*.py")):
        try:
            rel_path = str(py_file.relative_to(repo_path))
        except ValueError:
            continue

        # Skip hidden dirs and common non-source trees
        parts = rel_path.split("/")
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__")
            for part in parts
        ):
            continue

        all_py.append((py_file, rel_path))

    # Classify files
    test_paths: list[tuple[Path, str]] = []
    source_paths: list[tuple[Path, str]] = []

    for full_path, rel_path in all_py:
        if _is_test_file(rel_path):
            test_paths.append((full_path, rel_path))
        else:
            source_paths.append((full_path, rel_path))
            source_files_set.add(rel_path)

    # Count source lines
    for full_path, _rel in source_paths:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            source_lines += len(content.splitlines())
        except OSError:
            continue

    # Process test files
    for full_path, rel_path in test_paths:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = len(content.splitlines())
        test_lines += lines
        assertions = _count_assertions(content)
        total_assertions += assertions
        matched = _match_test_to_source(rel_path, source_files_set)

        test_files.append(
            {
                "file": rel_path,
                "lines": lines,
                "assertions": assertions,
                "matches_source": matched,
            }
        )

    # Identify untested source files
    tested_sources = {tf["matches_source"] for tf in test_files if tf["matches_source"]}
    untested_files = sorted(
        rel for rel in source_files_set if rel not in tested_sources
    )

    total_source = len(source_paths)
    total_test = len(test_paths)
    untested_count = len(untested_files)
    untested_pct = (untested_count / total_source * 100) if total_source > 0 else 0.0
    ratio = test_lines / source_lines if source_lines > 0 else 0.0
    avg_assertions = total_assertions / total_test if total_test > 0 else 0.0

    logger.info(
        "Testability: %d test files, %d source files, ratio=%.2f in %s",
        total_test,
        total_source,
        ratio,
        repo_path,
    )

    return {
        "status": "success",
        "test_files": test_files,
        "untested_files": untested_files,
        "stats": {
            "source_lines": source_lines,
            "test_lines": test_lines,
            "test_to_code_ratio": round(ratio, 4),
            "total_source_files": total_source,
            "total_test_files": total_test,
            "untested_file_count": untested_count,
            "untested_file_pct": round(untested_pct, 1),
            "total_assertions": total_assertions,
            "avg_assertions_per_test": round(avg_assertions, 2),
        },
    }
