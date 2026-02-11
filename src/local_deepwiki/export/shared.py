"""Shared export utilities for HTML and PDF exporters.

Functions extracted from html.py and pdf.py to eliminate duplication
of TOC rendering, breadcrumb building, and title extraction logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


def extract_title(md_file: Path) -> str:
    """Extract title from a markdown file.

    Reads the file looking for the first ``# heading`` or ``**bold**`` line.
    Falls back to a title derived from the filename.

    Args:
        md_file: Path to the markdown file.

    Returns:
        Extracted title string.
    """
    try:
        content = md_file.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("**") and line.endswith("**"):
                return line[2:-2].strip()
    except (OSError, UnicodeDecodeError) as e:
        # OSError: File access issues
        # UnicodeDecodeError: File encoding issues
        logger.debug("Could not extract title from %s: %s", md_file, e)
    return md_file.stem.replace("_", " ").replace("-", " ").title()


def render_toc_entry(entry: dict[str, Any], current_path: str, root_path: str) -> str:
    """Render a single TOC entry recursively as HTML.

    Args:
        entry: TOC entry dict with number, title, path, children.
        current_path: Current page path for highlighting the active link.
        root_path: Relative path to root (e.g. ``"../"``).

    Returns:
        HTML string for this entry and its children.
    """
    has_children = bool(entry.get("children"))
    parent_class = "toc-parent" if has_children else ""

    html = f'<div class="toc-item {parent_class}">'

    if entry.get("path"):
        # Convert .md to .html for static export
        html_path = entry["path"].replace(".md", ".html")
        active = "active" if entry["path"] == current_path else ""
        html += f"""<a href="{root_path}{html_path}" class="{active}">
                <span class="toc-number">{entry.get("number", "")}</span>
                <span>{entry.get("title", "")}</span>
            </a>"""
    else:
        # No link, just a grouping label
        html += f"""<span class="toc-parent">
                <span class="toc-number">{entry.get("number", "")}</span>
                <span>{entry.get("title", "")}</span>
            </span>"""

    if has_children:
        html += '<div class="toc-nested">'
        for child in entry["children"]:
            html += render_toc_entry(child, current_path, root_path)
        html += "</div>"

    html += "</div>"
    return html


def render_toc(entries: list[dict[str, Any]], current_path: str, root_path: str) -> str:
    """Render a list of TOC entries as HTML.

    Args:
        entries: List of TOC entry dicts.
        current_path: Current page path for highlighting the active link.
        root_path: Relative path to root (e.g. ``"../"``).

    Returns:
        Combined HTML string for all entries.
    """
    html_parts = []
    for entry in entries:
        html_parts.append(render_toc_entry(entry, current_path, root_path))
    return "\n".join(html_parts)


def build_breadcrumb(rel_path: Path, root_path: str, wiki_path: Path) -> str:
    """Build breadcrumb navigation HTML.

    Args:
        rel_path: Relative path of the current page within the wiki.
        root_path: Relative path to root (e.g. ``"../"``).
        wiki_path: Absolute path to the wiki directory (used to check
                   for ``index.md`` files in intermediate directories).

    Returns:
        HTML string for the breadcrumb, or empty string for root pages.
    """
    parts = list(rel_path.parts)

    # Root pages don't need breadcrumbs
    if len(parts) == 1:
        return ""

    breadcrumb_items = []

    # Always start with Home
    breadcrumb_items.append(f'<a href="{root_path}index.html">Home</a>')

    # Build path progressively
    cumulative_path = ""
    for part in parts[:-1]:  # Exclude current page
        if cumulative_path:
            cumulative_path = f"{cumulative_path}/{part}"
        else:
            cumulative_path = part

        # Check if there's an index.md in this folder
        index_path = wiki_path / cumulative_path / "index.md"
        display_name = part.replace("_", " ").replace("-", " ").title()

        if index_path.exists():
            link_path = f"{cumulative_path}/index.html"
            breadcrumb_items.append(
                f'<a href="{root_path}{link_path}">{display_name}</a>'
            )
        else:
            breadcrumb_items.append(f"<span>{display_name}</span>")

    # Add current page name
    current_page = parts[-1]
    if current_page.endswith(".md"):
        current_page = current_page[:-3]
    current_page = current_page.replace("_", " ").replace("-", " ").title()
    breadcrumb_items.append(f'<span class="current">{current_page}</span>')

    return (
        '<div class="breadcrumb">'
        + ' <span class="separator">&rsaquo;</span> '.join(breadcrumb_items)
        + "</div>"
    )
