"""Wiki generation pipeline — phase execution functions.

This module contains the individual phase implementations called by
``WikiGenerator.generate()``.  Each function accepts a ``WikiGenerator``
instance (and a ``_GenerationContext``) so that it can access the
generator's configuration, vector store, LLM, and other state without
being a method on the (already large) class.

Separating the pipeline logic keeps ``generator.py`` focused on the
public API (``WikiGenerator``, ``WikiGenerationOptions``, ``generate_wiki``)
while the per-phase orchestration lives here.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.generators.progress_tracker import GenerationProgress
from local_deepwiki.generators.wiki.plugin_runner import run_plugin_generators
from local_deepwiki.generators.wiki.postprocessing import (
    apply_cross_linking,
    build_wiki_status,
    generate_codemap_pages_phase,
    generate_freshness_and_finalize,
    generate_search_and_toc,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    IndexStatus,
    ProgressCallback,
    WikiGenerationStatus,
    WikiPage,
    WikiStructure,
)

if TYPE_CHECKING:
    from local_deepwiki.generators.wiki.generator import (
        WikiGenerator,
        _GenerationContext,
    )

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


async def init_generation_context(
    generator: WikiGenerator,
    index_status: IndexStatus,
    full_rebuild: bool,
) -> _GenerationContext:
    """Initialize the generation context with tracking state.

    Sets up the progress tracker, parses the project manifest, reloads
    custom prompts, and builds the file-hash map for incremental updates.
    """
    from local_deepwiki.generators.wiki.generator import _GenerationContext

    # Late import so test patches at generators.wiki.generator.get_cached_manifest work
    from local_deepwiki.generators.wiki import generator as _wiki_gen

    _get_cached_manifest = _wiki_gen.get_cached_manifest

    # Initialize live progress tracker
    generator._progress = GenerationProgress(wiki_path=generator.wiki_path)
    generator._progress.start_phase("initializing", total=0)

    # Store repo path and parse manifest for grounded generation (with caching)
    generator._repo_path = Path(index_status.repo_path)
    generator._manifest = _get_cached_manifest(
        generator._repo_path, cache_dir=generator.wiki_path
    )

    # Update prompt manager with repo path for per-project prompts
    generator._prompt_manager.loader.repo_path = generator._repo_path
    generator._prompt_manager.loader.clear_cache()
    # Reload system prompt and page-type prompts in case repo has custom prompts
    generator._system_prompt = generator._prompt_manager.get_wiki_system_prompt(
        provider=generator.config.llm.provider,
    )
    generator._page_prompts = generator._build_page_prompts()

    # Build file hash map for incremental generation
    generator.status_manager.file_hashes = {f.path: f.hash for f in index_status.files}
    all_source_files = list(generator.status_manager.file_hashes.keys())

    # Load previous wiki status for incremental updates
    if not full_rebuild:
        await generator.status_manager.load_status()

        summary = generator.status_manager.get_regeneration_summary()
        if summary["is_full_rebuild"]:
            logger.info("No previous wiki status found, performing full generation")
        else:
            logger.info(
                "Incremental update: %d files changed, %d pages to regenerate, %d pages unchanged",
                summary["changed_file_count"],
                summary["affected_page_count"],
                summary["unchanged_page_count"],
            )
            if summary["changed_file_count"] <= 5:
                for f in summary["changed_files"]:
                    logger.debug("  Changed: %s", f)

    # Pre-compute line info for source files (for source refs with line numbers)
    generator.status_manager.file_line_info = generator._get_main_definition_lines()

    return _GenerationContext(
        pages=[],
        pages_generated=0,
        pages_skipped=0,
        all_source_files=all_source_files,
        full_rebuild=full_rebuild,
        index_status=index_status,
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


async def analyze_imports_for_relationships(generator: WikiGenerator) -> None:
    """Collect import chunks for relationship analysis (See Also sections)."""
    import_results = await generator.vector_store.search(
        "import require include",
        limit=generator.config.wiki.import_search_limit,
    )
    import_chunks = [
        r.chunk for r in import_results if r.chunk.chunk_type.value == "import"
    ]
    generator.relationship_analyzer.analyze_chunks(import_chunks)


async def generate_module_pages(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Generate module documentation pages."""
    if progress_callback:
        progress_callback("Generating module documentation", 2, 14)

    generator._progress.start_phase("modules", total=0)

    # Late import so test patches at generators.wiki.generator work
    from local_deepwiki.generators.wiki import generator as _wiki_gen

    pipeline_ctx = generator._build_pipeline_context(
        index_status,
        system_prompt=generator._page_prompts.get("module", generator._system_prompt),
        full_rebuild=ctx.full_rebuild,
    )

    module_pages, gen_count, skip_count = await _wiki_gen.generate_module_docs(
        pipeline_ctx,
        semaphore=semaphore,
    )
    ctx.pages_generated += gen_count
    ctx.pages_skipped += skip_count

    # Update module stats and write pages
    generator._progress._phase_stats["modules"].items_completed = len(module_pages)
    generator._progress.complete_phase()

    for page in module_pages:
        ctx.pages.append(page)
        await generator._write_page(page)


async def generate_file_pages(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
    max_files: int | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Generate file-level documentation pages."""
    if progress_callback:
        progress_callback("Generating file documentation", 3, 14)

    # Late import so test patches at generators.wiki.generator work
    from local_deepwiki.generators.wiki import generator as _wiki_gen
    from local_deepwiki.generators.wiki.files import FileDocContext

    file_ctx = FileDocContext(
        index_status=index_status,
        vector_store=generator.vector_store,
        llm=generator.llm,
        system_prompt=generator._page_prompts.get("file", generator._system_prompt),
        status_manager=generator.status_manager,
        entity_registry=generator.entity_registry,
        config=generator.config,
        full_rebuild=ctx.full_rebuild,
    )
    file_pages, gen_count, skip_count = await _wiki_gen.generate_file_docs(
        file_ctx,
        progress_callback=progress_callback,
        write_callback=generator._write_page,
        generation_progress=generator._progress,
        max_files=max_files,
        semaphore=semaphore,
    )
    ctx.pages_generated += gen_count
    ctx.pages_skipped += skip_count
    ctx.pages.extend(file_pages)


async def run_wiki_plugin_generators(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Run registered wiki generator plugins."""
    new_pages, pages_generated = await run_plugin_generators(
        pages=ctx.pages,
        all_source_files=ctx.all_source_files,
        index_status=index_status,
        vector_store=generator.vector_store,
        llm=generator.llm,
        config=generator.config,
        wiki_path=generator.wiki_path,
        status_manager=generator.status_manager,
        write_callback=generator._write_page,
        progress_callback=progress_callback,
    )
    ctx.pages.extend(new_pages)
    ctx.pages_generated += pages_generated


async def generate_codemap_pages(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate codemap pages for auto-discovered entry points."""
    assert generator._repo_path is not None, (
        "Repository path must be set before generating codemaps"
    )

    pipeline_ctx = generator._build_pipeline_context(
        index_status,
        full_rebuild=ctx.full_rebuild,
    )

    (
        codemap_pages,
        ctx.pages_generated,
        ctx.pages_skipped,
    ) = await generate_codemap_pages_phase(
        ctx=pipeline_ctx,
        pages=ctx.pages,
        pages_generated=ctx.pages_generated,
        pages_skipped=ctx.pages_skipped,
        progress=generator._progress,
        write_callback=generator._write_page,
        progress_callback=progress_callback,
    )
    ctx.pages.extend(codemap_pages)


async def apply_cross_linking_phase(
    generator: WikiGenerator,
    pages: list[WikiPage],
    progress_callback: ProgressCallback | None,
) -> list[WikiPage]:
    """Apply cross-links, source refs, and see-also sections to pages."""
    return await apply_cross_linking(
        pages=pages,
        entity_registry=generator.entity_registry,
        relationship_analyzer=generator.relationship_analyzer,
        status_manager=generator.status_manager,
        wiki_path=generator.wiki_path,
        write_callback=generator._write_page,
        progress_callback=progress_callback,
    )


async def generate_search_and_toc_phase(
    generator: WikiGenerator,
    pages: list[WikiPage],
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate search index and table of contents."""
    await generate_search_and_toc(
        pages=pages,
        index_status=index_status,
        vector_store=generator.vector_store,
        wiki_path=generator.wiki_path,
        progress_callback=progress_callback,
    )


def build_wiki_status_from_context(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    index_status: IndexStatus,
) -> WikiGenerationStatus:
    """Build the wiki generation status object."""
    return build_wiki_status(
        pages=ctx.pages,
        index_status=index_status,
        page_statuses=generator.status_manager.page_statuses,
    )


async def generate_freshness_and_finalize_phase(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    wiki_status: WikiGenerationStatus,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate freshness report and finalize wiki status."""
    assert generator._repo_path is not None, (
        "Repository path must be set before generating wiki"
    )

    pipeline_ctx = generator._build_pipeline_context(
        index_status,
        full_rebuild=ctx.full_rebuild,
    )

    freshness_page, ctx.pages_generated = await generate_freshness_and_finalize(
        ctx=pipeline_ctx,
        pages=ctx.pages,
        all_source_files=ctx.all_source_files,
        pages_generated=ctx.pages_generated,
        pages_skipped=ctx.pages_skipped,
        wiki_status=wiki_status,
        write_callback=generator._write_page,
        progress_callback=progress_callback,
    )
    ctx.pages.append(freshness_page)


def log_cache_stats(generator: WikiGenerator) -> None:
    """Log LLM cache statistics if available."""
    try:
        cache_stats = getattr(generator.llm, "stats", None)
        if cache_stats is None:
            return
        hits = int(cache_stats.get("hits", 0))
        misses = int(cache_stats.get("misses", 0))
        skipped = int(cache_stats.get("skipped", 0))
        total = hits + misses
        hit_rate = (hits / total * 100) if total > 0 else 0.0
        logger.info(
            "LLM cache stats: %d hits, %d misses, %d skipped (%.1f%% hit rate)",
            hits,
            misses,
            skipped,
            hit_rate,
        )
    except (TypeError, ValueError, AttributeError):
        # Skip logging if stats are not properly available (e.g., mock objects)
        pass


# ---------------------------------------------------------------------------
# Top-level pipeline orchestrator
# ---------------------------------------------------------------------------


async def run_generation_pipeline(
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None = None,
    full_rebuild: bool = False,
    max_file_pages: int | None = None,
) -> WikiStructure:
    """Execute all generation phases and return the wiki structure.

    This function is called by ``WikiGenerator.generate()`` and contains
    the full multi-phase pipeline.
    """
    from local_deepwiki.generators.wiki.phases import (
        generate_auxiliary_pages as _phases_generate_auxiliary_pages,
        generate_changelog_phase,
        generate_dependencies_page_phase,
        generate_summary_pages,
    )

    logger.info("Starting wiki generation for %s", index_status.repo_path)
    logger.debug(
        "Full rebuild: %s, Total files: %s", full_rebuild, index_status.total_files
    )

    # Emit WIKI_START event
    emitter = get_event_emitter()
    await emitter.emit(
        EventType.WIKI_START,
        {
            "repo_path": index_status.repo_path,
            "full_rebuild": full_rebuild,
            "total_files": index_status.total_files,
        },
    )

    # Initialize generation context
    ctx = await init_generation_context(generator, index_status, full_rebuild)
    ctx.progress_callback = progress_callback

    # Phase 1: Generate summary pages (overview, architecture)
    await generate_summary_pages(ctx, generator)

    # Phase 2: Analyze imports for relationship tracking
    await analyze_imports_for_relationships(generator)

    # Phase 3+4: Generate module and file documentation concurrently
    shared_semaphore = asyncio.Semaphore(generator.config.effective_llm_concurrency)
    await asyncio.gather(
        generate_module_pages(
            generator, ctx, index_status, progress_callback, semaphore=shared_semaphore
        ),
        generate_file_pages(
            generator,
            ctx,
            index_status,
            progress_callback,
            max_files=max_file_pages,
            semaphore=shared_semaphore,
        ),
    )

    # Phase 5: Generate dependencies page
    await generate_dependencies_page_phase(ctx, generator)

    # Phase 6: Generate changelog
    await generate_changelog_phase(ctx, generator)

    # Phase 7: Generate auxiliary pages (inheritance, glossary, coverage)
    await _phases_generate_auxiliary_pages(ctx, generator)

    # Phase 7b: Run wiki generator plugins
    await run_wiki_plugin_generators(generator, ctx, index_status, progress_callback)

    # Phase 7c: Generate codemap pages
    await generate_codemap_pages(generator, ctx, index_status, progress_callback)

    # Phase 8: Apply cross-links and see-also sections
    ctx.pages = await apply_cross_linking_phase(generator, ctx.pages, progress_callback)

    # Phase 9: Generate search index and TOC
    await generate_search_and_toc_phase(
        generator, ctx.pages, index_status, progress_callback
    )

    # Phase 10: Generate freshness report and finalize
    wiki_status = build_wiki_status_from_context(generator, ctx, index_status)
    await generate_freshness_and_finalize_phase(
        generator, ctx, wiki_status, index_status, progress_callback
    )

    logger.info(
        "Wiki generation complete: %d pages generated, %d pages unchanged, %d total pages",
        ctx.pages_generated,
        ctx.pages_skipped,
        len(ctx.pages),
    )

    # Log any generation warnings
    if ctx.warnings:
        logger.warning(
            "Wiki generation completed with %s warning(s)", len(ctx.warnings)
        )
        for warning in ctx.warnings:
            logger.warning("  - %s", warning)
            generator._progress._log(f"WARNING: {warning}")

    # Log LLM cache statistics if available
    generator._log_cache_stats()

    # Finalize progress tracker and log summary
    summary = generator._progress.finalize(success=True, warnings=ctx.warnings)
    logger.info(summary)

    # Emit WIKI_COMPLETE event
    await emitter.emit(
        EventType.WIKI_COMPLETE,
        {
            "repo_path": index_status.repo_path,
            "total_pages": len(ctx.pages),
            "pages_generated": ctx.pages_generated,
            "pages_skipped": ctx.pages_skipped,
        },
    )

    return WikiStructure(root=str(generator.wiki_path), pages=ctx.pages)
