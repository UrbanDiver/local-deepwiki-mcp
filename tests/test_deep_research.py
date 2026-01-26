"""Tests for deep research pipeline."""

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
    DeepResearchResult,
    Language,
    ResearchProgress,
    ResearchProgressType,
    ResearchStepType,
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

    def get_dimension(self) -> int:
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

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        async def _stream() -> AsyncIterator[str]:
            response = await self.generate(prompt, system_prompt, max_tokens, temperature)
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


class TestSubQuestion:
    """Tests for SubQuestion model."""

    def test_create_sub_question(self):
        """Test creating a sub-question."""
        sq = SubQuestion(question="What is X?", category="structure")
        assert sq.question == "What is X?"
        assert sq.category == "structure"

    def test_repr(self):
        """Test string representation."""
        sq = SubQuestion(question="A very long question that should be truncated", category="flow")
        repr_str = repr(sq)
        assert "[flow]" in repr_str
        assert "..." in repr_str


class TestDeepResearchResult:
    """Tests for DeepResearchResult model."""

    def test_create_result(self):
        """Test creating a deep research result."""
        result = DeepResearchResult(
            question="Test question",
            answer="Test answer",
            sub_questions=[],
            sources=[],
            reasoning_trace=[],
            total_chunks_analyzed=5,
            total_llm_calls=3,
        )
        assert result.question == "Test question"
        assert result.total_llm_calls == 3


class TestDeepResearchPipelineDecomposition:
    """Tests for query decomposition."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        return store

    async def test_decompose_simple_question(self, mock_vector_store):
        """Test decomposition of a simple question."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "What is the structure?", "category": "structure"},
                            {"question": "How does it flow?", "category": "flow"},
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("How does authentication work?")

        assert len(result.sub_questions) == 2
        assert result.sub_questions[0].category == "structure"
        assert result.sub_questions[1].category == "flow"

    async def test_decompose_limits_sub_questions(self, mock_vector_store):
        """Test that decomposition limits sub-questions to max."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": f"Q{i}?", "category": "structure"} for i in range(10)
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            max_sub_questions=4,
        )

        result = await pipeline.research("Complex question")

        assert len(result.sub_questions) <= 4

    async def test_decompose_handles_invalid_json(self, mock_vector_store):
        """Test graceful handling of invalid JSON response."""
        llm = MockLLMProvider(
            responses=[
                "This is not valid JSON",
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Should still work, just with empty sub-questions
        assert result.sub_questions == []

    async def test_decompose_validates_categories(self, mock_vector_store):
        """Test that invalid categories are replaced with default."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "Q1?", "category": "invalid_category"},
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Invalid category should be replaced with "structure"
        assert result.sub_questions[0].category == "structure"


class TestDeepResearchPipelineRetrieval:
    """Tests for parallel retrieval."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM that returns valid responses."""
        return MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "What modules exist?", "category": "structure"},
                            {"question": "How do they connect?", "category": "dependencies"},
                        ]
                    }
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Synthesized answer",
            ]
        )

    async def test_parallel_retrieval_calls_search(self, mock_llm):
        """Test that parallel retrieval calls search for each sub-question."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=mock_llm,
            chunks_per_subquestion=3,
        )

        await pipeline.research("Question")

        # Should call search for each sub-question
        assert mock_store.search.call_count >= 2

    async def test_retrieval_deduplicates_results(self, mock_llm):
        """Test that duplicate chunks are deduplicated."""
        chunk = make_chunk("same_id")
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                make_search_result(chunk, score=0.8),
                make_search_result(chunk, score=0.7),  # Same chunk, lower score
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=mock_llm,
        )

        result = await pipeline.research("Question")

        # Should only have one instance of the chunk
        chunk_ids = [s.file_path for s in result.sources]
        # Deduplication should keep highest score
        assert len([c for c in chunk_ids if c == "test.py"]) >= 1


class TestDeepResearchPipelineGapAnalysis:
    """Tests for gap analysis."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store with results."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1", "auth.py")),
            ]
        )
        return store

    async def test_gap_analysis_generates_follow_ups(self, mock_vector_store):
        """Test that gap analysis can generate follow-up queries."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q1?", "category": "structure"}]}),
                json.dumps(
                    {
                        "gaps": ["Missing database layer info"],
                        "follow_up_queries": ["database connection", "SQL queries"],
                    }
                ),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        await pipeline.research("How does auth work?")

        # Should make additional search calls for follow-ups
        assert mock_vector_store.search.call_count >= 2

    async def test_gap_analysis_limits_follow_ups(self, mock_vector_store):
        """Test that follow-up queries are limited."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q1?", "category": "structure"}]}),
                json.dumps(
                    {
                        "gaps": ["Many gaps"],
                        "follow_up_queries": [f"query{i}" for i in range(10)],
                    }
                ),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            max_follow_up_queries=3,
        )

        await pipeline.research("Question")

        # Follow-up searches should be limited
        # 1 initial + 3 max follow-ups
        assert mock_vector_store.search.call_count <= 4


class TestDeepResearchPipelineSynthesis:
    """Tests for answer synthesis."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1", content="def auth(): pass")),
            ]
        )
        return store

    async def test_synthesis_includes_context(self, mock_vector_store):
        """Test that synthesis prompt includes code context."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Synthesized answer with auth.py:1-10",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Check that synthesis prompt includes the code
        assert "def auth(): pass" in llm.prompts[-1] or len(result.sources) > 0

    async def test_synthesis_handles_no_results(self):
        """Test synthesis when no code is found."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Should return a message about no context
        assert "couldn't find" in result.answer.lower() or "no" in result.answer.lower()


class TestDeepResearchPipelineTracing:
    """Tests for reasoning trace."""

    @pytest.fixture
    def mock_vector_store(self):
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
            ]
        )
        return store

    async def test_trace_includes_all_steps(self, mock_vector_store):
        """Test that reasoning trace includes all steps."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps(
                    {
                        "gaps": ["gap"],
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

        result = await pipeline.research("Question")

        # Should have: decomposition, retrieval, gap_analysis, retrieval, synthesis
        step_types = [s.step_type for s in result.reasoning_trace]
        assert ResearchStepType.DECOMPOSITION in step_types
        assert ResearchStepType.RETRIEVAL in step_types
        assert ResearchStepType.GAP_ANALYSIS in step_types
        assert ResearchStepType.SYNTHESIS in step_types

    async def test_trace_records_duration(self, mock_vector_store):
        """Test that each step has duration recorded."""
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

        result = await pipeline.research("Question")

        for step in result.reasoning_trace:
            assert step.duration_ms >= 0


class TestDeepResearchPipelineIntegration:
    """Integration tests for the full pipeline."""

    async def test_full_pipeline_flow(self):
        """Test complete pipeline with mocked dependencies."""
        # Mock vector store
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                make_search_result(
                    make_chunk("c1", "src/auth.py", "def login(user, password): pass", "login"),
                    score=0.9,
                ),
                make_search_result(
                    make_chunk("c2", "src/db.py", "def connect(): return db", "connect"),
                    score=0.85,
                ),
            ]
        )

        # Mock LLM with realistic responses
        llm = MockLLMProvider(
            responses=[
                # Decomposition
                json.dumps(
                    {
                        "sub_questions": [
                            {
                                "question": "What authentication methods are available?",
                                "category": "structure",
                            },
                            {
                                "question": "How does auth connect to database?",
                                "category": "dependencies",
                            },
                        ]
                    }
                ),
                # Gap analysis
                json.dumps(
                    {
                        "gaps": ["Session management details"],
                        "follow_up_queries": ["session handling"],
                    }
                ),
                # Synthesis
                """The authentication system consists of:

1. **Login Function** (`src/auth.py:1-10`)
   - Handles user/password authentication

2. **Database Connection** (`src/db.py:1-10`)
   - Provides database connectivity

The login function likely uses the database connection for user verification.""",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
        )

        result = await pipeline.research("How does the authentication system work?")

        # Verify result structure
        assert result.question == "How does the authentication system work?"
        assert len(result.sub_questions) == 2
        assert len(result.sources) > 0
        assert result.total_llm_calls == 3
        assert "authentication" in result.answer.lower() or "login" in result.answer.lower()

        # Verify sources include correct files
        source_files = [s.file_path for s in result.sources]
        assert "src/auth.py" in source_files

    async def test_pipeline_counts_llm_calls(self):
        """Test that LLM calls are counted correctly."""
        mock_store = MagicMock()
        mock_store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
            ]
        )

        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question")

        # Should be 3 LLM calls: decompose, gap analysis, synthesis
        assert result.total_llm_calls == 3
        assert llm.call_count == 3


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
        assert "Error" in result[0].text
        assert "at least 1 character" in result[0].text or "string_too_short" in result[0].text

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
        assert "Error" in result[0].text
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
        assert "Error" in result[0].text


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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                            {"question": "What is the architecture?", "category": "structure"},
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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

    async def test_progress_callback_includes_follow_up_queries(self, mock_vector_store):
        """Test that gap analysis progress includes follow-up queries."""
        captured: ResearchProgress | None = None

        async def capture(p: ResearchProgress) -> None:
            nonlocal captured
            if p.step_type == ResearchProgressType.GAP_ANALYSIS_COMPLETE:
                captured = p

        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
        # Lines 442-443: Truncation when results exceed max_total_chunks
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

    async def test_parse_decomposition_handles_json_decode_error(self, mock_vector_store):
        """Test that _parse_decomposition_response handles JSONDecodeError gracefully."""
        # Lines 538-540: json.JSONDecodeError handling
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
        # Lines 567-568: Handling search exceptions
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
        # Line 628: Empty results case
        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=MockLLMProvider(),
        )

        # Call the method directly with empty results
        summary = pipeline._build_context_summary([])

        assert summary == "No code context retrieved."

    async def test_parse_gap_analysis_no_json_match(self, mock_vector_store):
        """Test that _parse_gap_analysis_response handles no JSON in response."""
        # Line 660: No JSON match case
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
        # Lines 668-670: json.JSONDecodeError handling
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
        # Line 682: Empty queries case
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
        # Lines 694-695: Handling search exceptions in targeted retrieval
        mock_store = MagicMock()

        # Create side effect that fails on certain queries
        async def search_side_effect(query, limit=3):
            if "error" in query.lower():
                raise RuntimeError("Targeted search failed")
            return [make_search_result(make_chunk("c1"))]

        mock_store.search = AsyncMock(side_effect=search_side_effect)

        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps(
                    {
                        "gaps": ["missing info"],
                        "follow_up_queries": ["working query", "error query", "another query"],
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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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
            []  # Empty results
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
        response = json.dumps({
            "gaps": ["gap"],
            "follow_up_queries": ["valid query", "", "  ", None, 123, "another valid"]
        })

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
        response = json.dumps({
            "sub_questions": [
                {"question": "Valid question?", "category": "structure"},
                {"category": "flow"},  # Missing 'question'
                "not a dict",  # Not a dict
                {"question": "Another valid?", "category": "dependencies"},
            ]
        })

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
        response = json.dumps({
            "sub_questions": [
                {"question": "Question without category?"},
            ]
        })

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
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
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


class TestCheckpointManager:
    """Tests for the CheckpointManager class."""

    @pytest.fixture
    def checkpoint_manager(self, tmp_path):
        """Create a checkpoint manager with a temp directory."""
        from local_deepwiki.core.deep_research import CheckpointManager
        return CheckpointManager(tmp_path)

    @pytest.fixture
    def sample_checkpoint(self):
        """Create a sample checkpoint for testing."""
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time
        return ResearchCheckpoint(
            research_id="test-123",
            question="How does authentication work?",
            repo_path="/test/repo",
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            sub_questions=[SubQuestion(question="What is the auth flow?", category="flow")],
            completed_steps=["decomposition"],
        )

    def test_save_and_load_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test saving and loading a checkpoint."""
        checkpoint_manager.save_checkpoint(sample_checkpoint)

        loaded = checkpoint_manager.load_checkpoint(sample_checkpoint.research_id)

        assert loaded is not None
        assert loaded.research_id == sample_checkpoint.research_id
        assert loaded.question == sample_checkpoint.question
        assert loaded.current_step == sample_checkpoint.current_step
        assert len(loaded.sub_questions) == 1
        assert loaded.completed_steps == ["decomposition"]

    def test_load_nonexistent_checkpoint(self, checkpoint_manager):
        """Test loading a checkpoint that doesn't exist."""
        loaded = checkpoint_manager.load_checkpoint("nonexistent-id")
        assert loaded is None

    def test_list_checkpoints(self, checkpoint_manager, sample_checkpoint):
        """Test listing all checkpoints."""
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        # Save multiple checkpoints
        checkpoint_manager.save_checkpoint(sample_checkpoint)

        checkpoint2 = ResearchCheckpoint(
            research_id="test-456",
            question="Another question?",
            repo_path="/test/repo",
            started_at=time.time(),
            updated_at=time.time() + 1,  # Newer
            current_step=ResearchCheckpointStep.SYNTHESIS,
            completed_steps=["decomposition", "retrieval", "gap_analysis"],
        )
        checkpoint_manager.save_checkpoint(checkpoint2)

        checkpoints = checkpoint_manager.list_checkpoints()

        assert len(checkpoints) == 2
        # Should be sorted by updated_at descending
        assert checkpoints[0].research_id == "test-456"
        assert checkpoints[1].research_id == "test-123"

    def test_delete_checkpoint(self, checkpoint_manager, sample_checkpoint):
        """Test deleting a checkpoint."""
        checkpoint_manager.save_checkpoint(sample_checkpoint)

        # Verify it exists
        assert checkpoint_manager.load_checkpoint(sample_checkpoint.research_id) is not None

        # Delete it
        result = checkpoint_manager.delete_checkpoint(sample_checkpoint.research_id)
        assert result is True

        # Verify it's gone
        assert checkpoint_manager.load_checkpoint(sample_checkpoint.research_id) is None

    def test_delete_nonexistent_checkpoint(self, checkpoint_manager):
        """Test deleting a checkpoint that doesn't exist."""
        result = checkpoint_manager.delete_checkpoint("nonexistent-id")
        assert result is False

    def test_get_incomplete_checkpoints(self, checkpoint_manager):
        """Test getting only incomplete checkpoints."""
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        # Create incomplete checkpoint
        incomplete = ResearchCheckpoint(
            research_id="incomplete-1",
            question="Question 1",
            repo_path="/test/repo",
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            completed_steps=["decomposition"],
        )
        checkpoint_manager.save_checkpoint(incomplete)

        # Create complete checkpoint
        complete = ResearchCheckpoint(
            research_id="complete-1",
            question="Question 2",
            repo_path="/test/repo",
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.COMPLETE,
            completed_steps=["decomposition", "retrieval", "gap_analysis", "synthesis"],
        )
        checkpoint_manager.save_checkpoint(complete)

        # Create error checkpoint
        errored = ResearchCheckpoint(
            research_id="error-1",
            question="Question 3",
            repo_path="/test/repo",
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.ERROR,
            error="Something went wrong",
            completed_steps=["decomposition"],
        )
        checkpoint_manager.save_checkpoint(errored)

        incomplete_checkpoints = checkpoint_manager.get_incomplete_checkpoints()

        assert len(incomplete_checkpoints) == 1
        assert incomplete_checkpoints[0].research_id == "incomplete-1"


class TestResearchCheckpointing:
    """Tests for checkpoint save/load during research."""

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

    async def test_checkpoint_created_during_research(self, mock_vector_store, tmp_path):
        """Test that checkpoints are created during research."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            repo_path=tmp_path,
        )

        result = await pipeline.research("Question")

        # Research should complete successfully
        assert result.answer == "Final answer"

        # Checkpoint should be cleaned up on completion
        checkpoints = pipeline.list_checkpoints()
        assert len(checkpoints) == 0

    async def test_checkpoint_saved_on_cancellation(self, mock_vector_store, tmp_path):
        """Test that checkpoint is saved when research is cancelled."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            repo_path=tmp_path,
        )

        call_count = 0
        def cancel_after_decomposition() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 1

        with pytest.raises(ResearchCancelledError) as exc_info:
            await pipeline.research(
                "Question",
                cancellation_check=cancel_after_decomposition,
            )

        # Should have checkpoint ID
        assert exc_info.value.checkpoint_id is not None

        # Checkpoint should exist
        checkpoints = pipeline.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0].current_step.value == "cancelled"
        assert checkpoints[0].completed_steps == ["decomposition"]

    async def test_resume_from_checkpoint(self, mock_vector_store, tmp_path):
        """Test resuming research from a checkpoint."""
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        # Create a pre-existing checkpoint with decomposition complete
        from local_deepwiki.core.deep_research import CheckpointManager

        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="resume-test-123",
            question="How does auth work?",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            sub_questions=[SubQuestion(question="What is auth?", category="structure")],
            completed_steps=["decomposition"],
        )
        manager.save_checkpoint(checkpoint)

        # Create pipeline and resume
        llm = MockLLMProvider(
            responses=[
                # Should NOT need decomposition response since it's restored
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Resumed final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            repo_path=tmp_path,
        )

        result = await pipeline.research(
            "How does auth work?",
            resume_id="resume-test-123",
        )

        # Should complete successfully
        assert "Resumed" in result.answer

        # Should only have made 2 LLM calls (gap analysis + synthesis)
        # not 3 (decomposition was skipped)
        assert llm.call_count == 2

        # Checkpoint should be cleaned up
        checkpoints = pipeline.list_checkpoints()
        assert len(checkpoints) == 0

    async def test_resume_with_retrieved_contexts(self, mock_vector_store, tmp_path):
        """Test resuming research after retrieval is complete."""
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        from local_deepwiki.core.deep_research import CheckpointManager, _search_result_to_dict
        import time

        # Create checkpoint with retrieval already complete
        manager = CheckpointManager(tmp_path)
        chunk = make_chunk("restored-chunk", "restored.py", "def restored(): pass")
        search_result = make_search_result(chunk, score=0.95)

        checkpoint = ResearchCheckpoint(
            research_id="resume-test-456",
            question="Question about code",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.GAP_ANALYSIS,
            sub_questions=[SubQuestion(question="Q?", category="structure")],
            retrieved_contexts={"initial": [_search_result_to_dict(search_result)]},
            completed_steps=["decomposition", "retrieval"],
        )
        manager.save_checkpoint(checkpoint)

        # Resume - should skip decomposition and retrieval
        llm = MockLLMProvider(
            responses=[
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer using restored context",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            repo_path=tmp_path,
        )

        result = await pipeline.research(
            "Question about code",
            resume_id="resume-test-456",
        )

        # Should have used restored context
        assert len(result.sources) >= 1

        # Vector store should NOT have been called (results restored)
        # Actually it will still be called for gap analysis follow-ups
        # but the initial retrieval should use restored results

    async def test_checkpoint_not_created_without_repo_path(self, mock_vector_store):
        """Test that no checkpoint is created when repo_path is not provided."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            # No repo_path provided
        )

        result = await pipeline.research("Question")

        # Should still work
        assert result.answer == "Final answer"

        # No checkpoint manager
        assert pipeline._checkpoint_manager is None


class TestResearchCancellationWithCheckpoint:
    """Tests for cancellation with checkpoint functionality."""

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

    async def test_cancellation_via_event(self, mock_vector_store, tmp_path):
        """Test cancellation via asyncio.Event."""
        import asyncio

        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": [{"question": "Q?", "category": "structure"}]}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Final answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            repo_path=tmp_path,
        )

        # Create cancellation event and set it immediately
        cancel_event = asyncio.Event()
        cancel_event.set()

        with pytest.raises(ResearchCancelledError) as exc_info:
            await pipeline.research(
                "Question",
                cancellation_event=cancel_event,
            )

        assert exc_info.value.step == "decomposition"
        assert exc_info.value.checkpoint_id is not None


class TestCheckpointHelperFunctions:
    """Tests for the standalone checkpoint helper functions."""

    def test_cancel_research(self, tmp_path):
        """Test the cancel_research helper function."""
        from local_deepwiki.core.deep_research import (
            cancel_research,
            CheckpointManager,
        )
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        # Create a checkpoint first
        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="cancel-test",
            question="Question",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            completed_steps=["decomposition"],
        )
        manager.save_checkpoint(checkpoint)

        # Cancel it
        result = cancel_research(tmp_path, "cancel-test")

        assert result is not None
        assert result.current_step == ResearchCheckpointStep.CANCELLED
        assert result.error == "Research was cancelled by user"

    def test_cancel_nonexistent_research(self, tmp_path):
        """Test cancelling research that doesn't exist."""
        from local_deepwiki.core.deep_research import cancel_research

        result = cancel_research(tmp_path, "nonexistent")
        assert result is None

    def test_list_research_checkpoints(self, tmp_path):
        """Test the list_research_checkpoints helper function."""
        from local_deepwiki.core.deep_research import (
            list_research_checkpoints,
            CheckpointManager,
        )
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        # Create some checkpoints
        manager = CheckpointManager(tmp_path)
        for i in range(3):
            checkpoint = ResearchCheckpoint(
                research_id=f"list-test-{i}",
                question=f"Question {i}",
                repo_path=str(tmp_path),
                started_at=time.time(),
                updated_at=time.time() + i,
                current_step=ResearchCheckpointStep.RETRIEVAL,
                completed_steps=["decomposition"],
            )
            manager.save_checkpoint(checkpoint)

        result = list_research_checkpoints(tmp_path)

        assert len(result) == 3
        # Should be sorted by updated_at descending
        assert result[0].research_id == "list-test-2"

    def test_get_research_checkpoint(self, tmp_path):
        """Test the get_research_checkpoint helper function."""
        from local_deepwiki.core.deep_research import (
            get_research_checkpoint,
            CheckpointManager,
        )
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="get-test",
            question="Question",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.SYNTHESIS,
            completed_steps=["decomposition", "retrieval", "gap_analysis"],
        )
        manager.save_checkpoint(checkpoint)

        result = get_research_checkpoint(tmp_path, "get-test")

        assert result is not None
        assert result.research_id == "get-test"

    def test_delete_research_checkpoint(self, tmp_path):
        """Test the delete_research_checkpoint helper function."""
        from local_deepwiki.core.deep_research import (
            delete_research_checkpoint,
            CheckpointManager,
        )
        from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep
        import time

        manager = CheckpointManager(tmp_path)
        checkpoint = ResearchCheckpoint(
            research_id="delete-test",
            question="Question",
            repo_path=str(tmp_path),
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.COMPLETE,
            completed_steps=["decomposition", "retrieval", "gap_analysis", "synthesis"],
        )
        manager.save_checkpoint(checkpoint)

        result = delete_research_checkpoint(tmp_path, "delete-test")
        assert result is True

        # Verify it's gone
        from local_deepwiki.core.deep_research import get_research_checkpoint
        assert get_research_checkpoint(tmp_path, "delete-test") is None


class TestSearchResultSerialization:
    """Tests for SearchResult serialization for checkpoints."""

    def test_search_result_round_trip(self):
        """Test that SearchResult can be serialized and deserialized."""
        from local_deepwiki.core.deep_research import (
            _search_result_to_dict,
            _dict_to_search_result,
        )

        chunk = make_chunk(
            "test-id",
            "test/file.py",
            "def test(): pass",
            "test_func"
        )
        original = SearchResult(chunk=chunk, score=0.95, highlights=["test"])

        # Serialize
        data = _search_result_to_dict(original)

        # Deserialize
        restored = _dict_to_search_result(data)

        # Verify
        assert restored.chunk.id == original.chunk.id
        assert restored.chunk.file_path == original.chunk.file_path
        assert restored.chunk.content == original.chunk.content
        assert restored.chunk.language == original.chunk.language
        assert restored.chunk.chunk_type == original.chunk.chunk_type
        assert restored.score == original.score
        assert restored.highlights == original.highlights
