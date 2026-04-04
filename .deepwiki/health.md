# Architecture Health

**Overall Grade: B (89/100)**

## Scores by Dimension

| Dimension | Score | Grade |
|-----------|-------|-------|
| Complexity | 89.6 | B |
| Coupling | 79.1 | B |
| Smells | 95.2 | A |
| Layers | 100.0 | A |
| Churn | 100.0 | A |
| Cohesion | 66.7 | C |
| Duplication | 77.8 | B |
| Testability | 100.0 | A |
| Maintainability | 100.0 | A |

## Codebase Stats

- **Total lines:** 80,853
- **Total functions:** 2,389
- **Files scanned:** 269

## Complexity Hotspots

| Function | File | CC | Lines | Params |
|----------|------|----|-------|--------|
| `_compute_cognitive_complexity` | `src/local_deepwiki/generators/analysis/hotspots.py:126` | 16 | 55 | 1 |
| `_walk` | `src/local_deepwiki/generators/analysis/hotspots.py:136` | 16 | 42 | 2 |
| `_validate_wiki_settings` | `src/local_deepwiki/cli/config_validator.py:244` | 15 | 62 | 0 |
| `_get_python_docstring` | `src/local_deepwiki/core/parser/docstrings.py:67` | 15 | 20 | 2 |
| `analyze_file_coverage` | `src/local_deepwiki/generators/analysis/coverage.py:106` | 15 | 43 | 2 |

## High-Severity Design Smells

- **_compute_cognitive_complexity** in `src/local_deepwiki/generators/analysis/hotspots.py:126` (long_method) -- Function has 55 lines and cyclomatic complexity 16 (thresholds: 80 lines, CC 15)
- **_walk** in `src/local_deepwiki/generators/analysis/hotspots.py:136` (long_method) -- Function has 42 lines and cyclomatic complexity 16 (thresholds: 80 lines, CC 15)

## Layer Architecture

No layer violations detected.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:98-100`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](files/src/local_deepwiki/error_factories.md)
- [`src/local_deepwiki/errors.py:53-118`](files/src/local_deepwiki/errors.md)
- [`src/local_deepwiki/watcher.py:40-46`](files/src/local_deepwiki/watcher.md)


*Showing 10 of 269 source files.*
