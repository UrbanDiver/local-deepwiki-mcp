"""Tests for CrossEncoderReranker and get_reranker factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.core.reranker import CrossEncoderReranker, Reranker, get_reranker
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


def _make_result(score: float = 0.9, name: str = "func") -> SearchResult:
    chunk = CodeChunk(
        id=f"c-{name}",
        file_path="src/main.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name=name,
        content=f"def {name}(): pass",
        start_line=1,
        end_line=3,
    )
    return SearchResult(chunk=chunk, score=score, highlights=[])


class TestGetReranker:
    def test_returns_none_when_model_is_none(self):
        assert get_reranker(None) is None

    def test_returns_none_when_model_is_empty(self):
        assert get_reranker("") is None

    def test_returns_reranker_when_model_specified(self):
        reranker = get_reranker("cross-encoder/ms-marco-MiniLM-L-6-v2")
        assert reranker is not None
        assert isinstance(reranker, CrossEncoderReranker)

    def test_reranker_has_model_name(self):
        reranker = get_reranker("my-model")
        assert reranker is not None
        assert reranker.model_name == "my-model"


class TestCrossEncoderReranker:
    def test_model_name_property(self):
        reranker = CrossEncoderReranker("test-model")
        assert reranker.model_name == "test-model"

    def test_default_model_name(self):
        reranker = CrossEncoderReranker()
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    async def test_rerank_empty_results(self):
        reranker = CrossEncoderReranker("test-model")
        result = await reranker.rerank("query", [])
        assert result == []

    async def test_rerank_reorders_by_score(self):
        reranker = CrossEncoderReranker("test-model")
        results = [
            _make_result(0.5, "low"),
            _make_result(0.8, "mid"),
            _make_result(0.3, "lowest"),
        ]

        # Mock the model to return specific cross-encoder scores
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.2, 0.9, 0.5]  # mid gets highest
        reranker._model = mock_model

        reranked = await reranker.rerank("test query", results)

        assert len(reranked) == 3
        assert reranked[0].chunk.name == "mid"  # highest cross-encoder score
        assert reranked[1].chunk.name == "lowest"
        assert reranked[2].chunk.name == "low"

    async def test_rerank_respects_top_k(self):
        reranker = CrossEncoderReranker("test-model")
        results = [
            _make_result(0.9, "a"),
            _make_result(0.8, "b"),
            _make_result(0.7, "c"),
        ]

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.8, 0.7]
        reranker._model = mock_model

        reranked = await reranker.rerank("query", results, top_k=2)

        assert len(reranked) == 2

    async def test_rerank_updates_scores_to_cross_encoder_scores(self):
        reranker = CrossEncoderReranker("test-model")
        results = [_make_result(0.5, "func")]

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.95]
        reranker._model = mock_model

        reranked = await reranker.rerank("query", results)

        assert reranked[0].score == 0.95  # cross-encoder score, not original

    async def test_rerank_preserves_highlights(self):
        reranker = CrossEncoderReranker("test-model")
        chunk = CodeChunk(
            id="c1",
            file_path="a.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="f",
            content="code",
            start_line=1,
            end_line=2,
        )
        results = [SearchResult(chunk=chunk, score=0.5, highlights=["match1"])]

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8]
        reranker._model = mock_model

        reranked = await reranker.rerank("query", results)

        assert reranked[0].highlights == ["match1"]

    async def test_lazy_model_loading_raises_without_sentence_transformers(self):
        reranker = CrossEncoderReranker("test-model")

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers"):
                reranker._ensure_model()

    def test_implements_protocol(self):
        reranker = CrossEncoderReranker()
        assert isinstance(reranker, Reranker)


class TestRerankerIntegrationWithQueryService:
    """Test that reranker integrates correctly with QueryService."""

    async def test_debug_false_no_trace(self, tmp_path):
        """When debug=False, no trace is returned."""
        from local_deepwiki.services.query_service import QueryService

        vector_store = MagicMock()
        vector_store.search = AsyncMock(return_value=[_make_result()])

        llm_provider = AsyncMock()
        llm_provider.generate = AsyncMock(return_value="Answer")

        config = MagicMock()
        config.search.reranker_model = None
        config.get_wiki_path.return_value = tmp_path

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            result = await svc.answer_question(
                repo_path=tmp_path, question="What?", debug=False
            )

        assert result.trace is None

    async def test_debug_true_includes_trace(self, tmp_path):
        """When debug=True, trace is populated."""
        from local_deepwiki.services.query_service import QueryService

        vector_store = MagicMock()
        vector_store.search = AsyncMock(return_value=[_make_result()])

        llm_provider = AsyncMock()
        llm_provider.generate = AsyncMock(return_value="Answer")

        config = MagicMock()
        config.search.reranker_model = None
        config.get_wiki_path.return_value = tmp_path

        svc = QueryService(vector_store, llm_provider, config)

        with patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl:
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            result = await svc.answer_question(
                repo_path=tmp_path, question="What?", debug=True
            )

        assert result.trace is not None
        assert result.trace["query"] == "What?"
        assert result.trace["retrieval"]["chunks"] == 1
        assert result.trace["total_time_ms"] > 0

    async def test_reranker_enabled_in_trace(self, tmp_path):
        """When reranker is configured and debug=True, reranking section appears."""
        from local_deepwiki.services.query_service import QueryService

        results = [_make_result(0.9, "a"), _make_result(0.7, "b")]
        vector_store = MagicMock()
        vector_store.search = AsyncMock(return_value=results)

        llm_provider = AsyncMock()
        llm_provider.generate = AsyncMock(return_value="Answer")

        config = MagicMock()
        config.search.reranker_model = "test-reranker"
        config.get_wiki_path.return_value = tmp_path

        mock_reranker = MagicMock()
        mock_reranker.model_name = "test-reranker"
        mock_reranker.rerank = AsyncMock(return_value=[_make_result(0.95)])

        svc = QueryService(vector_store, llm_provider, config)

        with (
            patch("local_deepwiki.services.query_service.get_rate_limiter") as mock_rl,
            patch(
                "local_deepwiki.core.reranker.get_reranker",
                return_value=mock_reranker,
            ),
        ):
            mock_rl.return_value.__aenter__ = AsyncMock()
            mock_rl.return_value.__aexit__ = AsyncMock()
            result = await svc.answer_question(
                repo_path=tmp_path,
                question="What?",
                max_context=1,
                debug=True,
            )

        assert result.trace is not None
        assert "reranking" in result.trace
        assert result.trace["reranking"]["model"] == "test-reranker"
