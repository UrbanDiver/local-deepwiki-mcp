"""Tests for WatcherConfig, ChangeType, FileChange, and ReindexResult data models."""

from __future__ import annotations

import time

import pytest

from local_deepwiki.watcher import (
    WATCHED_EXTENSIONS,
    ChangeType,
    FileChange,
    ReindexResult,
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
