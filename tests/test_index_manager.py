"""Tests for IndexStatusManager class."""

import json
import time
from pathlib import Path

import pytest

from local_deepwiki.core.index_manager import (
    CURRENT_SCHEMA_VERSION,
    INDEX_STATUS_FILE,
    IndexStatusManager,
    _migrate_status,
    _needs_migration,
)
from local_deepwiki.models import FileInfo, IndexStatus, Language


class TestIndexStatusManagerLoad:
    """Tests for IndexStatusManager.load method."""

    def test_load_returns_none_when_file_missing(self, tmp_path):
        """Test that load returns None when status file doesn't exist."""
        manager = IndexStatusManager()
        result = manager.load(tmp_path)
        assert result is None

    def test_load_returns_valid_status(self, tmp_path):
        """Test that load returns a valid IndexStatus from file."""
        manager = IndexStatusManager()

        status_data = {
            "repo_path": "/test/repo",
            "indexed_at": 1234567890.0,
            "total_files": 5,
            "total_chunks": 50,
            "languages": {"python": 5},
            "files": [],
            "schema_version": CURRENT_SCHEMA_VERSION,
        }
        status_path = tmp_path / INDEX_STATUS_FILE
        status_path.write_text(json.dumps(status_data))

        result = manager.load(tmp_path)

        assert result is not None
        assert result.repo_path == "/test/repo"
        assert result.total_files == 5
        assert result.total_chunks == 50

    def test_load_handles_legacy_files_without_schema_version(self, tmp_path):
        """Test that load handles legacy files without schema_version."""
        manager = IndexStatusManager()

        legacy_status = {
            "repo_path": "/test/repo",
            "indexed_at": 1234567890.0,
            "total_files": 5,
            "total_chunks": 50,
            "languages": {"python": 5},
            "files": [],
        }
        status_path = tmp_path / INDEX_STATUS_FILE
        status_path.write_text(json.dumps(legacy_status))

        result = manager.load(tmp_path)

        assert result is not None
        assert result.schema_version == CURRENT_SCHEMA_VERSION

    def test_load_returns_none_for_invalid_json(self, tmp_path):
        """Test that load returns None for invalid JSON."""
        manager = IndexStatusManager()

        status_path = tmp_path / INDEX_STATUS_FILE
        status_path.write_text("not valid json {{{")

        result = manager.load(tmp_path)

        assert result is None

    def test_load_returns_none_for_invalid_data(self, tmp_path):
        """Test that load returns None for data that fails validation."""
        manager = IndexStatusManager()

        invalid_status = {"invalid_field": "value"}
        status_path = tmp_path / INDEX_STATUS_FILE
        status_path.write_text(json.dumps(invalid_status))

        result = manager.load(tmp_path)

        assert result is None


class TestIndexStatusManagerLoadWithMigrationInfo:
    """Tests for IndexStatusManager.load_with_migration_info method."""

    def test_load_with_migration_info_returns_none_when_missing(self, tmp_path):
        """Test that load_with_migration_info returns (None, False) when missing."""
        manager = IndexStatusManager()
        status, requires_rebuild = manager.load_with_migration_info(tmp_path)

        assert status is None
        assert requires_rebuild is False

    def test_load_with_migration_info_returns_status(self, tmp_path):
        """Test that load_with_migration_info returns valid status."""
        manager = IndexStatusManager()

        status_data = {
            "repo_path": "/test/repo",
            "indexed_at": 1234567890.0,
            "total_files": 5,
            "total_chunks": 50,
            "languages": {"python": 5},
            "files": [],
            "schema_version": CURRENT_SCHEMA_VERSION,
        }
        status_path = tmp_path / INDEX_STATUS_FILE
        status_path.write_text(json.dumps(status_data))

        status, requires_rebuild = manager.load_with_migration_info(tmp_path)

        assert status is not None
        assert requires_rebuild is False

    def test_load_with_migration_saves_migrated_status(self, tmp_path):
        """Test that migration saves the updated status file."""
        manager = IndexStatusManager()

        # Create old version status
        old_status = {
            "repo_path": "/test/repo",
            "indexed_at": 1234567890.0,
            "total_files": 5,
            "total_chunks": 50,
            "languages": {"python": 5},
            "files": [],
            "schema_version": 1,
        }
        status_path = tmp_path / INDEX_STATUS_FILE
        status_path.write_text(json.dumps(old_status))

        status, _ = manager.load_with_migration_info(tmp_path)

        # Reload to verify migration was saved
        with open(status_path) as f:
            saved_data = json.load(f)

        assert saved_data["schema_version"] == CURRENT_SCHEMA_VERSION


class TestIndexStatusManagerSave:
    """Tests for IndexStatusManager.save method."""

    def test_save_creates_directory_if_needed(self, tmp_path):
        """Test that save creates the wiki directory if it doesn't exist."""
        manager = IndexStatusManager()
        wiki_path = tmp_path / "subdir" / "wiki"

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=0,
            total_chunks=0,
        )

        manager.save(wiki_path, status)

        assert wiki_path.exists()
        assert (wiki_path / INDEX_STATUS_FILE).exists()

    def test_save_writes_valid_json(self, tmp_path):
        """Test that save writes valid JSON that can be loaded."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=50,
            languages={"python": 5},
            files=[],
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        manager.save(tmp_path, status)

        # Verify we can load it back
        loaded = manager.load(tmp_path)
        assert loaded is not None
        assert loaded.repo_path == status.repo_path
        assert loaded.total_files == status.total_files

    def test_save_overwrites_existing_file(self, tmp_path):
        """Test that save overwrites an existing status file."""
        manager = IndexStatusManager()

        status1 = IndexStatus(
            repo_path="/test/repo1",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=50,
        )
        manager.save(tmp_path, status1)

        status2 = IndexStatus(
            repo_path="/test/repo2",
            indexed_at=1234567891.0,
            total_files=10,
            total_chunks=100,
        )
        manager.save(tmp_path, status2)

        loaded = manager.load(tmp_path)
        assert loaded is not None
        assert loaded.repo_path == "/test/repo2"
        assert loaded.total_files == 10


class TestIndexStatusManagerCreate:
    """Tests for IndexStatusManager.create method."""

    def test_create_with_empty_files(self, tmp_path):
        """Test that create handles empty file list."""
        manager = IndexStatusManager()

        status = manager.create(
            repo_path=tmp_path,
            files=[],
            total_chunks=0,
        )

        assert status.repo_path == str(tmp_path)
        assert status.total_files == 0
        assert status.total_chunks == 0
        assert status.languages == {}
        assert status.schema_version == CURRENT_SCHEMA_VERSION

    def test_create_calculates_language_stats(self, tmp_path):
        """Test that create calculates correct language statistics."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
            FileInfo(
                path="file2.py",
                language=Language.PYTHON,
                size_bytes=200,
                last_modified=time.time(),
                hash="def456",
                chunk_count=10,
            ),
            FileInfo(
                path="file3.js",
                language=Language.JAVASCRIPT,
                size_bytes=150,
                last_modified=time.time(),
                hash="ghi789",
                chunk_count=7,
            ),
        ]

        status = manager.create(
            repo_path=tmp_path,
            files=files,
            total_chunks=22,
        )

        assert status.total_files == 3
        assert status.total_chunks == 22
        assert status.languages == {"python": 2, "javascript": 1}

    def test_create_uses_custom_schema_version(self, tmp_path):
        """Test that create uses custom schema version if provided."""
        manager = IndexStatusManager()

        status = manager.create(
            repo_path=tmp_path,
            files=[],
            total_chunks=0,
            schema_version=1,
        )

        assert status.schema_version == 1

    def test_create_sets_indexed_at_timestamp(self, tmp_path):
        """Test that create sets a valid indexed_at timestamp."""
        manager = IndexStatusManager()
        before = time.time()

        status = manager.create(
            repo_path=tmp_path,
            files=[],
            total_chunks=0,
        )

        after = time.time()
        assert before <= status.indexed_at <= after


class TestIndexStatusManagerValidate:
    """Tests for IndexStatusManager.validate method."""

    def test_validate_returns_empty_for_valid_status(self, tmp_path):
        """Test that validate returns empty list for valid status."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        errors = manager.validate(status)
        assert errors == []

    def test_validate_catches_empty_repo_path(self):
        """Test that validate catches empty repo_path."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="",
            indexed_at=time.time(),
            total_files=0,
            total_chunks=0,
        )

        errors = manager.validate(status)
        assert any("repo_path is empty" in e for e in errors)

    def test_validate_catches_invalid_timestamp(self):
        """Test that validate catches invalid indexed_at timestamp."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=-1.0,
            total_files=0,
            total_chunks=0,
        )

        errors = manager.validate(status)
        assert any("indexed_at" in e for e in errors)

    def test_validate_catches_file_count_mismatch(self):
        """Test that validate catches total_files mismatch."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=10,  # Wrong count
            total_chunks=0,
            files=[],  # Empty list
        )

        errors = manager.validate(status)
        assert any("total_files" in e for e in errors)

    def test_validate_catches_chunk_count_mismatch(self):
        """Test that validate catches total_chunks mismatch."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=100,  # Wrong count
            languages={"python": 1},
            files=files,
        )

        errors = manager.validate(status)
        assert any("total_chunks" in e for e in errors)

    def test_validate_catches_invalid_schema_version(self):
        """Test that validate catches invalid schema_version."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=0,
            total_chunks=0,
            schema_version=0,  # Invalid
        )

        errors = manager.validate(status)
        assert any("schema_version" in e for e in errors)

    def test_validate_catches_future_schema_version(self):
        """Test that validate catches schema_version newer than current."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=0,
            total_chunks=0,
            schema_version=CURRENT_SCHEMA_VERSION + 100,
        )

        errors = manager.validate(status)
        assert any("newer than" in e for e in errors)

    def test_validate_catches_language_mismatch(self):
        """Test that validate catches languages statistics mismatch."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"javascript": 1},  # Wrong language
            files=files,
        )

        errors = manager.validate(status)
        assert any("languages" in e for e in errors)

    def test_validate_catches_missing_hash(self):
        """Test that validate catches files with missing hash."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="",  # Empty hash
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
        )

        errors = manager.validate(status)
        assert any("missing a content hash" in e for e in errors)

    def test_validate_catches_empty_file_path(self):
        """Test that validate catches files with empty path."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="",  # Empty path
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
        )

        errors = manager.validate(status)
        assert any("empty path" in e for e in errors)


class TestIndexStatusManagerNeedsReindex:
    """Tests for IndexStatusManager.needs_reindex method."""

    def test_needs_reindex_returns_true_for_new_file(self):
        """Test that needs_reindex returns True for new files."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=0,
            total_chunks=0,
            files=[],
        )

        result = manager.needs_reindex(status, "new_file.py", "abc123")
        assert result is True

    def test_needs_reindex_returns_true_for_modified_file(self):
        """Test that needs_reindex returns True for modified files."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="old_hash",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
        )

        result = manager.needs_reindex(status, "file1.py", "new_hash")
        assert result is True

    def test_needs_reindex_returns_false_for_unchanged_file(self):
        """Test that needs_reindex returns False for unchanged files."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="same_hash",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
        )

        result = manager.needs_reindex(status, "file1.py", "same_hash")
        assert result is False


class TestIndexStatusManagerGetFilesNeedingReindex:
    """Tests for IndexStatusManager.get_files_needing_reindex method."""

    def test_get_files_needing_reindex_identifies_new_files(self):
        """Test that get_files_needing_reindex identifies new files."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=0,
            total_chunks=0,
            files=[],
        )

        current_files = {"new_file.py": "abc123"}
        new_files, modified_files, deleted_files = manager.get_files_needing_reindex(
            status, current_files
        )

        assert new_files == ["new_file.py"]
        assert modified_files == []
        assert deleted_files == []

    def test_get_files_needing_reindex_identifies_modified_files(self):
        """Test that get_files_needing_reindex identifies modified files."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="old_hash",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
        )

        current_files = {"file1.py": "new_hash"}
        new_files, modified_files, deleted_files = manager.get_files_needing_reindex(
            status, current_files
        )

        assert new_files == []
        assert modified_files == ["file1.py"]
        assert deleted_files == []

    def test_get_files_needing_reindex_identifies_deleted_files(self):
        """Test that get_files_needing_reindex identifies deleted files."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="file1.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=files,
        )

        current_files = {}  # File deleted
        new_files, modified_files, deleted_files = manager.get_files_needing_reindex(
            status, current_files
        )

        assert new_files == []
        assert modified_files == []
        assert deleted_files == ["file1.py"]

    def test_get_files_needing_reindex_handles_mixed_changes(self):
        """Test that get_files_needing_reindex handles mixed changes."""
        manager = IndexStatusManager()

        files = [
            FileInfo(
                path="existing.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="old_hash",
                chunk_count=5,
            ),
            FileInfo(
                path="deleted.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=3,
            ),
            FileInfo(
                path="unchanged.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="same_hash",
                chunk_count=2,
            ),
        ]

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=3,
            total_chunks=10,
            languages={"python": 3},
            files=files,
        )

        current_files = {
            "existing.py": "new_hash",  # Modified
            "unchanged.py": "same_hash",  # Unchanged
            "new_file.py": "brand_new",  # New
        }

        new_files, modified_files, deleted_files = manager.get_files_needing_reindex(
            status, current_files
        )

        assert "new_file.py" in new_files
        assert "existing.py" in modified_files
        assert "deleted.py" in deleted_files
        assert "unchanged.py" not in new_files
        assert "unchanged.py" not in modified_files


class TestIndexStatusManagerComputeStatusHash:
    """Tests for IndexStatusManager.compute_status_hash method."""

    def test_compute_status_hash_returns_string(self):
        """Test that compute_status_hash returns a string hash."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=50,
        )

        hash_value = manager.compute_status_hash(status)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex digest

    def test_compute_status_hash_is_deterministic(self):
        """Test that compute_status_hash returns same hash for same status."""
        manager = IndexStatusManager()

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=50,
        )

        hash1 = manager.compute_status_hash(status)
        hash2 = manager.compute_status_hash(status)

        assert hash1 == hash2

    def test_compute_status_hash_differs_for_different_status(self):
        """Test that compute_status_hash returns different hash for different status."""
        manager = IndexStatusManager()

        status1 = IndexStatus(
            repo_path="/test/repo1",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=50,
        )

        status2 = IndexStatus(
            repo_path="/test/repo2",
            indexed_at=1234567890.0,
            total_files=5,
            total_chunks=50,
        )

        hash1 = manager.compute_status_hash(status1)
        hash2 = manager.compute_status_hash(status2)

        assert hash1 != hash2


class TestIndexStatusManagerMergeFiles:
    """Tests for IndexStatusManager.merge_files method."""

    def test_merge_files_combines_lists(self):
        """Test that merge_files combines file lists correctly."""
        manager = IndexStatusManager()

        processed = [
            FileInfo(
                path="new.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        unchanged = [
            FileInfo(
                path="old.py",
                language=Language.PYTHON,
                size_bytes=200,
                last_modified=time.time(),
                hash="def456",
                chunk_count=10,
            ),
        ]

        all_files, total_chunks = manager.merge_files(processed, unchanged, 5)

        assert len(all_files) == 2
        assert total_chunks == 15  # 5 new + 10 unchanged

    def test_merge_files_handles_empty_processed(self):
        """Test that merge_files handles empty processed list."""
        manager = IndexStatusManager()

        unchanged = [
            FileInfo(
                path="old.py",
                language=Language.PYTHON,
                size_bytes=200,
                last_modified=time.time(),
                hash="def456",
                chunk_count=10,
            ),
        ]

        all_files, total_chunks = manager.merge_files([], unchanged, 0)

        assert len(all_files) == 1
        assert total_chunks == 10

    def test_merge_files_handles_empty_unchanged(self):
        """Test that merge_files handles empty unchanged list."""
        manager = IndexStatusManager()

        processed = [
            FileInfo(
                path="new.py",
                language=Language.PYTHON,
                size_bytes=100,
                last_modified=time.time(),
                hash="abc123",
                chunk_count=5,
            ),
        ]

        all_files, total_chunks = manager.merge_files(processed, [], 5)

        assert len(all_files) == 1
        assert total_chunks == 5


class TestMigrationFunctions:
    """Tests for migration helper functions."""

    def test_needs_migration_returns_true_for_old_version(self):
        """Test that _needs_migration returns True for old schema versions."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=0,
            total_chunks=0,
            schema_version=1,
        )

        if CURRENT_SCHEMA_VERSION > 1:
            assert _needs_migration(status) is True

    def test_needs_migration_returns_false_for_current_version(self):
        """Test that _needs_migration returns False for current schema version."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=0,
            total_chunks=0,
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        assert _needs_migration(status) is False

    def test_migrate_status_updates_version(self):
        """Test that _migrate_status updates the schema version."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=10,
            total_chunks=100,
            schema_version=1,
        )

        migrated, _ = _migrate_status(status)

        assert migrated.schema_version == CURRENT_SCHEMA_VERSION

    def test_migrate_status_preserves_data(self):
        """Test that _migrate_status preserves existing data."""
        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=10,
            total_chunks=100,
            languages={"python": 8, "javascript": 2},
            schema_version=1,
        )

        migrated, _ = _migrate_status(status)

        assert migrated.repo_path == "/test/repo"
        assert migrated.indexed_at == 1234567890.0
        assert migrated.total_files == 10
        assert migrated.total_chunks == 100
        assert migrated.languages == {"python": 8, "javascript": 2}


class TestCustomStatusFilename:
    """Tests for using custom status filename."""

    def test_custom_filename(self, tmp_path):
        """Test that custom status filename is used correctly."""
        manager = IndexStatusManager(status_filename="custom_status.json")

        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=time.time(),
            total_files=5,
            total_chunks=50,
        )

        manager.save(tmp_path, status)

        assert (tmp_path / "custom_status.json").exists()
        assert not (tmp_path / INDEX_STATUS_FILE).exists()

        loaded = manager.load(tmp_path)
        assert loaded is not None
        assert loaded.total_files == 5
