# Changelog

Recent changes to this repository.

## Recent Commits

### April 04, 2026

- [`7bbb5c7`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/7bbb5c7) docs: add cognitive complexity to get_hotspots description
  - Files: `README.md`

- [`db19fc2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/db19fc2) feat: add cognitive complexity metric to hotspot analysis (SonarSource spec)
  - Files: `src/local_deepwiki/generators/analysis/hotspots.py`, `tests/test_hotspots.py`

- [`0951abc`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0951abc) test: add tests for [GeneratorService](files/src/local_deepwiki/services/generator_service.md) (36% -> broad coverage)
  - Files: `tests/test_generator_service.py`

- [`3f49bc2`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/3f49bc2) test: add tests for agentic workflow runner functions (47% -> ~90% coverage)
  - Files: `tests/test_agentic_workflows.py`

- [`f74d89a`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/f74d89a) test: add tests for MCP prompt handlers (36% -> full coverage)
  - Files: `tests/test_handlers_prompts.py`

- [`2850769`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/2850769) test: add tests for web [rate_limit](files/src/local_deepwiki/web/rate_limit.md) Flask [decorator](files/src/local_deepwiki/providers/retry.md) (0% -> 100% coverage)
  - Files: `tests/test_rate_limit.py`

- [`43e9518`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/43e9518) fix: use per-file coverage percentages with 50% threshold instead of binary t...
  - Files: `src/local_deepwiki/generators/analysis/testability.py`, `tests/test_testability.py`

- [`0994907`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/0994907) feat: coverage-aware testability metric — read .coverage DB instead of filena...
  - Files: `src/local_deepwiki/generators/analysis/testability.py`, `tests/test_testability.py`

- [`e72b31b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e72b31b) docs: coverage-aware testability metric design spec
  - Files: `docs/superpowers/specs/2026-04-04-coverage-aware-testability-design.md`

- [`57587c1`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/57587c1) fix: resolve 1 broken wiki link and 29 skipped PDF tests (Homebrew lib path)
  - Files: `.deepwiki/onboarding.md`, `tests/conftest.py`

- [`8a348c8`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/8a348c8) fix: tune scoring penalties for clone groups and module cohesion to reduce fa...
  - Files: `src/local_deepwiki/generators/analysis/duplication.py`, `src/local_deepwiki/generators/analysis/health_scoring.py`, `tests/test_health_scoring.py`

- [`75687d9`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/75687d9) feat: health scorer consumes pattern-aware cohesion and inter-file duplicatio...
  - Files: `src/local_deepwiki/generators/analysis/health_scoring.py`, `tests/test_health_scoring.py`

- [`eb1bd6e`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/eb1bd6e) feat: separate intra-file from inter-file duplication in clone detection
  - Files: `src/local_deepwiki/generators/analysis/duplication.py`, `tests/test_duplication.py`

- [`e03bc9c`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/e03bc9c) refactor: extract TOC renderer from [StreamingPdfExporter](files/src/local_deepwiki/export/pdf.md)
  - Files: `src/local_deepwiki/export/pdf.py`, `src/local_deepwiki/export/toc_renderer.py`, `tests/test_pdf_streaming.py`, `tests/test_toc_renderer.py`

- [`2bc1322`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/2bc1322) refactor: extract generic register/unregister helpers in plugin registry
  - Files: `src/local_deepwiki/plugins/registry.py`

- [`4fb073b`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/4fb073b) feat: pattern-aware cohesion scoring — exclude ABCs, Protocols, Mixins from L...
  - Files: `src/local_deepwiki/generators/analysis/cohesion.py`, `tests/test_cohesion.py`

### April 03, 2026

- [`580c1b0`](https://github.com/UrbanDiver/local-deepwiki-mcp/commit/580c1b0) chore: update pre-built wiki with all 5 metric phases
  - Files: `.deepwiki/architecture.md`, `.deepwiki/changelog.md`, `.deepwiki/coupling.md`, `.deepwiki/coverage.md`, `.deepwiki/dependencies.md` (+80 more)

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

## Statistics

- **Commits shown**: 30
- **Contributors**: 1
- **Latest commit**: 2026-04-04

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
