"""Tests for search_params frozen dataclasses and their integration.

Covers: SearchPipelineParams, SearchExecutionContext, EmbeddingBatchParams,
SearchEngineConfig -- immutability, construction, field access, and integration
with the functions that consume them.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from local_deepwiki.core.vectorstore.search_params import (
    EmbeddingBatchParams,
    SearchEngineConfig,
    SearchExecutionContext,
    SearchPipelineParams,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row_to_chunk():
    """Return a mock row_to_chunk callable."""
    return MagicMock(return_value=MagicMock(id="chunk-1"))


def _make_lazy_index_manager():
    """Return a mock LazyIndexManager."""
    mgr = MagicMock()
    mgr.record_search_latency = MagicMock()
    mgr.should_create_index = MagicMock(return_value=False)
    return mgr


def _make_embedding_provider():
    """Return a mock EmbeddingProvider."""
    provider = MagicMock()
    provider.name = "mock:test"
    provider.dimension = 384
    provider.embed = AsyncMock(return_value=[[0.1] * 384])
    return provider


# ---------------------------------------------------------------------------
# SearchPipelineParams
# ---------------------------------------------------------------------------


class TestSearchPipelineParams:
    """Tests for SearchPipelineParams frozen dataclass."""

    def test_construction(self):
        """Test basic construction with all fields."""
        table = MagicMock()
        row_to_chunk = _make_row_to_chunk()
        lazy_mgr = _make_lazy_index_manager()

        params = SearchPipelineParams(
            table=table,
            query="def main",
            query_embedding=[0.1, 0.2, 0.3],
            filters=["language = 'python'"],
            fetch_limit=50,
            min_similarity=0.5,
            bm25_weight=0.3,
            row_to_chunk=row_to_chunk,
            lazy_index_manager=lazy_mgr,
        )

        assert params.query == "def main"
        assert params.query_embedding == [0.1, 0.2, 0.3]
        assert params.filters == ["language = 'python'"]
        assert params.fetch_limit == 50
        assert params.min_similarity == 0.5
        assert params.bm25_weight == 0.3
        assert params.table is table
        assert params.row_to_chunk is row_to_chunk
        assert params.lazy_index_manager is lazy_mgr

    def test_frozen_immutability(self):
        """Test that fields cannot be mutated after construction."""
        params = SearchPipelineParams(
            table=MagicMock(),
            query="test",
            query_embedding=[0.1],
            filters=[],
            fetch_limit=10,
            min_similarity=0.3,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        with pytest.raises(FrozenInstanceError):
            params.query = "mutated"

        with pytest.raises(FrozenInstanceError):
            params.fetch_limit = 999

        with pytest.raises(FrozenInstanceError):
            params.min_similarity = 0.99

    def test_empty_filters(self):
        """Test construction with empty filter list."""
        params = SearchPipelineParams(
            table=MagicMock(),
            query="test",
            query_embedding=[],
            filters=[],
            fetch_limit=10,
            min_similarity=0.0,
            bm25_weight=0.0,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )
        assert params.filters == []
        assert params.query_embedding == []

    def test_multiple_filters(self):
        """Test construction with multiple filter expressions."""
        params = SearchPipelineParams(
            table=MagicMock(),
            query="test",
            query_embedding=[0.1],
            filters=["language = 'python'", "chunk_type = 'function'"],
            fetch_limit=20,
            min_similarity=0.5,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )
        assert len(params.filters) == 2


# ---------------------------------------------------------------------------
# SearchExecutionContext
# ---------------------------------------------------------------------------


class TestSearchExecutionContext:
    """Tests for SearchExecutionContext frozen dataclass."""

    def test_construction(self):
        """Test basic construction with all fields."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile

        ctx = SearchExecutionContext(
            query_embedding=[0.1, 0.2],
            filters=["language = 'python'"],
            profile_config=MagicMock(),
            resolved_profile=SearchProfile.BALANCED,
            effective_min_similarity=0.5,
            effective_mode="hybrid",
            use_cache=True,
        )

        assert ctx.query_embedding == [0.1, 0.2]
        assert ctx.filters == ["language = 'python'"]
        assert ctx.resolved_profile == SearchProfile.BALANCED
        assert ctx.effective_min_similarity == 0.5
        assert ctx.effective_mode == "hybrid"
        assert ctx.use_cache is True

    def test_frozen_immutability(self):
        """Test that fields cannot be mutated after construction."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile

        ctx = SearchExecutionContext(
            query_embedding=[0.1],
            filters=[],
            profile_config=MagicMock(),
            resolved_profile=SearchProfile.FAST,
            effective_min_similarity=0.3,
            effective_mode="vector",
            use_cache=False,
        )

        with pytest.raises(FrozenInstanceError):
            ctx.effective_mode = "keyword"

        with pytest.raises(FrozenInstanceError):
            ctx.use_cache = True

        with pytest.raises(FrozenInstanceError):
            ctx.effective_min_similarity = 0.99

    def test_cache_disabled(self):
        """Test construction with caching disabled."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile

        ctx = SearchExecutionContext(
            query_embedding=[],
            filters=[],
            profile_config=MagicMock(),
            resolved_profile=SearchProfile.THOROUGH,
            effective_min_similarity=0.7,
            effective_mode="keyword",
            use_cache=False,
        )
        assert ctx.use_cache is False
        assert ctx.effective_mode == "keyword"

    def test_all_search_modes(self):
        """Test construction with each valid search mode."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile

        for mode in ("vector", "keyword", "hybrid"):
            ctx = SearchExecutionContext(
                query_embedding=[0.1],
                filters=[],
                profile_config=MagicMock(),
                resolved_profile=SearchProfile.BALANCED,
                effective_min_similarity=0.5,
                effective_mode=mode,
                use_cache=True,
            )
            assert ctx.effective_mode == mode


# ---------------------------------------------------------------------------
# EmbeddingBatchParams
# ---------------------------------------------------------------------------


class TestEmbeddingBatchParams:
    """Tests for EmbeddingBatchParams frozen dataclass."""

    def test_construction(self):
        """Test basic construction with all fields."""
        from local_deepwiki.config import EmbeddingBatchConfig

        provider = _make_embedding_provider()
        config = EmbeddingBatchConfig()
        semaphore = asyncio.Semaphore(4)
        rate_limiter = MagicMock()

        params = EmbeddingBatchParams(
            embedding_provider=provider,
            config=config,
            rate_limiter=rate_limiter,
            semaphore=semaphore,
        )

        assert params.embedding_provider is provider
        assert params.config is config
        assert params.rate_limiter is rate_limiter
        assert params.semaphore is semaphore

    def test_frozen_immutability(self):
        """Test that fields cannot be mutated after construction."""
        params = EmbeddingBatchParams(
            embedding_provider=_make_embedding_provider(),
            config=MagicMock(),
            rate_limiter=None,
            semaphore=asyncio.Semaphore(1),
        )

        with pytest.raises(FrozenInstanceError):
            params.embedding_provider = _make_embedding_provider()

        with pytest.raises(FrozenInstanceError):
            params.rate_limiter = MagicMock()

    def test_none_rate_limiter(self):
        """Test construction with None rate_limiter (local providers)."""
        params = EmbeddingBatchParams(
            embedding_provider=_make_embedding_provider(),
            config=MagicMock(),
            rate_limiter=None,
            semaphore=asyncio.Semaphore(8),
        )
        assert params.rate_limiter is None


# ---------------------------------------------------------------------------
# SearchEngineConfig
# ---------------------------------------------------------------------------


class TestSearchEngineConfig:
    """Tests for SearchEngineConfig frozen dataclass."""

    def test_default_values(self):
        """Test construction with all defaults."""
        cfg = SearchEngineConfig()

        assert cfg.default_search_profile is None
        assert cfg.adaptive_search_enabled is True
        assert cfg.default_search_mode == "vector"
        assert cfg.bm25_weight == 0.3

    def test_custom_values(self):
        """Test construction with custom values."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile

        cfg = SearchEngineConfig(
            default_search_profile=SearchProfile.THOROUGH,
            adaptive_search_enabled=False,
            default_search_mode="hybrid",
            bm25_weight=0.5,
        )

        assert cfg.default_search_profile == SearchProfile.THOROUGH
        assert cfg.adaptive_search_enabled is False
        assert cfg.default_search_mode == "hybrid"
        assert cfg.bm25_weight == 0.5

    def test_frozen_immutability(self):
        """Test that fields cannot be mutated after construction."""
        cfg = SearchEngineConfig()

        with pytest.raises(FrozenInstanceError):
            cfg.adaptive_search_enabled = False

        with pytest.raises(FrozenInstanceError):
            cfg.default_search_mode = "hybrid"

        with pytest.raises(FrozenInstanceError):
            cfg.bm25_weight = 0.99


# ---------------------------------------------------------------------------
# Integration: SearchPipelineParams with dispatch_search
# ---------------------------------------------------------------------------


class TestSearchPipelineParamsIntegration:
    """Integration tests for SearchPipelineParams with the search pipeline."""

    def test_dispatch_search_vector_mode(self):
        """Test dispatch_search with vector mode accepts SearchPipelineParams."""
        from local_deepwiki.core.vectorstore import search_pipeline

        table = MagicMock()
        table.search.return_value.limit.return_value.where.return_value.to_list.return_value = []
        table.search.return_value.limit.return_value.to_list.return_value = []

        params = SearchPipelineParams(
            table=table,
            query="test query",
            query_embedding=[0.1, 0.2],
            filters=[],
            fetch_limit=10,
            min_similarity=0.3,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        results = search_pipeline.dispatch_search("vector", params)
        assert isinstance(results, list)

    def test_dispatch_search_keyword_mode(self):
        """Test dispatch_search with keyword mode accepts SearchPipelineParams."""
        from local_deepwiki.core.vectorstore import search_pipeline

        table = MagicMock()
        table.search.return_value.limit.return_value.where.return_value.to_list.return_value = []
        table.search.return_value.limit.return_value.to_list.return_value = []

        params = SearchPipelineParams(
            table=table,
            query="test query",
            query_embedding=[],
            filters=[],
            fetch_limit=10,
            min_similarity=0.3,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        results = search_pipeline.dispatch_search("keyword", params)
        assert isinstance(results, list)

    def test_dispatch_search_hybrid_mode(self):
        """Test dispatch_search with hybrid mode accepts SearchPipelineParams."""
        from local_deepwiki.core.vectorstore import search_pipeline

        table = MagicMock()
        table.search.return_value.limit.return_value.where.return_value.to_list.return_value = []
        table.search.return_value.limit.return_value.to_list.return_value = []

        params = SearchPipelineParams(
            table=table,
            query="test query",
            query_embedding=[0.1, 0.2],
            filters=[],
            fetch_limit=10,
            min_similarity=0.3,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        results = search_pipeline.dispatch_search("hybrid", params)
        assert isinstance(results, list)

    def test_run_vector_pipeline_with_params(self):
        """Test run_vector_pipeline directly with SearchPipelineParams."""
        from local_deepwiki.core.vectorstore import search_pipeline

        table = MagicMock()
        table.search.return_value.limit.return_value.to_list.return_value = []

        params = SearchPipelineParams(
            table=table,
            query="test",
            query_embedding=[0.1],
            filters=[],
            fetch_limit=5,
            min_similarity=0.3,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        results = search_pipeline.run_vector_pipeline(params)
        assert isinstance(results, list)

    def test_run_hybrid_pipeline_with_params(self):
        """Test run_hybrid_pipeline directly with SearchPipelineParams."""
        from local_deepwiki.core.vectorstore import search_pipeline

        table = MagicMock()
        table.search.return_value.limit.return_value.to_list.return_value = []

        params = SearchPipelineParams(
            table=table,
            query="test",
            query_embedding=[0.1],
            filters=[],
            fetch_limit=5,
            min_similarity=0.3,
            bm25_weight=0.3,
            row_to_chunk=_make_row_to_chunk(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        results = search_pipeline.run_hybrid_pipeline(params)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Integration: EmbeddingBatchParams with embed_single_batch_with_retry
# ---------------------------------------------------------------------------


class TestEmbeddingBatchParamsIntegration:
    """Integration tests for EmbeddingBatchParams with the embedding pipeline."""

    async def test_embed_single_batch_with_retry(self):
        """Test embed_single_batch_with_retry accepts EmbeddingBatchParams."""
        from local_deepwiki.config import EmbeddingBatchConfig
        from local_deepwiki.core.vectorstore.embedding import (
            embed_single_batch_with_retry,
        )
        from local_deepwiki.core.vectorstore.schema import EmbeddingProgress

        provider = _make_embedding_provider()
        config = EmbeddingBatchConfig()
        progress = EmbeddingProgress(total_texts=3, total_batches=1)

        batch_params = EmbeddingBatchParams(
            embedding_provider=provider,
            config=config,
            rate_limiter=None,
            semaphore=asyncio.Semaphore(1),
        )

        result = await embed_single_batch_with_retry(
            0, ["text_1", "text_2", "text_3"], batch_params, progress
        )

        assert result.error is None
        assert result.batch_index == 0
        assert result.embeddings is not None

    async def test_embed_single_batch_with_rate_limiter(self):
        """Test embed_single_batch_with_retry with a rate limiter."""
        from local_deepwiki.config import EmbeddingBatchConfig
        from local_deepwiki.core.vectorstore.embedding import (
            embed_single_batch_with_retry,
        )
        from local_deepwiki.core.vectorstore.schema import EmbeddingProgress

        provider = _make_embedding_provider()
        config = EmbeddingBatchConfig()
        progress = EmbeddingProgress(total_texts=2, total_batches=1)
        rate_limiter = MagicMock()
        rate_limiter.acquire = AsyncMock()

        batch_params = EmbeddingBatchParams(
            embedding_provider=provider,
            config=config,
            rate_limiter=rate_limiter,
            semaphore=asyncio.Semaphore(1),
        )

        result = await embed_single_batch_with_retry(
            0, ["text_1", "text_2"], batch_params, progress
        )

        assert result.error is None
        rate_limiter.acquire.assert_awaited_once()


# ---------------------------------------------------------------------------
# Integration: SearchEngineConfig with SearchEngine.__init__
# ---------------------------------------------------------------------------


class TestSearchEngineConfigIntegration:
    """Integration tests for SearchEngineConfig with SearchEngine."""

    def test_search_engine_accepts_config(self):
        """Test SearchEngine.__init__ accepts SearchEngineConfig."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile
        from local_deepwiki.core.vectorstore.search_engine import SearchEngine

        cfg = SearchEngineConfig(
            default_search_profile=SearchProfile.THOROUGH,
            adaptive_search_enabled=False,
            default_search_mode="hybrid",
            bm25_weight=0.5,
        )

        engine = SearchEngine(
            get_table=MagicMock(return_value=None),
            row_to_chunk=_make_row_to_chunk(),
            embedding_provider=_make_embedding_provider(),
            get_search_cache=MagicMock(),
            fuzzy_search_config=MagicMock(),
            adaptive_searcher=MagicMock(),
            lazy_index_manager=_make_lazy_index_manager(),
            config=cfg,
        )

        assert engine.default_search_profile == SearchProfile.THOROUGH
        assert engine.adaptive_search_enabled is False
        assert engine._config_resolver.default_search_mode == "hybrid"
        assert engine._bm25_weight == 0.5

    def test_search_engine_rejects_legacy_kwargs(self):
        """Test SearchEngine.__init__ rejects removed legacy kwargs."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile
        from local_deepwiki.core.vectorstore.search_engine import SearchEngine

        with pytest.raises(TypeError):
            SearchEngine(
                get_table=MagicMock(return_value=None),
                row_to_chunk=_make_row_to_chunk(),
                embedding_provider=_make_embedding_provider(),
                get_search_cache=MagicMock(),
                fuzzy_search_config=MagicMock(),
                adaptive_searcher=MagicMock(),
                lazy_index_manager=_make_lazy_index_manager(),
                default_search_profile=SearchProfile.FAST,
            )

    def test_config_values_applied(self):
        """Test that config values are applied to the engine."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile
        from local_deepwiki.core.vectorstore.search_engine import SearchEngine

        cfg = SearchEngineConfig(
            default_search_profile=SearchProfile.THOROUGH,
            adaptive_search_enabled=False,
            default_search_mode="hybrid",
            bm25_weight=0.8,
        )

        engine = SearchEngine(
            get_table=MagicMock(return_value=None),
            row_to_chunk=_make_row_to_chunk(),
            embedding_provider=_make_embedding_provider(),
            get_search_cache=MagicMock(),
            fuzzy_search_config=MagicMock(),
            adaptive_searcher=MagicMock(),
            lazy_index_manager=_make_lazy_index_manager(),
            config=cfg,
        )

        assert engine.default_search_profile == SearchProfile.THOROUGH
        assert engine.adaptive_search_enabled is False
        assert engine._config_resolver.default_search_mode == "hybrid"
        assert engine._bm25_weight == 0.8

    def test_default_config_when_omitted(self):
        """Test that default SearchEngineConfig is used when config is None."""
        from local_deepwiki.core.vectorstore.schema import SearchProfile
        from local_deepwiki.core.vectorstore.search_engine import SearchEngine

        engine = SearchEngine(
            get_table=MagicMock(return_value=None),
            row_to_chunk=_make_row_to_chunk(),
            embedding_provider=_make_embedding_provider(),
            get_search_cache=MagicMock(),
            fuzzy_search_config=MagicMock(),
            adaptive_searcher=MagicMock(),
            lazy_index_manager=_make_lazy_index_manager(),
        )

        assert engine.default_search_profile == SearchProfile.BALANCED
        assert engine.adaptive_search_enabled is True
        assert engine._config_resolver.default_search_mode == "vector"
        assert engine._bm25_weight == 0.3


# ---------------------------------------------------------------------------
# Re-export tests
# ---------------------------------------------------------------------------


class TestReexports:
    """Test that parameter objects are re-exported from __init__.py."""

    def test_search_pipeline_params_importable(self):
        """Test SearchPipelineParams is importable from vectorstore package."""
        from local_deepwiki.core.vectorstore import SearchPipelineParams

        assert SearchPipelineParams is not None

    def test_search_execution_context_importable(self):
        """Test SearchExecutionContext is importable from vectorstore package."""
        from local_deepwiki.core.vectorstore import SearchExecutionContext

        assert SearchExecutionContext is not None

    def test_embedding_batch_params_importable(self):
        """Test EmbeddingBatchParams is importable from vectorstore package."""
        from local_deepwiki.core.vectorstore import EmbeddingBatchParams

        assert EmbeddingBatchParams is not None

    def test_search_engine_config_importable(self):
        """Test SearchEngineConfig is importable from vectorstore package."""
        from local_deepwiki.core.vectorstore import SearchEngineConfig

        assert SearchEngineConfig is not None


# ---------------------------------------------------------------------------
# SearchEngine config-only construction
# ---------------------------------------------------------------------------


async def test_search_engine_config_only_construction():
    """SearchEngine.__init__ accepts only SearchEngineConfig, no legacy kwargs."""
    from local_deepwiki.core.vectorstore.schema import SearchProfile
    from local_deepwiki.core.vectorstore.search_engine import SearchEngine
    from local_deepwiki.core.vectorstore.search_params import SearchEngineConfig

    cfg = SearchEngineConfig(
        default_search_profile=SearchProfile.BALANCED,
        adaptive_search_enabled=False,
        default_search_mode="hybrid",
        bm25_weight=0.5,
    )
    engine = SearchEngine(
        get_table=lambda: None,
        row_to_chunk=lambda row: None,
        embedding_provider=MagicMock(),
        get_search_cache=lambda: MagicMock(),
        fuzzy_search_config=MagicMock(),
        adaptive_searcher=MagicMock(),
        lazy_index_manager=MagicMock(),
        config=cfg,
    )
    assert engine._default_search_profile == SearchProfile.BALANCED
    assert engine._adaptive_search_enabled is False
    assert engine._default_search_mode == "hybrid"
    assert engine._bm25_weight == 0.5
