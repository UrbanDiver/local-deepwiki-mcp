"""Plugin generator orchestration for wiki generation.

Handles sorting generators by dependency order and running registered
wiki generator plugins.
"""

from __future__ import annotations

from operator import attrgetter
from typing import TYPE_CHECKING

from local_deepwiki.generators.wiki.pipeline_params import WikiPipelineParams
from local_deepwiki.logging import get_logger
from local_deepwiki.plugins.registry import get_plugin_registry

if TYPE_CHECKING:
    from local_deepwiki.models import WikiPage
    from local_deepwiki.plugins.base import WikiGeneratorPlugin

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
    params: WikiPipelineParams,
    pages: list[WikiPage],
) -> tuple[list[WikiPage], int]:
    """Run registered wiki generator plugins.

    Args:
        params: Pipeline parameter bundle with context, callbacks, and source files.
        pages: Current list of wiki pages (will not be mutated).

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
        "vector_store": params.ctx.vector_store,
        "llm": params.ctx.llm,
        "config": params.ctx.config,
        "existing_pages": list(pages),
    }

    new_pages, pages_generated = await _execute_plugin_generators(
        generators=generators,
        pages=pages,
        params=params,
        plugin_context=plugin_context,
    )
    return new_pages, pages_generated


async def _execute_plugin_generators(
    *,
    generators: list[WikiGeneratorPlugin],
    pages: list[WikiPage],
    params: WikiPipelineParams,
    plugin_context: dict[str, object],
) -> tuple[list[WikiPage], int]:
    """Execute each plugin generator in order, collecting generated pages."""
    new_pages: list[WikiPage] = []
    pages_generated = 0
    all_source_files = params.all_source_files or []

    for generator in generators:
        try:
            logger.debug("Running wiki generator plugin: %s", generator.generator_name)
            result = await generator.generate(
                index_status=params.ctx.index_status,
                wiki_path=params.ctx.wiki_path,
                context=plugin_context,
            )
            for page in result.pages:
                new_pages.append(page)
                params.ctx.status_manager.record_page_status(page, all_source_files)
                await params.write_callback(page)
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
