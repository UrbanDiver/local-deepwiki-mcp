"""Deep research, progress, and checkpoint models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ResearchStepType(StrEnum):
    """Types of steps in the deep research process."""

    DECOMPOSITION = "decomposition"
    RETRIEVAL = "retrieval"
    GAP_ANALYSIS = "gap_analysis"
    SYNTHESIS = "synthesis"


class ResearchStep(BaseModel):
    """A single step in the deep research process."""

    step_type: ResearchStepType = Field(description="Type of research step")
    description: str = Field(description="Description of what was done")
    duration_ms: int = Field(description="Duration of this step in milliseconds")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<ResearchStep {self.step_type.value} ({self.duration_ms}ms)>"


class SubQuestion(BaseModel):
    """A decomposed sub-question for deep research."""

    question: str = Field(description="The sub-question to investigate")
    category: str = Field(
        description="Category: structure, flow, dependencies, impact, or comparison"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<SubQuestion [{self.category}] {self.question[:50]}...>"


class SourceReference(BaseModel):
    """A reference to a source code location."""

    file_path: str = Field(description="Path to the source file")
    start_line: int = Field(description="Starting line number")
    end_line: int = Field(description="Ending line number")
    chunk_type: str = Field(description="Type of code chunk")
    name: str | None = Field(default=None, description="Name of the code element")
    relevance_score: float = Field(description="Relevance score from search")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        name = self.name or self.chunk_type
        return f"<Source {self.file_path}:{self.start_line}-{self.end_line} ({name})>"


class DeepResearchResult(BaseModel):
    """Result from deep research analysis."""

    question: str = Field(description="Original question asked")
    answer: str = Field(description="Comprehensive answer with citations")
    sub_questions: list[SubQuestion] = Field(
        default_factory=list, description="Decomposed sub-questions investigated"
    )
    sources: list[SourceReference] = Field(
        default_factory=list, description="Source code references used"
    )
    reasoning_trace: list[ResearchStep] = Field(
        default_factory=list, description="Steps taken during research"
    )
    total_chunks_analyzed: int = Field(description="Total code chunks analyzed")
    total_llm_calls: int = Field(description="Total LLM calls made")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return (
            f"<DeepResearchResult {len(self.sub_questions)} sub-questions, "
            f"{len(self.sources)} sources, {self.total_llm_calls} LLM calls>"
        )


class IndexingProgressType(StrEnum):
    """Types of indexing progress events."""

    STARTED = "started"
    SCANNING_FILES = "scanning_files"
    PARSING_FILES = "parsing_files"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    STORING_VECTORS = "storing_vectors"
    GENERATING_WIKI = "generating_wiki"
    GENERATING_PAGES = "generating_pages"
    COMPLETE = "complete"


class IndexingProgress(BaseModel):
    """Progress update from repository indexing.

    Sent via MCP progress notifications to provide real-time feedback
    during long-running indexing operations.
    """

    step: int = Field(description="Current step number")
    total_steps: int = Field(description="Total number of steps")
    step_type: IndexingProgressType = Field(description="Type of progress event")
    message: str = Field(description="Human-readable progress message")
    files_processed: int | None = Field(
        default=None, description="Number of files processed"
    )
    total_files: int | None = Field(default=None, description="Total files to process")
    chunks_created: int | None = Field(
        default=None, description="Number of chunks created"
    )
    pages_generated: int | None = Field(
        default=None, description="Wiki pages generated"
    )
    duration_ms: int | None = Field(
        default=None, description="Duration of step in milliseconds"
    )


class ResearchProgressType(StrEnum):
    """Types of deep research progress events."""

    STARTED = "started"
    DECOMPOSITION_COMPLETE = "decomposition_complete"
    RETRIEVAL_COMPLETE = "retrieval_complete"
    GAP_ANALYSIS_COMPLETE = "gap_analysis_complete"
    FOLLOWUP_COMPLETE = "followup_complete"
    SYNTHESIS_STARTED = "synthesis_started"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class ResearchProgress(BaseModel):
    """Progress update from deep research pipeline.

    Sent via MCP progress notifications to provide real-time feedback
    during long-running deep research operations.
    """

    step: int = Field(description="Current step number (0-5)")
    total_steps: int = Field(default=5, description="Total number of steps")
    step_type: ResearchProgressType = Field(description="Type of progress event")
    message: str = Field(description="Human-readable progress message")
    sub_questions: list[SubQuestion] | None = Field(
        default=None, description="Sub-questions after decomposition"
    )
    chunks_retrieved: int | None = Field(
        default=None, description="Number of chunks retrieved so far"
    )
    follow_up_queries: list[str] | None = Field(
        default=None, description="Follow-up queries from gap analysis"
    )
    duration_ms: int | None = Field(
        default=None, description="Duration of completed step in milliseconds"
    )


# =============================================================================
# Research Checkpoint Models
# =============================================================================


class ResearchCheckpointStep(StrEnum):
    """Current step in a research checkpoint."""

    DECOMPOSITION = "decomposition"
    RETRIEVAL = "retrieval"
    GAP_ANALYSIS = "gap_analysis"
    FOLLOW_UP_RETRIEVAL = "follow_up_retrieval"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


class ResearchCheckpoint(BaseModel):
    """Checkpoint state for resumable deep research operations.

    This model captures the complete state of a research operation,
    allowing it to be saved after each step and resumed if interrupted.
    """

    schema_version: int = Field(
        default=1, description="Schema version for checkpoint compatibility"
    )
    research_id: str = Field(description="UUID for this research session")
    question: str = Field(description="Original research question")
    repo_path: str = Field(description="Path to the repository being researched")
    started_at: float = Field(description="Unix timestamp when research started")
    updated_at: float = Field(description="Unix timestamp of last update")
    current_step: ResearchCheckpointStep = Field(
        description="Current step in the research pipeline"
    )
    sub_questions: list[SubQuestion] | None = Field(
        default=None, description="Decomposed sub-questions"
    )
    retrieved_contexts: dict[str, list[dict]] | None = Field(
        default=None, description="Mapping of sub_question to retrieved chunk data"
    )
    follow_up_queries: list[str] | None = Field(
        default=None, description="Follow-up queries from gap analysis"
    )
    follow_up_contexts: list[dict] | None = Field(
        default=None, description="Retrieved contexts from follow-up queries"
    )
    partial_synthesis: str | None = Field(
        default=None, description="Partial synthesis result if available"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    completed_steps: list[str] = Field(
        default_factory=list, description="List of completed step names"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return (
            f"<ResearchCheckpoint {self.research_id[:8]}... "
            f"step={self.current_step.value} "
            f"completed={len(self.completed_steps)}>"
        )


class ListResearchCheckpointsArgs(BaseModel):
    """Arguments for the list_research_checkpoints tool."""

    repo_path: str = Field(description="Path to the repository to list checkpoints for")


class ResumeResearchArgs(BaseModel):
    """Arguments for resuming research with a checkpoint."""

    repo_path: str = Field(description="Path to the indexed repository")
    research_id: str = Field(description="ID of the research checkpoint to resume")


class CancelResearchArgs(BaseModel):
    """Arguments for cancelling and checkpointing research."""

    repo_path: str = Field(description="Path to the repository")
    research_id: str = Field(description="ID of the research to cancel")
