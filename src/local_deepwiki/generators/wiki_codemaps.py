"""Codemap page generation for wiki.

Auto-generates execution-flow diagrams for high-value entry points
discovered by ``suggest_topics``, writing results as markdown pages
under ``codemaps/``.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.generators.codemap import (
    CodemapFocus,
    CodemapResult,
    generate_codemap,
    suggest_topics,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import WikiPage

if TYPE_CHECKING:
    from local_deepwiki.config import WikiConfig
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.generators.wiki_status import WikiStatusManager
    from local_deepwiki.providers.base import LLMProvider

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CLICK_RE = re.compile(r'(\s+click\s+\S+\s+)"files/([^"]+)"(\s+_blank)')
_MIN_NODES = 3


def _fix_mermaid_click_paths(diagram: str) -> str:
    """Rewrite Mermaid click handlers for wiki context.

    The codemap generator produces ``click N0 "files/src/foo.py" _blank``
    but wiki codemap pages live under ``codemaps/``, so relative links must
    go up one level and use ``.md`` extensions.
    """

    def _repl(m: re.Match) -> str:
        prefix, rel_path, suffix = m.group(1), m.group(2), m.group(3)
        # Strip source extension, add .md
        md_path = str(Path(rel_path).with_suffix(".md"))
        return f'{prefix}"../files/{md_path}"{suffix}'

    return _CLICK_RE.sub(_repl, diagram)


def _topic_slug(entry_point: str) -> str:
    """Derive a filesystem-safe slug from an entry-point name.

    Examples:
        >>> _topic_slug("WikiGenerator.generate")
        'wikigenerator-generate'
        >>> _topic_slug("__main__")
        'main'
    """
    slug = _SLUG_RE.sub("-", entry_point.lower()).strip("-")
    return slug[:80] if slug else "unnamed"


def _format_codemap_page(topic: dict, result: CodemapResult) -> str:
    """Format a single codemap result as a markdown page."""
    entry_point = topic.get("entry_point", "unknown")
    file_path = topic.get("file_path", "")

    diagram = _fix_mermaid_click_paths(result.mermaid_diagram)

    # Build a wiki-relative link for the entry point file
    entry_link = str(Path(file_path).with_suffix(".md")) if file_path else ""
    entry_ref = (
        f"> Entry point: [`{entry_point}`](../files/{entry_link}) in `{file_path}`"
        if entry_link
        else f"> Entry point: `{entry_point}` in `{file_path}`"
    )

    lines = [
        f"# Codemap: How {entry_point} Works",
        "",
        entry_ref,
        "",
        "## Execution Flow",
        "",
        "```mermaid",
        diagram,
        "```",
        "",
        "## Trace",
        "",
        result.narrative,
        "",
        "## Statistics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Nodes | {result.total_nodes} |",
        f"| Edges | {result.total_edges} |",
        f"| Cross-file edges | {result.cross_file_edges} |",
        f"| Files involved | {len(result.files_involved)} |",
        "",
        "## Files Involved",
        "",
    ]
    for fp in sorted(result.files_involved):
        md_rel = str(Path(fp).with_suffix(".md"))
        lines.append(f"- [`{fp}`](../files/{md_rel})")

    return "\n".join(lines) + "\n"


def _format_codemap_index(topics: list[dict]) -> str:
    """Format the codemaps index page listing all generated codemaps."""
    lines = [
        "# Codemaps",
        "",
        "Auto-generated execution-flow diagrams for key entry points.",
        "",
    ]
    if not topics:
        lines.append("*No codemaps were generated for this repository.*")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Entry Point | File | Reason |",
            "|-------------|------|--------|",
        ]
    )
    for topic in topics:
        entry = topic.get("entry_point", "")
        fp = topic.get("file_path", "")
        reason = topic.get("reason", "")
        slug = _topic_slug(entry)
        lines.append(f"| [{entry}]({slug}.md) | `{fp}` | {reason} |")

    return "\n".join(lines) + "\n"


async def generate_codemap_pages(
    vector_store: "VectorStore",
    llm: "LLMProvider",
    repo_path: Path,
    wiki_path: Path,
    status_manager: "WikiStatusManager",
    config: "WikiConfig",
    full_rebuild: bool,
) -> tuple[list[WikiPage], int, int]:
    """Generate codemap wiki pages for auto-discovered entry points.

    Args:
        vector_store: Vector store with indexed code.
        llm: LLM provider for narrative generation.
        repo_path: Path to the repository.
        wiki_path: Path to wiki output directory.
        status_manager: Wiki status manager for incremental updates.
        config: Wiki configuration with codemap settings.
        full_rebuild: If True, regenerate all codemap pages.

    Returns:
        Tuple of (pages list, generated count, skipped count).
    """
    if not config.codemap_enabled or config.codemap_max_topics <= 0:
        return [], 0, 0

    # Discover high-value entry points
    try:
        topics = await suggest_topics(
            vector_store=vector_store,
            repo_path=repo_path,
            max_suggestions=config.codemap_max_topics,
        )
    except (ValueError, RuntimeError, OSError):
        # ValueError/RuntimeError: vector store or call graph extraction failures
        # OSError: file I/O errors during topic discovery
        logger.exception("Failed to discover codemap topics")
        return [], 0, 0

    if not topics:
        logger.info("No codemap topics discovered, skipping codemap generation")
        return [], 0, 0

    logger.info(f"Generating codemaps for {len(topics)} entry points")

    pages: list[WikiPage] = []
    generated = 0
    skipped = 0
    generated_topics: list[dict] = []

    for topic in topics:
        entry_point = topic.get("entry_point", "")
        slug = _topic_slug(entry_point)
        page_path = f"codemaps/{slug}.md"
        source_files = [topic.get("file_path", "")]

        # Check if page needs regeneration
        if not full_rebuild and not status_manager.needs_regeneration(
            page_path, source_files
        ):
            existing_page = await status_manager.load_existing_page(page_path)
            if existing_page is not None:
                pages.append(existing_page)
                status_manager.record_page_status(existing_page, source_files)
                generated_topics.append(topic)
                skipped += 1
                continue

        # Generate codemap
        try:
            result = await generate_codemap(
                query=topic.get("suggested_query", f"How does {entry_point} work?"),
                vector_store=vector_store,
                repo_path=repo_path,
                llm=llm,
                entry_point=entry_point,
                focus=CodemapFocus.EXECUTION_FLOW,
                max_depth=config.codemap_max_depth,
                max_nodes=config.codemap_max_nodes,
            )
        except (ValueError, RuntimeError, OSError, TypeError):
            # ValueError/RuntimeError: vector store or LLM provider failures
            # OSError: file I/O or network errors
            # TypeError: unexpected data shapes from LLM or vector store
            logger.exception(f"Failed to generate codemap for {entry_point}")
            continue

        # Skip trivial graphs
        if result.total_nodes < _MIN_NODES:
            logger.debug(
                f"Skipping trivial codemap for {entry_point} ({result.total_nodes} nodes)"
            )
            continue

        content = _format_codemap_page(topic, result)
        page = WikiPage(
            path=page_path,
            title=f"Codemap: {entry_point}",
            content=content,
            generated_at=time.time(),
        )
        pages.append(page)
        status_manager.record_page_status(page, source_files)
        generated_topics.append(topic)
        generated += 1

    # Generate index page
    index_content = _format_codemap_index(generated_topics)
    index_page = WikiPage(
        path="codemaps/index.md",
        title="Codemaps",
        content=index_content,
        generated_at=time.time(),
    )
    pages.append(index_page)
    all_source_files = [t.get("file_path", "") for t in generated_topics]
    status_manager.record_page_status(index_page, all_source_files or [""])
    generated += 1

    # Clean up orphaned codemap pages
    codemaps_dir = wiki_path / "codemaps"
    if codemaps_dir.is_dir():
        current_slugs = {
            _topic_slug(t.get("entry_point", "")) for t in generated_topics
        }
        current_slugs.add("index")
        for md_file in codemaps_dir.glob("*.md"):
            if md_file.stem not in current_slugs:
                try:
                    md_file.unlink()
                    logger.debug(f"Removed orphaned codemap page: {md_file.name}")
                except OSError:
                    logger.warning(f"Failed to remove orphaned codemap: {md_file.name}")

    logger.info(
        f"Codemap generation complete: {generated} generated, {skipped} unchanged"
    )
    return pages, generated, skipped
