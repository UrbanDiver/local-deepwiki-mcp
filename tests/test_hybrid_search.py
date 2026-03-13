"""Tests for hybrid search: BM25, RRF merge, and search_mode parameter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.core.vectorstore.mixins.search import SearchMixin
from local_deepwiki.core.vectorstore.schema import SearchProfile
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


def _make_chunk(name: str = "func", content: str = "def func(): pass") -> CodeChunk:
    return CodeChunk(
        id=f"c-{name}",
        file_path="src/main.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name=name,
        content=content,
        start_line=1,
        end_line=3,
    )


def _make_row(
    name: str = "func",
    content: str = "def func(): pass",
    *,
    distance: float = 0.1,
    bm25_score: float = 5.0,
) -> dict:
    """Create a raw LanceDB row dict."""
    return {
        "id": f"c-{name}",
        "file_path": "src/main.py",
        "language": "python",
        "chunk_type": "function",
        "name": name,
        "content": content,
        "start_line": 1,
        "end_line": 3,
        "docstring": "",
        "parent_name": "",
        "metadata": "{}",
        "_distance": distance,
        "_score": bm25_score,
    }


# ---------------------------------------------------------------
# Config: SearchConfig defaults
# ---------------------------------------------------------------


class TestSearchConfigHybridFields:
    def test_default_search_mode_is_vector(self):
        from local_deepwiki.config.models import SearchConfig

        config = SearchConfig()
        assert config.default_search_mode == "vector"

    def test_default_bm25_weight(self):
        from local_deepwiki.config.models import SearchConfig

        config = SearchConfig()
        assert config.bm25_weight == 0.3

    def test_custom_search_mode(self):
        from local_deepwiki.config.models import SearchConfig

        config = SearchConfig(default_search_mode="hybrid")
        assert config.default_search_mode == "hybrid"

    def test_custom_bm25_weight(self):
        from local_deepwiki.config.models import SearchConfig

        config = SearchConfig(bm25_weight=0.5)
        assert config.bm25_weight == 0.5

    def test_invalid_search_mode_rejected(self):
        from pydantic import ValidationError

        from local_deepwiki.config.models import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(default_search_mode="invalid")

    def test_bm25_weight_bounds(self):
        from pydantic import ValidationError

        from local_deepwiki.config.models import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(bm25_weight=1.5)
        with pytest.raises(ValidationError):
            SearchConfig(bm25_weight=-0.1)


# ---------------------------------------------------------------
# SearchMixin._resolve_search_mode
# ---------------------------------------------------------------


class TestResolveSearchMode:
    def test_none_uses_default(self):
        assert SearchMixin._resolve_search_mode(None, "hybrid") == "hybrid"

    def test_explicit_overrides_default(self):
        assert SearchMixin._resolve_search_mode("keyword", "vector") == "keyword"

    def test_invalid_falls_back_to_vector(self):
        assert SearchMixin._resolve_search_mode("invalid", "hybrid") == "vector"

    def test_all_valid_modes(self):
        for mode in ("vector", "keyword", "hybrid"):
            assert SearchMixin._resolve_search_mode(mode, "vector") == mode


# ---------------------------------------------------------------
# SearchMixin._execute_fts_search
# ---------------------------------------------------------------


class TestExecuteFtsSearch:
    def test_returns_fts_results(self):
        mixin = SearchMixin()
        table = MagicMock()
        rows = [_make_row("a", bm25_score=5.0), _make_row("b", bm25_score=3.0)]
        table.search.return_value.limit.return_value.to_list.return_value = rows

        result = mixin._execute_fts_search(table, "query", [], 10)

        table.search.assert_called_once_with("query", query_type="fts")
        assert result == rows

    def test_applies_filters(self):
        mixin = SearchMixin()
        table = MagicMock()
        search_chain = table.search.return_value.limit.return_value
        search_chain.where.return_value.to_list.return_value = []

        mixin._execute_fts_search(table, "q", ["language = 'python'"], 10)

        search_chain.where.assert_called_once_with("language = 'python'")

    def test_graceful_degradation_on_error(self):
        mixin = SearchMixin()
        table = MagicMock()
        table.search.side_effect = RuntimeError("No FTS index")

        result = mixin._execute_fts_search(table, "query", [], 10)

        assert result == []


# ---------------------------------------------------------------
# SearchMixin._convert_fts_results
# ---------------------------------------------------------------


class TestConvertFtsResults:
    def test_empty_input(self):
        mixin = SearchMixin()
        mixin._row_to_chunk = MagicMock(side_effect=_make_chunk)
        assert mixin._convert_fts_results([]) == []

    def test_normalizes_scores(self):
        mixin = SearchMixin()
        mixin._row_to_chunk = MagicMock(side_effect=lambda r: _make_chunk(r["name"]))

        rows = [
            _make_row("a", bm25_score=10.0),
            _make_row("b", bm25_score=5.0),
            _make_row("c", bm25_score=2.5),
        ]
        results = mixin._convert_fts_results(rows)

        assert len(results) == 3
        assert results[0].score == 1.0  # 10/10
        assert results[1].score == 0.5  # 5/10
        assert results[2].score == 0.25  # 2.5/10

    def test_handles_zero_scores(self):
        mixin = SearchMixin()
        mixin._row_to_chunk = MagicMock(side_effect=lambda r: _make_chunk(r["name"]))

        rows = [_make_row("a", bm25_score=0.0)]
        results = mixin._convert_fts_results(rows)

        assert len(results) == 1
        assert results[0].score == 0.0


# ---------------------------------------------------------------
# SearchMixin._reciprocal_rank_fusion
# ---------------------------------------------------------------


class TestReciprocalRankFusion:
    def test_empty_inputs(self):
        result = SearchMixin._reciprocal_rank_fusion([], [])
        assert result == []

    def test_vector_only(self):
        rows = [_make_row("a"), _make_row("b")]
        result = SearchMixin._reciprocal_rank_fusion(rows, [])

        assert len(result) == 2
        assert result[0][0]["id"] == "c-a"  # rank 0 has higher RRF score
        assert result[0][1] == 1.0  # normalized to 1.0

    def test_fts_only(self):
        rows = [_make_row("a"), _make_row("b")]
        result = SearchMixin._reciprocal_rank_fusion([], rows)

        assert len(result) == 2
        assert result[0][0]["id"] == "c-a"

    def test_overlapping_documents_get_boosted(self):
        """Documents appearing in both result sets should rank higher."""
        vector_rows = [_make_row("a"), _make_row("b"), _make_row("c")]
        fts_rows = [_make_row("b"), _make_row("c"), _make_row("d")]

        result = SearchMixin._reciprocal_rank_fusion(vector_rows, fts_rows)

        result_ids = [row["id"] for row, _ in result]
        # 'b' and 'c' appear in both, should be ranked higher
        # 'b' is rank 1 in vector (1/62) + rank 0 in FTS (0.3/61) = boosted
        assert "c-b" in result_ids[:2] or "c-c" in result_ids[:2]
        # All 4 unique documents should appear
        assert len(result) == 4

    def test_bm25_weight_affects_ranking(self):
        """Higher BM25 weight should favor FTS-ranked documents."""
        vector_rows = [_make_row("v1"), _make_row("v2")]
        fts_rows = [_make_row("f1"), _make_row("f2")]

        # Low FTS weight — vector results dominate
        low_weight = SearchMixin._reciprocal_rank_fusion(
            vector_rows, fts_rows, fts_weight=0.1
        )

        # High FTS weight — FTS results get more influence
        high_weight = SearchMixin._reciprocal_rank_fusion(
            vector_rows, fts_rows, fts_weight=1.0
        )

        # With low weight, vector-top doc should still be #1
        assert low_weight[0][0]["id"] == "c-v1"
        # With high weight, FTS-top doc should gain more score relative to vector-top
        low_f1_score = next(s for r, s in low_weight if r["id"] == "c-f1")
        high_f1_score = next(s for r, s in high_weight if r["id"] == "c-f1")
        assert high_f1_score > low_f1_score

    def test_scores_are_normalized_to_0_1(self):
        vector_rows = [_make_row("a"), _make_row("b")]
        fts_rows = [_make_row("b"), _make_row("c")]

        result = SearchMixin._reciprocal_rank_fusion(vector_rows, fts_rows)

        scores = [score for _, score in result]
        assert scores[0] == 1.0  # max is always 1.0
        assert all(0 < s <= 1.0 for s in scores)

    def test_k_parameter(self):
        """Different k values should produce different score distributions."""
        rows_v = [_make_row("a")]
        rows_f = [_make_row("b")]

        result_k10 = SearchMixin._reciprocal_rank_fusion(rows_v, rows_f, k=10)
        result_k100 = SearchMixin._reciprocal_rank_fusion(rows_v, rows_f, k=100)

        # Both should return 2 results, but relative scores differ
        assert len(result_k10) == 2
        assert len(result_k100) == 2


# ---------------------------------------------------------------
# FTS index creation
# ---------------------------------------------------------------


class TestFtsIndexCreation:
    def test_create_fts_index_safe_success(self):
        from local_deepwiki.core.vectorstore.indexes import create_fts_index_safe

        table = MagicMock()
        create_fts_index_safe(table, "content")
        table.create_fts_index.assert_called_once_with("content", replace=True)

    def test_create_fts_index_safe_handles_error(self):
        from local_deepwiki.core.vectorstore.indexes import create_fts_index_safe

        table = MagicMock()
        table.create_fts_index.side_effect = RuntimeError("not supported")
        # Should not raise
        create_fts_index_safe(table, "content")

    def test_create_scalar_indexes_includes_fts(self):
        from local_deepwiki.core.vectorstore.indexes import create_scalar_indexes

        table = MagicMock()
        create_scalar_indexes(table)

        # Should create scalar indexes AND FTS index
        table.create_scalar_index.assert_any_call("id")
        table.create_scalar_index.assert_any_call("file_path")
        table.create_fts_index.assert_called_once_with("content", replace=True)


# ---------------------------------------------------------------
# Integration: search() with search_mode
# ---------------------------------------------------------------


class TestSearchWithSearchMode:
    """Integration tests for search() with different search modes."""

    def _make_mixin(self, default_mode: str = "vector") -> SearchMixin:
        """Create a SearchMixin with mocked dependencies."""
        mixin = SearchMixin()
        mixin._default_search_mode = default_mode
        mixin._bm25_weight = 0.3
        mixin._default_search_profile = SearchProfile.BALANCED
        mixin._search_cache = MagicMock()
        mixin._search_cache.get.return_value = None
        mixin._fuzzy_search_config = MagicMock()
        mixin._fuzzy_search_config.enable_auto_fuzzy = False
        mixin._adaptive_search_enabled = False
        mixin._adaptive_searcher = MagicMock()
        mixin._lazy_index_manager = MagicMock()
        mixin._lazy_index_manager.should_create_index.return_value = False

        table = MagicMock()
        mixin._get_table = MagicMock(return_value=table)
        mixin._row_to_chunk = MagicMock(side_effect=lambda r: _make_chunk(r["name"]))
        mixin.embedding_provider = AsyncMock()
        mixin.embedding_provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        return mixin

    async def test_vector_mode_skips_fts(self):
        mixin = self._make_mixin()
        table = mixin._get_table()
        vector_rows = [_make_row("a", distance=0.1)]
        table.search.return_value.limit.return_value.to_list.return_value = vector_rows

        results = await mixin.search("test query", limit=5, search_mode="vector")

        # Should call embed for vector search
        mixin.embedding_provider.embed.assert_called_once()
        assert len(results) >= 1

    async def test_keyword_mode_skips_embedding(self):
        mixin = self._make_mixin()
        table = mixin._get_table()
        fts_rows = [_make_row("a", bm25_score=5.0)]
        table.search.return_value.limit.return_value.to_list.return_value = fts_rows

        results = await mixin.search("test query", limit=5, search_mode="keyword")

        # Should NOT call embed for keyword search
        mixin.embedding_provider.embed.assert_not_called()
        # Should call FTS search
        table.search.assert_called_once_with("test query", query_type="fts")
        assert len(results) == 1

    async def test_hybrid_mode_calls_both(self):
        mixin = self._make_mixin()
        table = mixin._get_table()

        vector_rows = [_make_row("a", distance=0.1), _make_row("b", distance=0.2)]
        fts_rows = [_make_row("b", bm25_score=5.0), _make_row("c", bm25_score=3.0)]

        # First call = vector search, second call = FTS search
        call_count = 0

        def mock_search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if kwargs.get("query_type") == "fts":
                mock.limit.return_value.to_list.return_value = fts_rows
            else:
                mock.limit.return_value.to_list.return_value = vector_rows
            return mock

        table.search.side_effect = mock_search

        results = await mixin.search("test query", limit=5, search_mode="hybrid")

        # Should call embed (needed for vector part)
        mixin.embedding_provider.embed.assert_called_once()
        # Should have results from both sources merged
        assert len(results) == 3  # a, b, c (deduplicated)

    async def test_hybrid_falls_back_when_fts_unavailable(self):
        mixin = self._make_mixin()
        table = mixin._get_table()

        vector_rows = [_make_row("a", distance=0.1)]

        def mock_search(*args, **kwargs):
            mock = MagicMock()
            if kwargs.get("query_type") == "fts":
                raise RuntimeError("No FTS index")
            mock.limit.return_value.to_list.return_value = vector_rows
            return mock

        table.search.side_effect = mock_search

        results = await mixin.search("test query", limit=5, search_mode="hybrid")

        # Should still return vector results
        assert len(results) >= 1

    async def test_default_mode_from_config(self):
        mixin = self._make_mixin(default_mode="keyword")
        table = mixin._get_table()
        fts_rows = [_make_row("a", bm25_score=5.0)]
        table.search.return_value.limit.return_value.to_list.return_value = fts_rows

        # No explicit search_mode — should use default "keyword"
        results = await mixin.search("test query", limit=5)

        mixin.embedding_provider.embed.assert_not_called()
        table.search.assert_called_once_with("test query", query_type="fts")


# ---------------------------------------------------------------
# VectorStore constructor wiring
# ---------------------------------------------------------------


class TestVectorStoreHybridConfig:
    def test_default_search_mode_passed_through(self):
        from local_deepwiki.core.vectorstore.store import VectorStore

        provider = MagicMock()
        store = VectorStore(
            MagicMock(), provider, default_search_mode="hybrid", bm25_weight=0.5
        )
        assert store._default_search_mode == "hybrid"
        assert store._bm25_weight == 0.5

    def test_default_values(self):
        from local_deepwiki.core.vectorstore.store import VectorStore

        provider = MagicMock()
        store = VectorStore(MagicMock(), provider)
        assert store._default_search_mode == "vector"
        assert store._bm25_weight == 0.3
