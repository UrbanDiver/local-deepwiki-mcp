"""Tests for RepositoryWatcher, callbacks, and pending changes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import Config
from local_deepwiki.watcher import (
    ChangeType,
    DebouncedHandler,
    ReindexResult,
    RepositoryWatcher,
)


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
        import time

        watcher = RepositoryWatcher(repo_path=tmp_path, debounce_seconds=0.1)

        assert not watcher.is_running()

        watcher.start()
        assert watcher.is_running()

        watcher.stop()
        # Give it a moment to stop
        time.sleep(0.5)
        assert not watcher.is_running()

    def test_stop_without_start(self, tmp_path):
        """Test stopping a watcher that was never started."""
        watcher = RepositoryWatcher(repo_path=tmp_path)
        # Should not raise
        watcher.stop()
        assert not watcher.is_running()


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
