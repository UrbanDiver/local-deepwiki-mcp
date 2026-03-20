# God Class Method Count Reduction — Smells F to D+

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce god class count from 6 to ≤2 by moving methods off the classes. This drops the god_class penalty from 25 to ≤10, pushing smells from F (15) to D+ (30+) and overall from D (55) to C (62+).

**Architecture:** Remove delegation stubs that only exist for backward compatibility, move rendering/storage helpers to standalone modules. No behavioral changes — callers continue to work through the same entry points.

**Tech Stack:** Python, pytest

**Score math:**
- Current smells: 100 - 60 (density cap) - 25 (god class cap) = 15
- With ≤2 god classes: 100 - 60 - 10 = 30
- With ≤2 god classes + slightly reduced density: 100 - 55 - 10 = 35
- Overall with smells=35: 67.2×0.30 + 44.2×0.25 + 35×0.25 + 100×0.20 = 20.2 + 11.1 + 8.75 + 20 = **60.0 (C)**

---

## Task 1: SearchEngine — Remove delegation stubs (33 → ~14 methods)

The previous round extracted pipeline functions to `search_pipeline.py` and postprocessing to `search_postprocess.py`. But SearchEngine still has 33 methods because it kept delegation stubs like `run_vector_pipeline(self, ...)` that just call the extracted module functions.

**Files:**
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py`
- Modify: `src/local_deepwiki/core/vectorstore/search_pipeline.py`
- Modify: `src/local_deepwiki/core/vectorstore/search_postprocess.py`

**Strategy:** In `search_from_request` and `search_paginated`, call the pipeline/postprocess module functions directly instead of through `self.*` delegation methods. Then delete the delegation methods from SearchEngine.

- [ ] Read `search_engine.py` and identify all methods that are pure delegation (they call a function from `search_pipeline` or `search_postprocess` and do nothing else). These are the ones to remove.

- [ ] In `search_from_request`, replace calls like `self.run_vector_pipeline(...)` with `search_pipeline.run_vector_pipeline(...)`. Do the same for `dispatch_search`, `apply_fuzzy_reranking`, `apply_post_filters`, `attach_suggestions`, `record_and_cache`.

- [ ] In `search_paginated`, do the same replacements.

- [ ] Delete the delegation methods from SearchEngine. Keep only: `__init__`, properties, `search_from_request`, `search`, `search_paginated`, `resolve_search_profile`, `build_search_filters`, `compute_fetch_limit`, `convert_results_to_search_results`, `auto_search_limit`, `resolve_search_mode`, `build_cache_filters`, `record_feedback`, `adaptive_search_stats`, `get_fuzzy_helper`.

- [ ] Run: `uv run pytest tests/test_vectorstore*.py tests/test_search*.py -x -q`
- [ ] Commit: `refactor: remove SearchEngine delegation stubs (33 → ~14 methods)`

---

## Task 2: LazyPageGenerator — Remove cache delegation stubs (27 → ~14 methods)

The previous round extracted cache operations to `lazy_cache.py`. But LazyPageGenerator still delegates through `self._read_cached`, `self._write_page`, etc.

**Files:**
- Modify: `src/local_deepwiki/generators/lazy_generator.py`
- Modify: `src/local_deepwiki/generators/lazy_cache.py`

**Strategy:** In the methods that call cache operations, call `lazy_cache.*` directly. Delete the thin delegation methods.

- [ ] Read `lazy_generator.py` and identify all methods that just delegate to `lazy_cache`.

- [ ] Replace `self._read_cached(...)` with `lazy_cache.read_cached_page(...)` (or whatever the function name is) in all callers within the class.

- [ ] Delete the delegation methods. Keep only the public API and generation logic.

- [ ] Run: `uv run pytest tests/test_lazy_generator*.py -x -q`
- [ ] Commit: `refactor: remove LazyPageGenerator cache delegation stubs (27 → ~14 methods)`

---

## Task 3: VectorStore — Remove SearchMixin forwarding (23 → ~12 methods)

VectorStore inherits SearchMixin which exposes ~15 methods that just forward to `self._search_engine.*`. The mixin exists for backward compatibility.

**Files:**
- Modify: `src/local_deepwiki/core/vectorstore/store.py`
- Modify: `src/local_deepwiki/core/vectorstore/mixins/search.py`

**Strategy:** Instead of inheriting SearchMixin, expose `search_engine` as a public property on VectorStore. Callers that currently do `store.search(...)` can do `store.search_engine.search(...)`. Keep a thin `search()` convenience method on VectorStore itself for the most common call, but remove all the other forwarded methods.

**IMPORTANT:** This is the riskiest task — many callers use `store.search()`. Read the SearchMixin class carefully. Keep `search()` and `search_paginated()` as the two convenience methods on VectorStore (they delegate to search_engine). Remove everything else the mixin provides.

- [ ] Read `mixins/search.py` to understand what methods it adds.

- [ ] On VectorStore, add a `search_engine` property that returns `self._search_engine`.

- [ ] Keep `search()` and `search_paginated()` as thin methods on VectorStore that delegate to `self._search_engine`.

- [ ] Remove the SearchMixin inheritance from VectorStore's class definition. Copy the two kept methods directly onto VectorStore.

- [ ] Remove or simplify `mixins/search.py` — it may still be needed if other classes inherit it, so check first. If only VectorStore uses it, it can be deleted.

- [ ] Run: `uv run pytest tests/test_vectorstore*.py tests/test_search*.py -x -q`
- [ ] Run: `uv run pytest tests/ -x -q` (broad check since callers may be affected)
- [ ] Commit: `refactor: remove SearchMixin from VectorStore (23 → ~12 methods)`

---

## Task 4: DependencyGraphGenerator — Extract renderer (19 → ~10 methods)

This became a god class in the previous round when we added helper methods. The rendering functions should be standalone.

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/dependency_graph.py`

**Strategy:** The `_build_module_nodes`, `_build_module_edges`, `_collect_file_deps`, `_render_file_mermaid`, `_resolve_import_target` methods extracted in the previous round are instance methods but don't use `self`. Convert them to module-level functions. Also check the original rendering methods — `_render_module_graph` and `generate_file_graph` — if they only use `self` to call other methods that are now module-level, they can become module-level too.

- [ ] Read `dependency_graph.py` and identify methods that don't use `self` (or only use `self` to call other methods).

- [ ] Convert those methods to module-level functions. Update call sites within the class to call the module-level functions instead of `self.*`.

- [ ] Target: DependencyGraphGenerator should have ≤15 methods.

- [ ] Run: `uv run pytest tests/test_dependency_graph_*.py -x -q`
- [ ] Commit: `refactor: extract DependencyGraphGenerator renderers to module level (19 → ~10 methods)`

---

## Task 5: EmbeddingCache — Extract storage layer (23 → ~12 methods)

**Files:**
- Modify: `src/local_deepwiki/providers/embeddings/cache.py`

**Strategy:** EmbeddingCache mixes business logic (TTL checking, batch operations) with SQLite storage (table creation, queries, row parsing). Extract the SQLite operations into a `_CacheStorage` class or module-level functions.

- [ ] Read `cache.py` and identify the SQLite-specific methods (table creation, raw queries, connection management).

- [ ] Extract them into a `_CacheStorage` helper class in the same file (or a `cache_storage.py` if it's large enough). The helper handles: create table, insert row, query rows, delete rows, count rows, vacuum.

- [ ] EmbeddingCache keeps: the public API (`get`, `set`, `get_batch`, `set_batch`, `clear`, `stats`, `close`, `cleanup`) and TTL/eviction logic. It delegates storage to `_CacheStorage`.

- [ ] Target: EmbeddingCache ≤15 methods, _CacheStorage ≤10 methods.

- [ ] Run: `uv run pytest tests/test_embedding_cache*.py -x -q`
- [ ] Commit: `refactor: extract EmbeddingCache storage layer (23 → ~12 methods)`

---

## Task 6: Verification

- [ ] Run full test suite: `uv run pytest tests/ -q`

- [ ] Run health check:
```bash
uv run python -c "
import asyncio, json
from unittest.mock import patch
from local_deepwiki.handlers.analysis_architecture import handle_get_architecture_health, handle_compare_architecture
async def main():
    with patch('local_deepwiki.handlers.analysis_architecture.get_access_controller'):
        r = await handle_get_architecture_health({'repo_path': '.'})
        data = json.loads(r[0].text)
        o = data['overall']
        print(f'Health: {o[\"grade\"]} ({o[\"score\"]})')
        for dim, info in o['dimensions'].items():
            print(f'  {dim}: {info[\"grade\"]} ({info[\"score\"]})')
        print(f'God classes: {len(data[\"top_findings\"][\"god_classes\"])}')
        for gc in data['top_findings']['god_classes']:
            print(f'  {gc[\"entity\"]}: {gc[\"description\"]}')
asyncio.run(main())
"
```

- [ ] Expected: ≤2 god classes, smells ≥30, overall ≥60 (C grade)
- [ ] Commit: `chore: verify health grade improvement to C`

---

## Execution Notes

**Parallelization:** Tasks 1-5 touch non-overlapping files:
- Task 1: `search_engine.py`, `search_pipeline.py`, `search_postprocess.py`
- Task 2: `lazy_generator.py`, `lazy_cache.py`
- Task 3: `store.py`, `mixins/search.py`
- Task 4: `dependency_graph.py`
- Task 5: `providers/embeddings/cache.py`

All 5 can run in parallel. Task 6 runs after all complete.

**Risk:** Task 3 (VectorStore/SearchMixin) has the broadest impact since many files call `store.search()`. The kept convenience method ensures backward compat, but grep for other SearchMixin methods that callers might use.

**What we're NOT touching:** RepositoryIndexer stays at 25 methods — further splitting requires deeper architectural changes (extracting a full IndexingPipeline class) that risks destabilizing the core indexing flow. It stays as 1 of the ≤2 remaining god classes.
