"""Cache management CLI for local-deepwiki.

Provides commands to inspect and manage embedding and LLM caches:
    deepwiki cache stats [--repo PATH]
    deepwiki cache clear [--llm] [--embedding] [--repo PATH]
    deepwiki cache cleanup [--repo PATH]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Default paths
EMBEDDING_CACHE_DIR = Path.home() / ".cache" / "local-deepwiki"
EMBEDDING_CACHE_DB = EMBEDDING_CACHE_DIR / "embedding_cache.db"
DEFAULT_LLM_CACHE_SUBDIR = ".deepwiki/llm_cache.lance"


def _resolve_llm_cache_path(repo: str) -> Path:
    """Resolve the LLM cache path for a given repo.

    Args:
        repo: Repository path (default: current directory).

    Returns:
        Path to the LLM cache LanceDB directory.
    """
    return Path(repo).resolve() / DEFAULT_LLM_CACHE_SUBDIR


def _get_embedding_stats() -> dict[str, int | str]:
    """Get embedding cache statistics by querying SQLite directly.

    Returns:
        Dictionary with entry_count, total_size_bytes, oldest_entry, newest_entry.
    """
    if not EMBEDDING_CACHE_DB.exists():
        return {
            "entry_count": 0,
            "total_size_bytes": 0,
            "oldest_entry": "N/A",
            "newest_entry": "N/A",
        }

    try:
        conn = sqlite3.connect(str(EMBEDDING_CACHE_DB))
        try:
            cursor = conn.cursor()

            # Count entries
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            count = cursor.fetchone()[0]

            if count == 0:
                return {
                    "entry_count": 0,
                    "total_size_bytes": int(EMBEDDING_CACHE_DB.stat().st_size),
                    "oldest_entry": "N/A",
                    "newest_entry": "N/A",
                }

            # Get time range
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM embeddings")
            row = cursor.fetchone()
            oldest = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(row[0]))
                if row[0]
                else "N/A"
            )
            newest = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(row[1]))
                if row[1]
                else "N/A"
            )

            file_size = int(EMBEDDING_CACHE_DB.stat().st_size)

            return {
                "entry_count": count,
                "total_size_bytes": file_size,
                "oldest_entry": oldest,
                "newest_entry": newest,
            }
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return {
            "entry_count": 0,
            "total_size_bytes": 0,
            "oldest_entry": "N/A",
            "newest_entry": "N/A",
        }


def _get_llm_stats(repo: str) -> dict[str, int | str]:
    """Get LLM cache statistics by querying LanceDB directly.

    Args:
        repo: Repository path.

    Returns:
        Dictionary with entry_count, total_size_bytes.
    """
    cache_path = _resolve_llm_cache_path(repo)

    if not cache_path.exists():
        return {"entry_count": 0, "total_size_bytes": 0}

    try:
        import lancedb

        db = lancedb.connect(str(cache_path))
        table_names = db.table_names()

        if "llm_cache" not in table_names:
            return {"entry_count": 0, "total_size_bytes": _dir_size(cache_path)}

        table = db.open_table("llm_cache")
        count = table.count_rows()

        return {
            "entry_count": count,
            "total_size_bytes": _dir_size(cache_path),
        }
    except Exception:
        return {"entry_count": 0, "total_size_bytes": _dir_size(cache_path)}


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory in bytes.

    Args:
        path: Directory path.

    Returns:
        Total size in bytes.
    """
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g., "1.5 MB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def cmd_stats(args: argparse.Namespace) -> int:
    """Show cache statistics."""
    console = Console()
    repo = getattr(args, "repo", ".")

    table = Table(title="Cache Statistics", show_header=True, header_style="bold cyan")
    table.add_column("Cache", style="green", width=15)
    table.add_column("Entries", width=10, justify="right")
    table.add_column("Size", width=12, justify="right")
    table.add_column("Details", width=30)

    # Embedding cache stats
    embed_stats = _get_embedding_stats()
    embed_details = (
        f"Oldest: {embed_stats['oldest_entry']}\nNewest: {embed_stats['newest_entry']}"
    )
    table.add_row(
        "Embedding",
        str(embed_stats["entry_count"]),
        _format_size(int(embed_stats["total_size_bytes"])),
        embed_details,
    )

    # LLM cache stats
    llm_stats = _get_llm_stats(repo)
    table.add_row(
        "LLM",
        str(llm_stats["entry_count"]),
        _format_size(int(llm_stats["total_size_bytes"])),
        f"Repo: {Path(repo).resolve()}",
    )

    console.print(table)
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    """Clear cache entries."""
    console = Console()
    repo = getattr(args, "repo", ".")
    clear_llm = getattr(args, "llm", False)
    clear_embedding = getattr(args, "embedding", False)

    # If neither flag specified, clear both
    if not clear_llm and not clear_embedding:
        clear_llm = True
        clear_embedding = True

    cleared = []

    if clear_embedding:
        if EMBEDDING_CACHE_DB.exists():
            try:
                conn = sqlite3.connect(str(EMBEDDING_CACHE_DB))
                try:
                    conn.execute("DELETE FROM embeddings")
                    conn.commit()
                finally:
                    conn.close()
                cleared.append("embedding")
            except sqlite3.Error as e:
                console.print(f"[red]Failed to clear embedding cache: {e}[/red]")
        else:
            console.print("[dim]Embedding cache not found (nothing to clear)[/dim]")

    if clear_llm:
        cache_path = _resolve_llm_cache_path(repo)
        if cache_path.exists():
            try:
                import shutil

                shutil.rmtree(cache_path)
                cleared.append("LLM")
            except OSError as e:
                console.print(f"[red]Failed to clear LLM cache: {e}[/red]")
        else:
            console.print("[dim]LLM cache not found (nothing to clear)[/dim]")

    if cleared:
        console.print(f"[green]Cleared: {', '.join(cleared)} cache(s)[/green]")

    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    """Remove expired cache entries only."""
    console = Console()
    removed = 0

    # Clean up expired embedding entries (default TTL: 7 days = 604800 seconds)
    if EMBEDDING_CACHE_DB.exists():
        try:
            cutoff = time.time() - 604800  # 7 days
            conn = sqlite3.connect(str(EMBEDDING_CACHE_DB))
            try:
                cursor = conn.execute(
                    "DELETE FROM embeddings WHERE created_at < ?", (cutoff,)
                )
                removed += cursor.rowcount
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as e:
            console.print(
                f"[yellow]Warning: Could not clean embedding cache: {e}[/yellow]"
            )

    if removed > 0:
        console.print(f"[green]Removed {removed} expired embedding entries[/green]")
    else:
        console.print("[dim]No expired entries found[/dim]")

    return 0


def main() -> int:
    """Main entry point for the cache CLI."""
    parser = argparse.ArgumentParser(
        prog="deepwiki cache",
        description="Manage local-deepwiki caches (embedding cache + LLM response cache)",
        epilog=(
            "examples:\n"
            "  deepwiki cache stats               Show hit/miss rates and entry counts\n"
            "  deepwiki cache stats --repo /proj   Stats for a specific repo's LLM cache\n"
            "  deepwiki cache clear                Clear all caches\n"
            "  deepwiki cache clear --llm          Clear only the LLM response cache\n"
            "  deepwiki cache clear --embedding    Clear only the embedding cache\n"
            "  deepwiki cache cleanup              Remove expired entries (keep valid ones)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Cache commands")

    # stats
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show cache statistics",
        description="Display hit/miss rates, entry counts, and sizes for both caches.",
    )
    stats_parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Repository path for LLM cache (default: .)",
    )
    stats_parser.set_defaults(func=cmd_stats)

    # clear
    clear_parser = subparsers.add_parser(
        "clear",
        help="Clear cache entries",
        description="Delete all entries from one or both caches. Use --llm or --embedding to target a specific cache.",
    )
    clear_parser.add_argument("--llm", action="store_true", help="Clear only LLM cache")
    clear_parser.add_argument(
        "--embedding", action="store_true", help="Clear only embedding cache"
    )
    clear_parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Repository path for LLM cache (default: .)",
    )
    clear_parser.set_defaults(func=cmd_clear)

    # cleanup
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Remove expired entries only",
        description="Delete entries past their TTL while keeping valid cached data intact.",
    )
    cleanup_parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Repository path for LLM cache (default: .)",
    )
    cleanup_parser.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
