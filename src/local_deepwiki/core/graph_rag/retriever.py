"""Graph-augmented retriever for expanding vector search with knowledge graph traversal.

Expands vector search results by traversing the knowledge graph to find
structurally related code (e.g., called functions, parent classes, imported
modules). Graph-discovered chunks are scored below vector results using a
depth-decaying formula.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from local_deepwiki.logging import get_logger
from local_deepwiki.models.chunks import SearchResult

if TYPE_CHECKING:
    from local_deepwiki.config.models import GraphRAGConfig
    from local_deepwiki.core.graph_rag.store import KnowledgeGraphStore
    from local_deepwiki.core.vectorstore.store import VectorStore

logger = get_logger(__name__)


class GraphAugmentedRetriever:
    """Expand vector search results by traversing the knowledge graph.

    The retriever sits between the vector store search and the caller,
    enriching results with structurally related code discovered via
    graph traversal (calls, imports, inheritance, containment, references).

    Graph-discovered chunks are scored below the minimum vector result using
    a depth-decaying formula so they supplement -- but never outrank -- direct
    semantic matches.
    """

    __slots__ = ("_graph_store", "_vector_store", "_config")

    def __init__(
        self,
        graph_store: KnowledgeGraphStore,
        vector_store: VectorStore,
        config: GraphRAGConfig,
    ) -> None:
        self._graph_store = graph_store
        self._vector_store = vector_store
        self._config = config

    async def expand_results(
        self,
        search_results: list[SearchResult],
        relationship_types: list[str] | None = None,
    ) -> list[SearchResult]:
        """Expand vector search results with graph-discovered chunks.

        Algorithm:
        1. Extract ``chunk_id`` values from *search_results*.
        2. Look up corresponding graph entities via the graph store.
        3. For each entity, traverse neighbors via
           ``graph_store.get_neighbors()`` using
           ``config.max_traversal_depth`` and *relationship_types*.
        4. Collect unique neighbor ``chunk_id`` values (excluding chunks
           already present in the vector results).
        5. Fetch neighbor chunks from the vector store by ID.
        6. Score each graph chunk with :meth:`_compute_graph_score`.
        7. Return original results + graph results, capped by
           ``config.max_graph_neighbors``.

        Args:
            search_results: Vector search results to expand.
            relationship_types: Relationship types to traverse.  Falls back
                to ``config.relationship_types`` when *None*.

        Returns:
            The original results followed by graph-discovered results,
            deduplicated by ``chunk_id``.
        """
        if not search_results:
            return list(search_results)

        effective_rel_types = (
            relationship_types
            if relationship_types is not None
            else list(self._config.relationship_types)
        )

        # Step 1 — collect chunk IDs already in vector results
        seen_chunk_ids: set[str] = {r.chunk.id for r in search_results}
        original_chunk_ids = list(seen_chunk_ids)

        # Step 2 — map chunks to graph entities
        entities = await self._graph_store.get_entities_by_chunk_ids(original_chunk_ids)
        if not entities:
            logger.debug(
                "No graph entities found for %d chunks", len(original_chunk_ids)
            )
            return list(search_results)

        # Steps 3-4 — BFS traversal and neighbor collection
        seed_entity_ids = [e.id for e in entities]
        neighbor_chunk_depths = await self._traverse_and_collect_neighbors(
            seed_entity_ids, seen_chunk_ids, effective_rel_types
        )

        if not neighbor_chunk_depths:
            logger.debug("Graph traversal found no new neighbors")
            return list(search_results)

        # Steps 5-6 — fetch chunks from vector store and score them
        min_vector_score = min(r.score for r in search_results)
        graph_results = await self._fetch_and_score_graph_results(
            neighbor_chunk_depths, min_vector_score
        )

        logger.debug(
            "Graph expansion: %d vector results + %d graph results",
            len(search_results),
            len(graph_results),
        )

        return list(search_results) + graph_results

    async def _traverse_and_collect_neighbors(
        self,
        seed_entity_ids: list[str],
        seen_chunk_ids: set[str],
        relationship_types: list[str],
    ) -> dict[str, int]:
        """BFS traversal to discover neighbor chunk IDs and their shallowest depth.

        Calls ``graph_store.get_neighbors`` once per depth level, collecting
        every new chunk ID encountered.  Chunk IDs already present in
        *seen_chunk_ids* are skipped.

        Args:
            seed_entity_ids: Entity IDs from which to start traversal.
            seen_chunk_ids: Chunk IDs already in the vector results (excluded).
            relationship_types: Edge types to follow during traversal.

        Returns:
            Mapping of ``chunk_id`` -> shallowest depth at which it was found.
        """
        neighbor_chunk_depths: dict[str, int] = {}

        for depth in range(1, self._config.max_traversal_depth + 1):
            traversal = await self._graph_store.get_neighbors(
                seed_entity_ids,
                relationship_types=relationship_types,
                max_depth=depth,
            )
            for neighbor in traversal.entities:
                cid = neighbor.chunk_id
                if not cid or cid in seen_chunk_ids:
                    continue
                # Keep the shallowest depth at which we discovered this chunk
                if (
                    cid not in neighbor_chunk_depths
                    or depth < neighbor_chunk_depths[cid]
                ):
                    neighbor_chunk_depths[cid] = depth

        return neighbor_chunk_depths

    async def _fetch_and_score_graph_results(
        self,
        neighbor_chunk_depths: dict[str, int],
        min_vector_score: float,
    ) -> list[SearchResult]:
        """Fetch neighbor chunks from the vector store and compute their scores.

        Caps the number of graph neighbors at ``config.max_graph_neighbors``,
        preferring shallower (closer) neighbors.  Each fetched chunk is scored
        with :meth:`_compute_graph_score`.

        Args:
            neighbor_chunk_depths: Mapping of ``chunk_id`` -> discovery depth.
            min_vector_score: Lowest score among the original vector results.

        Returns:
            List of :class:`~local_deepwiki.models.chunks.SearchResult` for
            graph-discovered chunks, tagged with ``highlights=["graph-expanded"]``.
        """
        # Prefer shallower (closer) neighbors by sorting on depth
        sorted_neighbors = sorted(
            neighbor_chunk_depths.items(), key=lambda item: item[1]
        )
        capped = sorted_neighbors[: self._config.max_graph_neighbors]

        graph_results: list[SearchResult] = []
        for chunk_id, depth in capped:
            chunk = await self._vector_store.get_chunk_by_id(chunk_id)
            if chunk is None:
                logger.debug("Chunk %s not found in vector store, skipping", chunk_id)
                continue

            score = self._compute_graph_score(
                min_vector_score,
                self._config.score_boost_factor,
                depth,
            )
            graph_results.append(
                SearchResult(chunk=chunk, score=score, highlights=["graph-expanded"])
            )

        return graph_results

    @staticmethod
    def _compute_graph_score(
        min_vector_score: float,
        boost_factor: float,
        depth: int,
    ) -> float:
        """Compute score for a graph-discovered chunk.

        The score decays with traversal depth so that closer neighbors rank
        higher::

            score = min_vector_score * boost_factor * (1 / depth)

        This ensures graph results always rank below vector results (assuming
        ``boost_factor < 1``) while remaining above random noise.

        Args:
            min_vector_score: Lowest score among the original vector results.
            boost_factor: Multiplier from ``GraphRAGConfig.score_boost_factor``.
            depth: BFS depth at which the neighbor was discovered (>= 1).

        Returns:
            Non-negative float score.
        """
        if depth < 1:
            depth = 1
        return min_vector_score * boost_factor * (1.0 / depth)
