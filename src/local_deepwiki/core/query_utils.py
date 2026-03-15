"""Shared query preprocessing utilities for embedding search.

Provides filler-word stripping and project-specific term expansion to
improve vector similarity when queries are conversational rather than
technical (e.g. "tell me everything about how the RAG works").
"""

from __future__ import annotations

# Filler words stripped when condensing conversational queries into
# technical search terms (e.g. "tell me everything about how X works"
# -> "X works").
FILLER_WORDS: frozenset[str] = frozenset(
    {
        "tell",
        "me",
        "everything",
        "about",
        "how",
        "does",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "what",
        "can",
        "could",
        "would",
        "should",
        "please",
        "explain",
        "show",
        "describe",
        "give",
        "all",
        "detail",
        "details",
        "detailed",
        "in",
        "of",
        "for",
        "with",
        "to",
        "do",
        "i",
        "want",
        "know",
        "understand",
        "it",
        "its",
        "this",
        "that",
        "work",
        "works",
        "working",
    }
)

# Maps recognised project-domain terms to additional search tokens that
# help the embedding model locate relevant chunks.  Each key is matched
# case-insensitively against individual words in the query.
_PROJECT_TERM_EXPANSIONS: dict[str, list[str]] = {
    "handler": ["handle_", "TOOL_HANDLERS", "handlers"],
    "provider": ["LLMProvider", "get_llm_provider", "EmbeddingProvider"],
    "indexer": ["index_repository", "handle_index", "indexing_pipeline"],
    "parser": ["tree_sitter", "parse_file", "CodeParser"],
    "chunker": ["chunk_extractors", "semantic_chunks", "CodeChunk"],
    "vectorstore": ["LanceDB", "vector_search", "embeddings"],
    "wiki": ["WikiGenerator", "generate_wiki", "wiki_page"],
    "codemap": ["CodemapGraph", "generate_codemap", "BFS_traversal"],
    "research": ["deep_research", "query_decomposition", "synthesis"],
    "config": ["config.yaml", "ConfigModel", "configuration"],
}


def condense_query(query: str) -> str:
    """Strip filler words from a conversational query to improve embedding search.

    Conversational queries like "tell me everything about how the rag works"
    embed poorly because filler dilutes the signal.  Returns a condensed
    version keeping only technical terms, or the original if nothing remains.

    Args:
        query: The raw user query (may be conversational or technical).

    Returns:
        A condensed query with filler removed, or the original when
        condensation would discard all content or barely shorten it.
    """
    if not query:
        return query

    words = query.lower().split()
    technical = [w for w in words if w not in FILLER_WORDS and len(w) > 1]

    if not technical:
        return query

    # If condensation left very few words, append anchor terms to
    # give the embedding model enough signal to match code constructs.
    if len(technical) <= 2:
        technical.append("pipeline")
        technical.append("function")

    condensed = " ".join(technical)

    # Only return condensed if it is materially shorter than the original.
    if len(condensed) < len(query) * 0.9:
        return condensed
    return query


def expand_project_terms(query: str) -> str:
    """Append domain-specific synonyms for recognised project vocabulary.

    Scans *query* for words that match keys in
    ``_PROJECT_TERM_EXPANSIONS`` and appends the associated search tokens
    so that embedding similarity captures domain-specific relationships
    (e.g. "handler" also searches for "handle_" and "TOOL_HANDLERS").

    Args:
        query: The (possibly condensed) search query.

    Returns:
        The query with expansion terms appended, or the original when
        no recognised terms are found.
    """
    if not query:
        return query

    lower_words = {w.lower() for w in query.split()}
    expansions: list[str] = []

    for term, extras in _PROJECT_TERM_EXPANSIONS.items():
        if term in lower_words:
            expansions.extend(extras)

    if not expansions:
        return query

    return f"{query} {' '.join(expansions)}"
