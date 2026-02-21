"""Shared utilities for diagram generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from local_deepwiki.models import CodeChunk


@dataclass
class ClassInfo:
    """Information about a class for diagram generation."""

    name: str
    methods: list[str]
    attributes: list[str]
    parents: list[str]
    is_abstract: bool = False
    is_dataclass: bool = False
    docstring: str | None = None


_MERMAID_SANITIZE_TABLE = str.maketrans({ch: "_" for ch in "<>[] .-:"})


def sanitize_mermaid_name(name: str) -> str:
    """Sanitize a name for use in Mermaid diagrams.

    Args:
        name: Original name.

    Returns:
        Sanitized name safe for Mermaid syntax.
    """
    result = name.translate(_MERMAID_SANITIZE_TABLE)
    # Ensure it starts with a letter
    if result and result[0].isdigit():
        result = "C" + result
    return result


def _unwrap_chunk(chunk: CodeChunk | Any) -> CodeChunk:
    """Unwrap SearchResult to get the underlying chunk."""
    return getattr(chunk, "chunk", chunk)
