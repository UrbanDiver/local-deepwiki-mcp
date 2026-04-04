# Changelog

Recent changes to this repository.

## Recent Commits

### April 03, 2026

- [`72da5da`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/72da5da) docs: update README with 64 tools, architecture health section, and 9 dimensions
  - Files: `README.md`

- [`a75af5c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/a75af5c) refactor: extract helpers from long analysis methods
  - Files: `src/local_deepwiki/generators/analysis/churn.py`, `src/local_deepwiki/generators/analysis/duplication.py`, `src/local_deepwiki/generators/analysis/maintainability.py`, `src/local_deepwiki/generators/analysis/testability.py`

- [`56cb3da`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/56cb3da) feat: add maintainability index architecture health dimension (Phase 5)

- [`d50a656`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d50a656) feat: add maintainability index architecture health dimension (Phase 5)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/tool_args.py`, `tests/test_architecture_health.py` (+1 more)

- [`64e4b55`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/64e4b55) feat: add maintainability index architecture health dimension (Phase 5)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/generators/analysis/maintainability.py`, `src/local_deepwiki/handlers/__init__.py`, `src/local_deepwiki/handlers/analysis_architecture.py` (+8 more)

- [`ace2c6d`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ace2c6d) feat: add testability-based architecture health dimension (Phase 4)

- [`f47812a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/f47812a) feat: add testability-based architecture health dimension (Phase 4)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/generators/analysis/testability.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/tool_args.py` (+2 more)

- [`6d8243f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/6d8243f) feat: add testability-based architecture health dimension (Phase 4)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/generators/analysis/testability.py`, `src/local_deepwiki/handlers/__init__.py`, `src/local_deepwiki/handlers/analysis_architecture.py` (+7 more)

- [`9e4aba6`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/9e4aba6) feat: add duplication-based architecture health dimension (Phase 3)

- [`3fed1da`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3fed1da) feat: add duplication-based architecture health dimension (Phase 3)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/duplication.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/tool_args.py` (+2 more)

- [`d7e2187`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d7e2187) feat(duplication): add [score_duplication](files/src/local_deepwiki/generators/analysis/health_scoring.md), rebalance to 7 dimensions, integrat...
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/handlers/__init__.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/__init__.py` (+6 more)

- [`75290fc`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/75290fc) feat: add clone detection engine (Type 1 + Type 2 duplication)
  - Files: `src/local_deepwiki/generators/analysis/duplication.py`, `tests/test_duplication.py`

- [`3ad80b3`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3ad80b3) feat: add cohesion-based architecture health dimension (Phase 2)

- [`8a5e93f`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8a5e93f) feat: add cohesion-based architecture health dimension (Phase 2)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/cohesion.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/tool_args.py`, `tests/test_architecture_health.py` (+1 more)

- [`d2646c8`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d2646c8) feat(cohesion): integrate into health grade, add get_cohesion_metrics MCP tool
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/handlers/__init__.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/__init__.py`, `src/local_deepwiki/models/tool_args.py` (+4 more)

- [`0cd069b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0cd069b) feat(cohesion): add [score_cohesion](files/src/local_deepwiki/generators/analysis/health_scoring.md) and rebalance weights to 6 dimensions
  - Files: `src/local_deepwiki/generators/analysis/health_scoring.py`, `tests/test_health_scoring.py`

- [`0d6b194`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0d6b194) feat: add LCOM4 class cohesion and module import cohesion analysis
  - Files: `src/local_deepwiki/generators/analysis/cohesion.py`, `tests/test_cohesion.py`

- [`7a49ac9`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7a49ac9) chore: update pre-built wiki with Objective-C support
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coupling.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md` (+55 more)

- [`1d9acfb`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/1d9acfb) feat: add Objective-C language support
  - Files: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `pyproject.toml`, `src/local_deepwiki/core/parser/docstrings.py` (+3 more)

- [`ce54d91`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/ce54d91) feat: add churn-based architecture health dimension (Phase 1)

- [`c9577b2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c9577b2) feat: add churn-based architecture health dimension (Phase 1)
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/churn.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/tool_args.py` (+3 more)

- [`148a027`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/148a027) feat(churn): add MCP tools get_churn_metrics and get_co_change
  - Files: `src/local_deepwiki/handlers/__init__.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/__init__.py`, `src/local_deepwiki/models/tool_args.py`, `src/local_deepwiki/server.py` (+2 more)

- [`3336b41`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3336b41) feat(churn): add [score_churn](files/src/local_deepwiki/generators/analysis/health_scoring.md), rebalance weights, integrate into health grade
  - Files: `src/local_deepwiki/generators/analysis/architecture_health.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `tests/test_architecture_health.py`, `tests/test_health_scoring.py`

- [`deeeed1`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/deeeed1) feat(churn): add churn×complexity composite and [analyze_churn](files/src/local_deepwiki/generators/analysis/churn.md) orchestrator
  - Files: `src/local_deepwiki/generators/analysis/churn.py`, `tests/test_churn.py`

- [`da9dcc6`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/da9dcc6) feat(churn): add git log parser, file churn, and co-change coupling
  - Files: `src/local_deepwiki/generators/analysis/churn.py`, `tests/test_churn.py`

### April 01, 2026

- [`8daaf32`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8daaf32) chore: update pre-built wiki with latest regeneration
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coupling.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md` (+63 more)

- [`d437e06`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/d437e06) chore: update pre-built wiki with latest analysis fixes
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coupling.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md` (+68 more)

- [`c0fe1bd`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c0fe1bd) fix: unify module labels in coupling analysis
  - Files: `src/local_deepwiki/generators/analysis/coupling.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `src/local_deepwiki/generators/analysis/module_dependencies.py`, `tests/test_coupling_metrics.py`, `tests/test_health_scoring.py` (+1 more)

- [`56000bf`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/56000bf) fix: improve analysis accuracy for coupling, feature envy, and long_method
  - Files: `src/local_deepwiki/generators/analysis/coupling.py`, `src/local_deepwiki/generators/analysis/design_smells.py`, `src/local_deepwiki/handlers/analysis_architecture.py`, `src/local_deepwiki/models/tool_args.py`, `src/local_deepwiki/tool_defs/analysis.py` (+1 more)

### March 31, 2026

- [`c80b757`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/c80b757) build: exclude .deepwiki and tests from sdist
  - Files: `pyproject.toml`

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-04-03

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
