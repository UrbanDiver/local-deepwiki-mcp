"""Tests for debounce logic, timing, batching, event handling, and thread safety."""

from __future__ import annotations

from pathlib import Path
from threading import Thread
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import Config
from local_deepwiki.watcher import (
    ChangeType,
    DebouncedHandler,
    FileChange,
)


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

        with patch.object(
            handler, "_do_reindex", new_callable=AsyncMock
        ) as mock_reindex:
            handler._trigger_reindex()

        # Files should be cleared
        assert len(handler._pending_files) == 0
        mock_reindex.assert_called_once()

    def test_trigger_reindex_empty_files(self, handler):
        """Test _trigger_reindex does nothing when no files pending."""
        with patch.object(
            handler, "_do_reindex", new_callable=AsyncMock
        ) as mock_reindex:
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
        assert (
            handler._pending_changes[str(test_file)].change_type == ChangeType.MODIFIED
        )

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
        assert (
            handler._pending_changes[str(test_file)].change_type == ChangeType.CREATED
        )

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
        assert (
            handler._pending_changes[str(test_file)].change_type == ChangeType.DELETED
        )

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
        assert (
            handler._pending_changes[str(dest_file)].change_type == ChangeType.CREATED
        )

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
