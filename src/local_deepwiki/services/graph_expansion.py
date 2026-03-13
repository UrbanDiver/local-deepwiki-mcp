"""Graph-augmented search expansion helper.

Provides a single async function that optionally expands vector search results
with graph-discovered chunks when ``config.graph_rag.enabled`` is *True*.

The function is designed to be called from any service that does vector search,
keeping the wiring in one place rather than duplicated across handlers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.core.graph_rag.retriever import GraphAugmentedRetriever
from local_deepwiki.core.graph_rag.store import KnowledgeGraphStore
from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from local_deepwiki.config.models import Config
    from local_deepwiki.core.vectorstore.store import VectorStore
    from local_deepwiki.models.chunks import SearchResult

logger = get_logger(__name__)


async def expand_with_graph(
    search_results: list[SearchResult],
    vector_store: VectorStore,
    config: Config,
    repo_path: Path,
) -> list[SearchResult]:
    """Optionally expand *search_results* with graph-related chunks.

    When ``config.graph_rag.enabled`` is *False* (the default), the original
    results are returned unchanged with no extra work.

    When enabled, a :class:`~local_deepwiki.core.graph_rag.retriever.GraphAugmentedRetriever`
    traverses the knowledge graph and appends structurally related chunks
    (calls, imports, inheritance, etc.) scored below the vector results.

    The function is intentionally **non-blocking**: if graph expansion raises
    an exception, a warning is logged and the original results are returned
    so that the query pipeline continues without interruption.

    Args:
        search_results: Vector search results to expand.
        vector_store: The vector store used for the original search
            (needed by the retriever to fetch chunks by ID).
        config: Application configuration containing ``graph_rag`` settings.
        repo_path: Resolved path to the indexed repository (used to locate
            the LanceDB directory).

    Returns:
        The original results plus any graph-discovered results, or just the
        originals if graph expansion is disabled or fails.
    """
    if not config.graph_rag.enabled:
        return search_results

    if not search_results:
        return search_results

    try:
        graph_store = KnowledgeGraphStore(config.get_vector_db_path(repo_path))
        retriever = GraphAugmentedRetriever(
            graph_store=graph_store,
            vector_store=vector_store,
            config=config.graph_rag,
        )

        expanded = await retriever.expand_results(search_results)
        logger.debug(
            "Graph expansion: %d -> %d results",
            len(search_results),
            len(expanded),
        )
        return expanded
    except Exception:
        logger.warning(
            "Graph expansion failed, returning original results",
            exc_info=True,
        )
        return search_results
