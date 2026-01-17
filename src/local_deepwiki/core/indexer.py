"""Repository indexing orchestration with incremental update support."""

import asyncio
import fnmatch
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, FileInfo, IndexStatus, ProgressCallback
from local_deepwiki.providers.embeddings import get_embedding_provider

logger = get_logger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a single file."""

    file_path: Path
    file_info: FileInfo
    chunks: list[CodeChunk]
    error: str | None = None


# Schema version for tracking index format changes.
# Increment this when the schema changes in a way that requires re-indexing.
# Version history:
#   1 - Initial schema (all versions prior to explicit versioning)
#   2 - Added schema_version field and scalar indexes on id/file_path columns
CURRENT_SCHEMA_VERSION = 2


def _needs_migration(status: IndexStatus) -> bool:
    """Check if an index status needs migration to the current schema version.

    Args:
        status: The loaded index status.

    Returns:
        True if the schema version is older than current and needs migration.
    """
    return status.schema_version < CURRENT_SCHEMA_VERSION


def _migrate_status(status: IndexStatus) -> tuple[IndexStatus, bool]:
    """Migrate an index status to the current schema version.

    This function handles migrations between schema versions. Each migration
    step should be idempotent and handle the transition from version N to N+1.

    Args:
        status: The index status to migrate.

    Returns:
        Tuple of (migrated status, requires_rebuild).
        requires_rebuild is True if the vector store needs to be rebuilt.
    """
    requires_rebuild = False
    current_version = status.schema_version

    # Migration from version 1 to 2
    # Version 2 added scalar indexes - the index data is compatible but
    # indexes need to be created (handled by _ensure_scalar_indexes in VectorStore)
    if current_version < 2:
        logger.info("Migrating index status from schema version 1 to 2")
        # No data migration needed - indexes are created on table open
        current_version = 2

    # Update schema version
    status.schema_version = current_version

    return status, requires_rebuild


class RepositoryIndexer:
    """Orchestrates repository indexing with incremental update support."""

    INDEX_STATUS_FILE = "index_status.json"

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
        self.config = config or get_config()

        # Override embedding provider if specified
        if embedding_provider_name:
            self.config.embedding.provider = embedding_provider_name  # type: ignore

        self.wiki_path = self.config.get_wiki_path(self.repo_path)
        self.vector_db_path = self.config.get_vector_db_path(self.repo_path)

        self.parser = CodeParser()
        self.chunker = CodeChunker(self.config.chunking)
        self.embedding_provider = get_embedding_provider(self.config.embedding)
        self.vector_store = VectorStore(self.vector_db_path, self.embedding_provider)

    def _parse_single_file(self, file_path: Path) -> ParseResult:
        """Parse and chunk a single file (CPU-bound, runs in thread pool).

        Args:
            file_path: Path to the file to parse.

        Returns:
            ParseResult with file info and chunks, or error message.
        """
        try:
            file_info = self.parser.get_file_info(file_path, self.repo_path)
            chunks = list(self.chunker.chunk_file(file_path, self.repo_path))
            file_info.chunk_count = len(chunks)
            return ParseResult(file_path=file_path, file_info=file_info, chunks=chunks)
        except (OSError, ValueError, RuntimeError, UnicodeDecodeError) as e:
            # Return error result instead of raising
            file_info = self.parser.get_file_info(file_path, self.repo_path)
            return ParseResult(
                file_path=file_path,
                file_info=file_info,
                chunks=[],
                error=str(e),
            )

    async def index(
        self,
        full_rebuild: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexStatus:
        """Index the repository.

        Args:
            full_rebuild: If True, rebuild entire index. Otherwise, incremental update.
            progress_callback: Optional callback for progress updates (message, current, total).

        Returns:
            IndexStatus with indexing results.
        """
        # Ensure wiki directory exists
        self.wiki_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting indexing for repository: {self.repo_path}")
        logger.debug(f"Wiki path: {self.wiki_path}, Full rebuild: {full_rebuild}")

        # Load previous status for incremental updates
        previous_status = None
        if not full_rebuild:
            previous_status, requires_rebuild = self._load_status()
            if requires_rebuild:
                logger.info("Schema migration requires full rebuild")
                full_rebuild = True
                previous_status = None

        if previous_status:
            logger.debug(f"Loaded previous index status: {previous_status.total_files} files")

        # Find all source files
        source_files = list(self._find_source_files())
        logger.info(f"Found {len(source_files)} source files to consider")

        if progress_callback:
            progress_callback("Found source files", len(source_files), len(source_files))

        # Determine which files need processing
        files_to_process: list[Path] = []
        files_unchanged: list[FileInfo] = []

        for file_path in source_files:
            file_info = self.parser.get_file_info(file_path, self.repo_path)

            if previous_status and not full_rebuild:
                # Check if file has changed
                prev_file = next(
                    (f for f in previous_status.files if f.path == file_info.path), None
                )
                if prev_file and prev_file.hash == file_info.hash:
                    files_unchanged.append(prev_file)
                    continue

            files_to_process.append(file_path)

        if progress_callback:
            progress_callback(
                f"Processing {len(files_to_process)} files ({len(files_unchanged)} unchanged)",
                0,
                len(files_to_process),
            )

        # Process files in parallel using thread pool for CPU-bound parsing
        batch_size = self.config.chunking.batch_size
        parallel_workers = self.config.chunking.parallel_workers
        chunk_batch: list[CodeChunk] = []
        processed_files: list[FileInfo] = []
        total_chunks_processed = 0
        is_first_batch = True

        logger.info(f"Parsing files with {parallel_workers} parallel workers")

        # Use thread pool for parallel parsing (CPU-bound work)
        with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
            # Submit all parsing tasks
            futures = {
                executor.submit(self._parse_single_file, file_path): file_path
                for file_path in files_to_process
            }

            # Process results as they complete
            from concurrent.futures import as_completed

            for i, future in enumerate(as_completed(futures)):
                file_path = futures[future]
                if progress_callback:
                    progress_callback(f"Parsing {file_path.name}", i, len(files_to_process))

                result = future.result()

                if result.error:
                    logger.warning(f"Error processing {result.file_path}: {result.error}")
                    if progress_callback:
                        progress_callback(
                            f"Error processing {result.file_path}: {result.error}",
                            i,
                            len(files_to_process),
                        )
                    continue

                # If incremental, delete old chunks for this file before adding new ones
                if not full_rebuild and previous_status:
                    await self.vector_store.delete_chunks_by_file(result.file_info.path)

                chunk_batch.extend(result.chunks)
                processed_files.append(result.file_info)

                # Process batch if it reaches the batch size
                if len(chunk_batch) >= batch_size:
                    if progress_callback:
                        progress_callback(
                            f"Storing batch of {len(chunk_batch)} chunks...",
                            i,
                            len(files_to_process),
                        )

                    if full_rebuild and is_first_batch:
                        await self.vector_store.create_or_update_table(chunk_batch)
                        is_first_batch = False
                    else:
                        await self.vector_store.add_chunks(chunk_batch)

                    total_chunks_processed += len(chunk_batch)
                    chunk_batch = []  # Clear batch to free memory

        # Process any remaining chunks in the final batch
        if chunk_batch:
            if progress_callback:
                progress_callback(
                    f"Storing final batch of {len(chunk_batch)} chunks...",
                    len(files_to_process),
                    len(files_to_process),
                )

            if full_rebuild and is_first_batch:
                await self.vector_store.create_or_update_table(chunk_batch)
            else:
                await self.vector_store.add_chunks(chunk_batch)

            total_chunks_processed += len(chunk_batch)

        # Combine processed and unchanged files
        all_files = processed_files + files_unchanged

        # Calculate language statistics
        languages: dict[str, int] = {}
        for file_info in all_files:
            if file_info.language:
                lang = file_info.language.value
                languages[lang] = languages.get(lang, 0) + 1

        # Create status with current schema version
        status = IndexStatus(
            repo_path=str(self.repo_path),
            indexed_at=time.time(),
            total_files=len(all_files),
            total_chunks=total_chunks_processed + sum(f.chunk_count for f in files_unchanged),
            languages=languages,
            files=all_files,
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        # Save status
        self._save_status(status)

        logger.info(
            f"Indexing complete: {status.total_files} files, "
            f"{status.total_chunks} chunks, languages: {list(status.languages.keys())}"
        )

        if progress_callback:
            progress_callback("Indexing complete", 1, 1)

        return status

    def _find_source_files(self) -> list[Path]:
        """Find all source files in the repository.

        Uses os.walk() with early directory filtering to skip excluded
        directories entirely (e.g., node_modules, .git, vendor) instead
        of traversing them and checking each file.

        Returns:
            List of paths to source files.
        """
        import os
        import re

        files = []
        exclude_patterns = self.config.parsing.exclude_patterns
        max_size = self.config.parsing.max_file_size

        # Extract directory names to skip entirely (patterns like "node_modules/**")
        skip_dirs = set()
        file_patterns = []
        for pattern in exclude_patterns:
            # Patterns like "node_modules/**" or ".git/**" -> skip the directory
            if pattern.endswith("/**"):
                skip_dirs.add(pattern[:-3])
            else:
                file_patterns.append(pattern)

        # Compile patterns for faster matching
        compiled_patterns = [re.compile(fnmatch.translate(p)) for p in file_patterns]

        for root, dirs, filenames in os.walk(self.repo_path):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.repo_path)

            # Early directory filtering - modify dirs in-place to skip subdirs
            dirs[:] = [
                d for d in dirs
                if d not in skip_dirs
                and str(rel_root / d) not in skip_dirs
                and not d.startswith(".")  # Skip hidden directories
            ]

            for filename in filenames:
                file_path = root_path / filename
                rel_path = str(file_path.relative_to(self.repo_path))

                # Check against compiled file patterns
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
        status_path = self.wiki_path / self.INDEX_STATUS_FILE
        if not status_path.exists():
            return None, False

        try:
            with open(status_path) as f:
                data = json.load(f)

            # Handle legacy status files without schema_version
            if "schema_version" not in data:
                data["schema_version"] = 1

            status = IndexStatus.model_validate(data)

            # Check if migration is needed
            if _needs_migration(status):
                status, requires_rebuild = _migrate_status(status)
                # Save the migrated status
                self._save_status(status)
                return status, requires_rebuild

            return status, False
        except (json.JSONDecodeError, OSError, ValueError) as e:
            # json.JSONDecodeError: Corrupted or invalid JSON
            # OSError: File read issues
            # ValueError: Pydantic validation failure
            logger.warning(f"Failed to load index status from {status_path}: {e}")
            return None, False

    def _save_status(self, status: IndexStatus) -> None:
        """Save indexing status.

        Args:
            status: The IndexStatus to save.
        """
        status_path = self.wiki_path / self.INDEX_STATUS_FILE
        with open(status_path, "w") as f:
            json.dump(status.model_dump(), f, indent=2)

    def get_status(self) -> IndexStatus | None:
        """Get the current indexing status.

        Returns:
            IndexStatus or None if not indexed.
        """
        status, _ = self._load_status()
        return status

    async def search(
        self,
        query: str,
        limit: int = 10,
        language: str | None = None,
    ) -> list[dict]:
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
                "name": r.chunk.name,
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
