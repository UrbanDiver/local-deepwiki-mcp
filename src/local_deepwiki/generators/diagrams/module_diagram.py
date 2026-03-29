"""Module overview diagram generation using Mermaid."""

from __future__ import annotations

from collections import defaultdict, Counter
from pathlib import Path

from local_deepwiki.models import IndexStatus

from ._utils import sanitize_mermaid_name


# Artifact directories to exclude even if they slipped into the index
_ARTIFACT_DIRS: frozenset[str] = frozenset(
    {
        "htmlcov",
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".eggs",
    }
)

# Top-level layout prefixes that should be skipped in favour of their child
_LAYOUT_PREFIXES: frozenset[str] = frozenset({"src", "lib", "pkg"})


def _group_files_by_directory(
    index_status: IndexStatus,
) -> defaultdict[str, Counter[str]]:
    """Group indexed files by top-level directory, skipping artifacts."""
    directories: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for file_info in index_status.files:
        parts = list(Path(file_info.path).parts)
        if len(parts) < 2:
            continue
        if any(p in _ARTIFACT_DIRS for p in parts):
            continue

        top_dir = parts[0]
        if top_dir in _LAYOUT_PREFIXES and len(parts) > 1:
            top_dir = parts[1]
            parts = parts[1:]

        if len(parts) > 1:
            directories[top_dir][parts[1]] += 1
        else:
            directories[top_dir]["_root"] += 1

    return directories


def _add_directory_node(
    lines: list[str],
    top_dir: str,
    subdirs: Counter[str],
    show_file_counts: bool,
) -> None:
    """Append Mermaid lines for one top-level directory."""
    safe_dir = sanitize_mermaid_name(top_dir)
    total_files = sum(subdirs.values())

    if len(subdirs) > 1 and "_root" not in subdirs:
        lines.append(f"    subgraph {safe_dir}[{top_dir}]")
        for subdir, count in sorted(subdirs.items()):
            if subdir == "_root":
                continue
            safe_sub = sanitize_mermaid_name(f"{top_dir}_{subdir}")
            label = f"{subdir} ({count})" if show_file_counts else subdir
            lines.append(f"        {safe_sub}[{label}]")
        lines.append("    end")
    else:
        label = f"{top_dir} ({total_files})" if show_file_counts else top_dir
        lines.append(f"    {safe_dir}[{label}]")


def generate_module_overview(
    index_status: IndexStatus,
    show_file_counts: bool = True,
) -> str | None:
    """Generate a high-level module overview diagram.

    Shows package structure with subgraphs for major directories.

    Args:
        index_status: Index status with file information.
        show_file_counts: Whether to show file counts in nodes.

    Returns:
        Mermaid diagram string, or None if not enough structure.
    """
    if not index_status.files:
        return None

    directories = _group_files_by_directory(index_status)
    if not directories:
        return None

    lines = ["```mermaid", "graph TB"]
    for top_dir, subdirs in sorted(directories.items()):
        _add_directory_node(lines, top_dir, subdirs, show_file_counts)
    lines.append("```")

    return "\n".join(lines)
