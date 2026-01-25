"""Wiki generation status management for incremental updates."""

import asyncio
import hashlib
import json
import time
from pathlib import Path

from typing import Any

from local_deepwiki.logging import get_logger
from local_deepwiki.models import WikiGenerationStatus, WikiPage, WikiPageStatus

logger = get_logger(__name__)


class WikiStatusManager:
    """Manage wiki generation status for incremental updates."""

    WIKI_STATUS_FILE = "wiki_status.json"

    def __init__(self, wiki_path: Path):
        """Initialize the status manager.

        Args:
            wiki_path: Path to wiki output directory.
        """
        self.wiki_path = wiki_path

        # Track file hashes from index_status for incremental generation
        self._file_hashes: dict[str, str] = {}

        # Previous wiki generation status for incremental updates
        self._previous_status: WikiGenerationStatus | None = None

        # New page statuses for current generation
        self._page_statuses: dict[str, WikiPageStatus] = {}

        # Line info for source files (computed from chunks)
        self._file_line_info: dict[str, tuple[int, int]] = {}

    @property
    def file_hashes(self) -> dict[str, str]:
        """Get file hashes map."""
        return self._file_hashes

    @file_hashes.setter
    def file_hashes(self, value: dict[str, str]) -> None:
        """Set file hashes map."""
        self._file_hashes = value

    @property
    def file_line_info(self) -> dict[str, tuple[int, int]]:
        """Get file line info map."""
        return self._file_line_info

    @file_line_info.setter
    def file_line_info(self, value: dict[str, tuple[int, int]]) -> None:
        """Set file line info map."""
        self._file_line_info = value

    @property
    def page_statuses(self) -> dict[str, WikiPageStatus]:
        """Get page statuses map."""
        return self._page_statuses

    @property
    def previous_status(self) -> WikiGenerationStatus | None:
        """Get previous wiki generation status."""
        return self._previous_status

    async def load_status(self) -> WikiGenerationStatus | None:
        """Load previous wiki generation status.

        Returns:
            WikiGenerationStatus or None if not found.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        if not status_path.exists():
            return None

        def _read_status() -> WikiGenerationStatus | None:
            try:
                with open(status_path) as f:
                    data = json.load(f)
                return WikiGenerationStatus.model_validate(data)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                # json.JSONDecodeError: Corrupted or invalid JSON
                # OSError: File read issues
                # ValueError: Pydantic validation failure
                logger.warning(f"Failed to load wiki status from {status_path}: {e}")
                return None

        self._previous_status = await asyncio.to_thread(_read_status)
        return self._previous_status

    async def save_status(self, status: WikiGenerationStatus) -> None:
        """Save wiki generation status.

        Args:
            status: The WikiGenerationStatus to save.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        data = status.model_dump()

        def _write_status() -> None:
            with open(status_path, "w") as f:
                json.dump(data, f, indent=2)

        await asyncio.to_thread(_write_status)

    def compute_content_hash(self, content: str) -> str:
        """Compute hash of page content.

        Args:
            content: Page content.

        Returns:
            SHA256 hash of content (first 16 chars).
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def needs_regeneration(
        self,
        page_path: str,
        source_files: list[str],
    ) -> bool:
        """Check if a page needs regeneration based on source file changes.

        Args:
            page_path: Wiki page path.
            source_files: List of source files that contribute to this page.

        Returns:
            True if page needs regeneration, False if it can be skipped.
        """
        if self._previous_status is None:
            return True

        prev_page = self._previous_status.pages.get(page_path)
        if prev_page is None:
            return True

        # Check if any source file has changed
        for source_file in source_files:
            current_hash = self._file_hashes.get(source_file)
            prev_hash = prev_page.source_hashes.get(source_file)

            if current_hash is None or prev_hash is None:
                return True
            if current_hash != prev_hash:
                return True

        # Check if source files list changed
        if set(source_files) != set(prev_page.source_files):
            return True

        return False

    async def load_existing_page(self, page_path: str) -> WikiPage | None:
        """Load an existing wiki page from disk.

        Args:
            page_path: Relative path to the page.

        Returns:
            WikiPage if found, None otherwise.
        """
        full_path = self.wiki_path / page_path
        if not full_path.exists():
            return None

        # Capture values needed for the sync function
        prev_page = self._previous_status.pages.get(page_path) if self._previous_status else None
        title = Path(page_path).stem.replace("_", " ").title()
        generated_at = prev_page.generated_at if prev_page else time.time()

        def _read_page() -> WikiPage | None:
            try:
                content = full_path.read_text()
                return WikiPage(
                    path=page_path,
                    title=title,
                    content=content,
                    generated_at=generated_at,
                )
            except (OSError, UnicodeDecodeError) as e:
                # OSError: File read issues
                # UnicodeDecodeError: File encoding issues
                logger.warning(f"Failed to load existing page {page_path}: {e}")
                return None

        return await asyncio.to_thread(_read_page)

    def record_page_status(
        self,
        page: WikiPage,
        source_files: list[str],
    ) -> None:
        """Record status for a generated/loaded page.

        Args:
            page: The wiki page.
            source_files: Source files that contributed to this page.
        """
        source_hashes = {f: self._file_hashes.get(f, "") for f in source_files}

        # Include line info for source files that have it
        source_line_info = {
            f: {"start_line": self._file_line_info[f][0], "end_line": self._file_line_info[f][1]}
            for f in source_files
            if f in self._file_line_info
        }

        self._page_statuses[page.path] = WikiPageStatus(
            path=page.path,
            source_files=source_files,
            source_hashes=source_hashes,
            source_line_info=source_line_info,
            content_hash=self.compute_content_hash(page.content),
            generated_at=page.generated_at,
        )

    def get_changed_files(self) -> set[str]:
        """Get set of files that have changed since last generation.

        Compares current file hashes with previous generation's hashes.

        Returns:
            Set of file paths that have changed or are new.
        """
        if self._previous_status is None:
            # No previous status means all files are "new"
            return set(self._file_hashes.keys())

        changed = set()

        # Check each current file against previous hashes
        for file_path, current_hash in self._file_hashes.items():
            # Find any page that previously tracked this file
            prev_hash = None
            for page_status in self._previous_status.pages.values():
                if file_path in page_status.source_hashes:
                    prev_hash = page_status.source_hashes[file_path]
                    break

            if prev_hash is None or prev_hash != current_hash:
                changed.add(file_path)

        return changed

    def build_reverse_index(self) -> dict[str, set[str]]:
        """Build reverse index mapping source files to dependent wiki pages.

        Uses previous generation's page statuses to build the mapping.

        Returns:
            Dict mapping source file path to set of wiki page paths that depend on it.
        """
        reverse_index: dict[str, set[str]] = {}

        if self._previous_status is None:
            return reverse_index

        for page_path, page_status in self._previous_status.pages.items():
            for source_file in page_status.source_files:
                if source_file not in reverse_index:
                    reverse_index[source_file] = set()
                reverse_index[source_file].add(page_path)

        return reverse_index

    def get_affected_pages(self, changed_files: set[str] | None = None) -> set[str]:
        """Get set of wiki pages affected by file changes.

        Uses reverse index to efficiently find all pages that depend on changed files.

        Args:
            changed_files: Optional set of changed files. If None, computes automatically.

        Returns:
            Set of wiki page paths that need regeneration.
        """
        if changed_files is None:
            changed_files = self.get_changed_files()

        if not changed_files:
            return set()

        reverse_index = self.build_reverse_index()
        affected: set[str] = set()

        for file_path in changed_files:
            if file_path in reverse_index:
                affected.update(reverse_index[file_path])

        return affected

    def get_regeneration_summary(self) -> dict[str, Any]:
        """Get a summary of what will be regenerated and why.

        Returns:
            Dict with 'changed_files', 'affected_pages', 'unchanged_pages' counts.
        """
        changed_files = self.get_changed_files()
        affected_pages = self.get_affected_pages(changed_files)

        total_previous_pages = (
            len(self._previous_status.pages) if self._previous_status else 0
        )
        unchanged_pages = total_previous_pages - len(affected_pages)

        return {
            "changed_files": list(changed_files),
            "changed_file_count": len(changed_files),
            "affected_pages": list(affected_pages),
            "affected_page_count": len(affected_pages),
            "unchanged_page_count": max(0, unchanged_pages),
            "is_full_rebuild": self._previous_status is None,
        }
