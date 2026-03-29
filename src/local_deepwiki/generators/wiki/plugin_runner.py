"""Plugin generator orchestration for wiki generation.

Handles sorting generators by dependency order and running registered
wiki generator plugins.
"""

from __future__ import annotations

from operator import attrgetter
from typing import TYPE_CHECKING

from local_deepwiki.logging import get_logger
from local_deepwiki.plugins.registry import get_plugin_registry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from local_deepwiki.config import Config
    from local_deepwiki.core.vectorstore import VectorStore
    from local_deepwiki.generators.wiki.status import WikiStatusManager
    from local_deepwiki.models import IndexStatus, ProgressCallback, WikiPage
    from local_deepwiki.plugins.base import WikiGeneratorPlugin
    from local_deepwiki.providers.base import LLMProvider

logger = get_logger(__name__)


def _build_dependency_graph(
    generators: list[WikiGeneratorPlugin],
    available_names: set[str],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Build in-degree and dependents mappings for Kahn's topological sort."""
    in_degree: dict[str, int] = {g.generator_name: 0 for g in generators}
    dependents: dict[str, list[str]] = {g.generator_name: [] for g in generators}
    for generator in generators:
        for dep in generator.run_after:
            if dep in available_names:
                in_degree[generator.generator_name] += 1
                dependents[dep].append(generator.generator_name)
    return in_degree, dependents


def _kahn_topological_sort(
    generators: list[WikiGeneratorPlugin],
    by_name: dict[str, WikiGeneratorPlugin],
    in_degree: dict[str, int],
    dependents: dict[str, list[str]],
) -> list[WikiGeneratorPlugin]:
    """Run Kahn's algorithm to produce a priority-respecting topological ordering."""
    ready = sorted(
        [g for g in generators if in_degree[g.generator_name] == 0],
        key=attrgetter("priority"),
        reverse=True,
    )
    sorted_generators: list[WikiGeneratorPlugin] = []
    while ready:
        current = ready.pop(0)
        sorted_generators.append(current)
        for dep_name in dependents[current.generator_name]:
            in_degree[dep_name] -= 1
            if in_degree[dep_name] == 0:
                dep_gen = by_name[dep_name]
                insert_idx = 0
                for i, g in enumerate(ready):
                    if dep_gen.priority > g.priority:
                        insert_idx = i
                        break
                    insert_idx = i + 1
                ready.insert(insert_idx, dep_gen)
    return sorted_generators


def sort_generators_by_dependencies(
    generators: list[WikiGeneratorPlugin],
) -> list[WikiGeneratorPlugin]:
    """Sort generators respecting run_after dependencies with validation.

    Uses topological sort to ensure generators run after their dependencies.
    Validates that all dependencies exist and warns about missing ones.

    Args:
        generators: List of generator plugins to sort.

    Returns:
        Sorted list of generators respecting dependencies.
    """
    if not generators:
        return generators

    by_name: dict[str, WikiGeneratorPlugin] = {g.generator_name: g for g in generators}
    available_names = set(by_name.keys())

    # Warn about missing dependencies
    for generator in generators:
        missing_deps = set(generator.run_after) - available_names
        if missing_deps:
            logger.debug(
                "Wiki generator '%s' has missing dependencies: %s. "
                "These generators are not registered and will be skipped.",
                generator.generator_name,
                missing_deps,
            )

    in_degree, dependents = _build_dependency_graph(generators, available_names)
    sorted_generators = _kahn_topological_sort(
        generators, by_name, in_degree, dependents
    )

    if len(sorted_generators) != len(generators):
        unresolved = [
            g.generator_name for g in generators if g not in sorted_generators
        ]
        logger.error(
            "Circular dependency detected in wiki generators: %s. "
            "These generators will not run.",
            unresolved,
        )

    return sorted_generators


async def run_plugin_generators(
    *,
    pages: list[WikiPage],
    all_source_files: list[str],
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    config: Config,
    wiki_path: Path,
    status_manager: WikiStatusManager,
    write_callback: Callable[[WikiPage], Awaitable[None]],
    progress_callback: ProgressCallback | None,
) -> tuple[list[WikiPage], int]:
    """Run registered wiki generator plugins.

    Args:
        pages: Current list of wiki pages (will not be mutated).
        all_source_files: List of all source file paths.
        index_status: Index status.
        vector_store: Vector store for code search.
        llm: LLM provider instance.
        config: Configuration object.
        wiki_path: Path to wiki output directory.
        status_manager: Wiki status manager for tracking.
        write_callback: Async callback to write pages to disk.
        progress_callback: Optional progress callback.

    Returns:
        Tuple of (new_pages, pages_generated_count).
    """
    registry = get_plugin_registry()
    generators: list[WikiGeneratorPlugin] = list(registry.wiki_generators.values())

    if not generators:
        return [], 0

    # Validate and sort generators respecting run_after dependencies
    generators = sort_generators_by_dependencies(generators)

    logger.info("Running %s wiki generator plugin(s)", len(generators))

    # Build context dict for plugins
    plugin_context: dict[str, object] = {
        "vector_store": vector_store,
        "llm": llm,
        "config": config,
        "existing_pages": list(pages),
    }

    new_pages, pages_generated = await _execute_plugin_generators(
        generators=generators,
        pages=pages,
        index_status=index_status,
        wiki_path=wiki_path,
        plugin_context=plugin_context,
        all_source_files=all_source_files,
        status_manager=status_manager,
        write_callback=write_callback,
    )
    return new_pages, pages_generated


async def _execute_plugin_generators(
    *,
    generators: list[WikiGeneratorPlugin],
    pages: list[WikiPage],
    index_status: IndexStatus,
    wiki_path: Path,
    plugin_context: dict[str, object],
    all_source_files: list[str],
    status_manager: WikiStatusManager,
    write_callback: Callable[[WikiPage], Awaitable[None]],
) -> tuple[list[WikiPage], int]:
    """Execute each plugin generator in order, collecting generated pages."""
    new_pages: list[WikiPage] = []
    pages_generated = 0

    for generator in generators:
        try:
            logger.debug("Running wiki generator plugin: %s", generator.generator_name)
            result = await generator.generate(
                index_status=index_status,
                wiki_path=wiki_path,
                context=plugin_context,
            )
            for page in result.pages:
                new_pages.append(page)
                status_manager.record_page_status(page, all_source_files)
                await write_callback(page)
                pages_generated += 1
            # Update existing_pages in context for subsequent plugins
            plugin_context["existing_pages"] = list(pages) + list(new_pages)
            logger.debug(
                "Plugin '%s' generated %d page(s)",
                generator.generator_name,
                len(result.pages),
            )
        except Exception as e:  # noqa: BLE001 — plugin isolation
            logger.debug(
                "Wiki generator plugin '%s' failed: %s", generator.generator_name, e
            )

    return new_pages, pages_generated
