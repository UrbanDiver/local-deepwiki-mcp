# Vector Store Module

## File Overview

The `vectorstore.py` module provides a vector database implementation using LanceDB for storing and searching code chunks. It serves as the core storage layer for the local deepwiki system, enabling semantic search capabilities over code repositories.

## Classes

### VectorStore

The `VectorStore` class provides methods for managing a vector database of code chunks. It handles database connections, table operations, chunk storage, and semantic search functionality.

#### Key Methods

- `__init__(self, db_path: str, embedding_provider: EmbeddingProvider)`: Initializes the vector store with a database path and embedding provider
- `_connect(self)`: Establishes connection to the LanceDB database
- `_get_table(self)`: Retrieves or creates the database table
- `create_or_update_table(self)`: Creates or updates the database table schema
- `add_chunks(self, chunks: list[CodeChunk])`: Adds code chunks to the vector store
- `search(self, query: str, limit: int = 10)`: Performs semantic search on the vector store
- `get_chunk_by_id(self, chunk_id: str)`: Retrieves a specific chunk by ID
- `get_chunks_by_file(self, file_path: str)`: Retrieves all chunks for a given file
- `delete_chunks_by_file(self, file_path: str)`: Deletes all chunks associated with a file
- `get_stats(self)`: Returns database statistics
- `_chunk_to_text(self, chunk: CodeChunk)`: Converts a code chunk to text format for embedding

## Usage Examples

```python
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.providers.openai import OpenAIEmbeddingProvider

# Initialize the vector store
embedding_provider = OpenAIEmbeddingProvider(api_key="your-api-key")
vector_store = VectorStore(db_path="./vector_db", embedding_provider=embedding_provider)

# Add code chunks to the store
chunks = [
    CodeChunk(id="chunk1", file_path="src/main.py", content="def hello():\n    print('Hello')", start_line=1, end_line=2),
    CodeChunk(id="chunk2", file_path="src/main.py", content="def world():\n    print('World')", start_line=3, end_line=4)
]
vector_store.add_chunks(chunks)

# Perform semantic search
results = vector_store.search("function that prints hello", limit=5)
for result in results:
    print(f"Chunk ID: {result.chunk_id}, Score: {result.score}")
```

## Dependencies

This module imports:
- `json` - For JSON serialization/deserialization
- `pathlib.Path` - For file path operations
- `typing.Any` - For type hints
- `lancedb` - For vector database operations
- `lancedb.table.Table` - For database table operations
- `local_deepwiki.models.CodeChunk` - For code chunk data structures
- `local_deepwiki.models.SearchResult` - For search result data structures
- `local_deepwiki.providers.base.EmbeddingProvider` - For embedding generation interface

## Detailed Method Documentation

### `__init__(self, db_path: str, embedding_provider: EmbeddingProvider)`

Initializes the VectorStore with database path and embedding provider.

**Parameters:**
- `db_path` (str): Path to the LanceDB database
- `embedding_provider` (EmbeddingProvider): Provider for generating embeddings

### `_connect(self)`

Establishes connection to the LanceDB database.

### `_get_table(self)`

Retrieves or creates the database table for code chunks.

### `create_or_update_table(self)`

Creates or updates the database table schema to ensure compatibility with current requirements.

### `add_chunks(self, chunks: list[CodeChunk])`

Adds multiple code chunks to the vector store.

**Parameters:**
- `chunks` (list[CodeChunk]): List of code chunks to add

### `search(self, query: str, limit: int = 10)`

Performs semantic search on the vector store.

**Parameters:**
- `query` (str): Search query text
- `limit` (int): Maximum number of results to return (default: 10)

**Returns:**
- `list[SearchResult]`: List of search results with chunk IDs and similarity scores

### `get_chunk_by_id(self, chunk_id: str)`

Retrieves a specific code chunk by its ID.

**Parameters:**
- `chunk_id` (str): Unique identifier for the chunk

**Returns:**
- `CodeChunk`: The requested code chunk

### `get_chunks_by_file(self, file_path: str)`

Retrieves all code chunks associated with a specific file.

**Parameters:**
- `file_path` (str): Path to the source file

**Returns:**
- `list[CodeChunk]`: List of code chunks for the specified file

### `delete_chunks_by_file(self, file_path: str)`

Deletes all code chunks associated with a specific file.

**Parameters:**
- `file_path` (str): Path to the source file

### `get_stats(self)`

Returns database statistics including total chunks and table information.

**Returns:**
- `dict`: Database statistics

### `_chunk_to_text(self, chunk: CodeChunk)`

Converts a code chunk to text format for embedding generation.

**Parameters:**
- `chunk` (CodeChunk): The code chunk to convert

**Returns:**
- `str`: Text representation of the code chunk