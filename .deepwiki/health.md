# Architecture Health

**Overall Grade: B (86/100)**

## Scores by Dimension

| Dimension | Score | Grade |
|-----------|-------|-------|
| Complexity | 100.0 | A |
| Coupling | 46.9 | D |
| Smells | 96.2 | A |
| Layers | 100.0 | A |

## Codebase Stats

- **Total lines:** 78,369
- **Total functions:** 2,323
- **Files scanned:** 263

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

- [`src/local_deepwiki/tool_defs/analysis.py`](files/src/local_deepwiki/tool_defs/analysis.md)
- [`src/local_deepwiki/generators/analysis/coupling.py:48-90`](files/src/local_deepwiki/generators/analysis/coupling.md)
- [`src/local_deepwiki/handlers/analysis_architecture.py:43-94`](files/src/local_deepwiki/handlers/analysis_architecture.md)
- [`src/local_deepwiki/models/tool_args.py:15-49`](files/src/local_deepwiki/models/tool_args.md)
- [`src/local_deepwiki/generators/analysis/design_smells.py:162-163`](files/src/local_deepwiki/generators/analysis/design_smells.md)
- [`src/local_deepwiki/logging.py:28-83`](files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:92-94`](files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`


*Showing 10 of 263 source files.*
