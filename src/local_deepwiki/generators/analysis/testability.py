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

try:
    from coverage import CoverageData  # type: ignore[import-untyped]
except ImportError:
    CoverageData = None  # type: ignore[assignment,misc]

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


def _collect_python_files(repo_path: Path) -> list[tuple[Path, str]]:
    """Walk repo for .py files, skipping hidden/non-source dirs."""
    all_py: list[tuple[Path, str]] = []
    for py_file in sorted(repo_path.rglob("*.py")):
        try:
            rel_path = str(py_file.relative_to(repo_path))
        except ValueError:
            continue

        parts = rel_path.split("/")
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__")
            for part in parts
        ):
            continue

        all_py.append((py_file, rel_path))
    return all_py


def _classify_files(
    all_py: list[tuple[Path, str]],
    source_files_set: set[str],
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    """Split files into test and source lists. Populates *source_files_set* in place."""
    test_paths: list[tuple[Path, str]] = []
    source_paths: list[tuple[Path, str]] = []

    for full_path, rel_path in all_py:
        if _is_test_file(rel_path):
            test_paths.append((full_path, rel_path))
        else:
            source_paths.append((full_path, rel_path))
            source_files_set.add(rel_path)

    return test_paths, source_paths


def _count_source_lines(source_paths: list[tuple[Path, str]]) -> int:
    """Sum line counts across source files."""
    total = 0
    for full_path, _rel in source_paths:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            total += len(content.splitlines())
        except OSError:
            continue
    return total


def _process_test_files(
    test_paths: list[tuple[Path, str]],
    source_files_set: set[str],
) -> tuple[list[dict[str, Any]], int, int]:
    """Read test files, count assertions, match to source.

    Returns (test_files, test_lines, total_assertions).
    """
    test_files: list[dict[str, Any]] = []
    test_lines = 0
    total_assertions = 0

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

    return test_files, test_lines, total_assertions


def _read_coverage_db(
    coverage_path: Path,
    repo_path: Path,
    source_files_set: set[str],
) -> tuple[set[str], float] | None:
    """Read a ``.coverage`` database and return covered source files.

    Args:
        coverage_path: Path to the ``.coverage`` SQLite database.
        repo_path: Repository root (used to resolve relative paths).
        source_files_set: Set of relative source file paths to check.

    Returns:
        Tuple of (covered_files_set, avg_coverage_pct) or ``None`` if the
        database cannot be read.
    """
    if CoverageData is None:
        logger.debug("coverage package not available, skipping coverage DB")
        return None

    if not coverage_path.is_file():
        return None

    try:
        cd = CoverageData(str(coverage_path))
        cd.read()
    except Exception:
        logger.debug("Failed to read coverage database at %s", coverage_path)
        return None

    measured = cd.measured_files()
    if not measured:
        return None

    # Build absolute -> relative lookup for source files
    abs_to_rel: dict[str, str] = {}
    for rel in source_files_set:
        abs_path = str((repo_path / rel).resolve())
        abs_to_rel[abs_path] = rel

    covered: set[str] = set()
    coverage_pcts: list[float] = []

    for abs_path, rel_path in abs_to_rel.items():
        lines = cd.lines(abs_path)
        if lines:
            covered.add(rel_path)
            coverage_pcts.append(100.0)  # Has coverage (> 0 lines)
        else:
            coverage_pcts.append(0.0)

    avg_cov = sum(coverage_pcts) / len(coverage_pcts) if coverage_pcts else 0.0
    return covered, avg_cov


def _compute_testability_stats(
    source_paths: list[tuple[Path, str]],
    test_paths: list[tuple[Path, str]],
    test_files: list[dict[str, Any]],
    source_lines: int,
    test_lines: int,
    total_assertions: int,
    source_files_set: set[str],
    *,
    covered_files: set[str] | None = None,
    avg_coverage_pct: float | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Compute summary statistics.

    Args:
        covered_files: Files with > 0% line coverage from coverage DB.
            When provided, overrides filename-heuristic matching for
            determining untested files.
        avg_coverage_pct: Average coverage percentage across source files.

    Returns (untested_files, stats_dict).
    """
    if covered_files is not None:
        # Use real coverage data
        untested_files = sorted(
            rel for rel in source_files_set if rel not in covered_files
        )
        coverage_source = "coverage_db"
    else:
        # Fall back to filename-heuristic matching
        tested_sources = {
            tf["matches_source"] for tf in test_files if tf["matches_source"]
        }
        untested_files = sorted(
            rel for rel in source_files_set if rel not in tested_sources
        )
        coverage_source = "filename_heuristic"

    total_source = len(source_paths)
    total_test = len(test_paths)
    untested_count = len(untested_files)
    untested_pct = (untested_count / total_source * 100) if total_source > 0 else 0.0
    ratio = test_lines / source_lines if source_lines > 0 else 0.0
    avg_assertions = total_assertions / total_test if total_test > 0 else 0.0

    stats: dict[str, Any] = {
        "source_lines": source_lines,
        "test_lines": test_lines,
        "test_to_code_ratio": round(ratio, 4),
        "total_source_files": total_source,
        "total_test_files": total_test,
        "untested_file_count": untested_count,
        "untested_file_pct": round(untested_pct, 1),
        "total_assertions": total_assertions,
        "avg_assertions_per_test": round(avg_assertions, 2),
        "coverage_source": coverage_source,
    }
    if avg_coverage_pct is not None:
        stats["actual_coverage_pct"] = round(avg_coverage_pct, 1)

    return untested_files, stats


def analyze_testability(
    repo_path: Path | str,
    *,
    coverage_path: Path | None = None,
    exclude_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze testability metrics for a repository.

    Walks all Python files, classifies them as test or source, computes
    test-to-code ratio, matches test files to source, counts assertions,
    and identifies untested modules.

    When a ``.coverage`` database is available (from ``pytest --cov``),
    uses actual line-coverage data to determine which files are tested.
    Falls back to filename-heuristic matching otherwise.

    Args:
        repo_path: Repository root directory.
        coverage_path: Explicit path to ``.coverage`` database. Auto-discovers
            ``<repo_path>/.coverage`` when ``None``.
        exclude_patterns: Optional glob patterns to exclude.

    Returns:
        Dict with status, test_files, untested_files, and stats.
    """
    repo_path = Path(repo_path)

    source_files_set: set[str] = set()
    all_py = _collect_python_files(repo_path)
    test_paths, source_paths = _classify_files(all_py, source_files_set)
    source_lines = _count_source_lines(source_paths)
    test_files, test_lines, total_assertions = _process_test_files(
        test_paths, source_files_set
    )

    # Try to read real coverage data
    cov_path = coverage_path or (repo_path / ".coverage")
    cov_result = _read_coverage_db(cov_path, repo_path, source_files_set)
    covered_files = cov_result[0] if cov_result else None
    avg_coverage_pct = cov_result[1] if cov_result else None

    untested_files, stats = _compute_testability_stats(
        source_paths,
        test_paths,
        test_files,
        source_lines,
        test_lines,
        total_assertions,
        source_files_set,
        covered_files=covered_files,
        avg_coverage_pct=avg_coverage_pct,
    )

    logger.info(
        "Testability: %d test files, %d source files, ratio=%.2f, source=%s in %s",
        len(test_paths),
        len(source_paths),
        stats["test_to_code_ratio"],
        stats.get("coverage_source", "unknown"),
        repo_path,
    )

    return {
        "status": "success",
        "test_files": test_files,
        "untested_files": untested_files,
        "stats": stats,
    }
