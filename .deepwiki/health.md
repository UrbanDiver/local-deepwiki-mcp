# Architecture Health

**Overall Grade: B (89/100)**

## Scores by Dimension

| Dimension | Score | Grade |
|-----------|-------|-------|
| Complexity | 89.6 | B |
| Coupling | 79.1 | B |
| Smells | 95.1 | A |
| Layers | 100.0 | A |
| Churn | 100.0 | A |
| Cohesion | 66.7 | C |
| Duplication | 77.8 | B |
| Testability | 100.0 | A |
| Maintainability | 100.0 | A |

## Codebase Stats

- **Total lines:** 80,835
- **Total functions:** 2,386
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

- [`src/local_deepwiki/plugins/registry.py:25-361`](files/src/local_deepwiki/plugins/registry.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:34-39`](files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/generators/analysis/duplication.py:26-37`](files/src/local_deepwiki/generators/analysis/duplication.md)
- [`src/local_deepwiki/generators/analysis/testability.py:26-37`](files/src/local_deepwiki/generators/analysis/testability.md)
- [`src/local_deepwiki/export/toc_renderer.py:8-17`](files/src/local_deepwiki/export/toc_renderer.md)
- [`src/local_deepwiki/export/pdf.py:129-534`](files/src/local_deepwiki/export/pdf.md)
- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/generators/analysis/hotspots.py:69-89`](files/src/local_deepwiki/generators/analysis/hotspots.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:98-100`](files/src/local_deepwiki/server.md)


*Showing 10 of 269 source files.*
