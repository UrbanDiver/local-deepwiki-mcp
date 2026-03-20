"""Graph extraction concern extracted from RepositoryIndexer.

Handles knowledge-graph entity/relationship extraction during indexing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from local_deepwiki.core.graph_rag.extractor import GraphRelationshipExtractor
from local_deepwiki.core.graph_rag.models import FileGraphData
from local_deepwiki.events import EventType
from local_deepwiki.models import ProgressCallback

if TYPE_CHECKING:
    from local_deepwiki.core.graph_rag.store import KnowledgeGraphStore
    from local_deepwiki.core.parser import CodeParser
    from local_deepwiki.models import CodeChunk, FileInfo


class GraphExtractor:
    """Extracts graph entities and relationships from source files.

    This class encapsulates the graph extraction concern that was previously
    part of RepositoryIndexer, following the Single Responsibility Principle.

    Args:
        repo_path: Resolved path to the repository root.
        parser: CodeParser instance for AST parsing.
        graph_store: Optional KnowledgeGraphStore for persistence.
        graph_extractor: Optional GraphRelationshipExtractor for AST extraction.
        graph_enabled: Whether graph extraction is active.
        host_module: The parent module (``indexer``) whose ``logger`` and
            ``get_event_emitter`` attributes are used at call time, so that
            test patches applied to that module take effect.
    """

    def __init__(
        self,
        repo_path: Path,
        parser: CodeParser,
        graph_store: KnowledgeGraphStore | None,
        graph_extractor: GraphRelationshipExtractor | None,
        graph_enabled: bool,
        host_module: ModuleType,
    ) -> None:
        self.repo_path = repo_path
        self.parser = parser
        self.graph_store = graph_store
        self._graph_extractor = graph_extractor
        self._graph_enabled = graph_enabled
        self._host = host_module

    def extract_graph_for_file(
        self,
        file_path: Path,
        chunks: list[CodeChunk],
    ) -> FileGraphData | None:
        """Extract graph entities and relationships from a single file.

        This is a CPU-bound operation that runs in a thread pool. It parses the
        file's AST and extracts entities, then links them to existing code chunks.

        Args:
            file_path: Absolute path to the source file.
            chunks: Code chunks already extracted for this file.

        Returns:
            FileGraphData with entities and relationships, or None on failure.
        """
        if self._graph_extractor is None:
            return None

        parse_result = self.parser.parse_file(file_path)
        if parse_result is None:
            return None

        root_node, language, source_bytes = parse_result
        rel_path = str(file_path.relative_to(self.repo_path))

        try:
            graph_data = self._graph_extractor.extract_from_ast(
                root_node, source_bytes, language, rel_path
            )
        except Exception:
            self._host.logger.warning(
                "Graph extraction failed for %s, skipping",
                rel_path,
                exc_info=True,
            )
            return None

        # Link entities to their corresponding code chunks
        if graph_data.entities and chunks:
            try:
                linked_entities = GraphRelationshipExtractor.link_entities_to_chunks(
                    list(graph_data.entities), chunks
                )
                return FileGraphData(
                    file_path=graph_data.file_path,
                    entities=tuple(linked_entities),
                    relationships=graph_data.relationships,
                )
            except Exception:
                self._host.logger.warning(
                    "Entity-chunk linking failed for %s, using unlinked entities",
                    rel_path,
                    exc_info=True,
                )

        return graph_data

    async def emit_graph_start(self, files_to_process: list[Path]) -> None:
        """Emit the GRAPH_EXTRACT_START event."""
        emitter = self._host.get_event_emitter()
        await emitter.emit(
            EventType.GRAPH_EXTRACT_START,
            {
                "repo_path": str(self.repo_path),
                "file_count": len(files_to_process),
            },
        )

    async def delete_stale_graph_data(
        self,
        files_to_process: list[Path],
        prev_files_by_path: dict[str, FileInfo],
        deleted_file_paths: list[str],
        full_rebuild: bool,
    ) -> None:
        """Delete old graph data for modified and deleted files.

        Args:
            files_to_process: Files being re-processed in this run.
            prev_files_by_path: Previous index state for incremental detection.
            deleted_file_paths: Files removed since last index.
            full_rebuild: Whether this is a full rebuild (skips incremental deletion).
        """
        # For incremental re-indexing, delete old graph data for modified files
        if not full_rebuild and prev_files_by_path:
            for file_path in files_to_process:
                rel_path = str(file_path.relative_to(self.repo_path))
                if rel_path in prev_files_by_path:
                    try:
                        await self.graph_store.delete_by_file(rel_path)  # type: ignore[union-attr]
                    except Exception:
                        self._host.logger.warning(
                            "Failed to delete old graph data for %s",
                            rel_path,
                            exc_info=True,
                        )

        # Delete graph data for files that no longer exist
        for deleted_path in deleted_file_paths:
            try:
                await self.graph_store.delete_by_file(deleted_path)  # type: ignore[union-attr]
            except Exception:
                self._host.logger.warning(
                    "Failed to delete graph data for deleted file %s",
                    deleted_path,
                    exc_info=True,
                )

    async def extract_and_store_graph_data(
        self,
        files_to_process: list[Path],
        file_chunks: dict[str, list[CodeChunk]],
        progress_callback: ProgressCallback | None,
        extract_fn: Callable[[Path, list[CodeChunk]], FileGraphData | None]
        | None = None,
    ) -> tuple[int, int]:
        """Extract graph entities/relationships and store them for each file.

        Args:
            files_to_process: Files to extract graph data from.
            file_chunks: Mapping of relative file path to extracted chunks.
            progress_callback: Optional callback for progress updates.
            extract_fn: Optional override for the per-file extraction callable.
                Defaults to ``self.extract_graph_for_file``.

        Returns:
            Tuple of (total_entities, total_relationships) stored.
        """
        _extract = extract_fn or self.extract_graph_for_file
        total_entities = 0
        total_relationships = 0

        for idx, file_path in enumerate(files_to_process):
            rel_path = str(file_path.relative_to(self.repo_path))
            chunks = file_chunks.get(rel_path, [])

            graph_data = await asyncio.to_thread(_extract, file_path, chunks)

            if graph_data is None:
                continue

            try:
                if graph_data.entities:
                    entity_count = await self.graph_store.add_entities(
                        list(graph_data.entities)
                    )  # type: ignore[union-attr]
                    total_entities += entity_count

                if graph_data.relationships:
                    rel_count = await self.graph_store.add_relationships(  # type: ignore[union-attr]
                        list(graph_data.relationships)
                    )
                    total_relationships += rel_count
            except Exception:
                self._host.logger.warning(
                    "Failed to store graph data for %s",
                    rel_path,
                    exc_info=True,
                )

            if progress_callback:
                progress_callback(
                    f"Graph extraction: {rel_path}",
                    idx + 1,
                    len(files_to_process),
                )

        return total_entities, total_relationships

    async def emit_graph_complete(
        self, total_entities: int, total_relationships: int
    ) -> None:
        """Emit the GRAPH_EXTRACT_COMPLETE event and log summary.

        Args:
            total_entities: Total number of graph entities stored.
            total_relationships: Total number of graph relationships stored.
        """
        emitter = self._host.get_event_emitter()
        await emitter.emit(
            EventType.GRAPH_EXTRACT_COMPLETE,
            {
                "repo_path": str(self.repo_path),
                "total_entities": total_entities,
                "total_relationships": total_relationships,
            },
        )

        self._host.logger.info(
            "Graph extraction complete: %d entities, %d relationships",
            total_entities,
            total_relationships,
        )

    async def run_graph_extraction(
        self,
        files_to_process: list[Path],
        file_chunks: dict[str, list[CodeChunk]],
        prev_files_by_path: dict[str, FileInfo],
        deleted_file_paths: list[str],
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Run graph entity/relationship extraction for processed files.

        This phase runs after file parsing and chunk storage. It extracts
        entities and relationships from ASTs and stores them in the knowledge
        graph. Failures are logged but do not fail the overall indexing.

        Args:
            files_to_process: Files that were parsed in this indexing run.
            file_chunks: Mapping of relative file path to extracted chunks.
            prev_files_by_path: Previous index state for incremental detection.
            deleted_file_paths: Files removed since last index.
            full_rebuild: Whether this is a full rebuild.
            progress_callback: Optional callback for progress updates.
        """
        if not self._graph_enabled or self.graph_store is None:
            return

        await self.emit_graph_start(files_to_process)

        if progress_callback:
            progress_callback(
                f"Extracting graph entities from {len(files_to_process)} files...",
                0,
                len(files_to_process),
            )

        await self.delete_stale_graph_data(
            files_to_process, prev_files_by_path, deleted_file_paths, full_rebuild
        )
        total_entities, total_relationships = await self.extract_and_store_graph_data(
            files_to_process, file_chunks, progress_callback
        )
        await self.emit_graph_complete(total_entities, total_relationships)
