"""One-shot incremental update command for local-deepwiki.

Indexes the repository and regenerates wiki documentation:

    deepwiki update [REPO_PATH] [--full-rebuild] [--dry-run] [--no-progress] [--wiki-path PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from rich.console import Console

from local_deepwiki.cli.status_cli import _scan_current_files


def _run_dry_run(
    repo_path: Path,
    wiki_path: Path,
    console: Console,
) -> int:
    """Show what would change without doing any actual work.

    Args:
        repo_path: Path to the repository.
        wiki_path: Path to the wiki directory.
        console: Rich console for output.

    Returns:
        Exit code (0 = success).
    """
    from local_deepwiki.core.index_manager import IndexStatusManager

    manager = IndexStatusManager()
    status = manager.load(wiki_path)

    if status is None:
        console.print(
            "[yellow]No existing index.[/yellow] First run will index all files."
        )
        # Still scan to show file count
        current_files = _scan_current_files(repo_path)
        console.print(f"  Source files found: [bold]{len(current_files)}[/bold]")
        return 0

    console.print(
        f"[bold]Dry run[/bold] — comparing against index from {time.strftime('%Y-%m-%d %H:%M', time.localtime(status.indexed_at))}"
    )

    current_files = _scan_current_files(repo_path)
    new_files, modified_files, deleted_files = manager.get_files_needing_reindex(
        status, current_files
    )

    total_changed = len(new_files) + len(modified_files) + len(deleted_files)

    if total_changed == 0:
        console.print("[green]Everything is up to date.[/green] No changes detected.")
        return 0

    console.print(
        f"\n  [green]+{len(new_files)} new[/green]  [yellow]~{len(modified_files)} modified[/yellow]  [red]-{len(deleted_files)} deleted[/red]"
    )

    if new_files:
        console.print("\n  [bold]New files:[/bold]")
        for f in sorted(new_files)[:20]:
            console.print(f"    [green]+[/green] {f}")
        if len(new_files) > 20:
            console.print(f"    ... and {len(new_files) - 20} more")

    if modified_files:
        console.print("\n  [bold]Modified files:[/bold]")
        for f in sorted(modified_files)[:20]:
            console.print(f"    [yellow]~[/yellow] {f}")
        if len(modified_files) > 20:
            console.print(f"    ... and {len(modified_files) - 20} more")

    if deleted_files:
        console.print("\n  [bold]Deleted files:[/bold]")
        for f in sorted(deleted_files)[:20]:
            console.print(f"    [red]-[/red] {f}")
        if len(deleted_files) > 20:
            console.print(f"    ... and {len(deleted_files) - 20} more")

    console.print(
        f"\nRun [bold]deepwiki update {repo_path}[/bold] to apply these changes."
    )
    return 0


# ---------------------------------------------------------------------------
# _run_update_async helpers
# ---------------------------------------------------------------------------


async def _setup_indexer(
    repo_path: Path,
    wiki_path: Path,
    *,
    full_rebuild: bool,
    no_progress: bool,
    console: Console,
    progress: object,
) -> tuple[object, object]:
    """Initialise the indexer and run the indexing phase.

    Returns a tuple of ``(index_status, indexer)`` after the indexing phase
    completes.  The indexer's vector store is stabilised before returning.
    """
    from local_deepwiki.cli_progress import MultiPhaseProgress  # noqa: F401 — type hint only
    from local_deepwiki.config import Config
    from local_deepwiki.core.indexer import RepositoryIndexer

    config = Config.load()
    indexer = RepositoryIndexer(repo_path=repo_path, config=config)

    # Override wiki_path if user specified one
    if wiki_path != repo_path / ".deepwiki":
        indexer.wiki_path = wiki_path

    progress.add_phase("indexing", "Indexing repository", total=0)
    index_callback = progress.get_callback("indexing")

    def indexing_progress(msg: str, current: int, total: int) -> None:
        if index_callback:
            index_callback(msg, current, total)
        elif not no_progress:
            if total > 0:
                console.print(f"  [{current}/{total}] {msg}")
            else:
                console.print(f"  {msg}")

    index_status = await indexer.index(
        full_rebuild=full_rebuild,
        progress_callback=indexing_progress,
    )

    progress.complete_phase("indexing")
    console.print(
        f"[green]Indexed {index_status.total_files} files, "
        f"{index_status.total_chunks} chunks[/green]"
    )

    # LanceDB 0.26: compact all dataset versions into a single stable
    # snapshot so concurrent wiki-generation reads don't collide with
    # deferred fragment compaction.
    indexer.vector_store.stabilize()

    return index_status, indexer


async def _run_indexing_with_progress(
    repo_path: Path,
    wiki_path: Path,
    indexer: object,
    index_status: object,
    *,
    full_rebuild: bool,
    no_progress: bool,
    console: Console,
    progress: object,
) -> object:
    """Run the wiki generation phase with progress tracking.

    Returns the wiki structure produced by ``generate_wiki``.
    """
    from local_deepwiki.config import Config
    from local_deepwiki.generators.wiki import generate_wiki

    config = Config.load()

    progress.add_phase("wiki", "Generating wiki", total=0)
    wiki_callback = progress.get_callback("wiki")

    def wiki_progress(msg: str, current: int, total: int) -> None:
        if wiki_callback:
            wiki_callback(msg, current, total)
        elif not no_progress:
            if total > 0:
                console.print(f"  [{current}/{total}] {msg}")
            else:
                console.print(f"  {msg}")

    wiki_structure = await generate_wiki(
        repo_path=repo_path,
        wiki_path=indexer.wiki_path,
        vector_store=indexer.vector_store,
        index_status=index_status,
        config=config,
        progress_callback=wiki_progress,
        full_rebuild=full_rebuild,
    )

    progress.complete_phase("wiki")
    return wiki_structure


async def _run_update_async(
    repo_path: Path,
    wiki_path: Path,
    *,
    full_rebuild: bool = False,
    no_progress: bool = False,
    console: Console,
) -> int:
    """Run the actual indexing and wiki generation.

    Args:
        repo_path: Path to the repository.
        wiki_path: Wiki output directory override (or None for default).
        full_rebuild: Force complete re-index.
        no_progress: Disable Rich progress bars.
        console: Rich console for output.

    Returns:
        Exit code (0 = success).
    """
    from local_deepwiki.cli_progress import MultiPhaseProgress

    start_time = time.time()

    with MultiPhaseProgress(disable=no_progress) as progress:
        # Phase 1: Indexing
        index_status, indexer = await _setup_indexer(
            repo_path,
            wiki_path,
            full_rebuild=full_rebuild,
            no_progress=no_progress,
            console=console,
            progress=progress,
        )

        # Phase 2: Wiki generation
        wiki_structure = await _run_indexing_with_progress(
            repo_path,
            wiki_path,
            indexer,
            index_status,
            full_rebuild=full_rebuild,
            no_progress=no_progress,
            console=console,
            progress=progress,
        )

    elapsed = time.time() - start_time
    console.print(f"[green]Generated {len(wiki_structure.pages)} wiki pages[/green]")
    console.print(f"[bold green]Update complete in {elapsed:.1f}s[/bold green]")
    return 0


def run_update(
    repo_path: Path,
    *,
    full_rebuild: bool = False,
    dry_run: bool = False,
    no_progress: bool = False,
    wiki_path: Path | None = None,
    console: Console | None = None,
) -> int:
    """Run the update command and return exit code."""
    console = console or Console()
    repo_path = repo_path.resolve()
    effective_wiki_path = wiki_path or (repo_path / ".deepwiki")

    if not repo_path.is_dir():
        console.print(f"[red]Not a directory: {repo_path}[/red]")
        return 1

    if dry_run:
        return _run_dry_run(repo_path, effective_wiki_path, console)

    try:
        return asyncio.run(
            _run_update_async(
                repo_path,
                effective_wiki_path,
                full_rebuild=full_rebuild,
                no_progress=no_progress,
                console=console,
            )
        )
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Update interrupted.[/yellow] Partial progress may have been saved."
        )
        return 130


def main() -> int:
    """Main entry point for ``deepwiki update``."""
    parser = argparse.ArgumentParser(
        prog="deepwiki update",
        description="Index repository and regenerate wiki documentation",
        epilog=(
            "examples:\n"
            "  deepwiki update                     Incremental update for current directory\n"
            "  deepwiki update /path/to/repo        Update a specific repository\n"
            "  deepwiki update --full-rebuild        Force complete re-index\n"
            "  deepwiki update --dry-run             Show what would change\n"
            "  deepwiki update --no-progress         Disable progress bars (for CI)\n"
            "  deepwiki update --wiki-path ./docs    Output wiki to custom directory\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository path to index (default: current directory)",
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Force complete re-index (ignore incremental state)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without indexing",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable Rich progress bars (for CI environments)",
    )
    parser.add_argument(
        "--wiki-path",
        type=str,
        default=None,
        help="Wiki output directory (default: REPO_PATH/.deepwiki)",
    )

    args = parser.parse_args()

    return run_update(
        Path(args.repo_path),
        full_rebuild=args.full_rebuild,
        dry_run=args.dry_run,
        no_progress=args.no_progress,
        wiki_path=Path(args.wiki_path) if args.wiki_path else None,
    )


if __name__ == "__main__":
    sys.exit(main())
