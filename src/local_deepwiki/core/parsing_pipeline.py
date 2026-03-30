"""Self-contained file parsing and chunking pipeline.

Extracted from ``RepositoryIndexer`` to isolate the CPU-bound parsing and
embedding-storage phases into a cohesive unit.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, FileInfo, ProgressCallback

logger = get_logger(__name__)


@dataclass(frozen=True)
class PipelineContext:
    """Immutable configuration for a file-parsing pipeline run.

    Bundles the dependencies and tuning knobs that ``FileParsingPipeline``
    needs, replacing a long positional/keyword parameter list with a single
    frozen object.
    """

    parser: CodeParser
    chunker: CodeChunker
    repo_path: Path
    vector_store: VectorStore
    batch_size: int
    parallel_workers: int
    pipeline_logger: Any | None = None


@dataclass(slots=True)
class _WindowState:
    """Mutable running state threaded through the sliding-window loop.

    Keeps the accumulating counters and batch buffer in one place so that
    ``_run_window_loop`` and ``_process_window`` don't need long parameter
    lists.
    """

    file_count: int = 0
    chunk_batch: list[CodeChunk] = field(default_factory=list)
    processed_files: list[FileInfo] = field(default_factory=list)
    total_chunks_processed: int = 0
    is_first_batch: bool = True
    error_count: int = 0
    files_completed: int = 0


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
        ctx: Frozen pipeline context containing all dependencies and config.
    """

    def __init__(self, ctx: PipelineContext) -> None:
        self._ctx = ctx
        self.parser = ctx.parser
        self.chunker = ctx.chunker
        self.repo_path = ctx.repo_path
        self.vector_store = ctx.vector_store
        self.batch_size = ctx.batch_size
        self.parallel_workers = ctx.parallel_workers
        self._logger = ctx.pipeline_logger or logger

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
        file_count = len(files_to_process)
        state = _WindowState(file_count=file_count)

        if file_count == 0:
            self._logger.info("No files to parse")
            return state.processed_files, state.total_chunks_processed

        self._logger.info(
            "Starting parallel file parsing: %d files with %d workers",
            file_count,
            self.parallel_workers,
        )
        parse_start_time = time.time()

        await self._run_window_loop(
            files_to_process=files_to_process,
            _parse=_parse,
            state=state,
            full_rebuild=full_rebuild,
            progress_callback=progress_callback,
        )

        self._log_parse_metrics(
            parse_start_time,
            len(state.processed_files),
            state.total_chunks_processed,
            state.error_count,
        )

        return state.processed_files, state.total_chunks_processed

    async def _run_window_loop(
        self,
        *,
        files_to_process: list[Path],
        _parse: Callable[[Path], ParseResult],
        state: _WindowState,
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Process all files in windows and flush chunk batches.

        Mutates *state* in place with final counts.
        """
        file_count = len(files_to_process)
        window_size = max(self.batch_size, self.parallel_workers * 4)
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            for window_start in range(0, file_count, window_size):
                window_end = min(window_start + window_size, file_count)
                window_files = files_to_process[window_start:window_end]
                futures = {executor.submit(_parse, fp): fp for fp in window_files}
                await self._process_window(
                    futures=futures,
                    file_count=file_count,
                    state=state,
                    full_rebuild=full_rebuild,
                    progress_callback=progress_callback,
                )
        if state.chunk_batch:
            # For the final flush, files_completed == file_count
            state.files_completed = file_count
            chunks_stored = await self._process_chunk_batch(
                state=state,
                full_rebuild=full_rebuild,
                progress_callback=progress_callback,
                is_final=True,
            )
            state.total_chunks_processed += chunks_stored

    async def _process_window(
        self,
        *,
        futures: dict,
        file_count: int,
        state: _WindowState,
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Iterate completed futures for one sliding window, collecting results.

        Mutates *state* in place with updated counts and batch contents.

        Args:
            futures: Mapping of Future -> file_path for the current window.
            file_count: Total number of files in the entire parse run.
            state: Mutable running state for the window loop.
            full_rebuild: Passed through to ``_process_chunk_batch``.
            progress_callback: Optional progress callback.
        """
        for future in as_completed(futures):
            file_path = futures[future]
            if progress_callback:
                progress_callback(
                    f"Parsing {file_path.name}",
                    state.files_completed,
                    file_count,
                )

            result = future.result()
            skipped = await self._handle_parse_result(
                result,
                progress_callback,
                state.files_completed,
                file_count,
                state.chunk_batch,
                state.processed_files,
            )
            if skipped:
                state.error_count += 1
                state.files_completed += 1
                continue

            if len(state.chunk_batch) >= self.batch_size:
                chunks_stored = await self._process_chunk_batch(
                    state=state,
                    full_rebuild=full_rebuild,
                    progress_callback=progress_callback,
                )
                state.total_chunks_processed += chunks_stored
                state.is_first_batch = False
                state.chunk_batch.clear()

            state.files_completed += 1

    def _log_parse_metrics(
        self,
        parse_start_time: float,
        files_parsed: int,
        total_chunks_processed: int,
        error_count: int,
    ) -> None:
        """Log a summary of parallel parsing performance.

        Args:
            parse_start_time: ``time.time()`` recorded before parsing started.
            files_parsed: Number of files successfully parsed.
            total_chunks_processed: Total chunks stored to the vector store.
            error_count: Number of files that failed to parse.
        """
        parse_duration = time.time() - parse_start_time
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

    async def _handle_parse_result(
        self,
        result: ParseResult,
        progress_callback: ProgressCallback | None,
        files_completed: int,
        file_count: int,
        chunk_batch: list[CodeChunk],
        processed_files: list[FileInfo],
    ) -> bool:
        """Handle a single parsed file result, emitting events and updating state.

        Args:
            result: The ParseResult from parsing a single file.
            progress_callback: Optional progress callback.
            files_completed: Number of files already completed (for callback).
            file_count: Total number of files (for callback).
            chunk_batch: Mutable list to append chunks to (mutated in place).
            processed_files: Mutable list to append successful FileInfo to.

        Returns:
            True if the file had an error and should be counted as skipped.
        """
        if result.error:
            self._logger.warning(
                "Error processing %s: %s", result.file_path, result.error
            )
            if progress_callback:
                progress_callback(
                    f"Error processing {result.file_path}: {result.error}",
                    files_completed,
                    file_count,
                )
            emitter = get_event_emitter()
            await emitter.emit(
                EventType.INDEX_ERROR,
                {"file_path": str(result.file_path), "error": result.error},
            )
            return True

        chunk_batch.extend(result.chunks)
        processed_files.append(result.file_info)

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
        return False

    async def _process_chunk_batch(
        self,
        *,
        state: _WindowState,
        full_rebuild: bool,
        progress_callback: ProgressCallback | None,
        is_final: bool = False,
    ) -> int:
        """Process a batch of chunks and store in vector store.

        Args:
            state: Window state whose ``chunk_batch``, ``is_first_batch``,
                ``files_completed``, and ``file_count`` are read.
            full_rebuild: If True, may need to create table on first batch.
            progress_callback: Optional callback for progress updates.
            is_final: True if this is the final batch.

        Returns:
            Number of chunks processed.
        """
        batch_type = "final batch" if is_final else "batch"
        if progress_callback:
            progress_callback(
                f"Storing {batch_type} of {len(state.chunk_batch)} chunks...",
                state.files_completed,
                state.file_count,
            )

        if full_rebuild and state.is_first_batch:
            await self.vector_store.create_or_update_table(state.chunk_batch)
        else:
            await self.vector_store.add_chunks(state.chunk_batch)

        return len(state.chunk_batch)
