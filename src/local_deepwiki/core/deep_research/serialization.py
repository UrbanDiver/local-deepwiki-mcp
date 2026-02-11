"""Serialization utilities for converting SearchResult objects to/from dicts.

These functions support checkpoint persistence by converting rich domain
objects into JSON-serializable dictionaries and back.
"""

from __future__ import annotations

from typing import Any

from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


def search_result_to_dict(result: SearchResult) -> dict[str, Any]:
    """Convert a SearchResult to a serializable dictionary.

    Args:
        result: The search result to convert.

    Returns:
        Dictionary representation suitable for JSON serialization.
    """
    return {
        "chunk": {
            "id": result.chunk.id,
            "file_path": result.chunk.file_path,
            "language": result.chunk.language.value,
            "chunk_type": result.chunk.chunk_type.value,
            "name": result.chunk.name,
            "content": result.chunk.content,
            "start_line": result.chunk.start_line,
            "end_line": result.chunk.end_line,
            "docstring": result.chunk.docstring,
            "parent_name": result.chunk.parent_name,
            "metadata": result.chunk.metadata,
        },
        "score": result.score,
        "highlights": result.highlights,
    }


def dict_to_search_result(data: dict[str, Any]) -> SearchResult:
    """Convert a dictionary back to a SearchResult.

    Args:
        data: Dictionary representation of a search result.

    Returns:
        Reconstructed SearchResult object.
    """
    chunk_data = data["chunk"]
    chunk = CodeChunk(
        id=chunk_data["id"],
        file_path=chunk_data["file_path"],
        language=Language(chunk_data["language"]),
        chunk_type=ChunkType(chunk_data["chunk_type"]),
        name=chunk_data.get("name"),
        content=chunk_data["content"],
        start_line=chunk_data["start_line"],
        end_line=chunk_data["end_line"],
        docstring=chunk_data.get("docstring"),
        parent_name=chunk_data.get("parent_name"),
        metadata=chunk_data.get("metadata", {}),
    )
    return SearchResult(
        chunk=chunk,
        score=data["score"],
        highlights=data.get("highlights", []),
    )
