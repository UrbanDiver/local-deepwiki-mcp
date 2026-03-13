"""Tests for RAGTrace: structured observability for the RAG pipeline."""

from __future__ import annotations

import time

from local_deepwiki.core.tracing import RAGTrace
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


def _make_result(score: float = 0.9) -> SearchResult:
    chunk = CodeChunk(
        id="c1",
        file_path="src/main.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name="func",
        content="def func(): pass",
        start_line=1,
        end_line=3,
    )
    return SearchResult(chunk=chunk, score=score, highlights=[])


class TestRAGTraceCreation:
    def test_default_values(self):
        trace = RAGTrace(query="test")
        assert trace.query == "test"
        assert trace.retrieval_chunks == 0
        assert trace.reranking_enabled is False
        assert trace.agentic_rag_enabled is False
        assert trace.total_time_ms == 0.0

    def test_start_time_is_set(self):
        before = time.monotonic()
        trace = RAGTrace(query="q")
        after = time.monotonic()
        assert before <= trace.start_time <= after


class TestRecordRetrieval:
    def test_records_chunk_count_and_scores(self):
        trace = RAGTrace(query="q")
        results = [_make_result(0.95), _make_result(0.80)]
        trace.record_retrieval(results, 42.5)

        assert trace.retrieval_chunks == 2
        assert trace.retrieval_scores == [0.95, 0.8]
        assert trace.retrieval_time_ms == 42.5
        assert trace.search_mode == "vector"

    def test_records_search_mode(self):
        trace = RAGTrace(query="q")
        trace.record_retrieval([], 1.0, search_mode="hybrid")
        assert trace.search_mode == "hybrid"

    def test_empty_results(self):
        trace = RAGTrace(query="q")
        trace.record_retrieval([], 0.0)
        assert trace.retrieval_chunks == 0
        assert trace.retrieval_scores == []


class TestRecordReranking:
    def test_records_reranking_info(self):
        trace = RAGTrace(query="q")
        results = [_make_result(0.99)]
        trace.record_reranking(results, 15.3, "cross-encoder/ms-marco-MiniLM-L-6-v2")

        assert trace.reranking_enabled is True
        assert trace.reranking_model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert trace.reranking_time_ms == 15.3
        assert trace.reranked_scores == [0.99]


class TestRecordContext:
    def test_records_context_info(self):
        trace = RAGTrace(query="q")
        trace.record_context(5, 12000)
        assert trace.context_chunks_used == 5
        assert trace.context_total_chars == 12000


class TestRecordLLM:
    def test_records_llm_info(self):
        trace = RAGTrace(query="q")
        trace.record_llm(200.5, model="claude-3")
        assert trace.llm_time_ms == 200.5
        assert trace.llm_model == "claude-3"

    def test_records_without_model(self):
        trace = RAGTrace(query="q")
        trace.record_llm(100.0)
        assert trace.llm_model == ""


class TestToDict:
    def test_includes_query_and_total(self):
        trace = RAGTrace(query="What is X?")
        d = trace.to_dict()
        assert d["query"] == "What is X?"
        assert "total_time_ms" in d

    def test_includes_retrieval(self):
        trace = RAGTrace(query="q")
        trace.record_retrieval([_make_result()], 10.0)
        d = trace.to_dict()
        assert d["retrieval"]["chunks"] == 1
        assert d["retrieval"]["time_ms"] == 10.0

    def test_excludes_reranking_when_disabled(self):
        trace = RAGTrace(query="q")
        d = trace.to_dict()
        assert "reranking" not in d

    def test_includes_reranking_when_enabled(self):
        trace = RAGTrace(query="q")
        trace.record_reranking([_make_result()], 5.0, "model-x")
        d = trace.to_dict()
        assert "reranking" in d
        assert d["reranking"]["model"] == "model-x"

    def test_excludes_agentic_when_disabled(self):
        trace = RAGTrace(query="q")
        d = trace.to_dict()
        assert "agentic_rag" not in d

    def test_includes_agentic_when_enabled(self):
        trace = RAGTrace(query="q")
        trace.agentic_rag_enabled = True
        trace.agentic_time_ms = 300.0
        trace.agentic_rewritten_query = "Better query"
        d = trace.to_dict()
        assert d["agentic_rag"]["time_ms"] == 300.0
        assert d["agentic_rag"]["rewritten_query"] == "Better query"

    def test_excludes_context_when_zero(self):
        trace = RAGTrace(query="q")
        d = trace.to_dict()
        assert "context" not in d

    def test_includes_context_when_nonzero(self):
        trace = RAGTrace(query="q")
        trace.record_context(3, 5000)
        d = trace.to_dict()
        assert d["context"]["chunks_used"] == 3

    def test_excludes_llm_when_zero(self):
        trace = RAGTrace(query="q")
        d = trace.to_dict()
        assert "llm" not in d

    def test_includes_llm_when_nonzero(self):
        trace = RAGTrace(query="q")
        trace.record_llm(150.0, model="gpt-4")
        d = trace.to_dict()
        assert d["llm"]["time_ms"] == 150.0
        assert d["llm"]["model"] == "gpt-4"

    def test_finish_stamps_total_time(self):
        trace = RAGTrace(query="q")
        trace.start_time = time.monotonic() - 0.1  # 100ms ago
        d = trace.to_dict()
        assert d["total_time_ms"] >= 90  # allow some tolerance


class TestFullPipelineTrace:
    def test_complete_trace_has_all_sections(self):
        trace = RAGTrace(query="How does auth work?")
        trace.record_retrieval([_make_result(0.9), _make_result(0.7)], 25.0)
        trace.record_reranking([_make_result(0.95)], 8.0, "reranker-v1")
        trace.record_context(1, 2000)
        trace.record_llm(180.0, model="claude-3")

        d = trace.to_dict()

        assert d["query"] == "How does auth work?"
        assert d["total_time_ms"] > 0
        assert d["retrieval"]["chunks"] == 2
        assert d["reranking"]["model"] == "reranker-v1"
        assert d["context"]["chunks_used"] == 1
        assert d["llm"]["model"] == "claude-3"
