"""Extracted wiki generation phases.

This module contains standalone async functions that implement specific phases
of wiki generation, extracted from ``WikiGenerator`` methods to keep the
orchestrator file focused on the public API.

Functions in this module use late imports from ``local_deepwiki.generators.wiki``
for symbols that tests patch at that location (e.g. ``generate_inheritance_page``).
This ensures test patches remain effective without modifying any test files.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    IndexStatus,
    ProgressCallback,
    WikiPage,
)

if TYPE_CHECKING:
    from local_deepwiki.generators.wiki import WikiGenerator, _GenerationContext
    from local_deepwiki.generators.wiki_status import WikiStatusManager

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
    pages_to_generate = [
        (
            "index.md",
            "Generating overview",
            0,
            lambda: generator._generate_overview(index_status),
        ),
        (
            "architecture.md",
            "Generating architecture docs",
            1,
            lambda: generator._generate_architecture(index_status),
        ),
    ]
    for page_path, label, step, gen_fn in pages_to_generate:
        if progress_callback:
            progress_callback(label, step, 14)
        page, generated = await _generate_or_load_summary_page(
            ctx=ctx,
            page_path=page_path,
            generator=gen_fn,
            index_status=index_status,
            status_manager=generator.status_manager,
            write_callback=generator._write_page,
        )
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


async def generate_auxiliary_pages(
    ctx: _GenerationContext,
    generator: WikiGenerator,
    index_status: IndexStatus,
    progress_callback: ProgressCallback | None,
) -> None:
    """Generate auxiliary pages: inheritance, glossary, coverage, dependency graph.

    All four pages are generated concurrently with ``asyncio.gather``
    since they are independent of each other.  Uses structural
    fingerprinting so content-only changes skip these pages.

    Generator functions are imported late from ``local_deepwiki.generators.wiki``
    so that test patches applied at that location remain effective.

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
    import asyncio

    # Late imports so test patches at ``local_deepwiki.generators.wiki.*`` are
    # picked up at call time rather than module-load time.
    from local_deepwiki.generators import wiki as _wiki_mod

    _generate_inheritance_page = _wiki_mod.generate_inheritance_page
    _generate_glossary_page = _wiki_mod.generate_glossary_page
    _generate_coverage_page = _wiki_mod.generate_coverage_page
    _generate_dependency_graph_page = _wiki_mod.generate_dependency_graph_page

    if progress_callback:
        progress_callback("Generating auxiliary pages", 6, 14)

    status_manager = generator.status_manager

    aux_pages = [
        ("inheritance.md", "Class Inheritance"),
        ("glossary.md", "Glossary"),
        ("coverage.md", "Documentation Coverage"),
        ("dependency-graph.md", "Dependency Graph"),
    ]

    if await _try_load_cached_auxiliary_pages(
        ctx, aux_pages, index_status, status_manager
    ):
        return

    async def _safe_dependency_graph() -> str | None:
        """Wrapper that catches dependency graph errors."""
        try:
            return await _generate_dependency_graph_page(
                index_status=index_status,
                vector_store=generator.vector_store,
                show_external=True,
                max_external=10,
                wiki_base_path="files/",
            )
        except Exception as e:  # noqa: BLE001 — generator isolation: auxiliary page failure must not abort wiki build
            logger.debug("Failed to generate dependency graph: %s", e)
            ctx.warnings.append(f"Dependency graph generation failed: {e}")
            return None

    contents = await asyncio.gather(
        _generate_inheritance_page(index_status, generator.vector_store),
        _generate_glossary_page(index_status, generator.vector_store),
        _generate_coverage_page(index_status, generator.vector_store),
        _safe_dependency_graph(),
    )

    for (page_path, title), content in zip(aux_pages, contents):
        await _add_auxiliary_page(
            ctx,
            content,
            page_path,
            title,
            index_status,
            status_manager,
            generator._write_page,
        )
