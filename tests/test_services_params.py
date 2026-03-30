"""Tests for service-layer and remaining parameter objects (Task 8).

Validates that the new frozen dataclasses are constructible,
immutable, and accepted by their consumer methods.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# EntityExplainRequest
# ---------------------------------------------------------------------------


class TestEntityExplainRequest:
    def test_frozen(self):
        from local_deepwiki.services.analysis_service import EntityExplainRequest

        req = EntityExplainRequest(
            entity_name="Foo",
            repo_path=Path("/tmp"),
            index_status=None,
            wiki_path=Path("/tmp/wiki"),
            vector_store=None,
        )
        with pytest.raises(FrozenInstanceError):
            req.entity_name = "Bar"  # type: ignore[misc]

    def test_defaults(self):
        from local_deepwiki.services.analysis_service import EntityExplainRequest

        req = EntityExplainRequest(
            entity_name="X",
            repo_path=Path("/tmp"),
            index_status=None,
            wiki_path=Path("/tmp/wiki"),
            vector_store=None,
        )
        assert req.include_call_graph is True
        assert req.include_inheritance is True
        assert req.include_test_examples is True
        assert req.include_api_docs is True
        assert req.max_test_examples == 3


# ---------------------------------------------------------------------------
# QuestionRequest / CodeSearchRequest
# ---------------------------------------------------------------------------


class TestQuestionRequest:
    def test_frozen(self):
        from local_deepwiki.services.query_service import QuestionRequest

        req = QuestionRequest(repo_path=Path("/tmp"), question="Hello?")
        with pytest.raises(FrozenInstanceError):
            req.question = "changed"  # type: ignore[misc]

    def test_defaults(self):
        from local_deepwiki.services.query_service import QuestionRequest

        req = QuestionRequest(repo_path=Path("/tmp"), question="Q")
        assert req.max_context == 10
        assert req.agentic_rag is False
        assert req.wiki_path is None
        assert req.debug is False


class TestCodeSearchRequest:
    def test_frozen(self):
        from local_deepwiki.services.query_service import CodeSearchRequest

        req = CodeSearchRequest(repo_path=Path("/tmp"), query="search")
        with pytest.raises(FrozenInstanceError):
            req.query = "changed"  # type: ignore[misc]

    def test_defaults(self):
        from local_deepwiki.services.query_service import CodeSearchRequest

        req = CodeSearchRequest(repo_path=Path("/tmp"), query="q")
        assert req.limit == 20
        assert req.language is None
        assert req.chunk_type is None
        assert req.path_filter is None
        assert req.use_fuzzy is False
        assert req.fuzzy_weight == 0.3


# ---------------------------------------------------------------------------
# IndexPipelineRequest
# ---------------------------------------------------------------------------


class TestIndexPipelineRequest:
    def test_frozen(self):
        from local_deepwiki.services.indexing_service import IndexPipelineRequest

        req = IndexPipelineRequest(repo_path=Path("/tmp"))
        with pytest.raises(FrozenInstanceError):
            req.repo_path = Path("/other")  # type: ignore[misc]

    def test_defaults(self):
        from local_deepwiki.services.indexing_service import IndexPipelineRequest

        req = IndexPipelineRequest(repo_path=Path("/tmp"))
        assert req.full_rebuild is False
        assert req.embedding_provider is None
        assert req.llm_provider is None
        assert req.generation_mode == "eager"
        assert req.progress_callback is None


# ---------------------------------------------------------------------------
# OnboardingContext
# ---------------------------------------------------------------------------


class TestOnboardingContext:
    def test_frozen(self):
        from unittest.mock import MagicMock

        from local_deepwiki.generators.analysis.onboarding import OnboardingContext

        ctx = OnboardingContext(manifest=MagicMock(), directory_tree="tree")
        with pytest.raises(FrozenInstanceError):
            ctx.directory_tree = "changed"  # type: ignore[misc]

    def test_defaults(self):
        from unittest.mock import MagicMock

        from local_deepwiki.generators.analysis.onboarding import OnboardingContext

        ctx = OnboardingContext(manifest=MagicMock(), directory_tree="tree")
        assert ctx.entry_points == ()
        assert ctx.codemaps == ()
        assert ctx.wiki_pages == ()
        assert ctx.test_layout == ()
        assert ctx.config_files == ()


# ---------------------------------------------------------------------------
# CheckpointData / SynthesisResult
# ---------------------------------------------------------------------------


class TestCheckpointData:
    def test_frozen(self):
        from local_deepwiki.core.deep_research.config import CheckpointData
        from local_deepwiki.models import ResearchCheckpointStep

        data = CheckpointData(step=ResearchCheckpointStep.DECOMPOSITION)
        with pytest.raises(FrozenInstanceError):
            data.step = ResearchCheckpointStep.SYNTHESIS  # type: ignore[misc]

    def test_defaults(self):
        from local_deepwiki.core.deep_research.config import CheckpointData
        from local_deepwiki.models import ResearchCheckpointStep

        data = CheckpointData(step=ResearchCheckpointStep.RETRIEVAL)
        assert data.sub_questions is None
        assert data.retrieved_contexts is None
        assert data.follow_up_queries is None
        assert data.follow_up_contexts is None
        assert data.partial_synthesis is None
        assert data.error is None
        assert data.completed_step is None


class TestSynthesisResult:
    def test_frozen(self):
        from local_deepwiki.core.deep_research.config import SynthesisResult

        result = SynthesisResult(
            question="Q?",
            answer="A",
            sub_questions=[],
            all_results=[],
            trace=[],
            llm_calls=2,
        )
        with pytest.raises(FrozenInstanceError):
            result.answer = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ImportEdgeContext
# ---------------------------------------------------------------------------


class TestImportEdgeContext:
    def test_frozen(self):
        from local_deepwiki.generators.analysis.dependency_graph import (
            ImportEdgeContext,
        )

        ctx = ImportEdgeContext(
            file_to_module={},
            internal_modules=set(),
            repo_path="repo",
            show_external=False,
            exclude_tests=True,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.repo_path = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NumpyParserState (mutable by design)
# ---------------------------------------------------------------------------


class TestNumpyParserState:
    def test_mutable(self):
        from local_deepwiki.generators.analysis.api_docs import NumpyParserState

        state = NumpyParserState(
            current_section="description",
            current_param=None,
            args_dict={},
            returns_str=None,
            description_lines=[],
        )
        state.current_section = "args"
        assert state.current_section == "args"


# ---------------------------------------------------------------------------
# TreeTraversalState (mutable by design)
# ---------------------------------------------------------------------------


class TestTreeTraversalState:
    def test_mutable_counter(self):
        from local_deepwiki.generators.dir_tree import TreeTraversalState

        state = TreeTraversalState(max_depth=3, max_items=50, gitignored=set())
        state.items_shown += 1
        assert state.items_shown == 1


# ---------------------------------------------------------------------------
# CodemapStreamRequest
# ---------------------------------------------------------------------------


class TestCodemapStreamRequest:
    def test_frozen(self):
        from local_deepwiki.web.routes_codemap import CodemapStreamRequest

        req = CodemapStreamRequest(
            query="q",
            focus="execution_flow",
            max_depth=5,
            max_nodes=30,
            entry_point=None,
            wiki_path=Path("/tmp"),
            repo_path=Path("/tmp"),
            cache_k="k",
        )
        with pytest.raises(FrozenInstanceError):
            req.query = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IndexerStatusDeps
# ---------------------------------------------------------------------------


class TestIndexerStatusDeps:
    def test_frozen(self):
        from unittest.mock import MagicMock

        from local_deepwiki.core.indexer_status import IndexerStatusDeps

        deps = IndexerStatusDeps(
            status_manager=MagicMock(),
            find_source_files_fn=lambda: [],
            parser=MagicMock(),
            host_module=MagicMock(),
        )
        with pytest.raises(FrozenInstanceError):
            deps.parser = None  # type: ignore[misc]

    def test_ast_cache_default(self):
        from unittest.mock import MagicMock

        from local_deepwiki.core.indexer_status import IndexerStatusDeps

        deps = IndexerStatusDeps(
            status_manager=MagicMock(),
            find_source_files_fn=lambda: [],
            parser=MagicMock(),
            host_module=MagicMock(),
        )
        assert deps.ast_cache is None
