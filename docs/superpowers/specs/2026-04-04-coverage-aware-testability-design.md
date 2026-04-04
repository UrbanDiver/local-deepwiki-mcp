# Coverage-Aware Testability Metric

## Problem

The testability scorer uses filename matching (`test_foo.py` → `foo.py`) to determine which source files are "tested." This produces 69.5% untested file rate despite 92.7% actual code coverage, because most files are covered by integration tests without a 1:1 test file.

## Design

### Change Summary

`testability.py`'s `analyze_testability` reads the `.coverage` SQLite database (produced by `pytest --cov`) to determine per-file line coverage. A file is "untested" only if it has 0 lines covered. Falls back to filename matching when no coverage data exists.

### Interface

`analyze_testability(repo_path, *, coverage_path=None, exclude_patterns=None)`

- `coverage_path: Path | None` — explicit path to `.coverage` file. When `None`, auto-discovers `<repo_path>/.coverage`.
- Returns: existing shape plus two new stats fields:
  - `"coverage_source": "coverage_db" | "filename_heuristic"` — which method was used
  - `"actual_coverage_pct": float` — average line coverage across source files (only when coverage DB available)

### Logic

1. Check for `.coverage` file at `coverage_path` or `<repo_path>/.coverage`
2. If found:
   - Read via `coverage.CoverageData()` API (`coverage` package, already a test dependency)
   - For each source file, check if it appears in the coverage data with > 0 executed lines
   - `untested_files` = source files with 0 covered lines or absent from coverage data
   - Compute `actual_coverage_pct` as mean of per-file coverage percentages
3. If not found:
   - Fall back to current filename-matching heuristic
   - `coverage_source` = `"filename_heuristic"`

### What Does NOT Change

- `score_testability` in `health_scoring.py` — already consumes `untested_file_pct`; no changes needed
- Test-to-code ratio calculation (line-count based, independent of coverage)
- Assertion counting
- All existing return fields (changes are additive)
- `architecture_health.py` orchestrator — no changes needed

### Dependencies

- `coverage` package — already installed as a test dependency (`pytest-cov` depends on it). Used only for reading the `.coverage` database, not for running coverage. Import is guarded with try/except so the feature degrades gracefully if `coverage` is not installed.

### Expected Impact

- `untested_file_pct`: 69.5% → ~1-3% (only `web/rate_limit.py` at 0%)
- Testability score: B (75.7) → A (~95)
- Overall health: B (88.3) → A (~90)
