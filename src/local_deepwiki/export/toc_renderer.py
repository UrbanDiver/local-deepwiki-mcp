"""TOC rendering utilities for PDF/HTML export."""

from __future__ import annotations

from typing import Any


def _add_toc_entries_html(
    entries: list[dict[str, Any]], parts: list[str], depth: int
) -> None:
    """Recursively add TOC entries to HTML parts list."""
    for entry in entries:
        title = entry.get("title", "")
        indent = "  " * depth
        parts.append(f'{indent}<div class="toc-item">{title}</div>')
        if "children" in entry:
            _add_toc_entries_html(entry["children"], parts, depth + 1)


def render_toc_html(entries: list[dict[str, Any]]) -> str:
    """Render a list of TOC entries to an HTML string.

    Args:
        entries: List of TOC entry dicts, each with ``title`` and optional
            ``children`` list.

    Returns:
        HTML string with nested TOC divs.
    """
    parts = ['<div class="toc">']
    _add_toc_entries_html(entries, parts, 0)
    parts.append("</div>")
    return "\n".join(parts)
