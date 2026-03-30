# Architecture Grade A Improvement Plan

**Date:** 2026-03-29
**Goal:** Push architecture health from B (80.6) to A (91.5+)
**Baseline:** Complexity A (100), Coupling C (70.4), Smells D (52.1), Layers A (100)

## Score Target

Formula: `0.3*complexity + 0.25*coupling + 0.25*smells + 0.2*layers`

Complexity and Layers are already at A (100). To reach 91.5 overall, smells + coupling must average ~83:

- **Smells: 52.1 -> 85+** — eliminate most of 85 long_parameter_list + 5 god_class smells
- **Coupling: 70.4 -> 82+** — increase abstractness via Protocols at package boundaries

## Current Smell Breakdown

| Type | Count | Severity |
|------|-------|----------|
| long_parameter_list | 85 | medium |
| feature_envy | 12 | medium |
| large_file | 8 | medium |
| deep_nesting | 6 | medium |
| god_class | 5 | high |

## Phase 1: Parameter Object Consolidation

**Goal:** Reduce long_parameter_list from 85 to ~35 by bundling related params into frozen dataclasses.

**Approach:** Identify clusters of functions sharing 3+ identical parameters and create a context/config dataclass for each cluster. Follow the established `ResearchConfig` / `SearchRequest` / `ImpactAnalysisRequest` pattern.

### High-Priority Targets (7+ params)

| File | Functions | Params | Proposed Object |
|------|-----------|--------|-----------------|
| `core/audit.py` | `log_access_decision`, `log_query_execution`, `log_index_operation`, `log_export_operation` | 7-9 each | `AuditEvent` dataclass with `operation`, `repo_path`, `status`, `details`, `duration`, `user`, `role` |
| `cli/update_cli.py` | `_setup_indexer`, `_run_indexing_with_progress`, `run_update` | 7-9 each | `UpdateContext` with repo_path, config, provider settings, flags |
| `cli/init_cli.py` | `run_wizard` | 8 | `WizardConfig` with provider, model, paths, flags |
| `cli/interactive_search.py` | `run_search` | 9 | `SearchSessionConfig` with repo_path, wiki_path, provider settings, display options |
| `handlers/analysis_entity.py` | `_collect_inheritance_dependents` | 7 | Re-use or extend existing handler context |
| `services/analysis_service.py` | `_collect_inheritance_dependents` | 7 | Same — also deduplicate with handlers version |

### Medium-Priority Targets (extracted helpers)

Scan all files modified in the prior Grade A round's Phase 3-4 CC decomposition (29 files, see commits on `grade-a-improvements` branch) for extracted helper functions with 7+ params. Group by module and create per-module context objects where 2+ helpers share params.

### Constraints

- All new dataclasses are `@dataclass(frozen=True)` — no mutation
- Parameter objects live in the same module as their consumers (no new files unless 3+ modules share the object)
- Existing public APIs unchanged — parameter objects are internal

## Phase 2: God Class Decomposition

**Goal:** Eliminate all 5 god_class smells by splitting each class along responsibility boundaries.

### 2a. VectorStore (22 methods, 507 lines)

**File:** `core/vectorstore/store.py`

Split into:
- `VectorStore` — table CRUD, lifecycle (open/close/context manager), schema migration
- `VectorSearch` — query dispatch, hybrid/semantic/keyword search, ranking, result formatting

**Integration:** `VectorStore` holds a `VectorSearch` instance. Existing `VectorStore` API preserved via delegation.

### 2b. SearchEngine (22 methods, 539 lines)

**File:** `core/vectorstore/search_engine.py`

Split into:
- `SearchEngine` — dispatch, result aggregation, caching
- `SearchStrategies` module — `hybrid_search()`, `semantic_search()`, `keyword_search()` as standalone functions or a strategy class

**Integration:** `SearchEngine` delegates to strategy functions. Strategy selection logic stays in `SearchEngine`.

### 2c. RepositoryIndexer (19 methods, 521 lines)

**File:** `core/indexer.py`

Split into:
- `RepositoryIndexer` — file discovery, parsing, chunking, embedding pipeline
- `WikiOrchestrator` — wiki generation coordination, progress tracking, incremental updates

**Integration:** `RepositoryIndexer.index()` calls `WikiOrchestrator` as a post-indexing step. The orchestrator receives indexed data, not raw files.

### 2d. CodeChunker (17 methods, 670 lines)

**File:** `core/chunker.py`

Split into:
- `CodeChunker` — orchestration, chunk assembly, deduplication
- Language-specific extraction already partially lives in `chunk_extractors.py` — move remaining language-specific methods from `CodeChunker` into `chunk_extractors` module functions

**Integration:** `CodeChunker` calls `chunk_extractors` functions. No new classes needed — just method extraction to module-level functions.

### 2e. DeepResearchPipeline (17 methods, 576 lines)

**File:** `core/deep_research/pipeline.py`

Split into:
- `DeepResearchPipeline` — orchestration, checkpointing, progress tracking
- `ResearchSynthesizer` — synthesis, gap analysis, citation extraction, answer formatting

**Integration:** Pipeline calls synthesizer at the synthesis stage. Synthesizer is stateless, receives accumulated research context.

### Backward Compatibility

All splits use `__init__.py` re-exports so existing imports continue to work. This is the proven pattern from prior vectorstore and deep_research splits.

## Phase 3: Protocol Interfaces

**Goal:** Increase abstractness from 0.01 to ~0.10+ across key modules, improving coupling score from 70.4 to 82+.

### New Protocols

| Protocol | Module | Consumers | Methods |
|----------|--------|-----------|---------|
| `IndexerProtocol` | `core/` | `handlers/`, `services/` | `index()`, `get_status()` |
| `VectorStoreProtocol` | `core/vectorstore/` | `handlers/`, `services/`, `web/` | `search()`, `add()`, `delete()`, `close()` |
| `WikiGeneratorProtocol` | `generators/wiki/` | `handlers/`, `services/` | `generate_wiki()`, `generate_page()` |
| `SearchServiceProtocol` | `services/` | `web/` | `search_wiki()`, `fuzzy_search()` |
| `AnalysisProtocol` | `generators/analysis/` | `handlers/`, `services/` | `analyze()`, `get_metrics()` |

### Placement

Protocols live in the module they abstract (e.g., `IndexerProtocol` in `core/__init__.py` or `core/protocols.py`). Consumers import the Protocol, not the concrete class, in type annotations.

### Constraints

- Runtime behavior unchanged — Protocols are for static typing and abstractness metrics only
- Use `typing.Protocol` with `runtime_checkable` for optional runtime validation
- Only create Protocols where there is a real consumer boundary (not speculative)

## Phase 4: Remaining Smell Cleanup

### Feature Envy (12 instances)

Assess each case:
- `cli/config_cli.py` (3 instances) — formatting functions that heavily access config branches. If the branch objects are third-party or frozen, feature envy is acceptable. Otherwise, move formatting logic closer to data.
- Remaining 9 — evaluate case by case.

### Deep Nesting (6 instances)

- `config/loader.py:_apply_nested_updates` — flatten with guard clauses
- `core/chunk_extractors.py:_get_ts_js_parents`, `_get_kotlin_parents` — flatten with early returns
- Remaining 3 — evaluate case by case

### Large File (8 instances)

Review which are source (actionable) vs test (lower priority). Source files over 800 lines should be split.

### Deduplication

`_collect_inheritance_dependents` exists in both `handlers/analysis_entity.py:538` and `services/analysis_service.py:739` with identical signatures. Consolidate into a single shared function in `services/` or a utility module.

## Sequencing and Dependencies

```
Phase 1 (parameter objects) ─── no deps, highest score impact
    │
Phase 2 (god class splits) ─── some param objects from Phase 1 may apply to split classes
    │
Phase 3 (protocols) ─── depends on Phase 2 (protocols should match the split class interfaces)
    │
Phase 4 (cleanup) ─── independent, can partially overlap with Phase 2-3
```

Each phase produces independently mergeable commits. Run `uv run deepwiki check` after each phase to measure score progression.

## Success Criteria

- Overall health grade: A (91.5+)
- Smells score: 85+ (from 52.1)
- Coupling score: 82+ (from 70.4)
- All 6,054+ tests pass
- No new layer violations
- Zero regressions in existing public APIs

## Risk Mitigation

- **Regression risk:** 95% test coverage catches breakage immediately
- **Score regression from splits:** Phase 2 splits may temporarily increase smells if new files exceed thresholds — address in Phase 4
- **Over-abstraction:** Only create Protocols where a real consumer boundary exists (3+ consumers or cross-package usage)
- **Merge conflicts:** Phases are sequential; within each phase, target non-overlapping files for parallel agent work
