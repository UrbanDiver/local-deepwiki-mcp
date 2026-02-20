"""File watcher for auto-reindexing on file changes."""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock, Timer
from typing import TYPE_CHECKING, Callable, TypeAlias

from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from local_deepwiki.cli_progress import MultiPhaseProgress

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.core.parser import EXTENSION_MAP
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

console = Console()

# Supported file extensions
WATCHED_EXTENSIONS = set(EXTENSION_MAP.keys())


class ChangeType(Enum):
    """Type of file change detected."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class FileChange:
    """Represents a single file change event."""

    path: str
    change_type: ChangeType
    timestamp: float = field(default_factory=time.time)
    dest_path: str | None = None  # For moved files


@dataclass
class ReindexResult:
    """Result of a reindex operation."""

    success: bool
    files_processed: int
    pages_generated: int
    duration_seconds: float
    error: str | None = None
    changed_files: list[str] = field(default_factory=list)


# Type alias for reindex completion callbacks
ReindexCallback: TypeAlias = Callable[[ReindexResult], None]


class DebouncedHandler(FileSystemEventHandler):
    """File system event handler with debouncing.

    This handler collects file change events and debounces them to avoid
    triggering reindexing on every keystroke. It tracks the type of change
    (create, modify, delete, move) for selective reindexing.

    Thread Safety:
        All state mutations are protected by a lock to ensure thread safety
        since watchdog calls handlers from multiple threads.
    """

    def __init__(
        self,
        repo_path: Path,
        config: Config,
        debounce_seconds: float = 2.0,
        llm_provider: str | None = None,
        on_reindex_complete: ReindexCallback | None = None,
    ):
        """Initialize the handler.

        Args:
            repo_path: Path to the repository root.
            config: Configuration instance.
            debounce_seconds: Seconds to wait after last change before triggering.
            llm_provider: Optional LLM provider override.
            on_reindex_complete: Optional callback invoked when reindexing completes.
        """
        self.repo_path = repo_path
        # Store a defensive copy to prevent external mutation
        self.config = config.model_copy(deep=True)
        self.debounce_seconds = debounce_seconds
        self.llm_provider = llm_provider
        self.on_reindex_complete = on_reindex_complete

        # Thread-safe state management
        self._lock = Lock()
        self._timer: Timer | None = None
        self._pending_files: set[str] = set()
        self._pending_changes: dict[str, FileChange] = {}
        self._is_processing = False
        self._last_event_time: float = 0.0

    def _should_watch_file(self, path: str) -> bool:
        """Check if a file should trigger reindexing.

        Args:
            path: Absolute path to the file.

        Returns:
            True if the file should be watched.
        """
        file_path = Path(path)

        # Check extension
        if file_path.suffix.lower() not in WATCHED_EXTENSIONS:
            logger.debug("Ignoring file with unsupported extension: %s", path)
            return False

        # Check exclude patterns
        try:
            rel_path = str(file_path.relative_to(self.repo_path))
        except ValueError:
            logger.debug("File outside repo path: %s", path)
            return False

        for pattern in self.config.parsing.exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                logger.debug("File matches exclude pattern '%s': %s", pattern, rel_path)
                return False

        return True

    def _add_pending_change(
        self, path: str, change_type: ChangeType, dest_path: str | None = None
    ) -> None:
        """Add a file change to the pending set (thread-safe).

        Args:
            path: Path to the changed file.
            change_type: Type of change (created, modified, deleted, moved).
            dest_path: Destination path for moved files.
        """
        with self._lock:
            self._pending_files.add(path)
            self._pending_changes[path] = FileChange(
                path=path,
                change_type=change_type,
                dest_path=dest_path,
            )
            self._last_event_time = time.time()
            logger.debug("Added pending change: %s %s", change_type.value, path)

    def _schedule_reindex(self) -> None:
        """Schedule a reindex after debounce period (thread-safe)."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                logger.debug("Cancelled previous debounce timer")

            self._timer = Timer(self.debounce_seconds, self._trigger_reindex)
            self._timer.start()
            logger.debug("Scheduled reindex in %ss", self.debounce_seconds)

    def _trigger_reindex(self) -> None:
        """Trigger the actual reindex operation (thread-safe)."""
        with self._lock:
            if self._is_processing:
                # Re-schedule if already processing
                logger.info("Reindex already in progress, rescheduling")
                self._schedule_reindex()
                return

            files = list(self._pending_files)
            changes = dict(self._pending_changes)
            self._pending_files.clear()
            self._pending_changes.clear()

        if files:
            logger.info("Triggering reindex for %s files", len(files))
            # Run in asyncio event loop
            asyncio.run(self._do_reindex(files, changes))

    async def _do_reindex(
        self,
        changed_files: list[str],
        changes: dict[str, FileChange] | None = None,
    ) -> None:
        """Perform the reindex operation.

        Args:
            changed_files: List of changed file paths.
            changes: Optional dict mapping paths to FileChange details.
        """
        self._is_processing = True
        start_time = time.time()
        result = ReindexResult(
            success=False,
            files_processed=0,
            pages_generated=0,
            duration_seconds=0.0,
            changed_files=changed_files,
        )

        logger.info("Starting reindex for %s changed files", len(changed_files))

        try:
            console.print()
            console.rule("[bold blue]Changes Detected[/bold blue]")

            # Show changes with their types
            for f in changed_files[:10]:  # Show first 10
                rel_path = Path(f).relative_to(self.repo_path)
                change_type = ""
                if changes and f in changes:
                    change_type = f"[{changes[f].change_type.value}] "
                console.print(f"  [dim]- {change_type}{rel_path}[/dim]")
            if len(changed_files) > 10:
                console.print(f"  [dim]... and {len(changed_files) - 10} more[/dim]")

            # Log change type summary
            if changes:
                type_counts: dict[str, int] = {}
                for change in changes.values():
                    type_counts[change.change_type.value] = (
                        type_counts.get(change.change_type.value, 0) + 1
                    )
                logger.info("Change types: %s", type_counts)

            console.print()
            console.print("[yellow]Starting incremental reindex...[/yellow]")

            # Create indexer
            indexer = RepositoryIndexer(
                repo_path=self.repo_path,
                config=self.config,
            )

            # Progress callback
            def progress_callback(msg: str, current: int, total: int) -> None:
                if total > 0:
                    console.print(f"  [{current}/{total}] {msg}")
                else:
                    console.print(f"  {msg}")

            # Run incremental index
            status = await indexer.index(
                full_rebuild=False,
                progress_callback=progress_callback,
            )

            index_time = time.time() - start_time
            console.print(
                f"[green]Indexed {status.total_files} files in {index_time:.1f}s[/green]"
            )
            result.files_processed = status.total_files

            # Generate wiki
            console.print("[yellow]Regenerating wiki...[/yellow]")

            wiki_start = time.time()
            wiki_structure = await generate_wiki(
                repo_path=self.repo_path,
                wiki_path=indexer.wiki_path,
                vector_store=indexer.vector_store,
                index_status=status,
                config=self.config,
                llm_provider=self.llm_provider,
                progress_callback=progress_callback,
                full_rebuild=False,
            )

            wiki_time = time.time() - wiki_start
            console.print(
                f"[green]Generated {len(wiki_structure.pages)} pages in {wiki_time:.1f}s[/green]"
            )
            result.pages_generated = len(wiki_structure.pages)

            total_time = time.time() - start_time
            console.print()
            console.print(f"[bold green]Done in {total_time:.1f}s[/bold green]")
            console.rule()
            console.print("[dim]Watching for changes... (Ctrl+C to stop)[/dim]")

            result.success = True
            result.duration_seconds = total_time

        except Exception as e:  # noqa: BLE001 - Keep watcher alive despite errors
            logger.exception("Error during reindex: %s", e)
            console.print(f"[red]Error during reindex: {e}[/red]")
            result.error = str(e)
            result.duration_seconds = time.time() - start_time

        finally:
            self._is_processing = False

            # Invoke completion callback if registered
            if self.on_reindex_complete:
                try:
                    self.on_reindex_complete(result)
                except Exception as callback_error:  # noqa: BLE001
                    logger.error("Error in reindex callback: %s", callback_error)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        src_path = str(event.src_path)
        if self._should_watch_file(src_path):
            self._add_pending_change(src_path, ChangeType.MODIFIED)
            self._schedule_reindex()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        src_path = str(event.src_path)
        if self._should_watch_file(src_path):
            self._add_pending_change(src_path, ChangeType.CREATED)
            self._schedule_reindex()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if event.is_directory:
            return

        src_path = str(event.src_path)
        if self._should_watch_file(src_path):
            self._add_pending_change(src_path, ChangeType.DELETED)
            self._schedule_reindex()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if event.is_directory:
            return

        # Check both source and destination
        src_path = str(event.src_path)
        dest_path_str = str(event.dest_path) if hasattr(event, "dest_path") else None

        if self._should_watch_file(src_path):
            self._add_pending_change(
                src_path, ChangeType.MOVED, dest_path=dest_path_str
            )
            self._schedule_reindex()

        if dest_path_str and self._should_watch_file(dest_path_str):
            self._add_pending_change(dest_path_str, ChangeType.CREATED)
            self._schedule_reindex()


class RepositoryWatcher:
    """Watches a repository for file changes and triggers reindexing.

    This class provides a high-level interface for watching a repository
    and automatically regenerating wiki documentation when files change.

    Features:
        - Debounced file change detection to avoid excessive reindexing
        - Callback mechanism for notification when reindexing completes
        - Thread-safe operation with graceful shutdown

    Example:
        >>> watcher = RepositoryWatcher(
        ...     repo_path=Path("/path/to/repo"),
        ...     debounce_seconds=2.0,
        ...     on_reindex_complete=lambda result: print(f"Done: {result.success}")
        ... )
        >>> watcher.start()
        >>> # ... do work ...
        >>> watcher.stop()
    """

    def __init__(
        self,
        repo_path: Path,
        config: Config | None = None,
        debounce_seconds: float = 2.0,
        llm_provider: str | None = None,
        on_reindex_complete: ReindexCallback | None = None,
    ):
        """Initialize the watcher.

        Args:
            repo_path: Path to the repository to watch.
            config: Optional configuration.
            debounce_seconds: Seconds to wait after changes before reindexing.
            llm_provider: Optional LLM provider override.
            on_reindex_complete: Optional callback invoked when reindexing completes.
                The callback receives a ReindexResult with details about the operation.
        """
        self.repo_path = repo_path.resolve()
        base_config = config or get_config()
        # Store a defensive copy to prevent external mutation
        self.config = base_config.model_copy(deep=True)
        self.debounce_seconds = debounce_seconds
        self.llm_provider = llm_provider
        self.on_reindex_complete = on_reindex_complete
        self._observer: BaseObserver | None = None
        self._handler: DebouncedHandler | None = None

    def start(self) -> None:
        """Start watching the repository."""
        logger.info("Starting file watcher for %s", self.repo_path)

        self._handler = DebouncedHandler(
            repo_path=self.repo_path,
            config=self.config,
            debounce_seconds=self.debounce_seconds,
            llm_provider=self.llm_provider,
            on_reindex_complete=self.on_reindex_complete,
        )

        observer = Observer()
        observer.schedule(self._handler, str(self.repo_path), recursive=True)
        observer.start()
        self._observer = observer
        logger.debug("File watcher started successfully")

    def stop(self) -> None:
        """Stop watching the repository."""
        logger.info("Stopping file watcher")
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._handler = None
            logger.debug("File watcher stopped")

    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._observer is not None and self._observer.is_alive()

    def get_pending_changes(self) -> list[FileChange]:
        """Get the list of pending file changes (for debugging/monitoring).

        Returns:
            List of FileChange objects for pending changes.
        """
        if self._handler is None:
            return []
        with self._handler._lock:
            return list(self._handler._pending_changes.values())


async def initial_index(
    repo_path: Path,
    config: Config,
    llm_provider: str | None = None,
    full_rebuild: bool = False,
    *,
    no_progress: bool = False,
) -> None:
    """Perform initial indexing before starting watch mode.

    Args:
        repo_path: Path to the repository.
        config: Configuration instance.
        llm_provider: Optional LLM provider override.
        full_rebuild: Whether to do a full rebuild.
        no_progress: If True, disable progress bars.
    """
    console.print("[yellow]Running initial index...[/yellow]")

    indexer = RepositoryIndexer(repo_path=repo_path, config=config)
    start_time = time.time()

    with MultiPhaseProgress(disable=no_progress) as progress:
        # Add phases
        progress.add_phase("indexing", "Indexing repository", total=0)
        progress.add_phase("wiki", "Generating wiki", total=0)

        # Create callback adapter for indexing phase
        index_callback = progress.get_callback("indexing")

        def indexing_progress(msg: str, current: int, total: int) -> None:
            if index_callback:
                index_callback(msg, current, total)
            else:
                if total > 0:
                    console.print(f"  [{current}/{total}] {msg}")
                else:
                    console.print(f"  {msg}")

        status = await indexer.index(
            full_rebuild=full_rebuild,
            progress_callback=indexing_progress,
        )

        progress.complete_phase("indexing")
        console.print(
            f"[green]Indexed {status.total_files} files, {status.total_chunks} chunks[/green]"
        )

        # Create callback adapter for wiki phase
        wiki_callback = progress.get_callback("wiki")

        def wiki_progress(msg: str, current: int, total: int) -> None:
            if wiki_callback:
                wiki_callback(msg, current, total)
            else:
                if total > 0:
                    console.print(f"  [{current}/{total}] {msg}")
                else:
                    console.print(f"  {msg}")

        wiki_structure = await generate_wiki(
            repo_path=repo_path,
            wiki_path=indexer.wiki_path,
            vector_store=indexer.vector_store,
            index_status=status,
            config=config,
            llm_provider=llm_provider,
            progress_callback=wiki_progress,
            full_rebuild=full_rebuild,
        )

        progress.complete_phase("wiki")

    total_time = time.time() - start_time
    console.print(f"[green]Generated {len(wiki_structure.pages)} wiki pages[/green]")
    console.print(
        f"[bold green]Initial index complete in {total_time:.1f}s[/bold green]"
    )


def main() -> None:
    """Main entry point for the watch command."""
    parser = argparse.ArgumentParser(
        description="Watch a repository for changes and auto-regenerate wiki documentation."
    )
    parser.add_argument(
        "repo_path",
        type=str,
        nargs="?",
        default=".",
        help="Path to the repository to watch (default: current directory)",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=2.0,
        help="Seconds to wait after changes before reindexing (default: 2.0)",
    )
    parser.add_argument(
        "--llm",
        type=str,
        choices=["ollama", "anthropic", "openai"],
        help="LLM provider for wiki generation",
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Perform a full rebuild on startup instead of incremental",
    )
    parser.add_argument(
        "--skip-initial",
        action="store_true",
        help="Skip initial indexing, just start watching",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars (for non-interactive use)",
    )

    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        console.print(f"[red]Error: Path does not exist: {repo_path}[/red]")
        sys.exit(1)

    if not repo_path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {repo_path}[/red]")
        sys.exit(1)

    config = get_config()

    console.print()
    console.print("[bold]DeepWiki Watch Mode[/bold]")
    console.print(f"Repository: [cyan]{repo_path}[/cyan]")
    console.print(f"Debounce: [cyan]{args.debounce}s[/cyan]")
    console.print(f"LLM Provider: [cyan]{args.llm or config.llm.provider}[/cyan]")
    console.print()

    # Run initial index unless skipped
    if not args.skip_initial:
        asyncio.run(
            initial_index(
                repo_path=repo_path,
                config=config,
                llm_provider=args.llm,
                full_rebuild=args.full_rebuild,
                no_progress=args.no_progress,
            )
        )

    # Start watching
    console.print()
    console.rule("[bold blue]Starting Watch Mode[/bold blue]")
    console.print("[dim]Watching for changes... (Ctrl+C to stop)[/dim]")
    console.print()

    watcher = RepositoryWatcher(
        repo_path=repo_path,
        config=config,
        debounce_seconds=args.debounce,
        llm_provider=args.llm,
    )

    try:
        watcher.start()
        while watcher.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Stopping watcher...[/yellow]")
        watcher.stop()
        console.print("[green]Done.[/green]")


if __name__ == "__main__":
    main()
