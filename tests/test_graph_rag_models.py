"""Tests for GraphRAG data models."""

from __future__ import annotations

import pytest

from local_deepwiki.core.graph_rag.models import (
    EntityType,
    FileGraphData,
    GraphEntity,
    GraphRelationship,
    GraphTraversalResult,
    RelationshipType,
    entity_id,
    relationship_id,
)


class TestEntityType:
    def test_all_types(self):
        assert EntityType.FUNCTION == "function"
        assert EntityType.CLASS == "class"
        assert EntityType.METHOD == "method"
        assert EntityType.MODULE == "module"
        assert EntityType.VARIABLE == "variable"


class TestRelationshipType:
    def test_all_types(self):
        assert RelationshipType.CALLS == "calls"
        assert RelationshipType.IMPORTS == "imports"
        assert RelationshipType.INHERITS_FROM == "inherits_from"
        assert RelationshipType.CONTAINS == "contains"
        assert RelationshipType.REFERENCES == "references"


class TestEntityId:
    def test_deterministic(self):
        id1 = entity_id("src/main.py", "MyClass.method")
        id2 = entity_id("src/main.py", "MyClass.method")
        assert id1 == id2

    def test_format(self):
        result = entity_id("src/main.py", "parse_file")
        assert result == "src/main.py::parse_file"

    def test_different_files_different_ids(self):
        id1 = entity_id("a.py", "func")
        id2 = entity_id("b.py", "func")
        assert id1 != id2


class TestRelationshipId:
    def test_deterministic(self):
        id1 = relationship_id("a::f", "calls", "b::g")
        id2 = relationship_id("a::f", "calls", "b::g")
        assert id1 == id2

    def test_format(self):
        result = relationship_id("src::A", RelationshipType.INHERITS_FROM, "src::B")
        assert result == "src::A::inherits_from::src::B"

    def test_direction_matters(self):
        id1 = relationship_id("a", "calls", "b")
        id2 = relationship_id("b", "calls", "a")
        assert id1 != id2


class TestGraphEntity:
    def test_creation(self):
        e = GraphEntity(
            id="main.py::func",
            name="func",
            qualified_name="func",
            entity_type=EntityType.FUNCTION,
            file_path="main.py",
            start_line=1,
            end_line=5,
        )
        assert e.name == "func"
        assert e.entity_type == EntityType.FUNCTION
        assert e.chunk_id == ""
        assert e.metadata == {}

    def test_frozen(self):
        e = GraphEntity(
            id="x",
            name="x",
            qualified_name="x",
            entity_type=EntityType.FUNCTION,
            file_path="x.py",
            start_line=1,
            end_line=2,
        )
        with pytest.raises(AttributeError):
            e.name = "y"  # type: ignore[misc]

    def test_to_record(self):
        e = GraphEntity(
            id="main.py::func",
            name="func",
            qualified_name="func",
            entity_type=EntityType.FUNCTION,
            file_path="main.py",
            start_line=1,
            end_line=5,
            chunk_id="chunk-1",
            metadata={"language": "python"},
        )
        record = e.to_record()
        assert record["id"] == "main.py::func"
        assert record["entity_type"] == "function"
        assert record["chunk_id"] == "chunk-1"
        assert '"language"' in record["metadata"]

    def test_with_chunk_id(self):
        e = GraphEntity(
            id="x",
            name="x",
            qualified_name="x",
            entity_type=EntityType.CLASS,
            file_path="x.py",
            start_line=1,
            end_line=10,
            chunk_id="chunk-42",
        )
        assert e.chunk_id == "chunk-42"


class TestGraphRelationship:
    def test_creation(self):
        r = GraphRelationship(
            id="a::calls::b",
            source_id="a",
            target_id="b",
            relationship=RelationshipType.CALLS,
            file_path="main.py",
        )
        assert r.relationship == RelationshipType.CALLS
        assert r.weight == 1.0
        assert r.metadata == {}

    def test_frozen(self):
        r = GraphRelationship(
            id="x",
            source_id="a",
            target_id="b",
            relationship=RelationshipType.IMPORTS,
            file_path="x.py",
        )
        with pytest.raises(AttributeError):
            r.weight = 2.0  # type: ignore[misc]

    def test_to_record(self):
        r = GraphRelationship(
            id="a::calls::b",
            source_id="a",
            target_id="b",
            relationship=RelationshipType.CALLS,
            file_path="main.py",
            weight=0.8,
            metadata={"line": 42},
        )
        record = r.to_record()
        assert record["relationship"] == "calls"
        assert record["weight"] == 0.8
        assert '"line"' in record["metadata"]


class TestGraphTraversalResult:
    def test_empty(self):
        result = GraphTraversalResult()
        assert result.entity_count == 0
        assert result.relationship_count == 0
        assert result.depth_reached == 0

    def test_with_data(self):
        e = GraphEntity(
            id="x",
            name="x",
            qualified_name="x",
            entity_type=EntityType.FUNCTION,
            file_path="x.py",
            start_line=1,
            end_line=2,
        )
        r = GraphRelationship(
            id="y",
            source_id="a",
            target_id="b",
            relationship=RelationshipType.CALLS,
            file_path="x.py",
        )
        result = GraphTraversalResult(
            entities=(e,), relationships=(r,), depth_reached=2
        )
        assert result.entity_count == 1
        assert result.relationship_count == 1
        assert result.depth_reached == 2


class TestFileGraphData:
    def test_empty(self):
        data = FileGraphData(file_path="main.py")
        assert data.file_path == "main.py"
        assert data.entities == ()
        assert data.relationships == ()

    def test_frozen(self):
        data = FileGraphData(file_path="main.py")
        with pytest.raises(AttributeError):
            data.file_path = "other.py"  # type: ignore[misc]


class TestGraphRAGConfig:
    def test_defaults(self):
        from local_deepwiki.config.models import GraphRAGConfig

        config = GraphRAGConfig()
        assert config.enabled is False
        assert config.max_traversal_depth == 2
        assert config.max_graph_neighbors == 15
        assert config.score_boost_factor == 0.7
        assert config.extract_during_index is True

    def test_enabled(self):
        from local_deepwiki.config.models import GraphRAGConfig

        config = GraphRAGConfig(enabled=True)
        assert config.enabled is True

    def test_config_has_graph_rag_field(self):
        from local_deepwiki.config.models import Config

        config = Config()
        assert config.graph_rag.enabled is False

    def test_traversal_depth_bounds(self):
        from pydantic import ValidationError

        from local_deepwiki.config.models import GraphRAGConfig

        with pytest.raises(ValidationError):
            GraphRAGConfig(max_traversal_depth=0)
        with pytest.raises(ValidationError):
            GraphRAGConfig(max_traversal_depth=5)
