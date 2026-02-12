"""Tests for agentic RAG enhancement (Phase 5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.core.agentic_rag import (
    AgenticRetrievalResult,
    GradedChunk,
    agentic_retrieve,
    grade_relevance,
    rewrite_query,
)


def _make_search_result(
    file_path: str = "src/main.py",
    start_line: int = 1,
    content: str = "def foo(): pass",
) -> Any:
    """Create a mock SearchResult."""
    chunk = MagicMock()
    chunk.file_path = file_path
    chunk.start_line = start_line
    chunk.end_line = start_line + 5
    chunk.content = content
    chunk.chunk_type = MagicMock()
    chunk.chunk_type.value = "function"

    result = MagicMock()
    result.chunk = chunk
    result.score = 0.85
    return result


class TestGradeRelevance:
    """Tests for grade_relevance."""

    async def test_empty_results(self) -> None:
        llm = AsyncMock()
        graded = await grade_relevance([], "question", llm)
        assert graded == []
        llm.generate.assert_not_called()

    async def test_all_relevant(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = '["relevant", "relevant"]'

        results = [_make_search_result("a.py"), _make_search_result("b.py")]
        graded = await grade_relevance(results, "How does auth work?", llm)

        assert len(graded) == 2
        assert all(g.grade == "relevant" for g in graded)
        llm.generate.assert_called_once()

    async def test_mixed_grades(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = '["relevant", "irrelevant", "partial"]'

        results = [_make_search_result(f"{i}.py") for i in range(3)]
        graded = await grade_relevance(results, "question", llm)

        assert graded[0].grade == "relevant"
        assert graded[1].grade == "irrelevant"
        assert graded[2].grade == "partial"

    async def test_invalid_json_fallback(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "not valid json"

        results = [_make_search_result()]
        graded = await grade_relevance(results, "question", llm)

        # Should fall back to all relevant
        assert len(graded) == 1
        assert graded[0].grade == "relevant"

    async def test_length_mismatch_fallback(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = '["relevant"]'  # Only 1, but 2 results

        results = [_make_search_result(), _make_search_result()]
        graded = await grade_relevance(results, "question", llm)

        # Should fall back to all relevant
        assert len(graded) == 2
        assert all(g.grade == "relevant" for g in graded)

    async def test_llm_failure_fallback(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM unavailable")

        results = [_make_search_result()]
        graded = await grade_relevance(results, "question", llm)

        assert len(graded) == 1
        assert graded[0].grade == "relevant"

    async def test_invalid_grade_values(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = '["relevant", "unknown_grade"]'

        results = [_make_search_result(), _make_search_result()]
        graded = await grade_relevance(results, "question", llm)

        assert graded[0].grade == "relevant"
        assert graded[1].grade == "relevant"  # Unknown maps to relevant


class TestRewriteQuery:
    """Tests for rewrite_query."""

    async def test_successful_rewrite(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = (
            "How does the authentication middleware validate JWT tokens?"
        )

        rewritten = await rewrite_query(
            "How does auth work?",
            "Found some auth-related files",
            "Missing JWT validation logic",
            llm,
        )

        assert (
            rewritten == "How does the authentication middleware validate JWT tokens?"
        )

    async def test_strips_quotes(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = '"What is the auth flow?"'

        rewritten = await rewrite_query("auth?", "context", "gaps", llm)
        assert rewritten == "What is the auth flow?"

    async def test_llm_failure_returns_original(self) -> None:
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("fail")

        rewritten = await rewrite_query("original question", "context", "gaps", llm)
        assert rewritten == "original question"

    async def test_empty_response_returns_original(self) -> None:
        llm = AsyncMock()
        llm.generate.return_value = "   "

        rewritten = await rewrite_query("original", "ctx", "gaps", llm)
        assert rewritten == "original"


class TestAgenticRetrieve:
    """Tests for the full agentic retrieval pipeline."""

    async def test_high_quality_no_rewrite(self) -> None:
        """When most results are relevant, no rewrite should happen."""
        vector_store = AsyncMock()
        llm = AsyncMock()

        search_results = [_make_search_result(f"{i}.py") for i in range(5)]
        vector_store.search.return_value = search_results

        # All relevant
        llm.generate.return_value = json.dumps(["relevant"] * 5)

        result = await agentic_retrieve("question", vector_store, llm, max_context=5)

        assert isinstance(result, AgenticRetrievalResult)
        assert len(result.results) == 5
        assert result.rewritten_query is None
        assert result.metadata["rewritten"] is False
        assert result.metadata["rounds"] == 1

    async def test_low_quality_triggers_rewrite(self) -> None:
        """When few results are relevant, rewrite should be triggered."""
        vector_store = AsyncMock()
        llm = AsyncMock()

        initial_results = [_make_search_result(f"init_{i}.py") for i in range(5)]
        rewrite_results = [_make_search_result(f"rewrite_{i}.py") for i in range(5)]

        call_count = 0

        async def mock_search(query, limit=10):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return initial_results
            return rewrite_results

        vector_store.search = mock_search

        # First call: grade as mostly irrelevant
        # Second call (rewrite query): return rewritten text
        # Third call: grade new results as relevant
        call_idx = 0

        async def mock_generate(prompt, system_prompt=None):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                # Grade initial: only 1 relevant out of 5
                return json.dumps(
                    ["relevant", "irrelevant", "irrelevant", "irrelevant", "irrelevant"]
                )
            if call_idx == 2:
                # Rewrite
                return "Better question about the topic"
            if call_idx == 3:
                # Grade rewritten results
                return json.dumps(
                    ["relevant", "relevant", "relevant", "relevant", "partial"]
                )
            return "[]"

        llm.generate = mock_generate

        result = await agentic_retrieve(
            "vague question", vector_store, llm, max_context=10
        )

        assert result.rewritten_query == "Better question about the topic"
        assert result.metadata["rewritten"] is True
        assert result.metadata["rounds"] == 2

    async def test_empty_results(self) -> None:
        """When vector store returns nothing, should return empty."""
        vector_store = AsyncMock()
        llm = AsyncMock()
        vector_store.search.return_value = []

        result = await agentic_retrieve("question", vector_store, llm)

        assert result.results == []
        assert result.metadata["initial_count"] == 0

    async def test_grading_failure_continues(self) -> None:
        """If grading fails, should fall back to ungraded results."""
        vector_store = AsyncMock()
        llm = AsyncMock()

        search_results = [_make_search_result(f"{i}.py") for i in range(3)]
        vector_store.search.return_value = search_results

        # LLM fails
        llm.generate.side_effect = RuntimeError("LLM error")

        result = await agentic_retrieve("question", vector_store, llm)

        # Should still return results (all graded as "relevant" via fallback)
        assert len(result.results) == 3
        assert all(g.grade == "relevant" for g in result.graded)
        # No rewrite because all marked relevant via fallback
        assert result.metadata["rewritten"] is False


class TestGradedChunkFrozen:
    """Tests for GradedChunk dataclass."""

    def test_frozen(self) -> None:
        chunk = _make_search_result()
        graded = GradedChunk(chunk=chunk, grade="relevant")
        with pytest.raises(AttributeError):
            graded.grade = "irrelevant"

    def test_fields(self) -> None:
        chunk = _make_search_result()
        graded = GradedChunk(chunk=chunk, grade="partial")
        assert graded.grade == "partial"
        assert graded.chunk is chunk
