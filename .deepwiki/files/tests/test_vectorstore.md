# test_vectorstore.py

## File Overview

This file contains comprehensive test suites for the [VectorStore](../src/local_deepwiki/core/vectorstore.md) component, covering functionality like chunk indexing, search operations, statistics, and edge cases. The tests use pytest fixtures and a mock embedding provider to verify vector store behavior across different scenarios.

## Test Classes

### TestVectorStoreIndexes

Tests for vector store scalar indexes functionality.

**Key Test Methods:**
- `vector_store()` - Fixture that creates a [VectorStore](../src/local_deepwiki/core/vectorstore.md) instance for testing using a temporary Lance database
- `populated_store()` - Fixture that creates a vector store pre-populated with test data

### TestVectorStoreSearch

Tests for vector store search functionality.

**Key Test Methods:**
- `vector_store()` - Fixture that creates a [VectorStore](../src/local_deepwiki/core/vectorstore.md) instance for testing
- `test_search_empty_store()` - Verifies that searching an empty store returns empty results

### TestVectorStoreStats

Tests for vector store statistics functionality.

**Key Test Methods:**
- `vector_store()` - Fixture that creates a [VectorStore](../src/local_deepwiki/core/vectorstore.md) instance for testing
- `test_stats_empty_store()` - Tests that statistics for an empty store show zero chunks and empty language mapping

### TestVectorStoreAddChunks

Tests for adding chunks to existing vector store tables.

**Key Test Methods:**
- `vector_store()` - Fixture that creates a [VectorStore](../src/local_deepwiki/core/vectorstore.md) instance for testing
- `test_add_to_empty_creates_table()` - Verifies that adding chunks to an empty store creates the underlying table

### TestVectorStoreEdgeCases

Comprehensive tests for edge cases and error conditions in vector store operations.

**Key Test Methods:**
- `vector_store()` - Fixture that creates a [VectorStore](../src/local_deepwiki/core/vectorstore.md) instance for testing
- `test_get_chunk_by_id_empty_db()` - Tests that retrieving a chunk by ID from an empty database returns None
- `test_get_chunks_by_file_empty_db()` - Tests that retrieving chunks by file from an empty database returns an empty list
- `test_delete_chunks_by_file_empty_db()` - Tests that deleting chunks by file from an empty database returns 0
- `test_create_or_update_empty_list()` - Tests that creating/updating with an empty chunk list returns 0
- `test_chunk_id_with_quotes()` - Tests handling of chunk IDs containing quote characters
- `test_file_path_with_quotes()` - Tests safe handling of file paths containing quote characters
- `test_delete_file_path_with_quotes()` - Tests safe deletion of files with quote characters in paths
- `test_file_path_injection_attempt()` - Tests that SQL-like injection attempts in file paths are neutralized
- `test_search_limit_zero_raises()` - Tests that searching with a limit of 0 raises a ValueError

## Usage Examples

### Setting Up Test Vector Store

```python
@pytest.fixture
def vector_store(self, tmp_path):
    """Create a vector store for testing."""
    from local_deepwiki.core.vectorstore import VectorStore

    db_path = tmp_path / "test.lance"
    provider = MockEmbeddingProvider()
    return VectorStore(db_path, provider)
```

### Testing Empty Store Statistics

```python
def test_stats_empty_store(self, vector_store):
    """Test stats for empty store."""
    stats = vector_store.get_stats()
    assert stats["total_chunks"] == 0
    assert stats["languages"] == {}
```

### Testing Search Limit Validation

```python
async def test_search_limit_zero_raises(self, vector_store):
    """Test search with limit=0 raises ValueError."""
    chunk = make_chunk("test")
    await vector_store.create_or_update_table([chunk])

    # LanceDB requires limit > 0 for vector searches
    with pytest.raises(ValueError, match="Limit is required"):
        await vector_store.search("test", limit=0)
```

## Related Components

This test file works with several components from the local_deepwiki package:

- **[VectorStore](../src/local_deepwiki/core/vectorstore.md)** - The [main](../src/local_deepwiki/export/html.md) class being tested, imported from `local_deepwiki.core.vectorstore`
- **[EmbeddingProvider](../src/local_deepwiki/providers/base.md)** - Base class for embedding providers, imported from `local_deepwiki.providers.base`
- **[ChunkType](../src/local_deepwiki/models.md), [CodeChunk](../src/local_deepwiki/models.md), [Language](../src/local_deepwiki/models.md)** - Data models imported from `local_deepwiki.models`
- **MockEmbeddingProvider** - A mock implementation used for testing (defined within the test file)

The tests verify integration between the [VectorStore](../src/local_deepwiki/core/vectorstore.md) and these components, ensuring proper handling of chunks, embeddings, and database operations across various scenarios including edge cases and error conditions.

## API Reference

### class `MockEmbeddingProvider`

**Inherits from:** [`EmbeddingProvider`](../src/local_deepwiki/providers/base.md)

Mock embedding provider for testing.

**Methods:**

#### `__init__`

```python
def __init__(dimension: int = 384)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `dimension` | `int` | `384` | - |

#### `name`

```python
def name() -> str
```

Return provider name.

#### `get_dimension`

```python
def get_dimension() -> int
```

Return embedding dimension.

#### `embed`

```python
async def embed(texts: list[str]) -> list[list[float]]
```

Generate mock embeddings.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `texts` | `list[str]` | - | - |


### class `TestVectorStoreIndexes`

Tests for vector store scalar indexes.

**Methods:**

#### `vector_store`

```python
def vector_store(tmp_path)
```

Create a vector store for testing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `populated_store`

```python
async def populated_store(vector_store)
```

Create a vector store with test data.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_create_table_creates_indexes`

```python
async def test_create_table_creates_indexes(populated_store)
```

Test that creating a table creates scalar indexes.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `populated_store` | - | - | - |

#### `test_get_chunk_by_id_uses_index`

```python
async def test_get_chunk_by_id_uses_index(populated_store)
```

Test that get_chunk_by_id can [find](../src/local_deepwiki/generators/manifest.md) chunks efficiently.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `populated_store` | - | - | - |

#### `test_get_chunks_by_file_uses_index`

```python
async def test_get_chunks_by_file_uses_index(populated_store)
```

Test that get_chunks_by_file can [find](../src/local_deepwiki/generators/manifest.md) chunks efficiently.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `populated_store` | - | - | - |

#### `test_delete_chunks_by_file_uses_index`

```python
async def test_delete_chunks_by_file_uses_index(populated_store)
```

Test that delete_chunks_by_file works efficiently.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `populated_store` | - | - | - |

#### `test_ensure_indexes_on_existing_table`

```python
async def test_ensure_indexes_on_existing_table(vector_store, tmp_path)
```

Test that opening an existing table ensures indexes exist.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |
| `tmp_path` | - | - | - |


### class `TestVectorStoreSearch`

Tests for vector store search functionality.

**Methods:**

#### `vector_store`

```python
def vector_store(tmp_path)
```

Create a vector store for testing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_search_empty_store`

```python
async def test_search_empty_store(vector_store)
```

Test searching an empty store returns empty results.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_with_results`

```python
async def test_search_with_results(vector_store)
```

Test searching returns results.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_with_language_filter`

```python
async def test_search_with_language_filter(vector_store)
```

Test searching with language filter.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_invalid_language_raises`

```python
async def test_search_invalid_language_raises(vector_store)
```

Test searching with invalid language raises ValueError.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_with_chunk_type_filter`

```python
async def test_search_with_chunk_type_filter(vector_store)
```

Test searching with chunk type filter.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_invalid_chunk_type_raises`

```python
async def test_search_invalid_chunk_type_raises(vector_store)
```

Test searching with invalid chunk type raises ValueError.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |


### class `TestVectorStoreStats`

Tests for vector store statistics.

**Methods:**

#### `vector_store`

```python
def vector_store(tmp_path)
```

Create a vector store for testing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_stats_empty_store`

```python
def test_stats_empty_store(vector_store)
```

Test stats for empty store.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_stats_with_data`

```python
async def test_stats_with_data(vector_store)
```

Test stats with data.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |


### class `TestVectorStoreAddChunks`

Tests for adding chunks to existing table.

**Methods:**

#### `vector_store`

```python
def vector_store(tmp_path)
```

Create a vector store for testing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_add_to_empty_creates_table`

```python
async def test_add_to_empty_creates_table(vector_store)
```

Test adding to empty store creates table.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_add_to_existing_table`

```python
async def test_add_to_existing_table(vector_store)
```

Test adding chunks to existing table.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_add_empty_list`

```python
async def test_add_empty_list(vector_store)
```

Test adding empty list returns 0.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |


### class `TestVectorStoreEdgeCases`

Tests for vector store edge cases and error handling.

**Methods:**

#### `vector_store`

```python
def vector_store(tmp_path)
```

Create a vector store for testing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_get_chunk_by_id_empty_db`

```python
async def test_get_chunk_by_id_empty_db(vector_store)
```

Test get_chunk_by_id on empty database returns None.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_get_chunks_by_file_empty_db`

```python
async def test_get_chunks_by_file_empty_db(vector_store)
```

Test get_chunks_by_file on empty database returns empty list.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_delete_chunks_by_file_empty_db`

```python
async def test_delete_chunks_by_file_empty_db(vector_store)
```

Test delete_chunks_by_file on empty database returns 0.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_create_or_update_empty_list`

```python
async def test_create_or_update_empty_list(vector_store)
```

Test create_or_update_table with empty list returns 0.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_chunk_id_with_quotes`

```python
async def test_chunk_id_with_quotes(vector_store)
```

Test chunk ID with single quotes is handled safely.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_file_path_with_quotes`

```python
async def test_file_path_with_quotes(vector_store)
```

Test file path with quotes is handled safely.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_delete_file_path_with_quotes`

```python
async def test_delete_file_path_with_quotes(vector_store)
```

Test deleting file path with quotes is handled safely.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_chunk_id_injection_attempt`

```python
async def test_chunk_id_injection_attempt(vector_store)
```

Test that SQL-like injection in chunk_id is neutralized.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_file_path_injection_attempt`

```python
async def test_file_path_injection_attempt(vector_store)
```

Test that SQL-like injection in file_path is neutralized.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_unicode_content`

```python
async def test_unicode_content(vector_store)
```

Test handling of Unicode content in chunks.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_reopen_database`

```python
async def test_reopen_database(tmp_path)
```

Test reopening database preserves data.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_replace_existing_table`

```python
async def test_replace_existing_table(vector_store)
```

Test create_or_update_table replaces existing data.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_db_path_created_if_not_exists`

```python
async def test_db_path_created_if_not_exists(tmp_path)
```

Test that database directory is created if it doesn't exist.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_single_chunk_operations`

```python
async def test_single_chunk_operations(vector_store)
```

Test operations with single chunk.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_empty_content_chunk`

```python
async def test_empty_content_chunk(vector_store)
```

Test chunk with empty content.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_large_content_chunk`

```python
async def test_large_content_chunk(vector_store)
```

Test chunk with large content.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_many_chunks_same_file`

```python
async def test_many_chunks_same_file(vector_store)
```

Test many chunks from same file.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_limit_zero_raises`

```python
async def test_search_limit_zero_raises(vector_store)
```

Test search with limit=0 raises ValueError.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |

#### `test_search_very_long_query`

```python
async def test_search_very_long_query(vector_store)
```

Test search with very long query string.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector_store` | - | - | - |


---

### Functions

#### `make_chunk`

```python
def make_chunk(id: str, file_path: str = "test.py", content: str = "test code", language: Language = Language.PYTHON, chunk_type: ChunkType = ChunkType.FUNCTION) -> CodeChunk
```

Create a test code chunk.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `id` | `str` | - | - |
| `file_path` | `str` | `"test.py"` | - |
| `content` | `str` | `"test code"` | - |
| `language` | [`Language`](../src/local_deepwiki/models.md) | `Language.PYTHON` | - |
| `chunk_type` | [`ChunkType`](../src/local_deepwiki/models.md) | `ChunkType.FUNCTION` | - |

**Returns:** [`CodeChunk`](../src/local_deepwiki/models.md)



## Class Diagram

```mermaid
classDiagram
    class MockEmbeddingProvider {
        -_dimension
        +embed_calls: list[list[str]]
        -__init__()
        +name() -> str
        +get_dimension() -> int
        +embed() -> list[list[float]]
    }
    class TestVectorStoreAddChunks {
        +vector_store()
        +test_add_to_empty_creates_table()
        +test_add_to_existing_table()
        +test_add_empty_list()
    }
    class TestVectorStoreEdgeCases {
        +vector_store(tmp_path)
        +test_get_chunk_by_id_empty_db(vector_store)
        +test_get_chunks_by_file_empty_db(vector_store)
        +test_delete_chunks_by_file_empty_db(vector_store)
        +test_create_or_update_empty_list(vector_store)
        +test_chunk_id_with_quotes(vector_store)
        +test_file_path_with_quotes(vector_store)
        +test_delete_file_path_with_quotes(vector_store)
        +test_chunk_id_injection_attempt(vector_store)
        +test_file_path_injection_attempt(vector_store)
        +test_unicode_content(vector_store)
        +test_reopen_database(tmp_path)
        +test_replace_existing_table(vector_store)
        +test_db_path_created_if_not_exists(tmp_path)
        +test_single_chunk_operations(vector_store)
    }
    class TestVectorStoreIndexes {
        +vector_store()
        +populated_store()
        +main()
        +helper()
        +util()
        +test()
        +test_create_table_creates_indexes()
        +test_get_chunk_by_id_uses_index()
        +test_get_chunks_by_file_uses_index()
        +test_delete_chunks_by_file_uses_index()
        +test_ensure_indexes_on_existing_table()
    }
    class TestVectorStoreSearch {
        +vector_store()
        +test_search_empty_store()
        +test_search_with_results()
        +calculate_sum()
        +calculate_product()
        +test_search_with_language_filter()
        +test_search_invalid_language_raises()
        +test_search_with_chunk_type_filter()
        +test_search_invalid_chunk_type_raises()
    }
    class TestVectorStoreStats {
        +vector_store()
        +test_stats_empty_store()
        +test_stats_with_data()
    }
    MockEmbeddingProvider --|> EmbeddingProvider
```

## Call Graph

```mermaid
flowchart TD
    N0[MockEmbeddingProvider]
    N1[TestVectorStoreAddChunks.te...]
    N2[TestVectorStoreAddChunks.te...]
    N3[TestVectorStoreEdgeCases.te...]
    N4[TestVectorStoreEdgeCases.te...]
    N5[TestVectorStoreEdgeCases.te...]
    N6[TestVectorStoreEdgeCases.te...]
    N7[TestVectorStoreEdgeCases.te...]
    N8[TestVectorStoreEdgeCases.te...]
    N9[TestVectorStoreEdgeCases.te...]
    N10[TestVectorStoreEdgeCases.te...]
    N11[TestVectorStoreEdgeCases.te...]
    N12[TestVectorStoreEdgeCases.te...]
    N13[TestVectorStoreIndexes.test...]
    N14[TestVectorStoreSearch.test_...]
    N15[TestVectorStoreSearch.test_...]
    N16[TestVectorStoreSearch.test_...]
    N17[TestVectorStoreSearch.test_...]
    N18[TestVectorStoreSearch.test_...]
    N19[TestVectorStoreStats.test_s...]
    N20[VectorStore]
    N21[add_chunks]
    N22[create_or_update_table]
    N23[delete_chunks_by_file]
    N24[get_chunk_by_id]
    N25[get_chunks_by_file]
    N26[get_stats]
    N27[make_chunk]
    N28[raises]
    N29[search]
    N13 --> N27
    N13 --> N22
    N13 --> N20
    N13 --> N0
    N13 --> N24
    N18 --> N27
    N18 --> N22
    N18 --> N29
    N17 --> N27
    N17 --> N22
    N17 --> N29
    N15 --> N27
    N15 --> N22
    N15 --> N28
    N15 --> N29
    N16 --> N27
    N16 --> N22
    N16 --> N29
    N14 --> N27
    N14 --> N22
    N14 --> N28
    N14 --> N29
    N19 --> N27
    N19 --> N22
    N19 --> N26
    N1 --> N27
    N1 --> N21
    N1 --> N26
    N2 --> N27
    N2 --> N22
    N2 --> N21
    N2 --> N26
    N4 --> N27
    N4 --> N22
    N4 --> N24
    N7 --> N27
    N7 --> N22
    N7 --> N25
    N6 --> N27
    N6 --> N22
    N6 --> N23
    N3 --> N27
    N3 --> N22
    N3 --> N24
    N9 --> N0
    N9 --> N20
    N9 --> N27
    N9 --> N22
    N9 --> N24
    N10 --> N27
    N10 --> N22
    N10 --> N26
    N10 --> N24
    N5 --> N0
    N5 --> N20
    N5 --> N27
    N5 --> N22
    N12 --> N27
    N12 --> N22
    N12 --> N29
    N12 --> N24
    N12 --> N26
    N8 --> N27
    N8 --> N22
    N8 --> N25
    N8 --> N23
    N11 --> N27
    N11 --> N22
    N11 --> N28
    N11 --> N29
    classDef func fill:#e1f5fe
    class N0,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19 method
```

## Relevant Source Files

- `tests/test_vectorstore.py:9-28`

## See Also

- [vectorstore](../src/local_deepwiki/core/vectorstore.md) - dependency
- [models](../src/local_deepwiki/models.md) - dependency
- [test_chunker](test_chunker.md) - shares 2 dependencies
- [test_see_also](test_see_also.md) - shares 2 dependencies
- [test_api_docs](test_api_docs.md) - shares 2 dependencies
