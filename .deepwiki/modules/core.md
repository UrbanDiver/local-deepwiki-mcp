# Core Module Documentation

## Module Purpose

The `core` module provides foundational components for the Local DeepWiki MCP Server, implementing core functionality for repository indexing, RAG-based question answering, and documentation generation. It includes components for parsing code, chunking content, vector storage, LLM interactions, secret detection, and tracing.

## Key Classes and Functions

### `GradedChunk`
Defined in `agentic_rag.py`

A dataclass representing a chunk of code with a relevance grade for agentic RAG workflows.

### `AuditEventType`
Defined in `audit.py`

An enumeration defining types of audit events that can be logged during repository operations.

### `get_parent_classes`
Defined in `chunk_extractors.py`

A function that extracts parent class information from AST nodes.

### `CodeChunker`
Defined in `chunker.py`

A class responsible for semantic code chunking using Tree-sitter AST parsing and chunk extraction functions.

### `NameEntry`
Defined in `fuzzy_search.py`

A dataclass representing a name entry used for fuzzy name matching during search suggestions.

### `BlameInfo`
Defined in `git_blame.py`

A dataclass containing Git blame information for code entities.

### `EntityType`
Defined in `graph_rag/models.py`

An enumeration defining types of entities in the knowledge graph.

### `GraphAugmentedRetriever`
Defined in `graph_rag/retriever.py`

A class that retrieves relevant chunks using graph-enhanced search techniques.

### `KnowledgeGraphStore`
Defined in `graph_rag/store.py`

A class managing a knowledge graph storage system for semantic relationships between code entities.

### `IndexStatusManager`
Defined in `index_manager.py`

A class that tracks index status and handles schema versioning for repository indexing.

### `RepositoryIndexer`
Defined in `indexer.py`

A class orchestrating the complete repository indexing pipeline including parsing, chunking, embedding, and wiki generation.

### `LLMCache`
Defined in `llm_cache.py`

An LRU cache implementation for storing and retrieving LLM responses to improve performance.

### `ParseResult`
Defined in `parsing_pipeline.py`

A dataclass representing the result of code parsing operations.

### `validate_file_in_repo`
Defined in `path_utils.py`

A function that validates file paths within a repository to prevent path traversal attacks.

### `condense_query`
Defined in `query_utils.py`

A function that condenses complex queries for improved search performance.

### `RateLimitExceeded`
Defined in `rate_limiter.py`

An exception class raised when API rate limits are exceeded.

### `Reranker`
Defined in `reranker.py`

A protocol defining the interface for reranking search results by relevance to a query.

### `CrossEncoderReranker`
Defined in `reranker.py`

A concrete implementation of the [`Reranker`](../files/src/local_deepwiki/core/reranker.md) protocol using sentence-transformers CrossEncoder for cross-encoder reranking.

### `get_reranker`
Defined in `reranker.py`

A factory function that returns a configured [`CrossEncoderReranker`](../files/src/local_deepwiki/core/reranker.md) instance or `None`.

### `SecretType`
Defined in `secret_detector.py`

An enumeration of secret types that can be detected, including AWS keys, API keys, private keys, and more.

### `SecretFinding`
Defined in `secret_detector.py`

A dataclass representing a detected secret in code with details about type, location, confidence, and recommendation.

### `SecretDetector`
Defined in `secret_detector.py`

A class that scans code for hardcoded credentials using regular expression patterns and false positive filtering.

### `RAGTrace`
Defined in `tracing.py`

A dataclass for tracking RAG (Retrieval-Augmented Generation) operation metrics including retrieval, reranking, context processing, and LLM interaction times.

## How Components Interact

The core module components work together as follows:

1. **Repository Indexing Pipeline**: The [`RepositoryIndexer`](../files/src/local_deepwiki/core/indexer.md) orchestrates the complete indexing process, delegating to:
   - [`CodeChunker`](../files/src/local_deepwiki/core/chunker.md) for semantic code chunking
   - [`SecretDetector`](../files/src/local_deepwiki/core/secret_detector.md) for security scanning during indexing
   - [`LLMCache`](../files/src/local_deepwiki/core/llm_cache.md) for caching LLM responses during documentation generation
   - [`IndexStatusManager`](../files/src/local_deepwiki/core/index_manager.md) for tracking index state and schema versions

2. **RAG Operations**: During question answering, components interact through:
   - [`GraphAugmentedRetriever`](../files/src/local_deepwiki/core/graph_rag/retriever.md) and [`KnowledgeGraphStore`](../files/src/local_deepwiki/core/graph_rag/store.md) for graph-enhanced retrieval
   - [`Reranker`](../files/src/local_deepwiki/core/reranker.md) implementations (specifically [`CrossEncoderReranker`](../files/src/local_deepwiki/core/reranker.md)) to improve search result relevance
   - [`RAGTrace`](../files/src/local_deepwiki/core/tracing.md) for performance monitoring and debugging

3. **Security**: The [`SecretDetector`](../files/src/local_deepwiki/core/secret_detector.md) scans code during indexing to identify hardcoded credentials, preventing security issues.

4. **Performance Optimization**: 
   - [`LLMCache`](../files/src/local_deepwiki/core/llm_cache.md) caches expensive LLM calls
   - [`RateLimitExceeded`](../files/src/local_deepwiki/core/rate_limiter.md) handles API rate limiting
   - [`CrossEncoderReranker`](../files/src/local_deepwiki/core/reranker.md) provides efficient cross-encoder reranking in a thread pool

## Usage Examples

### Using the Reranker```python
from local_deepwiki.core.reranker import get_reranker
from local_deepwiki.models import SearchResult

# Get a configured reranker
reranker = get_reranker("cross-encoder/ms-marco-MiniLM-L-6-v2")

# Use it to rerank results
query = "How does the authentication work?"
results = [SearchResult(...)]  # Your search results
reranked_results = await reranker.rerank(query, results, top_k=5)
```
### Using the Secret Detector```python
from local_deepwiki.core.secret_detector import scan_repository_for_secrets

# Scan a repository for hardcoded secrets
findings = scan_repository_for_secrets("/path/to/repo")
for file_path, secrets in findings.items():
    print(f"Secrets found in {file_path}:")
    for secret in secrets:
        print(f"  - {secret.secret_type} at line {secret.line_number}")
```
### Using the Index Status Manager```python
from local_deepwiki.core.index_manager import IndexStatusManager

# Initialize status manager
status_manager = IndexStatusManager("/path/to/index")

# Check current index status
status = status_manager.get_status()
print(f"Index schema version: {status.schema_version}")
```
### Using the LLM Cache```python
from local_deepwiki.core.llm_cache import LLMCache

# Initialize cache with max size
cache = LLMCache(max_size=100)

# Check if response is cached
key = "prompt_hash_abc123"
if key in cache:
    response = cache[key]
else:
    # Generate response (expensive operation)
    response = generate_response(prompt)
    cache[key] = response
```
## Dependencies

This module depends on:
- `asyncio`
- `dataclasses` 
- `datetime`
- `enum`
- `json`
- `LanceDB`
- `local_deepwiki.logging`
- `local_deepwiki.models`
- `sentence_transformers` (optional, only when using [CrossEncoderReranker](../files/src/local_deepwiki/core/reranker.md))
- `tree-sitter` (via parser components)
- `tqdm` (for progress tracking in some operations)

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/core/reranker.py:20-44`](../files/src/local_deepwiki/core/reranker.md)
- [`src/local_deepwiki/core/secret_detector.py:29-58`](../files/src/local_deepwiki/core/secret_detector.md)
- [`src/local_deepwiki/core/tracing.py:16-146`](../files/src/local_deepwiki/core/tracing.md)
- [`src/local_deepwiki/core/audit.py:31-62`](../files/src/local_deepwiki/core/audit.md)
- [`src/local_deepwiki/core/chunker.py:55-665`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/core/llm_cache.py:21-472`](../files/src/local_deepwiki/core/llm_cache.md)
- [`src/local_deepwiki/core/agentic_rag.py:30-34`](../files/src/local_deepwiki/core/agentic_rag.md)
- [`src/local_deepwiki/core/index_manager.py:67-380`](../files/src/local_deepwiki/core/index_manager.md)
- [`src/local_deepwiki/core/rate_limiter.py:39-59`](../files/src/local_deepwiki/core/rate_limiter.md)
- [`src/local_deepwiki/core/parsing_pipeline.py:27-33`](../files/src/local_deepwiki/core/parsing_pipeline.md)


*Showing 10 of 49 source files.*
