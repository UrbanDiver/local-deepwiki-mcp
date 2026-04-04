# Architecture Health

**Overall Grade: B (84/100)**

## Scores by Dimension

| Dimension | Score | Grade |
|-----------|-------|-------|
| Complexity | 100.0 | A |
| Coupling | 79.1 | B |
| Smells | 96.1 | A |
| Layers | 100.0 | A |
| Churn | 100.0 | A |
| Cohesion | 46.0 | D |
| Duplication | 55.0 | D |
| Testability | 75.6 | B |
| Maintainability | 100.0 | A |

## Codebase Stats

- **Total lines:** 80,497
- **Total functions:** 2,377
- **Files scanned:** 268

## Complexity Hotspots

| Function | File | CC | Lines | Params |
|----------|------|----|-------|--------|
| `_validate_wiki_settings` | `src/local_deepwiki/cli/config_validator.py:244` | 15 | 62 | 0 |
| `_get_python_docstring` | `src/local_deepwiki/core/parser/docstrings.py:67` | 15 | 20 | 2 |
| `analyze_file_coverage` | `src/local_deepwiki/generators/analysis/coverage.py:106` | 15 | 43 | 2 |
| `suggest_topics` | `src/local_deepwiki/generators/codemap/generator.py:549` | 15 | 64 | 3 |
| `_collect_relevant_lines` | `src/local_deepwiki/generators/examples/orchestrator.py:100` | 15 | 46 | 3 |

## Layer Architecture

No layer violations detected.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/server.py:98-100`](files/src/local_deepwiki/server.md)
- `src/local_deepwiki/models/__init__.py`
- [`src/local_deepwiki/tool_defs/analysis.py`](files/src/local_deepwiki/tool_defs/analysis.md)
- [`src/local_deepwiki/generators/analysis/duplication.py:26-37`](files/src/local_deepwiki/generators/analysis/duplication.md)
- [`src/local_deepwiki/generators/analysis/architecture_health.py:55-123`](files/src/local_deepwiki/generators/analysis/architecture_health.md)
- [`src/local_deepwiki/generators/analysis/maintainability.py:69-79`](files/src/local_deepwiki/generators/analysis/maintainability.md)
- [`src/local_deepwiki/models/tool_args.py:15-49`](files/src/local_deepwiki/models/tool_args.md)
- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:34-39`](files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/generators/analysis/churn.py:25-38`](files/src/local_deepwiki/generators/analysis/churn.md)


*Showing 10 of 268 source files.*
