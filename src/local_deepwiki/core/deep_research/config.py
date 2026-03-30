"""Configuration and parameter dataclasses for the deep research pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.models import (
        ResearchCheckpointStep,
        ResearchStep,
        SearchResult,
        SubQuestion,
    )


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    """Immutable configuration for DeepResearchPipeline.

    Consolidates the 12 keyword arguments of ``__init__`` into a single object.
    """

    max_sub_questions: int = 4
    chunks_per_subquestion: int = 5
    max_total_chunks: int = 30
    max_follow_up_queries: int = 3
    synthesis_temperature: float = 0.5
    synthesis_max_tokens: int = 4096
    decomposition_prompt: str | None = None
    gap_analysis_prompt: str | None = None
    synthesis_prompt: str | None = None
    repo_path: Path | None = None


@dataclass(frozen=True, slots=True)
class CheckpointData:
    """Immutable snapshot of data to persist in a checkpoint save."""

    step: ResearchCheckpointStep
    sub_questions: list[SubQuestion] | None = None
    retrieved_contexts: dict[str, list[dict]] | None = None
    follow_up_queries: list[str] | None = None
    follow_up_contexts: list[dict] | None = None
    partial_synthesis: str | None = None
    error: str | None = None
    completed_step: str | None = None


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    """Immutable result of the research synthesis step.

    Bundles all the data needed by :meth:`_finalize_research` to produce
    the final :class:`DeepResearchResult`.
    """

    question: str
    answer: str
    sub_questions: list[SubQuestion]
    all_results: list[SearchResult]
    trace: list[ResearchStep]
    llm_calls: int
