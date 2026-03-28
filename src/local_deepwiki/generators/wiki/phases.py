"""Extracted wiki generation phases.

This module contains standalone async functions that implement specific phases
of wiki generation, extracted from ``WikiGenerator`` methods to keep the
orchestrator file focused on the public API.

Functions in this module use late imports from ``local_deepwiki.generators.wiki``
for symbols that tests patch at that location (e.g. ``generate_inheritance_page``).
This ensures test patches remain effective without modifying any test files.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    IndexStatus,
    ProgressCallback,
    WikiPage,
)

if TYPE_CHECKING:
    from local_deepwiki.generators.wiki.generator import (
        WikiGenerator,
        _GenerationContext,
    )
    from local_deepwiki.generators.wiki.status import WikiStatusManager

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Phase 1 helpers: summary pages (overview + architecture)
# ---------------------------------------------------------------------------


async def _generate_or_load_page(
    ctx: _GenerationContext,
    page_path: str,
    generator: Callable[[], Awaitable[WikiPage]],
    source_files: list[str],
    status_manager: WikiStatusManager,
    write_callback: Callable[[WikiPage], Awaitable[None]],
) -> tuple[WikiPage, bool]:
    """Generate a page or load from cache if unchanged.

    Parameters
    ----------
    ctx:
        Mutable generation context.
    page_path:
        Wiki-relative path of the page (e.g. ``"index.md"``).
    generator:
        Async callable that produces the page when generation is needed.
    source_files:
        Source files that the page depends on.
    status_manager:
        ``WikiStatusManager`` instance for incremental tracking.
    write_callback:
        Async callable to persist the page to disk.
    """
    if ctx.full_rebuild or status_manager.needs_regeneration(page_path, source_files):
        page = await generator()
        was_generated = True
    else:
        existing_page = await status_manager.load_existing_page(page_path)
        if existing_page is None:
            page = await generator()
            was_generated = True
        else:
            page = existing_page
            was_generated = False

    status_manager.record_page_status(page, source_files)
    await write_callback(page)

    emitter = get_event_emitter()
    await emitter.emit(
        EventType.WIKI_PAGE_COMPLETE,
        {
            "page_path": page.path,
            "page_title": page.title,
            "was_generated": was_generated,
        },
    )

    return page, was_generated


async def _generate_or_load_summary_page(
    ctx: _GenerationContext,
    page_path: str,
    generator: Callable[[], Awaitable[WikiPage]],
    index_status: IndexStatus,
    status_manager: WikiStatusManager,
    write_callback: Callable[[WikiPage], Awaitable[None]],
) -> tuple[WikiPage, bool]:
    """Generate a summary page or load from cache using structural fingerprint.

    Parameters
    ----------
    ctx:
        Mutable generation context.
    page_path:
        Wiki-relative path of the page.
    generator:
        Async callable that produces the page when generation is needed.
    index_status:
        Current repository index status.
    status_manager:
        ``WikiStatusManager`` instance for incremental tracking.
    write_callback:
        Async callable to persist the page to disk.
    """
    if ctx.full_rebuild or status_manager.needs_regeneration_structural(
        page_path, index_status
    ):
        page = await generator()
        was_generated = True
    else:
        existing_page = await status_manager.load_existing_page(page_path)
        if existing_page is None:
            page = await generator()
            was_generated = True
        else:
            page = existing_page
            was_generated = False

    status_manager.record_summary_page_status(page, ctx.all_source_files, index_status)
    await write_callback(page)

    emitter = get_event_emitter()
    await emitter.emit(
        EventType.WIKI_PAGE_COMPLETE,
        {
            "page_path": page.path,
            "page_title": page.title,
            "was_generated": was_generated,
        },
    )

    return page, was_generated


async def generate_summary_pages(
    ctx: _GenerationContext,
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate overview and architecture pages (Phase 1).

    Parameters
    ----------
    ctx:
        Mutable generation context.
    generator:
        ``WikiGenerator`` instance providing ``_generate_overview``,
        ``_generate_architecture``, ``status_manager``, and ``_write_page``.
    index_status:
        Current repository index status.
    progress_callback:
        Optional progress callback.
    """
    if progress_callback:
        progress_callback("Generating overview and architecture", 0, 14)

    # Generate overview and architecture pages concurrently — they are independent
    results = await asyncio.gather(
        _generate_or_load_summary_page(
            ctx=ctx,
            page_path="index.md",
            generator=lambda: generator._generate_overview(index_status),
            index_status=index_status,
            status_manager=generator.status_manager,
            write_callback=generator._write_page,
        ),
        _generate_or_load_summary_page(
            ctx=ctx,
            page_path="architecture.md",
            generator=lambda: generator._generate_architecture(index_status),
            index_status=index_status,
            status_manager=generator.status_manager,
            write_callback=generator._write_page,
        ),
    )

    for page, generated in results:
        ctx.pages.append(page)
        if generated:
            ctx.pages_generated += 1
        else:
            ctx.pages_skipped += 1


# ---------------------------------------------------------------------------
# Phase 5: dependencies page
# ---------------------------------------------------------------------------


async def generate_dependencies_page_phase(
    ctx: _GenerationContext,
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate the dependencies documentation page (Phase 5).

    Parameters
    ----------
    ctx:
        Mutable generation context.
    generator:
        ``WikiGenerator`` instance.
    index_status:
        Current repository index status.
    progress_callback:
        Optional progress callback.
    """
    if progress_callback:
        progress_callback("Generating dependencies", 4, 14)

    deps_path = "dependencies.md"
    status_manager = generator.status_manager

    if ctx.full_rebuild or status_manager.needs_regeneration(
        deps_path, ctx.all_source_files
    ):
        deps_page, deps_source_files = await generator._generate_dependencies(
            index_status
        )
        ctx.pages_generated += 1
    else:
        existing_deps_page = await status_manager.load_existing_page(deps_path)
        if existing_deps_page is None:
            deps_page, deps_source_files = await generator._generate_dependencies(
                index_status
            )
            ctx.pages_generated += 1
        else:
            deps_page = existing_deps_page
            prev_status = status_manager.page_statuses.get(deps_path) or (
                status_manager.previous_status.pages.get(deps_path)
                if status_manager.previous_status
                else None
            )
            deps_source_files = (
                prev_status.source_files if prev_status else ctx.all_source_files
            )
            ctx.pages_skipped += 1

    ctx.pages.append(deps_page)
    status_manager.record_page_status(deps_page, deps_source_files)
    await generator._write_page(deps_page)


# ---------------------------------------------------------------------------
# Phase 6: changelog page
# ---------------------------------------------------------------------------


async def generate_changelog_phase(
    ctx: _GenerationContext,
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate changelog page from git history (Phase 6).

    Parameters
    ----------
    ctx:
        Mutable generation context.
    generator:
        ``WikiGenerator`` instance.
    index_status:
        Current repository index status.
    progress_callback:
        Optional progress callback.
    """
    if progress_callback:
        progress_callback("Generating changelog", 5, 14)

    page_path = "changelog.md"
    status_manager = generator.status_manager

    if not ctx.full_rebuild and not status_manager.needs_regeneration_structural(
        page_path, index_status
    ):
        existing_page = await status_manager.load_existing_page(page_path)
        if existing_page is not None:
            ctx.pages.append(existing_page)
            status_manager.record_summary_page_status(
                existing_page, ctx.all_source_files, index_status
            )
            ctx.pages_skipped += 1
            return

    changelog_page = await generator._generate_changelog()
    if changelog_page:
        ctx.pages.append(changelog_page)
        status_manager.record_summary_page_status(
            changelog_page, ctx.all_source_files, index_status
        )
        await generator._write_page(changelog_page)
        ctx.pages_generated += 1


# ---------------------------------------------------------------------------
# Phase 7: auxiliary pages (inheritance, glossary, coverage, dependency graph)
# ---------------------------------------------------------------------------


async def _add_auxiliary_page(
    ctx: _GenerationContext,
    content: str | None,
    path: str,
    title: str,
    index_status: IndexStatus,
    status_manager: WikiStatusManager,
    write_callback: Callable[[WikiPage], Awaitable[None]],
) -> None:
    """Record and write an auxiliary page if content was generated."""
    if not content:
        return
    page = WikiPage(path=path, title=title, content=content, generated_at=time.time())
    ctx.pages.append(page)
    status_manager.record_summary_page_status(page, ctx.all_source_files, index_status)
    await write_callback(page)
    ctx.pages_generated += 1


async def _try_load_cached_auxiliary_pages(
    ctx: _GenerationContext,
    aux_pages: list[tuple[str, str]],
    index_status: IndexStatus,
    status_manager: WikiStatusManager,
) -> bool:
    """Try to load all auxiliary pages from cache.

    Returns True if all pages loaded successfully; False (with rollback)
    if any page was missing.
    """
    if ctx.full_rebuild or status_manager.needs_regeneration_structural(
        aux_pages[0][0], index_status
    ):
        return False

    for page_path, _title in aux_pages:
        existing = await status_manager.load_existing_page(page_path)
        if existing is None:
            loaded_paths = {
                pp for pp, _ in aux_pages if pp in status_manager.page_statuses
            }
            ctx.pages = [p for p in ctx.pages if p.path not in loaded_paths]
            for pp in loaded_paths:
                status_manager.page_statuses.pop(pp, None)
            ctx.pages_skipped -= len(loaded_paths)
            return False

        ctx.pages.append(existing)
        status_manager.record_summary_page_status(
            existing, ctx.all_source_files, index_status
        )
        ctx.pages_skipped += 1

    return True


async def _safe_dependency_graph(
    index_status: IndexStatus,
    vector_store: object,
    generate_fn: Callable[..., Awaitable[str | None]],
    warnings: list[str],
) -> str | None:
    """Wrapper that catches dependency graph errors."""
    try:
        return await generate_fn(
            index_status=index_status,
            vector_store=vector_store,
            show_external=True,
            max_external=10,
            wiki_base_path="files/",
        )
    except Exception as e:  # noqa: BLE001 — generator isolation: auxiliary page failure must not abort wiki build
        logger.debug("Failed to generate dependency graph: %s", e)
        warnings.append(f"Dependency graph generation failed: {e}")
        return None


async def _safe_executor_page(
    repo_path_str: str,
    analyze_fn_path: str,
    render_fn_path: str,
    label: str,
    warnings: list[str],
    *,
    pass_project_name: bool = False,
) -> str | None:
    """Run a sync analysis in an executor and render the result page.

    Parameters
    ----------
    repo_path_str:
        Repository path string from ``index_status.repo_path``.
    analyze_fn_path:
        Dotted import path for the analysis function (e.g.
        ``"local_deepwiki.generators.analysis.hotspots.analyze_hotspots"``).
    render_fn_path:
        Dotted import path for the page-rendering function.
    label:
        Human-readable label used in warning messages.
    warnings:
        List to append warning messages to on failure.
    pass_project_name:
        If True, pass ``project_name`` as the second argument to the analysis
        function (used by ``analyze_architecture_health``).
    """
    import importlib
    from pathlib import Path as _Path

    try:
        # Dynamically import analysis and render functions
        analyze_mod_path, analyze_fn_name = analyze_fn_path.rsplit(".", 1)
        render_mod_path, render_fn_name = render_fn_path.rsplit(".", 1)
        analyze_fn = getattr(importlib.import_module(analyze_mod_path), analyze_fn_name)
        render_fn = getattr(importlib.import_module(render_mod_path), render_fn_name)

        repo_path = _Path(repo_path_str)
        if pass_project_name:
            data = await asyncio.get_event_loop().run_in_executor(
                None, analyze_fn, repo_path, repo_path.name
            )
        else:
            data = await asyncio.get_event_loop().run_in_executor(
                None, analyze_fn, repo_path
            )
        return render_fn(data)
    except Exception as e:  # noqa: BLE001 — generator isolation: auxiliary page failure must not abort wiki build
        logger.debug("Failed to generate %s page: %s", label, e)
        warnings.append(f"{label} page generation failed: {e}")
        return None


# Specs for executor-based auxiliary pages: (analyze_path, render_path, label, pass_project_name)
_EXECUTOR_PAGE_SPECS: list[tuple[str, str, str, bool]] = [
    (
        "local_deepwiki.generators.analysis.architecture_health.analyze_architecture_health",
        "local_deepwiki.generators.analysis.health_page.generate_health_page",
        "Architecture health",
        True,
    ),
    (
        "local_deepwiki.generators.analysis.hotspots.analyze_hotspots",
        "local_deepwiki.generators.analysis.hotspots_page.generate_hotspots_page",
        "Complexity hotspots",
        False,
    ),
    (
        "local_deepwiki.generators.analysis.design_smells.analyze_design_smells",
        "local_deepwiki.generators.analysis.smells_page.generate_smells_page",
        "Design smells",
        False,
    ),
    (
        "local_deepwiki.generators.analysis.coupling.analyze_coupling_metrics",
        "local_deepwiki.generators.analysis.coupling_page.generate_coupling_page",
        "Coupling metrics",
        False,
    ),
]

# Metadata for all auxiliary pages (path, title) — order must match the gather call
# in ``_gather_auxiliary_contents``.
_AUX_PAGE_METADATA: list[tuple[str, str]] = [
    ("inheritance.md", "Class Inheritance"),
    ("glossary.md", "Glossary"),
    ("coverage.md", "Documentation Coverage"),
    ("dependency-graph.md", "Dependency Graph"),
    ("health.md", "Architecture Health"),
    ("hotspots.md", "Complexity Hotspots"),
    ("smells.md", "Design Smells"),
    ("coupling.md", "Coupling Metrics"),
]


async def _gather_auxiliary_contents(
    index_status: IndexStatus,
    vector_store: Any,
    warnings: list[str],
) -> list[str | None]:
    """Run all auxiliary page generators concurrently.

    Late-imports the wiki generator module so that test patches remain effective.

    Returns a tuple of content strings (or None) aligned with ``_AUX_PAGE_METADATA``.
    """
    from local_deepwiki.generators.wiki import generator as _wiki_gen

    repo_path_str = index_status.repo_path

    return await asyncio.gather(
        _wiki_gen.generate_inheritance_page(index_status, vector_store),
        _wiki_gen.generate_glossary_page(index_status, vector_store),
        _wiki_gen.generate_coverage_page(index_status, vector_store),
        _safe_dependency_graph(
            index_status,
            vector_store,
            _wiki_gen.generate_dependency_graph_page,
            warnings,
        ),
        *(
            _safe_executor_page(
                repo_path_str,
                analyze_path,
                render_path,
                label,
                warnings,
                pass_project_name=needs_name,
            )
            for analyze_path, render_path, label, needs_name in _EXECUTOR_PAGE_SPECS
        ),
    )


async def generate_auxiliary_pages(
    ctx: _GenerationContext,
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate auxiliary pages concurrently with structural fingerprinting.

    Parameters
    ----------
    ctx:
        Mutable generation context.
    generator:
        ``WikiGenerator`` instance.
    index_status:
        Current repository index status.
    progress_callback:
        Optional progress callback.
    """
    if progress_callback:
        progress_callback("Generating auxiliary pages", 6, 14)

    status_manager = generator.status_manager

    if await _try_load_cached_auxiliary_pages(
        ctx, _AUX_PAGE_METADATA, index_status, status_manager
    ):
        return

    contents = await _gather_auxiliary_contents(
        index_status,
        generator.vector_store,
        ctx.warnings,
    )

    for (page_path, title), content in zip(_AUX_PAGE_METADATA, contents):
        await _add_auxiliary_page(
            ctx,
            content,
            page_path,
            title,
            index_status,
            status_manager,
            generator._write_page,
        )

    # Generate onboarding guide (requires vector store + LLM)
    onboarding_page = await generate_onboarding_page(
        repo_path=Path(index_status.repo_path),
        wiki_path=generator.wiki_path,
        vector_store=generator.vector_store,
        llm=generator.llm,
        index_status=index_status,
        status_manager=status_manager,
        full_rebuild=ctx.full_rebuild,
    )
    if onboarding_page is not None:
        ctx.pages.append(onboarding_page)
        await generator._write_page(onboarding_page)
        ctx.pages_generated += 1


async def generate_onboarding_page(
    repo_path: Path,
    wiki_path: Path,
    vector_store: Any,
    llm: Any,
    index_status: IndexStatus | None = None,
    status_manager: Any | None = None,
    full_rebuild: bool = False,
) -> WikiPage | None:
    """Generate the rich onboarding page for the wiki.

    Returns a WikiPage if successful, None if generation fails.
    This is called during the auxiliary pages phase of wiki generation.
    """
    from local_deepwiki.generators.analysis.onboarding import generate_rich_onboarding

    page_path = "onboarding.md"

    try:
        result = await generate_rich_onboarding(
            repo_path=repo_path,
            vector_store=vector_store,
            llm=llm,
        )
        guide = result.get("guide", "")
        if not guide:
            return None

        return WikiPage(
            path=page_path,
            title="Developer Onboarding Guide",
            content=guide,
            generated_at=time.time(),
        )
    except Exception:
        logger.warning("Rich onboarding generation failed, skipping")
        return None
