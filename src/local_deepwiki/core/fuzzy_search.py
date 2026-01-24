"""Fuzzy text matching for code search.

This module provides fuzzy matching capabilities using rapidfuzz,
which can be combined with vector similarity search for better results.
"""

import fnmatch
import re
from typing import Any

from rapidfuzz import fuzz, process

from local_deepwiki.models import CodeChunk, SearchResult


def fuzzy_score(query: str, text: str) -> float:
    """Calculate fuzzy match score between query and text.

    Uses a combination of fuzzy matching algorithms for best results:
    - token_set_ratio: Good for matching when words are out of order
    - partial_ratio: Good for matching substrings

    Args:
        query: The search query.
        text: The text to match against.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not query or not text:
        return 0.0

    # Normalize inputs
    query_lower = query.lower()
    text_lower = text.lower()

    # Use weighted combination of fuzzy algorithms
    # token_set_ratio handles word order and duplicates well
    token_score = fuzz.token_set_ratio(query_lower, text_lower)
    # partial_ratio handles substring matching well
    partial_score = fuzz.partial_ratio(query_lower, text_lower)

    # Combine scores (weighted average, partial gets more weight for code search)
    combined = (token_score * 0.4 + partial_score * 0.6) / 100.0
    return combined


def fuzzy_match_name(query: str, name: str | None) -> float:
    """Calculate fuzzy match score for function/class names.

    Optimized for code identifier matching with special handling for:
    - snake_case and camelCase names
    - Exact prefix matches
    - Word boundary matches

    Args:
        query: The search query.
        name: The name to match (function, class, method name).

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not name or not query:
        return 0.0

    query_lower = query.lower()
    name_lower = name.lower()

    # Exact match gets highest score
    if query_lower == name_lower:
        return 1.0

    # Prefix match gets high score
    if name_lower.startswith(query_lower):
        return 0.95

    # Contains match gets good score
    if query_lower in name_lower:
        return 0.85

    # Split name by common separators (snake_case, camelCase)
    name_parts = re.split(r"[_\-\s]|(?<=[a-z])(?=[A-Z])", name)
    name_parts_lower = [p.lower() for p in name_parts if p]

    # Check if query matches any part
    for part in name_parts_lower:
        if part.startswith(query_lower):
            return 0.8
        if query_lower in part:
            return 0.7

    # Fall back to fuzzy matching
    return fuzzy_score(query, name) * 0.6


def matches_path_pattern(file_path: str, pattern: str) -> bool:
    """Check if a file path matches a glob-like pattern.

    Supports patterns like:
    - "*.py" - matches Python files
    - "src/**/*.py" - matches Python files in src and subdirectories
    - "tests/*" - matches files directly in tests directory

    Args:
        file_path: The file path to check.
        pattern: Glob-like pattern to match against.

    Returns:
        True if the path matches the pattern.
    """
    if not pattern:
        return True

    # Normalize path separators
    file_path = file_path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")

    # Handle ** (match any number of directories)
    if "**" in pattern:
        # Convert to regex using placeholders to avoid replacement conflicts
        regex_pattern = pattern.replace(".", r"\.")
        # Use placeholders for ** patterns before replacing single *
        regex_pattern = regex_pattern.replace("**/", "\x00DSTAR_SLASH\x00")
        regex_pattern = regex_pattern.replace("**", "\x00DSTAR\x00")
        # Now safely replace single * (won't affect placeholders)
        regex_pattern = regex_pattern.replace("*", "[^/]*")
        # Replace placeholders with actual regex
        regex_pattern = regex_pattern.replace("\x00DSTAR_SLASH\x00", "(?:.*/)?")
        regex_pattern = regex_pattern.replace("\x00DSTAR\x00", ".*")
        regex_pattern = f"^{regex_pattern}$"
        return bool(re.match(regex_pattern, file_path))

    # Use fnmatch for simple patterns
    return fnmatch.fnmatch(file_path, pattern)


def rerank_with_fuzzy(
    results: list[SearchResult],
    query: str,
    fuzzy_weight: float = 0.3,
) -> list[SearchResult]:
    """Re-rank search results by combining vector similarity with fuzzy matching.

    This improves search results by boosting results where the query
    matches the code name or content more precisely.

    Args:
        results: List of search results from vector search.
        query: The original search query.
        fuzzy_weight: Weight for fuzzy score (0.0-1.0). Vector score gets (1 - fuzzy_weight).

    Returns:
        Re-ranked list of search results with updated scores.
    """
    if not results:
        return results

    if fuzzy_weight <= 0:
        # No fuzzy reranking, but still ensure sorted by original score
        return sorted(results, key=lambda r: r.score, reverse=True)

    reranked = []
    for result in results:
        chunk = result.chunk
        vector_score = result.score

        # Calculate fuzzy scores
        name_fuzzy = fuzzy_match_name(query, chunk.name)

        # Also check content for the query
        content_fuzzy = fuzzy_score(query, chunk.content[:500])  # Limit content length

        # Also check docstring if present
        docstring_fuzzy = fuzzy_score(query, chunk.docstring or "") if chunk.docstring else 0.0

        # Combined fuzzy score (weighted)
        fuzzy_combined = max(
            name_fuzzy * 1.0,  # Name match is most important
            content_fuzzy * 0.7,  # Content match
            docstring_fuzzy * 0.8,  # Docstring match
        )

        # Combine vector and fuzzy scores
        final_score = (1 - fuzzy_weight) * vector_score + fuzzy_weight * fuzzy_combined

        reranked.append(
            SearchResult(
                chunk=chunk,
                score=final_score,
                highlights=result.highlights,
            )
        )

    # Sort by combined score (descending)
    reranked.sort(key=lambda r: r.score, reverse=True)
    return reranked


def extract_highlights(content: str, query: str, context_chars: int = 50) -> list[str]:
    """Extract highlighted snippets around query matches.

    Args:
        content: The content to search in.
        query: The search query.
        context_chars: Number of characters to include around each match.

    Returns:
        List of highlight snippets with matches marked.
    """
    if not query or not content:
        return []

    highlights = []
    query_lower = query.lower()
    content_lower = content.lower()

    # Find all occurrences
    start = 0
    while True:
        pos = content_lower.find(query_lower, start)
        if pos == -1:
            break

        # Extract context around the match
        ctx_start = max(0, pos - context_chars)
        ctx_end = min(len(content), pos + len(query) + context_chars)

        # Build highlight
        snippet = content[ctx_start:ctx_end]

        # Add ellipsis if truncated
        if ctx_start > 0:
            snippet = "..." + snippet
        if ctx_end < len(content):
            snippet = snippet + "..."

        highlights.append(snippet)
        start = pos + 1

        # Limit number of highlights
        if len(highlights) >= 3:
            break

    return highlights


def filter_by_path(
    results: list[SearchResult],
    path_pattern: str | None,
) -> list[SearchResult]:
    """Filter search results by file path pattern.

    Args:
        results: List of search results.
        path_pattern: Glob-like pattern to filter by (e.g., "src/**/*.py").

    Returns:
        Filtered list of search results.
    """
    if not path_pattern:
        return results

    return [r for r in results if matches_path_pattern(r.chunk.file_path, path_pattern)]
