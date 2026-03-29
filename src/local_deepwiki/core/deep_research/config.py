"""Configuration dataclass for the deep research pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
