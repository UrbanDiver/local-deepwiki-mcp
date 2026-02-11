# Technical Debt Remediation Plan

**Created:** 2026-02-10
**Revised:** 2026-02-10 (rev 2)
**Target Completion:** 6 weeks
**Estimated Effort:** 50-65 hours

---

## Executive Summary

This plan addresses technical debt identified in the codebase audit. Work is organized into 3 phases, prioritized by risk and impact. Each phase can be executed independently, with earlier phases unlocking benefits for later ones.

**Changes from original plan:**
- Removed DI container (over-engineered for this codebase; Python module singletons are idiomatic)
- Removed vector store abstraction (YAGNI; no second backend exists or is planned)
- Moved exception audit earlier (silent swallowing masks async bugs, so fix together)
- Added mypy baseline task (CI will fail immediately without it)
- Added LLM mocking strategy for integration tests
- Compressed from 4 phases / 8 weeks to 3 phases / 6 weeks

---

## Phase 1: Critical Infrastructure (Weeks 1-2)

**Goal:** Establish automated quality gates, fix security defaults, stop hiding bugs.

### 1.1 CI/CD Pipeline (Priority: P0) -- DONE

**Problem:** No automated testing, linting, or security scanning.

**Actions (completed):**
1. Created `.github/workflows/ci.yml` with test matrix (Python 3.11, 3.12), lint (black, isort, mypy), and security (pip-audit)
2. Mypy step made blocking (no `continue-on-error`)
3. Committed and pushed (`7c54a3b`)

**Effort:** 3 hours (actual)
**Owner:** DevOps/Maintainer

---

### 1.2 Mypy Baseline (Priority: P0) -- DONE

**Problem:** `mypy src/` had 102 errors; CI lint job would fail on day one.

**Actions (completed):**
1. Fixed real type bugs: `ToolHandler` callable type, `DeepResearchResult` import, Path/str mismatch in export handlers, variable reuse in plugin cleanup
2. Added `from __future__ import annotations` + `TYPE_CHECKING` imports for forward references
3. Configured per-module mypy overrides for mixin `attr-defined`, Rich stubs, dynamic generator code
4. Global `disable_error_code` for `no-any-return`, `prop-decorator`, `no-redef`
5. Result: 0 errors across 128 source files

**Effort:** 3 hours (actual)
**Owner:** Backend

---

### 1.3 Security Posture Logging (Priority: P1) -- DONE

**Problem (revised):** The original audit found "access control disabled by default," but this was inaccurate. The actual security model uses `RBACMode.PERMISSIVE` as default (not disabled), and audit logging has no off switch. PERMISSIVE is correct for a local MCP server — unauthenticated requests are allowed, but authenticated subjects get full RBAC enforcement. The real gap was no visibility into which mode is active at startup.

**Actions:**
1. ~~Change default config~~ — Not needed. PERMISSIVE is the correct default for local use.
2. **Add startup log** in `server.py:main()` that reports the active RBAC mode:
   - `DISABLED` -> `logger.warning()`
   - `PERMISSIVE` -> `logger.info()`
   - `ENFORCED` -> `logger.info()`

**Status:** Complete. See `_log_security_posture()` in `server.py`.

**Effort:** 0.5 hours (actual)
**Owner:** Security/Backend

---

### 1.4 Fix Suppressed Test Warnings (Priority: P1) -- DONE

**Problem:** `filterwarnings` hides async bugs.

**Actions (completed):**
1. Removed `filterwarnings` suppression from `pyproject.toml`
2. Fixed `test_main_keyboard_interrupt` — coroutine leak (close coro before raising)
3. Fixed `test_tool_schemas_have_required_fields` — replaced deprecated `get_event_loop().run_until_complete()` with `async def` + `await`

**Status:** Complete. All tests pass with zero filterwarnings suppression.

**Effort:** 1.5 hours (actual)
**Owner:** Backend

---

## Phase 2: Bug Fixes & Code Cleanup (Weeks 3-4)

**Goal:** Fix silent failures, reduce large files, establish exception handling discipline.

### 2.1 Exception Handling Audit (Priority: P1) -- DONE

**Problem (revised):** The original audit counted 299 using `grep "except.*:$"` which matched *all* typed except clauses. Actual count: **67 `except Exception`** clauses, **0 bare `except:`** clauses.

**Actions (completed):**
1. Audited all 67 `except Exception` clauses across `src/`
2. Categorized each:
   - **Kept (justified):** 14 — callback/plugin isolation (`events.py` x8, `plugins/registry.py` x6) with documentation comments
   - **Narrowed:** 22 — replaced with specific types (`OSError`, `ValueError`, `RuntimeError`, `ConnectionError`, `TimeoutError`, provider-specific exceptions)
   - **Kept (user-facing):** 31 — web routes, CLI, exports where broad catches are appropriate
3. Updated 6 test files to raise specific exception types matching the narrowed handlers
4. Zero bare `except:` clauses exist

**Results:** 67 → 45 `except Exception` clauses. All tests pass.

**Effort:** 3 hours (actual)
**Owner:** Backend

---

### 2.2 Split Large Files (Priority: P2) -- DONE (original targets)

**Problem:** 4 files over 1,000 lines each.

**Actions (completed):**

#### 2.2.1 Split `server.py` (1,013 lines) -- DONE
- Extracted tool definitions to `server_tool_defs.py` (876 lines)
- `server.py` reduced to 167 lines (init + dispatch only)

#### 2.2.2 Split `handlers/analysis.py` (1,520 lines) -- DONE
- `analysis.py` → 43 lines (re-exports)
- `analysis_diff.py` (430), `analysis_entity.py` (531), `analysis_metadata.py` (369), `analysis_search.py` (248)

#### 2.2.3 Split `models.py` (1,017 lines) -- DONE
- Converted to `models/` package with 6 submodules: `chunks.py`, `foundation.py`, `provider_types.py`, `research.py`, `tool_args.py`, `wiki.py`
- `__init__.py` re-exports for backward compatibility

**Note:** `codemap.py` (1,018 lines) stays as-is — single responsibility.

**Status:** Complete. All original targets split. However, a full scan reveals **8 additional files >1,000 lines** that were not in the original audit (see 2.2.4).

#### 2.2.4 Remaining Large Files (NEW - Priority: P3)

Files >1,000 lines discovered after completing the original splits:

| File | Lines | Assessment |
|------|-------|------------|
| `core/vectorstore/store.py` | 1,844 | Largest file; candidate for split (CRUD, search, maintenance) |
| `generators/diagrams.py` | 1,262 | 5 diagram types; could extract per-type generators |
| `export/pdf.py` | 1,184 | Complex but single responsibility; low priority |
| `export/html.py` | 1,111 | Complex but single responsibility; low priority |
| `generators/test_examples.py` | 1,095 | Single responsibility; leave as-is |
| `events.py` | 1,089 | Evaluated in 3.4 (simplification candidate) |
| `config/models.py` | 1,079 | Pydantic models; splitting adds import complexity |
| `cli/config_cli.py` | 1,008 | CLI commands; could group by subcommand |

**Recommendation:** Split `vectorstore/store.py` (highest value). Others are lower priority — single-responsibility files that happen to be long.

**Effort:** Original: 6-8 hours (actual). Remaining (2.2.4): 4-6 hours if pursued.
**Owner:** Backend

---

## Phase 3: Testing & Long-term Quality (Weeks 5-6)

**Goal:** Validate resource limits, add integration tests, clean up async boundaries.

### 3.1 Enable Skipped Resource Limit Tests (Priority: P1) -- DONE

**Problem:** 3 tests in `test_resource_limits.py` unconditionally skipped because they claimed to need real 1GB/50k-file/50MB resources.

**Actions (completed):**
1. Replaced `pytest.skip()` bodies with mock-based tests in the existing test file:
   - `test_repo_too_large_raises` — 25 files with mocked `Path.stat` returning 45MB each (1.125GB > 1GB limit)
   - `test_too_many_files_raises` — mocked `os.walk` yielding 50,001 filenames
   - `test_file_too_large_raises` — mocked `Path.stat` returning `MAX_FILE_SIZE + 1`
2. Removed unused `os` and `tempfile` imports

**Results:** Skipped tests reduced from 32 to 29. Remaining 29 are all WeasyPrint/PDF-dependent (legitimate environment skips).

**Effort:** 0.5 hours (actual)
**Owner:** Backend

---

### 3.2 Add Integration Test Suite (Priority: P2) -- DONE

**Problem:** No end-to-end tests for full pipelines.

**Actions (completed):**
1. `tests/test_integration_pipeline.py` (25 tests) — index → wiki → HTML export → ask_question → search_code flows with real LanceDB VectorStore and content-aware hash-based embeddings.
2. `tests/test_integration_analysis.py` (10 tests) — analysis handler pipelines:
   - `TestSearchWikiIntegration` (2): entity search by name, page search by title
   - `TestFuzzySearchIntegration` (2): typo correction, file suggestions
   - `TestExplainEntityIntegration` (2): class explanation with call graph + API docs, function explanation with parameters
   - `TestImpactAnalysisIntegration` (1): reverse call graph + risk level
   - `TestFileContextIntegration` (1): imports and related files
   - `TestComplexityMetricsIntegration` (1): cyclomatic complexity via tree-sitter AST
   - `TestDeepResearchIntegration` (1): multi-step reasoning with mock LLM

All tests use mock LLM providers — no API keys needed for CI.

**Effort:** 4 hours (actual)
**Owner:** QA/Backend

---

### 3.3 Async/Sync Boundary Cleanup (Priority: P2) -- DONE

**Problem:** Mixed sync/async patterns cause confusion and potential blocking.

**Actions (completed):**
1. Wrapped 21 blocking I/O calls in `await asyncio.to_thread()` across 6 files:
   - `handlers/analysis_diff.py` (2): `toc_path.read_text()`, `search_path.read_text()`
   - `handlers/analysis_entity.py` (2): `search_json_path.read_text()`, `toc_path.read_text()`
   - `handlers/analysis_search.py` (1): `search_index_path.read_text()`
   - `handlers/analysis_metadata.py` (5): 4x `path.read_text()`, 1x `wiki_path.glob()`
   - `core/indexer.py` (4): `scan_repository_for_secrets()`, `wiki_path.mkdir()`, `_load_previous_status()`, `_save_index_status()`
   - `export/pdf.py` (7): `load_toc()`, 3x `mkdir()`, 2x `_render_batch_to_pdf()`, `shutil.copy()`, `_export_single_page()`
2. No new abstractions needed — pure call-site wrapping following existing `handlers/core.py` convention.
3. All 4845 tests pass, mypy 0 errors.

**Effort:** 2 hours (actual)
**Owner:** Backend

---

### 3.4 Simplify Over-Engineered Systems (Priority: P3)

**Problem:** Events and progress systems are complex but potentially underutilized.

**Actions:**
1. **Audit usage first** — count actual call sites for `HandlerStats`, `HandlerLifecycle`, priority ordering

2. **If <5 usages of advanced features:**
   - Remove `HandlerStats`, `HandlerLifecycle`, priority ordering
   - Simplify to basic pub-sub pattern (~200 lines instead of 1,082)

3. **If >=5 usages:** leave as-is, this is proportionate complexity

**Effort:** 4-6 hours
**Owner:** Architecture

---

## Removed Items (with rationale)

### ~~Dependency Injection Container~~ — Removed

**Original estimate:** 8-12 hours (P1)

**Why removed:** Python module-level singletons with `get_*()` functions are idiomatic. The proposed `AppContainer` replaces one pattern with an equivalent one that adds indirection without fixing real bugs. For test isolation, `unittest.mock.patch` already works. If test teardown becomes a recurring pain point, a simple `reset_all_singletons()` test helper achieves the same goal in ~20 lines instead of a full container migration.

### ~~Abstract Vector Store~~ — Removed

**Original estimate:** 6-8 hours (P2)

**Why removed:** YAGNI. There is no second vector store backend, and none is planned. The abstraction adds a layer of indirection that makes debugging harder. When a second backend is actually needed, extract the interface at that point — it's straightforward refactoring with the existing clean API boundary in `core/vectorstore.py`.

**Hours saved:** ~16-20 hours redirected to higher-value work (exception audit moved earlier, mypy baseline, integration test mocking strategy).

---

## Implementation Schedule

| Week | Items | Status | Hours |
|------|-------|--------|-------|
| 1 | 1.1, 1.2, 1.3 | ALL DONE | 6-11 |
| 2 | 1.4 | DONE | 4-6 |
| 3 | 2.1 | DONE | 6-8 |
| 4 | 2.2 | DONE (original targets) | 6-8 |
| 5 | 3.1, 3.2 | 3.1 DONE, 3.2 pending | 12-16 |
| 6 | 3.3, 3.4 | Pending | 10-14 |

**Original total:** 44-63 hours
**Completed:** ~18 hours (1.1 + 1.2 + 1.3 + 1.4 + 2.1 + 2.2 + 3.1)
**Remaining:** ~19-27 hours (2.2.4 optional + 3.2 + 3.3 + 3.4)

---

## Success Metrics

| Metric | Before | Current | Target |
|--------|--------|---------|--------|
| CI pipeline | None | ✅ Full test/lint/security | Full test/lint/security |
| Mypy | 102 errors | ✅ 0 errors (128 files) | Passing in CI |
| `except Exception` handlers | 67 | ✅ 45 (14 justified) | <50 |
| Suppressed warnings | `filterwarnings` active | ✅ Removed | Removed |
| Security posture logging | None | ✅ Startup log | Startup log |
| Files >1000 lines (original 4) | 4 | ✅ 1 (codemap.py, intentional) | 1 |
| Files >1000 lines (all) | 9 | 9 (see 2.2.4) | Assess per-file |
| Tests passing | 4,834 | 4,855 | Stable |
| Skipped tests | 32 | ✅ 29 (all WeasyPrint) | 29 (env-dependent, legitimate) |
| Integration tests | 0 | ✅ 35 (25 pipeline + 10 analysis) | 5+ |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| CI blocks all PRs on day one | Mypy baseline (1.2) ensures lint job passes immediately |
| Exception audit introduces regressions | Run full test suite after each file; commit per-module |
| Time overruns | Each phase is independent; can pause between phases |
| Regression in splitting files | Comprehensive import tests before/after; re-exports in `__init__.py` |
| Integration tests flaky without real LLM | Mock-first strategy (3.2); real LLM tests opt-in via env var |

---

## Appendix: File Inventory

### Original Splits (DONE)
```
server.py          1,013 -> server.py (167) + server_tool_defs.py (876)
handlers/analysis  1,520 -> analysis.py (43) + 4 submodules (248-531 each)
models.py          1,017 -> models/ package with 6 submodules (36-494 each)
codemap.py         1,018 -> kept as-is (single responsibility)
```

### Remaining Files >1,000 Lines
```
core/vectorstore/store.py     1,844  ← highest-value split candidate
generators/diagrams.py        1,262
export/pdf.py                 1,184
export/html.py                1,111
generators/test_examples.py   1,095
events.py                     1,089  ← evaluated in 3.4
config/models.py              1,079
generators/codemap.py         1,018  ← intentionally kept
cli/config_cli.py             1,008
```
