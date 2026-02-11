"""Step execution methods for the deep research pipeline.

Contains the orchestration logic for each research step: decomposition,
retrieval, gap analysis, follow-up retrieval, and synthesis. Each step
handles checkpoint restoration and progress reporting.
"""

from __future__ import annotations

import time

from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    ResearchCheckpointStep,
    ResearchProgressType,
    ResearchStep,
    ResearchStepType,
    SearchResult,
    SubQuestion,
)

from .serialization import dict_to_search_result, search_result_to_dict

logger = get_logger(__name__)


class StepsMixin:
    """Mixin providing step execution methods for DeepResearchPipeline.

    Each method handles both fresh execution and checkpoint restoration.

    Expects the following attributes/methods on the host class:
        - _current_checkpoint: ResearchCheckpoint | None
        - _check_cancelled(step_name: str) -> None
        - _save_checkpoint(...) -> None
        - _report_progress(...) -> None
        - _decompose_question(question: str) -> list[SubQuestion]
        - _parallel_retrieve(sub_questions) -> list[SearchResult]
        - _analyze_gaps(question, sub_questions, results) -> list[str]
        - _targeted_retrieve(queries) -> list[SearchResult]
        - _deduplicate_results(results) -> list[SearchResult]
        - _synthesize(question, sub_questions, results) -> str
        - _build_sources(results) -> list[SourceReference]
        - _results_to_checkpoint_format(results, key) -> dict
        - max_total_chunks: int
    """

    async def _execute_decomposition_step(
        self,
        question: str,
        completed_steps: set[str],
    ) -> tuple[list[SubQuestion], ResearchStep, int]:
        """Execute or restore the decomposition step.

        Args:
            question: The research question.
            completed_steps: Set of already completed step names.

        Returns:
            Tuple of (sub_questions, trace_step, llm_call_count).
        """
        checkpoint = self._current_checkpoint

        if (
            "decomposition" in completed_steps
            and checkpoint
            and checkpoint.sub_questions
        ):
            # Restore from checkpoint
            sub_questions = checkpoint.sub_questions
            logger.info(f"Restored {len(sub_questions)} sub-questions from checkpoint")
            step = ResearchStep(
                step_type=ResearchStepType.DECOMPOSITION,
                description=f"Restored {len(sub_questions)} sub-questions from checkpoint",
                duration_ms=0,
            )
            return sub_questions, step, 0

        # Execute the step
        sub_questions, step, calls = await self._step_decompose(question)
        # Save checkpoint after decomposition
        self._save_checkpoint(
            step=ResearchCheckpointStep.RETRIEVAL,
            sub_questions=sub_questions,
            completed_step="decomposition",
        )
        return sub_questions, step, calls

    async def _execute_retrieval_step(
        self,
        sub_questions: list[SubQuestion],
        completed_steps: set[str],
    ) -> tuple[list[SearchResult], ResearchStep]:
        """Execute or restore the initial retrieval step.

        Args:
            sub_questions: The decomposed sub-questions.
            completed_steps: Set of already completed step names.

        Returns:
            Tuple of (search_results, trace_step).
        """
        checkpoint = self._current_checkpoint

        if (
            "retrieval" in completed_steps
            and checkpoint
            and checkpoint.retrieved_contexts
        ):
            # Restore from checkpoint
            initial_results = self._checkpoint_to_results(checkpoint.retrieved_contexts)
            logger.info(f"Restored {len(initial_results)} chunks from checkpoint")
            step = ResearchStep(
                step_type=ResearchStepType.RETRIEVAL,
                description=f"Restored {len(initial_results)} chunks from checkpoint",
                duration_ms=0,
            )
            return initial_results, step

        # Execute the step
        initial_results, step = await self._step_retrieve(sub_questions)
        # Save checkpoint after retrieval
        self._save_checkpoint(
            step=ResearchCheckpointStep.GAP_ANALYSIS,
            retrieved_contexts=self._results_to_checkpoint_format(
                initial_results, "initial"
            ),
            completed_step="retrieval",
        )
        return initial_results, step

    async def _execute_gap_analysis_step(
        self,
        question: str,
        sub_questions: list[SubQuestion],
        initial_results: list[SearchResult],
        completed_steps: set[str],
    ) -> tuple[list[str], ResearchStep, int]:
        """Execute or restore the gap analysis step.

        Args:
            question: The original research question.
            sub_questions: The decomposed sub-questions.
            initial_results: Results from initial retrieval.
            completed_steps: Set of already completed step names.

        Returns:
            Tuple of (follow_up_queries, trace_step, llm_call_count).
        """
        checkpoint = self._current_checkpoint

        if (
            "gap_analysis" in completed_steps
            and checkpoint
            and checkpoint.follow_up_queries is not None
        ):
            # Restore from checkpoint
            follow_up_queries = checkpoint.follow_up_queries
            logger.info(
                f"Restored {len(follow_up_queries)} follow-up queries from checkpoint"
            )
            step = ResearchStep(
                step_type=ResearchStepType.GAP_ANALYSIS,
                description=f"Restored {len(follow_up_queries)} follow-up queries from checkpoint",
                duration_ms=0,
            )
            return follow_up_queries, step, 0

        # Execute the step
        follow_up_queries, step, calls = await self._step_gap_analysis(
            question, sub_questions, initial_results
        )
        # Save checkpoint after gap analysis
        self._save_checkpoint(
            step=ResearchCheckpointStep.FOLLOW_UP_RETRIEVAL
            if follow_up_queries
            else ResearchCheckpointStep.SYNTHESIS,
            follow_up_queries=follow_up_queries,
            completed_step="gap_analysis",
        )
        return follow_up_queries, step, calls

    async def _execute_follow_up_step(
        self,
        follow_up_queries: list[str],
        initial_count: int,
        completed_steps: set[str],
    ) -> tuple[list[SearchResult], ResearchStep | None]:
        """Execute or restore the follow-up retrieval step.

        Args:
            follow_up_queries: Queries from gap analysis.
            initial_count: Number of results from initial retrieval.
            completed_steps: Set of already completed step names.

        Returns:
            Tuple of (additional_results, trace_step or None if no follow-up needed).
        """
        if not follow_up_queries:
            return [], None

        checkpoint = self._current_checkpoint

        if (
            "follow_up_retrieval" in completed_steps
            and checkpoint
            and checkpoint.follow_up_contexts
        ):
            # Restore from checkpoint
            additional_results = [
                dict_to_search_result(d) for d in checkpoint.follow_up_contexts
            ]
            logger.info(
                f"Restored {len(additional_results)} follow-up chunks from checkpoint"
            )
            step = ResearchStep(
                step_type=ResearchStepType.RETRIEVAL,
                description=f"Restored {len(additional_results)} follow-up chunks from checkpoint",
                duration_ms=0,
            )
            return additional_results, step

        # Execute the step
        additional_results, step = await self._step_follow_up_retrieve(
            follow_up_queries, initial_count
        )
        # Save checkpoint after follow-up retrieval
        self._save_checkpoint(
            step=ResearchCheckpointStep.SYNTHESIS,
            follow_up_contexts=[search_result_to_dict(r) for r in additional_results],
            completed_step="follow_up_retrieval",
        )
        return additional_results, step

    async def _step_decompose(
        self, question: str
    ) -> tuple[list[SubQuestion], ResearchStep, int]:
        """Execute the decomposition step.

        Returns:
            Tuple of (sub_questions, trace_step, llm_call_count).
        """
        self._check_cancelled("decomposition")
        start_time = time.time()

        sub_questions = await self._decompose_question(question)
        duration_ms = int((time.time() - start_time) * 1000)

        step = ResearchStep(
            step_type=ResearchStepType.DECOMPOSITION,
            description=f"Decomposed into {len(sub_questions)} sub-questions",
            duration_ms=duration_ms,
        )

        logger.info(f"Decomposed question into {len(sub_questions)} sub-questions")

        # Emit RESEARCH_QUERY events for each sub-question
        emitter = get_event_emitter()
        for sq in sub_questions:
            await emitter.emit(
                EventType.RESEARCH_QUERY,
                {
                    "question": sq.question,
                    "category": sq.category,
                },
            )

        await self._report_progress(
            1,
            ResearchProgressType.DECOMPOSITION_COMPLETE,
            f"Decomposed into {len(sub_questions)} sub-questions",
            sub_questions=sub_questions,
            duration_ms=duration_ms,
        )

        return sub_questions, step, 1

    async def _step_retrieve(
        self, sub_questions: list[SubQuestion]
    ) -> tuple[list[SearchResult], ResearchStep]:
        """Execute the initial retrieval step.

        Returns:
            Tuple of (search_results, trace_step).
        """
        self._check_cancelled("retrieval")
        start_time = time.time()

        results = await self._parallel_retrieve(sub_questions)
        duration_ms = int((time.time() - start_time) * 1000)

        step = ResearchStep(
            step_type=ResearchStepType.RETRIEVAL,
            description=f"Retrieved {len(results)} code chunks",
            duration_ms=duration_ms,
        )

        logger.info(f"Initial retrieval found {len(results)} chunks")
        await self._report_progress(
            2,
            ResearchProgressType.RETRIEVAL_COMPLETE,
            f"Retrieved {len(results)} code chunks",
            chunks_retrieved=len(results),
            duration_ms=duration_ms,
        )

        return results, step

    async def _step_gap_analysis(
        self,
        question: str,
        sub_questions: list[SubQuestion],
        results: list[SearchResult],
    ) -> tuple[list[str], ResearchStep, int]:
        """Execute the gap analysis step.

        Returns:
            Tuple of (follow_up_queries, trace_step, llm_call_count).
        """
        self._check_cancelled("gap_analysis")
        start_time = time.time()

        follow_up_queries = await self._analyze_gaps(question, sub_questions, results)
        duration_ms = int((time.time() - start_time) * 1000)

        step = ResearchStep(
            step_type=ResearchStepType.GAP_ANALYSIS,
            description=f"Identified {len(follow_up_queries)} gaps to fill",
            duration_ms=duration_ms,
        )

        logger.info(
            f"Gap analysis generated {len(follow_up_queries)} follow-up queries"
        )
        await self._report_progress(
            3,
            ResearchProgressType.GAP_ANALYSIS_COMPLETE,
            f"Identified {len(follow_up_queries)} follow-up queries",
            follow_up_queries=follow_up_queries if follow_up_queries else None,
            duration_ms=duration_ms,
        )

        return follow_up_queries, step, 1

    async def _step_follow_up_retrieve(
        self, queries: list[str], initial_count: int
    ) -> tuple[list[SearchResult], ResearchStep]:
        """Execute the follow-up retrieval step.

        Returns:
            Tuple of (search_results, trace_step).
        """
        self._check_cancelled("follow_up_retrieval")
        start_time = time.time()

        results = await self._targeted_retrieve(queries)
        duration_ms = int((time.time() - start_time) * 1000)

        step = ResearchStep(
            step_type=ResearchStepType.RETRIEVAL,
            description=f"Follow-up retrieved {len(results)} chunks",
            duration_ms=duration_ms,
        )

        logger.info(f"Follow-up retrieval found {len(results)} chunks")
        await self._report_progress(
            4,
            ResearchProgressType.FOLLOWUP_COMPLETE,
            f"Follow-up retrieved {len(results)} additional chunks",
            chunks_retrieved=initial_count + len(results),
            duration_ms=duration_ms,
        )

        return results, step

    async def _step_synthesize(
        self,
        question: str,
        sub_questions: list[SubQuestion],
        results: list[SearchResult],
    ) -> tuple[str, ResearchStep, int]:
        """Execute the synthesis step.

        Returns:
            Tuple of (answer, trace_step, llm_call_count).
        """
        # Notify synthesis is starting (it's the longest step)
        await self._report_progress(
            4,
            ResearchProgressType.SYNTHESIS_STARTED,
            f"Synthesizing answer from {len(results)} chunks...",
            chunks_retrieved=len(results),
        )

        self._check_cancelled("synthesis")
        start_time = time.time()

        answer = await self._synthesize(question, sub_questions, results)
        duration_ms = int((time.time() - start_time) * 1000)

        step = ResearchStep(
            step_type=ResearchStepType.SYNTHESIS,
            description=f"Synthesized answer from {len(results)} chunks",
            duration_ms=duration_ms,
        )

        logger.info("Synthesis complete")

        return answer, step, 1
