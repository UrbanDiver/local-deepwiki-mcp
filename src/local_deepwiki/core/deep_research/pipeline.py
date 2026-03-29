"""Main DeepResearchPipeline class orchestrating multi-step research.

This module contains the pipeline class that coordinates decomposition,
retrieval, gap analysis, follow-up retrieval, and synthesis steps to
answer complex codebase questions.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from itertools import chain
from pathlib import Path
from typing import Any

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    CancellationChecker,
    DeepResearchResult,
    ProgressReporter,
    ResearchCheckpoint,
    ResearchCheckpointStep,
    ResearchProgress,
    ResearchProgressType,
    ResearchStep,
    SearchResult,
    SubQuestion,
)
from local_deepwiki.providers.base import LLMProvider

from .checkpoints import CheckpointManager
from .config import ResearchConfig
from .reasoning import (
    DECOMPOSITION_SYSTEM_PROMPT,
    GAP_ANALYSIS_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    ReasoningMixin,
)
from .serialization import dict_to_search_result, search_result_to_dict
from .steps import StepsMixin

logger = get_logger(__name__)


class ResearchCancelledError(Exception):
    """Raised when a deep research operation is cancelled."""

    def __init__(self, step: str = "unknown", checkpoint_id: str | None = None):
        self.step = step
        self.checkpoint_id = checkpoint_id
        msg = f"Research cancelled during {step}"
        if checkpoint_id:
            msg += f" (checkpoint: {checkpoint_id})"
        super().__init__(msg)


class DeepResearchPipeline(ReasoningMixin, StepsMixin):
    """Multi-step research pipeline for complex codebase questions.

    This pipeline performs:
    1. Query decomposition - breaks question into sub-questions
    2. Parallel retrieval - searches for each sub-question
    3. Gap analysis - identifies missing context
    4. Follow-up retrieval - targeted search for gaps
    5. Synthesis - combines context into comprehensive answer
    """

    def __init__(
        self,
        vector_store: VectorStore,
        llm_provider: LLMProvider,
        *,
        config: ResearchConfig | None = None,
        # Individual kwargs kept for backward compatibility
        max_sub_questions: int = 4,
        chunks_per_subquestion: int = 5,
        max_total_chunks: int = 30,
        max_follow_up_queries: int = 3,
        synthesis_temperature: float = 0.5,
        synthesis_max_tokens: int = 4096,
        decomposition_prompt: str | None = None,
        gap_analysis_prompt: str | None = None,
        synthesis_prompt: str | None = None,
        repo_path: Path | None = None,
    ):
        """Initialize the deep research pipeline.

        Args:
            vector_store: Vector store for semantic search.
            llm_provider: LLM provider for reasoning.
            config: Optional :class:`ResearchConfig` consolidating all keyword
                arguments.  When provided, individual kwargs are ignored.
            max_sub_questions: Maximum sub-questions to generate.
            chunks_per_subquestion: Chunks to retrieve per sub-question.
            max_total_chunks: Maximum total chunks to use in synthesis.
            max_follow_up_queries: Maximum follow-up queries in gap analysis.
            synthesis_temperature: LLM temperature for synthesis (0.0-2.0).
            synthesis_max_tokens: Maximum tokens in synthesis response.
            decomposition_prompt: Custom system prompt for decomposition (optional).
            gap_analysis_prompt: Custom system prompt for gap analysis (optional).
            synthesis_prompt: Custom system prompt for synthesis (optional).
            repo_path: Path to the repository (required for checkpointing).
        """
        if config is None:
            config = ResearchConfig(
                max_sub_questions=max_sub_questions,
                chunks_per_subquestion=chunks_per_subquestion,
                max_total_chunks=max_total_chunks,
                max_follow_up_queries=max_follow_up_queries,
                synthesis_temperature=synthesis_temperature,
                synthesis_max_tokens=synthesis_max_tokens,
                decomposition_prompt=decomposition_prompt,
                gap_analysis_prompt=gap_analysis_prompt,
                synthesis_prompt=synthesis_prompt,
                repo_path=repo_path,
            )

        self.vector_store = vector_store
        self.llm = llm_provider
        self.max_sub_questions = config.max_sub_questions
        self.chunks_per_subquestion = config.chunks_per_subquestion
        self.max_total_chunks = config.max_total_chunks
        self.max_follow_up_queries = config.max_follow_up_queries
        self.synthesis_temperature = config.synthesis_temperature
        self.synthesis_max_tokens = config.synthesis_max_tokens

        # Use custom prompts if provided, otherwise use defaults
        self.decomposition_prompt = (
            config.decomposition_prompt or DECOMPOSITION_SYSTEM_PROMPT
        )
        self.gap_analysis_prompt = (
            config.gap_analysis_prompt or GAP_ANALYSIS_SYSTEM_PROMPT
        )
        self.synthesis_prompt = config.synthesis_prompt or SYNTHESIS_SYSTEM_PROMPT

        # Repository path for checkpointing
        self.repo_path = config.repo_path
        self._checkpoint_manager: CheckpointManager | None = None
        if config.repo_path:
            self._checkpoint_manager = CheckpointManager(config.repo_path)

        # Runtime state (set during research())
        self._progress_callback: ProgressReporter | None = None
        self._cancellation_check: CancellationChecker | None = None
        self._current_checkpoint: ResearchCheckpoint | None = None
        self._cancellation_event: asyncio.Event | None = None

    def _check_cancelled(self, step_name: str) -> None:
        """Check if research was cancelled and raise if so.

        Args:
            step_name: Name of the current step for error message.

        Raises:
            ResearchCancelledError: If cancellation was requested.
        """
        # Check the cancellation event first
        if self._cancellation_event and self._cancellation_event.is_set():
            logger.info("Research cancelled via event during %s", step_name)
            checkpoint_id = (
                self._current_checkpoint.research_id
                if self._current_checkpoint
                else None
            )
            raise ResearchCancelledError(step_name, checkpoint_id)

        # Then check the callback
        if self._cancellation_check and self._cancellation_check():
            logger.info("Research cancelled during %s", step_name)
            checkpoint_id = (
                self._current_checkpoint.research_id
                if self._current_checkpoint
                else None
            )
            raise ResearchCancelledError(step_name, checkpoint_id)

    def _save_checkpoint(
        self,
        step: ResearchCheckpointStep,
        sub_questions: list[SubQuestion] | None = None,
        retrieved_contexts: dict[str, list[dict]] | None = None,
        follow_up_queries: list[str] | None = None,
        follow_up_contexts: list[dict] | None = None,
        partial_synthesis: str | None = None,
        error: str | None = None,
        completed_step: str | None = None,
    ) -> None:
        """Save the current research state as a checkpoint.

        Args:
            step: The current step in the research process.
            sub_questions: Decomposed sub-questions (if available).
            retrieved_contexts: Retrieved context data (if available).
            follow_up_queries: Follow-up queries from gap analysis (if available).
            follow_up_contexts: Follow-up retrieval contexts (if available).
            partial_synthesis: Partial synthesis result (if available).
            error: Error message if failed.
            completed_step: Name of the step that was just completed.
        """
        if not self._checkpoint_manager or not self._current_checkpoint:
            return

        checkpoint = self._current_checkpoint

        # Update checkpoint fields
        checkpoint.current_step = step
        checkpoint.updated_at = time.time()

        if sub_questions is not None:
            checkpoint.sub_questions = sub_questions
        if retrieved_contexts is not None:
            checkpoint.retrieved_contexts = retrieved_contexts
        if follow_up_queries is not None:
            checkpoint.follow_up_queries = follow_up_queries
        if follow_up_contexts is not None:
            checkpoint.follow_up_contexts = follow_up_contexts
        if partial_synthesis is not None:
            checkpoint.partial_synthesis = partial_synthesis
        if error is not None:
            checkpoint.error = error
        if completed_step and completed_step not in checkpoint.completed_steps:
            checkpoint.completed_steps.append(completed_step)

        self._checkpoint_manager.save_checkpoint(checkpoint)

    def _create_checkpoint(self, question: str) -> ResearchCheckpoint:
        """Create a new checkpoint for a research session.

        Args:
            question: The research question.

        Returns:
            A new ResearchCheckpoint object.
        """
        now = time.time()
        return ResearchCheckpoint(
            research_id=str(uuid.uuid4()),
            question=question,
            repo_path=str(self.repo_path) if self.repo_path else "",
            started_at=now,
            updated_at=now,
            current_step=ResearchCheckpointStep.DECOMPOSITION,
            completed_steps=[],
        )

    @staticmethod
    def _results_to_checkpoint_format(
        results: list[SearchResult],
        key: str = "default",
    ) -> dict[str, list[dict]]:
        """Convert search results to checkpoint-serializable format.

        Args:
            results: List of search results.
            key: Key to use in the dictionary.

        Returns:
            Dictionary mapping key to list of serialized results.
        """
        return {key: [search_result_to_dict(r) for r in results]}

    @staticmethod
    def _checkpoint_to_results(
        contexts: dict[str, list[dict]] | None,
    ) -> list[SearchResult]:
        """Convert checkpoint context data back to SearchResults.

        Args:
            contexts: Dictionary of serialized contexts from checkpoint.

        Returns:
            List of reconstructed SearchResult objects.
        """
        if not contexts:
            return []

        results = []
        for data in chain.from_iterable(contexts.values()):
            try:
                results.append(dict_to_search_result(data))
            except (KeyError, ValueError) as e:
                logger.warning("Failed to restore search result: %s", e)
                continue
        return results

    def load_checkpoint(self, research_id: str) -> ResearchCheckpoint | None:
        """Load a checkpoint by ID.

        Args:
            research_id: The research session ID.

        Returns:
            The loaded checkpoint, or None if not found.
        """
        if not self._checkpoint_manager:
            return None
        return self._checkpoint_manager.load_checkpoint(research_id)

    def list_checkpoints(self) -> list[ResearchCheckpoint]:
        """List all checkpoints for this repository.

        Returns:
            List of checkpoints.
        """
        if not self._checkpoint_manager:
            return []
        return self._checkpoint_manager.list_checkpoints()

    def delete_checkpoint(self, research_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            research_id: The research session ID.

        Returns:
            True if deleted, False if not found.
        """
        if not self._checkpoint_manager:
            return False
        return self._checkpoint_manager.delete_checkpoint(research_id)

    async def _report_progress(
        self,
        step: int,
        step_type: ResearchProgressType,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Report progress to the callback if set.

        Args:
            step: Current step number.
            step_type: Type of progress event.
            message: Human-readable progress message.
            **kwargs: Additional progress data.
        """
        if self._progress_callback:
            await self._progress_callback(
                ResearchProgress(
                    step=step,
                    step_type=step_type,
                    message=message,
                    **kwargs,
                )
            )

    def _init_checkpoint(self, question: str, resume_id: str | None) -> None:
        """Initialize or restore the checkpoint for this research run.

        Sets ``self._current_checkpoint`` based on whether we are resuming an
        existing checkpoint or starting fresh.

        Args:
            question: The research question (used when creating a new checkpoint).
            resume_id: Optional checkpoint ID to resume from.
        """
        if resume_id and self._checkpoint_manager:
            checkpoint = self._checkpoint_manager.load_checkpoint(resume_id)
            if checkpoint:
                self._current_checkpoint = checkpoint
                logger.info(
                    "Resuming research %s from step %s",
                    resume_id,
                    checkpoint.current_step,
                )
                return
            logger.warning("Checkpoint %s not found, starting fresh", resume_id)

        if self._checkpoint_manager:
            self._current_checkpoint = self._create_checkpoint(question)
        else:
            self._current_checkpoint = None

    async def _run_pipeline_with_checkpoint(self, question: str) -> DeepResearchResult:
        """Run the pipeline and manage checkpoint lifecycle on success or error.

        Deletes the checkpoint on success; saves an error/cancelled checkpoint
        on failure before re-raising.

        Args:
            question: The research question.

        Returns:
            DeepResearchResult from the pipeline.

        Raises:
            ResearchCancelledError: Propagated from the pipeline.
            Exception: Any other pipeline error is re-raised after saving state.
        """
        try:
            result = await self._execute_pipeline(question)

            if self._current_checkpoint and self._checkpoint_manager:
                self._checkpoint_manager.delete_checkpoint(
                    self._current_checkpoint.research_id
                )

            return result

        except ResearchCancelledError:
            if self._current_checkpoint:
                self._save_checkpoint(
                    step=ResearchCheckpointStep.CANCELLED,
                    error="Research was cancelled by user",
                )
            raise

        except Exception as e:  # noqa: BLE001 — checkpoint boundary
            if self._current_checkpoint:
                self._save_checkpoint(
                    step=ResearchCheckpointStep.ERROR,
                    error=str(e),
                )
            raise

    async def research(
        self,
        question: str,
        progress_callback: ProgressReporter | None = None,
        cancellation_check: CancellationChecker | None = None,
        resume_id: str | None = None,
        cancellation_event: asyncio.Event | None = None,
    ) -> DeepResearchResult:
        """Execute the full research pipeline.

        Args:
            question: The complex question to research.
            progress_callback: Optional async callback for progress updates.
            cancellation_check: Optional callback that returns True if cancelled.
            resume_id: Optional checkpoint ID to resume from.
            cancellation_event: Optional asyncio.Event for cancellation signaling.

        Returns:
            DeepResearchResult with answer, sources, and reasoning trace.

        Raises:
            ResearchCancelledError: If the operation is cancelled.
        """
        self._progress_callback = progress_callback
        self._cancellation_check = cancellation_check
        self._cancellation_event = cancellation_event

        self._init_checkpoint(question, resume_id)

        try:
            return await self._run_pipeline_with_checkpoint(question)
        finally:
            self._progress_callback = None
            self._cancellation_check = None
            self._cancellation_event = None
            self._current_checkpoint = None

    async def _execute_pipeline(self, question: str) -> DeepResearchResult:
        """Execute the research pipeline steps.

        This is a high-level orchestrator that coordinates the research steps,
        delegating checkpoint restoration and step execution to helper methods.

        Args:
            question: The complex question to research.

        Returns:
            DeepResearchResult with answer, sources, and reasoning trace.
        """
        trace: list[ResearchStep] = []
        llm_calls = 0

        # Determine what steps to skip based on checkpoint
        checkpoint = self._current_checkpoint
        completed_steps = set(checkpoint.completed_steps) if checkpoint else set()

        # Emit start event and report progress
        await self._emit_start_event(question, completed_steps)

        # Step 1: Decompose question
        sub_questions, step, calls = await self._execute_decomposition_step(
            question, completed_steps
        )
        trace.append(step)
        llm_calls += calls

        # Step 2: Parallel retrieval
        initial_results, step = await self._execute_retrieval_step(
            sub_questions, completed_steps
        )
        trace.append(step)

        # Step 3: Gap analysis
        follow_up_queries, step, calls = await self._execute_gap_analysis_step(
            question, sub_questions, initial_results, completed_steps
        )
        trace.append(step)
        llm_calls += calls

        # Step 4: Follow-up retrieval (if needed)
        additional_results, follow_up_step = await self._execute_follow_up_step(
            follow_up_queries, len(initial_results), completed_steps
        )
        if follow_up_step:
            trace.append(follow_up_step)

        # Prepare results for synthesis
        all_results = self._prepare_results_for_synthesis(
            initial_results, additional_results
        )

        # Step 5: Synthesis
        answer, step, calls = await self._step_synthesize(
            question, sub_questions, all_results
        )
        trace.append(step)
        llm_calls += calls

        # Finalize and build result
        return await self._finalize_research(
            question,
            answer,
            sub_questions,
            all_results,
            trace,
            llm_calls,
            step.duration_ms,
        )

    async def _emit_start_event(
        self,
        question: str,
        completed_steps: set[str],
    ) -> None:
        """Emit the research start event and report initial progress.

        Args:
            question: The research question.
            completed_steps: Set of already completed step names.
        """
        emitter = get_event_emitter()
        is_resuming = bool(completed_steps)

        if not is_resuming:
            await emitter.emit(
                EventType.RESEARCH_START,
                {"question": question},
            )
            await self._report_progress(
                0, ResearchProgressType.STARTED, "Starting deep research..."
            )
        else:
            await self._report_progress(
                0,
                ResearchProgressType.STARTED,
                f"Resuming deep research from checkpoint (completed: {', '.join(completed_steps)})",
            )

    def _prepare_results_for_synthesis(
        self,
        initial_results: list[SearchResult],
        additional_results: list[SearchResult],
    ) -> list[SearchResult]:
        """Deduplicate and limit results for synthesis.

        Returns:
            Prepared list of search results.
        """
        all_results = self._deduplicate_results(initial_results + additional_results)

        if len(all_results) > self.max_total_chunks:
            all_results = all_results[: self.max_total_chunks]
            logger.info("Limited to %s chunks for synthesis", self.max_total_chunks)

        return all_results

    async def _finalize_research(
        self,
        question: str,
        answer: str,
        sub_questions: list[SubQuestion],
        all_results: list[SearchResult],
        trace: list[ResearchStep],
        llm_calls: int,
        synthesis_duration_ms: int,
    ) -> DeepResearchResult:
        """Finalize the research by saving checkpoint and emitting completion events.

        Args:
            question: The original research question.
            answer: The synthesized answer.
            sub_questions: The decomposed sub-questions.
            all_results: All retrieved search results.
            trace: The reasoning trace.
            llm_calls: Total number of LLM calls made.
            synthesis_duration_ms: Duration of the synthesis step.

        Returns:
            The final DeepResearchResult.
        """
        # Mark checkpoint as complete
        self._save_checkpoint(
            step=ResearchCheckpointStep.COMPLETE,
            partial_synthesis=answer,
            completed_step="synthesis",
        )

        # Report completion
        await self._report_progress(
            5,
            ResearchProgressType.COMPLETE,
            f"Research complete: {len(all_results)} chunks analyzed, {llm_calls} LLM calls",
            chunks_retrieved=len(all_results),
            duration_ms=synthesis_duration_ms,
        )

        # Emit RESEARCH_COMPLETE event
        emitter = get_event_emitter()
        await emitter.emit(
            EventType.RESEARCH_COMPLETE,
            {
                "question": question,
                "sub_question_count": len(sub_questions),
                "chunks_analyzed": len(all_results),
                "llm_calls": llm_calls,
            },
        )

        return DeepResearchResult(
            question=question,
            answer=answer,
            sub_questions=sub_questions,
            sources=self._build_sources(all_results),
            reasoning_trace=trace,
            total_chunks_analyzed=len(all_results),
            total_llm_calls=llm_calls,
        )
