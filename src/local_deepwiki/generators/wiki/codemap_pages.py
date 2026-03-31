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
    from local_deepwiki.generators.wiki.context import WikiPipelineContext

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_CLICK_RE = re.compile(r'(\s+click\s+\S+\s+)"files/([^"]+)"(\s+_blank)')
_MIN_NODES = 3


def _has_wiki_page(wiki_path: Path | None, rel_md: str) -> bool:
    """Check whether a wiki file page exists on disk."""
    if wiki_path is None:
        return True  # Optimistic when wiki_path unknown
    return (wiki_path / "files" / rel_md).exists()


def _fix_mermaid_click_paths(diagram: str, wiki_path: Path | None = None) -> str:
    """Rewrite Mermaid click handlers for wiki context.

    The codemap generator produces ``click N0 "files/src/foo.py" _blank``
    but wiki codemap pages live under ``codemaps/``, so relative links must
    go up one level and use ``.md`` extensions.

    Click handlers for files without wiki pages are removed entirely.
    """

    def _repl(m: re.Match) -> str:
        prefix, rel_path, suffix = m.group(1), m.group(2), m.group(3)
        md_path = str(Path(rel_path).with_suffix(".md"))
        if not _has_wiki_page(wiki_path, md_path):
            return ""  # Remove click handler for missing pages
        return f'{prefix}"../files/{md_path}"{suffix}'

    # Filter out empty replacements (removed click lines)
    result = _CLICK_RE.sub(_repl, diagram)
    return "\n".join(line for line in result.split("\n") if line.strip())


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


def _format_codemap_page(
    topic: dict, result: CodemapResult, wiki_path: Path | None = None
) -> str:
    """Format a single codemap result as a markdown page."""
    entry_point = topic.get("entry_point", "unknown")
    file_path = topic.get("file_path", "")

    diagram = _fix_mermaid_click_paths(result.mermaid_diagram, wiki_path)

    # Build a wiki-relative link for the entry point file (only if page exists)
    entry_link = str(Path(file_path).with_suffix(".md")) if file_path else ""
    if entry_link and _has_wiki_page(wiki_path, entry_link):
        entry_ref = (
            f"> Entry point: [`{entry_point}`](../files/{entry_link}) in `{file_path}`"
        )
    else:
        entry_ref = f"> Entry point: `{entry_point}` in `{file_path}`"

    query = topic.get("suggested_query", f"How does {entry_point} work?")

    lines = [
        f"# Codemap: How {entry_point} Works",
        "",
        # Hidden metadata for the "Open in Codemap" link in page.html.
        # The template JS reads data-codemap-* attributes to pass the same
        # parameters to the interactive codemap, ensuring identical results.
        f'<div data-codemap-query="{query}" data-codemap-entry="{entry_point}"'
        f' data-codemap-focus="execution_flow" style="display:none"></div>',
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
        if _has_wiki_page(wiki_path, md_rel):
            lines.append(f"- [`{fp}`](../files/{md_rel})")
        else:
            lines.append(f"- `{fp}`")

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


async def _process_codemap_topic(
    topic: dict,
    ctx: "WikiPipelineContext",
) -> tuple[WikiPage | None, bool, bool]:
    """Process a single codemap topic: check cache or generate fresh.

    Args:
        topic: Topic dict with entry_point, file_path, suggested_query.
        ctx: Immutable pipeline context bundling shared parameters.

    Returns:
        Tuple of (page_or_None, was_skipped, was_generated). Both False when
        the topic was skipped due to error or trivial result.
    """
    entry_point = topic.get("entry_point", "")
    slug = _topic_slug(entry_point)
    page_path = f"codemaps/{slug}.md"
    source_files = [topic.get("file_path", "")]

    config = ctx.wiki_config

    # Check if page needs regeneration
    if not ctx.full_rebuild and not ctx.status_manager.needs_regeneration(
        page_path, source_files
    ):
        existing_page = await ctx.status_manager.load_existing_page(page_path)
        if existing_page is not None:
            ctx.status_manager.record_page_status(existing_page, source_files)
            return existing_page, True, False

    # Generate codemap
    try:
        result = await generate_codemap(
            query=topic.get("suggested_query", f"How does {entry_point} work?"),
            vector_store=ctx.vector_store,
            repo_path=ctx.repo_path,
            llm=ctx.llm,
            entry_point=entry_point,
            focus=CodemapFocus.EXECUTION_FLOW,
            max_depth=config.codemap_max_depth,
            max_nodes=config.codemap_max_nodes,
        )
    except (ValueError, RuntimeError, OSError, TypeError):
        # ValueError/RuntimeError: vector store or LLM provider failures
        # OSError: file I/O or network errors
        # TypeError: unexpected data shapes from LLM or vector store
        logger.exception("Failed to generate codemap for %s", entry_point)
        return None, False, False

    # Skip trivial graphs
    if result.total_nodes < _MIN_NODES:
        logger.debug(
            "Skipping trivial codemap for %s (%d nodes)",
            entry_point,
            result.total_nodes,
        )
        return None, False, False

    content = _format_codemap_page(topic, result, ctx.wiki_path)
    page = WikiPage(
        path=page_path,
        title=f"Codemap: {entry_point}",
        content=content,
        generated_at=time.time(),
    )
    ctx.status_manager.record_page_status(page, source_files)
    return page, False, True


def _cleanup_orphaned_codemap_pages(
    wiki_path: Path | None, generated_topics: list[dict]
) -> None:
    """Remove codemap pages on disk that are no longer in the generated set.

    Args:
        wiki_path: Wiki output directory.
        generated_topics: Topics that were successfully generated or loaded.
    """
    if wiki_path is None:
        return
    codemaps_dir = wiki_path / "codemaps"
    if not codemaps_dir.is_dir():
        return
    current_slugs = {_topic_slug(t.get("entry_point", "")) for t in generated_topics}
    current_slugs.add("index")
    for md_file in codemaps_dir.glob("*.md"):
        if md_file.stem not in current_slugs:
            try:
                md_file.unlink()
                logger.debug("Removed orphaned codemap page: %s", md_file.name)
            except OSError:
                logger.debug("Failed to remove orphaned codemap: %s", md_file.name)


async def generate_codemap_pages(
    ctx: "WikiPipelineContext",
) -> tuple[list[WikiPage], int, int]:
    """Generate codemap wiki pages for auto-discovered entry points.

    Args:
        ctx: Immutable pipeline context bundling shared parameters.

    Returns:
        Tuple of (pages list, generated count, skipped count).
    """
    config = ctx.wiki_config
    if not config.codemap_enabled or config.codemap_max_topics <= 0:
        return [], 0, 0

    # Discover high-value entry points
    try:
        topics = await suggest_topics(
            vector_store=ctx.vector_store,
            repo_path=ctx.repo_path,
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

    logger.info("Generating codemaps for %s entry points", len(topics))

    pages: list[WikiPage] = []
    generated = 0
    skipped = 0
    generated_topics: list[dict] = []

    for topic in topics:
        page, was_skipped, was_generated = await _process_codemap_topic(
            topic,
            ctx,
        )
        if page is not None:
            pages.append(page)
            generated_topics.append(topic)
            if was_skipped:
                skipped += 1
            elif was_generated:
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
    ctx.status_manager.record_page_status(index_page, all_source_files or [""])
    generated += 1

    # Clean up orphaned codemap pages
    _cleanup_orphaned_codemap_pages(ctx.wiki_path, generated_topics)

    logger.info(
        "Codemap generation complete: %d generated, %d unchanged", generated, skipped
    )
    return pages, generated, skipped
