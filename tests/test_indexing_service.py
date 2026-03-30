"""Tests for IndexingService: indexing pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.services.indexing_service import (
    IndexingService,
    IndexPipelineRequest,
)
from local_deepwiki.services.models import IndexPipelineResult


def _make_config(tmp_path: Path) -> MagicMock:
    from local_deepwiki.config import GenerationMode

    config = MagicMock()
    config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    config.get_vector_db_path.return_value = tmp_path / ".deepwiki" / "vectors.lance"
    config.wiki.max_file_docs = 500
    config.wiki.hybrid_eager_pages = 10
    config.wiki.prefetch_drain = False
    config.wiki.generation_mode = GenerationMode.EAGER
    return config


def _make_mock_indexer(tmp_path: Path) -> MagicMock:
    indexer = MagicMock()
    indexer.wiki_path = tmp_path / ".deepwiki"
    indexer.vector_store = MagicMock()
    indexer.vector_store.stabilize = MagicMock()
    indexer.config = _make_config(tmp_path)

    status = MagicMock()
    status.total_files = 10
    status.total_chunks = 100
    status.languages = {"python": 8, "javascript": 2}
    status.files = []
    indexer.index = AsyncMock(return_value=status)

    return indexer


class TestRunPipeline:
    async def test_eager_mode_returns_result(self, tmp_path: Path):
        config = _make_config(tmp_path)
        mock_indexer = _make_mock_indexer(tmp_path)

        wiki_structure = MagicMock()
        wiki_structure.pages = ["index.md", "overview.md", "architecture.md"]

        svc = IndexingService(config)

        with (
            patch(
                "local_deepwiki.services.indexing_service.RepositoryIndexer",
                return_value=mock_indexer,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=wiki_structure,
            ),
        ):
            result = await svc.run_pipeline(IndexPipelineRequest(repo_path=tmp_path))

        assert isinstance(result, IndexPipelineResult)
        assert result.files_indexed == 10
        assert result.chunks_created == 100
        assert result.wiki_pages_generated == 3
        mock_indexer.vector_store.stabilize.assert_called_once()

    async def test_progress_callback_invoked(self, tmp_path: Path):
        config = _make_config(tmp_path)
        mock_indexer = _make_mock_indexer(tmp_path)

        async def mock_index(full_rebuild=False, progress_callback=None):
            if progress_callback:
                progress_callback("Scanning...", 1, 3)
                progress_callback("Parsing...", 2, 3)
                progress_callback("Done", 3, 3)
            status = MagicMock()
            status.total_files = 5
            status.total_chunks = 50
            status.languages = {"python": 5}
            status.files = []
            return status

        mock_indexer.index = AsyncMock(side_effect=mock_index)

        wiki_structure = MagicMock()
        wiki_structure.pages = []

        progress_calls: list[tuple[str, float]] = []

        def on_progress(msg: str, fraction: float) -> None:
            progress_calls.append((msg, fraction))

        svc = IndexingService(config)

        with (
            patch(
                "local_deepwiki.services.indexing_service.RepositoryIndexer",
                return_value=mock_indexer,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=wiki_structure,
            ),
        ):
            await svc.run_pipeline(
                IndexPipelineRequest(repo_path=tmp_path, progress_callback=on_progress)
            )

        assert len(progress_calls) >= 3
        for _msg, fraction in progress_calls:
            assert 0.0 <= fraction <= 1.0

    async def test_full_rebuild_flag_passed(self, tmp_path: Path):
        config = _make_config(tmp_path)
        mock_indexer = _make_mock_indexer(tmp_path)

        wiki_structure = MagicMock()
        wiki_structure.pages = []

        svc = IndexingService(config)

        with (
            patch(
                "local_deepwiki.services.indexing_service.RepositoryIndexer",
                return_value=mock_indexer,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=wiki_structure,
            ),
        ):
            await svc.run_pipeline(
                IndexPipelineRequest(repo_path=tmp_path, full_rebuild=True)
            )

        mock_indexer.index.assert_called_once()
        call_kwargs = mock_indexer.index.call_args[1]
        assert call_kwargs["full_rebuild"] is True

    async def test_embedding_provider_override(self, tmp_path: Path):
        config = _make_config(tmp_path)
        mock_indexer = _make_mock_indexer(tmp_path)

        wiki_structure = MagicMock()
        wiki_structure.pages = []

        svc = IndexingService(config)

        with (
            patch(
                "local_deepwiki.services.indexing_service.RepositoryIndexer",
                return_value=mock_indexer,
            ) as mock_cls,
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=wiki_structure,
            ),
        ):
            await svc.run_pipeline(
                IndexPipelineRequest(repo_path=tmp_path, embedding_provider="openai")
            )

        mock_cls.assert_called_once_with(
            repo_path=tmp_path,
            config=config,
            embedding_provider_name="openai",
        )

    async def test_error_during_indexing_propagates(self, tmp_path: Path):
        config = _make_config(tmp_path)
        mock_indexer = _make_mock_indexer(tmp_path)
        mock_indexer.index = AsyncMock(side_effect=RuntimeError("Index failed"))

        svc = IndexingService(config)

        with patch(
            "local_deepwiki.services.indexing_service.RepositoryIndexer",
            return_value=mock_indexer,
        ):
            with pytest.raises(RuntimeError, match="Index failed"):
                await svc.run_pipeline(IndexPipelineRequest(repo_path=tmp_path))
