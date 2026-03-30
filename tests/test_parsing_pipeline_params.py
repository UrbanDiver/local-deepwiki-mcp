"""Tests for PipelineContext frozen dataclass and _WindowState."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.core.parsing_pipeline import (
    FileParsingPipeline,
    PipelineContext,
    _WindowState,
)


def _make_context(**overrides):
    """Build a PipelineContext with mock defaults, merging *overrides*."""
    defaults = {
        "parser": MagicMock(),
        "chunker": MagicMock(),
        "repo_path": Path("/tmp/repo"),
        "vector_store": MagicMock(),
        "batch_size": 50,
        "parallel_workers": 4,
        "pipeline_logger": None,
    }
    return PipelineContext(**{**defaults, **overrides})


# -- PipelineContext frozen tests --


class TestPipelineContext:
    def test_frozen_rejects_mutation(self):
        ctx = _make_context()
        with pytest.raises(FrozenInstanceError):
            ctx.batch_size = 100  # type: ignore[misc]

    def test_frozen_rejects_repo_path_mutation(self):
        ctx = _make_context()
        with pytest.raises(FrozenInstanceError):
            ctx.repo_path = Path("/other")  # type: ignore[misc]

    def test_stores_all_fields(self):
        parser = MagicMock()
        chunker = MagicMock()
        vs = MagicMock()
        ctx = PipelineContext(
            parser=parser,
            chunker=chunker,
            repo_path=Path("/repo"),
            vector_store=vs,
            batch_size=32,
            parallel_workers=8,
            pipeline_logger="custom_logger",
        )
        assert ctx.parser is parser
        assert ctx.chunker is chunker
        assert ctx.repo_path == Path("/repo")
        assert ctx.vector_store is vs
        assert ctx.batch_size == 32
        assert ctx.parallel_workers == 8
        assert ctx.pipeline_logger == "custom_logger"

    def test_default_pipeline_logger_is_none(self):
        ctx = _make_context()
        assert ctx.pipeline_logger is None

    def test_equality(self):
        parser = MagicMock()
        chunker = MagicMock()
        vs = MagicMock()
        shared = {
            "parser": parser,
            "chunker": chunker,
            "repo_path": Path("/repo"),
            "vector_store": vs,
            "batch_size": 50,
            "parallel_workers": 4,
        }
        ctx1 = PipelineContext(**shared)
        ctx2 = PipelineContext(**shared)
        assert ctx1 == ctx2


# -- _WindowState tests --


class TestWindowState:
    def test_defaults(self):
        state = _WindowState()
        assert state.file_count == 0
        assert state.chunk_batch == []
        assert state.processed_files == []
        assert state.total_chunks_processed == 0
        assert state.is_first_batch is True
        assert state.error_count == 0
        assert state.files_completed == 0

    def test_mutable(self):
        state = _WindowState()
        state.total_chunks_processed = 42
        state.error_count = 3
        state.is_first_batch = False
        state.files_completed = 10
        assert state.total_chunks_processed == 42
        assert state.error_count == 3
        assert state.is_first_batch is False
        assert state.files_completed == 10

    def test_independent_instances(self):
        """Each _WindowState gets its own list instances."""
        s1 = _WindowState()
        s2 = _WindowState()
        s1.chunk_batch.append("x")
        assert s2.chunk_batch == []


# -- FileParsingPipeline construction via PipelineContext --


class TestFileParsingPipelineConstruction:
    def test_init_exposes_ctx_fields(self):
        ctx = _make_context(batch_size=99, parallel_workers=7)
        pipeline = FileParsingPipeline(ctx)
        assert pipeline.batch_size == 99
        assert pipeline.parallel_workers == 7
        assert pipeline.parser is ctx.parser
        assert pipeline.chunker is ctx.chunker
        assert pipeline.repo_path == ctx.repo_path
        assert pipeline.vector_store is ctx.vector_store
        assert pipeline._ctx is ctx

    def test_custom_logger_propagated(self):
        custom = MagicMock()
        ctx = _make_context(pipeline_logger=custom)
        pipeline = FileParsingPipeline(ctx)
        assert pipeline._logger is custom

    def test_default_logger_when_none(self):
        ctx = _make_context(pipeline_logger=None)
        pipeline = FileParsingPipeline(ctx)
        # Should fall back to the module-level logger, not None
        assert pipeline._logger is not None


# -- parse_files_parallel integration smoke test --


class TestParseFilesParallelSmoke:
    async def test_empty_file_list_returns_empty(self):
        ctx = _make_context()
        pipeline = FileParsingPipeline(ctx)
        files, chunks = await pipeline.parse_files_parallel([], False, None)
        assert files == []
        assert chunks == 0

    async def test_single_file_round_trip(self):
        """One file through the full pipeline with mocked parse and store."""
        mock_vs = AsyncMock()
        mock_vs.create_or_update_table = AsyncMock()
        mock_vs.add_chunks = AsyncMock()

        ctx = _make_context(
            vector_store=mock_vs,
            batch_size=1,
            parallel_workers=1,
        )
        pipeline = FileParsingPipeline(ctx)

        fake_file = Path("/tmp/repo/hello.py")
        fake_info = MagicMock()
        fake_chunk = MagicMock()

        from local_deepwiki.core.parsing_pipeline import ParseResult

        def fake_parse(fp):
            return ParseResult(file_path=fp, file_info=fake_info, chunks=[fake_chunk])

        files, total = await pipeline.parse_files_parallel(
            [fake_file], full_rebuild=True, progress_callback=None, parse_fn=fake_parse
        )
        assert len(files) == 1
        assert total >= 1
