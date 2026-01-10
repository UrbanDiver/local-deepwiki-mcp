"""Repository indexing orchestration with incremental update support."""

import fnmatch
import json
import time
from pathlib import Path
from typing import Callable

from rich.progress import Progress, TaskID

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.models import CodeChunk, FileInfo, IndexStatus
from local_deepwiki.providers.embeddings import get_embedding_provider


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

    async def index(
        self,
        full_rebuild: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
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

        # Load previous status for incremental updates
        previous_status = None if full_rebuild else self._load_status()

        # Find all source files
        source_files = list(self._find_source_files())

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
                    (f for f in previous_status.files if f.path == file_info.path),
                    None
                )
                if prev_file and prev_file.hash == file_info.hash:
                    files_unchanged.append(prev_file)
                    continue

            files_to_process.append(file_path)

        if progress_callback:
            progress_callback(
                f"Processing {len(files_to_process)} files ({len(files_unchanged)} unchanged)",
                0,
                len(files_to_process)
            )

        # Process files and collect chunks
        all_chunks: list[CodeChunk] = []
        processed_files: list[FileInfo] = []

        for i, file_path in enumerate(files_to_process):
            if progress_callback:
                progress_callback(f"Parsing {file_path.name}", i, len(files_to_process))

            try:
                # Get file info
                file_info = self.parser.get_file_info(file_path, self.repo_path)

                # Extract chunks
                chunks = list(self.chunker.chunk_file(file_path, self.repo_path))
                file_info.chunk_count = len(chunks)

                all_chunks.extend(chunks)
                processed_files.append(file_info)

            except Exception as e:
                # Log error but continue with other files
                if progress_callback:
                    progress_callback(f"Error processing {file_path}: {e}", i, len(files_to_process))

        # If incremental, delete old chunks for processed files
        if not full_rebuild and previous_status:
            for file_info in processed_files:
                await self.vector_store.delete_chunks_by_file(file_info.path)

        # Store chunks in vector database
        if progress_callback:
            progress_callback("Generating embeddings and storing chunks", 0, 1)

        if full_rebuild:
            await self.vector_store.create_or_update_table(all_chunks)
        else:
            await self.vector_store.add_chunks(all_chunks)

        # Combine processed and unchanged files
        all_files = processed_files + files_unchanged

        # Calculate language statistics
        languages: dict[str, int] = {}
        for file_info in all_files:
            if file_info.language:
                lang = file_info.language.value
                languages[lang] = languages.get(lang, 0) + 1

        # Create status
        status = IndexStatus(
            repo_path=str(self.repo_path),
            indexed_at=time.time(),
            total_files=len(all_files),
            total_chunks=len(all_chunks) + sum(f.chunk_count for f in files_unchanged),
            languages=languages,
            files=all_files,
        )

        # Save status
        self._save_status(status)

        if progress_callback:
            progress_callback("Indexing complete", 1, 1)

        return status

    def _find_source_files(self) -> list[Path]:
        """Find all source files in the repository.

        Yields:
            Paths to source files.
        """
        files = []
        exclude_patterns = self.config.parsing.exclude_patterns
        max_size = self.config.parsing.max_file_size

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Check against exclude patterns
            rel_path = str(file_path.relative_to(self.repo_path))
            if any(fnmatch.fnmatch(rel_path, pattern) for pattern in exclude_patterns):
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

    def _load_status(self) -> IndexStatus | None:
        """Load previous indexing status.

        Returns:
            IndexStatus or None if not found.
        """
        status_path = self.wiki_path / self.INDEX_STATUS_FILE
        if not status_path.exists():
            return None

        try:
            with open(status_path) as f:
                data = json.load(f)
            return IndexStatus.model_validate(data)
        except Exception:
            return None

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
        return self._load_status()

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
                "content": r.chunk.content[:500] + "..." if len(r.chunk.content) > 500 else r.chunk.content,
                "docstring": r.chunk.docstring,
            }
            for r in results
        ]
