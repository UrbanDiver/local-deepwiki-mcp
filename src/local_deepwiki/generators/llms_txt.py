"""Generate an llms.txt file for LLM-friendly project discovery.

The llms.txt format provides a concise, structured summary of a project's
documentation pages and code statistics. It is designed to be consumed by
LLM agents for quick orientation.

See https://llmstxt.org for the specification.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from local_deepwiki.models import IndexStatus, WikiPage

logger = get_logger(__name__)


def _sort_key(page: WikiPage) -> tuple[int, str]:
    """Sort pages: index first, architecture, then modules/, files/, rest.

    Args:
        page: A wiki page.

    Returns:
        Tuple for sort ordering.
    """
    path = page.path
    if path == "index.md":
        return (0, path)
    if path == "architecture.md":
        return (1, path)
    if path.startswith("modules/"):
        return (2, path)
    if path.startswith("files/"):
        return (3, path)
    return (4, path)


def generate_llms_txt(
    pages: list[WikiPage],
    index_status: IndexStatus,
    wiki_path: Path,
    manifest: dict | None = None,
) -> Path:
    """Generate an llms.txt file summarizing the wiki for LLM agents.

    Args:
        pages: List of generated wiki pages.
        index_status: Index status with repo metadata.
        wiki_path: Path to the wiki output directory.
        manifest: Optional parsed project manifest dict (name, description, etc.).

    Returns:
        Path to the written llms.txt file.
    """
    # Determine project name and description
    project_name = "Project"
    description = ""

    if manifest:
        project_name = manifest.get("name", project_name)
        description = manifest.get("description", "")

    if not description:
        # Fall back to repo directory name
        repo_path = Path(index_status.repo_path)
        project_name = project_name if project_name != "Project" else repo_path.name
        description = f"Documentation for {project_name}"

    lines: list[str] = []
    lines.append(f"# {project_name}")
    lines.append(f"> {description}")
    lines.append("")

    # Documentation pages
    sorted_pages = sorted(pages, key=_sort_key)
    if sorted_pages:
        lines.append("## Documentation Pages")
        for page in sorted_pages:
            # Use title and path
            title = page.title or page.path
            lines.append(f"- [{title}]({page.path}): {_page_summary(page)}")
        lines.append("")

    # Code statistics
    lines.append("## Code Statistics")
    lines.append(f"- Files indexed: {index_status.total_files}")

    if index_status.languages:
        lang_list = ", ".join(sorted(index_status.languages.keys()))
        lines.append(f"- Languages: {lang_list}")

    lines.append(f"- Code chunks: {index_status.total_chunks}")
    lines.append(f"- Wiki pages: {len(pages)}")
    lines.append("")

    output_path = wiki_path / "llms.txt"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Generated llms.txt at %s (%d pages)", output_path, len(pages))

    return output_path


def generate_llms_full_txt(
    pages: list[WikiPage],
    index_status: IndexStatus,
    wiki_path: Path,
    manifest: dict | None = None,
) -> Path:
    """Generate an llms-full.txt file with full wiki content concatenated.

    Per the llmstxt.org specification, llms-full.txt provides the complete
    documentation content in a single file, with ``---`` separators between
    pages.

    Args:
        pages: List of generated wiki pages.
        index_status: Index status with repo metadata.
        wiki_path: Path to the wiki output directory.
        manifest: Optional parsed project manifest dict.

    Returns:
        Path to the written llms-full.txt file.
    """
    project_name = "Project"
    if manifest:
        project_name = manifest.get("name", project_name)
    if project_name == "Project":
        project_name = Path(index_status.repo_path).name

    parts: list[str] = [f"# {project_name} — Full Documentation\n"]

    sorted_pages = sorted(pages, key=_sort_key)
    for page in sorted_pages:
        parts.append(f"---\n\n## {page.title or page.path}\n")
        parts.append(page.content.strip())
        parts.append("")

    output_path = wiki_path / "llms-full.txt"
    output_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info(
        "Generated llms-full.txt at %s (%d pages, %d bytes)",
        output_path,
        len(pages),
        output_path.stat().st_size,
    )
    return output_path


def _page_summary(page: WikiPage) -> str:
    """Extract a brief summary from a page's content.

    Takes the first non-heading, non-empty line as a summary.

    Args:
        page: The wiki page.

    Returns:
        A short summary string.
    """
    for line in page.content.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            # Truncate to reasonable length
            if len(stripped) > 120:
                return stripped[:117] + "..."
            return stripped
    return page.title or page.path
