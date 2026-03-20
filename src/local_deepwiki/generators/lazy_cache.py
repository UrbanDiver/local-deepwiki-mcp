"""Page caching helpers for LazyPageGenerator.

These functions encapsulate reading, writing, and maintaining the on-disk wiki
page cache used by ``LazyPageGenerator``.  They are imported and delegated to
by ``LazyPageGenerator``; external callers should use ``LazyPageGenerator``
directly rather than importing from this module.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.models import WikiPage


def read_cached_page(wiki_path: Path, page_path: str) -> str | None:
    """Return cached page content from disk, or None if not yet generated.

    Args:
        wiki_path: Root directory of the wiki on disk.
        page_path: Relative path of the page within the wiki (e.g. ``index.md``).

    Returns:
        The file's text content if it exists on disk, or ``None``.
    """
    full = wiki_path / page_path
    if full.exists():
        return full.read_text()
    return None


async def write_page(wiki_path: Path, page: "WikiPage") -> None:
    """Write a generated wiki page to disk, creating parent directories as needed.

    Args:
        wiki_path: Root directory of the wiki on disk.
        page: The ``WikiPage`` to persist.
    """
    page_path = wiki_path / page.path

    def _sync() -> None:
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(page.content)

    await asyncio.to_thread(_sync)


def append_to_search_index(wiki_path: Path, page: "WikiPage") -> None:
    """Append a page entry to the JSON search index for client-side search.

    The search index is a JSON array stored at ``wiki_path/search_index.json``.
    Each entry contains the page path, title, and a short summary snippet.

    Args:
        wiki_path: Root directory of the wiki on disk.
        page: The ``WikiPage`` to add to the index.
    """
    idx_path = wiki_path / "search_index.json"
    try:
        entries = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except (json.JSONDecodeError, OSError):
        entries = []
    entries.append(
        {
            "path": page.path,
            "title": page.title,
            "summary": page.content[:200],
        }
    )
    idx_path.write_text(json.dumps(entries))


def is_page_cached(wiki_path: Path, page_path: str) -> bool:
    """Return True if a cached copy of the page exists on disk.

    Args:
        wiki_path: Root directory of the wiki on disk.
        page_path: Relative path of the page within the wiki.

    Returns:
        True if the page file exists on disk.
    """
    return (wiki_path / page_path).exists()


def invalidate_page(wiki_path: Path, page_path: str) -> bool:
    """Remove a cached page from disk, forcing regeneration on next access.

    Args:
        wiki_path: Root directory of the wiki on disk.
        page_path: Relative path of the page within the wiki.

    Returns:
        True if the file was deleted, False if it did not exist.
    """
    full = wiki_path / page_path
    if full.exists():
        full.unlink()
        return True
    return False
