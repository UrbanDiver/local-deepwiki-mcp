"""Streaming export base classes and utilities for memory-efficient wiki export.

This module provides abstract base classes and utilities for streaming wiki
exports that avoid loading all pages into memory at once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


class ExportConfig(BaseModel):
    """Configuration for streaming export operations."""

    model_config = {"frozen": True}

    batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Pages per batch for PDF generation",
    )
    memory_limit_mb: int = Field(
        default=500,
        ge=100,
        le=4096,
        description="Memory threshold to trigger streaming mode (MB)",
    )
    enable_streaming: bool = Field(
        default=True,
        description="Enable streaming mode for large wikis",
    )


@dataclass
class WikiPageMetadata:
    """Lightweight metadata for a wiki page without full content."""

    path: str
    title: str
    file_size: int
    relative_path: Path


@dataclass
class WikiPage:
    """A wiki page with content loaded on demand."""

    metadata: WikiPageMetadata
    _content: str | None = field(default=None, repr=False)
    _full_path: Path | None = field(default=None, repr=False)

    @property
    def path(self) -> str:
        """Return the relative path of the page."""
        return self.metadata.path

    @property
    def title(self) -> str:
        """Return the title of the page."""
        return self.metadata.title

    @property
    def content(self) -> str:
        """Return the content of the page, loading from disk if needed."""
        if self._content is None:
            if self._full_path is None:
                raise ValueError("Cannot load content: full_path not set")
            self._content = self._full_path.read_text()
        return self._content

    def release_content(self) -> None:
        """Release the content from memory."""
        self._content = None


@dataclass
class ExportResult:
    """Result of an export operation."""

    pages_exported: int
    output_path: Path
    duration_ms: int
    peak_memory_mb: float = 0.0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Return a human-readable summary."""
        return (
            f"Exported {self.pages_exported} pages to {self.output_path} "
            f"in {self.duration_ms}ms"
        )


ProgressCallback: TypeAlias = Callable[[int, int, str], None]
"""Progress callback signature: (current, total, message) -> None"""


class WikiPageIterator:
    """Memory-efficient iterator over wiki pages.

    Yields pages one at a time, loading content only when accessed.
    Supports counting pages without loading content.
    """

    def __init__(self, wiki_path: Path, toc_order: list[str] | None = None):
        """Initialize the iterator.

        Args:
            wiki_path: Path to the .deepwiki directory.
            toc_order: Optional list of page paths in TOC order.
                       If not provided, pages are iterated in alphabetical order.
        """
        self.wiki_path = wiki_path
        self._toc_order = toc_order
        self._page_count: int | None = None
        self._total_size: int = 0

    def get_page_count(self) -> int:
        """Return total page count without loading content."""
        if self._page_count is None:
            self._scan_pages()
        return self._page_count or 0

    def get_total_size_bytes(self) -> int:
        """Return total size of all pages in bytes."""
        if self._page_count is None:
            self._scan_pages()
        return self._total_size

    def should_use_streaming(self, memory_limit_mb: int = 500) -> bool:
        """Determine if streaming mode should be used based on wiki size.

        Args:
            memory_limit_mb: Memory threshold in megabytes.

        Returns:
            True if wiki size exceeds threshold and streaming is recommended.
        """
        total_mb = self.get_total_size_bytes() / (1024 * 1024)
        # Use streaming if wiki is larger than threshold
        # or if there are many pages (>100)
        return total_mb > memory_limit_mb or self.get_page_count() > 100

    def _scan_pages(self) -> None:
        """Scan wiki directory to count pages and calculate total size."""
        md_files = list(self.wiki_path.rglob("*.md"))
        self._page_count = len(md_files)
        self._total_size = sum(f.stat().st_size for f in md_files)
        logger.debug(
            "Scanned wiki: %d pages, %.2f MB",
            self._page_count,
            self._total_size / 1024 / 1024,
        )

    def _get_ordered_paths(self) -> list[Path]:
        """Get page paths in the correct order (TOC order or alphabetical)."""
        all_files = {
            str(f.relative_to(self.wiki_path)): f for f in self.wiki_path.rglob("*.md")
        }

        if self._toc_order:
            # Order by TOC, then add any remaining files
            ordered = []
            for path in self._toc_order:
                if path in all_files:
                    ordered.append(all_files.pop(path))
            # Add remaining files in sorted order
            ordered.extend(sorted(all_files.values(), key=lambda p: str(p)))
            return ordered
        else:
            return sorted(all_files.values(), key=lambda p: str(p))

    async def __aiter__(self) -> AsyncIterator[WikiPage]:
        """Yield pages one at a time.

        Content is loaded lazily when the `content` property is accessed.
        """
        for full_path in self._get_ordered_paths():
            rel_path = full_path.relative_to(self.wiki_path)
            title = self._extract_title(full_path)
            file_size = full_path.stat().st_size

            metadata = WikiPageMetadata(
                path=str(rel_path),
                title=title,
                file_size=file_size,
                relative_path=rel_path,
            )

            page = WikiPage(
                metadata=metadata,
                _content=None,
                _full_path=full_path,
            )

            yield page

    @staticmethod
    def _extract_title(md_file: Path) -> str:
        """Extract title from markdown file without loading full content.

        Reads only the first few lines to find the title.
        """
        try:
            with md_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# "):
                        return line[2:].strip()
                    if line.startswith("**") and line.endswith("**"):
                        return line[2:-2].strip()
                    # Only check first 10 lines
                    if f.tell() > 1024:
                        break
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Could not extract title from %s: %s", md_file, e)

        return md_file.stem.replace("_", " ").replace("-", " ").title()


class StreamingExporter(ABC):
    """Abstract base class for streaming wiki exporters.

    Subclasses implement memory-efficient export by processing pages
    one at a time or in small batches.
    """

    def __init__(
        self,
        wiki_path: Path,
        output_path: Path,
        config: ExportConfig | None = None,
    ):
        """Initialize the streaming exporter.

        Args:
            wiki_path: Path to the .deepwiki directory.
            output_path: Output path for exported content.
            config: Export configuration. Uses defaults if not provided.
        """
        self.wiki_path = Path(wiki_path)
        self.output_path = Path(output_path)
        self.config = config or ExportConfig()
        self._toc_entries: list[dict[str, Any]] = []

    def load_toc(self) -> list[str]:
        """Load and parse table of contents, returning ordered page paths.

        Returns:
            List of page paths in TOC order.
        """
        import json

        toc_path = self.wiki_path / "toc.json"
        if not toc_path.exists():
            return []

        try:
            toc_data = json.loads(toc_path.read_text())
            self._toc_entries = toc_data.get("entries", [])
            paths: list[str] = []
            self._extract_paths_from_toc(self._toc_entries, paths)
            logger.debug("Loaded %s paths from TOC", len(paths))
            return paths
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load TOC: %s", e)
            return []

    def _extract_paths_from_toc(
        self, entries: list[dict[str, Any]], paths: list[str]
    ) -> None:
        """Recursively extract paths from TOC entries."""
        for entry in entries:
            path = entry.get("path", "")
            if path:  # Skip empty paths
                paths.append(path)
            if "children" in entry:
                self._extract_paths_from_toc(entry["children"], paths)

    def get_page_iterator(self) -> WikiPageIterator:
        """Get an iterator over wiki pages in TOC order."""
        toc_order = self.load_toc()
        return WikiPageIterator(self.wiki_path, toc_order)

    @abstractmethod
    async def export(
        self, progress_callback: ProgressCallback | None = None
    ) -> ExportResult:
        """Export wiki with streaming.

        Args:
            progress_callback: Optional callback for progress updates.

        Returns:
            ExportResult with export statistics.
        """
        ...

    async def iter_pages(self) -> AsyncIterator[WikiPage]:
        """Iterate over wiki pages without loading all into memory."""
        iterator = self.get_page_iterator()
        async for page in iterator:
            yield page
