"""GraphRAG — knowledge graph-augmented retrieval for code search.

Extracts entities and relationships from code during indexing and uses
graph traversal to expand vector search results with structurally related code.
"""

from __future__ import annotations

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
from local_deepwiki.core.graph_rag.extractor import GraphRelationshipExtractor
from local_deepwiki.core.graph_rag.retriever import GraphAugmentedRetriever
from local_deepwiki.core.graph_rag.store import KnowledgeGraphStore

__all__ = [
    "EntityType",
    "FileGraphData",
    "GraphAugmentedRetriever",
    "GraphEntity",
    "GraphRelationship",
    "GraphRelationshipExtractor",
    "GraphTraversalResult",
    "KnowledgeGraphStore",
    "RelationshipType",
    "entity_id",
    "relationship_id",
]
