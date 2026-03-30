"""Wiki generation pipeline -- phase execution functions.

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
from typing import TYPE_CHECKING, Any

from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.generators.progress_tracker import GenerationProgress
from local_deepwiki.generators.wiki.pipeline_params import WikiPipelineParams
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
                "Incremental update: %d files changed, "
                "%d pages to regenerate, %d pages unchanged",
                summary["changed_file_count"],
                summary["affected_page_count"],
                summary["unchanged_page_count"],
            )
            if summary["changed_file_count"] <= 5:
                for f in summary["changed_files"]:
                    logger.debug("  Changed: %s", f)

    # Pre-compute line info for source files (for source refs with line numbers)
    generator.status_manager.file_line_info = generator._get_main_definition_lines()

    from local_deepwiki.generators.wiki.context import WikiPipelineContext

    pipeline_ctx = WikiPipelineContext(
        index_status=index_status,
        vector_store=generator.vector_store,
        llm=generator.llm,
        system_prompt=generator._system_prompt,
        repo_path=generator._repo_path,
        wiki_path=generator.wiki_path,
        config=generator.config,
        wiki_config=generator.config.wiki,
        manifest=generator._manifest,
        status_manager=generator.status_manager,
        full_rebuild=full_rebuild,
        max_chunk_content_chars=generator.config.wiki.max_chunk_content_chars,
    )

    return _GenerationContext(
        pages=[],
        pages_generated=0,
        pages_skipped=0,
        all_source_files=all_source_files,
        full_rebuild=full_rebuild,
        index_status=index_status,
        pipeline_ctx=pipeline_ctx,
    )


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------


def _build_pipeline_params(
    generator: WikiGenerator,
    ctx: _GenerationContext,
) -> WikiPipelineParams:
    """Build a :class:`WikiPipelineParams` from generator and context state."""
    assert ctx.pipeline_ctx is not None, (
        "pipeline_ctx must be set before building pipeline params"
    )
    return WikiPipelineParams(
        ctx=ctx.pipeline_ctx,
        write_callback=generator._write_page,
        progress_callback=ctx.progress_callback,
        all_source_files=ctx.all_source_files,
    )


async def analyze_imports_for_relationships(
    generator: WikiGenerator,
) -> None:
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
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Generate module documentation pages."""
    if ctx.progress_callback:
        ctx.progress_callback("Generating module documentation", 2, 14)

    generator._progress.start_phase("modules", total=0)

    # Late import so test patches at generators.wiki.generator work
    from local_deepwiki.generators.wiki import generator as _wiki_gen

    pipeline_ctx = generator._build_pipeline_context(
        ctx.index_status,
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
    max_files: int | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> None:
    """Generate file-level documentation pages."""
    if ctx.progress_callback:
        ctx.progress_callback("Generating file documentation", 3, 14)

    # Late import so test patches at generators.wiki.generator work
    from local_deepwiki.generators.wiki import generator as _wiki_gen
    from local_deepwiki.generators.wiki.files import FileDocContext

    file_ctx = FileDocContext(
        index_status=ctx.index_status,
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
        progress_callback=ctx.progress_callback,
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
) -> None:
    """Run registered wiki generator plugins."""
    params = _build_pipeline_params(generator, ctx)
    new_pages, pages_generated = await run_plugin_generators(
        params=params,
        pages=ctx.pages,
    )
    ctx.pages.extend(new_pages)
    ctx.pages_generated += pages_generated


async def generate_codemap_pages(
    generator: WikiGenerator,
    ctx: _GenerationContext,
) -> None:
    """Generate codemap pages for auto-discovered entry points."""
    assert generator._repo_path is not None, (
        "Repository path must be set before generating codemaps"
    )

    params = _build_pipeline_params(generator, ctx)

    (
        codemap_pages,
        ctx.pages_generated,
        ctx.pages_skipped,
    ) = await generate_codemap_pages_phase(
        ctx=params.ctx,
        pages=ctx.pages,
        pages_generated=ctx.pages_generated,
        pages_skipped=ctx.pages_skipped,
        progress=generator._progress,
        params=params,
    )
    ctx.pages.extend(codemap_pages)


async def apply_cross_linking_phase(
    generator: WikiGenerator,
    ctx: _GenerationContext,
) -> list[WikiPage]:
    """Apply cross-links, source refs, and see-also sections to pages."""
    params = _build_pipeline_params(generator, ctx)
    return await apply_cross_linking(
        pages=ctx.pages,
        entity_registry=generator.entity_registry,
        relationship_analyzer=generator.relationship_analyzer,
        params=params,
    )


async def generate_search_and_toc_phase(
    generator: WikiGenerator,
    ctx: _GenerationContext,
) -> None:
    """Generate search index and table of contents."""
    await generate_search_and_toc(
        pages=ctx.pages,
        index_status=ctx.index_status,
        vector_store=generator.vector_store,
        wiki_path=generator.wiki_path,
        progress_callback=ctx.progress_callback,
    )


def build_wiki_status_from_context(
    generator: WikiGenerator,
    ctx: _GenerationContext,
) -> WikiGenerationStatus:
    """Build the wiki generation status object."""
    return build_wiki_status(
        pages=ctx.pages,
        index_status=ctx.index_status,
        page_statuses=generator.status_manager.page_statuses,
    )


async def generate_freshness_and_finalize_phase(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    wiki_status: WikiGenerationStatus,
) -> None:
    """Generate freshness report and finalize wiki status."""
    assert generator._repo_path is not None, (
        "Repository path must be set before generating wiki"
    )

    params = _build_pipeline_params(generator, ctx)

    freshness_page, ctx.pages_generated = await generate_freshness_and_finalize(
        params=params,
        pages=ctx.pages,
        pages_generated=ctx.pages_generated,
        pages_skipped=ctx.pages_skipped,
        wiki_status=wiki_status,
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
        # Skip logging if stats are not properly available
        pass


# ---------------------------------------------------------------------------
# Top-level pipeline orchestrator
# ---------------------------------------------------------------------------


async def _emit_wiki_complete_event(
    index_status: IndexStatus,
    ctx: Any,
) -> None:
    """Emit the WIKI_COMPLETE event with page statistics."""
    emitter = get_event_emitter()
    await emitter.emit(
        EventType.WIKI_COMPLETE,
        {
            "repo_path": index_status.repo_path,
            "total_pages": len(ctx.pages),
            "pages_generated": ctx.pages_generated,
            "pages_skipped": ctx.pages_skipped,
        },
    )


def _log_generation_summary(generator: WikiGenerator, ctx: Any) -> None:
    """Log completion stats, warnings, cache stats, and finalize."""
    logger.info(
        "Wiki generation complete: %d pages generated, "
        "%d pages unchanged, %d total pages",
        ctx.pages_generated,
        ctx.pages_skipped,
        len(ctx.pages),
    )
    if ctx.warnings:
        logger.warning(
            "Wiki generation completed with %s warning(s)",
            len(ctx.warnings),
        )
        for warning in ctx.warnings:
            logger.warning("  - %s", warning)
            generator._progress._log(f"WARNING: {warning}")
    generator._log_cache_stats()
    summary = generator._progress.finalize(success=True, warnings=ctx.warnings)
    logger.info(summary)


async def _init_pipeline_context(
    generator: WikiGenerator,
    index_status: IndexStatus,
    full_rebuild: bool,
    progress_callback: ProgressCallback | None,
) -> _GenerationContext:
    """Emit WIKI_START event and initialise the generation context."""
    emitter = get_event_emitter()
    await emitter.emit(
        EventType.WIKI_START,
        {
            "repo_path": index_status.repo_path,
            "full_rebuild": full_rebuild,
            "total_files": index_status.total_files,
        },
    )
    ctx = await init_generation_context(generator, index_status, full_rebuild)
    ctx.progress_callback = progress_callback
    return ctx


async def _generate_content_pages(
    generator: WikiGenerator,
    ctx: _GenerationContext,
    max_file_pages: int | None,
) -> None:
    """Run module and file documentation phases concurrently (phases 3+4)."""
    shared_semaphore = asyncio.Semaphore(generator.config.effective_llm_concurrency)
    await asyncio.gather(
        generate_module_pages(generator, ctx, semaphore=shared_semaphore),
        generate_file_pages(
            generator,
            ctx,
            max_files=max_file_pages,
            semaphore=shared_semaphore,
        ),
    )


async def _finalize_pipeline(
    generator: WikiGenerator,
    ctx: _GenerationContext,
) -> None:
    """Cross-link, build search/TOC, freshness report, and emit completion."""
    # Phase 8: cross-links and see-also sections
    ctx.pages = await apply_cross_linking_phase(generator, ctx)

    # Phase 9: search index and TOC
    await generate_search_and_toc_phase(generator, ctx)

    # Phase 10: freshness report and finalize
    wiki_status = build_wiki_status_from_context(generator, ctx)
    await generate_freshness_and_finalize_phase(generator, ctx, wiki_status)

    _log_generation_summary(generator, ctx)
    await _emit_wiki_complete_event(ctx.index_status, ctx)


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
        "Full rebuild: %s, Total files: %s",
        full_rebuild,
        index_status.total_files,
    )

    ctx = await _init_pipeline_context(
        generator, index_status, full_rebuild, progress_callback
    )

    # Phase 1: summary pages (overview, architecture)
    await generate_summary_pages(ctx, generator)

    # Phase 2: import analysis for relationship tracking
    await analyze_imports_for_relationships(generator)

    # Phase 3+4: module and file documentation (concurrent)
    await _generate_content_pages(generator, ctx, max_file_pages)

    # Phase 5: dependencies page
    await generate_dependencies_page_phase(ctx, generator)

    # Phase 6: changelog
    await generate_changelog_phase(ctx, generator)

    # Phase 7: auxiliary pages + plugins + codemap
    await _phases_generate_auxiliary_pages(ctx, generator)
    await run_wiki_plugin_generators(generator, ctx)
    await generate_codemap_pages(generator, ctx)

    # Phases 8-10: cross-links, search/TOC, freshness, and completion
    await _finalize_pipeline(generator, ctx)

    return WikiStructure(root=str(generator.wiki_path), pages=ctx.pages)
