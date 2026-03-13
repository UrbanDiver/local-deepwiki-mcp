"""Data models for the GraphRAG knowledge graph.

Defines entities (functions, classes, modules), relationships (calls, imports,
inherits), and traversal results used throughout the graph_rag package.
All models are frozen dataclasses with ``slots=True`` for immutability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EntityType(StrEnum):
    """Types of code entities in the knowledge graph."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    VARIABLE = "variable"


class RelationshipType(StrEnum):
    """Types of relationships between code entities."""

    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS_FROM = "inherits_from"
    CONTAINS = "contains"
    REFERENCES = "references"


def entity_id(file_path: str, qualified_name: str) -> str:
    """Generate a deterministic entity ID.

    Args:
        file_path: Source file path.
        qualified_name: Fully qualified entity name (e.g. "MyClass.my_method").

    Returns:
        Deterministic string ID in the form ``file_path::qualified_name``.
    """
    return f"{file_path}::{qualified_name}"


def relationship_id(
    source_id: str, rel_type: str | RelationshipType, target_id: str
) -> str:
    """Generate a deterministic relationship ID.

    Args:
        source_id: Source entity ID.
        rel_type: Relationship type.
        target_id: Target entity ID.

    Returns:
        Deterministic string ID in the form ``source_id::rel_type::target_id``.
    """
    return f"{source_id}::{rel_type}::{target_id}"


@dataclass(frozen=True, slots=True)
class GraphEntity:
    """A code entity node in the knowledge graph."""

    id: str
    name: str
    qualified_name: str
    entity_type: EntityType
    file_path: str
    start_line: int
    end_line: int
    chunk_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Serialize to a dict suitable for LanceDB storage."""
        import json

        return {
            "id": self.id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "entity_type": self.entity_type.value,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_id": self.chunk_id,
            "metadata": json.dumps(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class GraphRelationship:
    """A directed relationship edge in the knowledge graph."""

    id: str
    source_id: str
    target_id: str
    relationship: RelationshipType
    file_path: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Serialize to a dict suitable for LanceDB storage."""
        import json

        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship.value,
            "file_path": self.file_path,
            "weight": self.weight,
            "metadata": json.dumps(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class GraphTraversalResult:
    """Result of a graph traversal (BFS from seed entities)."""

    entities: tuple[GraphEntity, ...] = ()
    relationships: tuple[GraphRelationship, ...] = ()
    depth_reached: int = 0

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)


@dataclass(frozen=True, slots=True)
class FileGraphData:
    """Extracted graph data from a single source file."""

    file_path: str
    entities: tuple[GraphEntity, ...] = ()
    relationships: tuple[GraphRelationship, ...] = ()
