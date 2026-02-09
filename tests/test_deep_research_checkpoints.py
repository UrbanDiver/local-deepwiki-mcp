"""Tests for deep research pipeline - checkpointing and serialization."""

import json
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.core.deep_research import (
    CheckpointManager,
    DeepResearchPipeline,
    ResearchCancelledError,
    _dict_to_search_result,
    _search_result_to_dict,
    cancel_research,
    delete_research_checkpoint,
    get_research_checkpoint,
    list_research_checkpoints,
)
from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    Language,
    ResearchCheckpoint,
    ResearchCheckpointStep,
    SearchResult,
    SubQuestion,
)
from local_deepwiki.providers.base import EmbeddingProvider, LLMProvider


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


class TestCheckpointManager:
    """Tests for the CheckpointManager class."""

    @pytest.fixture
    def checkpoint_manager(self, tmp_path):
        """Create a checkpoint manager with a temp directory."""
        return CheckpointManager(tmp_path)

    @pytest.fixture
    def sample_checkpoint(self):
        """Create a sample checkpoint for testing."""
        return ResearchCheckpoint(
            research_id="test-123",
            question="How does authentication work?",
            repo_path="/test/repo",
            started_at=time.time(),
            updated_at=time.time(),
            current_step=ResearchCheckpointStep.RETRIEVAL,
            sub_questions=[
                SubQuestion(question="What is the auth flow?", category="flow")
            ],
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
        assert (
            checkpoint_manager.load_checkpoint(sample_checkpoint.research_id)
            is not None
        )

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

    async def test_checkpoint_created_during_research(
        self, mock_vector_store, tmp_path
    ):
        """Test that checkpoints are created during research."""
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
        # Create a pre-existing checkpoint with decomposition complete
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

    async def test_checkpoint_not_created_without_repo_path(self, mock_vector_store):
        """Test that no checkpoint is created when repo_path is not provided."""
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
        result = cancel_research(tmp_path, "nonexistent")
        assert result is None

    def test_list_research_checkpoints(self, tmp_path):
        """Test the list_research_checkpoints helper function."""
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
        assert get_research_checkpoint(tmp_path, "delete-test") is None


class TestSearchResultSerialization:
    """Tests for SearchResult serialization for checkpoints."""

    def test_search_result_round_trip(self):
        """Test that SearchResult can be serialized and deserialized."""
        chunk = make_chunk("test-id", "test/file.py", "def test(): pass", "test_func")
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
