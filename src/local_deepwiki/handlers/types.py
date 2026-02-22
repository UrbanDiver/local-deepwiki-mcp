"""TypedDict definitions for high-traffic handler return shapes."""

from __future__ import annotations

from typing import TypedDict


class SearchResult(TypedDict):
    """Shape returned by ``RepositoryIndexer.search()`` for each result."""

    file_path: str
    name: str
    type: str
    language: str
    lines: str
    score: float
    content: str
    docstring: str | None


class ResearchSubQuestion(TypedDict):
    """Sub-question entry in a research result."""

    question: str
    category: str


class ResearchSource(TypedDict):
    """Source entry in a research result."""

    file: str
    lines: str
    type: str
    name: str
    relevance: float


class ResearchTraceStep(TypedDict):
    """Trace step in a research result."""

    step: str
    description: str
    duration_ms: int


class ResearchStats(TypedDict):
    """Statistics in a research result."""

    chunks_analyzed: int
    llm_calls: int


class ResearchResult(TypedDict):
    """Shape returned by ``_format_research_results()``."""

    question: str
    answer: str
    sub_questions: list[ResearchSubQuestion]
    sources: list[ResearchSource]
    research_trace: list[ResearchTraceStep]
    stats: ResearchStats


class SecretFinding(TypedDict):
    """A single secret finding entry."""

    type: str
    line: int
    confidence: float
    recommendation: str


class SecretFileFinding(TypedDict):
    """Per-file secret findings."""

    file_path: str
    is_test_file: bool
    secrets: list[SecretFinding]


class SecretScanResult(TypedDict):
    """Shape returned by ``handle_detect_secrets()``."""

    status: str
    files_with_secrets: int
    total_findings: int
    exclude_tests: bool
    findings: list[SecretFileFinding]
