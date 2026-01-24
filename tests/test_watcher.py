"""Tests for file watcher functionality."""

import sys
import time
from pathlib import Path
from threading import Thread
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import Config
from local_deepwiki.watcher import (
    WATCHED_EXTENSIONS,
    ChangeType,
    DebouncedHandler,
    FileChange,
    ReindexCallback,
    ReindexResult,
    RepositoryWatcher,
    initial_index,
    main,
)


class TestWatchedExtensions:
    """Test that watched extensions are correct."""

    def test_python_extensions(self):
        """Test Python extensions are watched."""
        assert ".py" in WATCHED_EXTENSIONS
        assert ".pyi" in WATCHED_EXTENSIONS

    def test_javascript_extensions(self):
        """Test JavaScript/TypeScript extensions are watched."""
        assert ".js" in WATCHED_EXTENSIONS
        assert ".jsx" in WATCHED_EXTENSIONS
        assert ".ts" in WATCHED_EXTENSIONS
        assert ".tsx" in WATCHED_EXTENSIONS

    def test_other_extensions(self):
        """Test other language extensions are watched."""
        assert ".go" in WATCHED_EXTENSIONS
        assert ".rs" in WATCHED_EXTENSIONS
        assert ".java" in WATCHED_EXTENSIONS
        assert ".c" in WATCHED_EXTENSIONS
        assert ".cpp" in WATCHED_EXTENSIONS
        assert ".swift" in WATCHED_EXTENSIONS


class TestDebouncedHandler:
    """Test DebouncedHandler functionality."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        config = Config()
        return DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,  # Short debounce for testing
        )

    def test_should_watch_python_file(self, handler, tmp_path):
        """Test that Python files are watched."""
        test_file = tmp_path / "test.py"
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is True

    def test_should_watch_typescript_file(self, handler, tmp_path):
        """Test that TypeScript files are watched."""
        test_file = tmp_path / "test.ts"
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is True

    def test_should_not_watch_text_file(self, handler, tmp_path):
        """Test that text files are not watched."""
        test_file = tmp_path / "readme.txt"
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is False

    def test_should_not_watch_json_file(self, handler, tmp_path):
        """Test that JSON files are not watched."""
        test_file = tmp_path / "package.json"
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is False

    def test_should_exclude_node_modules(self, handler, tmp_path):
        """Test that node_modules files are excluded."""
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        test_file = node_modules / "some_pkg" / "index.js"
        test_file.parent.mkdir()
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is False

    def test_should_exclude_venv(self, handler, tmp_path):
        """Test that venv files are excluded."""
        venv = tmp_path / "venv"
        venv.mkdir()
        test_file = venv / "lib" / "test.py"
        test_file.parent.mkdir()
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is False

    def test_should_exclude_pycache(self, handler, tmp_path):
        """Test that __pycache__ files are excluded."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        test_file = pycache / "module.cpython-311.pyc"
        # .pyc isn't in WATCHED_EXTENSIONS anyway, but test the pattern
        # Create a .py file in __pycache__ to test the pattern
        py_file = pycache / "test.py"
        py_file.touch()
        assert handler._should_watch_file(str(py_file)) is False

    def test_should_exclude_git(self, handler, tmp_path):
        """Test that .git files are excluded."""
        git = tmp_path / ".git"
        git.mkdir()
        test_file = git / "hooks" / "pre-commit.py"
        test_file.parent.mkdir()
        test_file.touch()
        # Note: .git/** pattern should exclude this
        # But since .py is watched, we need to verify the pattern works
        # The exclude pattern is ".git/**" which should match
        assert handler._should_watch_file(str(test_file)) is False

    def test_should_watch_nested_file(self, handler, tmp_path):
        """Test that nested source files are watched."""
        src = tmp_path / "src" / "components"
        src.mkdir(parents=True)
        test_file = src / "Button.tsx"
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is True

    def test_file_outside_repo_not_watched(self, handler, tmp_path):
        """Test that files outside repo are not watched."""
        other_dir = tmp_path.parent / "other_project"
        other_dir.mkdir(exist_ok=True)
        test_file = other_dir / "test.py"
        test_file.touch()
        assert handler._should_watch_file(str(test_file)) is False


class TestRepositoryWatcher:
    """Test RepositoryWatcher functionality."""

    def test_create_watcher(self, tmp_path):
        """Test creating a watcher."""
        watcher = RepositoryWatcher(repo_path=tmp_path)
        assert watcher.repo_path == tmp_path
        assert watcher.debounce_seconds == 2.0
        assert not watcher.is_running()

    def test_create_watcher_with_options(self, tmp_path):
        """Test creating a watcher with options."""
        config = Config()
        watcher = RepositoryWatcher(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=5.0,
            llm_provider="anthropic",
        )
        assert watcher.debounce_seconds == 5.0
        assert watcher.llm_provider == "anthropic"

    def test_start_stop_watcher(self, tmp_path):
        """Test starting and stopping a watcher."""
        watcher = RepositoryWatcher(repo_path=tmp_path, debounce_seconds=0.1)

        assert not watcher.is_running()

        watcher.start()
        assert watcher.is_running()

        watcher.stop()
        # Give it a moment to stop
        time.sleep(0.2)
        assert not watcher.is_running()

    def test_stop_without_start(self, tmp_path):
        """Test stopping a watcher that was never started."""
        watcher = RepositoryWatcher(repo_path=tmp_path)
        # Should not raise
        watcher.stop()
        assert not watcher.is_running()


class TestDebouncedHandlerEvents:
    """Test event handling with debouncing."""

    @pytest.fixture
    def handler_with_mock(self, tmp_path):
        """Create a handler with mocked reindex."""
        config = Config()
        handler = DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
        )
        # Mock the reindex method
        handler._do_reindex = AsyncMock()
        return handler

    def test_on_modified_schedules_reindex(self, handler_with_mock, tmp_path):
        """Test that file modification schedules reindex."""
        test_file = tmp_path / "test.py"
        test_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler_with_mock.on_modified(event)

        assert str(test_file) in handler_with_mock._pending_files
        assert handler_with_mock._timer is not None

        # Cancel timer to prevent actual reindex
        handler_with_mock._timer.cancel()

    def test_on_created_schedules_reindex(self, handler_with_mock, tmp_path):
        """Test that file creation schedules reindex."""
        test_file = tmp_path / "new_file.py"
        test_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler_with_mock.on_created(event)

        assert str(test_file) in handler_with_mock._pending_files

        # Cancel timer
        if handler_with_mock._timer:
            handler_with_mock._timer.cancel()

    def test_on_deleted_schedules_reindex(self, handler_with_mock, tmp_path):
        """Test that file deletion schedules reindex."""
        test_file = tmp_path / "deleted.py"
        # Don't create the file, just use the path

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler_with_mock.on_deleted(event)

        assert str(test_file) in handler_with_mock._pending_files

        # Cancel timer
        if handler_with_mock._timer:
            handler_with_mock._timer.cancel()

    def test_directory_events_ignored(self, handler_with_mock, tmp_path):
        """Test that directory events are ignored."""
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(tmp_path / "new_dir")

        handler_with_mock.on_created(event)

        assert len(handler_with_mock._pending_files) == 0
        assert handler_with_mock._timer is None

    def test_on_modified_directory_ignored(self, handler_with_mock, tmp_path):
        """Test that directory modify events are ignored."""
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(tmp_path / "modified_dir")

        handler_with_mock.on_modified(event)

        assert len(handler_with_mock._pending_files) == 0
        assert handler_with_mock._timer is None

    def test_non_watched_file_ignored(self, handler_with_mock, tmp_path):
        """Test that non-watched files are ignored."""
        test_file = tmp_path / "readme.md"
        test_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler_with_mock.on_modified(event)

        assert len(handler_with_mock._pending_files) == 0
        assert handler_with_mock._timer is None

    def test_multiple_changes_debounced(self, handler_with_mock, tmp_path):
        """Test that multiple rapid changes are debounced."""
        files = [tmp_path / f"file{i}.py" for i in range(5)]
        for f in files:
            f.touch()

        for f in files:
            event = MagicMock()
            event.is_directory = False
            event.src_path = str(f)
            handler_with_mock.on_modified(event)

        # All files should be pending
        assert len(handler_with_mock._pending_files) == 5

        # Only one timer should be active
        assert handler_with_mock._timer is not None

        # Cancel timer
        handler_with_mock._timer.cancel()

    def test_on_moved_schedules_reindex_for_source(self, handler_with_mock, tmp_path):
        """Test that file move schedules reindex for source path."""
        src_file = tmp_path / "old_name.py"
        src_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(src_file)
        # No dest_path attribute

        handler_with_mock.on_moved(event)

        assert str(src_file) in handler_with_mock._pending_files

        # Cancel timer
        if handler_with_mock._timer:
            handler_with_mock._timer.cancel()

    def test_on_moved_schedules_reindex_for_dest(self, handler_with_mock, tmp_path):
        """Test that file move schedules reindex for destination path."""
        src_file = tmp_path / "old_name.py"
        dest_file = tmp_path / "new_name.py"
        dest_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(src_file)
        event.dest_path = str(dest_file)

        handler_with_mock.on_moved(event)

        # Both source and dest should be in pending files
        assert str(src_file) in handler_with_mock._pending_files
        assert str(dest_file) in handler_with_mock._pending_files

        # Cancel timer
        if handler_with_mock._timer:
            handler_with_mock._timer.cancel()

    def test_on_moved_directory_ignored(self, handler_with_mock, tmp_path):
        """Test that directory move events are ignored."""
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(tmp_path / "old_dir")

        handler_with_mock.on_moved(event)

        assert len(handler_with_mock._pending_files) == 0
        assert handler_with_mock._timer is None

    def test_on_deleted_directory_ignored(self, handler_with_mock, tmp_path):
        """Test that directory delete events are ignored."""
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(tmp_path / "deleted_dir")

        handler_with_mock.on_deleted(event)

        assert len(handler_with_mock._pending_files) == 0
        assert handler_with_mock._timer is None


class TestTriggerReindex:
    """Test _trigger_reindex functionality."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        config = Config()
        return DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
        )

    def test_trigger_reindex_with_pending_files(self, handler, tmp_path):
        """Test _trigger_reindex runs reindex when files are pending."""
        test_file = tmp_path / "test.py"
        test_file.touch()
        handler._pending_files.add(str(test_file))

        with patch.object(handler, "_do_reindex", new_callable=AsyncMock) as mock_reindex:
            handler._trigger_reindex()

        # Files should be cleared
        assert len(handler._pending_files) == 0
        mock_reindex.assert_called_once()

    def test_trigger_reindex_empty_files(self, handler):
        """Test _trigger_reindex does nothing when no files pending."""
        with patch.object(handler, "_do_reindex", new_callable=AsyncMock) as mock_reindex:
            handler._trigger_reindex()

        mock_reindex.assert_not_called()

    def test_trigger_reindex_reschedules_when_processing(self, handler, tmp_path):
        """Test _trigger_reindex reschedules when already processing."""
        handler._is_processing = True
        handler._pending_files.add(str(tmp_path / "test.py"))

        with patch.object(handler, "_schedule_reindex") as mock_schedule:
            handler._trigger_reindex()

        mock_schedule.assert_called_once()
        # Files should still be pending
        assert len(handler._pending_files) == 1


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
        with (
            patch("sys.argv", ["deepwiki-watch", str(tmp_path)]),
            patch("local_deepwiki.watcher.console"),
            patch("local_deepwiki.watcher.asyncio.run") as mock_asyncio_run,
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
        with (
            patch("sys.argv", ["deepwiki-watch", str(tmp_path), "--full-rebuild"]),
            patch("local_deepwiki.watcher.console"),
            patch("local_deepwiki.watcher.asyncio.run") as mock_asyncio_run,
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


class TestChangeTypeEnum:
    """Test ChangeType enum."""

    def test_change_type_values(self):
        """Test that ChangeType has expected values."""
        assert ChangeType.CREATED.value == "created"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.DELETED.value == "deleted"
        assert ChangeType.MOVED.value == "moved"

    def test_change_type_members(self):
        """Test that all expected members exist."""
        members = list(ChangeType)
        assert len(members) == 4
        assert ChangeType.CREATED in members
        assert ChangeType.MODIFIED in members
        assert ChangeType.DELETED in members
        assert ChangeType.MOVED in members


class TestFileChange:
    """Test FileChange dataclass."""

    def test_file_change_creation(self):
        """Test creating a FileChange."""
        change = FileChange(
            path="/path/to/file.py",
            change_type=ChangeType.MODIFIED,
        )
        assert change.path == "/path/to/file.py"
        assert change.change_type == ChangeType.MODIFIED
        assert change.timestamp > 0
        assert change.dest_path is None

    def test_file_change_with_dest_path(self):
        """Test FileChange with destination path for moved files."""
        change = FileChange(
            path="/old/path.py",
            change_type=ChangeType.MOVED,
            dest_path="/new/path.py",
        )
        assert change.path == "/old/path.py"
        assert change.change_type == ChangeType.MOVED
        assert change.dest_path == "/new/path.py"

    def test_file_change_timestamp_auto_set(self):
        """Test that timestamp is automatically set."""
        before = time.time()
        change = FileChange(path="/file.py", change_type=ChangeType.CREATED)
        after = time.time()
        assert before <= change.timestamp <= after


class TestReindexResult:
    """Test ReindexResult dataclass."""

    def test_reindex_result_success(self):
        """Test successful ReindexResult."""
        result = ReindexResult(
            success=True,
            files_processed=10,
            pages_generated=5,
            duration_seconds=2.5,
        )
        assert result.success is True
        assert result.files_processed == 10
        assert result.pages_generated == 5
        assert result.duration_seconds == 2.5
        assert result.error is None
        assert result.changed_files == []

    def test_reindex_result_failure(self):
        """Test failed ReindexResult."""
        result = ReindexResult(
            success=False,
            files_processed=0,
            pages_generated=0,
            duration_seconds=0.5,
            error="Index failed",
            changed_files=["/path/file.py"],
        )
        assert result.success is False
        assert result.error == "Index failed"
        assert result.changed_files == ["/path/file.py"]


class TestDebouncedHandlerCallback:
    """Test callback mechanism in DebouncedHandler."""

    @pytest.fixture
    def handler_with_callback(self, tmp_path):
        """Create a handler with a callback for testing."""
        config = Config()
        callback_results = []

        def on_complete(result: ReindexResult) -> None:
            callback_results.append(result)

        handler = DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
            on_reindex_complete=on_complete,
        )
        handler._callback_results = callback_results  # For test access
        return handler

    @pytest.mark.asyncio
    async def test_callback_invoked_on_success(self, handler_with_callback, tmp_path):
        """Test that callback is invoked on successful reindex."""
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

            await handler_with_callback._do_reindex([str(test_file)])

        # Verify callback was invoked
        assert len(handler_with_callback._callback_results) == 1
        result = handler_with_callback._callback_results[0]
        assert result.success is True
        assert result.files_processed == 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_callback_invoked_on_failure(self, handler_with_callback, tmp_path):
        """Test that callback is invoked on failed reindex."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        with (
            patch("local_deepwiki.watcher.RepositoryIndexer") as mock_indexer_class,
            patch("local_deepwiki.watcher.console"),
        ):
            mock_indexer = MagicMock()
            mock_indexer.index = AsyncMock(side_effect=Exception("Index failed"))
            mock_indexer_class.return_value = mock_indexer

            await handler_with_callback._do_reindex([str(test_file)])

        # Verify callback was invoked with error
        assert len(handler_with_callback._callback_results) == 1
        result = handler_with_callback._callback_results[0]
        assert result.success is False
        assert result.error == "Index failed"

    @pytest.mark.asyncio
    async def test_callback_exception_handled(self, tmp_path):
        """Test that exceptions in callback are handled gracefully."""
        config = Config()

        def bad_callback(result: ReindexResult) -> None:
            raise RuntimeError("Callback exploded")

        handler = DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
            on_reindex_complete=bad_callback,
        )

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

            # Should not raise despite callback exception
            await handler._do_reindex([str(test_file)])

        # Verify handler state is correct
        assert handler._is_processing is False


class TestChangeTypeTracking:
    """Test that change types are tracked correctly."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        config = Config()
        return DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=0.1,
        )

    def test_modified_change_tracked(self, handler, tmp_path):
        """Test that modified changes are tracked with correct type."""
        test_file = tmp_path / "test.py"
        test_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler.on_modified(event)

        assert str(test_file) in handler._pending_changes
        assert handler._pending_changes[str(test_file)].change_type == ChangeType.MODIFIED

        # Cancel timer
        if handler._timer:
            handler._timer.cancel()

    def test_created_change_tracked(self, handler, tmp_path):
        """Test that created changes are tracked with correct type."""
        test_file = tmp_path / "new_file.py"
        test_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler.on_created(event)

        assert str(test_file) in handler._pending_changes
        assert handler._pending_changes[str(test_file)].change_type == ChangeType.CREATED

        if handler._timer:
            handler._timer.cancel()

    def test_deleted_change_tracked(self, handler, tmp_path):
        """Test that deleted changes are tracked with correct type."""
        test_file = tmp_path / "deleted.py"

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(test_file)

        handler.on_deleted(event)

        assert str(test_file) in handler._pending_changes
        assert handler._pending_changes[str(test_file)].change_type == ChangeType.DELETED

        if handler._timer:
            handler._timer.cancel()

    def test_moved_change_tracked_with_dest(self, handler, tmp_path):
        """Test that moved changes track destination path."""
        src_file = tmp_path / "old_name.py"
        src_file.touch()
        dest_file = tmp_path / "new_name.py"
        dest_file.touch()

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(src_file)
        event.dest_path = str(dest_file)

        handler.on_moved(event)

        # Source should be tracked as MOVED with dest_path
        assert str(src_file) in handler._pending_changes
        change = handler._pending_changes[str(src_file)]
        assert change.change_type == ChangeType.MOVED
        assert change.dest_path == str(dest_file)

        # Dest should be tracked as CREATED
        assert str(dest_file) in handler._pending_changes
        assert handler._pending_changes[str(dest_file)].change_type == ChangeType.CREATED

        if handler._timer:
            handler._timer.cancel()


class TestThreadSafety:
    """Test thread safety of the watcher."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create a handler for testing."""
        config = Config()
        return DebouncedHandler(
            repo_path=tmp_path,
            config=config,
            debounce_seconds=10.0,  # Long debounce to prevent actual trigger
        )

    def test_concurrent_add_pending_change(self, handler, tmp_path):
        """Test that concurrent calls to _add_pending_change are thread-safe."""
        num_files = 100
        files = [tmp_path / f"file{i}.py" for i in range(num_files)]
        for f in files:
            f.touch()

        threads = []
        for i, f in enumerate(files):
            t = Thread(
                target=handler._add_pending_change,
                args=(str(f), ChangeType.MODIFIED),
            )
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # Verify all files were added
        assert len(handler._pending_files) == num_files
        assert len(handler._pending_changes) == num_files

        if handler._timer:
            handler._timer.cancel()

    def test_concurrent_event_handling(self, handler, tmp_path):
        """Test that concurrent event handling is thread-safe."""
        num_events = 50
        files = [tmp_path / f"event{i}.py" for i in range(num_events)]
        for f in files:
            f.touch()

        def simulate_events(file_list: list[Path]) -> None:
            for f in file_list:
                event = MagicMock()
                event.is_directory = False
                event.src_path = str(f)
                handler.on_modified(event)

        # Split files into groups for different threads
        group_size = num_events // 5
        threads = []
        for i in range(5):
            start = i * group_size
            end = start + group_size
            t = Thread(target=simulate_events, args=(files[start:end],))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all files were added
        assert len(handler._pending_files) == num_events

        if handler._timer:
            handler._timer.cancel()


class TestRepositoryWatcherCallback:
    """Test callback mechanism in RepositoryWatcher."""

    def test_create_watcher_with_callback(self, tmp_path):
        """Test creating a watcher with a callback."""
        results = []

        def on_complete(result: ReindexResult) -> None:
            results.append(result)

        watcher = RepositoryWatcher(
            repo_path=tmp_path,
            on_reindex_complete=on_complete,
        )
        assert watcher.on_reindex_complete is on_complete

    def test_callback_passed_to_handler(self, tmp_path):
        """Test that callback is passed to handler on start."""
        results = []

        def on_complete(result: ReindexResult) -> None:
            results.append(result)

        watcher = RepositoryWatcher(
            repo_path=tmp_path,
            on_reindex_complete=on_complete,
            debounce_seconds=0.1,
        )

        watcher.start()
        try:
            assert watcher._handler is not None
            assert watcher._handler.on_reindex_complete is on_complete
        finally:
            watcher.stop()


class TestGetPendingChanges:
    """Test get_pending_changes method."""

    def test_get_pending_changes_empty(self, tmp_path):
        """Test get_pending_changes with no pending changes."""
        watcher = RepositoryWatcher(repo_path=tmp_path)
        watcher.start()
        try:
            changes = watcher.get_pending_changes()
            assert changes == []
        finally:
            watcher.stop()

    def test_get_pending_changes_not_started(self, tmp_path):
        """Test get_pending_changes when watcher not started."""
        watcher = RepositoryWatcher(repo_path=tmp_path)
        changes = watcher.get_pending_changes()
        assert changes == []

    def test_get_pending_changes_with_events(self, tmp_path):
        """Test get_pending_changes returns pending changes."""
        watcher = RepositoryWatcher(
            repo_path=tmp_path,
            debounce_seconds=10.0,  # Long debounce to keep changes pending
        )
        watcher.start()
        try:
            # Simulate a file change directly on handler
            test_file = tmp_path / "test.py"
            test_file.touch()

            event = MagicMock()
            event.is_directory = False
            event.src_path = str(test_file)

            watcher._handler.on_modified(event)

            changes = watcher.get_pending_changes()
            assert len(changes) == 1
            assert changes[0].path == str(test_file)
            assert changes[0].change_type == ChangeType.MODIFIED

            # Cancel timer
            if watcher._handler._timer:
                watcher._handler._timer.cancel()
        finally:
            watcher.stop()


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
