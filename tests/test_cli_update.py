"""Tests for the deepwiki update command (cli/update_cli.py)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from local_deepwiki.cli.update_cli import (
    _run_dry_run,
    main,
    run_update,
)
from local_deepwiki.models import FileInfo, IndexStatus, WikiPage, WikiStructure


def _make_index_status(
    repo_path: str = "/tmp/repo",
    total_files: int = 3,
    total_chunks: int = 10,
    files: list | None = None,
    indexed_at: float | None = None,
) -> IndexStatus:
    """Factory for IndexStatus objects used in tests."""
    return IndexStatus(
        repo_path=repo_path,
        indexed_at=indexed_at or time.time(),
        total_files=total_files,
        total_chunks=total_chunks,
        languages={"python": total_files},
        files=files or [],
        schema_version=2,
    )


def _make_wiki_structure(page_count: int = 3) -> WikiStructure:
    """Factory for WikiStructure objects used in tests."""
    pages = [
        WikiPage(
            path=f"page{i}.md",
            title=f"Page {i}",
            content=f"# Page {i}",
            generated_at=time.time(),
        )
        for i in range(page_count)
    ]
    return WikiStructure(root=".", pages=pages)


# ── Dry-run tests ────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_no_existing_index(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"

        # Create a source file so scan finds something
        (tmp_path / "app.py").write_text("print('hello')")

        result = _run_dry_run(tmp_path, wiki_path, console)
        assert result == 0
        captured = capsys.readouterr()
        assert "No existing index" in captured.out
        assert "Source files found" in captured.out

    def test_dry_run_everything_up_to_date(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create a source file and index it with correct hash
        (tmp_path / "app.py").write_text("print('hello')")
        from local_deepwiki.core.parser import _compute_file_hash

        file_hash = _compute_file_hash(tmp_path / "app.py")

        files = [
            FileInfo(
                path="app.py",
                hash=file_hash,
                language="python",
                chunk_count=2,
                size_bytes=100,
                last_modified=1700000000.0,
            ),
        ]
        status = _make_index_status(
            repo_path=str(tmp_path), total_files=1, total_chunks=2, files=files
        )
        import json

        (wiki_path / "index_status.json").write_text(
            json.dumps(status.model_dump(), indent=2)
        )

        result = _run_dry_run(tmp_path, wiki_path, console)
        assert result == 0
        captured = capsys.readouterr()
        assert "up to date" in captured.out

    def test_dry_run_shows_changes(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        # Create a file with a different hash than indexed
        (tmp_path / "app.py").write_text("print('changed')")

        files = [
            FileInfo(
                path="app.py",
                hash="oldhash",
                language="python",
                chunk_count=2,
                size_bytes=100,
                last_modified=1700000000.0,
            ),
            FileInfo(
                path="removed.py",
                hash="deadbeef",
                language="python",
                chunk_count=1,
                size_bytes=50,
                last_modified=1700000000.0,
            ),
        ]
        status = _make_index_status(
            repo_path=str(tmp_path), total_files=2, total_chunks=3, files=files
        )
        import json

        (wiki_path / "index_status.json").write_text(
            json.dumps(status.model_dump(), indent=2)
        )

        result = _run_dry_run(tmp_path, wiki_path, console)
        assert result == 0
        captured = capsys.readouterr()
        # Should show modified (app.py hash changed) and deleted (removed.py not on disk)
        assert "modified" in captured.out.lower() or "~" in captured.out
        assert "deleted" in captured.out.lower() or "-" in captured.out

    def test_run_update_dry_run_flag(self, tmp_path: Path, capsys):
        result = run_update(tmp_path, dry_run=True)
        assert result == 0


class TestDryRunNoIndex:
    def test_first_run_message(self, tmp_path: Path, capsys):
        from rich.console import Console

        console = Console(file=sys.stdout, force_terminal=False)
        wiki_path = tmp_path / ".deepwiki"

        result = _run_dry_run(tmp_path, wiki_path, console)
        assert result == 0
        captured = capsys.readouterr()
        assert "No existing index" in captured.out
        assert "first run" in captured.out.lower()


# ── Full update tests ────────────────────────────────────────────────


class TestFullUpdate:
    def test_calls_indexer_and_generate_wiki(self, tmp_path: Path):
        mock_status = _make_index_status(repo_path=str(tmp_path))
        mock_wiki = _make_wiki_structure()

        mock_indexer_instance = MagicMock()
        mock_indexer_instance.wiki_path = tmp_path / ".deepwiki"
        mock_indexer_instance.vector_store = MagicMock()
        mock_indexer_instance.index = AsyncMock(return_value=mock_status)

        with (
            patch(
                "local_deepwiki.core.indexer.RepositoryIndexer",
                return_value=mock_indexer_instance,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=mock_wiki,
            ) as mock_gen,
            patch("local_deepwiki.config.Config") as mock_config_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            result = run_update(tmp_path)

        assert result == 0
        mock_indexer_instance.index.assert_awaited_once()
        mock_gen.assert_awaited_once()

    def test_full_rebuild_flag(self, tmp_path: Path):
        mock_status = _make_index_status(repo_path=str(tmp_path))
        mock_wiki = _make_wiki_structure()

        mock_indexer_instance = MagicMock()
        mock_indexer_instance.wiki_path = tmp_path / ".deepwiki"
        mock_indexer_instance.vector_store = MagicMock()
        mock_indexer_instance.index = AsyncMock(return_value=mock_status)

        with (
            patch(
                "local_deepwiki.core.indexer.RepositoryIndexer",
                return_value=mock_indexer_instance,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=mock_wiki,
            ),
            patch("local_deepwiki.config.Config") as mock_config_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            result = run_update(tmp_path, full_rebuild=True)

        assert result == 0
        mock_indexer_instance.index.assert_awaited_once_with(
            full_rebuild=True,
            progress_callback=mock_indexer_instance.index.await_args.kwargs[
                "progress_callback"
            ],
        )


class TestFullRebuild:
    def test_full_rebuild_passes_flag(self, tmp_path: Path):
        mock_status = _make_index_status(repo_path=str(tmp_path))
        mock_wiki = _make_wiki_structure()

        mock_indexer_instance = MagicMock()
        mock_indexer_instance.wiki_path = tmp_path / ".deepwiki"
        mock_indexer_instance.vector_store = MagicMock()
        mock_indexer_instance.index = AsyncMock(return_value=mock_status)

        with (
            patch(
                "local_deepwiki.core.indexer.RepositoryIndexer",
                return_value=mock_indexer_instance,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=mock_wiki,
            ) as mock_gen,
            patch("local_deepwiki.config.Config") as mock_config_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            run_update(tmp_path, full_rebuild=True)

        # Verify full_rebuild was passed to both indexer and wiki generator
        call_kwargs = mock_indexer_instance.index.await_args.kwargs
        assert call_kwargs["full_rebuild"] is True

        gen_kwargs = mock_gen.await_args.kwargs
        assert gen_kwargs["full_rebuild"] is True


# ── Error handling ───────────────────────────────────────────────────


class TestRepoNotFound:
    def test_invalid_path_returns_1(self, tmp_path: Path, capsys):
        result = run_update(tmp_path / "nonexistent")
        assert result == 1
        captured = capsys.readouterr()
        assert "Not a directory" in captured.out


class TestNoProgress:
    def test_no_progress_disables_bars(self, tmp_path: Path):
        mock_status = _make_index_status(repo_path=str(tmp_path))
        mock_wiki = _make_wiki_structure()

        mock_indexer_instance = MagicMock()
        mock_indexer_instance.wiki_path = tmp_path / ".deepwiki"
        mock_indexer_instance.vector_store = MagicMock()
        mock_indexer_instance.index = AsyncMock(return_value=mock_status)

        with (
            patch(
                "local_deepwiki.core.indexer.RepositoryIndexer",
                return_value=mock_indexer_instance,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=mock_wiki,
            ),
            patch("local_deepwiki.config.Config") as mock_config_cls,
            patch(
                "local_deepwiki.cli_progress.MultiPhaseProgress"
            ) as mock_progress_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            # Set up the context manager mock
            mock_progress = MagicMock()
            mock_progress.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress.__exit__ = MagicMock(return_value=False)
            mock_progress.get_callback.return_value = None
            mock_progress_cls.return_value = mock_progress

            run_update(tmp_path, no_progress=True)

        mock_progress_cls.assert_called_once_with(disable=True)


class TestKeyboardInterrupt:
    def test_keyboard_interrupt_returns_130(self, tmp_path: Path, capsys):
        with (
            patch(
                "local_deepwiki.cli.update_cli.asyncio.run",
                side_effect=KeyboardInterrupt,
            ),
        ):
            result = run_update(tmp_path)

        assert result == 130
        captured = capsys.readouterr()
        assert "interrupted" in captured.out.lower()


# ── Wiki path override ───────────────────────────────────────────────


class TestWikiPathOverride:
    def test_custom_wiki_path(self, tmp_path: Path):
        mock_status = _make_index_status(repo_path=str(tmp_path))
        mock_wiki = _make_wiki_structure()
        custom_wiki = tmp_path / "custom-docs"

        mock_indexer_instance = MagicMock()
        mock_indexer_instance.wiki_path = tmp_path / ".deepwiki"
        mock_indexer_instance.vector_store = MagicMock()
        mock_indexer_instance.index = AsyncMock(return_value=mock_status)

        with (
            patch(
                "local_deepwiki.core.indexer.RepositoryIndexer",
                return_value=mock_indexer_instance,
            ),
            patch(
                "local_deepwiki.generators.wiki.generate_wiki",
                new_callable=AsyncMock,
                return_value=mock_wiki,
            ) as mock_gen,
            patch("local_deepwiki.config.Config") as mock_config_cls,
        ):
            mock_config_cls.load.return_value = MagicMock()
            run_update(tmp_path, wiki_path=custom_wiki)

        # Verify wiki_path was overridden on the indexer
        assert mock_indexer_instance.wiki_path == custom_wiki


# ── Main dispatch ────────────────────────────────────────────────────


class TestMainDispatch:
    def test_help_flag(self):
        with patch.object(sys, "argv", ["deepwiki update", "--help"]):
            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    def test_default_args_dry_run(self, tmp_path: Path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch.object(sys, "argv", ["deepwiki update", "--dry-run"]):
            result = main()
        assert result == 0

    def test_full_rebuild_flag_parsed(self):
        with (
            patch.object(
                sys, "argv", ["deepwiki update", "--full-rebuild", "--dry-run"]
            ),
            patch(
                "local_deepwiki.cli.update_cli.run_update", return_value=0
            ) as mock_run,
        ):
            main()

        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["full_rebuild"] is True
        assert call_kwargs.kwargs["dry_run"] is True

    def test_custom_wiki_path_parsed(self):
        with (
            patch.object(
                sys,
                "argv",
                ["deepwiki update", "--wiki-path", "/tmp/docs", "--dry-run"],
            ),
            patch(
                "local_deepwiki.cli.update_cli.run_update", return_value=0
            ) as mock_run,
        ):
            main()

        assert mock_run.call_args.kwargs["wiki_path"] == Path("/tmp/docs")
