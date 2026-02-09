"""Index status management with centralized load/save/validation logic."""

import hashlib
import json
import time
from pathlib import Path

from local_deepwiki.logging import get_logger
from local_deepwiki.models import FileInfo, IndexStatus

logger = get_logger(__name__)

# Schema version for tracking index format changes.
# Increment this when the schema changes in a way that requires re-indexing.
# Version history:
#   1 - Initial schema (all versions prior to explicit versioning)
#   2 - Added schema_version field and scalar indexes on id/file_path columns
CURRENT_SCHEMA_VERSION = 2

INDEX_STATUS_FILE = "index_status.json"


def _needs_migration(status: IndexStatus) -> bool:
    """Check if an index status needs migration to the current schema version.

    Args:
        status: The loaded index status.

    Returns:
        True if the schema version is older than current and needs migration.
    """
    return status.schema_version < CURRENT_SCHEMA_VERSION


def _migrate_status(status: IndexStatus) -> tuple[IndexStatus, bool]:
    """Migrate an index status to the current schema version.

    This function handles migrations between schema versions. Each migration
    step should be idempotent and handle the transition from version N to N+1.

    Args:
        status: The index status to migrate.

    Returns:
        Tuple of (migrated status, requires_rebuild).
        requires_rebuild is True if the vector store needs to be rebuilt.
    """
    requires_rebuild = False
    current_version = status.schema_version

    # Migration from version 1 to 2
    # Version 2 added scalar indexes - the index data is compatible but
    # indexes need to be created (handled by _ensure_scalar_indexes in VectorStore)
    if current_version < 2:
        logger.info("Migrating index status from schema version 1 to 2")
        # No data migration needed - indexes are created on table open
        current_version = 2

    # Update schema version
    status.schema_version = current_version

    return status, requires_rebuild


class IndexStatusManager:
    """Manages index status operations including load, save, create, and validate.

    This class consolidates all index status management logic that was previously
    spread across RepositoryIndexer and handlers. It provides a single point of
    responsibility for:
    - Loading index status from manifest files
    - Saving index status to manifest files
    - Creating new index status instances
    - Validating index status integrity
    - Checking if files need reindexing
    """

    def __init__(self, status_filename: str = INDEX_STATUS_FILE):
        """Initialize the index status manager.

        Args:
            status_filename: Name of the index status file (default: index_status.json).
        """
        self.status_filename = status_filename

    def load(self, wiki_path: Path) -> IndexStatus | None:
        """Load index status from a wiki directory.

        Handles legacy files without schema_version and performs migration
        if needed.

        Args:
            wiki_path: Path to the wiki directory containing the index status file.

        Returns:
            IndexStatus if found and valid, None otherwise.
        """
        status, _ = self.load_with_migration_info(wiki_path)
        return status

    def load_with_migration_info(
        self, wiki_path: Path
    ) -> tuple[IndexStatus | None, bool]:
        """Load index status and return migration information.

        Args:
            wiki_path: Path to the wiki directory containing the index status file.

        Returns:
            Tuple of (IndexStatus or None, requires_rebuild).
            requires_rebuild is True if the index should be fully rebuilt.
        """
        status_path = wiki_path / self.status_filename
        if not status_path.exists():
            return None, False

        try:
            with open(status_path) as f:
                data = json.load(f)

            # Handle legacy status files without schema_version
            if "schema_version" not in data:
                data["schema_version"] = 1

            status = IndexStatus.model_validate(data)

            # Check if migration is needed
            if _needs_migration(status):
                status, requires_rebuild = _migrate_status(status)
                # Save the migrated status
                self.save(wiki_path, status)
                return status, requires_rebuild

            return status, False
        except (json.JSONDecodeError, OSError, ValueError) as e:
            # json.JSONDecodeError: Corrupted or invalid JSON
            # OSError: File read issues
            # ValueError: Pydantic validation failure
            logger.warning(f"Failed to load index status from {status_path}: {e}")
            return None, False

    def save(self, wiki_path: Path, status: IndexStatus) -> None:
        """Save index status to a wiki directory.

        Creates the wiki directory if it doesn't exist.

        Args:
            wiki_path: Path to the wiki directory.
            status: The IndexStatus to save.
        """
        wiki_path.mkdir(parents=True, exist_ok=True)
        status_path = wiki_path / self.status_filename
        # Atomic write: write to temp file then rename to avoid corruption on crash
        tmp_path = status_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(status.model_dump(), f, indent=2)
                f.flush()
            tmp_path.replace(status_path)
        except Exception:
            # Clean up temp file on failure (OSError from write, json errors, etc.)
            # but do not catch KeyboardInterrupt or SystemExit
            tmp_path.unlink(missing_ok=True)
            raise

    def create(
        self,
        repo_path: Path,
        files: list[FileInfo],
        total_chunks: int,
        schema_version: int | None = None,
    ) -> IndexStatus:
        """Create a new index status with calculated statistics.

        Args:
            repo_path: Path to the repository being indexed.
            files: List of FileInfo objects for all indexed files.
            total_chunks: Total number of chunks across all files.
            schema_version: Optional schema version (defaults to CURRENT_SCHEMA_VERSION).

        Returns:
            A new IndexStatus instance with calculated language statistics.
        """
        # Calculate language statistics
        languages: dict[str, int] = {}
        for file_info in files:
            if file_info.language:
                lang = file_info.language.value
                languages[lang] = languages.get(lang, 0) + 1

        return IndexStatus(
            repo_path=str(repo_path),
            indexed_at=time.time(),
            total_files=len(files),
            total_chunks=total_chunks,
            languages=languages,
            files=files,
            schema_version=schema_version or CURRENT_SCHEMA_VERSION,
        )

    def validate(self, status: IndexStatus) -> list[str]:
        """Validate an index status and return a list of errors.

        Checks for:
        - Valid repo_path
        - Positive indexed_at timestamp
        - Consistent file counts
        - Valid schema version
        - File integrity (hashes present, etc.)

        Args:
            status: The IndexStatus to validate.

        Returns:
            List of validation error messages. Empty list means valid.
        """
        errors: list[str] = []

        # Check repo_path
        if not status.repo_path:
            errors.append("repo_path is empty")
        elif not Path(status.repo_path).is_absolute():
            # repo_path should be absolute for clarity
            pass  # This is a warning, not an error

        # Check indexed_at timestamp
        if status.indexed_at <= 0:
            errors.append("indexed_at must be a positive timestamp")

        # Check file count consistency
        if status.total_files != len(status.files):
            errors.append(
                f"total_files ({status.total_files}) does not match "
                f"number of files ({len(status.files)})"
            )

        # Check chunk count consistency
        actual_chunks = sum(f.chunk_count for f in status.files)
        if status.total_chunks != actual_chunks:
            errors.append(
                f"total_chunks ({status.total_chunks}) does not match "
                f"sum of file chunk counts ({actual_chunks})"
            )

        # Check schema version
        if status.schema_version < 1:
            errors.append("schema_version must be at least 1")
        elif status.schema_version > CURRENT_SCHEMA_VERSION:
            errors.append(
                f"schema_version ({status.schema_version}) is newer than "
                f"current version ({CURRENT_SCHEMA_VERSION})"
            )

        # Check language statistics consistency
        language_counts: dict[str, int] = {}
        for file_info in status.files:
            if file_info.language:
                lang = file_info.language.value
                language_counts[lang] = language_counts.get(lang, 0) + 1

        if language_counts != status.languages:
            errors.append("languages statistics do not match file languages")

        # Check file integrity
        for file_info in status.files:
            if not file_info.hash:
                errors.append(f"File {file_info.path} is missing a content hash")
            if not file_info.path:
                errors.append("Found a file with empty path")

        return errors

    def needs_reindex(
        self,
        status: IndexStatus,
        file_path: str,
        file_hash: str,
    ) -> bool:
        """Check if a specific file needs reindexing.

        Compares the current file hash with the stored hash to determine
        if the file has changed since last indexing.

        Args:
            status: The current index status.
            file_path: Relative path to the file from repo root.
            file_hash: Current hash of the file content.

        Returns:
            True if the file needs reindexing (new or changed), False otherwise.
        """
        # Build lookup map for efficient access
        files_by_path = {f.path: f for f in status.files}

        prev_file = files_by_path.get(file_path)
        if prev_file is None:
            # New file
            return True

        # File exists - check if hash changed
        return prev_file.hash != file_hash

    def get_files_needing_reindex(
        self,
        status: IndexStatus,
        current_files: dict[str, str],
    ) -> tuple[list[str], list[str], list[str]]:
        """Get lists of files that need processing.

        Compares current files with the index status to identify:
        - New files (not in previous index)
        - Modified files (hash changed)
        - Deleted files (in previous index but not in current)

        Args:
            status: The current index status.
            current_files: Dict mapping file paths to their current hashes.

        Returns:
            Tuple of (new_files, modified_files, deleted_files).
        """
        prev_files = {f.path: f.hash for f in status.files}

        new_files: list[str] = []
        modified_files: list[str] = []
        deleted_files: list[str] = []

        # Check current files
        for path, current_hash in current_files.items():
            if path not in prev_files:
                new_files.append(path)
            elif prev_files[path] != current_hash:
                modified_files.append(path)

        # Check for deleted files
        for path in prev_files:
            if path not in current_files:
                deleted_files.append(path)

        return new_files, modified_files, deleted_files

    def compute_status_hash(self, status: IndexStatus) -> str:
        """Compute a hash of the index status for change detection.

        This hash can be used to detect if the index has changed since
        last wiki generation.

        Args:
            status: The IndexStatus to hash.

        Returns:
            SHA-256 hex digest of the status.
        """
        return hashlib.sha256(
            json.dumps(status.model_dump(), sort_keys=True).encode()
        ).hexdigest()

    def merge_files(
        self,
        processed_files: list[FileInfo],
        unchanged_files: list[FileInfo],
        total_new_chunks: int,
    ) -> tuple[list[FileInfo], int]:
        """Merge processed files with unchanged files for final status.

        Args:
            processed_files: Files that were newly processed.
            unchanged_files: Files that were unchanged from previous index.
            total_new_chunks: Number of chunks from newly processed files.

        Returns:
            Tuple of (all_files, total_chunks).
        """
        all_files = processed_files + unchanged_files
        total_chunks = total_new_chunks + sum(f.chunk_count for f in unchanged_files)
        return all_files, total_chunks
