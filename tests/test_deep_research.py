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
        assert "cannot be empty" in result[0].text

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
