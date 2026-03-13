"""LanceDB-backed storage for the GraphRAG knowledge graph.

Manages two tables — ``graph_entities`` and ``graph_edges`` — that store
code entities (functions, classes, modules) and the relationships between
them (calls, imports, inherits_from, contains, references).

Thread-safe via ``threading.RLock`` following the same lazy-connect pattern
as :class:`~local_deepwiki.core.vectorstore.store.VectorStore`.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import lancedb
from lancedb.table import Table

from local_deepwiki.logging import get_logger

from .models import (
    EntityType,
    GraphEntity,
    GraphRelationship,
    GraphTraversalResult,
    RelationshipType,
)

logger = get_logger(__name__)


def _sanitize_string_value(value: str) -> str:
    """Escape single quotes for safe use in LanceDB filter expressions."""
    return value.replace("'", "''")


def _create_index_safe(table: Table, column: str) -> None:
    """Create a scalar index on *column*, silently ignoring failures."""
    try:
        table.create_scalar_index(column)
        logger.debug("Created scalar index on '%s'", column)
    except (ValueError, RuntimeError, OSError) as exc:
        logger.debug("Could not create index on '%s': %s", column, exc)


class KnowledgeGraphStore:
    """LanceDB-backed store for code entities and relationships.

    Parameters
    ----------
    db_path:
        Path to the LanceDB database directory (same path used by
        :class:`~local_deepwiki.core.vectorstore.store.VectorStore`).
    """

    ENTITIES_TABLE = "graph_entities"
    EDGES_TABLE = "graph_edges"

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._db: lancedb.DBConnection | None = None
        self._entities_table: Table | None = None
        self._edges_table: Table | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _connect(self) -> lancedb.DBConnection:
        """Lazy, thread-safe database connection."""
        if self._db is None:
            with self._lock:
                if self._db is None:
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    self._db = lancedb.connect(str(self.db_path))
        return self._db

    def _get_entities_table(self) -> Table | None:
        """Return the entities table if it exists, creating indexes on first access."""
        if self._entities_table is None:
            with self._lock:
                if self._entities_table is None:
                    db = self._connect()
                    if self.ENTITIES_TABLE in db.list_tables().tables:
                        self._entities_table = db.open_table(self.ENTITIES_TABLE)
                        _create_index_safe(self._entities_table, "id")
                        _create_index_safe(self._entities_table, "file_path")
                        _create_index_safe(self._entities_table, "chunk_id")
        return self._entities_table

    def _get_edges_table(self) -> Table | None:
        """Return the edges table if it exists, creating indexes on first access."""
        if self._edges_table is None:
            with self._lock:
                if self._edges_table is None:
                    db = self._connect()
                    if self.EDGES_TABLE in db.list_tables().tables:
                        self._edges_table = db.open_table(self.EDGES_TABLE)
                        _create_index_safe(self._edges_table, "id")
                        _create_index_safe(self._edges_table, "source_id")
                        _create_index_safe(self._edges_table, "target_id")
                        _create_index_safe(self._edges_table, "file_path")
        return self._edges_table

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add_entities(self, entities: list[GraphEntity]) -> int:
        """Batch-insert entities into the graph.

        Returns the number of entities added.
        """
        if not entities:
            return 0

        records = [e.to_record() for e in entities]
        db = self._connect()

        with self._lock:
            table = self._get_entities_table()
            if table is None:
                self._entities_table = db.create_table(self.ENTITIES_TABLE, records)
                _create_index_safe(self._entities_table, "id")
                _create_index_safe(self._entities_table, "file_path")
                _create_index_safe(self._entities_table, "chunk_id")
            else:
                table.add(records)

        logger.debug("Added %d entities", len(records))
        return len(records)

    async def add_relationships(self, relationships: list[GraphRelationship]) -> int:
        """Batch-insert relationships (edges) into the graph.

        Returns the number of relationships added.
        """
        if not relationships:
            return 0

        records = [r.to_record() for r in relationships]
        db = self._connect()

        with self._lock:
            table = self._get_edges_table()
            if table is None:
                self._edges_table = db.create_table(self.EDGES_TABLE, records)
                _create_index_safe(self._edges_table, "id")
                _create_index_safe(self._edges_table, "source_id")
                _create_index_safe(self._edges_table, "target_id")
                _create_index_safe(self._edges_table, "file_path")
            else:
                table.add(records)

        logger.debug("Added %d relationships", len(records))
        return len(records)

    async def delete_by_file(self, file_path: str) -> None:
        """Delete all entities *and* edges associated with *file_path*.

        Used for incremental re-indexing of a single file.
        """
        safe_path = _sanitize_string_value(file_path)
        filter_expr = f"file_path = '{safe_path}'"

        entities_table = self._get_entities_table()
        if entities_table is not None:
            entities_table.delete(filter_expr)

        edges_table = self._get_edges_table()
        if edges_table is not None:
            edges_table.delete(filter_expr)

        logger.debug("Deleted graph data for file: %s", file_path)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Look up a single entity by its deterministic ID."""
        table = self._get_entities_table()
        if table is None:
            return None

        safe_id = _sanitize_string_value(entity_id)
        rows = table.search().where(f"id = '{safe_id}'").limit(1).to_list()
        if not rows:
            return None
        return self._record_to_entity(rows[0])

    async def get_entities_by_chunk_ids(
        self, chunk_ids: list[str]
    ) -> list[GraphEntity]:
        """Return all entities whose ``chunk_id`` is in *chunk_ids*."""
        if not chunk_ids:
            return []

        table = self._get_entities_table()
        if table is None:
            return []

        safe_ids = [_sanitize_string_value(cid) for cid in chunk_ids]
        in_clause = ", ".join(f"'{cid}'" for cid in safe_ids)
        filter_expr = f"chunk_id IN ({in_clause})"

        rows = (
            table.search()
            .where(filter_expr)
            .limit(len(chunk_ids) * 10)  # generous upper bound
            .to_list()
        )
        return [self._record_to_entity(r) for r in rows]

    async def get_neighbors(
        self,
        entity_ids: list[str],
        relationship_types: list[str] | None = None,
        direction: str = "both",
        max_depth: int = 1,
    ) -> GraphTraversalResult:
        """BFS traversal from *entity_ids*.

        Parameters
        ----------
        entity_ids:
            Seed entity IDs to start traversal from.
        relationship_types:
            If provided, only follow edges whose ``relationship`` is in the
            list.  ``None`` means follow all relationship types.
        direction:
            ``"outgoing"`` — entity is ``source_id``.
            ``"incoming"`` — entity is ``target_id``.
            ``"both"`` — follow edges in either direction.
        max_depth:
            Maximum number of hops (BFS levels).

        Returns
        -------
        GraphTraversalResult
            All discovered entities and relationships within *max_depth* hops.
        """
        edges_table = self._get_edges_table()
        entities_table = self._get_entities_table()
        if edges_table is None or entities_table is None:
            return GraphTraversalResult()

        visited_entity_ids: set[str] = set(entity_ids)
        all_relationships: list[GraphRelationship] = []
        frontier: set[str] = set(entity_ids)
        depth_reached = 0

        for depth in range(1, max_depth + 1):
            if not frontier:
                break

            edges = self._fetch_edges(
                edges_table, frontier, relationship_types, direction
            )
            if not edges:
                break

            depth_reached = depth
            next_frontier: set[str] = set()
            for edge in edges:
                all_relationships.append(edge)
                # Determine the "other side" entity ID
                neighbor_ids_for_edge: set[str] = set()
                if edge.source_id in frontier:
                    neighbor_ids_for_edge.add(edge.target_id)
                if edge.target_id in frontier:
                    neighbor_ids_for_edge.add(edge.source_id)

                for nid in neighbor_ids_for_edge:
                    if nid not in visited_entity_ids:
                        visited_entity_ids.add(nid)
                        next_frontier.add(nid)

            frontier = next_frontier

        # Fetch all discovered entity objects
        all_entities = self._fetch_entities_by_ids(entities_table, visited_entity_ids)

        return GraphTraversalResult(
            entities=tuple(all_entities),
            relationships=tuple(all_relationships),
            depth_reached=depth_reached,
        )

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    async def get_entity_count(self) -> int:
        """Return the total number of entities in the graph."""
        table = self._get_entities_table()
        if table is None:
            return 0
        return table.count_rows()

    async def get_relationship_count(self) -> int:
        """Return the total number of relationships in the graph."""
        table = self._get_edges_table()
        if table is None:
            return 0
        return table.count_rows()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release all resources.  Safe to call multiple times."""
        with self._lock:
            self._entities_table = None
            self._edges_table = None
            self._db = None

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_entity(row: dict[str, Any]) -> GraphEntity:
        """Deserialize a LanceDB row dict into a :class:`GraphEntity`."""
        metadata_raw = row.get("metadata", "{}")
        metadata = (
            json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
        )

        return GraphEntity(
            id=row["id"],
            name=row["name"],
            qualified_name=row["qualified_name"],
            entity_type=EntityType(row["entity_type"]),
            file_path=row["file_path"],
            start_line=int(row["start_line"]),
            end_line=int(row["end_line"]),
            chunk_id=row.get("chunk_id", ""),
            metadata=metadata if metadata else {},
        )

    @staticmethod
    def _record_to_relationship(row: dict[str, Any]) -> GraphRelationship:
        """Deserialize a LanceDB row dict into a :class:`GraphRelationship`."""
        metadata_raw = row.get("metadata", "{}")
        metadata = (
            json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
        )

        return GraphRelationship(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relationship=RelationshipType(row["relationship"]),
            file_path=row["file_path"],
            weight=float(row.get("weight", 1.0)),
            metadata=metadata if metadata else {},
        )

    # ------------------------------------------------------------------
    # Internal query helpers
    # ------------------------------------------------------------------

    def _fetch_edges(
        self,
        edges_table: Table,
        frontier_ids: set[str],
        relationship_types: list[str] | None,
        direction: str,
    ) -> list[GraphRelationship]:
        """Fetch all edges touching *frontier_ids* in the given *direction*."""
        safe_ids = [_sanitize_string_value(eid) for eid in frontier_ids]
        id_list = ", ".join(f"'{eid}'" for eid in safe_ids)

        clauses: list[str] = []
        if direction in ("outgoing", "both"):
            clauses.append(f"source_id IN ({id_list})")
        if direction in ("incoming", "both"):
            clauses.append(f"target_id IN ({id_list})")

        if not clauses:
            return []

        filter_expr = " OR ".join(clauses)

        if relationship_types:
            safe_types = [_sanitize_string_value(rt) for rt in relationship_types]
            types_list = ", ".join(f"'{rt}'" for rt in safe_types)
            filter_expr = f"({filter_expr}) AND relationship IN ({types_list})"

        rows = edges_table.search().where(filter_expr).limit(10_000).to_list()
        return [self._record_to_relationship(r) for r in rows]

    def _fetch_entities_by_ids(
        self, entities_table: Table, entity_ids: set[str]
    ) -> list[GraphEntity]:
        """Fetch entities whose ``id`` is in *entity_ids*."""
        if not entity_ids:
            return []

        safe_ids = [_sanitize_string_value(eid) for eid in entity_ids]
        id_list = ", ".join(f"'{eid}'" for eid in safe_ids)
        filter_expr = f"id IN ({id_list})"

        rows = (
            entities_table.search()
            .where(filter_expr)
            .limit(len(entity_ids) + 10)
            .to_list()
        )
        return [self._record_to_entity(r) for r in rows]
