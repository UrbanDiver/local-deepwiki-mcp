"""Tests for handler research and export operations - deep research, PDF export, checkpoints."""

import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.handlers import (
    handle_cancel_research,
    handle_deep_research,
    handle_export_wiki_pdf,
    handle_list_research_checkpoints,
    handle_resume_research,
)
from local_deepwiki.handlers.research import (
    _DeepResearchContext,
    _create_progress_callbacks,
    _handle_deep_research_impl,
)


class TestHandleDeepResearch:
    """Tests for handle_deep_research handler."""

    async def test_returns_error_for_empty_question(self):
        """Test error returned for empty question."""
        result = await handle_deep_research(
            {
                "repo_path": "/some/path",
                "question": "",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        # Pydantic validates min_length=1
        assert (
            "at least 1 character" in result[0].text
            or "string_too_short" in result[0].text
        )

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        result = await handle_deep_research(
            {
                "repo_path": str(tmp_path),
                "question": "What is the architecture?",
            }
        )

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "not indexed" in result[0].text

    async def test_rejects_max_chunks_out_of_range(self, tmp_path):
        """Test that max_chunks out of valid range is rejected."""
        result = await handle_deep_research(
            {
                "repo_path": str(tmp_path),
                "question": "Test question",
                "max_chunks": 10000,  # Above max (50), should be rejected
            }
        )

        # Pydantic now rejects out-of-range values instead of clamping
        assert "Error" in result[0].text
        assert "less_than_equal" in result[0].text or "50" in result[0].text

    async def test_handles_cancelled_error(self, tmp_path):
        """Test that CancelledError is propagated."""

        async def mock_research(*args, **kwargs):
            raise asyncio.CancelledError()

        with patch(
            "local_deepwiki.handlers.research._handle_deep_research_impl",
            side_effect=asyncio.CancelledError(),
        ):
            with pytest.raises(asyncio.CancelledError):
                await handle_deep_research(
                    {
                        "repo_path": str(tmp_path),
                        "question": "Test question",
                    }
                )


class TestHandleDeepResearchErrorHandling:
    """Tests for handle_deep_research error handling paths."""

    async def test_handles_generic_exception(self, tmp_path):
        """Test that generic exceptions are caught and returned as errors."""
        with patch(
            "local_deepwiki.handlers.research._handle_deep_research_impl",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await handle_deep_research(
                {
                    "repo_path": str(tmp_path),
                    "question": "Test question",
                }
            )

            assert len(result) == 1
            assert "Error" in result[0].text
            assert "Unexpected error" in result[0].text


class TestHandleDeepResearchImpl:
    """Tests for _handle_deep_research_impl implementation."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="Test answer")
        return mock

    async def test_successful_research(self, tmp_path):
        """Test successful deep research execution."""
        # Create vector db path
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze gaps",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            # Create mock research result with proper types
                            mock_result = SimpleNamespace(
                                question="Test question",
                                answer="Test answer",
                                sub_questions=[
                                    SimpleNamespace(
                                        question="Sub Q1", category="architecture"
                                    ),
                                ],
                                sources=[
                                    SimpleNamespace(
                                        file_path="test.py",
                                        start_line=1,
                                        end_line=10,
                                        chunk_type="function",
                                        name="test_func",
                                        relevance_score=0.9,
                                    ),
                                ],
                                reasoning_trace=[
                                    SimpleNamespace(
                                        step_type=SimpleNamespace(
                                            value="decomposition"
                                        ),
                                        description="Breaking down question",
                                        duration_ms=100,
                                    ),
                                ],
                                total_chunks_analyzed=10,
                                total_llm_calls=3,
                            )

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "What is the architecture?",
                                }
                            )

                            assert len(result) == 1
                            data = json.loads(result[0].text)
                            assert data["question"] == "Test question"
                            assert data["answer"] == "Test answer"
                            assert len(data["sub_questions"]) == 1
                            assert len(data["sources"]) == 1
                            assert data["stats"]["chunks_analyzed"] == 10

    async def test_research_with_preset(self, tmp_path):
        """Test deep research with preset parameter."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=5,
                chunks_per_subquestion=10,
                max_total_chunks=50,
                max_follow_up_queries=3,
                synthesis_temperature=0.5,
                synthesis_max_tokens=4000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                    "preset": "thorough",
                                }
                            )

                            # Verify preset was passed to config
                            config.deep_research.with_preset.assert_called_with(
                                "thorough"
                            )
                            assert len(result) == 1

    async def test_research_cancelled_error(self, tmp_path):
        """Test handling of ResearchCancelledError."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            from local_deepwiki.core.deep_research import (
                                ResearchCancelledError,
                            )

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(
                                side_effect=ResearchCancelledError("synthesis")
                            )
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                }
                            )

                            assert len(result) == 1
                            data = json.loads(result[0].text)
                            assert data["status"] == "cancelled"
                            assert "synthesis" in data["message"]

    async def test_research_asyncio_cancelled_error(self, tmp_path):
        """Test handling of asyncio.CancelledError."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(
                                side_effect=asyncio.CancelledError()
                            )
                            mock_pipeline_class.return_value = mock_pipeline

                            with pytest.raises(asyncio.CancelledError):
                                await _handle_deep_research_impl(
                                    {
                                        "repo_path": str(tmp_path),
                                        "question": "Test question",
                                    }
                                )

    async def test_progress_callback_with_server(self, tmp_path):
        """Test progress callback sends notifications with server."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        # Create mock server with request context
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock()
        mock_server.request_context = mock_ctx

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            async def mock_research(
                                question,
                                progress_callback=None,
                                cancellation_check=None,
                                resume_id=None,
                                cancellation_event=None,
                            ):
                                # Call progress callback to test notification sending
                                if progress_callback:
                                    from local_deepwiki.models import (
                                        ResearchProgress,
                                        ResearchProgressType,
                                    )

                                    await progress_callback(
                                        ResearchProgress(
                                            step=1,
                                            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
                                            message="Decomposing question",
                                        )
                                    )
                                return mock_result

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = mock_research
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                },
                                server=mock_server,
                            )

                            assert len(result) == 1

    async def test_progress_callback_without_server(self, tmp_path):
        """Test progress callback handles missing server gracefully."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            async def mock_research(
                                question,
                                progress_callback=None,
                                cancellation_check=None,
                                resume_id=None,
                                cancellation_event=None,
                            ):
                                if progress_callback:
                                    from local_deepwiki.models import (
                                        ResearchProgress,
                                        ResearchProgressType,
                                    )

                                    # This should not raise even without server
                                    await progress_callback(
                                        ResearchProgress(
                                            step=1,
                                            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
                                            message="Decomposing",
                                        )
                                    )
                                return mock_result

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = mock_research
                            mock_pipeline_class.return_value = mock_pipeline

                            # Call without server - should not raise
                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                }
                            )

                            assert len(result) == 1

    async def test_server_without_progress_token(self, tmp_path):
        """Test handling server without progress token in request context."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        # Create mock server with request context but no progress token
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta = None  # No meta
        mock_server.request_context = mock_ctx

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                },
                                server=mock_server,
                            )

                            assert len(result) == 1

    async def test_server_lookup_error(self, tmp_path):
        """Test handling LookupError when accessing request context."""
        vector_path = tmp_path / ".deepwiki" / "vectors"
        vector_path.mkdir(parents=True)

        # Create mock server that raises LookupError on request_context access
        mock_server = MagicMock()
        type(mock_server).request_context = property(
            lambda self: (_ for _ in ()).throw(LookupError("Not in request context"))
        )

        with patch("local_deepwiki.handlers.research.get_config") as mock_config:
            config = MagicMock()
            config.get_vector_db_path.return_value = vector_path
            config.get_wiki_path.return_value = tmp_path / ".deepwiki"
            config.embedding = MagicMock()
            config.llm_cache = MagicMock()
            config.llm = MagicMock()
            config.deep_research.with_preset.return_value = MagicMock(
                max_sub_questions=3,
                chunks_per_subquestion=5,
                max_total_chunks=20,
                max_follow_up_queries=2,
                synthesis_temperature=0.7,
                synthesis_max_tokens=2000,
            )
            config.get_prompts.return_value = MagicMock(
                research_decomposition="decompose",
                research_gap_analysis="analyze",
                research_synthesis="synthesize",
            )
            mock_config.return_value = config

            with patch("local_deepwiki.handlers.research.get_embedding_provider"):
                with patch("local_deepwiki.handlers.research.VectorStore"):
                    with patch("local_deepwiki.providers.llm.get_cached_llm_provider"):
                        with patch(
                            "local_deepwiki.core.deep_research.DeepResearchPipeline"
                        ) as mock_pipeline_class:
                            mock_result = MagicMock()
                            mock_result.question = "Test"
                            mock_result.answer = "Answer"
                            mock_result.sub_questions = []
                            mock_result.sources = []
                            mock_result.reasoning_trace = []
                            mock_result.total_chunks_analyzed = 5
                            mock_result.total_llm_calls = 2

                            mock_pipeline = MagicMock()
                            mock_pipeline.research = AsyncMock(return_value=mock_result)
                            mock_pipeline_class.return_value = mock_pipeline

                            # Should not raise
                            result = await _handle_deep_research_impl(
                                {
                                    "repo_path": str(tmp_path),
                                    "question": "Test question",
                                },
                                server=mock_server,
                            )

                            assert len(result) == 1


class TestCancellationAndProgressCallbacks:
    """Tests for _create_progress_callbacks and cancellation handling."""

    async def test_is_cancelled_returns_true_when_event_set(self, tmp_path):
        """Test is_cancelled returns True when cancellation_event is set."""
        # Create a context with the cancellation event set
        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=None,
        )
        ctx.cancellation_event.set()  # Set the cancellation event

        is_cancelled, _, _ = _create_progress_callbacks(ctx)

        # Should return True because event is set
        assert is_cancelled() is True

    async def test_is_cancelled_returns_false_when_not_cancelled(self, tmp_path):
        """Test is_cancelled returns False when nothing is cancelled."""
        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=None,
        )

        is_cancelled, _, _ = _create_progress_callbacks(ctx)

        # Should return False - neither event set nor task cancelled
        assert is_cancelled() is False

    async def test_is_cancelled_checks_task_cancelled_state(self, tmp_path):
        """Test is_cancelled checks asyncio task cancelled state."""
        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=None,
        )

        is_cancelled, _, _ = _create_progress_callbacks(ctx)

        # Create a task and cancel it to test the task.cancelled() branch
        async def check_cancelled():
            # Get current task and check if is_cancelled sees it
            task = asyncio.current_task()
            # Without cancellation, should return False
            return is_cancelled()

        result = await check_cancelled()
        assert result is False

    async def test_is_cancelled_returns_true_when_task_cancelled(self, tmp_path):
        """Test is_cancelled returns True when current task is cancelled."""
        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=None,
        )

        is_cancelled, _, _ = _create_progress_callbacks(ctx)

        # Mock asyncio.current_task to return a cancelled task
        mock_task = MagicMock()
        mock_task.cancelled.return_value = True

        with patch("asyncio.current_task", return_value=mock_task):
            result = is_cancelled()

        assert result is True

    async def test_is_cancelled_handles_runtime_error(self, tmp_path):
        """Test is_cancelled handles RuntimeError from asyncio.current_task()."""
        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=None,
        )

        is_cancelled, _, _ = _create_progress_callbacks(ctx)

        # Mock asyncio.current_task to raise RuntimeError
        with patch(
            "asyncio.current_task", side_effect=RuntimeError("No running event loop")
        ):
            result = is_cancelled()

        # Should return False, not raise
        assert result is False

    async def test_progress_callback_handles_runtime_error(self, tmp_path):
        """Test progress_callback logs warning on RuntimeError."""
        from local_deepwiki.models import ResearchProgress, ResearchProgressType

        # Create mock server that raises RuntimeError
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock(
            side_effect=RuntimeError("Session closed")
        )
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, progress_callback, _ = _create_progress_callbacks(ctx)

        # Should not raise, just log warning
        progress = ResearchProgress(
            step=1,
            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
            message="Test progress",
        )
        await progress_callback(progress)  # Should not raise

    async def test_progress_callback_handles_os_error(self, tmp_path):
        """Test progress_callback logs warning on OSError."""
        from local_deepwiki.models import ResearchProgress, ResearchProgressType

        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock(
            side_effect=OSError("Network error")
        )
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, progress_callback, _ = _create_progress_callbacks(ctx)

        progress = ResearchProgress(
            step=1,
            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
            message="Test progress",
        )
        await progress_callback(progress)  # Should not raise

    async def test_progress_callback_handles_attribute_error(self, tmp_path):
        """Test progress_callback logs warning on AttributeError."""
        from local_deepwiki.models import ResearchProgress, ResearchProgressType

        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock(
            side_effect=AttributeError("Missing attribute")
        )
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, progress_callback, _ = _create_progress_callbacks(ctx)

        progress = ResearchProgress(
            step=1,
            step_type=ResearchProgressType.DECOMPOSITION_COMPLETE,
            message="Test progress",
        )
        await progress_callback(progress)  # Should not raise

    async def test_send_cancellation_notification_sends_notification(self, tmp_path):
        """Test send_cancellation_notification sends proper notification."""
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock()
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, _, send_cancellation_notification = _create_progress_callbacks(ctx)

        await send_cancellation_notification("synthesis")

        # Verify notification was sent
        mock_ctx.session.send_progress_notification.assert_called_once()
        call_kwargs = mock_ctx.session.send_progress_notification.call_args[1]
        assert call_kwargs["progress_token"] == "test-token"
        assert call_kwargs["progress"] == 0.0
        assert call_kwargs["total"] == 5.0
        assert "cancelled" in call_kwargs["message"].lower()

    async def test_send_cancellation_notification_skips_without_token(self, tmp_path):
        """Test send_cancellation_notification does nothing without progress token."""
        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=None,
        )
        # progress_token is None by default

        _, _, send_cancellation_notification = _create_progress_callbacks(ctx)

        # Should complete without error, doing nothing
        await send_cancellation_notification("test_step")

    async def test_send_cancellation_notification_handles_runtime_error(self, tmp_path):
        """Test send_cancellation_notification logs warning on RuntimeError."""
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock(
            side_effect=RuntimeError("Session closed")
        )
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, _, send_cancellation_notification = _create_progress_callbacks(ctx)

        # Should not raise, just log warning
        await send_cancellation_notification("synthesis")

    async def test_send_cancellation_notification_handles_os_error(self, tmp_path):
        """Test send_cancellation_notification logs warning on OSError."""
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock(
            side_effect=OSError("Network error")
        )
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, _, send_cancellation_notification = _create_progress_callbacks(ctx)

        await send_cancellation_notification("synthesis")

    async def test_send_cancellation_notification_handles_attribute_error(
        self, tmp_path
    ):
        """Test send_cancellation_notification logs warning on AttributeError."""
        mock_server = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.meta.progressToken = "test-token"
        mock_ctx.session.send_progress_notification = AsyncMock(
            side_effect=AttributeError("Missing attribute")
        )
        mock_server.request_context = mock_ctx

        ctx = _DeepResearchContext(
            repo_path=tmp_path,
            question="Test question",
            max_chunks=20,
            preset=None,
            server=mock_server,
        )
        ctx.progress_token = "test-token"

        _, _, send_cancellation_notification = _create_progress_callbacks(ctx)

        await send_cancellation_notification("synthesis")


class TestHandleExportWikiPdf:
    """Tests for handle_export_wiki_pdf handler."""

    async def test_returns_error_for_nonexistent_wiki(self, tmp_path):
        """Test error returned for non-existent wiki path."""
        nonexistent = tmp_path / "does_not_exist"

        # Mock the pdf module before import
        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Success")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf({"wiki_path": str(nonexistent)})

        assert len(result) == 1
        assert "Error" in result[0].text
        assert "does not exist" in result[0].text

    async def test_exports_single_file_pdf(self, tmp_path):
        """Test exporting wiki to single PDF file."""
        # Create minimal wiki
        (tmp_path / "index.md").write_text("# Test Wiki")

        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Exported successfully")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                    "single_file": True,
                }
            )

            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            assert data["message"] == "Exported successfully"
            # Default output should be wiki_name.pdf
            assert data["output_path"].endswith(".pdf")

    async def test_exports_multiple_pdfs(self, tmp_path):
        """Test exporting wiki to multiple PDF files."""
        (tmp_path / "index.md").write_text("# Test Wiki")

        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(return_value="Exported 5 pages")

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                    "single_file": False,
                }
            )

            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            # Multiple files output should be wiki_name_pdfs directory
            assert data["output_path"].endswith("_pdfs")

    async def test_exports_with_custom_output_path(self, tmp_path):
        """Test exporting wiki to custom output path."""
        (tmp_path / "index.md").write_text("# Test Wiki")
        output_path = tmp_path / "custom_output.pdf"

        mock_pdf_module = MagicMock()
        mock_pdf_module.export_to_pdf = MagicMock(
            return_value="Exported to custom path"
        )

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            result = await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                    "output_path": str(output_path),
                }
            )

            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            assert str(output_path) in data["output_path"]

    async def test_default_single_file_true(self, tmp_path):
        """Test that single_file defaults to True."""
        (tmp_path / "index.md").write_text("# Test Wiki")

        mock_pdf_module = MagicMock()
        mock_export = MagicMock(return_value="Success")
        mock_pdf_module.export_to_pdf = mock_export

        with patch.dict(sys.modules, {"local_deepwiki.export.pdf": mock_pdf_module}):
            await handle_export_wiki_pdf(
                {
                    "wiki_path": str(tmp_path),
                }
            )

            # Verify export_to_pdf was called with single_file=True
            mock_export.assert_called_once()
            call_kwargs = mock_export.call_args[1]
            assert call_kwargs["single_file"] is True


class TestHandleListResearchCheckpoints:
    """Tests for handle_list_research_checkpoints handler."""

    async def test_returns_error_for_nonexistent_path(self):
        """Test that handler returns error for nonexistent path."""
        result = await handle_list_research_checkpoints(
            {"repo_path": "/nonexistent/path"}
        )
        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_returns_empty_list_when_no_checkpoints(self, tmp_path):
        """Test listing checkpoints when none exist."""
        result = await handle_list_research_checkpoints({"repo_path": str(tmp_path)})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["checkpoints"] == []

    async def test_returns_checkpoints_list(self, tmp_path):
        """Test listing existing checkpoints."""
        from local_deepwiki.core.deep_research import CheckpointManager
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep

        # Create a checkpoint
        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="test-list-123",
            question="Test question for listing",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            completed_steps=["decomposition"],
        )
        manager.save_checkpoint(checkpoint)

        result = await handle_list_research_checkpoints({"repo_path": str(tmp_path)})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["checkpoint_count"] == 1
        assert data["checkpoints"][0]["research_id"] == "test-list-123"
        assert data["checkpoints"][0]["can_resume"] is True


class TestHandleCancelResearch:
    """Tests for handle_cancel_research handler."""

    async def test_returns_error_for_nonexistent_path(self):
        """Test that handler returns error for nonexistent path."""
        result = await handle_cancel_research(
            {"repo_path": "/nonexistent/path", "research_id": "test-123"}
        )
        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_returns_error_for_nonexistent_checkpoint(self, tmp_path):
        """Test cancelling a checkpoint that doesn't exist."""
        result = await handle_cancel_research(
            {"repo_path": str(tmp_path), "research_id": "nonexistent-id"}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "not found" in data["message"]

    async def test_cancels_existing_checkpoint(self, tmp_path):
        """Test successfully cancelling an existing checkpoint."""
        from local_deepwiki.core.deep_research import CheckpointManager
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep

        # Create a checkpoint
        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="cancel-test-123",
            question="Test question",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            completed_steps=["decomposition"],
        )
        manager.save_checkpoint(checkpoint)

        result = await handle_cancel_research(
            {"repo_path": str(tmp_path), "research_id": "cancel-test-123"}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "checkpoint" in data["message"]

        # Verify checkpoint is now cancelled
        updated = manager.load_checkpoint("cancel-test-123")
        assert updated.current_step == ResearchCheckpointStep.CANCELLED


class TestHandleResumeResearch:
    """Tests for handle_resume_research handler."""

    async def test_returns_error_for_nonexistent_path(self):
        """Test that handler returns error for nonexistent path."""
        result = await handle_resume_research(
            {"repo_path": "/nonexistent/path", "research_id": "test-123"}
        )
        assert len(result) == 1
        assert "Error" in result[0].text

    async def test_returns_error_for_nonexistent_checkpoint(self, tmp_path):
        """Test resuming a checkpoint that doesn't exist."""
        result = await handle_resume_research(
            {"repo_path": str(tmp_path), "research_id": "nonexistent-id"}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "not found" in data["message"]

    async def test_returns_error_for_complete_checkpoint(self, tmp_path):
        """Test resuming a checkpoint that is already complete."""
        from local_deepwiki.core.deep_research import CheckpointManager
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep

        # Create a complete checkpoint
        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="complete-test-123",
            question="Test question",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.COMPLETE,
            completed_steps=["decomposition", "retrieval", "gap_analysis", "synthesis"],
        )
        manager.save_checkpoint(checkpoint)

        result = await handle_resume_research(
            {"repo_path": str(tmp_path), "research_id": "complete-test-123"}
        )
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "already complete" in data["message"]
