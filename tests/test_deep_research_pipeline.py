"""Tests for deep research pipeline - core pipeline functionality."""

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


class TestSubQuestion:
    """Tests for SubQuestion model."""

    def test_creates_sub_question(self):
        """Test creating a SubQuestion."""
        sq = SubQuestion(question="What is auth?", category="structure")
        assert sq.question == "What is auth?"
        assert sq.category == "structure"

    def test_creates_sub_question_with_explicit_category(self):
        """Test creating a SubQuestion requires category."""
        sq = SubQuestion(question="Question?", category="structure")
        assert sq.question == "Question?"
        assert sq.category == "structure"


class TestDeepResearchResult:
    """Tests for DeepResearchResult model."""

    def test_creates_result(self):
        """Test creating a DeepResearchResult."""
        result = DeepResearchResult(
            question="Question?",
            answer="Answer",
            sub_questions=[SubQuestion(question="Sub?", category="flow")],
            sources=[],
            reasoning_trace=[],
            total_chunks_analyzed=10,
            total_llm_calls=3,
        )
        assert result.question == "Question?"
        assert result.answer == "Answer"
        assert len(result.sub_questions) == 1


class TestDeepResearchPipelineDecomposition:
    """Tests for the decomposition step of the pipeline."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        return store

    async def test_decomposes_question(self, mock_vector_store):
        """Test that research decomposes the question into sub-questions."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "What is the auth flow?", "category": "flow"},
                            {
                                "question": "What is the data model?",
                                "category": "structure",
                            },
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

        result = await pipeline.research("How does auth work?")

        assert len(result.sub_questions) == 2
        assert result.sub_questions[0].question == "What is the auth flow?"

    async def test_handles_empty_sub_questions(self, mock_vector_store):
        """Test handling when LLM returns no sub-questions."""
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": []}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer without sub-questions",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Simple question?")

        assert result.sub_questions == []
        # With no sub-questions and empty vector store, pipeline returns
        # a "no relevant code" message instead of calling the LLM for synthesis
        assert result.answer is not None
        assert len(result.answer) > 0

    async def test_handles_malformed_json(self, mock_vector_store):
        """Test handling when LLM returns malformed JSON."""
        llm = MockLLMProvider(
            responses=[
                "This is not JSON at all",
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer with failed decomposition",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question?")

        # Should handle gracefully
        assert result.sub_questions == []

    async def test_max_sub_questions_limit(self, mock_vector_store):
        """Test that sub-questions are limited."""
        many_questions = [
            {"question": f"Q{i}?", "category": "structure"} for i in range(20)
        ]
        llm = MockLLMProvider(
            responses=[
                json.dumps({"sub_questions": many_questions}),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
            max_sub_questions=5,
        )

        result = await pipeline.research("Big question?")

        assert len(result.sub_questions) <= 5


class TestDeepResearchPipelineRetrieval:
    """Tests for the retrieval step of the pipeline."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(make_chunk("c1")),
                make_search_result(make_chunk("c2")),
            ]
        )
        return store

    async def test_retrieves_chunks_for_sub_questions(self, mock_vector_store):
        """Test that chunks are retrieved for each sub-question."""
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
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question?")

        # Should have called search for each sub-question
        assert mock_vector_store.search.call_count >= 2
        assert result.total_chunks_analyzed > 0

    async def test_deduplicates_chunks(self, mock_vector_store):
        """Test that duplicate chunks are removed."""
        # Return same chunk for both searches
        same_chunk = make_search_result(make_chunk("same"))
        mock_vector_store.search = AsyncMock(return_value=[same_chunk])

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
                "Answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question?")

        # Should deduplicate
        assert result.total_chunks_analyzed <= 2


class TestDeepResearchPipelineGapAnalysis:
    """Tests for the gap analysis step of the pipeline."""

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

    async def test_identifies_gaps(self, mock_vector_store):
        """Test that gap analysis identifies missing information."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps(
                    {
                        "gaps": ["Missing auth details"],
                        "follow_up_queries": ["auth flow details", "token validation"],
                    }
                ),
                "Answer with gap-filled context",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question?")

        # Additional searches should have been made for follow-up queries
        assert mock_vector_store.search.call_count >= 2

    async def test_handles_no_gaps(self, mock_vector_store):
        """Test handling when no gaps are found."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "Complete answer",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("Question?")

        assert result.answer == "Complete answer"


class TestDeepResearchPipelineSynthesis:
    """Tests for the synthesis step of the pipeline."""

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

    async def test_synthesizes_answer(self, mock_vector_store):
        """Test that final answer is synthesized."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {"sub_questions": [{"question": "Q?", "category": "structure"}]}
                ),
                json.dumps({"gaps": [], "follow_up_queries": []}),
                "The auth system uses JWT tokens with refresh capability.",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("How does auth work?")

        assert "JWT" in result.answer
        assert result.total_llm_calls == 3

    async def test_includes_sources(self, mock_vector_store):
        """Test that sources are included in the result."""
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

        result = await pipeline.research("Question?")

        assert len(result.sources) > 0


class TestDeepResearchPipelineTracing:
    """Tests for the reasoning trace functionality."""

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

    async def test_includes_reasoning_trace(self, mock_vector_store):
        """Test that reasoning trace is included."""
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

        result = await pipeline.research("Question?")

        assert len(result.reasoning_trace) > 0
        # Should have at least decomposition, retrieval, gap_analysis, synthesis
        step_types = [step.step_type.value for step in result.reasoning_trace]
        assert "decomposition" in step_types

    async def test_trace_includes_durations(self, mock_vector_store):
        """Test that reasoning trace includes duration information."""
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

        result = await pipeline.research("Question?")

        for step in result.reasoning_trace:
            assert step.duration_ms is not None
            assert step.duration_ms >= 0


class TestDeepResearchPipelineIntegration:
    """Integration tests for the full pipeline."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.search = AsyncMock(
            return_value=[
                make_search_result(
                    make_chunk("c1", "auth.py", "def authenticate(): ...")
                ),
            ]
        )
        return store

    async def test_full_pipeline(self, mock_vector_store):
        """Test full pipeline execution."""
        llm = MockLLMProvider(
            responses=[
                json.dumps(
                    {
                        "sub_questions": [
                            {"question": "What is the auth flow?", "category": "flow"},
                        ]
                    }
                ),
                json.dumps(
                    {
                        "gaps": ["Missing token validation"],
                        "follow_up_queries": ["token validation"],
                    }
                ),
                "Complete auth answer with all details.",
            ]
        )

        pipeline = DeepResearchPipeline(
            vector_store=mock_vector_store,
            llm_provider=llm,
        )

        result = await pipeline.research("How does auth work?")

        assert result.question == "How does auth work?"
        assert result.answer is not None
        assert len(result.sub_questions) == 1
        assert result.total_llm_calls == 3
        assert result.total_chunks_analyzed > 0

    async def test_pipeline_with_custom_limits(self, mock_vector_store):
        """Test pipeline with custom configuration."""
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
            max_sub_questions=2,
            chunks_per_subquestion=3,
            max_total_chunks=10,
        )

        result = await pipeline.research("Question?")

        assert result.answer is not None
