"""Tests for CLI parameter object dataclasses.

Validates that ``UpdateContext``, ``WizardConfig``, and
``SearchSessionConfig`` are frozen, store defaults correctly, and are
accepted by the functions that previously took loose parameters.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from local_deepwiki.cli.init_cli import WizardConfig
from local_deepwiki.cli.interactive_search import SearchSessionConfig
from local_deepwiki.cli.update_cli import UpdateContext


# ── UpdateContext ───────────────────────────────────────────────────────


class TestUpdateContext:
    """UpdateContext is a frozen dataclass with sensible defaults."""

    def test_frozen(self, tmp_path: Path):
        ctx = UpdateContext(repo_path=tmp_path, wiki_path=tmp_path / ".deepwiki")
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.repo_path = tmp_path / "other"  # type: ignore[misc]

    def test_defaults(self, tmp_path: Path):
        ctx = UpdateContext(repo_path=tmp_path, wiki_path=tmp_path / ".deepwiki")
        assert ctx.full_rebuild is False
        assert ctx.no_progress is False
        assert ctx.console is None

    def test_resolved_console_default(self, tmp_path: Path):
        ctx = UpdateContext(repo_path=tmp_path, wiki_path=tmp_path / ".deepwiki")
        console = ctx.resolved_console
        assert isinstance(console, Console)

    def test_resolved_console_provided(self, tmp_path: Path):
        custom = Console()
        ctx = UpdateContext(
            repo_path=tmp_path,
            wiki_path=tmp_path / ".deepwiki",
            console=custom,
        )
        assert ctx.resolved_console is custom

    def test_all_fields(self, tmp_path: Path):
        console = Console()
        ctx = UpdateContext(
            repo_path=tmp_path,
            wiki_path=tmp_path / "docs",
            full_rebuild=True,
            no_progress=True,
            console=console,
        )
        assert ctx.repo_path == tmp_path
        assert ctx.wiki_path == tmp_path / "docs"
        assert ctx.full_rebuild is True
        assert ctx.no_progress is True
        assert ctx.console is console

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(UpdateContext)

    def test_equality(self, tmp_path: Path):
        a = UpdateContext(repo_path=tmp_path, wiki_path=tmp_path / ".deepwiki")
        b = UpdateContext(repo_path=tmp_path, wiki_path=tmp_path / ".deepwiki")
        assert a == b

    def test_inequality(self, tmp_path: Path):
        a = UpdateContext(repo_path=tmp_path, wiki_path=tmp_path / ".deepwiki")
        b = UpdateContext(
            repo_path=tmp_path,
            wiki_path=tmp_path / ".deepwiki",
            full_rebuild=True,
        )
        assert a != b


# ── WizardConfig ────────────────────────────────────────────────────────


class TestWizardConfig:
    """WizardConfig is a frozen dataclass with sensible defaults."""

    def test_frozen(self, tmp_path: Path):
        cfg = WizardConfig(repo_path=tmp_path, console=Console())
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.repo_path = tmp_path / "other"  # type: ignore[misc]

    def test_defaults(self, tmp_path: Path):
        cfg = WizardConfig(repo_path=tmp_path, console=Console())
        assert cfg.non_interactive is False
        assert cfg.force is False
        assert cfg.provider_flag is None
        assert cfg.embedding_flag is None
        assert cfg.config_dest is None

    def test_all_fields(self, tmp_path: Path):
        console = Console()
        dest = tmp_path / "config.yaml"
        cfg = WizardConfig(
            repo_path=tmp_path,
            console=console,
            non_interactive=True,
            force=True,
            provider_flag="anthropic",
            embedding_flag="openai",
            config_dest=dest,
        )
        assert cfg.repo_path == tmp_path
        assert cfg.console is console
        assert cfg.non_interactive is True
        assert cfg.force is True
        assert cfg.provider_flag == "anthropic"
        assert cfg.embedding_flag == "openai"
        assert cfg.config_dest == dest

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(WizardConfig)

    def test_run_wizard_accepts_wizard_config(self, tmp_path: Path):
        """run_wizard should accept a WizardConfig directly."""
        from unittest.mock import patch

        from local_deepwiki.cli.init_cli import run_wizard

        dest = tmp_path / "config.yaml"
        console = MagicMock()

        cfg = WizardConfig(
            repo_path=tmp_path,
            console=console,
            non_interactive=True,
            config_dest=dest,
        )

        with (
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config", return_value=None
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": True,
                    "anthropic": False,
                    "openai": False,
                },
            ),
        ):
            result = run_wizard(cfg)

        assert result == 0
        assert dest.exists()


# ── SearchSessionConfig ─────────────────────────────────────────────────


class TestSearchSessionConfig:
    """SearchSessionConfig is a frozen dataclass with sensible defaults."""

    def test_frozen(self, tmp_path: Path):
        cfg = SearchSessionConfig(repo_path=tmp_path)
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.repo_path = tmp_path / "other"  # type: ignore[misc]

    def test_defaults(self, tmp_path: Path):
        cfg = SearchSessionConfig(repo_path=tmp_path)
        assert cfg.query is None
        assert cfg.language is None
        assert cfg.chunk_type is None
        assert cfg.file_pattern is None
        assert cfg.min_score == 0.0
        assert cfg.limit == 20
        assert cfg.interactive is True
        assert cfg.show_preview is False

    def test_all_fields(self, tmp_path: Path):
        cfg = SearchSessionConfig(
            repo_path=tmp_path,
            query="search term",
            language="python",
            chunk_type="function",
            file_pattern="*.py",
            min_score=0.5,
            limit=10,
            interactive=False,
            show_preview=True,
        )
        assert cfg.repo_path == tmp_path
        assert cfg.query == "search term"
        assert cfg.language == "python"
        assert cfg.chunk_type == "function"
        assert cfg.file_pattern == "*.py"
        assert cfg.min_score == 0.5
        assert cfg.limit == 10
        assert cfg.interactive is False
        assert cfg.show_preview is True

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(SearchSessionConfig)

    async def test_run_search_accepts_config(self, tmp_path: Path):
        """run_search should accept a SearchSessionConfig directly.

        Imports are done inside the test to stay resilient to module
        reloads that ``pytest-randomly`` may trigger via other test
        files (e.g. ``test_interactive_search_cli.py``).
        """
        from unittest.mock import AsyncMock, patch

        import local_deepwiki.cli.interactive_search as mod

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        cfg = mod.SearchSessionConfig(
            repo_path=repo_path,
            query="test",
            interactive=False,
        )

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await mod.run_search(cfg)

                    mock_store.search.assert_called()

    async def test_run_search_legacy_kwargs_still_work(self, tmp_path: Path):
        """run_search should still accept the old keyword-argument style.

        Imports are done inside the test to stay resilient to module
        reloads that ``pytest-randomly`` may trigger via other test
        files.
        """
        from unittest.mock import AsyncMock, patch

        import local_deepwiki.cli.interactive_search as mod

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".deepwiki" / "vectordb").mkdir(parents=True)

        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.cli.interactive_search.Console") as mock_console_cls:
            mock_console = MagicMock()
            mock_console_cls.return_value = mock_console

            with patch("local_deepwiki.cli.interactive_search.get_embedding_provider"):
                with patch(
                    "local_deepwiki.cli.interactive_search.VectorStore",
                    return_value=mock_store,
                ):
                    await mod.run_search(
                        repo_path=repo_path,
                        query="test",
                        interactive=False,
                    )

                    mock_store.search.assert_called()

    def test_equality(self, tmp_path: Path):
        a = SearchSessionConfig(repo_path=tmp_path, query="test")
        b = SearchSessionConfig(repo_path=tmp_path, query="test")
        assert a == b

    def test_inequality(self, tmp_path: Path):
        a = SearchSessionConfig(repo_path=tmp_path, query="test")
        b = SearchSessionConfig(repo_path=tmp_path, query="other")
        assert a != b
