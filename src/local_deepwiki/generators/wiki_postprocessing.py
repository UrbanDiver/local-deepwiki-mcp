"""Post-processing steps for wiki generation.

Handles cross-linking, search/TOC generation, codemap pages,
wiki status building, and freshness report finalization.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING

from local_deepwiki.generators.crosslinks import add_cross_links
from local_deepwiki.generators.search import write_full_search_index
from local_deepwiki.generators.see_also import add_see_also_sections
from local_deepwiki.generators.source_refs import add_source_refs_sections
from local_deepwiki.generators.stale_detection import generate_stale_report_page
from local_deepwiki.generators.toc import generate_toc, write_toc
from local_deepwiki.generators.wiki_codemaps import generate_codemap_pages
from local_deepwiki.logging import get_logger
from local_deepwiki.models import WikiGenerationStatus, WikiPage

if TYPE_CHECKING:
    from pathlib import Path

    from local_deepwiki.config import WikiConfig
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.generators.crosslinks import EntityRegistry
    from local_deepwiki.generators.progress_tracker import GenerationProgress
    from local_deepwiki.generators.see_also import RelationshipAnalyzer
    from local_deepwiki.generators.wiki_status import WikiStatusManager
    from local_deepwiki.models import IndexStatus, ProgressCallback

logger = get_logger(__name__)


async def generate_codemap_pages_phase(
    *,
    pages: list[WikiPage],
    pages_generated: int,
    pages_skipped: int,
    full_rebuild: bool,
    repo_path: Path,
    wiki_path: Path,
    wiki_config: WikiConfig,
    vector_store: VectorStore,
    llm: object,
    status_manager: WikiStatusManager,
    progress: GenerationProgress,
    write_callback: object,
    progress_callback: ProgressCallback | None,
) -> tuple[list[WikiPage], int, int]:
    """Generate codemap pages for auto-discovered entry points.

    Args:
        pages: Current list of wiki pages (will not be mutated).
        pages_generated: Running count of generated pages.
        pages_skipped: Running count of skipped pages.
        full_rebuild: Whether this is a full rebuild.
        repo_path: Path to the repository.
        wiki_path: Path to wiki output directory.
        wiki_config: Wiki configuration section.
        vector_store: Vector store for code search.
        llm: LLM provider instance.
        status_manager: Wiki status manager.
        progress: Generation progress tracker.
        write_callback: Async callback to write pages to disk.
        progress_callback: Optional progress callback.

    Returns:
        Tuple of (new_codemap_pages, new_pages_generated, new_pages_skipped).
    """
    codemap_enabled = getattr(wiki_config, "codemap_enabled", None)
    if not isinstance(codemap_enabled, bool) or not codemap_enabled:
        return [], pages_generated, pages_skipped

    if progress_callback:
        progress_callback("Generating codemaps", 10, 14)

    progress.start_phase("codemaps", total=0)

    codemap_pages, gen_count, skip_count = await generate_codemap_pages(
        vector_store=vector_store,
        llm=llm,
        repo_path=repo_path,
        wiki_path=wiki_path,
        status_manager=status_manager,
        config=wiki_config,
        full_rebuild=full_rebuild,
    )
    pages_generated += gen_count
    pages_skipped += skip_count

    progress._phase_stats["codemaps"].items_completed = len(codemap_pages)
    progress.complete_phase()

    for page in codemap_pages:
        await write_callback(page)

    return codemap_pages, pages_generated, pages_skipped


async def apply_cross_linking(
    *,
    pages: list[WikiPage],
    entity_registry: EntityRegistry,
    relationship_analyzer: RelationshipAnalyzer,
    status_manager: WikiStatusManager,
    wiki_path: Path,
    write_callback: object,
    progress_callback: ProgressCallback | None,
) -> list[WikiPage]:
    """Apply cross-links, source refs, and see-also sections to pages.

    Args:
        pages: List of wiki pages to process.
        entity_registry: Entity registry for cross-linking.
        relationship_analyzer: Analyzer for see-also sections.
        status_manager: Wiki status manager.
        wiki_path: Path to wiki output directory.
        write_callback: Async callback to write pages to disk.
        progress_callback: Optional progress callback.

    Returns:
        Updated list of pages with cross-linking applied.
    """
    if progress_callback:
        progress_callback("Adding cross-links", 10, 14)

    pages = add_cross_links(pages, entity_registry)

    # Add Relevant Source Files sections with local wiki links
    pages = add_source_refs_sections(pages, status_manager.page_statuses, wiki_path)

    if progress_callback:
        progress_callback("Adding See Also sections", 11, 14)

    pages = add_see_also_sections(pages, relationship_analyzer)

    # Re-write pages with cross-links and See Also sections
    for page in pages:
        await write_callback(page)

    return pages


async def generate_search_and_toc(
    *,
    pages: list[WikiPage],
    index_status: IndexStatus,
    vector_store: VectorStore,
    wiki_path: Path,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate search index and table of contents.

    Args:
        pages: List of wiki pages.
        index_status: Index status.
        vector_store: Vector store.
        wiki_path: Path to wiki output directory.
        progress_callback: Optional progress callback.
    """
    if progress_callback:
        progress_callback("Generating search index", 12, 14)

    await write_full_search_index(wiki_path, pages, index_status, vector_store)

    # Generate table of contents with hierarchical numbering
    page_list = [{"path": p.path, "title": p.title} for p in pages]
    toc = generate_toc(page_list)
    write_toc(toc, wiki_path)

    # Generate llms.txt and llms-full.txt for LLM-friendly project discovery
    try:
        from local_deepwiki.generators.llms_txt import (
            generate_llms_full_txt,
            generate_llms_txt,
        )

        generate_llms_txt(pages, index_status, wiki_path)
        generate_llms_full_txt(pages, index_status, wiki_path)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to generate llms.txt / llms-full.txt", exc_info=True)


def build_wiki_status(
    *,
    pages: list[WikiPage],
    index_status: IndexStatus,
    page_statuses: dict,
) -> WikiGenerationStatus:
    """Build the wiki generation status object.

    Args:
        pages: List of generated wiki pages.
        index_status: Index status.
        page_statuses: Page status dict from the status manager.

    Returns:
        WikiGenerationStatus object.
    """
    return WikiGenerationStatus(
        repo_path=index_status.repo_path,
        generated_at=time.time(),
        total_pages=len(pages),
        index_status_hash=hashlib.sha256(
            json.dumps(index_status.model_dump(), sort_keys=True).encode()
        ).hexdigest()[:16],
        pages=page_statuses,
    )


async def generate_freshness_and_finalize(
    *,
    pages: list[WikiPage],
    all_source_files: list[str],
    pages_generated: int,
    pages_skipped: int,
    repo_path: Path,
    wiki_status: WikiGenerationStatus,
    index_status: IndexStatus,
    status_manager: WikiStatusManager,
    write_callback: object,
    progress_callback: ProgressCallback | None,
) -> tuple[WikiPage, int]:
    """Generate freshness report and finalize wiki status.

    Args:
        pages: Current list of wiki pages (will not be mutated).
        all_source_files: List of all source file paths.
        pages_generated: Running count of generated pages.
        pages_skipped: Running count of skipped pages.
        repo_path: Path to the repository.
        wiki_status: Wiki generation status to update.
        index_status: Index status for structural fingerprint.
        status_manager: Wiki status manager.
        write_callback: Async callback to write pages to disk.
        progress_callback: Optional progress callback.

    Returns:
        Tuple of (freshness_page, updated_pages_generated).
    """
    total_steps = 14

    freshness_page = generate_stale_report_page(
        repo_path=repo_path,
        wiki_status=wiki_status,
        stale_threshold_days=0,
    )
    status_manager.record_summary_page_status(
        freshness_page, all_source_files, index_status
    )
    await write_callback(freshness_page)
    pages_generated += 1

    # Update wiki status with freshness page
    wiki_status.pages[freshness_page.path] = status_manager.page_statuses[
        freshness_page.path
    ]
    wiki_status.total_pages = len(pages) + 1

    await status_manager.save_status(wiki_status)

    if progress_callback:
        progress_callback(
            f"Wiki generation complete ({pages_generated} generated, {pages_skipped} unchanged)",
            total_steps,
            total_steps,
        )

    return freshness_page, pages_generated
