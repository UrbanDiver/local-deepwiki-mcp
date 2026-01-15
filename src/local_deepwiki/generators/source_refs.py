"""Relevant source files section generator for wiki pages.

This module adds a "Relevant Source Files" section to wiki pages,
listing the source code files that informed the documentation.
Links use local wiki paths to keep users on-site.
"""

import re
from pathlib import Path

from local_deepwiki.models import WikiPage, WikiPageStatus


def build_file_to_wiki_map(pages: list[WikiPage]) -> dict[str, str]:
    """Build a mapping from source file paths to wiki page paths.

    Args:
        pages: List of wiki pages.

    Returns:
        Dictionary mapping source file path to wiki page path.
    """
    file_to_wiki: dict[str, str] = {}

    for page in pages:
        # Wiki paths like "files/src/local_deepwiki/core/chunker.md"
        # correspond to source files like "src/local_deepwiki/core/chunker.py"
        if page.path.startswith("files/"):
            # Remove "files/" prefix and change .md to .py
            source_path = page.path[6:]  # Remove "files/"
            source_path = re.sub(r"\.md$", ".py", source_path)
            file_to_wiki[source_path] = page.path

    return file_to_wiki


def _relative_path(from_path: str, to_path: str) -> str:
    """Calculate relative path between two wiki pages.

    Args:
        from_path: Path of the source page.
        to_path: Path of the target page.

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


def _format_file_entry(
    file_path: str,
    wiki_path: str | None,
    current_wiki_path: str,
    line_info: dict[str, int] | None = None,
) -> str:
    """Format a single source file entry with optional line numbers.

    Args:
        file_path: Source file path.
        wiki_path: Wiki page path for this file (if exists).
        current_wiki_path: Path of the current wiki page.
        line_info: Optional dict with 'start_line' and 'end_line' keys.

    Returns:
        Formatted markdown list item.
    """
    # Build display text with line numbers if available
    if line_info:
        display = f"`{file_path}:{line_info['start_line']}-{line_info['end_line']}`"
    else:
        display = f"`{file_path}`"

    # Format the entry - prefer local wiki links to keep users on-site
    if wiki_path and wiki_path != current_wiki_path:
        rel_path = _relative_path(current_wiki_path, wiki_path)
        return f"- [{display}]({rel_path})"
    else:
        return f"- {display}"


def generate_source_refs_section(
    source_files: list[str],
    current_wiki_path: str,
    file_to_wiki: dict[str, str],
    file_line_info: dict[str, dict[str, int]] | None = None,
    max_items: int = 10,
) -> str | None:
    """Generate a Relevant Source Files section for a wiki page.

    Args:
        source_files: List of source file paths that contributed to this page.
        current_wiki_path: Path of the current wiki page.
        file_to_wiki: Mapping of source files to wiki paths.
        file_line_info: Optional mapping of file paths to line info dicts.
        max_items: Maximum number of files to list.

    Returns:
        Markdown string for Relevant Source Files section, or None if no files.
    """
    if not source_files:
        return None

    # Filter and limit source files
    files_to_show = source_files[:max_items]

    # For pages with many source files (like overview/architecture),
    # we could show a summary instead
    if len(source_files) > max_items:
        summary_note = f"\n\n*Showing {max_items} of {len(source_files)} source files.*"
    else:
        summary_note = ""

    # Generate markdown
    lines = ["## Relevant Source Files", ""]

    if len(files_to_show) == 1:
        # Single file - simple format
        file_path = files_to_show[0]
        wiki_path = file_to_wiki.get(file_path)
        line_info = file_line_info.get(file_path) if file_line_info else None
        lines.append(
            _format_file_entry(file_path, wiki_path, current_wiki_path, line_info)
        )
    else:
        # Multiple files - list format for overview/module pages
        lines.append("The following source files were used to generate this documentation:")
        lines.append("")

        for file_path in files_to_show:
            wiki_path = file_to_wiki.get(file_path)
            line_info = file_line_info.get(file_path) if file_line_info else None
            lines.append(
                _format_file_entry(file_path, wiki_path, current_wiki_path, line_info)
            )

    if summary_note:
        lines.append(summary_note)

    return "\n".join(lines)


def _strip_existing_source_refs(content: str) -> str:
    """Remove any existing Relevant Source Files section from content.

    Args:
        content: Wiki page content.

    Returns:
        Content with Relevant Source Files section removed.
    """
    # Pattern to match the section header and everything until the next ## header or end
    source_refs_marker = "\n## Relevant Source Files"
    if source_refs_marker not in content:
        return content

    # Split on the marker and find where the section ends
    parts = content.split(source_refs_marker)
    if len(parts) < 2:
        return content

    result = parts[0].rstrip()

    # For each subsequent part, find where the next section starts
    for part in parts[1:]:
        # Find the next ## header (if any)
        next_section = re.search(r"\n## ", part)
        if next_section:
            # Keep everything from the next section onwards
            result += part[next_section.start():]
        # else: section goes to end, discard it

    return result


def add_source_refs_sections(
    pages: list[WikiPage],
    page_statuses: dict[str, WikiPageStatus],
) -> list[WikiPage]:
    """Add Relevant Source Files sections to wiki pages.

    Args:
        pages: List of wiki pages.
        page_statuses: Dictionary mapping page paths to their status (with source_files).

    Returns:
        List of wiki pages with Relevant Source Files sections added.
    """
    # Build file to wiki path mapping
    file_to_wiki = build_file_to_wiki_map(pages)

    updated_pages = []
    for page in pages:
        # Get source files for this page
        status = page_statuses.get(page.path)
        if not status or not status.source_files:
            updated_pages.append(page)
            continue

        # Skip index pages (like files/index.md, modules/index.md)
        if page.path.endswith("/index.md") or page.path == "index.md":
            # For top-level index, don't add source refs (too many files)
            updated_pages.append(page)
            continue

        # Generate Relevant Source Files section with line info
        source_refs = generate_source_refs_section(
            status.source_files,
            page.path,
            file_to_wiki,
            file_line_info=status.source_line_info,
        )

        if source_refs:
            # First, strip any existing Relevant Source Files section
            content = _strip_existing_source_refs(page.content.rstrip())

            # Check if there's a See Also section to insert before
            see_also_marker = "\n## See Also"
            if see_also_marker in content:
                # Insert before See Also
                parts = content.split(see_also_marker, 1)
                new_content = (
                    parts[0].rstrip() + "\n\n" + source_refs + "\n" + see_also_marker + parts[1]
                )
            else:
                # Add at end
                new_content = content + "\n\n" + source_refs + "\n"

            updated_pages.append(
                WikiPage(
                    path=page.path,
                    title=page.title,
                    content=new_content,
                    generated_at=page.generated_at,
                )
            )
        else:
            updated_pages.append(page)

    return updated_pages
