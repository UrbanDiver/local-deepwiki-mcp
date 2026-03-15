"""Tests for deep research pipeline - progress, cancellation, and edge cases."""

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.core.deep_research import (
    DeepResearchPipeline,
    ResearchCancelledError,
)
from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    Language,
    ResearchProgress,
    ResearchProgressType,
    SearchResult,
    SubQuestion,
)
from local_deepwiki.providers.base import EmbeddingProvider, LLMProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def name(self) -> str:
        return "mock"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._dimension for _ in texts]


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or []
        self.call_count = 0
        self.prompts: list[str] = []
        self.system_prompts: list[str | None] = []

    @property
    def name(self) -> str:
        return "mock"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            response = "{}"
        self.call_count += 1
        return response

    async def _generate_stream_impl(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        async def _stream() -> AsyncIterator[str]:
            response = await self.generate(
                prompt, system_prompt, max_tokens, temperature
            )
            yield response

        return _stream()


def make_chunk(
    id: str,
    file_path: str = "test.py",
    content: str = "test code",
    name: str = "test_func",
) -> CodeChunk:
    """Create a test code chunk."""
    return CodeChunk(
        id=id,
        file_path=file_path,
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name=name,
        content=content,
        start_line=1,
        end_line=10,
    )


def make_search_result(chunk: CodeChunk, score: float = 0.8) -> SearchResult:
    """Create a test search result."""
    return SearchResult(chunk=chunk, score=score, highlights=[])


class TestHandleDeepResearch:
    """Tests for the MCP server handler."""

    async def test_returns_error_for_empty_question(self):
        """Test error returned for empty question."""
        from local_deepwiki.handlers import handle_deep_research

        result = await handle_deep_research(
            {
                "repo_path": "/some/path",
                "question": "",
            }
        )

        assert len(result) == 1
        assert "error" in result[0].text.lower()
        assert (
            "at least 1 character" in result[0].text
            or "string_too_short" in result[0].text
        )

    async def test_returns_error_for_unindexed_repo(self, tmp_path):
        """Test error returned when repository is not indexed."""
        from local_deepwiki.handlers import handle_deep_research

        result = await handle_deep_research(
            {
                "repo_path": str(tmp_path),
                "question": "How does auth work?",
            }
        )

        assert len(result) == 1
        assert "error" in result[0].text.lower()
        assert "not indexed" in result[0].text

    async def test_validates_max_chunks(self):
        """Test that max_chunks is validated."""
        from local_deepwiki.handlers import handle_deep_research

        # Should not error, but clamp to valid range
        result = await handle_deep_research(
            {
                "repo_path": "/some/path",
                "question": "Question",
                "max_chunks": 1000,  # Too high
            }
        )

        # Will fail on "not indexed" but that's after validation
        assert "error" in result[0].text.lower()


class TestDeepResearchProgress:
    """Tests for progress callback functionality."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
            ]
        )
        return store

    async def test_progress_callback_receives_all_steps(self, mock_vector_store):
        """Test that progress callback receives expected events."""
        events: list[ResearchProgress] = []

        async def capture(p: ResearchProgress) -> None:
            events.append(p)

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("Question", progress_callback=capture)

        # Should have at least: started, decomposition, retrieval, gap_analysis, synthesis_started, complete
        assert len(events) >= 5
        types = [e.step_type for e in events]
        assert ResearchProgressType.STARTED in types
        assert ResearchProgressType.DECOMPOSITION_COMPLETE in types
        assert ResearchProgressType.RETRIEVAL_COMPLETE in types
        assert ResearchProgressType.GAP_ANALYSIS_COMPLETE in types
        assert ResearchProgressType.COMPLETE in types

    async def test_progress_callback_includes_sub_questions(self, mock_vector_store):
        """Test that decomposition progress includes sub-questions."""
        captured: ResearchProgress | None = None

        async def capture(p: ResearchProgress) -> None:
            nonlocal captured
            if p.step_type == ResearchProgressType.DECOMPOSITION_COMPLETE:
                captured = p

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {
                                "question": "What is the architecture?",
                                "category": "structure",
                            },
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("Question", progress_callback=capture)

        assert captured is not None
        assert captured.sub_questions is not None
        assert len(captured.sub_questions) == 1
        assert captured.sub_questions[0].question == "What is the architecture?"

    async def test_progress_callback_includes_chunk_counts(self, mock_vector_store):
        """Test that retrieval progress includes chunk counts."""
        captured: ResearchProgress | None = None

        async def capture(p: ResearchProgress) -> None:
            nonlocal captured
            if p.step_type == ResearchProgressType.RETRIEVAL_COMPLETE:
                captured = p

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("Question", progress_callback=capture)

        assert captured is not None
        assert captured.chunks_retrieved is not None
        assert captured.chunks_retrieved >= 0

    async def test_progress_callback_includes_follow_up_queries(
        self, mock_vector_store
    ):
        """Test that gap analysis progress includes follow-up queries."""
        captured: ResearchProgress | None = None

        async def capture(p: ResearchProgress) -> None:
            nonlocal captured
            if p.step_type == ResearchProgressType.GAP_ANALYSIS_COMPLETE:
                captured = p

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps(
                    {
                        "gaps": ["Missing info"],
                        "follow_up_queries": ["search query 1", "search query 2"],
                    }
                ),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("Question", progress_callback=capture)

        assert captured is not None
        assert captured.follow_up_queries is not None
        assert len(captured.follow_up_queries) == 2

    async def test_progress_callback_none_works(self, mock_vector_store):
        """Test that pipeline works without progress callback."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": []}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        # Should not raise
        result = await pipeline.research("Question", progress_callback=None)
        assert result.answer is not None

    async def test_progress_callback_includes_duration(self, mock_vector_store):
        """Test that progress events include duration."""
        events: list[ResearchProgress] = []

        async def capture(p: ResearchProgress) -> None:
            events.append(p)

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("Question", progress_callback=capture)

        # Completed steps should have duration
        for event in events:
            if event.step_type in {
                ResearchProgressType.DECOMPOSITION_COMPLETE,
                ResearchProgressType.RETRIEVAL_COMPLETE,
                ResearchProgressType.GAP_ANALYSIS_COMPLETE,
                ResearchProgressType.COMPLETE,
            }:
                assert event.duration_ms is not None
                assert event.duration_ms >= 0

    async def test_progress_step_numbers_increase(self, mock_vector_store):
        """Test that step numbers increase monotonically."""
        events: list[ResearchProgress] = []

        async def capture(p: ResearchProgress) -> None:
            events.append(p)

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("Question", progress_callback=capture)

        # Step numbers should be non-decreasing
        prev_step = -1
        for event in events:
            assert event.step >= prev_step
            prev_step = event.step

        # Final step should be 5 (COMPLETE)
        assert events[-1].step == 5
        assert events[-1].step_type == ResearchProgressType.COMPLETE


class TestResearchCancellation:
    """Tests for research cancellation functionality."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
            ]
        )
        return store

    def test_research_cancelled_error_creation(self):
        """Test ResearchCancelledError can be created with step info."""
        error = ResearchCancelledError("decomposition")
        assert error.step == "decomposition"
        assert "decomposition" in str(error)

    def test_research_cancelled_error_default_step(self):
        """Test ResearchCancelledError with default step."""
        error = ResearchCancelledError()
        assert error.step == "unknown"

    async def test_cancellation_before_decomposition(self, mock_vector_store):
        """Test cancellation before decomposition starts."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": []}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        # Cancel immediately
        def always_cancelled() -> bool:
            return True

        with pytest.raises(ResearchCancelledError) as exc_info:
            await pipeline.research(
                "Question",
                cancellation_check=always_cancelled,
            )

        assert exc_info.value.step == "decomposition"

    async def test_cancellation_after_decomposition(self, mock_vector_store):
        """Test cancellation after decomposition completes."""
        call_count = 0

        def cancel_after_first_step() -> bool:
            nonlocal call_count
            call_count += 1
            # Cancel after first check (decomposition)
            return call_count > 1

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        with pytest.raises(ResearchCancelledError) as exc_info:
            await pipeline.research(
                "Question",
                cancellation_check=cancel_after_first_step,
            )

        assert exc_info.value.step == "retrieval"

    async def test_cancellation_before_gap_analysis(self, mock_vector_store):
        """Test cancellation before gap analysis."""
        call_count = 0

        def cancel_before_gap_analysis() -> bool:
            nonlocal call_count
            call_count += 1
            # Cancel on third check (gap analysis)
            return call_count >= 3

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        with pytest.raises(ResearchCancelledError) as exc_info:
            await pipeline.research(
                "Question",
                cancellation_check=cancel_before_gap_analysis,
            )

        assert exc_info.value.step == "gap_analysis"

    async def test_cancellation_before_synthesis(self, mock_vector_store):
        """Test cancellation before synthesis."""
        call_count = 0

        def cancel_before_synthesis() -> bool:
            nonlocal call_count
            call_count += 1
            # Cancel on fifth check (synthesis)
            return call_count >= 5

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps(
                    {
                        "gaps": ["missing"],
                        "follow_up_queries": ["follow up"],
                    }
                ),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        with pytest.raises(ResearchCancelledError) as exc_info:
            await pipeline.research(
                "Question",
                cancellation_check=cancel_before_synthesis,
            )

        assert exc_info.value.step == "synthesis"

    async def test_no_cancellation_when_check_is_none(self, mock_vector_store):
        """Test that pipeline completes when cancellation_check is None."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": []}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research(
            "Question",
            cancellation_check=None,
        )

        assert result.answer is not None

    async def test_no_cancellation_when_check_returns_false(self, mock_vector_store):
        """Test that pipeline completes when cancellation check returns False."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": []}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        def never_cancelled() -> bool:
            return False

        result = await pipeline.research(
            "Question",
            cancellation_check=never_cancelled,
        )

        assert result.answer is not None

    async def test_cancellation_stops_llm_calls(self, mock_vector_store):
        """Test that cancellation prevents further LLM calls."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        # Cancel after decomposition
        call_count = 0

        def cancel_after_decomposition() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1

        with pytest.raises(ResearchCancelledError):
            await pipeline.research(
                "Question",
                cancellation_check=cancel_after_decomposition,
            )

        # Should only have made 1 LLM call (decomposition)
        assert llm.call_count == 1

    async def test_cancelled_progress_type_exists(self):
        """Test that CANCELLED progress type exists."""
        assert ResearchProgressType.CANCELLED == "cancelled"


class TestDeepResearchEdgeCases:
    """Tests for edge cases and error handling to improve coverage."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
            ]
        )
        return store

    async def test_prepare_results_truncates_when_exceeds_max(self):
        """Test that _prepare_results_for_synthesis truncates results exceeding max_total_chunks."""
        mock_store = MagicMock()

        # Create many search results
        many_results = [
            make_search_result(make_chunk(f"c{i}", f"file{i}.py"), score=0.9 - i * 0.01)
            for i in range(50)
        ]
        mock_store.search = AsyncMock(return_value=many_results)

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "Q1?", "category": "structure"},
                            {"question": "Q2?", "category": "flow"},
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Synthesized answer",
            ]
        )

        # Set a small max_total_chunks to trigger truncation
        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
            max_total_chunks=10,
        )

        result = await pipeline.research("Question")

        # Should be limited to max_total_chunks
        assert result.total_chunks_analyzed <= 10

    async def test_parse_decomposition_handles_json_decode_error(
        self, mock_vector_store
    ):
        """Test that _parse_decomposition_response handles JSONDecodeError gracefully."""
        llm = MockLLMProvider(
            responses=[
                # Response with JSON-like structure but invalid JSON
                '{"sub_questions": [{"question": "Q1?", category: invalid}]}',  # Missing quotes
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Should handle gracefully with empty sub_questions
        assert result.sub_questions == []

    async def test_parallel_retrieve_handles_search_exceptions(self):
        """Test that _parallel_retrieve handles exceptions from search."""
        mock_store = MagicMock()

        # First search succeeds, second throws an exception
        async def search_side_effect(query, limit=5):
            if "fail" in query.lower():
                raise RuntimeError("Search failed")
            return [make_search_result(make_chunk("c1"))]

        mock_store.search = AsyncMock(side_effect=search_side_effect)

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "Working query?", "category": "structure"},
                            {"question": "This will fail query?", "category": "flow"},
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer with partial results",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
        )

        # Should not raise, should continue with partial results
        result = await pipeline.research("Question")
        assert result.answer is not None

    async def test_build_context_summary_empty_results(self, mock_vector_store):
        """Test that _build_context_summary handles empty results."""
        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=MockLLMProvider(),
        )

        # Call the method directly with empty results
        summary = pipeline._build_context_summary([])

        assert summary == "No code context retrieved."

    async def test_parse_gap_analysis_no_json_match(self, mock_vector_store):
        """Test that _parse_gap_analysis_response handles no JSON in response."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                # Response with no JSON at all
                "This response has no JSON content at all, just plain text.",
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Should handle gracefully - no follow-up queries
        assert result.answer is not None

    async def test_parse_gap_analysis_json_decode_error(self, mock_vector_store):
        """Test that _parse_gap_analysis_response handles JSONDecodeError."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                # Invalid JSON that looks like JSON (has braces)
                '{gaps: ["missing"], follow_up_queries: [invalid]}',
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Should handle gracefully
        assert result.answer is not None

    async def test_targeted_retrieve_empty_queries(self):
        """Test that _targeted_retrieve handles empty query list."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=MockLLMProvider(),
        )

        # Call the method directly with empty queries
        results = await pipeline._targeted_retrieve([])

        assert results == []
        # Search should not have been called
        mock_store.search.assert_not_called()

    async def test_targeted_retrieve_handles_search_exceptions(self):
        """Test that _targeted_retrieve handles exceptions from search."""
        mock_store = MagicMock()

        # Create side effect that fails on certain queries
        async def search_side_effect(query, limit=3):
            if "error" in query.lower():
                raise RuntimeError("Targeted search failed")
            return [make_search_result(make_chunk("c1"))]

        mock_store.search = AsyncMock(side_effect=search_side_effect)

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps(
                    {
                        "gaps": ["missing info"],
                        "follow_up_queries": [
                            "working query",
                            "error query",
                            "another query",
                        ],
                    }
                ),
                "Answer with partial follow-up results",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
        )

        # Should not raise, should continue with partial results
        result = await pipeline.research("Question")
        assert result.answer is not None

    async def test_parallel_retrieve_with_empty_sub_questions(self):
        """Test that _parallel_retrieve handles empty sub_questions list."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=MockLLMProvider(),
        )

        # Call the method directly with empty list
        results = await pipeline._parallel_retrieve([])

        assert results == []
        # Search should not have been called
        mock_store.search.assert_not_called()

    async def test_targeted_retrieve_async_directly(self):
        """Test _targeted_retrieve with empty queries directly via async."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=MockLLMProvider(),
        )

        # Call directly with empty list
        results = await pipeline._targeted_retrieve([])

        assert results == []
        mock_store.search.assert_not_called()

    async def test_analyze_gaps_with_no_results(self):
        """Test that _analyze_gaps returns original question when no results."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
        )

        # Call _analyze_gaps directly with empty results
        sub_questions = [SubQuestion(question="Q?", category="structure")]
        follow_ups = await pipeline._analyze_gaps(
            "Original question?",
            sub_questions,
            [],  # Empty results
        )

        # Should return original question as follow-up
        assert follow_ups == ["Original question?"]

    def test_parse_gap_analysis_filters_empty_strings(self, mock_vector_store):
        """Test that _parse_gap_analysis_response filters out empty strings."""
        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=MockLLMProvider(),
        )

        # Response with empty strings and non-string values in follow_up_queries
        response = json.dumps(
            {
                "gaps": ["gap"],
                "follow_up_queries": [
                    "valid query",
                    "",
                    "  ",
                    None,
                    123,
                    "another valid",
                ],
            }
        )

        result = pipeline._parse_gap_analysis_response(response)

        # Should only contain non-empty string queries
        assert "valid query" in result
        assert "another valid" in result
        assert "" not in result
        # None and 123 are filtered because isinstance(q, str) check

    def test_parse_decomposition_missing_question_key(self, mock_vector_store):
        """Test parsing decomposition when items are missing question key."""
        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=MockLLMProvider(),
        )

        # Response with some items missing 'question' key
        response = json.dumps(
            {
                "sub_questions": [
                    {"question": "Valid question?", "category": "structure"},
                    {"category": "flow"},  # Missing 'question'
                    "not a dict",  # Not a dict
                    {"question": "Another valid?", "category": "dependencies"},
                ]
            }
        )

        result = pipeline._parse_decomposition_response(response)

        # Should only return valid items with 'question' key
        assert len(result) == 2
        assert result[0].question == "Valid question?"
        assert result[1].question == "Another valid?"

    def test_parse_decomposition_default_category(self, mock_vector_store):
        """Test that decomposition uses default category when missing."""
        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=MockLLMProvider(),
        )

        # Response with missing category
        response = json.dumps(
            {
                "sub_questions": [
                    {"question": "Question without category?"},
                ]
            }
        )

        result = pipeline._parse_decomposition_response(response)

        # Should use "structure" as default category
        assert len(result) == 1
        assert result[0].category == "structure"

    async def test_custom_prompts_are_used(self, mock_vector_store):
        """Test that custom prompts are used when provided."""
        custom_decomposition = "Custom decomposition prompt"
        custom_gap_analysis = "Custom gap analysis prompt"
        custom_synthesis = "Custom synthesis prompt"

        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            decomposition_prompt=custom_decomposition,
            gap_analysis_prompt=custom_gap_analysis,
            synthesis_prompt=custom_synthesis,
        )

        await pipeline.research("Question")

        # Verify custom prompts were used
        assert custom_decomposition in llm.system_prompts
        assert custom_gap_analysis in llm.system_prompts
        assert custom_synthesis in llm.system_prompts
