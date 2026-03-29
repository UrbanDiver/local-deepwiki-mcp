"""Repository indexing orchestration with incremental update support."""

from __future__ import annotations

import asyncio
import fnmatch
import re
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.graph_rag.extractor import GraphRelationshipExtractor
from local_deepwiki.core.graph_rag.store import KnowledgeGraphStore
from local_deepwiki.core.index_manager import (
    CURRENT_SCHEMA_VERSION,
    INDEX_STATUS_FILE,
    IndexStatusManager,
)
from local_deepwiki.core.indexer_files import find_source_files
from local_deepwiki.core.indexer_graph import GraphExtractor
from local_deepwiki.core.indexer_status import IndexStatusTracker
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
    "RepositoryIndexerProtocol",
]


@runtime_checkable
class RepositoryIndexerProtocol(Protocol):
    """Protocol defining the public interface for repository indexers.

    Handlers and services that drive the indexing pipeline should accept this
    Protocol rather than the concrete ``RepositoryIndexer`` so that:

    - Tests can pass lightweight stubs without constructing a full indexer.
    - Alternative indexer implementations (e.g. remote, read-only) can satisfy
      the contract without inheriting from the concrete class.
    """

    async def index(
        self,
        full_rebuild: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexStatus:
        """Index the repository and return the resulting status."""
        ...

    def get_status(self) -> IndexStatus | None:
        """Return the current index status, or None if not yet indexed."""
        ...

    async def search(
        self,
        query: str,
        limit: int = 10,
        language: str | None = None,
    ) -> list[SearchResult]:
        """Search the indexed repository and return matching chunks."""
        ...


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

        # Composition: delegate graph extraction and status tracking.
        # Use lazy lookups for logger/get_event_emitter so that test patches
        # applied to this module's globals are picked up at call time.
        import sys

        _this_module = sys.modules[__name__]
        self._graph_helper = GraphExtractor(
            repo_path=self.repo_path,
            parser=self.parser,
            graph_store=self.graph_store,
            graph_extractor=self._graph_extractor,
            graph_enabled=self._graph_enabled,
            host_module=_this_module,
        )
        self._status_tracker = IndexStatusTracker(
            wiki_path=self.wiki_path,
            repo_path=self.repo_path,
            status_manager=self._status_manager,
            find_source_files_fn=self._find_source_files,
            parser=self.parser,
            host_module=_this_module,
            ast_cache=self.ast_cache,
        )

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

        secret_findings = await asyncio.to_thread(
            scan_repository_for_secrets, self.repo_path
        )

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
            logger.debug(
                "Batch deleted chunks for %d modified files", len(files_to_delete)
            )

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

    def _sync_graph_helper(self) -> None:
        """Sync mutable graph state to the composed GraphExtractor.

        Tests may mutate ``self.graph_store``, ``self._graph_enabled``, or
        ``self._graph_extractor`` after construction.  This method propagates
        those changes so the helper always operates on the current values.
        """
        helper = self._graph_helper
        helper.graph_store = self.graph_store
        helper._graph_enabled = self._graph_enabled
        helper._graph_extractor = self._graph_extractor

    async def _run_graph_extraction(
        self,
        files_to_process: list[Path],
        file_chunks: dict[str, list[CodeChunk]],
        prev_files_by_path: dict[str, FileInfo],
        deleted_file_paths: list[str],
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Orchestrate graph extraction via the composed GraphExtractor.

        Syncs mutable state once, then delegates the full pipeline to
        ``GraphExtractor.run_graph_extraction``.
        """
        if not self._graph_enabled or self.graph_store is None:
            return

        self._sync_graph_helper()
        await self._graph_helper.run_graph_extraction(
            files_to_process=files_to_process,
            file_chunks=file_chunks,
            prev_files_by_path=prev_files_by_path,
            deleted_file_paths=deleted_file_paths,
            full_rebuild=full_rebuild,
            progress_callback=progress_callback,
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
            self._status_tracker.load_previous_status, full_rebuild
        )

        # Phase 2: Collect files to process (and detect deleted files)
        files_to_process, files_unchanged, deleted_file_paths = (
            self._status_tracker.collect_files_to_process(
                prev_files_by_path, progress_callback
            )
        )

        # Phase 3: Delete old chunks for modified and deleted files (incremental only)
        if not full_rebuild and prev_files_by_path:
            if files_to_process:
                await self._delete_old_chunks_for_modified_files(
                    files_to_process, prev_files_by_path, progress_callback
                )
            if deleted_file_paths:
                await self._delete_chunks_for_deleted_files(
                    deleted_file_paths, progress_callback
                )

        # Phase 4: Parse files in parallel and store chunks
        (
            processed_files,
            total_chunks_processed,
            file_chunks,
        ) = await self._parse_files_parallel(
            files_to_process, full_rebuild, progress_callback
        )

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
        status = self._status_tracker.create_index_status(
            processed_files, files_unchanged, total_chunks_processed
        )
        await asyncio.to_thread(self._status_tracker.save_index_status, status)

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
        return find_source_files(
            repo_path=self.repo_path,
            parser=self.parser,
            max_file_size=self.config.parsing.max_file_size,
            skip_dirs=self._exclude_skip_dirs,
            compiled_patterns=self._exclude_compiled,
            languages=self.config.parsing.languages,
        )

    def get_status(self) -> IndexStatus | None:
        """Get the current indexing status.

        Returns:
            IndexStatus or None if not indexed.
        """
        return self._status_tracker.get_status()

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
                    r.chunk.content[:500] + "..."
                    if len(r.chunk.content) > 500
                    else r.chunk.content
                ),
                "docstring": r.chunk.docstring,
            }
            for r in results
        ]
