"""Data types for the search pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from ..schema import SearchProfile


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """Immutable value object encapsulating all search parameters.

    Consolidates the many keyword arguments of ``SearchMixin.search()`` into
    a single, hashable object that is easy to pass between pipeline stages.
    """

    query: str
    limit: int = 10
    search_mode: str | None = None
    language: str | None = None
    chunk_type: str | None = None
    path_pattern: str | None = None
    use_fuzzy: bool = False
    fuzzy_weight: float = 0.3
    profile: SearchProfile | str | None = None
    min_similarity: float | None = None
    auto_suggest: bool = True
