"""Tests for KnowledgeGraphStore — LanceDB-backed graph storage.

Covers: CRUD operations, delete_by_file, get_neighbors (BFS at depth 1/2),
direction filtering, relationship type filtering, empty graph handling,
serialization round-trips, and count methods.
"""

from __future__ import annotations

import pytest

from local_deepwiki.core.graph_rag.models import (
    EntityType,
    GraphEntity,
    GraphRelationship,
    GraphTraversalResult,
    RelationshipType,
    entity_id,
    relationship_id,
)
from local_deepwiki.core.graph_rag.store import (
    KnowledgeGraphStore,
    _create_index_safe,
    _sanitize_string_value,
)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_entity(
    file_path: str = "src/main.py",
    name: str = "main",
    qualified_name: str = "main",
    entity_type: EntityType = EntityType.FUNCTION,
    start_line: int = 1,
    end_line: int = 10,
    chunk_id: str = "chunk_1",
    metadata: dict | None = None,
) -> GraphEntity:
    """Create a ``GraphEntity`` with sensible defaults."""
    return GraphEntity(
        id=entity_id(file_path, qualified_name),
        name=name,
        qualified_name=qualified_name,
        entity_type=entity_type,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        chunk_id=chunk_id,
        metadata=metadata or {},
    )


def make_relationship(
    source: GraphEntity,
    target: GraphEntity,
    rel_type: RelationshipType = RelationshipType.CALLS,
    weight: float = 1.0,
    metadata: dict | None = None,
) -> GraphRelationship:
    """Create a ``GraphRelationship`` between two entities."""
    return GraphRelationship(
        id=relationship_id(source.id, rel_type, target.id),
        source_id=source.id,
        target_id=target.id,
        relationship=rel_type,
        file_path=source.file_path,
        weight=weight,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    """Return an empty KnowledgeGraphStore backed by a temporary LanceDB."""
    db_path = tmp_path / "test_graph.lance"
    s = KnowledgeGraphStore(db_path)
    yield s
    s.close()


@pytest.fixture()
def sample_entities() -> list[GraphEntity]:
    """Three entities across two files."""
    return [
        make_entity(
            file_path="src/main.py",
            name="main",
            qualified_name="main",
            entity_type=EntityType.FUNCTION,
            chunk_id="chunk_main",
        ),
        make_entity(
            file_path="src/main.py",
            name="helper",
            qualified_name="helper",
            entity_type=EntityType.FUNCTION,
            chunk_id="chunk_helper",
        ),
        make_entity(
            file_path="src/utils.py",
            name="util_fn",
            qualified_name="util_fn",
            entity_type=EntityType.FUNCTION,
            chunk_id="chunk_util",
        ),
    ]


@pytest.fixture()
def sample_relationships(sample_entities) -> list[GraphRelationship]:
    """main -> calls -> helper, main -> calls -> util_fn."""
    main_ent, helper_ent, util_ent = sample_entities
    return [
        make_relationship(main_ent, helper_ent, RelationshipType.CALLS),
        make_relationship(main_ent, util_ent, RelationshipType.CALLS),
    ]


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestSanitizeStringValue:
    def test_no_quotes(self):
        assert _sanitize_string_value("hello") == "hello"

    def test_single_quote_escaped(self):
        assert _sanitize_string_value("it's") == "it''s"

    def test_multiple_quotes(self):
        assert _sanitize_string_value("a'b'c") == "a''b''c"


class TestCreateIndexSafe:
    """Verify that _create_index_safe silently handles failures."""

    def test_does_not_raise_on_error(self, tmp_path):
        """Calling with an object that raises should not propagate."""

        class FakeTable:
            def create_scalar_index(self, column):
                raise RuntimeError("boom")

        # Should not raise
        _create_index_safe(FakeTable(), "id")


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


class TestAddEntities:
    async def test_add_entities_creates_table(self, store, sample_entities):
        count = await store.add_entities(sample_entities)
        assert count == 3
        assert await store.get_entity_count() == 3

    async def test_add_entities_empty_list(self, store):
        count = await store.add_entities([])
        assert count == 0

    async def test_add_entities_appends(self, store, sample_entities):
        await store.add_entities(sample_entities[:2])
        await store.add_entities(sample_entities[2:])
        assert await store.get_entity_count() == 3


class TestAddRelationships:
    async def test_add_relationships_creates_table(
        self, store, sample_entities, sample_relationships
    ):
        await store.add_entities(sample_entities)
        count = await store.add_relationships(sample_relationships)
        assert count == 2
        assert await store.get_relationship_count() == 2

    async def test_add_relationships_empty_list(self, store):
        count = await store.add_relationships([])
        assert count == 0


class TestGetEntity:
    async def test_get_existing_entity(self, store, sample_entities):
        await store.add_entities(sample_entities)
        ent = await store.get_entity(sample_entities[0].id)
        assert ent is not None
        assert ent.id == sample_entities[0].id
        assert ent.name == "main"
        assert ent.entity_type == EntityType.FUNCTION

    async def test_get_nonexistent_entity(self, store, sample_entities):
        await store.add_entities(sample_entities)
        ent = await store.get_entity("nonexistent::id")
        assert ent is None

    async def test_get_entity_empty_graph(self, store):
        ent = await store.get_entity("anything")
        assert ent is None


class TestGetEntitiesByChunkIds:
    async def test_lookup_by_chunk_ids(self, store, sample_entities):
        await store.add_entities(sample_entities)
        results = await store.get_entities_by_chunk_ids(["chunk_main", "chunk_util"])
        assert len(results) == 2
        names = {e.name for e in results}
        assert names == {"main", "util_fn"}

    async def test_empty_chunk_ids(self, store, sample_entities):
        await store.add_entities(sample_entities)
        results = await store.get_entities_by_chunk_ids([])
        assert results == []

    async def test_no_matching_chunk_ids(self, store, sample_entities):
        await store.add_entities(sample_entities)
        results = await store.get_entities_by_chunk_ids(["nonexistent"])
        assert results == []

    async def test_empty_graph(self, store):
        results = await store.get_entities_by_chunk_ids(["chunk_1"])
        assert results == []


# ---------------------------------------------------------------------------
# delete_by_file tests
# ---------------------------------------------------------------------------


class TestDeleteByFile:
    async def test_deletes_entities_for_file(self, store, sample_entities):
        await store.add_entities(sample_entities)
        # Delete entities for src/main.py (2 entities)
        await store.delete_by_file("src/main.py")
        assert await store.get_entity_count() == 1
        remaining = await store.get_entity(sample_entities[2].id)
        assert remaining is not None
        assert remaining.file_path == "src/utils.py"

    async def test_deletes_edges_for_file(
        self, store, sample_entities, sample_relationships
    ):
        await store.add_entities(sample_entities)
        await store.add_relationships(sample_relationships)
        # Both relationships have file_path="src/main.py"
        await store.delete_by_file("src/main.py")
        assert await store.get_relationship_count() == 0

    async def test_delete_nonexistent_file_no_error(self, store, sample_entities):
        await store.add_entities(sample_entities)
        await store.delete_by_file("nonexistent.py")
        assert await store.get_entity_count() == 3

    async def test_delete_on_empty_graph(self, store):
        # Should not raise
        await store.delete_by_file("anything.py")


# ---------------------------------------------------------------------------
# get_neighbors tests
# ---------------------------------------------------------------------------


class TestGetNeighborsDepth1:
    """BFS traversal at depth 1."""

    async def test_outgoing_neighbors(
        self, store, sample_entities, sample_relationships
    ):
        await store.add_entities(sample_entities)
        await store.add_relationships(sample_relationships)

        main_id = sample_entities[0].id
        result = await store.get_neighbors([main_id], direction="outgoing", max_depth=1)

        assert isinstance(result, GraphTraversalResult)
        assert result.depth_reached == 1
        # main calls helper and util_fn
        assert result.relationship_count == 2
        entity_names = {e.name for e in result.entities}
        assert "helper" in entity_names
        assert "util_fn" in entity_names
        # seed entity should also be fetched
        assert "main" in entity_names

    async def test_incoming_neighbors(
        self, store, sample_entities, sample_relationships
    ):
        await store.add_entities(sample_entities)
        await store.add_relationships(sample_relationships)

        helper_id = sample_entities[1].id
        result = await store.get_neighbors(
            [helper_id], direction="incoming", max_depth=1
        )

        assert result.depth_reached == 1
        entity_names = {e.name for e in result.entities}
        assert "main" in entity_names
        assert "helper" in entity_names

    async def test_both_direction(self, store, sample_entities, sample_relationships):
        await store.add_entities(sample_entities)
        await store.add_relationships(sample_relationships)

        helper_id = sample_entities[1].id
        result = await store.get_neighbors([helper_id], direction="both", max_depth=1)

        assert result.depth_reached == 1
        entity_names = {e.name for e in result.entities}
        assert "main" in entity_names
        assert "helper" in entity_names


class TestGetNeighborsDepth2:
    """BFS traversal at depth 2."""

    async def test_transitive_neighbors(self, store):
        """A -> B -> C chain: from A at depth 2 finds C."""
        a = make_entity(name="a", qualified_name="a", chunk_id="ca")
        b = make_entity(name="b", qualified_name="b", chunk_id="cb")
        c = make_entity(name="c", qualified_name="c", chunk_id="cc")
        await store.add_entities([a, b, c])

        ab = make_relationship(a, b)
        bc = make_relationship(b, c)
        await store.add_relationships([ab, bc])

        result = await store.get_neighbors([a.id], direction="outgoing", max_depth=2)

        assert result.depth_reached == 2
        entity_names = {e.name for e in result.entities}
        assert entity_names == {"a", "b", "c"}
        assert result.relationship_count == 2

    async def test_depth2_no_extra_when_depth1_sufficient(self, store):
        """If all neighbors are found at depth 1, depth_reached should be 1."""
        a = make_entity(name="a", qualified_name="a", chunk_id="ca")
        b = make_entity(name="b", qualified_name="b", chunk_id="cb")
        await store.add_entities([a, b])
        await store.add_relationships([make_relationship(a, b)])

        result = await store.get_neighbors([a.id], direction="outgoing", max_depth=2)

        # depth 1 finds b; depth 2 has empty frontier so stops
        assert result.depth_reached == 1
        assert result.entity_count == 2


class TestGetNeighborsRelationshipFilter:
    async def test_filter_by_relationship_type(self, store):
        a = make_entity(name="a", qualified_name="a", chunk_id="ca")
        b = make_entity(name="b", qualified_name="b", chunk_id="cb")
        c = make_entity(name="c", qualified_name="c", chunk_id="cc")
        await store.add_entities([a, b, c])

        calls_edge = make_relationship(a, b, RelationshipType.CALLS)
        imports_edge = make_relationship(a, c, RelationshipType.IMPORTS)
        await store.add_relationships([calls_edge, imports_edge])

        # Only follow "calls"
        result = await store.get_neighbors(
            [a.id],
            relationship_types=["calls"],
            direction="outgoing",
            max_depth=1,
        )

        assert result.relationship_count == 1
        neighbor_names = {e.name for e in result.entities if e.name != "a"}
        assert neighbor_names == {"b"}

    async def test_filter_excludes_all(self, store):
        a = make_entity(name="a", qualified_name="a", chunk_id="ca")
        b = make_entity(name="b", qualified_name="b", chunk_id="cb")
        await store.add_entities([a, b])
        await store.add_relationships([make_relationship(a, b, RelationshipType.CALLS)])

        result = await store.get_neighbors(
            [a.id],
            relationship_types=["imports"],
            direction="outgoing",
            max_depth=1,
        )

        # No edges match the filter, so depth is 0
        assert result.depth_reached == 0
        assert result.relationship_count == 0


class TestGetNeighborsEmptyGraph:
    async def test_empty_graph_returns_empty_result(self, store):
        result = await store.get_neighbors(["any_id"], max_depth=1)
        assert result == GraphTraversalResult()
        assert result.entity_count == 0
        assert result.relationship_count == 0
        assert result.depth_reached == 0


# ---------------------------------------------------------------------------
# Count tests
# ---------------------------------------------------------------------------


class TestCounts:
    async def test_entity_count_empty(self, store):
        assert await store.get_entity_count() == 0

    async def test_relationship_count_empty(self, store):
        assert await store.get_relationship_count() == 0

    async def test_counts_after_inserts(
        self, store, sample_entities, sample_relationships
    ):
        await store.add_entities(sample_entities)
        await store.add_relationships(sample_relationships)
        assert await store.get_entity_count() == 3
        assert await store.get_relationship_count() == 2


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------


class TestRecordRoundTrip:
    def test_entity_round_trip(self):
        ent = make_entity(metadata={"doc": "hello"})
        record = ent.to_record()
        restored = KnowledgeGraphStore._record_to_entity(record)
        assert restored.id == ent.id
        assert restored.name == ent.name
        assert restored.entity_type == ent.entity_type
        assert restored.metadata == {"doc": "hello"}

    def test_relationship_round_trip(self):
        a = make_entity(name="a", qualified_name="a")
        b = make_entity(name="b", qualified_name="b")
        rel = make_relationship(a, b, weight=0.75, metadata={"info": 42})
        record = rel.to_record()
        restored = KnowledgeGraphStore._record_to_relationship(record)
        assert restored.id == rel.id
        assert restored.relationship == RelationshipType.CALLS
        assert restored.weight == 0.75
        assert restored.metadata == {"info": 42}

    def test_entity_empty_metadata(self):
        record = {
            "id": "x",
            "name": "x",
            "qualified_name": "x",
            "entity_type": "function",
            "file_path": "f.py",
            "start_line": 1,
            "end_line": 2,
            "chunk_id": "",
            "metadata": "{}",
        }
        ent = KnowledgeGraphStore._record_to_entity(record)
        assert ent.metadata == {}

    def test_relationship_default_weight(self):
        record = {
            "id": "x",
            "source_id": "a",
            "target_id": "b",
            "relationship": "calls",
            "file_path": "f.py",
            "metadata": "{}",
        }
        rel = KnowledgeGraphStore._record_to_relationship(record)
        assert rel.weight == 1.0


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


class TestClose:
    async def test_close_releases_resources(self, store, sample_entities):
        await store.add_entities(sample_entities)
        store.close()
        assert store._db is None
        assert store._entities_table is None
        assert store._edges_table is None

    async def test_close_is_idempotent(self, store):
        store.close()
        store.close()  # should not raise

    async def test_usable_after_close(self, store, sample_entities):
        """Store reconnects lazily after close."""
        await store.add_entities(sample_entities)
        store.close()
        # Should reconnect and create a new table (old data persists on disk)
        count = await store.get_entity_count()
        assert count == 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    async def test_entity_with_special_characters_in_name(self, store):
        ent = make_entity(
            name="it's_special",
            qualified_name="it's_special",
            chunk_id="c1",
        )
        await store.add_entities([ent])
        result = await store.get_entity(ent.id)
        assert result is not None
        assert result.name == "it's_special"

    async def test_metadata_preserved(self, store):
        ent = make_entity(
            metadata={"complexity": 5, "tags": ["api", "public"]},
        )
        await store.add_entities([ent])
        result = await store.get_entity(ent.id)
        assert result is not None
        assert result.metadata["complexity"] == 5
        assert result.metadata["tags"] == ["api", "public"]

    async def test_multiple_seeds_in_get_neighbors(self, store):
        """BFS from multiple seed entities at once."""
        a = make_entity(name="a", qualified_name="a", chunk_id="ca")
        b = make_entity(name="b", qualified_name="b", chunk_id="cb")
        c = make_entity(name="c", qualified_name="c", chunk_id="cc")
        d = make_entity(name="d", qualified_name="d", chunk_id="cd")
        await store.add_entities([a, b, c, d])

        await store.add_relationships(
            [
                make_relationship(a, c, RelationshipType.CALLS),
                make_relationship(b, d, RelationshipType.CALLS),
            ]
        )

        # Start from both a and b
        result = await store.get_neighbors(
            [a.id, b.id], direction="outgoing", max_depth=1
        )
        entity_names = {e.name for e in result.entities}
        assert {"a", "b", "c", "d"} == entity_names
