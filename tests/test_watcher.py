"""Tests for file watcher functionality."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import Config
from local_deepwiki.watcher import WATCHED_EXTENSIONS, DebouncedHandler, RepositoryWatcher


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
