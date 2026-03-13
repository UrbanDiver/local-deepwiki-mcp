"""Tests for GraphAugmentedRetriever."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.config.models import GraphRAGConfig
from local_deepwiki.core.graph_rag.models import (
    EntityType,
    GraphEntity,
    GraphTraversalResult,
)
from local_deepwiki.core.graph_rag.retriever import GraphAugmentedRetriever
from local_deepwiki.models.chunks import CodeChunk, SearchResult
from local_deepwiki.models.foundation import ChunkType, Language


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, name: str = "func") -> CodeChunk:
    """Create a minimal CodeChunk for testing."""
    return CodeChunk(
        id=chunk_id,
        file_path=f"src/{name}.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.FUNCTION,
        name=name,
        content=f"def {name}(): pass",
        start_line=1,
        end_line=1,
    )


def _make_search_result(
    chunk_id: str, score: float, name: str = "func"
) -> SearchResult:
    """Create a SearchResult wrapping a real CodeChunk."""
    return SearchResult(chunk=_make_chunk(chunk_id, name), score=score)


def _make_entity(
    entity_id: str,
    chunk_id: str,
    name: str = "func",
) -> GraphEntity:
    """Create a GraphEntity with a given chunk_id."""
    return GraphEntity(
        id=entity_id,
        name=name,
        qualified_name=name,
        entity_type=EntityType.FUNCTION,
        file_path=f"src/{name}.py",
        start_line=1,
        end_line=1,
        chunk_id=chunk_id,
    )


def _make_traversal(*entities: GraphEntity) -> GraphTraversalResult:
    """Wrap entities into a GraphTraversalResult."""
    return GraphTraversalResult(entities=tuple(entities), depth_reached=1)


def _make_config(**overrides: object) -> GraphRAGConfig:
    """Create a GraphRAGConfig with sensible defaults, applying overrides."""
    defaults: dict[str, object] = {
        "enabled": True,
        "max_traversal_depth": 2,
        "max_graph_neighbors": 15,
        "relationship_types": ["calls", "imports"],
        "score_boost_factor": 0.7,
    }
    defaults.update(overrides)
    return GraphRAGConfig(**defaults)  # type: ignore[arg-type]


def _make_stores() -> tuple[MagicMock, MagicMock]:
    """Return (graph_store, vector_store) mocks with async methods."""
    graph_store = MagicMock()
    graph_store.get_entities_by_chunk_ids = AsyncMock(return_value=[])
    graph_store.get_neighbors = AsyncMock(return_value=GraphTraversalResult())

    vector_store = MagicMock()
    vector_store.get_chunk_by_id = AsyncMock(return_value=None)
    return graph_store, vector_store


# ---------------------------------------------------------------------------
# Tests — _compute_graph_score
# ---------------------------------------------------------------------------


class TestComputeGraphScore:
    def test_depth_one(self):
        score = GraphAugmentedRetriever._compute_graph_score(0.8, 0.7, 1)
        assert score == pytest.approx(0.8 * 0.7)

    def test_depth_two(self):
        score = GraphAugmentedRetriever._compute_graph_score(0.8, 0.7, 2)
        assert score == pytest.approx(0.8 * 0.7 * 0.5)

    def test_depth_three(self):
        score = GraphAugmentedRetriever._compute_graph_score(0.6, 0.5, 3)
        expected = 0.6 * 0.5 * (1.0 / 3)
        assert score == pytest.approx(expected)

    def test_depth_zero_clamped_to_one(self):
        """Depth < 1 is clamped to 1 to avoid division by zero."""
        score = GraphAugmentedRetriever._compute_graph_score(1.0, 0.7, 0)
        assert score == pytest.approx(0.7)

    def test_negative_depth_clamped(self):
        score = GraphAugmentedRetriever._compute_graph_score(1.0, 0.7, -5)
        assert score == pytest.approx(0.7)

    def test_zero_min_score(self):
        score = GraphAugmentedRetriever._compute_graph_score(0.0, 0.7, 1)
        assert score == 0.0

    def test_zero_boost_factor(self):
        score = GraphAugmentedRetriever._compute_graph_score(0.9, 0.0, 1)
        assert score == 0.0

    def test_full_boost(self):
        score = GraphAugmentedRetriever._compute_graph_score(1.0, 1.0, 1)
        assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests — expand_results
# ---------------------------------------------------------------------------


class TestExpandResultsEmpty:
    async def test_empty_search_results(self):
        """Empty input returns empty output, no store calls."""
        graph_store, vector_store = _make_stores()
        retriever = GraphAugmentedRetriever(graph_store, vector_store, _make_config())
        result = await retriever.expand_results([])
        assert result == []
        graph_store.get_entities_by_chunk_ids.assert_not_awaited()

    async def test_no_entities_returns_original(self):
        """When graph store finds no entities, return originals unchanged."""
        graph_store, vector_store = _make_stores()
        graph_store.get_entities_by_chunk_ids.return_value = []

        sr = _make_search_result("chunk-1", 0.9, "alpha")
        retriever = GraphAugmentedRetriever(graph_store, vector_store, _make_config())
        result = await retriever.expand_results([sr])

        assert len(result) == 1
        assert result[0].chunk.id == "chunk-1"
        vector_store.get_chunk_by_id.assert_not_awaited()


class TestExpandResultsBasic:
    async def test_expands_with_graph_neighbors(self):
        """Neighbors from graph traversal are appended to results."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1)

        # Vector result
        sr = _make_search_result("chunk-A", 0.9, "alpha")

        # Graph entity for chunk-A
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        # Neighbor entity with a different chunk
        neighbor = _make_entity("ent-B", "chunk-B", "beta")
        graph_store.get_neighbors.return_value = _make_traversal(entity_a, neighbor)

        # Vector store returns a chunk for the neighbor
        neighbor_chunk = _make_chunk("chunk-B", "beta")
        vector_store.get_chunk_by_id.return_value = neighbor_chunk

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        assert len(result) == 2
        assert result[0].chunk.id == "chunk-A"
        assert result[1].chunk.id == "chunk-B"
        assert result[1].highlights == ["graph-expanded"]

    async def test_graph_score_below_vector_score(self):
        """Graph-discovered results should score below vector results."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1, score_boost_factor=0.7)

        sr = _make_search_result("chunk-A", 0.8, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        neighbor = _make_entity("ent-B", "chunk-B", "beta")
        graph_store.get_neighbors.return_value = _make_traversal(entity_a, neighbor)

        vector_store.get_chunk_by_id.return_value = _make_chunk("chunk-B", "beta")

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        # Graph score = 0.8 * 0.7 * (1/1) = 0.56
        assert result[1].score == pytest.approx(0.56)
        assert result[1].score < result[0].score


class TestExpandResultsDeduplication:
    async def test_already_in_vector_results_skipped(self):
        """Chunks already in vector results are not duplicated."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1)

        sr = _make_search_result("chunk-A", 0.9, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        # Neighbor has the SAME chunk_id as the vector result
        neighbor_same = _make_entity("ent-A2", "chunk-A", "alpha")
        graph_store.get_neighbors.return_value = _make_traversal(
            entity_a, neighbor_same
        )

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        # No expansion — neighbor chunk already present
        assert len(result) == 1
        vector_store.get_chunk_by_id.assert_not_awaited()

    async def test_empty_chunk_id_skipped(self):
        """Entities with empty chunk_id are skipped."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1)

        sr = _make_search_result("chunk-A", 0.9, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        # Neighbor has no chunk_id
        neighbor_no_chunk = _make_entity("ent-X", "", "orphan")
        graph_store.get_neighbors.return_value = _make_traversal(
            entity_a, neighbor_no_chunk
        )

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        assert len(result) == 1
        vector_store.get_chunk_by_id.assert_not_awaited()


class TestExpandResultsMissingChunk:
    async def test_chunk_not_in_vector_store_skipped(self):
        """If vector store returns None for a chunk_id, skip it gracefully."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1)

        sr = _make_search_result("chunk-A", 0.9, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        neighbor = _make_entity("ent-B", "chunk-GONE", "beta")
        graph_store.get_neighbors.return_value = _make_traversal(entity_a, neighbor)

        # Chunk does not exist in vector store
        vector_store.get_chunk_by_id.return_value = None

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        assert len(result) == 1
        assert result[0].chunk.id == "chunk-A"


class TestExpandResultsDepthScoring:
    async def test_deeper_neighbors_score_lower(self):
        """Neighbors at depth 2 score lower than those at depth 1."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=2, score_boost_factor=0.7)

        sr = _make_search_result("chunk-A", 1.0, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        neighbor_d1 = _make_entity("ent-B", "chunk-B", "beta")
        neighbor_d2 = _make_entity("ent-C", "chunk-C", "gamma")

        # At depth=1, only neighbor_d1 is found (alongside seed entity_a)
        # At depth=2, both neighbors found
        async def mock_get_neighbors(
            entity_ids: list[str],
            relationship_types: list[str] | None = None,
            max_depth: int = 1,
            **kwargs: object,
        ) -> GraphTraversalResult:
            if max_depth == 1:
                return _make_traversal(entity_a, neighbor_d1)
            return _make_traversal(entity_a, neighbor_d1, neighbor_d2)

        graph_store.get_neighbors.side_effect = mock_get_neighbors

        vector_store.get_chunk_by_id.side_effect = lambda cid: (
            _make_chunk("chunk-B", "beta")
            if cid == "chunk-B"
            else _make_chunk("chunk-C", "gamma")
        )

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        # 1 original + 2 graph
        assert len(result) == 3
        # chunk-B discovered at depth 1: score = 1.0 * 0.7 * 1.0 = 0.7
        assert result[1].chunk.id == "chunk-B"
        assert result[1].score == pytest.approx(0.7)
        # chunk-C discovered at depth 2: score = 1.0 * 0.7 * 0.5 = 0.35
        assert result[2].chunk.id == "chunk-C"
        assert result[2].score == pytest.approx(0.35)


class TestExpandResultsMaxNeighborsCap:
    async def test_cap_limits_graph_results(self):
        """max_graph_neighbors caps the number of graph-added results."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1, max_graph_neighbors=2)

        sr = _make_search_result("chunk-A", 0.9, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        # Return 5 neighbor entities (plus seed)
        neighbors = [
            _make_entity(f"ent-{i}", f"chunk-{i}", f"func_{i}") for i in range(5)
        ]
        graph_store.get_neighbors.return_value = _make_traversal(entity_a, *neighbors)

        # All chunks exist in vector store
        vector_store.get_chunk_by_id.side_effect = lambda cid: _make_chunk(
            cid, f"func_{cid}"
        )

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr])

        # 1 original + 2 graph (capped at max_graph_neighbors=2)
        assert len(result) == 3


class TestExpandResultsRelationshipTypes:
    async def test_uses_config_defaults_when_none(self):
        """When relationship_types=None, config defaults are used."""
        graph_store, vector_store = _make_stores()
        config = _make_config(
            max_traversal_depth=1, relationship_types=["calls", "imports"]
        )

        sr = _make_search_result("chunk-A", 0.9, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]
        graph_store.get_neighbors.return_value = GraphTraversalResult()

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        await retriever.expand_results([sr], relationship_types=None)

        graph_store.get_neighbors.assert_awaited_once_with(
            ["ent-A"],
            relationship_types=["calls", "imports"],
            max_depth=1,
        )

    async def test_uses_explicit_relationship_types(self):
        """When relationship_types is provided, it overrides config."""
        graph_store, vector_store = _make_stores()
        config = _make_config(
            max_traversal_depth=1, relationship_types=["calls", "imports"]
        )

        sr = _make_search_result("chunk-A", 0.9, "alpha")
        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]
        graph_store.get_neighbors.return_value = GraphTraversalResult()

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        await retriever.expand_results([sr], relationship_types=["inherits_from"])

        graph_store.get_neighbors.assert_awaited_once_with(
            ["ent-A"],
            relationship_types=["inherits_from"],
            max_depth=1,
        )


class TestExpandResultsMultipleVectorResults:
    async def test_min_score_used_across_all_vector_results(self):
        """The minimum score across ALL vector results is used for graph scoring."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1, score_boost_factor=0.5)

        sr_high = _make_search_result("chunk-A", 0.95, "alpha")
        sr_low = _make_search_result("chunk-B", 0.60, "beta")

        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        neighbor = _make_entity("ent-C", "chunk-C", "gamma")
        graph_store.get_neighbors.return_value = _make_traversal(entity_a, neighbor)

        vector_store.get_chunk_by_id.return_value = _make_chunk("chunk-C", "gamma")

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr_high, sr_low])

        # min score = 0.60, so graph score = 0.60 * 0.5 * 1.0 = 0.30
        assert len(result) == 3
        assert result[2].score == pytest.approx(0.30)


class TestExpandResultsNoNewNeighbors:
    async def test_all_neighbors_already_seen(self):
        """When all neighbors are already in vector results, no expansion."""
        graph_store, vector_store = _make_stores()
        config = _make_config(max_traversal_depth=1)

        sr_a = _make_search_result("chunk-A", 0.9, "alpha")
        sr_b = _make_search_result("chunk-B", 0.8, "beta")

        entity_a = _make_entity("ent-A", "chunk-A", "alpha")
        graph_store.get_entities_by_chunk_ids.return_value = [entity_a]

        # Neighbor points to chunk-B which is already in vector results
        neighbor = _make_entity("ent-B", "chunk-B", "beta")
        graph_store.get_neighbors.return_value = _make_traversal(entity_a, neighbor)

        retriever = GraphAugmentedRetriever(graph_store, vector_store, config)
        result = await retriever.expand_results([sr_a, sr_b])

        assert len(result) == 2
        vector_store.get_chunk_by_id.assert_not_awaited()


class TestSlots:
    def test_has_slots(self):
        """Verify __slots__ is defined to prevent accidental attributes."""
        assert "__slots__" in vars(GraphAugmentedRetriever)
        assert "_graph_store" in GraphAugmentedRetriever.__slots__
        assert "_vector_store" in GraphAugmentedRetriever.__slots__
        assert "_config" in GraphAugmentedRetriever.__slots__

    def test_no_dict(self):
        """Instances should not have __dict__ due to __slots__."""
        graph_store, vector_store = _make_stores()
        retriever = GraphAugmentedRetriever(graph_store, vector_store, _make_config())
        assert not hasattr(retriever, "__dict__")
