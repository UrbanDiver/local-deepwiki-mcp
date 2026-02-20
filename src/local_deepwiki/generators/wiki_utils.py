"""Shared utility functions for wiki generators.

Consolidates path-manipulation helpers that were previously duplicated
across crosslinks, see_also, source_refs, glossary, and coverage modules.
"""

from __future__ import annotations

from pathlib import Path


def relative_wiki_path(from_path: str, to_path: str) -> str:
    """Calculate relative path between two wiki pages.

    Args:
        from_path: Path of the source page (e.g., "modules/src.md").
        to_path: Path of the target page (e.g., "files/src/indexer.md").

    Returns:
        Relative path from source to target.
    """
    from_parts = Path(from_path).parts[:-1]  # Directory parts only
    to_parts = Path(to_path).parts

    # Find common prefix
    common_length = 0
    for i in range(min(len(from_parts), len(to_parts) - 1)):
        if from_parts[i] == to_parts[i]:
            common_length = i + 1
        else:
            break

    # Build relative path
    ups = len(from_parts) - common_length
    rel_parts = [".."] * ups + list(to_parts[common_length:])

    return "/".join(rel_parts)


def file_path_to_wiki_path(file_path: str) -> str:
    """Convert a source file path to a wiki page path.

    Works for any language by replacing the file extension with .md
    and prepending the files/ directory.

    Examples:
        src/indexer.py  -> files/src/indexer.md
        main.go         -> files/main.md
        lib/utils.ts    -> files/lib/utils.md
    """
    p = Path(file_path)
    parts = p.parts
    stem = p.stem
    if len(parts) > 1:
        return f"files/{'/'.join(parts[:-1])}/{stem}.md"
    return f"files/{stem}.md"
