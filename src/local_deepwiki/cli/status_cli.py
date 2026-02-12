"""Index health dashboard for local-deepwiki.

Reads the index status and wiki directory to display repository
indexing health, freshness, and wiki coverage:

    deepwiki status [WIKI_PATH] [--json] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _format_timestamp(ts: float) -> str:
    """Format a Unix timestamp to a human-readable string."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _count_wiki_pages(wiki_path: Path) -> int:
    """Count .md files in the wiki directory."""
    if not wiki_path.exists():
        return 0
    return sum(1 for f in wiki_path.rglob("*.md") if f.is_file())


def _scan_current_files(repo_path: Path) -> dict[str, str]:
    """Scan a repository for source files and compute their hashes.

    Uses the same exclusion logic as the indexer's ``_find_source_files``
    so that the freshness check only considers files the indexer would
    actually process.  This means:

    * Hidden directories (starting with ``"."``) are skipped.
    * Directories matching ``exclude_patterns`` ending with ``/**`` are skipped.
    * Individual files matching other ``exclude_patterns`` are skipped.
    * Only files whose extension is in the parser's ``EXTENSION_MAP`` and
      whose language is in the configured ``parsing.languages`` are included.

    Returns:
        Dict mapping relative file paths to their SHA-256 hashes.
    """
    import fnmatch
    import os
    import re

    from local_deepwiki.config import Config
    from local_deepwiki.core.parser import EXTENSION_MAP, _compute_file_hash

    config = Config.load()

    # Build skip_dirs and compiled file patterns from config, mirroring
    # Indexer._compile_exclude_patterns().
    skip_dirs: set[str] = set()
    compiled_patterns: list[re.Pattern[str]] = []
    for pattern in config.parsing.exclude_patterns:
        if pattern.endswith("/**"):
            skip_dirs.add(pattern[:-3])
        else:
            compiled_patterns.append(re.compile(fnmatch.translate(pattern)))

    # Also always skip .deepwiki itself
    skip_dirs.add(".deepwiki")

    configured_languages = set(config.parsing.languages)
    max_size = config.parsing.max_file_size

    # Map extensions to their language names so we can filter by config
    ext_to_lang: dict[str, str] = {}
    for ext, lang in EXTENSION_MAP.items():
        # EXTENSION_MAP values are Language enum members; use .value for the
        # string name that appears in config.parsing.languages.
        ext_to_lang[ext] = lang.value if hasattr(lang, "value") else str(lang)

    current_files: dict[str, str] = {}

    for root, dirs, filenames in os.walk(repo_path):
        root_path = Path(root)
        rel_root = root_path.relative_to(repo_path)

        # Early directory filtering — mirrors Indexer._find_source_files()
        dirs[:] = [
            d
            for d in dirs
            if d not in skip_dirs
            and str(rel_root / d) not in skip_dirs
            and not d.startswith(".")  # Skip hidden directories
        ]

        for filename in filenames:
            file_path = root_path / filename
            rel_path = str(file_path.relative_to(repo_path))

            # Check against compiled file patterns
            if any(p.match(rel_path) for p in compiled_patterns):
                continue

            # Check file size
            try:
                if file_path.stat().st_size > max_size:
                    continue
            except OSError:
                continue

            # Check if extension is recognised
            ext = file_path.suffix.lower()
            lang = ext_to_lang.get(ext)
            if lang is None:
                continue

            # Check if language is in configured list
            if lang not in configured_languages:
                continue

            try:
                current_files[rel_path] = _compute_file_hash(file_path)
            except OSError:
                pass

    return current_files


def collect_status(
    wiki_path: Path,
    *,
    verbose: bool = False,
) -> dict:
    """Collect all status information and return as a dict.

    Args:
        wiki_path: Path to the wiki directory.
        verbose: If True, include per-file change details.

    Returns:
        Dictionary with all status information.
    """
    from local_deepwiki.core.index_manager import IndexStatusManager

    manager = IndexStatusManager()
    status = manager.load(wiki_path)

    if status is None:
        return {"indexed": False}

    repo_path = Path(status.repo_path)
    page_count = _count_wiki_pages(wiki_path)
    disk_usage = _dir_size(wiki_path)

    result: dict = {
        "indexed": True,
        "repository": {
            "path": status.repo_path,
            "indexed_at": status.indexed_at,
            "indexed_at_human": _format_timestamp(status.indexed_at),
            "schema_version": status.schema_version,
        },
        "index": {
            "total_files": status.total_files,
            "total_chunks": status.total_chunks,
            "languages": status.languages,
        },
        "wiki": {
            "page_count": page_count,
            "disk_usage_bytes": disk_usage,
            "disk_usage_human": _format_size(disk_usage),
        },
    }

    # Freshness check
    if repo_path.is_dir():
        current_files = _scan_current_files(repo_path)
        new_files, modified_files, deleted_files = manager.get_files_needing_reindex(
            status, current_files
        )
        total_changed = len(new_files) + len(modified_files) + len(deleted_files)

        if total_changed == 0:
            freshness_label = "Fresh"
        else:
            freshness_label = f"Stale ({total_changed} files changed)"

        freshness: dict = {
            "status": freshness_label,
            "new_count": len(new_files),
            "modified_count": len(modified_files),
            "deleted_count": len(deleted_files),
        }

        if verbose:
            freshness["new_files"] = sorted(new_files)
            freshness["modified_files"] = sorted(modified_files)
            freshness["deleted_files"] = sorted(deleted_files)

        result["freshness"] = freshness
    else:
        result["freshness"] = {
            "status": "Repository not found",
            "new_count": 0,
            "modified_count": 0,
            "deleted_count": 0,
        }

    if page_count == 0 and status.total_files > 0:
        result["note"] = "Indexed but wiki not generated"

    return result


def display_status(data: dict, console: Console) -> None:
    """Render status data as Rich panels and tables."""
    if not data.get("indexed"):
        console.print(
            "[yellow]Not indexed yet.[/yellow] Run: [bold]deepwiki update[/bold]"
        )
        return

    # Repository section
    repo = data["repository"]
    repo_lines = [
        f"[bold]Path:[/bold]           {repo['path']}",
        f"[bold]Last indexed:[/bold]   {repo['indexed_at_human']}",
        f"[bold]Schema version:[/bold] {repo['schema_version']}",
    ]
    console.print(Panel("\n".join(repo_lines), title="Repository", border_style="blue"))

    # Index section
    idx = data["index"]
    lang_table = Table(show_header=True, header_style="bold cyan", padding=(0, 1))
    lang_table.add_column("Language", style="green")
    lang_table.add_column("Files", justify="right")
    for lang, count in sorted(idx["languages"].items(), key=lambda x: -x[1]):
        lang_table.add_row(lang, str(count))

    console.print(
        Panel(
            f"[bold]Files:[/bold]  {idx['total_files']}   [bold]Chunks:[/bold] {idx['total_chunks']}",
            title="Index",
            border_style="blue",
        )
    )
    if idx["languages"]:
        console.print(lang_table)

    # Wiki section
    wiki = data["wiki"]
    console.print(
        Panel(
            f"[bold]Pages:[/bold] {wiki['page_count']}   [bold]Disk:[/bold] {wiki['disk_usage_human']}",
            title="Wiki",
            border_style="blue",
        )
    )

    # Freshness section
    freshness = data.get("freshness", {})
    status_label = freshness.get("status", "Unknown")
    if status_label == "Fresh":
        style = "green"
    elif "Stale" in status_label:
        style = "yellow"
    else:
        style = "red"

    freshness_lines = [f"[bold]Status:[/bold] [{style}]{status_label}[/{style}]"]
    if (
        freshness.get("new_count", 0)
        or freshness.get("modified_count", 0)
        or freshness.get("deleted_count", 0)
    ):
        freshness_lines.append(
            f"  New: {freshness['new_count']}  Modified: {freshness['modified_count']}  Deleted: {freshness['deleted_count']}"
        )

    # Verbose per-file details
    for label, key in [
        ("New", "new_files"),
        ("Modified", "modified_files"),
        ("Deleted", "deleted_files"),
    ]:
        files = freshness.get(key, [])
        if files:
            freshness_lines.append(f"\n  [bold]{label}:[/bold]")
            for f in files:
                freshness_lines.append(f"    {f}")

    console.print(
        Panel("\n".join(freshness_lines), title="Freshness", border_style="blue")
    )

    # Note
    if "note" in data:
        console.print(f"\n[yellow]{data['note']}[/yellow]")


def run_status(
    wiki_path: Path,
    *,
    as_json: bool = False,
    verbose: bool = False,
    console: Console | None = None,
) -> int:
    """Run the status command and return exit code."""
    console = console or Console()
    data = collect_status(wiki_path, verbose=verbose)

    if as_json:
        print(json.dumps(data, indent=2))
    else:
        display_status(data, console)

    return 0


def main() -> int:
    """Main entry point for ``deepwiki status``."""
    parser = argparse.ArgumentParser(
        prog="deepwiki status",
        description="Show index health, wiki coverage, and freshness for a deepwiki project",
        epilog=(
            "examples:\n"
            "  deepwiki status                   Show status for .deepwiki\n"
            "  deepwiki status /path/to/.deepwiki Show status for a specific wiki\n"
            "  deepwiki status --json             Machine-readable JSON output\n"
            "  deepwiki status --verbose          Show per-file change details\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "wiki_path",
        nargs="?",
        default=".deepwiki",
        help="Path to the wiki directory (default: .deepwiki)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as JSON for scripting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show per-file change details",
    )

    args = parser.parse_args()

    return run_status(
        Path(args.wiki_path),
        as_json=args.as_json,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
