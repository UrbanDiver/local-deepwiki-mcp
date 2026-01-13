"""File watcher for auto-reindexing on file changes."""

import argparse
import asyncio
import fnmatch
import sys
import time
from pathlib import Path
from threading import Timer

from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.core.parser import EXTENSION_MAP
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

console = Console()

# Supported file extensions
WATCHED_EXTENSIONS = set(EXTENSION_MAP.keys())


class DebouncedHandler(FileSystemEventHandler):
    """File system event handler with debouncing."""

    def __init__(
        self,
        repo_path: Path,
        config: Config,
        debounce_seconds: float = 2.0,
        llm_provider: str | None = None,
    ):
        """Initialize the handler.

        Args:
            repo_path: Path to the repository root.
            config: Configuration instance.
            debounce_seconds: Seconds to wait after last change before triggering.
            llm_provider: Optional LLM provider override.
        """
        self.repo_path = repo_path
        self.config = config
        self.debounce_seconds = debounce_seconds
        self.llm_provider = llm_provider
        self._timer: Timer | None = None
        self._pending_files: set[str] = set()
        self._is_processing = False

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
            logger.debug(f"Ignoring file with unsupported extension: {path}")
            return False

        # Check exclude patterns
        try:
            rel_path = str(file_path.relative_to(self.repo_path))
        except ValueError:
            logger.debug(f"File outside repo path: {path}")
            return False

        for pattern in self.config.parsing.exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                logger.debug(f"File matches exclude pattern '{pattern}': {rel_path}")
                return False

        return True

    def _schedule_reindex(self) -> None:
        """Schedule a reindex after debounce period."""
        if self._timer:
            self._timer.cancel()

        self._timer = Timer(self.debounce_seconds, self._trigger_reindex)
        self._timer.start()

    def _trigger_reindex(self) -> None:
        """Trigger the actual reindex operation."""
        if self._is_processing:
            # Re-schedule if already processing
            self._schedule_reindex()
            return

        files = list(self._pending_files)
        self._pending_files.clear()

        if files:
            # Run in asyncio event loop
            asyncio.run(self._do_reindex(files))

    async def _do_reindex(self, changed_files: list[str]) -> None:
        """Perform the reindex operation.

        Args:
            changed_files: List of changed file paths.
        """
        self._is_processing = True
        logger.info(f"Starting reindex for {len(changed_files)} changed files")

        try:
            console.print()
            console.rule("[bold blue]Changes Detected[/bold blue]")
            for f in changed_files[:10]:  # Show first 10
                rel_path = Path(f).relative_to(self.repo_path)
                console.print(f"  [dim]- {rel_path}[/dim]")
            if len(changed_files) > 10:
                console.print(f"  [dim]... and {len(changed_files) - 10} more[/dim]")

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
            start_time = time.time()
            status = await indexer.index(
                full_rebuild=False,
                progress_callback=progress_callback,
            )

            index_time = time.time() - start_time
            console.print(f"[green]Indexed {status.total_files} files in {index_time:.1f}s[/green]")

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

            total_time = time.time() - start_time
            console.print()
            console.print(f"[bold green]Done in {total_time:.1f}s[/bold green]")
            console.rule()
            console.print("[dim]Watching for changes... (Ctrl+C to stop)[/dim]")

        except Exception as e:
            logger.exception(f"Error during reindex: {e}")
            console.print(f"[red]Error during reindex: {e}[/red]")

        finally:
            self._is_processing = False

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        if self._should_watch_file(event.src_path):
            self._pending_files.add(event.src_path)
            self._schedule_reindex()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        if self._should_watch_file(event.src_path):
            self._pending_files.add(event.src_path)
            self._schedule_reindex()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if event.is_directory:
            return

        if self._should_watch_file(event.src_path):
            self._pending_files.add(event.src_path)
            self._schedule_reindex()

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if event.is_directory:
            return

        # Check both source and destination
        if hasattr(event, "src_path") and self._should_watch_file(event.src_path):
            self._pending_files.add(event.src_path)
            self._schedule_reindex()

        if hasattr(event, "dest_path") and self._should_watch_file(event.dest_path):
            self._pending_files.add(event.dest_path)
            self._schedule_reindex()


class RepositoryWatcher:
    """Watches a repository for file changes and triggers reindexing."""

    def __init__(
        self,
        repo_path: Path,
        config: Config | None = None,
        debounce_seconds: float = 2.0,
        llm_provider: str | None = None,
    ):
        """Initialize the watcher.

        Args:
            repo_path: Path to the repository to watch.
            config: Optional configuration.
            debounce_seconds: Seconds to wait after changes before reindexing.
            llm_provider: Optional LLM provider override.
        """
        self.repo_path = repo_path.resolve()
        self.config = config or get_config()
        self.debounce_seconds = debounce_seconds
        self.llm_provider = llm_provider
        self._observer: Observer | None = None

    def start(self) -> None:
        """Start watching the repository."""
        logger.info(f"Starting file watcher for {self.repo_path}")

        handler = DebouncedHandler(
            repo_path=self.repo_path,
            config=self.config,
            debounce_seconds=self.debounce_seconds,
            llm_provider=self.llm_provider,
        )

        observer = Observer()
        observer.schedule(handler, str(self.repo_path), recursive=True)
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
            logger.debug("File watcher stopped")

    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._observer is not None and self._observer.is_alive()


async def initial_index(
    repo_path: Path,
    config: Config,
    llm_provider: str | None = None,
    full_rebuild: bool = False,
) -> None:
    """Perform initial indexing before starting watch mode.

    Args:
        repo_path: Path to the repository.
        config: Configuration instance.
        llm_provider: Optional LLM provider override.
        full_rebuild: Whether to do a full rebuild.
    """
    console.print("[yellow]Running initial index...[/yellow]")

    indexer = RepositoryIndexer(repo_path=repo_path, config=config)

    def progress_callback(msg: str, current: int, total: int) -> None:
        if total > 0:
            console.print(f"  [{current}/{total}] {msg}")
        else:
            console.print(f"  {msg}")

    start_time = time.time()
    status = await indexer.index(
        full_rebuild=full_rebuild,
        progress_callback=progress_callback,
    )

    console.print(
        f"[green]Indexed {status.total_files} files, {status.total_chunks} chunks[/green]"
    )

    # Generate wiki
    console.print("[yellow]Generating wiki...[/yellow]")

    wiki_structure = await generate_wiki(
        repo_path=repo_path,
        wiki_path=indexer.wiki_path,
        vector_store=indexer.vector_store,
        index_status=status,
        config=config,
        llm_provider=llm_provider,
        progress_callback=progress_callback,
        full_rebuild=full_rebuild,
    )

    total_time = time.time() - start_time
    console.print(f"[green]Generated {len(wiki_structure.pages)} wiki pages[/green]")
    console.print(f"[bold green]Initial index complete in {total_time:.1f}s[/bold green]")


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
