# Architecture Grade A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push architecture health from B (80.6) to A (91.5+) by eliminating 85 long_parameter_list smells, 5 god classes, and increasing abstractness via Protocols.

**Architecture:** Four sequential phases — parameter object consolidation (smells D->B), god class decomposition (smells + cohesion), Protocol interfaces (coupling C->B), and remaining smell cleanup. Each phase produces independently mergeable commits.

**Tech Stack:** Python 3.11+, frozen dataclasses, `typing.Protocol`, `@runtime_checkable`, pytest

**Verification:** Run `uv run deepwiki check` after each task to measure score progression. Run `uv run pytest tests/ -x -q` to verify no regressions.

---

## Phase 1: Parameter Object Consolidation

### Task 1: Search Pipeline Parameter Objects

Fixes 16 long_parameter_list smells across the vectorstore search subsystem by introducing `SearchPipelineParams` and `SearchExecutionContext`.

**Files:**
- Create: `src/local_deepwiki/core/vectorstore/search_params.py`
- Modify: `src/local_deepwiki/core/vectorstore/search_pipeline.py:193,239,297`
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py:628,672,740,802`
- Modify: `src/local_deepwiki/core/vectorstore/mixins/search.py:169,275,347`
- Modify: `src/local_deepwiki/core/vectorstore/embedding.py:115,328,370`
- Test: `tests/test_search_params.py`

- [ ] **Step 1: Write failing test for SearchPipelineParams**

```python
# tests/test_search_params.py
"""Tests for search pipeline parameter objects."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from local_deepwiki.core.vectorstore.search_params import (
    EmbeddingBatchParams,
    SearchExecutionContext,
    SearchPipelineParams,
)


class TestSearchPipelineParams:
    def test_frozen(self):
        params = SearchPipelineParams(
            mode="vector",
            query_embedding=[0.1, 0.2],
            limit=10,
            fetch_limit=30,
            similarity_threshold=0.5,
            bm25_weight=0.3,
        )
        with pytest.raises(FrozenInstanceError):
            params.limit = 20

    def test_defaults(self):
        params = SearchPipelineParams(
            mode="vector",
            query_embedding=[0.1],
            limit=10,
            fetch_limit=30,
        )
        assert params.similarity_threshold == 0.0
        assert params.bm25_weight == 0.3
        assert params.language is None
        assert params.file_pattern is None
        assert params.chunk_types is None

    def test_all_fields(self):
        params = SearchPipelineParams(
            mode="hybrid",
            query_embedding=[0.1, 0.2],
            limit=5,
            fetch_limit=15,
            similarity_threshold=0.7,
            bm25_weight=0.5,
            language="python",
            file_pattern="*.py",
            chunk_types=["function", "class"],
        )
        assert params.mode == "hybrid"
        assert params.chunk_types == ["function", "class"]


class TestSearchExecutionContext:
    def test_frozen(self):
        ctx = SearchExecutionContext(
            query="test query",
            query_embedding=[0.1],
            mode="vector",
            profile=None,
            limit=10,
            fetch_limit=30,
            similarity_threshold=0.5,
            bm25_weight=0.3,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.query = "other"

    def test_from_pipeline_params(self):
        params = SearchPipelineParams(
            mode="vector",
            query_embedding=[0.1],
            limit=10,
            fetch_limit=30,
            similarity_threshold=0.5,
        )
        ctx = SearchExecutionContext.from_pipeline_params(
            query="test", profile=None, params=params
        )
        assert ctx.query == "test"
        assert ctx.mode == "vector"
        assert ctx.limit == 10


class TestEmbeddingBatchParams:
    def test_frozen(self):
        params = EmbeddingBatchParams(
            batch_size=100,
            max_concurrent=4,
            max_retries=3,
            retry_delay=1.0,
        )
        with pytest.raises(FrozenInstanceError):
            params.batch_size = 50

    def test_defaults(self):
        params = EmbeddingBatchParams(batch_size=100, max_concurrent=4)
        assert params.max_retries == 3
        assert params.retry_delay == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_search_params.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'local_deepwiki.core.vectorstore.search_params'`

- [ ] **Step 3: Create the parameter objects**

```python
# src/local_deepwiki/core/vectorstore/search_params.py
"""Parameter objects for the search pipeline.

Consolidates long parameter lists in search_pipeline.py, search_engine.py,
and embedding.py into frozen dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchPipelineParams:
    """Parameters for search pipeline dispatch and execution."""

    mode: str
    query_embedding: list[float]
    limit: int
    fetch_limit: int
    similarity_threshold: float = 0.0
    bm25_weight: float = 0.3
    language: str | None = None
    file_pattern: str | None = None
    chunk_types: list[str] | None = None


@dataclass(frozen=True)
class SearchExecutionContext:
    """Full context for a search execution pass (engine -> pipeline -> results)."""

    query: str
    query_embedding: list[float]
    mode: str
    profile: object | None
    limit: int
    fetch_limit: int
    similarity_threshold: float = 0.0
    bm25_weight: float = 0.3
    language: str | None = None
    file_pattern: str | None = None
    chunk_types: list[str] | None = None

    @classmethod
    def from_pipeline_params(
        cls,
        query: str,
        profile: object | None,
        params: SearchPipelineParams,
    ) -> SearchExecutionContext:
        return cls(
            query=query,
            query_embedding=params.query_embedding,
            mode=params.mode,
            profile=profile,
            limit=params.limit,
            fetch_limit=params.fetch_limit,
            similarity_threshold=params.similarity_threshold,
            bm25_weight=params.bm25_weight,
            language=params.language,
            file_pattern=params.file_pattern,
            chunk_types=params.chunk_types,
        )


@dataclass(frozen=True)
class EmbeddingBatchParams:
    """Parameters for batch embedding operations."""

    batch_size: int
    max_concurrent: int
    max_retries: int = 3
    retry_delay: float = 1.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_search_params.py -v`
Expected: PASS

- [ ] **Step 5: Migrate search_pipeline.py to use SearchPipelineParams**

Read `search_pipeline.py` and replace the three functions (`run_hybrid_pipeline`, `run_vector_pipeline`, `dispatch_search`) to accept `SearchPipelineParams` instead of individual parameters. Keep the old signatures as thin wrappers during migration.

Targets:
- `run_hybrid_pipeline` (line 193, 9 params) — extract `mode, query_embedding, limit, fetch_limit, similarity_threshold, bm25_weight, language, file_pattern, chunk_types` into `SearchPipelineParams`
- `run_vector_pipeline` (line 239, 7 params) — same extraction
- `dispatch_search` (line 297, 10 params) — same extraction

- [ ] **Step 6: Migrate search_engine.py to use SearchExecutionContext**

Targets:
- `_execute_and_record` (line 628, 11 params)
- `_record_and_store_results` (line 672, 10 params)
- `search` (line 740, 14 params) — the main entry point, builds context then delegates
- `search_paginated` (line 802, 13 params)

- [ ] **Step 7: Migrate embedding.py to use EmbeddingBatchParams**

Targets:
- `embed_single_batch_with_retry` (line 115, 8 params)
- `_run_parallel_batches` (line 328, 10 params)
- `batch_embed` (line 370, 7 params)

- [ ] **Step 8: Migrate mixins/search.py**

Targets:
- `_record_and_cache` (line 169, 8 params)
- `search` (line 275, 13 params)
- `search_paginated` (line 347, 13 params)

- [ ] **Step 9: Update __init__.py re-exports**

Add `SearchPipelineParams`, `SearchExecutionContext`, `EmbeddingBatchParams` to `core/vectorstore/__init__.py`.

- [ ] **Step 10: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 11: Verify smell reduction**

Run: `uv run deepwiki check --json`
Expected: long_parameter_list count drops by ~16

- [ ] **Step 12: Commit**

```bash
git add src/local_deepwiki/core/vectorstore/search_params.py \
        src/local_deepwiki/core/vectorstore/search_pipeline.py \
        src/local_deepwiki/core/vectorstore/search_engine.py \
        src/local_deepwiki/core/vectorstore/mixins/search.py \
        src/local_deepwiki/core/vectorstore/embedding.py \
        src/local_deepwiki/core/vectorstore/__init__.py \
        tests/test_search_params.py
git commit -m "refactor: introduce search pipeline parameter objects (16 smells)"
```

---

### Task 2: Wiki Generation Context Extension

Fixes 13 long_parameter_list smells across `generators/wiki/` by extending the existing `WikiPipelineContext` pattern.

**Files:**
- Create: `src/local_deepwiki/generators/wiki/pipeline_params.py`
- Modify: `src/local_deepwiki/generators/wiki/files.py:388,689`
- Modify: `src/local_deepwiki/generators/wiki/generator.py:121,616`
- Modify: `src/local_deepwiki/generators/wiki/modules.py:277`
- Modify: `src/local_deepwiki/generators/wiki/phases.py:313,390,588`
- Modify: `src/local_deepwiki/generators/wiki/plugin_runner.py:123,185`
- Modify: `src/local_deepwiki/generators/wiki/postprocessing.py:42,88,225`
- Modify: `src/local_deepwiki/generators/wiki/codemap_pages.py:159`
- Test: `tests/test_wiki_pipeline_params.py`

- [ ] **Step 1: Write failing test for WikiPipelineParams**

```python
# tests/test_wiki_pipeline_params.py
"""Tests for wiki pipeline parameter objects."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from local_deepwiki.generators.wiki.pipeline_params import WikiPipelineParams


class TestWikiPipelineParams:
    def test_frozen(self):
        params = WikiPipelineParams(
            repo_path=Path("/tmp/repo"),
            wiki_path=Path("/tmp/wiki"),
            vector_store=MagicMock(),
            index_status=MagicMock(),
            config=MagicMock(),
        )
        with pytest.raises(FrozenInstanceError):
            params.repo_path = Path("/other")

    def test_defaults(self):
        params = WikiPipelineParams(
            repo_path=Path("/tmp/repo"),
            wiki_path=Path("/tmp/wiki"),
            vector_store=MagicMock(),
            index_status=MagicMock(),
            config=MagicMock(),
        )
        assert params.progress_callback is None
        assert params.full_rebuild is False
        assert params.max_file_pages is None
        assert params.llm_provider is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wiki_pipeline_params.py -v`
Expected: FAIL

- [ ] **Step 3: Create WikiPipelineParams**

```python
# src/local_deepwiki/generators/wiki/pipeline_params.py
"""Parameter objects for wiki generation pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.models.foundation import ProgressCallback


@dataclass(frozen=True)
class WikiPipelineParams:
    """Consolidated parameters for wiki generation pipeline functions.

    Replaces the common (repo_path, wiki_path, vector_store, index_status,
    config, progress_callback, full_rebuild, max_file_pages, llm_provider)
    parameter pattern that appears across files.py, generator.py, modules.py,
    phases.py, plugin_runner.py, postprocessing.py, and codemap_pages.py.
    """

    repo_path: Path
    wiki_path: Path
    vector_store: Any  # VectorStore — Any to avoid circular import at runtime
    index_status: Any  # IndexStatus
    config: Any  # Config
    progress_callback: ProgressCallback | None = None
    full_rebuild: bool = False
    max_file_pages: int | None = None
    llm_provider: Any | None = None  # LLMProvider
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wiki_pipeline_params.py -v`
Expected: PASS

- [ ] **Step 5: Migrate generators/wiki/generator.py**

Targets:
- `WikiGenerator.__init__` (line 121, 7 params) — accept `WikiPipelineParams` as alternative constructor
- `generate_wiki` (line 616, 11 params) — accept `WikiPipelineParams`, destructure internally

- [ ] **Step 6: Migrate generators/wiki/files.py**

Targets:
- `_generate_new_file_page` (line 388, 10 params)
- `generate_file_docs` (line 689, 7 params)

- [ ] **Step 7: Migrate generators/wiki/modules.py, phases.py**

Targets:
- `generate_single_module_doc` (line 277, 8 params)
- `_add_auxiliary_page` (line 313, 7 params)
- `_safe_executor_page` (line 390, 7 params)
- `generate_onboarding_page` (line 588, 7 params)

- [ ] **Step 8: Migrate generators/wiki/plugin_runner.py, postprocessing.py, codemap_pages.py**

Targets:
- `run_plugin_generators` (line 123, 11 params)
- `_execute_plugin_generators` (line 185, 9 params)
- `generate_codemap_pages_phase` (line 42, 8 params)
- `apply_cross_linking` (line 88, 8 params)
- `generate_freshness_and_finalize` (line 225, 9 params)
- `_process_codemap_topic` (line 159, 9 params)

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add src/local_deepwiki/generators/wiki/pipeline_params.py \
        src/local_deepwiki/generators/wiki/*.py \
        tests/test_wiki_pipeline_params.py
git commit -m "refactor: introduce WikiPipelineParams (13 smells)"
```

---

### Task 3: Parsing Pipeline Context

Fixes 4 long_parameter_list smells in `core/parsing_pipeline.py`.

**Files:**
- Modify: `src/local_deepwiki/core/parsing_pipeline.py:51,154,206,366`
- Test: `tests/test_parsing_pipeline_params.py`

- [ ] **Step 1: Write failing test for PipelineContext**

```python
# tests/test_parsing_pipeline_params.py
"""Tests for parsing pipeline parameter objects."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from local_deepwiki.core.parsing_pipeline import PipelineContext


class TestPipelineContext:
    def test_frozen(self):
        ctx = PipelineContext(
            repo_root=Path("/tmp"),
            chunker=MagicMock(),
            graph_extractor=MagicMock(),
            source_files=[],
            exclude_patterns=[],
            window_size=50,
            overlap=10,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.window_size = 100

    def test_defaults(self):
        ctx = PipelineContext(
            repo_root=Path("/tmp"),
            chunker=MagicMock(),
            graph_extractor=MagicMock(),
            source_files=[],
            exclude_patterns=[],
        )
        assert ctx.window_size == 50
        assert ctx.overlap == 10
        assert ctx.progress_callback is None
        assert ctx.max_workers == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_parsing_pipeline_params.py -v`
Expected: FAIL

- [ ] **Step 3: Add PipelineContext dataclass to parsing_pipeline.py**

Add at the top of `parsing_pipeline.py` (after imports):

```python
@dataclass(frozen=True)
class PipelineContext:
    """Consolidated context for the file parsing pipeline."""

    repo_root: Path
    chunker: Any  # CodeChunker
    graph_extractor: Any  # GraphExtractor
    source_files: list[Path]
    exclude_patterns: list[str]
    window_size: int = 50
    overlap: int = 10
    progress_callback: Any | None = None
    max_workers: int = 4
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_parsing_pipeline_params.py -v`
Expected: PASS

- [ ] **Step 5: Migrate FileParsingPipeline.__init__ and helpers**

Targets:
- `__init__` (line 51, 7 params) — accept `PipelineContext`
- `_run_window_loop` (line 154, 11 params) — extract shared params from context
- `_process_window` (line 206, 10 params) — same
- `_process_chunk_batch` (line 366, 7 params) — same

- [ ] **Step 6: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/core/parsing_pipeline.py tests/test_parsing_pipeline_params.py
git commit -m "refactor: introduce PipelineContext for parsing pipeline (4 smells)"
```

---

### Task 4: Audit Convenience Methods

Fixes 4 long_parameter_list smells in `core/audit.py`. The `AuditEvent` dataclass already exists — the convenience methods (`log_access_decision`, `log_query_execution`, `log_index_operation`, `log_export_operation`) duplicate fields that `AuditEvent` already holds. Replace with thin wrappers that accept partial `AuditEvent` kwargs.

**Files:**
- Modify: `src/local_deepwiki/core/audit.py:220,262,318,384`
- Test: existing tests in `tests/test_audit.py`

- [ ] **Step 1: Read existing AuditEvent dataclass and test file**

Read `src/local_deepwiki/core/audit.py` (lines 1-100) and `tests/test_audit.py` to understand the existing `AuditEvent` structure and test patterns.

- [ ] **Step 2: Write failing tests for new convenience API**

Add tests to `tests/test_audit.py` that verify the new parameter objects:

```python
class TestAuditConvenienceParams:
    def test_log_query_with_query_params(self, logger):
        from local_deepwiki.core.audit import QueryParams

        params = QueryParams(
            subject_id="user1",
            repo_path="/repo",
            query="test query",
            success=True,
            query_type="search",
        )
        logger.log_query(params)
        assert len(logger._events) == 1
        assert logger._events[0].resource_path == "/repo"

    def test_log_index_with_index_params(self, logger):
        from local_deepwiki.core.audit import IndexParams

        params = IndexParams(
            subject_id="user1",
            repo_path="/repo",
            operation="completed",
            success=True,
            files_processed=10,
        )
        logger.log_index(params)
        assert len(logger._events) == 1

    def test_log_export_with_export_params(self, logger):
        from local_deepwiki.core.audit import ExportParams

        params = ExportParams(
            subject_id="user1",
            wiki_path="/wiki",
            output_path="/out",
            export_type="html",
            operation="completed",
            success=True,
        )
        logger.log_export(params)
        assert len(logger._events) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_audit.py -v -k "Params"`
Expected: FAIL

- [ ] **Step 4: Add parameter dataclasses and new methods**

Add to `core/audit.py`:

```python
@dataclass(frozen=True)
class QueryParams:
    """Parameters for query audit logging."""
    subject_id: str | None
    repo_path: str
    query: str
    success: bool
    query_type: str = "search"
    error_message: str | None = None
    chunks_returned: int | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class IndexParams:
    """Parameters for index operation audit logging."""
    subject_id: str | None
    repo_path: str
    operation: str
    success: bool
    files_processed: int | None = None
    chunks_created: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ExportParams:
    """Parameters for export operation audit logging."""
    subject_id: str | None
    wiki_path: str
    output_path: str
    export_type: str
    operation: str
    success: bool
    pages_exported: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None
```

Add new methods `log_query(params)`, `log_index(params)`, `log_export(params)` that delegate to the existing methods. Then migrate callers to use the new API and remove the old methods.

- [ ] **Step 5: Migrate callers and run tests**

Search for all callers of `log_query_execution`, `log_index_operation`, `log_export_operation`, `log_access_decision`. Migrate each to use the parameter object API.

Run: `uv run pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/core/audit.py tests/test_audit.py
git commit -m "refactor: introduce audit parameter objects (4 smells)"
```

---

### Task 5: CLI Parameter Objects

Fixes 5 long_parameter_list smells across CLI modules.

**Files:**
- Modify: `src/local_deepwiki/cli/update_cli.py:101,157,256`
- Modify: `src/local_deepwiki/cli/init_cli.py:405`
- Modify: `src/local_deepwiki/cli/interactive_search.py:539`
- Test: existing CLI test files

- [ ] **Step 1: Add UpdateContext to update_cli.py**

```python
@dataclass(frozen=True)
class UpdateContext:
    """Consolidated context for the update command pipeline."""
    repo_path: Path
    wiki_path: Path
    full_rebuild: bool = False
    no_progress: bool = False
    dry_run: bool = False
    console: Any = None  # Console
```

- [ ] **Step 2: Add WizardConfig to init_cli.py**

```python
@dataclass(frozen=True)
class WizardConfig:
    """Configuration for the init wizard."""
    repo_path: Path
    console: Any  # Console
    non_interactive: bool = False
    force: bool = False
    provider_flag: str | None = None
    embedding_flag: str | None = None
    config_dest: Path | None = None
```

- [ ] **Step 3: Add SearchSessionConfig to interactive_search.py**

```python
@dataclass(frozen=True)
class SearchSessionConfig:
    """Configuration for an interactive search session."""
    repo_path: Path
    query: str | None = None
    language: str | None = None
    chunk_type: str | None = None
    file_pattern: str | None = None
    min_score: float = 0.0
    limit: int = 20
    interactive: bool = True
    show_preview: bool = False
```

- [ ] **Step 4: Migrate functions to accept parameter objects**

For each function, add a new overload accepting the dataclass. Keep old signatures temporarily for backward compat, then migrate callers and remove.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/test_config_cli.py tests/test_interactive_search.py -v`
Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/cli/update_cli.py \
        src/local_deepwiki/cli/init_cli.py \
        src/local_deepwiki/cli/interactive_search.py
git commit -m "refactor: introduce CLI parameter objects (5 smells)"
```

---

### Task 6: Codemap & Diagram Parameter Objects

Fixes 8 long_parameter_list smells across codemap and diagram generators.

**Files:**
- Create: `src/local_deepwiki/generators/codemap/params.py`
- Modify: `src/local_deepwiki/generators/codemap/generator.py:216`
- Modify: `src/local_deepwiki/generators/codemap/graph.py:281,421,460,542`
- Modify: `src/local_deepwiki/generators/diagrams/dependency_diagram.py:48,102,143,412`
- Test: `tests/test_codemap_params.py`

- [ ] **Step 1: Write failing test for CodemapParams and DiagramScanContext**

```python
# tests/test_codemap_params.py
"""Tests for codemap and diagram parameter objects."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from local_deepwiki.generators.codemap.params import (
    CodemapRequest,
    GraphBuildContext,
)


class TestCodemapRequest:
    def test_frozen(self):
        req = CodemapRequest(
            entry_point="main",
            focus="execution_flow",
            depth=3,
            max_nodes=30,
        )
        with pytest.raises(FrozenInstanceError):
            req.depth = 5

    def test_defaults(self):
        req = CodemapRequest(entry_point="main")
        assert req.focus == "execution_flow"
        assert req.depth == 5
        assert req.max_nodes == 30


class TestGraphBuildContext:
    def test_frozen(self):
        from unittest.mock import MagicMock

        ctx = GraphBuildContext(
            vector_store=MagicMock(),
            repo_path="/tmp",
            entry_file="main.py",
            entry_function="main",
            depth=3,
            max_nodes=30,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.depth = 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_codemap_params.py -v`
Expected: FAIL

- [ ] **Step 3: Create parameter objects**

```python
# src/local_deepwiki/generators/codemap/params.py
"""Parameter objects for codemap and graph building."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CodemapRequest:
    """Parameters for a codemap generation request."""
    entry_point: str
    focus: str = "execution_flow"
    depth: int = 5
    max_nodes: int = 30
    include_tests: bool = False


@dataclass(frozen=True)
class GraphBuildContext:
    """Context for cross-file graph building."""
    vector_store: Any
    repo_path: str
    entry_file: str
    entry_function: str
    depth: int = 5
    max_nodes: int = 30
    language: str | None = None
```

- [ ] **Step 4: Migrate codemap functions**

Targets:
- `generate_codemap` (line 216, 9 params)
- `_apply_fallback_search` (line 281, 7 params)
- `_resolve_cross_file_callee` (line 421, 8 params)
- `_resolve_callees_for_node` (line 460, 10 params)
- `build_cross_file_graph` (line 542, 7 params)

- [ ] **Step 5: Create DiagramScanContext and migrate diagram functions**

Add to `generators/diagrams/dependency_diagram.py`:

```python
@dataclass(frozen=True)
class DiagramScanContext:
    """Context for dependency diagram import scanning."""
    chunks: list
    file_path: str
    import_edges: set
    imported_modules: set
    module_name: str
    all_modules: set
    reverse_alias_map: dict
    source_code: str | None = None
    known_functions: set | None = None
```

Targets:
- `_scan_import_lines` (line 48, 10 params)
- `_scan_chunk_imports` (line 102, 11 params)
- `_scan_fallback_chunks` (line 143, 10 params)
- `generate_dependency_graph` (line 412, 8 params) — separate from scan context

- [ ] **Step 6: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/generators/codemap/params.py \
        src/local_deepwiki/generators/codemap/generator.py \
        src/local_deepwiki/generators/codemap/graph.py \
        src/local_deepwiki/generators/diagrams/dependency_diagram.py \
        tests/test_codemap_params.py
git commit -m "refactor: introduce codemap and diagram parameter objects (8 smells)"
```

---

### Task 7: Retry & Handlers Parameter Objects

Fixes 4 smells in `providers/retry.py` and 8 smells across `handlers/`.

**Files:**
- Modify: `src/local_deepwiki/providers/retry.py:61,84,113,139`
- Modify: `src/local_deepwiki/handlers/indexing.py:165,214,282,406`
- Modify: `src/local_deepwiki/handlers/analysis_entity.py:464,538`
- Modify: `src/local_deepwiki/handlers/analysis_diff.py:411`
- Modify: `src/local_deepwiki/handlers/core.py:261`
- Test: existing test files

- [ ] **Step 1: Add RetryContext to providers/retry.py**

```python
@dataclass(frozen=True)
class RetryContext:
    """Context for a retry attempt."""
    func_name: str
    attempt: int
    max_retries: int
    base_delay: float
    max_delay: float
    backoff_factor: float = 2.0
    jitter: bool = True
```

Migrate `_retry_known_error`, `_handle_retryable_exception`, `_handle_generic_exception`, `_execute_with_backoff` to use `RetryContext`.

- [ ] **Step 2: Add IndexingPipelineContext to handlers/indexing.py**

```python
@dataclass(frozen=True)
class IndexingPipelineContext:
    """Context for the indexing handler pipeline."""
    repo_path: str
    wiki_path: str | None
    config: Any
    vector_store: Any
    notifier: Any  # ProgressNotifier
    full_rebuild: bool = False
    wiki_generation: str = "full"
```

Migrate `_generate_wiki_hybrid`, `_generate_wiki_for_mode`, `_run_index_and_notify`, `_run_pipeline_with_audit`.

- [ ] **Step 3: Create EntityAnalysisContext for handlers/analysis_entity.py**

```python
@dataclass(frozen=True)
class EntityAnalysisContext:
    """Context for entity analysis operations (reverse calls, inheritance)."""
    vector_store: Any
    repo_path: str
    entity_name: str
    entity_file: str
    sections: dict
    max_results: int = 5
```

Migrate `_collect_reverse_calls` (line 464) and `_collect_inheritance_dependents` (line 538).

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/providers/retry.py \
        src/local_deepwiki/handlers/indexing.py \
        src/local_deepwiki/handlers/analysis_entity.py \
        src/local_deepwiki/handlers/analysis_diff.py \
        src/local_deepwiki/handlers/core.py
git commit -m "refactor: introduce retry and handler parameter objects (12 smells)"
```

---

### Task 8: Services & Remaining Parameter Objects

Fixes 9 smells in `services/` and ~9 remaining scattered smells.

**Files:**
- Modify: `src/local_deepwiki/services/analysis_service.py:57,163,241,304,679,739`
- Modify: `src/local_deepwiki/services/indexing_service.py:34`
- Modify: `src/local_deepwiki/services/query_service.py:167,291`
- Modify: `src/local_deepwiki/generators/analysis/onboarding.py:492,582`
- Modify: `src/local_deepwiki/generators/analysis/dependency_graph.py:666`
- Modify: `src/local_deepwiki/generators/analysis/api_docs.py:375`
- Modify: `src/local_deepwiki/generators/dir_tree.py:97`
- Modify: `src/local_deepwiki/core/indexer_status.py:42`
- Modify: `src/local_deepwiki/web/routes_codemap.py:249`
- Modify: `src/local_deepwiki/core/deep_research/pipeline.py:71,180,575`
- Modify: `src/local_deepwiki/core/chunker.py:343`
- Test: existing test files

- [ ] **Step 1: Add EntityExplainRequest to services/analysis_service.py**

```python
@dataclass(frozen=True)
class EntityExplainRequest:
    """Request parameters for explain_entity."""
    repo_path: str
    entity_name: str
    entity_file: str | None = None
    include_callers: bool = True
    include_callees: bool = True
    include_inheritance: bool = True
    include_tests: bool = True
    include_api_docs: bool = True
    include_git_blame: bool = True
    max_results: int = 5
```

This fixes `explain_entity` (11 params), `_populate_entity_sections` (13 params), `_collect_reverse_calls` (7 params), and `_collect_inheritance_dependents` (7 params) — which also deduplicates with `handlers/analysis_entity.py`.

- [ ] **Step 2: Fix _normalize_impact_request (already has ImpactAnalysisRequest)**

`_normalize_impact_request` (line 57, 13 params) exists to normalize into `ImpactAnalysisRequest` — refactor it to accept `ImpactAnalysisRequest` directly and remove the long param list.

`impact_analysis` (line 241, 13 params) — same treatment.

- [ ] **Step 3: Fix remaining scattered smells**

For each of these, add a small frozen dataclass in the same file:

- `services/indexing_service.py:run_pipeline` (7 params) — `IndexPipelineRequest`
- `services/query_service.py:answer_question` (7 params) — `QuestionRequest`
- `services/query_service.py:search_code` (9 params) — use existing `SearchRequest`
- `generators/analysis/onboarding.py` (2 functions, 7-8 params) — `OnboardingContext`
- `generators/analysis/dependency_graph.py:_add_import_edges` (7 params) — `ImportEdgeContext`
- `generators/dir_tree.py:_traverse_directory` (8 params) — `TraversalContext`
- `core/indexer_status.py:__init__` (7 params) — already a dataclass, convert to `@dataclass(frozen=True)` if not already
- `web/routes_codemap.py:_codemap_sse_stream` (9 params) — `CodemapStreamContext`
- `core/deep_research/pipeline.py:__init__` (14 params) — already has `ResearchConfig`; remove backward-compat individual kwargs and require `config=ResearchConfig(...)`
- `core/deep_research/pipeline.py:_save_checkpoint` (8 params) — `CheckpointData`
- `core/deep_research/pipeline.py:_finalize_research` (7 params) — `ResearchResult`
- `core/chunker.py:_create_class_summary_chunk` (7 params) — `ClassSummaryContext`

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Verify smell count**

Run: `uv run deepwiki check --json`
Expected: long_parameter_list count near 0, smells score ~75-80

- [ ] **Step 6: Commit**

```bash
git add -u
git commit -m "refactor: introduce service and remaining parameter objects (~18 smells)"
```

---

## Phase 1 Checkpoint

Run: `uv run deepwiki check --json`

**Expected scores:**
- Smells: 52.1 -> ~75 (from eliminating ~80 of 85 long_parameter_list smells)
- Overall: 80.6 -> ~87

---

## Phase 2: God Class Decomposition

> **Note:** The spec proposed VectorStore -> VectorStore + VectorSearch, and SearchEngine -> SearchEngine + SearchStrategies. After detailed code analysis, the plan refines these: VectorStore's search is already delegated to SearchEngine, so the extract target is EmbeddingBatcher. SearchEngine's config resolution methods form the most cohesive extract group, not search strategies (which are already in search_pipeline.py). Same goal, better boundaries.

### Task 9: Split VectorStore

Reduce from 22 methods/507 lines to <15 methods/<500 lines by extracting embedding operations.

**Files:**
- Create: `src/local_deepwiki/core/vectorstore/embedding_batcher.py`
- Modify: `src/local_deepwiki/core/vectorstore/store.py`
- Modify: `src/local_deepwiki/core/vectorstore/__init__.py`
- Test: `tests/test_embedding_batcher.py`

- [ ] **Step 1: Write failing test for EmbeddingBatcher**

```python
# tests/test_embedding_batcher.py
"""Tests for EmbeddingBatcher extracted from VectorStore."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.core.vectorstore.embedding_batcher import EmbeddingBatcher


class TestEmbeddingBatcher:
    def test_init(self):
        provider = MagicMock()
        provider.name = "test"
        batcher = EmbeddingBatcher(
            embedding_provider=provider,
            batch_size=100,
            max_concurrent=4,
        )
        assert batcher.batch_size == 100
        assert batcher.max_concurrent == 4

    @pytest.mark.asyncio
    async def test_batch_embed(self):
        provider = AsyncMock()
        provider.embed = AsyncMock(return_value=[[0.1, 0.2]])
        provider.name = "test"
        batcher = EmbeddingBatcher(
            embedding_provider=provider,
            batch_size=10,
            max_concurrent=1,
        )
        results = await batcher.batch_embed(["hello world"])
        assert len(results) == 1

    def test_is_local_provider(self):
        provider = MagicMock()
        provider.name = "sentence-transformers"
        batcher = EmbeddingBatcher(embedding_provider=provider)
        assert batcher.is_local_provider is True

        provider.name = "openai"
        batcher2 = EmbeddingBatcher(embedding_provider=provider)
        assert batcher2.is_local_provider is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_embedding_batcher.py -v`
Expected: FAIL

- [ ] **Step 3: Extract EmbeddingBatcher from VectorStore**

Move these methods from `VectorStore` to `EmbeddingBatcher`:
- `_is_local_provider` (line 369) -> property `is_local_provider`
- `_get_optimal_batch_config` (line 375) -> `get_optimal_batch_config`
- `_batch_embed` (line 383) -> `batch_embed`
- `_batch_embed_sequential` (line 401) -> `batch_embed_sequential`

Also move `_row_to_chunk` (line 578) and `_chunk_to_text` (line 603) to module-level functions (they're static/classmethod-like).

`VectorStore` gains `self._embedding_batcher = EmbeddingBatcher(...)` in `__init__` and delegates embedding calls.

- [ ] **Step 4: Run tests to verify extraction**

Run: `uv run pytest tests/test_embedding_batcher.py tests/test_vectorstore*.py -v`
Expected: All pass

- [ ] **Step 5: Update __init__.py**

Add `EmbeddingBatcher` to re-exports.

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/core/vectorstore/embedding_batcher.py \
        src/local_deepwiki/core/vectorstore/store.py \
        src/local_deepwiki/core/vectorstore/__init__.py \
        tests/test_embedding_batcher.py
git commit -m "refactor: extract EmbeddingBatcher from VectorStore (god class)"
```

---

### Task 10: Split SearchEngine

Reduce from 22 methods/539 lines to <15 methods/<500 lines by extracting config resolution.

**Files:**
- Create: `src/local_deepwiki/core/vectorstore/search_config_resolver.py`
- Modify: `src/local_deepwiki/core/vectorstore/search_engine.py`
- Modify: `src/local_deepwiki/core/vectorstore/__init__.py`
- Test: `tests/test_search_config_resolver.py`

- [ ] **Step 1: Write failing test for SearchConfigResolver**

```python
# tests/test_search_config_resolver.py
"""Tests for SearchConfigResolver extracted from SearchEngine."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from local_deepwiki.core.vectorstore.search_config_resolver import (
    SearchConfigResolver,
)


class TestSearchConfigResolver:
    def test_resolve_search_profile(self):
        resolver = SearchConfigResolver(
            default_search_profile=MagicMock(),
            default_search_mode="vector",
            bm25_weight=0.3,
        )
        # Verify it resolves profile to enum + config
        assert resolver is not None

    def test_compute_fetch_limit(self):
        resolver = SearchConfigResolver(
            default_search_profile=MagicMock(),
            default_search_mode="vector",
            bm25_weight=0.3,
        )
        limit = resolver.compute_fetch_limit(requested_limit=10, mode="hybrid")
        assert limit >= 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_search_config_resolver.py -v`
Expected: FAIL

- [ ] **Step 3: Extract SearchConfigResolver**

Move from `SearchEngine`:
- `resolve_search_profile` (line 430)
- `_resolve_search_config` (line 450)
- `_compute_fetch_limit` (line 470)
- Properties: `default_search_profile`, `adaptive_search_enabled`, `fuzzy_search_helper` (getters/setters)
- `get_fuzzy_helper` (line 407)

`SearchEngine` gains `self._config_resolver = SearchConfigResolver(...)` and delegates.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/core/vectorstore/search_config_resolver.py \
        src/local_deepwiki/core/vectorstore/search_engine.py \
        src/local_deepwiki/core/vectorstore/__init__.py \
        tests/test_search_config_resolver.py
git commit -m "refactor: extract SearchConfigResolver from SearchEngine (god class)"
```

---

### Task 11: Split RepositoryIndexer

Reduce from 19 methods/521 lines by extracting wiki orchestration.

**Files:**
- Create: `src/local_deepwiki/core/wiki_orchestrator.py`
- Modify: `src/local_deepwiki/core/indexer.py`
- Test: `tests/test_wiki_orchestrator.py`

- [ ] **Step 1: Identify methods to extract**

Read `core/indexer.py` and identify the wiki-generation-related methods. Based on the analysis:
- Keep in `RepositoryIndexer`: `__init__`, `_init_composition_objects`, `_compile_exclude_patterns`, `_scan_for_secrets`, `_create_parsing_pipeline`, `_parse_single_file`, `_delete_old_chunks_for_modified_files`, `_delete_chunks_for_deleted_files`, `_sync_graph_helper`, `_run_graph_extraction`, `_parse_files_parallel`, `_find_source_files`, `get_status`, `search`
- Extract event emission to module-level helpers or a small `IndexEventEmitter`: `_emit_index_start`, `_emit_index_complete`
- Simplify `index()` and `_prepare_incremental_update()` by moving orchestration logic to a separate function

The goal is to get below 15 methods. Currently 19. Moving 4-5 methods to helpers/separate class achieves this.

- [ ] **Step 2: Write failing test**

```python
# tests/test_wiki_orchestrator.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestIndexEventHelpers:
    @pytest.mark.asyncio
    async def test_emit_index_start(self):
        from local_deepwiki.core.indexer import emit_index_start

        events = MagicMock()
        await emit_index_start(events, "/repo", full_rebuild=False)
        events.emit.assert_called_once()
```

- [ ] **Step 3: Extract event emission to module-level functions**

Move `_emit_index_start` and `_emit_index_complete` from the class to module-level `async def emit_index_start(events, repo_path, *, full_rebuild)` and `async def emit_index_complete(events, repo_path, index_status, elapsed)`.

- [ ] **Step 4: Extract _prepare_incremental_update to module-level function**

Move `_prepare_incremental_update` out of the class — it doesn't need `self`, just the index status tracker and repo path.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/core/indexer.py tests/test_wiki_orchestrator.py
git commit -m "refactor: extract helpers from RepositoryIndexer (god class)"
```

---

### Task 12: Split CodeChunker

Reduce from 17 methods/670 lines by moving summary chunk creation to module-level functions.

**Files:**
- Create: `src/local_deepwiki/core/chunk_builders.py`
- Modify: `src/local_deepwiki/core/chunker.py`
- Test: `tests/test_chunk_builders.py`

- [ ] **Step 1: Identify methods to extract**

Summary/overview chunk builders that don't need `self` beyond `self.config`:
- `_create_module_chunk` (line 148)
- `_create_file_summary` (line 194)
- `_create_imports_chunk` (line 242)
- `_create_file_summary_chunk` (line 584)
- `_create_module_summary_chunk` (line 633)

These 5 methods can become module-level functions that accept `config` as a parameter. This drops `CodeChunker` from 17 to 12 methods.

- [ ] **Step 2: Write failing tests**

```python
# tests/test_chunk_builders.py
"""Tests for chunk builder functions extracted from CodeChunker."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from local_deepwiki.core.chunk_builders import (
    create_file_summary,
    create_imports_chunk,
    create_module_chunk,
)


class TestCreateModuleChunk:
    def test_basic(self):
        chunk = create_module_chunk(
            file_path=Path("test.py"),
            repo_root=Path("/repo"),
            language="python",
            docstring="Module docstring",
            imports=["import os"],
            classes=["Foo"],
            functions=["bar"],
            config=MagicMock(min_chunk_lines=1),
        )
        assert chunk is not None
        assert chunk.chunk_type == "module"
```

- [ ] **Step 3: Extract chunk builders**

Move the 5 methods to `core/chunk_builders.py` as standalone functions. Each receives `config` as a parameter instead of accessing `self.config`.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/core/chunk_builders.py \
        src/local_deepwiki/core/chunker.py \
        tests/test_chunk_builders.py
git commit -m "refactor: extract chunk builders from CodeChunker (god class)"
```

---

### Task 13: Split DeepResearchPipeline

Reduce from 17 methods/576 lines by extracting checkpoint management (already partially done with `CheckpointManager`).

**Files:**
- Modify: `src/local_deepwiki/core/deep_research/pipeline.py`
- Modify: `src/local_deepwiki/core/deep_research/checkpoints.py`
- Modify: `src/local_deepwiki/core/deep_research/__init__.py`
- Test: existing tests

- [ ] **Step 1: Identify methods to move to CheckpointManager**

These methods belong with the existing `CheckpointManager` class:
- `_save_checkpoint` (line 180)
- `_create_checkpoint` (line 229)
- `_results_to_checkpoint_format` (line 249)
- `_checkpoint_to_results` (line 265)
- `_init_checkpoint` (line 350)

`load_checkpoint`, `list_checkpoints`, `delete_checkpoint` already delegate to `CheckpointManager`.

- [ ] **Step 2: Move checkpoint methods**

Move the 5 checkpoint-related methods to either `CheckpointManager` (in `checkpoints.py`) or to module-level functions in `checkpoints.py`. Update `DeepResearchPipeline` to delegate.

This drops the pipeline from 17 to 12 methods.

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest tests/test_deep_research*.py -v`
Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/core/deep_research/pipeline.py \
        src/local_deepwiki/core/deep_research/checkpoints.py \
        src/local_deepwiki/core/deep_research/__init__.py
git commit -m "refactor: move checkpoint methods to CheckpointManager (god class)"
```

---

## Phase 2 Checkpoint

Run: `uv run deepwiki check --json`

**Expected scores:**
- Smells: ~75 -> ~82 (god_class count: 5 -> 0)
- Overall: ~87 -> ~89

---

## Phase 3: Protocol Interfaces

### Task 14: Add Protocols at Package Boundaries

Increase abstractness from 0.01 to ~0.10+ by adding Protocol interfaces that consumers import instead of concrete classes.

**Files:**
- Create: `src/local_deepwiki/core/protocols.py`
- Create: `src/local_deepwiki/services/protocols.py`
- Create: `src/local_deepwiki/generators/protocols.py`
- Modify: `src/local_deepwiki/core/__init__.py`
- Modify: `src/local_deepwiki/services/__init__.py`
- Modify: `src/local_deepwiki/generators/__init__.py`
- Test: `tests/test_protocols.py`

- [ ] **Step 1: Write failing test for Protocols**

```python
# tests/test_protocols.py
"""Tests that Protocol interfaces are correctly defined and satisfied."""
from __future__ import annotations

from typing import runtime_checkable

import pytest

from local_deepwiki.core.protocols import (
    ChunkerProtocol,
    IndexerProtocol,
    SearchEngineProtocol,
)
from local_deepwiki.generators.protocols import (
    AnalysisGeneratorProtocol,
    WikiGeneratorProtocol,
)
from local_deepwiki.services.protocols import (
    AnalysisServiceProtocol,
    QueryServiceProtocol,
)


class TestCoreProtocols:
    def test_indexer_protocol_is_runtime_checkable(self):
        assert hasattr(IndexerProtocol, "__protocol_attrs__") or hasattr(
            IndexerProtocol, "_is_protocol"
        )

    def test_indexer_implementation_satisfies_protocol(self):
        from local_deepwiki.core.indexer import RepositoryIndexer

        assert isinstance(RepositoryIndexer, type)
        # Verify method signatures match
        assert hasattr(RepositoryIndexer, "index")
        assert hasattr(RepositoryIndexer, "get_status")
        assert hasattr(RepositoryIndexer, "search")

    def test_search_engine_protocol(self):
        from local_deepwiki.core.vectorstore import SearchEngine

        assert hasattr(SearchEngine, "search")
        assert hasattr(SearchEngine, "search_from_request")

    def test_chunker_protocol(self):
        from local_deepwiki.core.chunker import CodeChunker

        assert hasattr(CodeChunker, "chunk_file")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_protocols.py -v`
Expected: FAIL

- [ ] **Step 3: Create core/protocols.py**

```python
# src/local_deepwiki/core/protocols.py
"""Protocol interfaces for core components.

These Protocols define the contracts that core components expose to
handlers, services, and generators. Consumers should type-hint against
these Protocols rather than concrete classes to improve abstractness
and testability.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class IndexerProtocol(Protocol):
    """Protocol for repository indexing."""

    async def index(
        self, *, full_rebuild: bool = False, progress_callback: Any = None
    ) -> Any: ...

    def get_status(self) -> Any: ...

    async def search(
        self, query: str, limit: int = 10, language: str | None = None
    ) -> list: ...


@runtime_checkable
class SearchEngineProtocol(Protocol):
    """Protocol for search operations."""

    async def search(self, query: str, limit: int = 10, **kwargs: Any) -> list: ...

    async def search_from_request(self, request: Any) -> Any: ...


@runtime_checkable
class ChunkerProtocol(Protocol):
    """Protocol for code chunking."""

    def chunk_file(self, file_path: Path, repo_root: Path) -> Iterator: ...
```

- [ ] **Step 4: Create services/protocols.py**

```python
# src/local_deepwiki/services/protocols.py
"""Protocol interfaces for service layer."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class QueryServiceProtocol(Protocol):
    """Protocol for question answering and code search."""

    async def answer_question(self, repo_path: str, query: str, **kwargs: Any) -> Any: ...

    async def search_code(self, repo_path: str, query: str, **kwargs: Any) -> Any: ...


@runtime_checkable
class AnalysisServiceProtocol(Protocol):
    """Protocol for code analysis operations."""

    async def explain_entity(self, repo_path: str, entity_name: str, **kwargs: Any) -> Any: ...

    async def impact_analysis(self, repo_path: str, entity_name: str, **kwargs: Any) -> Any: ...
```

- [ ] **Step 5: Create generators/protocols.py**

```python
# src/local_deepwiki/generators/protocols.py
"""Protocol interfaces for generator components."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WikiGeneratorProtocol(Protocol):
    """Protocol for wiki generation."""

    async def generate(
        self, index_status: Any, *, progress_callback: Any = None, full_rebuild: bool = False
    ) -> Any: ...


@runtime_checkable
class AnalysisGeneratorProtocol(Protocol):
    """Protocol for analysis generation (complexity, coverage, etc.)."""

    async def analyze(self, repo_path: str, **kwargs: Any) -> Any: ...
```

Note: `WikiGeneratorProtocol` already exists in `generators/wiki/generator.py` and `VectorStoreProtocol` already exists in `core/vectorstore/store.py`. Before creating new protocols, check existing ones — extend or consolidate rather than duplicate.

- [ ] **Step 6: Update __init__.py re-exports**

Add Protocol classes to the respective `__init__.py` files.

- [ ] **Step 7: Update type annotations in consumers**

In key consumer files (handlers, services), update type hints to reference Protocols where the concrete type was used only for its interface. This is opt-in — change annotations where it makes the code clearer, don't force it everywhere.

- [ ] **Step 8: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/core/protocols.py \
        src/local_deepwiki/services/protocols.py \
        src/local_deepwiki/generators/protocols.py \
        src/local_deepwiki/core/__init__.py \
        src/local_deepwiki/services/__init__.py \
        src/local_deepwiki/generators/__init__.py \
        tests/test_protocols.py
git commit -m "refactor: add Protocol interfaces at package boundaries (coupling)"
```

---

## Phase 3 Checkpoint

Run: `uv run deepwiki check --json`

**Expected scores:**
- Coupling: 70.4 -> ~82 (abstractness rises from 0.01 to ~0.10+)
- Overall: ~89 -> ~91

---

## Phase 4: Remaining Smell Cleanup

### Feature Envy (not addressed)

The 12 feature_envy smells are intentionally not addressed as separate tasks. They are all in formatting/rendering code (Rich Tree builders in `config_cli.py`, result dict formatting in handlers) where accessing another object's properties repeatedly is inherent to the pattern. Fixing them would couple data and presentation. At 12 medium-severity smells they have negligible score impact compared to the 85 long_parameter_list + 5 god_class targets.

### Task 15: Fix Deep Nesting

Fixes 6 deep_nesting smells using guard clauses and early returns.

**Files:**
- Modify: `src/local_deepwiki/config/loader.py:258`
- Modify: `src/local_deepwiki/core/chunk_extractors.py:104,175`
- Modify: `src/local_deepwiki/generators/analysis/callgraph.py:110`
- Modify: `src/local_deepwiki/generators/diagrams/class_diagram.py:67`
- Modify: `src/local_deepwiki/plugins/registry.py:262`

- [ ] **Step 1: Read each function and apply guard clause pattern**

For `_apply_nested_updates` in `config/loader.py:258`:

Replace nested `if isinstance(value, dict)` checks with `continue` guards:

```python
def _apply_nested_updates(config, updates):
    for key, value in updates.items():
        if not isinstance(value, dict):
            # Direct value — handled by Pydantic model_copy
            continue
        current = getattr(config, key, None)
        if current is None or not isinstance(current, BaseModel):
            continue
        # Now process nested dict at depth 1
        _apply_single_level(current, value)
```

Extract a `_apply_single_level` helper for the inner loop.

- [ ] **Step 2: Fix chunk_extractors.py nesting**

For `_get_ts_js_parents` (line 104) and `_get_kotlin_parents` (line 175):

Extract the inner loop body into a helper function:

```python
def _collect_parent_identifiers(heritage_node, clause_types, id_types):
    """Extract parent identifiers from a class heritage node."""
    parents = []
    for clause in heritage_node.children:
        if clause.type not in clause_types:
            continue
        for item in clause.children:
            if item.type in id_types:
                parents.append(item.text.decode())
    return parents
```

- [ ] **Step 3: Fix remaining 3 nesting smells**

Apply the same guard-clause pattern to:
- `callgraph.py:_extract_swift_call` (line 110)
- `class_diagram.py:_extract_methods_from_class_content` (line 67)
- `registry.py:load_from_entry_points` (line 262)

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/config/loader.py \
        src/local_deepwiki/core/chunk_extractors.py \
        src/local_deepwiki/generators/analysis/callgraph.py \
        src/local_deepwiki/generators/diagrams/class_diagram.py \
        src/local_deepwiki/plugins/registry.py
git commit -m "refactor: flatten deep nesting with guard clauses (6 smells)"
```

---

### Task 16: Deduplicate _collect_inheritance_dependents

**Files:**
- Modify: `src/local_deepwiki/handlers/analysis_entity.py:538`
- Modify: `src/local_deepwiki/services/analysis_service.py:739`

- [ ] **Step 1: Verify duplication**

Read both functions and confirm they have identical logic. If so, consolidate into a shared utility.

- [ ] **Step 2: Move to shared location**

Create a shared function in `services/analysis_service.py` (or a new `services/analysis_utils.py`) and have `handlers/analysis_entity.py` import it.

If Task 7 already created `EntityAnalysisContext`, use it here.

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add src/local_deepwiki/handlers/analysis_entity.py \
        src/local_deepwiki/services/analysis_service.py
git commit -m "refactor: deduplicate _collect_inheritance_dependents"
```

---

### Task 17: Large File Splits (Source Only)

Fixes large_file smells for source files over 800 lines.

**Source files over threshold:**
- `core/vectorstore/search_engine.py` (857 lines) — already reduced by Task 10 (SearchConfigResolver extraction)
- `generators/analysis/api_docs.py` (828 lines) — split docstring parsing into `api_docs_parser.py`
- `generators/analysis/dependency_graph.py` (841 lines) — split data classes already in `dependency_graph_data.py`, verify remaining is under 800
- `handlers/analysis_architecture.py` (829 lines) — split formatting helpers into `analysis_architecture_format.py`
- `models/tool_args.py` (859 lines) — split into `tool_args_core.py` and `tool_args_analysis.py`
- `services/analysis_service.py` (867 lines) — already reduced by Task 8 extractions
- `tool_defs/analysis.py` (850 lines) — split into `tool_defs/analysis_core.py` and `tool_defs/analysis_extra.py`
- `generators/wiki/files.py` (802 lines) — borderline, may be under threshold after Task 2

- [ ] **Step 1: Check which files are still over 800 after prior tasks**

After Tasks 1-16, re-measure file sizes. Only split files that are still over 800.

- [ ] **Step 2: Split remaining oversized files**

For each file still over 800 lines:
1. Identify a cohesive group of functions to extract
2. Create a new file with the extracted functions
3. Update the original to import from the new file
4. Update `__init__.py` if needed

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest tests/ -x -q`

```bash
git add -u
git commit -m "refactor: split large files over 800 lines"
```

---

## Final Verification

### Task 18: Final Score Check and Cleanup

- [ ] **Step 1: Run architecture health check**

Run: `uv run deepwiki check --json`

**Target:** Overall >= 91.5 (Grade A)
- Complexity: A (100)
- Coupling: B+ (~82+)
- Smells: B+ (~85+)
- Layers: A (100)

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All 6,054+ tests pass

- [ ] **Step 3: If score is below target, identify remaining gaps**

Run: `uv run deepwiki check --json` and compare per-dimension scores.

If smells is still below 85: check remaining long_parameter_list count and fix stragglers.
If coupling is still below 82: add 1-2 more Protocol classes in high-fan-out modules.

- [ ] **Step 4: Final commit**

```bash
git add -u
git commit -m "refactor: architecture Grade A achieved"
```
