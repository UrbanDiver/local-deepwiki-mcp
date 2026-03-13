"""Tests for SearchMixin extracted helper methods.

Verifies the 3 methods extracted from search() during Phase 1:
- _execute_vector_search
- _apply_fuzzy_reranking
- _record_and_cache
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    Language,
    SearchResult,
)


def _make_mixin() -> MagicMock:
    """Create a mock SearchMixin instance with required attributes."""
    from local_deepwiki.core.vectorstore.mixins.search import SearchMixin

    mixin = MagicMock(spec=SearchMixin)
    # Bind the real methods to the mock instance
    mixin._execute_vector_search = SearchMixin._execute_vector_search.__get__(mixin)
    mixin._apply_fuzzy_reranking = SearchMixin._apply_fuzzy_reranking.__get__(mixin)
    mixin._record_and_cache = SearchMixin._record_and_cache.__get__(mixin)

    # Default attributes
    mixin._lazy_index_manager = MagicMock()
    mixin._lazy_index_manager.should_create_index.return_value = False
    mixin._adaptive_search_enabled = False
    mixin._adaptive_searcher = MagicMock()
    mixin._search_cache = MagicMock()
    mixin._fuzzy_search_config = MagicMock()
    mixin._fuzzy_search_config.enable_auto_fuzzy = False

    return mixin


def _make_search_result(
    score: float = 0.9,
    name: str = "test_func",
    content: str = "def test_func(): pass",
) -> SearchResult:
    """Create a SearchResult with a real CodeChunk."""
    chunk = CodeChunk(
        id="test-chunk-1",
        file_path="src/main.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name=name,
        content=content,
        start_line=1,
        end_line=5,
    )
    return SearchResult(chunk=chunk, score=score, highlights=[])


class TestExecuteVectorSearch:
    """Tests for _execute_vector_search."""

    def test_basic_search_returns_results(self):
        mixin = _make_mixin()
        table = MagicMock()
        rows = [{"file_path": "a.py", "_distance": 0.1}]
        table.search.return_value.limit.return_value.to_list.return_value = rows

        result = mixin._execute_vector_search(table, [0.1, 0.2], [], 10)

        assert result == rows
        table.search.assert_called_once_with([0.1, 0.2])

    def test_applies_filters_as_where_clause(self):
        mixin = _make_mixin()
        table = MagicMock()
        search_chain = table.search.return_value.limit.return_value
        search_chain.where.return_value.to_list.return_value = []

        mixin._execute_vector_search(
            table, [0.1], ["language = 'python'", "chunk_type = 'function'"], 20
        )

        search_chain.where.assert_called_once_with(
            "language = 'python' AND chunk_type = 'function'"
        )

    def test_no_filters_skips_where(self):
        mixin = _make_mixin()
        table = MagicMock()
        search_chain = table.search.return_value.limit.return_value
        search_chain.to_list.return_value = []

        mixin._execute_vector_search(table, [0.1], [], 10)

        search_chain.where.assert_not_called()

    def test_records_search_latency(self):
        mixin = _make_mixin()
        table = MagicMock()
        table.search.return_value.limit.return_value.to_list.return_value = []

        mixin._execute_vector_search(table, [0.1], [], 10)

        mixin._lazy_index_manager.record_search_latency.assert_called_once()
        latency_ms = mixin._lazy_index_manager.record_search_latency.call_args[0][0]
        assert latency_ms >= 0

    def test_triggers_index_creation_when_needed(self):
        mixin = _make_mixin()
        mixin._lazy_index_manager.should_create_index.return_value = True
        mixin._lazy_index_manager.schedule_index_creation = MagicMock()

        table = MagicMock()
        table.search.return_value.limit.return_value.to_list.return_value = []

        # Need an event loop for create_task — the method catches RuntimeError
        mixin._execute_vector_search(table, [0.1], [], 10)

        mixin._lazy_index_manager.should_create_index.assert_called_once()

    def test_respects_fetch_limit(self):
        mixin = _make_mixin()
        table = MagicMock()
        table.search.return_value.limit.return_value.to_list.return_value = []

        mixin._execute_vector_search(table, [0.1], [], 42)

        table.search.return_value.limit.assert_called_once_with(42)


class TestApplyFuzzyReranking:
    """Tests for _apply_fuzzy_reranking."""

    def test_no_fuzzy_returns_original(self):
        mixin = _make_mixin()
        results = [_make_search_result(0.9)]

        reranked, auto_enabled = mixin._apply_fuzzy_reranking(
            results, "test", 0.3, use_fuzzy=False
        )

        assert reranked == results
        assert auto_enabled is False

    def test_explicit_fuzzy_reranks(self):
        mixin = _make_mixin()
        results = [_make_search_result(0.9), _make_search_result(0.7)]

        with patch(
            "local_deepwiki.core.fuzzy_search.rerank_with_fuzzy",
            return_value=list(reversed(results)),
        ) as mock_rerank:
            reranked, auto_enabled = mixin._apply_fuzzy_reranking(
                results, "query", 0.5, use_fuzzy=True
            )

        mock_rerank.assert_called_once_with(results, "query", 0.5)
        assert auto_enabled is False

    def test_auto_fuzzy_enables_on_poor_results(self):
        mixin = _make_mixin()
        mixin._fuzzy_search_config.enable_auto_fuzzy = True
        mixin._fuzzy_search_config.auto_fuzzy_threshold = 0.5

        low_score_results = [_make_search_result(0.3)]

        with (
            patch(
                "local_deepwiki.core.fuzzy_search.should_auto_enable_fuzzy",
                return_value=True,
            ),
            patch(
                "local_deepwiki.core.fuzzy_search.rerank_with_fuzzy",
                return_value=low_score_results,
            ),
            patch(
                "local_deepwiki.core.fuzzy_search.extract_highlights",
                return_value=["match"],
            ),
        ):
            reranked, auto_enabled = mixin._apply_fuzzy_reranking(
                low_score_results, "query", 0.3, use_fuzzy=False
            )

        assert auto_enabled is True

    def test_empty_results_no_reranking(self):
        mixin = _make_mixin()

        reranked, auto_enabled = mixin._apply_fuzzy_reranking(
            [], "query", 0.3, use_fuzzy=True
        )

        assert reranked == []
        assert auto_enabled is False

    def test_highlights_attached_on_fuzzy(self):
        mixin = _make_mixin()
        results = [_make_search_result(0.9)]

        with (
            patch(
                "local_deepwiki.core.fuzzy_search.rerank_with_fuzzy",
                return_value=results,
            ),
            patch(
                "local_deepwiki.core.fuzzy_search.extract_highlights",
                return_value=["matched_term"],
            ),
        ):
            reranked, _ = mixin._apply_fuzzy_reranking(
                results, "query", 0.3, use_fuzzy=True
            )

        assert reranked[0].highlights == ["matched_term"]


class TestRecordAndCache:
    """Tests for _record_and_cache."""

    def test_caches_when_enabled(self):
        mixin = _make_mixin()
        results = [_make_search_result()]
        embedding = [0.1, 0.2]
        filters = {"limit": 10}

        mixin._record_and_cache(
            "query",
            embedding,
            results,
            filters,
            use_cache=True,
            auto_fuzzy_enabled=False,
            fetch_limit=20,
        )

        mixin._search_cache.set.assert_called_once_with(
            "query", embedding, results, filters
        )

    def test_skips_cache_when_disabled(self):
        mixin = _make_mixin()
        results = [_make_search_result()]

        mixin._record_and_cache(
            "query",
            [0.1],
            results,
            {},
            use_cache=False,
            auto_fuzzy_enabled=False,
            fetch_limit=20,
        )

        mixin._search_cache.set.assert_not_called()

    def test_skips_cache_when_auto_fuzzy(self):
        mixin = _make_mixin()
        results = [_make_search_result()]

        mixin._record_and_cache(
            "query",
            [0.1],
            results,
            {},
            use_cache=True,
            auto_fuzzy_enabled=True,
            fetch_limit=20,
        )

        mixin._search_cache.set.assert_not_called()

    def test_records_adaptive_quality(self):
        mixin = _make_mixin()
        mixin._adaptive_search_enabled = True
        r1 = _make_search_result(score=0.8)
        r2 = _make_search_result(score=0.6)

        mixin._record_and_cache(
            "query",
            [0.1],
            [r1, r2],
            {},
            use_cache=False,
            auto_fuzzy_enabled=False,
            fetch_limit=30,
        )

        mixin._adaptive_searcher.record_search_quality.assert_called_once_with(
            "query", 0.7, 2, 30
        )

    def test_skips_adaptive_when_disabled(self):
        mixin = _make_mixin()
        mixin._adaptive_search_enabled = False
        results = [_make_search_result()]

        mixin._record_and_cache(
            "query",
            [0.1],
            results,
            {},
            use_cache=False,
            auto_fuzzy_enabled=False,
            fetch_limit=20,
        )

        mixin._adaptive_searcher.record_search_quality.assert_not_called()

    def test_skips_adaptive_with_empty_results(self):
        mixin = _make_mixin()
        mixin._adaptive_search_enabled = True

        mixin._record_and_cache(
            "query",
            [0.1],
            [],
            {},
            use_cache=False,
            auto_fuzzy_enabled=False,
            fetch_limit=20,
        )

        mixin._adaptive_searcher.record_search_quality.assert_not_called()
