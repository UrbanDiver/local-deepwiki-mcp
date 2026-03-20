"""Agentic RAG: relevance grading and query rewriting for ask_question.

Opt-in enhancement that adds a retrieve-grade-rewrite loop:
1. Retrieve chunks (normal vector search)
2. Grade relevance via a single LLM call
3. If <50% chunks are relevant, rewrite the query and re-retrieve
4. Return the combined high-quality results

Cost: 1 extra LLM call (grading) always; 1 more (rewrite) only if needed.
Default off — enabled via `agentic_rag=True` on ask_question.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.models.chunks import SearchResult
    from local_deepwiki.providers.base import LLMProvider

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GradedChunk:
    """A search result with its relevance grade."""

    chunk: SearchResult
    grade: str  # "relevant", "partial", "irrelevant"


@dataclass(frozen=True, slots=True)
class AgenticRetrievalResult:
    """Result of the agentic retrieval process."""

    results: list[SearchResult]
    graded: list[GradedChunk]
    rewritten_query: str | None
    metadata: dict[str, Any]


async def grade_relevance(
    results: list[SearchResult],
    question: str,
    llm: LLMProvider,
) -> list[GradedChunk]:
    """Grade the relevance of search results to the question.

    Makes a single LLM call to grade all chunks at once.

    Args:
        results: Search results from vector store.
        question: The original user question.
        llm: LLM provider instance.

    Returns:
        List of GradedChunk with relevance grades.
    """
    if not results:
        return []

    # Build a compact prompt for grading
    chunk_summaries = []
    for i, r in enumerate(results):
        chunk = r.chunk
        preview = chunk.content[:200].replace("\n", " ")
        chunk_summaries.append(
            f"[{i}] {chunk.file_path}:{chunk.start_line} — {preview}"
        )

    prompt = f"""Grade the relevance of each code chunk to this question: "{question}"

Chunks:
{chr(10).join(chunk_summaries)}

Respond with a JSON array of grades, one per chunk. Each grade must be exactly one of: "relevant", "partial", "irrelevant".
Example: ["relevant", "irrelevant", "partial"]

JSON array:"""

    system_prompt = (
        "You are a relevance grading assistant. "
        "Output only a JSON array of grade strings, nothing else."
    )

    try:
        response = await llm.generate(prompt, system_prompt=system_prompt)
        # Parse the JSON response
        grades = json.loads(response.strip())
        if not isinstance(grades, list) or len(grades) != len(results):
            logger.warning(
                "Grade response length mismatch: got %d, expected %d",
                len(grades) if isinstance(grades, list) else 0,
                len(results),
            )
            # Fall back: treat all as relevant
            return [GradedChunk(chunk=r, grade="relevant") for r in results]

        valid_grades = {"relevant", "partial", "irrelevant"}
        return [
            GradedChunk(
                chunk=r,
                grade=g if g in valid_grades else "relevant",
            )
            for r, g in zip(results, grades)
        ]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("Failed to parse relevance grades: %s", e)
        # Fall back: treat all as relevant
        return [GradedChunk(chunk=r, grade="relevant") for r in results]
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM grading failed: %s", e)
        return [GradedChunk(chunk=r, grade="relevant") for r in results]


async def rewrite_query(
    question: str,
    context_summary: str,
    gaps: str,
    llm: LLMProvider,
) -> str:
    """Rewrite a query to better target missing information.

    Args:
        question: Original question.
        context_summary: Summary of what was already found.
        gaps: Description of what's missing.
        llm: LLM provider instance.

    Returns:
        Rewritten query string.
    """
    prompt = f"""The user asked: "{question}"

What was found so far: {context_summary}
What's missing: {gaps}

Rewrite the question to better find the missing information. Output only the rewritten question, nothing else."""

    system_prompt = (
        "You are a query rewriting assistant. Output only the rewritten question."
    )

    try:
        rewritten = await llm.generate(prompt, system_prompt=system_prompt)
        rewritten = rewritten.strip().strip('"')
        if rewritten:
            return rewritten
    except Exception as e:  # noqa: BLE001
        logger.warning("Query rewrite failed: %s", e)

    return question  # Fall back to original


def _grade_and_filter_results(
    graded: list[GradedChunk],
    relevant_count: int,
) -> tuple[str, str]:
    """Summarise what was found and describe the gaps for query rewriting.

    Args:
        graded: Graded chunks from the first retrieval round.
        relevant_count: Number of chunks graded as "relevant".

    Returns:
        Tuple of (context_summary, gaps) strings for use in query rewriting.
    """
    relevant_files = [g.chunk.chunk.file_path for g in graded if g.grade == "relevant"]
    irrelevant_files = [
        g.chunk.chunk.file_path for g in graded if g.grade == "irrelevant"
    ]
    context_summary = (
        f"Found {relevant_count} relevant chunks in: {', '.join(relevant_files[:5])}"
        if relevant_files
        else "No clearly relevant code found"
    )
    gaps = (
        f"Most results were irrelevant (from: {', '.join(irrelevant_files[:5])}). "
        "Need more targeted results."
    )
    return context_summary, gaps


def _merge_graded_results(
    first_graded: list[GradedChunk],
    new_graded: list[GradedChunk],
    max_context: int,
) -> list[GradedChunk]:
    """Merge two rounds of graded results, deduplicating by file+line.

    Relevant chunks from both rounds come first; irrelevant chunks from
    the first round are appended as a fallback.

    Args:
        first_graded: Graded results from the initial retrieval.
        new_graded: Graded results from the rewritten-query retrieval.
        max_context: Maximum number of chunks to return.

    Returns:
        Merged, deduplicated list capped at *max_context*.
    """
    seen: set[str] = set()
    merged: list[GradedChunk] = []

    for g in first_graded + new_graded:
        key = f"{g.chunk.chunk.file_path}:{g.chunk.chunk.start_line}"
        if key not in seen and g.grade != "irrelevant":
            seen.add(key)
            merged.append(g)

    for g in first_graded:
        key = f"{g.chunk.chunk.file_path}:{g.chunk.chunk.start_line}"
        if key not in seen:
            seen.add(key)
            merged.append(g)

    return merged[:max_context]


async def agentic_retrieve(
    question: str,
    vector_store: VectorStore,
    llm: LLMProvider,
    *,
    max_context: int = 15,
    relevance_threshold: float = 0.5,
) -> AgenticRetrievalResult:
    """Perform agentic retrieval: retrieve, grade, optionally rewrite and re-retrieve.

    Args:
        question: User question.
        vector_store: Vector store for search.
        llm: LLM provider for grading and rewriting.
        max_context: Maximum chunks to retrieve.
        relevance_threshold: Fraction of chunks that must be relevant to skip rewrite.

    Returns:
        AgenticRetrievalResult with graded results and metadata.
    """
    initial_results = await vector_store.search(question, limit=max_context)

    if not initial_results:
        return AgenticRetrievalResult(
            results=[],
            graded=[],
            rewritten_query=None,
            metadata={"rounds": 1, "initial_count": 0, "rewritten": False},
        )

    graded = await grade_relevance(initial_results, question, llm)

    relevant_count = sum(1 for g in graded if g.grade == "relevant")
    relevant_fraction = relevant_count / len(graded) if graded else 0

    rewritten_query = None

    if relevant_fraction < relevance_threshold and len(graded) > 0:
        context_summary, gaps = _grade_and_filter_results(graded, relevant_count)
        rewritten_query = await rewrite_query(question, context_summary, gaps, llm)

        if rewritten_query != question:
            new_results = await vector_store.search(rewritten_query, limit=max_context)
            new_graded = await grade_relevance(new_results, question, llm)
            graded = _merge_graded_results(graded, new_graded, max_context)

    final_results = [g.chunk for g in graded]

    return AgenticRetrievalResult(
        results=final_results,
        graded=graded,
        rewritten_query=rewritten_query,
        metadata={
            "rounds": 2 if rewritten_query else 1,
            "initial_count": len(initial_results),
            "relevant_count": relevant_count,
            "relevant_fraction": round(relevant_fraction, 3),
            "rewritten": rewritten_query is not None,
        },
    )
