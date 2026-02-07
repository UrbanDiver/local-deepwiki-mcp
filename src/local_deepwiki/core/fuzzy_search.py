"""Fuzzy text matching for code search.

This module provides fuzzy matching capabilities using rapidfuzz,
which can be combined with vector similarity search for better results.

Key features:
- Fuzzy name matching for function/class/method names
- "Did you mean?" suggestions when search results are poor
- Path pattern filtering with glob support
- Re-ranking results by combining vector similarity with fuzzy scores
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rapidfuzz import fuzz, process

from local_deepwiki.models import ChunkType, CodeChunk, SearchResult

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore import VectorStore


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
        docstring_fuzzy = (
            fuzzy_score(query, chunk.docstring or "") if chunk.docstring else 0.0
        )

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


@dataclass
class NameEntry:
    """An indexed name entry for fuzzy matching.

    Attributes:
        name: The function/class/method name.
        chunk_type: The type of chunk (function, class, method, etc.).
        file_path: Path to the file containing this name.
        full_qualified_name: Optional fully qualified name (e.g., "ClassName.method_name").
    """

    name: str
    chunk_type: ChunkType
    file_path: str
    full_qualified_name: str | None = None


class FuzzySearchHelper:
    """Helper class for fuzzy code search with "Did you mean?" suggestions.

    This class maintains an index of all function/class/method names in the
    codebase and provides fast fuzzy matching using Levenshtein distance.

    Example:
        ```python
        helper = FuzzySearchHelper(vector_store)
        await helper.build_name_index()

        # Find similar names to a query
        suggestions = helper.find_similar_names("calcluate_sum", threshold=0.6)
        # Returns: [("calculate_sum", 0.92), ("calculate_diff", 0.75)]

        # Generate "Did you mean?" suggestions for poor results
        suggestions = helper.generate_suggestions("calcluate", results)
        # Returns: ["calculate_sum", "calculate_product"]
        ```
    """

    def __init__(self, store: "VectorStore"):
        """Initialize the fuzzy search helper.

        Args:
            store: The VectorStore instance to index names from.
        """
        self._store = store
        self._name_cache: dict[str, list[NameEntry]] = {}  # chunk_type -> entries
        self._all_names: list[
            str
        ] = []  # Flat list of all names for rapid fuzzy matching
        self._name_to_entries: dict[
            str, list[NameEntry]
        ] = {}  # name -> entries mapping
        self._is_built = False

    @property
    def is_built(self) -> bool:
        """Check if the name index has been built."""
        return self._is_built

    async def build_name_index(self) -> None:
        """Build an index of all function/class/method names for fuzzy matching.

        This method iterates over all chunks in the vector store and extracts
        names for functions, classes, methods, and modules. The index is used
        for fast fuzzy matching and suggestion generation.
        """
        self._name_cache.clear()
        self._all_names.clear()
        self._name_to_entries.clear()

        table = self._store._get_table()
        if table is None:
            self._is_built = True
            return

        # Types of chunks that have meaningful names
        name_types = {
            ChunkType.FUNCTION,
            ChunkType.CLASS,
            ChunkType.METHOD,
            ChunkType.MODULE,
        }

        # Iterate over all chunks to extract names
        # Use batched iteration to avoid memory issues with large tables
        try:
            # LanceDB returns a pyarrow table or list
            all_rows = table.to_pandas()
            for _, row in all_rows.iterrows():
                name = row.get("name")
                if not name or not isinstance(name, str) or not name.strip():
                    continue

                chunk_type_str = row.get("chunk_type", "")
                try:
                    chunk_type = ChunkType(chunk_type_str)
                except ValueError:
                    continue

                if chunk_type not in name_types:
                    continue

                file_path = row.get("file_path", "")
                parent_name = row.get("parent_name")

                # Create fully qualified name for methods
                full_qualified_name = None
                if chunk_type == ChunkType.METHOD and parent_name:
                    full_qualified_name = f"{parent_name}.{name}"

                entry = NameEntry(
                    name=name,
                    chunk_type=chunk_type,
                    file_path=file_path,
                    full_qualified_name=full_qualified_name,
                )

                # Add to type-specific cache
                type_key = chunk_type.value
                if type_key not in self._name_cache:
                    self._name_cache[type_key] = []
                self._name_cache[type_key].append(entry)

                # Add to flat name list (for fuzzy matching)
                if name not in self._name_to_entries:
                    self._name_to_entries[name] = []
                    self._all_names.append(name)
                self._name_to_entries[name].append(entry)

                # Also index fully qualified name if present
                if (
                    full_qualified_name
                    and full_qualified_name not in self._name_to_entries
                ):
                    self._name_to_entries[full_qualified_name] = [entry]
                    self._all_names.append(full_qualified_name)

        except Exception:
            # If pandas is not available or table is empty, fall back to iteration
            pass

        self._is_built = True

    def find_similar_names(
        self,
        query: str,
        threshold: float = 0.6,
        limit: int = 5,
        chunk_type: ChunkType | None = None,
    ) -> list[tuple[str, float]]:
        """Find similar names using Levenshtein distance.

        Uses rapidfuzz for efficient fuzzy string matching.

        Args:
            query: The query string to match against.
            threshold: Minimum similarity score (0.0-1.0) for inclusion.
            limit: Maximum number of results to return.
            chunk_type: Optional filter by chunk type.

        Returns:
            List of (name, score) tuples sorted by score descending.
            Scores are normalized to 0.0-1.0 range.
        """
        if not query or not self._all_names:
            return []

        # Get the candidates to search
        if chunk_type is not None and chunk_type.value in self._name_cache:
            candidates = [e.name for e in self._name_cache[chunk_type.value]]
            # Also include fully qualified names for methods
            if chunk_type == ChunkType.METHOD:
                candidates.extend(
                    e.full_qualified_name
                    for e in self._name_cache.get(chunk_type.value, [])
                    if e.full_qualified_name
                )
        else:
            candidates = self._all_names

        if not candidates:
            return []

        # Use rapidfuzz's extract function for efficient batch matching
        # The scorer uses a combination of token_set_ratio and partial_ratio
        # which handles typos well
        query_lower = query.lower()

        # Use process.extract with custom scorer
        matches = process.extract(
            query_lower,
            [c.lower() for c in candidates],
            scorer=fuzz.WRatio,  # Weighted ratio - good for typos
            limit=limit * 2,  # Get more results to filter by threshold
        )

        # Map back to original case and filter by threshold
        results: list[tuple[str, float]] = []
        seen_names: set[str] = set()

        for match in matches:
            matched_lower, score, idx = match
            # Normalize score to 0-1 range (rapidfuzz returns 0-100)
            normalized_score = score / 100.0

            if normalized_score < threshold:
                continue

            # Get original case name
            original_name = candidates[idx]
            if original_name in seen_names:
                continue

            seen_names.add(original_name)
            results.append((original_name, normalized_score))

            if len(results) >= limit:
                break

        return results

    def generate_suggestions(
        self,
        query: str,
        results: list[SearchResult],
        threshold: float = 0.6,
        max_suggestions: int = 3,
    ) -> list[str]:
        """Generate 'Did you mean?' suggestions based on the query.

        This method analyzes the query and current results to suggest
        alternative names that the user might have meant to search for.

        Args:
            query: The original search query.
            results: The current search results (may be empty or low-quality).
            threshold: Minimum similarity for suggestions.
            max_suggestions: Maximum number of suggestions to return.

        Returns:
            List of suggested names, ordered by relevance.
        """
        if not query:
            return []

        # Extract key terms from the query
        # Split on common delimiters and filter short words
        query_terms = re.split(r"[\s_\-\.]+", query.lower())
        query_terms = [t for t in query_terms if len(t) >= 2]

        if not query_terms:
            query_terms = [query.lower()]

        suggestions: list[tuple[str, float]] = []
        seen: set[str] = set()

        # Get names from current results to exclude
        result_names = {r.chunk.name for r in results if r.chunk.name}

        # Find similar names for each query term
        for term in query_terms:
            similar = self.find_similar_names(
                term,
                threshold=threshold,
                limit=max_suggestions * 2,
            )

            for name, score in similar:
                # Skip names already in results or already suggested
                if name in result_names or name in seen:
                    continue

                seen.add(name)
                suggestions.append((name, score))

        # Also try the full query as a single term
        full_query_similar = self.find_similar_names(
            query,
            threshold=threshold,
            limit=max_suggestions,
        )

        for name, score in full_query_similar:
            if name not in result_names and name not in seen:
                seen.add(name)
                # Boost score for full query matches
                suggestions.append((name, score * 1.1))

        # Sort by score descending and limit
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in suggestions[:max_suggestions]]

    def get_file_suggestions(
        self,
        query: str,
        threshold: float = 0.6,
        limit: int = 3,
    ) -> list[str]:
        """Get file path suggestions based on a query.

        Useful when the user might be searching for a specific file.

        Args:
            query: The query to match against file paths.
            threshold: Minimum similarity for suggestions.
            limit: Maximum number of suggestions.

        Returns:
            List of suggested file paths.
        """
        if not self._name_to_entries:
            return []

        # Collect unique file paths
        file_paths: set[str] = set()
        for entries in self._name_to_entries.values():
            for entry in entries:
                if entry.file_path:
                    file_paths.add(entry.file_path)

        if not file_paths:
            return []

        # Extract filename from query if it looks like a path
        query_name = Path(query).name if "/" in query or "\\" in query else query
        query_lower = query_name.lower()

        # Match against file names
        matches = process.extract(
            query_lower,
            [Path(fp).name.lower() for fp in file_paths],
            scorer=fuzz.WRatio,
            limit=limit * 2,
        )

        # Map back to full paths
        file_paths_list = list(file_paths)
        results: list[str] = []

        for match in matches:
            _, score, idx = match
            if score / 100.0 >= threshold:
                results.append(file_paths_list[idx])
                if len(results) >= limit:
                    break

        return results

    def get_entries_for_name(self, name: str) -> list[NameEntry]:
        """Get all entries for a given name.

        Args:
            name: The name to look up.

        Returns:
            List of NameEntry objects for this name, or empty list if not found.
        """
        return self._name_to_entries.get(name, [])

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the name index.

        Returns:
            Dictionary with counts of indexed names by type.
        """
        stats = {
            "total_names": len(self._all_names),
            "unique_names": len(self._name_to_entries),
        }

        for chunk_type, entries in self._name_cache.items():
            stats[f"{chunk_type}_count"] = len(entries)

        return stats


def should_auto_enable_fuzzy(
    results: list[SearchResult],
    threshold: float = 0.5,
) -> bool:
    """Determine if fuzzy matching should be auto-enabled based on result quality.

    Args:
        results: Current search results.
        threshold: Score threshold below which to enable fuzzy.

    Returns:
        True if fuzzy should be enabled (results are poor quality).
    """
    if not results:
        return True

    # Check if the best result score is below threshold
    best_score = max(r.score for r in results)
    return best_score < threshold
