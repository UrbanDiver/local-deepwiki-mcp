"""Standalone search post-processing functions.

These functions handle the post-retrieval stages of the search pipeline:
fuzzy re-ranking, path filtering, and "Did you mean?" suggestion generation.
They were previously embedded as methods on ``SearchEngine`` and are extracted
here to keep ``SearchEngine`` focused on orchestration.

``SearchEngine`` imports from here and delegates; external consumers should go
through ``SearchEngine`` or ``VectorStore``, not import from this module
directly.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from local_deepwiki.logging import get_logger
from local_deepwiki.models import SearchResult

if TYPE_CHECKING:
    from local_deepwiki.config import FuzzySearchConfig
    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper

logger = get_logger(__name__)


def apply_fuzzy_reranking(
    search_results: list[SearchResult],
    query: str,
    fuzzy_weight: float,
    *,
    use_fuzzy: bool,
    fuzzy_config: "FuzzySearchConfig",
) -> tuple[list[SearchResult], bool]:
    """Apply fuzzy re-ranking if explicitly requested or auto-enabled.

    When results are of poor quality (all scores below the auto-fuzzy threshold)
    and ``enable_auto_fuzzy`` is on in the config, fuzzy matching is applied
    automatically even if the caller did not request it.

    Args:
        search_results: Current search results from the main pipeline.
        query: Original search query.
        fuzzy_weight: Weight given to the fuzzy score during re-ranking.
        use_fuzzy: Whether the caller explicitly requested fuzzy matching.
        fuzzy_config: Fuzzy search configuration.

    Returns:
        Tuple of (reranked_results, auto_fuzzy_enabled).
        ``auto_fuzzy_enabled`` is True when fuzzy was turned on automatically.
    """
    from local_deepwiki.core.fuzzy_search import (
        extract_highlights,
        rerank_with_fuzzy,
        should_auto_enable_fuzzy,
    )

    auto_fuzzy_enabled = False

    if (
        fuzzy_config.enable_auto_fuzzy
        and not use_fuzzy
        and should_auto_enable_fuzzy(search_results, fuzzy_config.auto_fuzzy_threshold)
    ):
        auto_fuzzy_enabled = True
        logger.debug(
            "Auto-enabling fuzzy search due to poor results (best score below %s)",
            fuzzy_config.auto_fuzzy_threshold,
        )

    if (use_fuzzy or auto_fuzzy_enabled) and search_results:
        search_results = rerank_with_fuzzy(search_results, query, fuzzy_weight)
        for result in search_results:
            result.highlights = extract_highlights(result.chunk.content, query)

    return search_results, auto_fuzzy_enabled


def apply_post_filters(
    results: list[SearchResult],
    path_pattern: str | None,
) -> list[SearchResult]:
    """Apply post-retrieval filters (path pattern) to search results.

    Args:
        results: Search results to filter.
        path_pattern: Optional glob-style pattern to match against file paths.
            Results whose file path does not match are removed.

    Returns:
        Filtered list of ``SearchResult`` objects.
    """
    if not path_pattern:
        return results
    from local_deepwiki.core.fuzzy_search import filter_by_path

    return filter_by_path(results, path_pattern)


async def generate_suggestions(
    query: str,
    search_results: list[SearchResult],
    store: Any,
    fuzzy_config: "FuzzySearchConfig",
    get_fuzzy_helper: Callable[[Any], Coroutine[Any, Any, "FuzzySearchHelper"]],
) -> list[str] | None:
    """Generate 'Did you mean?' suggestions for poor-quality results.

    Suggestions are only generated when ``enable_auto_fuzzy`` is True in the
    config and results look poor (below ``auto_fuzzy_threshold``).

    Args:
        query: Original search query.
        search_results: Current search results to evaluate quality.
        store: The ``VectorStore`` instance (passed to the fuzzy helper).
        fuzzy_config: Fuzzy search configuration.
        get_fuzzy_helper: Async callable that returns a ``FuzzySearchHelper``
            for the given ``store``.

    Returns:
        List of suggestion strings, or None if no suggestions are generated.
    """
    from local_deepwiki.core.fuzzy_search import should_auto_enable_fuzzy

    if not (
        fuzzy_config.enable_auto_fuzzy
        and should_auto_enable_fuzzy(search_results, fuzzy_config.auto_fuzzy_threshold)
    ):
        return None

    try:
        fuzzy_helper = await get_fuzzy_helper(store)
        suggestions = fuzzy_helper.generate_suggestions(
            query,
            search_results,
            threshold=fuzzy_config.suggestion_threshold,
            max_suggestions=fuzzy_config.max_suggestions,
        )
        if suggestions:
            logger.debug("Generated suggestions: %s", suggestions)
        return suggestions or None
    except (RuntimeError, OSError, ValueError, KeyError) as e:
        logger.warning("Failed to generate suggestions: %s", e)
        return None


async def attach_suggestions(
    query: str,
    search_results: list[SearchResult],
    store: Any,
    fuzzy_config: "FuzzySearchConfig",
    get_fuzzy_helper: Callable[[Any], Coroutine[Any, Any, "FuzzySearchHelper"]],
) -> list[SearchResult]:
    """Generate and attach 'Did you mean?' suggestions to the first result.

    If suggestions are generated, a new ``SearchResult`` is created for the
    first result with the suggestions attached (immutable replacement), and
    returned alongside the remaining results unchanged.

    Args:
        query: Original search query.
        search_results: Current search results.
        store: The ``VectorStore`` instance.
        fuzzy_config: Fuzzy search configuration.
        get_fuzzy_helper: Async callable that returns a ``FuzzySearchHelper``.

    Returns:
        Updated list of ``SearchResult`` objects (first result may carry
        ``suggestions``).
    """
    suggestions = await generate_suggestions(
        query, search_results, store, fuzzy_config, get_fuzzy_helper
    )
    if not suggestions:
        return search_results
    if search_results:
        first = search_results[0]
        return [
            SearchResult(
                chunk=first.chunk,
                score=first.score,
                highlights=first.highlights,
                suggestions=suggestions,
            ),
            *search_results[1:],
        ]
    logger.debug("No results but have suggestions: %s", suggestions)
    return search_results
