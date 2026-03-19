"""Tests for reindexing triggers, initial_index, and CLI main() integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import Config
from local_deepwiki.watcher import (
    ChangeType,
    DebouncedHandler,
    FileChange,
    initial_index,
    main,
)


class TestDoReindex:
    """Test _do_reindex async functionality."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        config = Config()
        return DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
        )

    @pytest.mark.asyncio
    async def test_do_reindex_success(self, handler, tmp_path):
        """Test successful reindex operation."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_status = MagicMock()
        mock_status.total_files = 1

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await handler._do_reindex([str(test_file)])

        assert handler._is_processing is False
        mock_indexer.index.assert_called_once()
        mock_generate_wiki.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_reindex_handles_exception(self, handler, tmp_path):
        """Test that reindex handles exceptions gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(side_effect=Exception("Index failed"))
            mock_indexer_class.return_value = mock_indexer

            await handler._do_reindex([str(test_file)])

        # Should not raise, and should reset processing flag
        assert handler._is_processing is False

    @pytest.mark.asyncio
    async def test_do_reindex_shows_truncated_file_list(self, handler, tmp_path):
        """Test that reindex shows only first 10 files when many changed."""
        files = [str(tmp_path / f"file{i}.py") for i in range(15)]
        for f in files:
            Path(f).write_text("# code")

        mock_status = MagicMock()
        mock_status.total_files = 15

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await handler._do_reindex(files)

        # Verify console.print was called with truncation message
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("and 5 more" in str(c) for c in print_calls)

    @pytest.mark.asyncio
    async def test_do_reindex_with_llm_provider(self, handler, tmp_path):
        """Test reindex passes LLM provider to wiki generation."""
        handler.llm_provider = "anthropic"
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_status = MagicMock()
        mock_status.total_files = 1

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console"),
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await handler._do_reindex([str(test_file)])

        # Verify llm_provider was passed
        mock_generate_wiki.assert_called_once()
        call_kwargs = mock_generate_wiki.call_args[1]
        assert call_kwargs["llm_provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_do_reindex_progress_callback_with_total(self, handler, tmp_path):
        """Test progress callback handles total > 0."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_status = MagicMock()
        mock_status.total_files = 1

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()

            # Capture the progress callback and call it
            async def index_with_callback(*args, **kwargs):
                callback = kwargs.get("progress_callback")
                if callback:
                    callback("Processing", 1, 5)  # total > 0
                    callback("Done", 0, 0)  # total == 0
                return mock_status

            mock_indexer.index = index_with_callback
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await handler._do_reindex([str(test_file)])

        # Verify both callback branches were exercised
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("[1/5]" in str(c) for c in print_calls)
        assert any("Done" in str(c) for c in print_calls)


class TestDoReindexWithChanges:
    """Test _do_reindex with FileChange details."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        config = Config()
        return DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
        )

    @pytest.mark.asyncio
    async def test_do_reindex_logs_change_types(self, handler, tmp_path):
        """Test that reindex logs change type summary."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        changes = {
            str(test_file): FileChange(
                path=str(test_file),
                change_type=ChangeType.MODIFIED,
            ),
        }

        mock_status = MagicMock()
        mock_status.total_files = 1

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
            patch("local_deepwiki.watcher.logger") as mock_logger,
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await handler._do_reindex([str(test_file)], changes)

        # Verify change types were logged
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Change types" in str(c) for c in info_calls)

    @pytest.mark.asyncio
    async def test_do_reindex_shows_change_type_in_output(self, handler, tmp_path):
        """Test that reindex shows change type prefix in console output."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        changes = {
            str(test_file): FileChange(
                path=str(test_file),
                change_type=ChangeType.CREATED,
            ),
        }

        mock_status = MagicMock()
        mock_status.total_files = 1

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await handler._do_reindex([str(test_file)], changes)

        # Verify change type shown in output
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("[created]" in str(c) for c in print_calls)


class TestInitialIndex:
    """Test initial_index function."""

    @pytest.mark.asyncio
    async def test_initial_index_success(self, tmp_path):
        """Test successful initial indexing."""
        mock_status = MagicMock()
        mock_status.total_files = 10
        mock_status.total_chunks = 100

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = [MagicMock(), MagicMock()]

        config = Config()

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await initial_index(
                repo_path=tmp_path,
                config=config,
            )

        mock_indexer.index.assert_called_once()
        mock_generate_wiki.assert_called_once()

    @pytest.mark.asyncio
    async def test_initial_index_with_llm_provider(self, tmp_path):
        """Test initial indexing with LLM provider override."""
        mock_status = MagicMock()
        mock_status.total_files = 5
        mock_status.total_chunks = 50

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        config = Config()

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console"),
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await initial_index(
                repo_path=tmp_path,
                config=config,
                llm_provider="openai",
            )

        call_kwargs = mock_generate_wiki.call_args[1]
        assert call_kwargs["llm_provider"] == "openai"

    @pytest.mark.asyncio
    async def test_initial_index_full_rebuild(self, tmp_path):
        """Test initial indexing with full rebuild."""
        mock_status = MagicMock()
        mock_status.total_files = 5
        mock_status.total_chunks = 50

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        config = Config()

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console"),
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(return_value=mock_status)
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await initial_index(
                repo_path=tmp_path,
                config=config,
                full_rebuild=True,
            )

        # Verify full_rebuild passed to indexer
        call_kwargs = mock_indexer.index.call_args[1]
        assert call_kwargs["full_rebuild"] is True

        # Verify full_rebuild passed to wiki generation
        wiki_kwargs = mock_generate_wiki.call_args[1]
        assert wiki_kwargs["full_rebuild"] is True

    @pytest.mark.asyncio
    async def test_initial_index_progress_callback(self, tmp_path):
        """Test initial indexing progress callback paths."""
        mock_status = MagicMock()
        mock_status.total_files = 5
        mock_status.total_chunks = 50

        mock_wiki_structure = MagicMock()
        mock_wiki_structure.pages = []

        config = Config()

        callback_calls = []

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch(
                "local_deepwiki.watcher.generate_wiki", new_callable=AsyncMock
            ) as mock_generate_wiki,
            patch("local_deepwiki.watcher.console") as mock_console,
        ):
            mock_indexer = MagicMock()

            # Capture and call progress callback
            async def index_with_callback(*args, **kwargs):
                callback = kwargs.get("progress_callback")
                if callback:
                    callback("Processing files", 3, 10)  # total > 0
                    callback("Finalizing", 0, 0)  # total == 0
                    callback_calls.append(("Processing files", 3, 10))
                    callback_calls.append(("Finalizing", 0, 0))
                return mock_status

            mock_indexer.index = index_with_callback
            mock_indexer.wiki_path = tmp_path / ".deepwiki"
            mock_indexer.vector_store = MagicMock()
            mock_indexer_class.return_value = mock_indexer

            mock_generate_wiki.return_value = mock_wiki_structure

            await initial_index(
                repo_path=tmp_path,
                config=config,
                no_progress=True,  # Disable progress bars for simpler testing
            )

        # Verify progress callbacks were invoked
        assert len(callback_calls) >= 2
        assert callback_calls[0] == ("Processing files", 3, 10)
        assert callback_calls[1] == ("Finalizing", 0, 0)

        # Verify console output for final status
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("Indexed" in str(c) for c in print_calls)


class TestMain:
    """Test main CLI entry point."""

    def test_main_path_does_not_exist(self, tmp_path):
        """Test main exits when path doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"

        with (
            patch("sys.argv", ["deepwiki-watch", str(nonexistent)]),
            patch("local_deepwiki.watcher.console") as mock_console,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_main_path_is_not_directory(self, tmp_path):
        """Test main exits when path is not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.touch()

        with (
            patch("sys.argv", ["deepwiki-watch", str(file_path)]),
            patch("local_deepwiki.watcher.console") as mock_console,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_main_skip_initial_starts_watcher(self, tmp_path):
        """Test main with --skip-initial starts watcher immediately."""
        with (
            patch("sys.argv", ["deepwiki-watch", str(tmp_path), "--skip-initial"]),
            patch("local_deepwiki.watcher.console"),
            patch("local_deepwiki.watcher.RepositoryWatcher") as mock_watcher_class,
            patch("local_deepwiki.watcher.get_config") as mock_get_config,
            patch("time.sleep", side_effect=KeyboardInterrupt),  # Exit after one loop
        ):
            mock_config = Config()
            mock_get_config.return_value = mock_config

            mock_watcher = MagicMock()
            mock_watcher.is_running.return_value = True
            mock_watcher_class.return_value = mock_watcher

            main()

        mock_watcher.start.assert_called_once()
        mock_watcher.stop.assert_called_once()

    def test_main_with_options(self, tmp_path):
        """Test main with various CLI options."""
        with (
            patch(
                "sys.argv",
                [
                    "deepwiki-watch",
                    str(tmp_path),
                    "--skip-initial",
                    "--debounce",
                    "5.0",
                    "--llm",
                    "anthropic",
                ],
            ),
            patch("local_deepwiki.watcher.console"),
            patch("local_deepwiki.watcher.RepositoryWatcher") as mock_watcher_class,
            patch("local_deepwiki.watcher.get_config") as mock_get_config,
            patch("time.sleep", side_effect=KeyboardInterrupt),
        ):
            mock_config = Config()
            mock_get_config.return_value = mock_config

            mock_watcher = MagicMock()
            mock_watcher.is_running.return_value = True
            mock_watcher_class.return_value = mock_watcher

            main()

        # Verify watcher was created with correct options
        mock_watcher_class.assert_called_once()
        call_kwargs = mock_watcher_class.call_args[1]
        assert call_kwargs["debounce_seconds"] == 5.0
        assert call_kwargs["llm_provider"] == "anthropic"

    def test_main_runs_initial_index(self, tmp_path):
        """Test main runs initial index by default."""

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            coro.close()
            return None

        with (
            patch("sys.argv", ["deepwiki-watch", str(tmp_path)]),
            patch("local_deepwiki.watcher.console"),
            patch(
                "local_deepwiki.watcher.asyncio.run", side_effect=close_coro
            ) as mock_asyncio_run,
            patch("local_deepwiki.watcher.RepositoryWatcher") as mock_watcher_class,
            patch("local_deepwiki.watcher.get_config") as mock_get_config,
            patch("time.sleep", side_effect=KeyboardInterrupt),
        ):
            mock_config = Config()
            mock_get_config.return_value = mock_config

            mock_watcher = MagicMock()
            mock_watcher.is_running.return_value = True
            mock_watcher_class.return_value = mock_watcher

            main()

        # Verify asyncio.run was called (for initial_index)
        mock_asyncio_run.assert_called_once()

    def test_main_with_full_rebuild(self, tmp_path):
        """Test main with --full-rebuild flag."""

        def close_coro(coro):
            """Close coroutine to avoid 'was never awaited' warning."""
            coro.close()
            return None

        with (
            patch("sys.argv", ["deepwiki-watch", str(tmp_path), "--full-rebuild"]),
            patch("local_deepwiki.watcher.console"),
            patch(
                "local_deepwiki.watcher.asyncio.run", side_effect=close_coro
            ) as mock_asyncio_run,
            patch("local_deepwiki.watcher.RepositoryWatcher") as mock_watcher_class,
            patch("local_deepwiki.watcher.get_config") as mock_get_config,
            patch("time.sleep", side_effect=KeyboardInterrupt),
        ):
            mock_config = Config()
            mock_get_config.return_value = mock_config

            mock_watcher = MagicMock()
            mock_watcher.is_running.return_value = True
            mock_watcher_class.return_value = mock_watcher

            main()

        # asyncio.run should be called with initial_index
        mock_asyncio_run.assert_called_once()

    def test_main_default_repo_path(self, monkeypatch, tmp_path):
        """Test main uses current directory as default."""
        monkeypatch.chdir(tmp_path)

        with (
            patch("sys.argv", ["deepwiki-watch", "--skip-initial"]),
            patch("local_deepwiki.watcher.console"),
            patch("local_deepwiki.watcher.RepositoryWatcher") as mock_watcher_class,
            patch("local_deepwiki.watcher.get_config") as mock_get_config,
            patch("time.sleep", side_effect=KeyboardInterrupt),
        ):
            mock_config = Config()
            mock_get_config.return_value = mock_config

            mock_watcher = MagicMock()
            mock_watcher.is_running.return_value = True
            mock_watcher_class.return_value = mock_watcher

            main()

        # Verify watcher was created with current directory
        call_kwargs = mock_watcher_class.call_args[1]
        assert call_kwargs["repo_path"] == tmp_path

    def test_main_watcher_stops_on_interrupt(self, tmp_path):
        """Test main handles KeyboardInterrupt gracefully."""
        loop_count = [0]

        def mock_sleep(seconds):
            loop_count[0] += 1
            if loop_count[0] >= 2:
                raise KeyboardInterrupt

        with (
            patch("sys.argv", ["deepwiki-watch", str(tmp_path), "--skip-initial"]),
            patch("local_deepwiki.watcher.console") as mock_console,
            patch("local_deepwiki.watcher.RepositoryWatcher") as mock_watcher_class,
            patch("local_deepwiki.watcher.get_config") as mock_get_config,
            patch("time.sleep", side_effect=mock_sleep),
        ):
            mock_config = Config()
            mock_get_config.return_value = mock_config

            mock_watcher = MagicMock()
            mock_watcher.is_running.return_value = True
            mock_watcher_class.return_value = mock_watcher

            main()

        # Verify stop was called and graceful shutdown message printed
        mock_watcher.stop.assert_called_once()
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any("Stopping" in str(c) for c in print_calls)
        assert any("Done" in str(c) for c in print_calls)
