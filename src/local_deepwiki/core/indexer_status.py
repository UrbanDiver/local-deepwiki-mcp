"""Index status tracking concern extracted from RepositoryIndexer.

Handles loading, saving, and managing index status for incremental updates.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from local_deepwiki.core.index_manager import IndexStatusManager
from local_deepwiki.core.indexer_files import (
    compute_files_to_process,
    detect_deleted_files,
)
from local_deepwiki.models import FileInfo, IndexStatus, ProgressCallback

if TYPE_CHECKING:
    from local_deepwiki.core.parser import ASTCache, CodeParser


class IndexStatusTracker:
    """Tracks index status for incremental updates.

    This class encapsulates the status/file management concern that was
    previously part of RepositoryIndexer, following the Single Responsibility
    Principle.

    Args:
        wiki_path: Path to the wiki output directory.
        repo_path: Resolved path to the repository root.
        status_manager: IndexStatusManager instance for persistence.
        find_source_files_fn: Callable that returns the list of source files.
        parser: CodeParser for file info lookups.
        host_module: The parent module (``indexer``) whose ``logger`` attribute
            is used at call time, so that test patches take effect.
        ast_cache: Optional AST cache for logging stats on save.
    """

    def __init__(
        self,
        wiki_path: Path,
        repo_path: Path,
        status_manager: IndexStatusManager,
        find_source_files_fn: Callable[[], list[Path]],
        parser: CodeParser,
        host_module: ModuleType,
        ast_cache: ASTCache | None = None,
    ) -> None:
        self.wiki_path = wiki_path
        self.repo_path = repo_path
        self._status_manager = status_manager
        self._find_source_files = find_source_files_fn
        self.parser = parser
        self._host = host_module
        self.ast_cache = ast_cache

    def load_previous_status(
        self, full_rebuild: bool
    ) -> tuple[IndexStatus | None, dict[str, FileInfo], bool]:
        """Load and validate previous index status for incremental updates.

        Args:
            full_rebuild: If True, skip loading previous status.

        Returns:
            Tuple of (previous_status, prev_files_by_path, full_rebuild_required).
            prev_files_by_path is a hash map for O(1) lookups.
            full_rebuild_required may be True if schema migration requires it.
        """
        if full_rebuild:
            return None, {}, full_rebuild

        previous_status, requires_rebuild = (
            self._status_manager.load_with_migration_info(self.wiki_path)
        )
        if requires_rebuild:
            self._host.logger.info("Schema migration requires full rebuild")
            return None, {}, True

        if previous_status:
            self._host.logger.debug(
                "Loaded previous index status: %d files", previous_status.total_files
            )
            # Pre-build hash map for O(1) lookups instead of O(N) linear scan per file
            # This reduces O(N*M) to O(N+M) for file comparison
            prev_files_by_path = {f.path: f for f in previous_status.files}
            return previous_status, prev_files_by_path, full_rebuild

        return None, {}, full_rebuild

    def collect_files_to_process(
        self,
        prev_files_by_path: dict[str, FileInfo],
        progress_callback: ProgressCallback | None,
    ) -> tuple[list[Path], list[FileInfo], list[str]]:
        """Gather source files and determine what needs processing.

        Args:
            prev_files_by_path: Hash map of previous files for O(1) lookup.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (files_to_process, files_unchanged, deleted_file_paths).
            deleted_file_paths contains relative paths of files that existed in the
            previous index but are no longer present on disk.
        """
        source_files = list(self._find_source_files())
        self._host.logger.info("Found %s source files to consider", len(source_files))

        if progress_callback:
            progress_callback(
                "Found source files", len(source_files), len(source_files)
            )

        files_to_process, files_unchanged = compute_files_to_process(
            source_files=source_files,
            parser=self.parser,
            repo_path=self.repo_path,
            prev_files_by_path=prev_files_by_path,
        )

        # Build the set of current relative paths for deleted file detection
        current_file_paths: set[str] = set()
        for file_path in source_files:
            file_info = self.parser.get_file_info(file_path, self.repo_path)
            current_file_paths.add(file_info.path)

        deleted_file_paths = detect_deleted_files(
            prev_files_by_path, current_file_paths
        )

        if deleted_file_paths:
            self._host.logger.info(
                "Detected %d deleted file(s): %s",
                len(deleted_file_paths),
                deleted_file_paths,
            )

        if progress_callback:
            progress_callback(
                f"Processing {len(files_to_process)} files "
                f"({len(files_unchanged)} unchanged, {len(deleted_file_paths)} deleted)",
                0,
                len(files_to_process),
            )

        return files_to_process, files_unchanged, deleted_file_paths

    def create_index_status(
        self,
        processed_files: list[FileInfo],
        files_unchanged: list[FileInfo],
        total_chunks_processed: int,
    ) -> IndexStatus:
        """Create the final index status with statistics.

        Args:
            processed_files: List of files that were processed.
            files_unchanged: List of files that were unchanged.
            total_chunks_processed: Number of chunks processed in this run.

        Returns:
            IndexStatus with complete indexing results.
        """
        all_files, total_chunks = self._status_manager.merge_files(
            processed_files, files_unchanged, total_chunks_processed
        )

        return self._status_manager.create(
            repo_path=self.repo_path,
            files=all_files,
            total_chunks=total_chunks,
        )

    def save_index_status(self, status: IndexStatus) -> None:
        """Save the final index status and log completion.

        Args:
            status: The IndexStatus to save.
        """
        self._status_manager.save(self.wiki_path, status)
        self._host.logger.info(
            "Indexing complete: %d files, %d chunks, languages: %s",
            status.total_files,
            status.total_chunks,
            list(status.languages.keys()),
        )

        # Log AST cache statistics if enabled
        if self.ast_cache is not None:
            cache_stats = self.ast_cache.get_stats()
            self._host.logger.info(
                "AST cache stats: hits=%d, misses=%d, hit_rate=%.2f%%, entries=%d, memory=%.1fKB",
                cache_stats["hits"],
                cache_stats["misses"],
                cache_stats["hit_rate"] * 100,
                cache_stats["total_entries"],
                cache_stats["estimated_memory_bytes"] / 1024,
            )

    def load_status(self) -> tuple[IndexStatus | None, bool]:
        """Load previous indexing status and check for migration needs.

        Returns:
            Tuple of (IndexStatus or None, requires_rebuild).
            requires_rebuild is True if the index should be fully rebuilt.
        """
        return self._status_manager.load_with_migration_info(self.wiki_path)

    def save_status(self, status: IndexStatus) -> None:
        """Save indexing status.

        Args:
            status: The IndexStatus to save.
        """
        self._status_manager.save(self.wiki_path, status)

    def get_status(self) -> IndexStatus | None:
        """Get the current indexing status.

        Returns:
            IndexStatus or None if not indexed.
        """
        return self._status_manager.load(self.wiki_path)
