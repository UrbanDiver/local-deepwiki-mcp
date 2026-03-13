"""Repository indexing orchestration with incremental update support."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.graph_rag.extractor import GraphRelationshipExtractor
from local_deepwiki.core.graph_rag.models import FileGraphData
from local_deepwiki.core.graph_rag.store import KnowledgeGraphStore
from local_deepwiki.core.index_manager import (
    CURRENT_SCHEMA_VERSION,
    INDEX_STATUS_FILE,
    IndexStatusManager,
)
from local_deepwiki.core.parser import ASTCache, CodeParser
from local_deepwiki.core.parsing_pipeline import FileParsingPipeline, ParseResult
from local_deepwiki.core.secret_detector import scan_repository_for_secrets
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, FileInfo, IndexStatus, ProgressCallback
from local_deepwiki.providers.embeddings import get_embedding_provider

if TYPE_CHECKING:
    from local_deepwiki.handlers.types import SearchResult

logger = get_logger(__name__)


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "INDEX_STATUS_FILE",
    "ParseResult",
    "RepositoryIndexer",
]


class RepositoryIndexer:
    """Orchestrates repository indexing with incremental update support."""

    # Backward compatibility: keep class constant
    INDEX_STATUS_FILE = INDEX_STATUS_FILE

    def __init__(
        self,
        repo_path: Path,
        config: Config | None = None,
        embedding_provider_name: str | None = None,
    ):
        """Initialize the indexer.

        Args:
            repo_path: Path to the repository root.
            config: Optional configuration.
            embedding_provider_name: Override embedding provider ("local" or "openai").
        """
        self.repo_path = repo_path.resolve()
        base_config = config or get_config()

        # Create a copy with overridden embedding provider if specified
        if embedding_provider_name:
            self.config = base_config.with_embedding_provider(embedding_provider_name)
        else:
            # Store a defensive copy to prevent external mutation
            self.config = base_config.model_copy(deep=True)

        self.wiki_path = self.config.get_wiki_path(self.repo_path)
        self.vector_db_path = self.config.get_vector_db_path(self.repo_path)

        # Create AST cache if enabled
        self.ast_cache: ASTCache | None = None
        if self.config.ast_cache.enabled:
            self.ast_cache = ASTCache(
                max_entries=self.config.ast_cache.max_entries,
                ttl_seconds=self.config.ast_cache.ttl_seconds,
            )
            logger.debug(
                "AST cache enabled: max_entries=%d, ttl=%ds",
                self.config.ast_cache.max_entries,
                self.config.ast_cache.ttl_seconds,
            )

        self.parser = CodeParser(cache=self.ast_cache)
        self.chunker = CodeChunker(self.config.chunking)
        self.embedding_provider = get_embedding_provider(self.config.embedding)
        self.vector_store = VectorStore(self.vector_db_path, self.embedding_provider)

        # GraphRAG: optional knowledge graph store and extractor
        self._graph_enabled = (
            self.config.graph_rag.enabled and self.config.graph_rag.extract_during_index
        )
        self.graph_store: KnowledgeGraphStore | None = None
        self._graph_extractor: GraphRelationshipExtractor | None = None
        if self._graph_enabled:
            self.graph_store = KnowledgeGraphStore(self.vector_db_path)
            self._graph_extractor = GraphRelationshipExtractor()
            logger.debug("GraphRAG extraction enabled during indexing")

        # Use IndexStatusManager for all status operations
        self._status_manager = IndexStatusManager()

        # Pre-compile exclude patterns (config is frozen, so these never change)
        self._exclude_skip_dirs: set[str] = set()
        self._exclude_compiled: list = []
        self._compile_exclude_patterns()

    def _compile_exclude_patterns(self) -> None:
        """Pre-compile exclude patterns from config into skip_dirs and regexes."""
        for pattern in self.config.parsing.exclude_patterns:
            if pattern.endswith("/**"):
                self._exclude_skip_dirs.add(pattern[:-3])
            else:
                self._exclude_compiled.append(re.compile(fnmatch.translate(pattern)))

    async def _scan_for_secrets(
        self,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Scan repository for hardcoded secrets before indexing.

        This method warns about potential secrets but does not fail indexing.
        Users should remediate the findings, but indexing can proceed.

        Args:
            progress_callback: Optional callback for progress updates.
        """
        if progress_callback:
            progress_callback("Scanning for hardcoded secrets...", 0, 1)

        logger.info("Scanning for hardcoded secrets...")

        secret_findings = await asyncio.to_thread(scan_repository_for_secrets, self.repo_path)

        if secret_findings:
            total_secrets = sum(len(findings) for findings in secret_findings.values())
            logger.warning(
                "SECURITY WARNING: Found %d potential secret(s) in %d file(s)",
                total_secrets,
                len(secret_findings),
            )

            # Log each finding with recommendations
            for file_path, findings in secret_findings.items():
                for finding in findings:
                    logger.warning(
                        "  [%s] %s:%d (confidence: %.0f%%)",
                        finding.secret_type.value,
                        finding.file_path,
                        finding.line_number,
                        finding.confidence * 100,
                    )
                    logger.warning("    Context: %s", finding.context)
                    logger.warning("    Recommendation: %s", finding.recommendation)

            logger.warning(
                "Please remediate these findings before sharing or deploying this code. "
                "Indexing will continue, but secrets may appear in search results."
            )

            # Emit event for secret detection
            emitter = get_event_emitter()
            await emitter.emit(
                EventType.INDEX_ERROR,
                {
                    "repo_path": str(self.repo_path),
                    "error": f"Found {total_secrets} potential hardcoded secrets",
                    "severity": "warning",
                    "secret_count": total_secrets,
                    "affected_files": len(secret_findings),
                },
            )
        else:
            logger.info("No hardcoded secrets detected")

    def _create_parsing_pipeline(self) -> FileParsingPipeline:
        """Create a FileParsingPipeline from current indexer state."""
        return FileParsingPipeline(
            parser=self.parser,
            chunker=self.chunker,
            repo_path=self.repo_path,
            vector_store=self.vector_store,
            batch_size=self.config.chunking.batch_size,
            parallel_workers=self.config.chunking.parallel_workers,
            pipeline_logger=logger,
        )

    def _parse_single_file(self, file_path: Path) -> ParseResult:
        """Parse and chunk a single file. Delegates to FileParsingPipeline."""
        return self._create_parsing_pipeline().parse_single_file(file_path)

    def _load_previous_status(
        self, full_rebuild: bool
    ) -> tuple[IndexStatus | None, dict[str, FileInfo], bool]:
        """Load and validate previous index status for incremental updates.

        Args:
            full_rebuild: If True, skip loading previous status.

        Returns:
            Tuple of (previous_status, prev_files_by_path, full_rebuild_required).
            prev_files_by_path is a hash map for O(1) lookups.
            full_rebuild_required may be True if schema migration requires it.
        """
        if full_rebuild:
            return None, {}, full_rebuild

        previous_status, requires_rebuild = self._status_manager.load_with_migration_info(
            self.wiki_path
        )
        if requires_rebuild:
            logger.info("Schema migration requires full rebuild")
            return None, {}, True

        if previous_status:
            logger.debug("Loaded previous index status: %d files", previous_status.total_files)
            # Pre-build hash map for O(1) lookups instead of O(N) linear scan per file
            # This reduces O(N*M) to O(N+M) for file comparison
            prev_files_by_path = {f.path: f for f in previous_status.files}
            return previous_status, prev_files_by_path, full_rebuild

        return None, {}, full_rebuild

    def _collect_files_to_process(
        self,
        prev_files_by_path: dict[str, FileInfo],
        progress_callback: ProgressCallback | None,
    ) -> tuple[list[Path], list[FileInfo], list[str]]:
        """Gather source files and determine what needs processing.

        Args:
            prev_files_by_path: Hash map of previous files for O(1) lookup.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (files_to_process, files_unchanged, deleted_file_paths).
            deleted_file_paths contains relative paths of files that existed in the
            previous index but are no longer present on disk.
        """
        source_files = list(self._find_source_files())
        logger.info("Found %s source files to consider", len(source_files))

        if progress_callback:
            progress_callback("Found source files", len(source_files), len(source_files))

        files_to_process: list[Path] = []
        files_unchanged: list[FileInfo] = []

        # Track current file paths for deleted file detection
        current_file_paths: set[str] = set()

        for file_path in source_files:
            file_info = self.parser.get_file_info(file_path, self.repo_path)
            current_file_paths.add(file_info.path)

            if prev_files_by_path:
                # Check if file has changed using O(1) dict lookup
                prev_file = prev_files_by_path.get(file_info.path)
                if prev_file and prev_file.hash == file_info.hash:
                    files_unchanged.append(prev_file)
                    continue

            files_to_process.append(file_path)

        # Detect files that existed in the previous index but no longer exist on disk
        deleted_file_paths = [path for path in prev_files_by_path if path not in current_file_paths]

        if deleted_file_paths:
            logger.info(
                "Detected %d deleted file(s): %s",
                len(deleted_file_paths),
                deleted_file_paths,
            )

        if progress_callback:
            progress_callback(
                f"Processing {len(files_to_process)} files "
                f"({len(files_unchanged)} unchanged, {len(deleted_file_paths)} deleted)",
                0,
                len(files_to_process),
            )

        return files_to_process, files_unchanged, deleted_file_paths

    async def _delete_old_chunks_for_modified_files(
        self,
        files_to_process: list[Path],
        prev_files_by_path: dict[str, FileInfo],
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Batch delete old chunks for files being re-processed.

        This avoids N+1 delete problem by doing a single batch delete upfront.

        Args:
            files_to_process: List of file paths to be processed.
            prev_files_by_path: Hash map of previous files for O(1) lookup.
            progress_callback: Optional callback for progress updates.
        """
        files_to_delete = []
        for file_path in files_to_process:
            file_info = self.parser.get_file_info(file_path, self.repo_path)
            # Only delete if file existed in previous index (was modified, not new)
            # Use O(1) dict lookup instead of O(N) linear scan
            if file_info.path in prev_files_by_path:
                files_to_delete.append(file_info.path)

        if files_to_delete:
            if progress_callback:
                progress_callback(
                    f"Removing old chunks for {len(files_to_delete)} modified files...",
                    0,
                    len(files_to_process),
                )
            await self.vector_store.delete_chunks_by_files(files_to_delete)
            logger.debug("Batch deleted chunks for %d modified files", len(files_to_delete))

    async def _delete_chunks_for_deleted_files(
        self,
        deleted_file_paths: list[str],
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Delete chunks from the vector store for files that no longer exist on disk.

        Args:
            deleted_file_paths: Relative paths of deleted files.
            progress_callback: Optional callback for progress updates.
        """
        if progress_callback:
            progress_callback(
                f"Removing stale chunks for {len(deleted_file_paths)} deleted file(s)...",
                0,
                len(deleted_file_paths),
            )
        await self.vector_store.delete_chunks_by_files(deleted_file_paths)
        logger.info(
            "Cleaned up chunks for %d deleted file(s): %s",
            len(deleted_file_paths),
            deleted_file_paths,
        )

    def _extract_graph_for_file(
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
            logger.warning(
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
                logger.warning(
                    "Entity-chunk linking failed for %s, using unlinked entities",
                    rel_path,
                    exc_info=True,
                )

        return graph_data

    async def _run_graph_extraction(
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

        emitter = get_event_emitter()
        await emitter.emit(
            EventType.GRAPH_EXTRACT_START,
            {
                "repo_path": str(self.repo_path),
                "file_count": len(files_to_process),
            },
        )

        if progress_callback:
            progress_callback(
                f"Extracting graph entities from {len(files_to_process)} files...",
                0,
                len(files_to_process),
            )

        total_entities = 0
        total_relationships = 0

        # For incremental re-indexing, delete old graph data for modified files
        if not full_rebuild and prev_files_by_path:
            for file_path in files_to_process:
                rel_path = str(file_path.relative_to(self.repo_path))
                if rel_path in prev_files_by_path:
                    try:
                        await self.graph_store.delete_by_file(rel_path)
                    except Exception:
                        logger.warning(
                            "Failed to delete old graph data for %s",
                            rel_path,
                            exc_info=True,
                        )

        # Delete graph data for files that no longer exist
        for deleted_path in deleted_file_paths:
            try:
                await self.graph_store.delete_by_file(deleted_path)
            except Exception:
                logger.warning(
                    "Failed to delete graph data for deleted file %s",
                    deleted_path,
                    exc_info=True,
                )

        # Extract graph data for each processed file
        for idx, file_path in enumerate(files_to_process):
            rel_path = str(file_path.relative_to(self.repo_path))
            chunks = file_chunks.get(rel_path, [])

            graph_data = await asyncio.to_thread(self._extract_graph_for_file, file_path, chunks)

            if graph_data is None:
                continue

            try:
                if graph_data.entities:
                    entity_count = await self.graph_store.add_entities(list(graph_data.entities))
                    total_entities += entity_count

                if graph_data.relationships:
                    rel_count = await self.graph_store.add_relationships(
                        list(graph_data.relationships)
                    )
                    total_relationships += rel_count
            except Exception:
                logger.warning(
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

        await emitter.emit(
            EventType.GRAPH_EXTRACT_COMPLETE,
            {
                "repo_path": str(self.repo_path),
                "total_entities": total_entities,
                "total_relationships": total_relationships,
            },
        )

        logger.info(
            "Graph extraction complete: %d entities, %d relationships",
            total_entities,
            total_relationships,
        )

    async def _parse_files_parallel(
        self,
        files_to_process: list[Path],
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
    ) -> tuple[list[FileInfo], int, dict[str, list[CodeChunk]]]:
        """Handle parallel file parsing. Delegates to FileParsingPipeline.

        Returns:
            Tuple of (processed_files, total_chunks_processed, file_chunks).
            file_chunks maps relative file paths to their extracted code chunks,
            used by graph extraction to link entities to chunks.
        """
        file_chunks: dict[str, list[CodeChunk]] = {}

        if self._graph_enabled:
            # Collect per-file chunks for graph entity-chunk linking.
            # Dict assignment is atomic under CPython GIL; each thread writes
            # to a unique key so no contention occurs.
            def _collecting_parse(file_path: Path) -> ParseResult:
                result = self._parse_single_file(file_path)
                if not result.error and result.chunks:
                    rel_path = str(file_path.relative_to(self.repo_path))
                    file_chunks[rel_path] = list(result.chunks)
                return result

            parse_fn = _collecting_parse
        else:
            parse_fn = self._parse_single_file

        pipeline = self._create_parsing_pipeline()
        processed_files, total_chunks = await pipeline.parse_files_parallel(
            files_to_process,
            full_rebuild,
            progress_callback,
            parse_fn=parse_fn,
        )
        return processed_files, total_chunks, file_chunks

    def _create_index_status(
        self,
        processed_files: list[FileInfo],
        files_unchanged: list[FileInfo],
        total_chunks_processed: int,
    ) -> IndexStatus:
        """Create the final index status with statistics.

        Args:
            processed_files: List of files that were processed.
            files_unchanged: List of files that were unchanged.
            total_chunks_processed: Number of chunks processed in this run.

        Returns:
            IndexStatus with complete indexing results.
        """
        all_files, total_chunks = self._status_manager.merge_files(
            processed_files, files_unchanged, total_chunks_processed
        )

        return self._status_manager.create(
            repo_path=self.repo_path,
            files=all_files,
            total_chunks=total_chunks,
        )

    def _save_index_status(self, status: IndexStatus) -> None:
        """Save the final index status and log completion.

        Args:
            status: The IndexStatus to save.
        """
        self._status_manager.save(self.wiki_path, status)
        logger.info(
            "Indexing complete: %d files, %d chunks, languages: %s",
            status.total_files,
            status.total_chunks,
            list(status.languages.keys()),
        )

        # Log AST cache statistics if enabled
        if self.ast_cache is not None:
            cache_stats = self.ast_cache.get_stats()
            logger.info(
                "AST cache stats: hits=%d, misses=%d, hit_rate=%.2f%%, entries=%d, memory=%.1fKB",
                cache_stats["hits"],
                cache_stats["misses"],
                cache_stats["hit_rate"] * 100,
                cache_stats["total_entries"],
                cache_stats["estimated_memory_bytes"] / 1024,
            )

    async def index(
        self,
        full_rebuild: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexStatus:
        """Index the repository.

        This method coordinates the indexing process by delegating to
        focused private methods for each phase of the operation.

        Args:
            full_rebuild: If True, rebuild entire index. Otherwise, incremental update.
            progress_callback: Optional callback for progress updates (message, current, total).

        Returns:
            IndexStatus with indexing results.
        """
        # Ensure wiki directory exists
        await asyncio.to_thread(self.wiki_path.mkdir, parents=True, exist_ok=True)

        logger.info("Starting indexing for repository: %s", self.repo_path)
        logger.debug("Wiki path: %s, Full rebuild: %s", self.wiki_path, full_rebuild)

        # Emit INDEX_START event
        emitter = get_event_emitter()
        await emitter.emit(
            EventType.INDEX_START,
            {
                "repo_path": str(self.repo_path),
                "full_rebuild": full_rebuild,
            },
        )

        # Security: Scan for hardcoded secrets before indexing
        await self._scan_for_secrets(progress_callback)

        # Phase 1: Load previous status for incremental updates
        previous_status, prev_files_by_path, full_rebuild = await asyncio.to_thread(
            self._load_previous_status, full_rebuild
        )

        # Phase 2: Collect files to process (and detect deleted files)
        files_to_process, files_unchanged, deleted_file_paths = self._collect_files_to_process(
            prev_files_by_path, progress_callback
        )

        # Phase 3: Delete old chunks for modified and deleted files (incremental only)
        if not full_rebuild and prev_files_by_path:
            if files_to_process:
                await self._delete_old_chunks_for_modified_files(
                    files_to_process, prev_files_by_path, progress_callback
                )
            if deleted_file_paths:
                await self._delete_chunks_for_deleted_files(deleted_file_paths, progress_callback)

        # Phase 4: Parse files in parallel and store chunks
        (
            processed_files,
            total_chunks_processed,
            file_chunks,
        ) = await self._parse_files_parallel(files_to_process, full_rebuild, progress_callback)

        # Phase 5: Graph extraction (optional, non-blocking)
        if self._graph_enabled and files_to_process:
            try:
                await self._run_graph_extraction(
                    files_to_process=files_to_process,
                    file_chunks=file_chunks,
                    prev_files_by_path=prev_files_by_path,
                    deleted_file_paths=deleted_file_paths,
                    full_rebuild=full_rebuild,
                    progress_callback=progress_callback,
                )
            except Exception:
                logger.warning(
                    "Graph extraction failed, continuing without graph data",
                    exc_info=True,
                )

        # Phase 6: Create and save index status
        status = self._create_index_status(processed_files, files_unchanged, total_chunks_processed)
        await asyncio.to_thread(self._save_index_status, status)

        if progress_callback:
            progress_callback("Indexing complete", 1, 1)

        # Emit INDEX_COMPLETE event
        await emitter.emit(
            EventType.INDEX_COMPLETE,
            {
                "repo_path": str(self.repo_path),
                "total_files": status.total_files,
                "total_chunks": status.total_chunks,
                "languages": list(status.languages.keys()),
            },
        )

        return status

    def _find_source_files(self) -> list[Path]:
        """Find all source files in the repository.

        Uses os.walk() with early directory filtering to skip excluded
        directories entirely (e.g., node_modules, .git, vendor) instead
        of traversing them and checking each file.

        Returns:
            List of paths to source files.
        """
        files = []
        max_size = self.config.parsing.max_file_size
        skip_dirs = self._exclude_skip_dirs
        compiled_patterns = self._exclude_compiled

        for root, dirs, filenames in os.walk(self.repo_path):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.repo_path)

            # Early directory filtering - modify dirs in-place to skip subdirs
            dirs[:] = [
                d
                for d in dirs
                if d not in skip_dirs
                and str(rel_root / d) not in skip_dirs
                and not d.startswith(".")  # Skip hidden directories
            ]

            for filename in filenames:
                file_path = root_path / filename
                rel_path = str(file_path.relative_to(self.repo_path))

                # Check against pre-compiled file patterns
                if any(p.match(rel_path) for p in compiled_patterns):
                    continue

                # Check file size
                try:
                    if file_path.stat().st_size > max_size:
                        continue
                except OSError:
                    continue

                # Check if language is supported
                language = self.parser.detect_language(file_path)
                if language is None:
                    continue

                # Check if language is in configured list
                if language.value not in self.config.parsing.languages:
                    continue

                files.append(file_path)

        return files

    def _load_status(self) -> tuple[IndexStatus | None, bool]:
        """Load previous indexing status and check for migration needs.

        Returns:
            Tuple of (IndexStatus or None, requires_rebuild).
            requires_rebuild is True if the index should be fully rebuilt.
        """
        return self._status_manager.load_with_migration_info(self.wiki_path)

    def _save_status(self, status: IndexStatus) -> None:
        """Save indexing status.

        Args:
            status: The IndexStatus to save.
        """
        self._status_manager.save(self.wiki_path, status)

    def get_status(self) -> IndexStatus | None:
        """Get the current indexing status.

        Returns:
            IndexStatus or None if not indexed.
        """
        return self._status_manager.load(self.wiki_path)

    async def search(
        self,
        query: str,
        limit: int = 10,
        language: str | None = None,
    ) -> list[SearchResult]:
        """Search the indexed repository.

        Args:
            query: Search query.
            limit: Maximum results.
            language: Optional language filter.

        Returns:
            List of search result dictionaries.
        """
        results = await self.vector_store.search(query, limit=limit, language=language)
        return [
            {
                "file_path": r.chunk.file_path,
                "name": r.chunk.name or "",
                "type": r.chunk.chunk_type.value,
                "language": r.chunk.language.value,
                "lines": f"{r.chunk.start_line}-{r.chunk.end_line}",
                "score": r.score,
                "content": (
                    r.chunk.content[:500] + "..." if len(r.chunk.content) > 500 else r.chunk.content
                ),
                "docstring": r.chunk.docstring,
            }
            for r in results
        ]
