"""Shared test helpers and fixtures for the local-deepwiki test suite.

This module provides commonly used factory functions for creating test objects.
These are plain helper functions (not fixtures) so any test file can import
and use them directly.

Usage in test files:
    from conftest import make_index_status, make_file_info, make_code_chunk
"""

import time
import uuid

from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    FileInfo,
    IndexStatus,
    Language,
    SearchResult,
)


def make_index_status(
    repo_path: str,
    total_files: int = 0,
    total_chunks: int = 0,
    languages: dict | None = None,
    files: list | None = None,
) -> IndexStatus:
    """Create an IndexStatus with required fields and sensible defaults.

    Args:
        repo_path: Path to the repository.
        total_files: Number of indexed files.
        total_chunks: Number of code chunks.
        languages: Language distribution dict.
        files: List of FileInfo objects.

    Returns:
        A new IndexStatus instance.
    """
    return IndexStatus(
        repo_path=repo_path,
        indexed_at=time.time(),
        total_files=total_files,
        total_chunks=total_chunks,
        languages=languages or {},
        files=files or [],
    )


def make_file_info(
    path: str,
    hash: str = "abc123",
    language: Language | None = Language.PYTHON,
    size_bytes: int = 100,
    chunk_count: int = 0,
) -> FileInfo:
    """Create a FileInfo with required fields and sensible defaults.

    Args:
        path: File path relative to repository root.
        hash: Content hash for change detection.
        language: Programming language of the file.
        size_bytes: File size in bytes.
        chunk_count: Number of chunks extracted from this file.

    Returns:
        A new FileInfo instance.
    """
    return FileInfo(
        path=path,
        hash=hash,
        language=language,
        size_bytes=size_bytes,
        last_modified=time.time(),
        chunk_count=chunk_count,
    )


def make_code_chunk(
    file_path: str = "src/test.py",
    name: str = "TestClass",
    chunk_type: ChunkType = ChunkType.CLASS,
    content: str = "class TestClass:\n    pass",
    language: Language = Language.PYTHON,
    start_line: int = 1,
    end_line: int = 10,
    parent_name: str | None = None,
) -> CodeChunk:
    """Create a CodeChunk with sensible defaults.

    Args:
        file_path: Source file path.
        name: Name of the code entity.
        chunk_type: Type of chunk (class, function, etc.).
        content: Source code content.
        language: Programming language.
        start_line: Starting line number.
        end_line: Ending line number.
        parent_name: Name of the parent entity.

    Returns:
        A new CodeChunk instance.
    """
    return CodeChunk(
        id=f"{file_path}:{name}",
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=name,
        content=content,
        start_line=start_line,
        end_line=end_line,
        parent_name=parent_name,
    )


def make_search_result(
    chunk: CodeChunk | None = None,
    score: float = 0.9,
) -> SearchResult:
    """Create a SearchResult with sensible defaults.

    Args:
        chunk: The code chunk for this result. If None, creates a default.
        score: Relevance score (0-1).

    Returns:
        A new SearchResult instance.
    """
    if chunk is None:
        chunk = make_code_chunk()
    return SearchResult(
        chunk=chunk,
        score=score,
        highlights=[],
    )


def make_chunk(
    id: str,
    file_path: str = "test.py",
    content: str = "test code",
    language: Language = Language.PYTHON,
    chunk_type: ChunkType = ChunkType.FUNCTION,
) -> CodeChunk:
    """Create a test CodeChunk with an explicit ID (vectorstore-style).

    This variant requires an explicit id parameter and is commonly used
    in vectorstore and pagination tests.

    Args:
        id: Unique chunk identifier.
        file_path: Source file path.
        content: Source code content.
        language: Programming language.
        chunk_type: Type of chunk.

    Returns:
        A new CodeChunk instance.
    """
    return CodeChunk(
        id=id,
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=f"test_{id}",
        content=content,
        start_line=1,
        end_line=10,
    )
