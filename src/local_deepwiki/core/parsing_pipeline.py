"""Self-contained file parsing and chunking pipeline.

Extracted from ``RepositoryIndexer`` to isolate the CPU-bound parsing and
embedding-storage phases into a cohesive unit.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, FileInfo, ProgressCallback

logger = get_logger(__name__)


@dataclass(slots=True)
class ParseResult:
    """Result of parsing a single file."""

    file_path: Path
    file_info: FileInfo
    chunks: list[CodeChunk]
    error: str | None = None


class FileParsingPipeline:
    """Parallel file parsing, chunking, and vector-store ingestion.

    This pipeline owns no persistent state — it receives the parser, chunker,
    and vector store from its caller and orchestrates parsing in a thread pool.

    Args:
        parser: The code parser instance.
        chunker: The code chunker instance.
        repo_path: Resolved path to the repository root.
        vector_store: Vector store for chunk storage.
        batch_size: Number of chunks per storage batch.
        parallel_workers: Number of threads for parallel parsing.
    """

    def __init__(
        self,
        parser: CodeParser,
        chunker: CodeChunker,
        repo_path: Path,
        vector_store: VectorStore,
        batch_size: int,
        parallel_workers: int,
        pipeline_logger: Any | None = None,
    ) -> None:
        self.parser = parser
        self.chunker = chunker
        self.repo_path = repo_path
        self.vector_store = vector_store
        self.batch_size = batch_size
        self.parallel_workers = parallel_workers
        self._logger = pipeline_logger or logger

    def parse_single_file(self, file_path: Path) -> ParseResult:
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

    async def parse_files_parallel(
        self,
        files_to_process: list[Path],
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
        parse_fn: Callable[[Path], ParseResult] | None = None,
    ) -> tuple[list[FileInfo], int]:
        """Handle parallel file parsing with ThreadPoolExecutor.

        Uses multiple threads to parse files concurrently, significantly speeding up
        indexing for large repositories. Embedding generation remains sequential
        to respect API rate limits.

        Args:
            files_to_process: List of file paths to parse.
            full_rebuild: If True, this is a full rebuild (affects table creation).
            progress_callback: Optional callback for progress updates.
            parse_fn: Optional override for the per-file parse function.
                Defaults to ``self.parse_single_file``.

        Returns:
            Tuple of (processed_files, total_chunks_processed).
        """
        _parse = parse_fn or self.parse_single_file
        chunk_batch: list[CodeChunk] = []
        processed_files: list[FileInfo] = []
        total_chunks_processed = 0
        is_first_batch = True
        error_count = 0

        file_count = len(files_to_process)
        if file_count == 0:
            self._logger.info("No files to parse")
            return processed_files, total_chunks_processed

        self._logger.info(
            "Starting parallel file parsing: %d files with %d workers",
            file_count,
            self.parallel_workers,
        )
        parse_start_time = time.time()

        # Process files in windows to limit memory from queued futures.
        # Each window submits at most ``window_size`` futures at a time so
        # that completed results can be flushed before the next window.
        window_size = max(self.batch_size, self.parallel_workers * 4)
        files_completed = 0

        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            for window_start in range(0, file_count, window_size):
                window_end = min(window_start + window_size, file_count)
                window_files = files_to_process[window_start:window_end]
                futures = {executor.submit(_parse, fp): fp for fp in window_files}

                for future in as_completed(futures):
                    file_path = futures[future]
                    if progress_callback:
                        progress_callback(
                            f"Parsing {file_path.name}",
                            files_completed,
                            file_count,
                        )

                    result = future.result()

                    if result.error:
                        error_count += 1
                        self._logger.warning(
                            "Error processing %s: %s", result.file_path, result.error
                        )
                        if progress_callback:
                            progress_callback(
                                f"Error processing {result.file_path}: {result.error}",
                                files_completed,
                                file_count,
                            )
                        # Emit INDEX_ERROR event for file processing errors
                        emitter = get_event_emitter()
                        await emitter.emit(
                            EventType.INDEX_ERROR,
                            {
                                "file_path": str(result.file_path),
                                "error": result.error,
                            },
                        )
                        files_completed += 1
                        continue

                    chunk_batch.extend(result.chunks)
                    processed_files.append(result.file_info)

                    # Emit INDEX_FILE event for successfully parsed file
                    emitter = get_event_emitter()
                    await emitter.emit(
                        EventType.INDEX_FILE,
                        {
                            "file_path": str(result.file_path),
                            "language": (
                                result.file_info.language.value
                                if result.file_info.language
                                else None
                            ),
                            "chunk_count": len(result.chunks),
                        },
                    )

                    # Process batch if it reaches the batch size
                    if len(chunk_batch) >= self.batch_size:
                        chunks_stored = await self._process_chunk_batch(
                            chunk_batch,
                            full_rebuild,
                            is_first_batch,
                            progress_callback,
                            files_completed,
                            file_count,
                        )
                        total_chunks_processed += chunks_stored
                        is_first_batch = False
                        chunk_batch = []

                    files_completed += 1

        # Process any remaining chunks in the final batch
        if chunk_batch:
            chunks_stored = await self._process_chunk_batch(
                chunk_batch,
                full_rebuild,
                is_first_batch,
                progress_callback,
                file_count,
                file_count,
                is_final=True,
            )
            total_chunks_processed += chunks_stored

        # Log performance metrics
        parse_duration = time.time() - parse_start_time
        files_parsed = len(processed_files)
        files_per_second = files_parsed / parse_duration if parse_duration > 0 else 0
        chunks_per_second = (
            total_chunks_processed / parse_duration if parse_duration > 0 else 0
        )

        self._logger.info(
            "Parallel parsing complete: %d files, %d chunks in %.2fs "
            "(%.1f files/s, %.1f chunks/s, %d workers, %d errors)",
            files_parsed,
            total_chunks_processed,
            parse_duration,
            files_per_second,
            chunks_per_second,
            self.parallel_workers,
            error_count,
        )

        return processed_files, total_chunks_processed

    async def _process_chunk_batch(
        self,
        chunk_batch: list[CodeChunk],
        full_rebuild: bool,
        is_first_batch: bool,
        progress_callback: ProgressCallback | None,
        current: int,
        total: int,
        is_final: bool = False,
    ) -> int:
        """Process a batch of chunks and store in vector store.

        Args:
            chunk_batch: List of code chunks to store.
            full_rebuild: If True, may need to create table on first batch.
            is_first_batch: True if this is the first batch being processed.
            progress_callback: Optional callback for progress updates.
            current: Current progress index.
            total: Total number of files being processed.
            is_final: True if this is the final batch.

        Returns:
            Number of chunks processed.
        """
        batch_type = "final batch" if is_final else "batch"
        if progress_callback:
            progress_callback(
                f"Storing {batch_type} of {len(chunk_batch)} chunks...",
                current,
                total,
            )

        if full_rebuild and is_first_batch:
            await self.vector_store.create_or_update_table(chunk_batch)
        else:
            await self.vector_store.add_chunks(chunk_batch)

        return len(chunk_batch)
