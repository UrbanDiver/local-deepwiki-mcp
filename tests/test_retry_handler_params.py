"""Tests for parameter objects introduced in Task 7: Retry & Handlers.

Covers RetryConfig, IndexingPipelineContext, IndexingAuditContext,
EntityAnalysisContext, DiffSynthesisContext, and ExportCompletionContext.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------


class TestRetryConfig:
    """Tests for the RetryConfig frozen dataclass."""

    def test_defaults(self) -> None:
        from local_deepwiki.providers.retry import RetryConfig

        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 30.0
        assert cfg.exponential_base == 2.0
        assert cfg.jitter is True

    def test_custom_values(self) -> None:
        from local_deepwiki.providers.retry import RetryConfig

        cfg = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=60.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert cfg.max_attempts == 5
        assert cfg.base_delay == 0.5
        assert cfg.max_delay == 60.0
        assert cfg.exponential_base == 3.0
        assert cfg.jitter is False

    def test_frozen(self) -> None:
        from local_deepwiki.providers.retry import RetryConfig

        cfg = RetryConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.max_attempts = 10  # type: ignore[misc]

    def test_slots(self) -> None:
        from local_deepwiki.providers.retry import RetryConfig

        cfg = RetryConfig()
        assert not hasattr(cfg, "__dict__")

    def test_exported_in_all(self) -> None:
        from local_deepwiki.providers import retry

        assert "RetryConfig" in retry.__all__

    async def test_with_retry_uses_config(self) -> None:
        """Verify with_retry still functions after refactoring to RetryConfig."""
        from local_deepwiki.providers.retry import with_retry

        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.01)
        async def succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeeds()
        assert result == "ok"
        assert call_count == 1

    async def test_with_retry_retries_with_config(self) -> None:
        """Verify retries work after refactoring to RetryConfig."""
        from local_deepwiki.providers.retry import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "recovered"

        result = await flaky()
        assert result == "recovered"
        assert call_count == 3


# ---------------------------------------------------------------------------
# IndexingPipelineContext
# ---------------------------------------------------------------------------


class TestIndexingPipelineContext:
    """Tests for the IndexingPipelineContext frozen dataclass."""

    def test_construction(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.indexing import IndexingPipelineContext

        ctx = IndexingPipelineContext(
            repo_path=tmp_path,
            config=MagicMock(),
            llm_provider="ollama",
            full_rebuild=True,
        )
        assert ctx.repo_path == tmp_path
        assert ctx.llm_provider == "ollama"
        assert ctx.full_rebuild is True

    def test_frozen(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.indexing import IndexingPipelineContext

        ctx = IndexingPipelineContext(
            repo_path=tmp_path,
            config=MagicMock(),
            llm_provider=None,
            full_rebuild=False,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.full_rebuild = True  # type: ignore[misc]

    def test_slots(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.indexing import IndexingPipelineContext

        ctx = IndexingPipelineContext(
            repo_path=tmp_path,
            config=MagicMock(),
            llm_provider=None,
            full_rebuild=False,
        )
        assert not hasattr(ctx, "__dict__")

    def test_none_llm_provider(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.indexing import IndexingPipelineContext

        ctx = IndexingPipelineContext(
            repo_path=tmp_path,
            config=MagicMock(),
            llm_provider=None,
            full_rebuild=False,
        )
        assert ctx.llm_provider is None


# ---------------------------------------------------------------------------
# IndexingAuditContext
# ---------------------------------------------------------------------------


class TestIndexingAuditContext:
    """Tests for the IndexingAuditContext frozen dataclass."""

    def test_construction(self) -> None:
        from local_deepwiki.handlers.indexing import IndexingAuditContext

        audit = IndexingAuditContext(
            audit_logger=MagicMock(),
            subject_id="user-123",
            start_time=1000.0,
        )
        assert audit.subject_id == "user-123"
        assert audit.start_time == 1000.0

    def test_frozen(self) -> None:
        from local_deepwiki.handlers.indexing import IndexingAuditContext

        audit = IndexingAuditContext(
            audit_logger=MagicMock(),
            subject_id="user-123",
            start_time=1000.0,
        )
        with pytest.raises(FrozenInstanceError):
            audit.subject_id = "other"  # type: ignore[misc]

    def test_slots(self) -> None:
        from local_deepwiki.handlers.indexing import IndexingAuditContext

        audit = IndexingAuditContext(
            audit_logger=MagicMock(),
            subject_id="user-123",
            start_time=1000.0,
        )
        assert not hasattr(audit, "__dict__")


# ---------------------------------------------------------------------------
# EntityAnalysisContext (handlers copy)
# ---------------------------------------------------------------------------


class TestEntityAnalysisContextHandlers:
    """Tests for EntityAnalysisContext in handlers/analysis_entity.py."""

    def test_construction(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.analysis_entity import EntityAnalysisContext

        ctx = EntityAnalysisContext(
            file_path="src/module.py",
            entity_name="MyClass",
            repo_path=tmp_path,
            full_file=tmp_path / "src" / "module.py",
        )
        assert ctx.file_path == "src/module.py"
        assert ctx.entity_name == "MyClass"
        assert ctx.repo_path == tmp_path

    def test_defaults(self) -> None:
        from local_deepwiki.handlers.analysis_entity import EntityAnalysisContext

        ctx = EntityAnalysisContext(
            file_path="module.py",
            entity_name=None,
        )
        assert ctx.repo_path is None
        assert ctx.full_file is None
        assert ctx.index_status is None
        assert ctx.vector_store is None

    def test_frozen(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.analysis_entity import EntityAnalysisContext

        ctx = EntityAnalysisContext(
            file_path="module.py",
            entity_name="func",
            repo_path=tmp_path,
            full_file=tmp_path / "module.py",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.entity_name = "other"  # type: ignore[misc]

    def test_slots(self) -> None:
        from local_deepwiki.handlers.analysis_entity import EntityAnalysisContext

        ctx = EntityAnalysisContext(file_path="m.py", entity_name=None)
        assert not hasattr(ctx, "__dict__")


# ---------------------------------------------------------------------------
# EntityAnalysisContext (service copy)
# ---------------------------------------------------------------------------


class TestEntityAnalysisContextService:
    """Tests for EntityAnalysisContext in services/analysis_service.py."""

    def test_construction(self, tmp_path: Path) -> None:
        from local_deepwiki.services.analysis_service import EntityAnalysisContext

        ctx = EntityAnalysisContext(
            file_path="src/module.py",
            entity_name="MyClass",
            repo_path=tmp_path,
            full_file=tmp_path / "src" / "module.py",
            index_status=MagicMock(),
            vector_store=MagicMock(),
        )
        assert ctx.file_path == "src/module.py"
        assert ctx.entity_name == "MyClass"
        assert ctx.index_status is not None
        assert ctx.vector_store is not None

    def test_frozen(self) -> None:
        from local_deepwiki.services.analysis_service import EntityAnalysisContext

        ctx = EntityAnalysisContext(file_path="m.py", entity_name=None)
        with pytest.raises(FrozenInstanceError):
            ctx.file_path = "other.py"  # type: ignore[misc]

    def test_slots(self) -> None:
        from local_deepwiki.services.analysis_service import EntityAnalysisContext

        ctx = EntityAnalysisContext(file_path="m.py", entity_name=None)
        assert not hasattr(ctx, "__dict__")


# ---------------------------------------------------------------------------
# DiffSynthesisContext
# ---------------------------------------------------------------------------


class TestDiffSynthesisContext:
    """Tests for the DiffSynthesisContext frozen dataclass."""

    def test_construction(self) -> None:
        from local_deepwiki.handlers.analysis_diff import DiffSynthesisContext

        ctx = DiffSynthesisContext(
            question="What changed?",
            diff_text="--- a/f.py\n+++ b/f.py",
            base_ref="main",
            head_ref="feature",
            additional_context="some context",
        )
        assert ctx.question == "What changed?"
        assert ctx.diff_text.startswith("---")
        assert ctx.base_ref == "main"
        assert ctx.head_ref == "feature"
        assert ctx.additional_context == "some context"

    def test_frozen(self) -> None:
        from local_deepwiki.handlers.analysis_diff import DiffSynthesisContext

        ctx = DiffSynthesisContext(
            question="q",
            diff_text="d",
            base_ref="a",
            head_ref="b",
            additional_context="c",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.question = "other"  # type: ignore[misc]

    def test_slots(self) -> None:
        from local_deepwiki.handlers.analysis_diff import DiffSynthesisContext

        ctx = DiffSynthesisContext(
            question="q",
            diff_text="d",
            base_ref="a",
            head_ref="b",
            additional_context="c",
        )
        assert not hasattr(ctx, "__dict__")


# ---------------------------------------------------------------------------
# ExportCompletionContext
# ---------------------------------------------------------------------------


class TestExportCompletionContext:
    """Tests for the ExportCompletionContext frozen dataclass."""

    def test_construction(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.core import ExportCompletionContext

        ctx = ExportCompletionContext(
            audit_logger=MagicMock(),
            subject_id="user-1",
            wiki_path=tmp_path / "wiki",
            output_path=tmp_path / "out",
            export_type="html",
        )
        assert ctx.subject_id == "user-1"
        assert ctx.export_type == "html"
        assert ctx.wiki_path == tmp_path / "wiki"
        assert ctx.output_path == tmp_path / "out"

    def test_frozen(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.core import ExportCompletionContext

        ctx = ExportCompletionContext(
            audit_logger=MagicMock(),
            subject_id="user-1",
            wiki_path=tmp_path / "wiki",
            output_path=tmp_path / "out",
            export_type="html",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.export_type = "pdf"  # type: ignore[misc]

    def test_slots(self, tmp_path: Path) -> None:
        from local_deepwiki.handlers.core import ExportCompletionContext

        ctx = ExportCompletionContext(
            audit_logger=MagicMock(),
            subject_id="user-1",
            wiki_path=tmp_path / "wiki",
            output_path=tmp_path / "out",
            export_type="html",
        )
        assert not hasattr(ctx, "__dict__")

    def test_audit_export_completed_uses_context(self, tmp_path: Path) -> None:
        """Verify _audit_export_completed works with ExportCompletionContext."""
        from local_deepwiki.handlers.core import (
            ExportCompletionContext,
            _audit_export_completed,
        )

        mock_logger = MagicMock()
        ctx = ExportCompletionContext(
            audit_logger=mock_logger,
            subject_id="user-1",
            wiki_path=tmp_path / "wiki",
            output_path=tmp_path / "out",
            export_type="html",
        )
        _audit_export_completed(ctx, page_count=10, duration_ms=500)

        mock_logger.log_export.assert_called_once()
        call_args = mock_logger.log_export.call_args[0][0]
        assert call_args.subject_id == "user-1"
        assert call_args.export_type == "html"
        assert call_args.pages_exported == 10
        assert call_args.duration_ms == 500
