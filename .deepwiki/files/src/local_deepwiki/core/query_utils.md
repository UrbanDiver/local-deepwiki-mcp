# File: `src/local_deepwiki/core/query_utils.py`

## File Overview

This module provides query preprocessing utilities designed to improve the effectiveness of embedding-based search. It contains two core functions: `condense_query` and `expand_project_terms`. These functions are intended to transform conversational user queries into forms that better align with technical terminology and domain-specific vocabulary, thus improving vector similarity matching.

The module is used by test utilities (`test_query_utils`) to validate query transformations. It is part of the `local_deepwiki.core` package and supports embedding search workflows where query quality directly affects retrieval accuracy.

## Key Concepts

### Query Condensation
The `condense_query` function addresses the problem of conversational queries diluting signal through filler words. It strips non-technical terms while preserving the core technical vocabulary. If the resulting query is too short, it appends anchor terms (`"pipeline"` and `"function"`) to maintain semantic richness for embedding models.

This approach was chosen because embedding models perform better when input text contains focused, technical terms rather than natural language filler. The heuristic ensures that condensation only occurs if it results in a meaningful reduction in length (at least 10% shorter), preserving the original query when condensation would be ineffective.

### Project Term Expansion
The `expand_project_terms` function enhances the query by appending domain-specific synonyms for recognized project terms. It uses a predefined mapping (`_PROJECT_TERM_EXPANSIONS`) to identify key terms and append related search tokens that help capture semantic relationships.

This technique improves recall in embedding-based search by expanding the search space without requiring explicit training data for every synonym. It leverages known vocabulary mappings to increase the likelihood of matching relevant code constructs or documentation.

## Integration

This module is used by `test_query_utils`, indicating its role in testing and validating the behavior of query preprocessing functions. While not directly imported by other modules in the provided code, its functions are expected to be integrated into embedding search pipelines where conversational queries are processed before being embedded.

The module supports the broader goal of improving semantic search fidelity by ensuring that user queries are transformed into representations that better align with internal technical terminology and code structures.

## Design Notes

### Edge Cases Handled
- **Empty or null queries**: Both functions return the input unchanged if the query is empty or None.
- **No technical terms after filtering**: If all words are filtered out, the original query is returned.
- **Minimal technical content**: When condensation results in very few words, anchor terms are appended to ensure sufficient signal for embeddings.

### Implementation Choices
- **Heuristic-based condensation**: The decision to condense is based on whether the new query is at least 10% shorter than the original. This prevents unnecessary transformation of already concise queries.
- **Anchor term insertion**: Adding `"pipeline"` and `"function"` ensures that even short condensed queries retain enough signal to match code constructs.
- **Expansion via dictionary lookup**: The use of `_PROJECT_TERM_EXPANSIONS` allows for easy extension and maintenance of domain-specific vocabulary mappings.

These choices reflect a balance between improving search quality and preserving the intent and structure of user queries.

## API Reference

### Functions

#### `condense_query`

```python
def condense_query(query: str) -> str
```

Strip filler words from a conversational query to improve embedding search.  Conversational queries like "tell me everything about how the rag works" embed poorly because filler dilutes the signal.  Returns a condensed version keeping only technical terms, or the original if nothing remains.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | - | The raw user query (may be conversational or technical). |

**Returns:** `str`



<details>
<summary>View Source (lines 79-113) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/query_utils.py#L79-L113">GitHub</a></summary>

```python
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
```

</details>

#### `expand_project_terms`

```python
def expand_project_terms(query: str) -> str
```

Append domain-specific synonyms for recognised project vocabulary.  Scans *query* for words that match keys in ``_PROJECT_TERM_EXPANSIONS`` and appends the associated search tokens so that embedding similarity captures domain-specific relationships (e.g. "handler" also searches for "handle_" and "TOOL_HANDLERS").


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | - | The (possibly condensed) search query. |

**Returns:** `str`




<details>
<summary>View Source (lines 116-144) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/query_utils.py#L116-L144">GitHub</a></summary>

```python
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
```

</details>

## Usage Examples

*Examples extracted from test files*

### Conversational filler like 'tell', 'everything', 'about' should be removed

From `test_query_utils.py::TestCondenseQuery::test_strips_filler_words`:

```python
result = condense_query("tell me everything about how the rag works")
lowered = result.lower()
assert "tell" not in lowered.split()
assert "everything" not in lowered.split()
assert "rag" in lowered
```

### Pure technical queries should pass through unchanged

From `test_query_utils.py::TestCondenseQuery::test_preserves_technical_terms`:

```python
query = "VectorStore search hybrid"
result = condense_query(query)
# All meaningful terms must survive
for term in ("vectorstore", "search", "hybrid"):
    assert term in result.lower()
```

### handler' should expand to include handler-specific search terms

From `test_query_utils.py::TestExpandProjectTerms::test_expands_handler`:

```python
result = expand_project_terms("handler architecture")
lowered = result.lower()
assert "handler" in lowered
assert "architecture" in lowered
# Should include at least one expansion term
assert "handle_" in lowered or "tool_handlers" in lowered
```

### provider' should expand to include provider-specific search terms

From `test_query_utils.py::TestExpandProjectTerms::test_expands_provider`:

```python
result = expand_project_terms("LLM provider setup")
lowered = result.lower()
assert "provider" in lowered
# Should include at least one expansion term
assert "llmprovider" in lowered or "get_llm_provider" in lowered
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `condense_query` | function | Brian Breidenbach | 2 weeks ago | `25048e9` refactor: extract _condense... |
| `expand_project_terms` | function | Brian Breidenbach | 2 weeks ago | `25048e9` refactor: extract _condense... |

## Relevant Source Files

- `src/local_deepwiki/core/query_utils.py:79-113`
