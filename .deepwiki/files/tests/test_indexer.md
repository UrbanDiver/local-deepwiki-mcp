# File Overview

This file, `tests/test_indexer.py`, contains unit tests for the `RepositoryIndexer` class and related functionality in the `local_deepwiki.core.indexer` module. It tests batched processing of code chunks, schema version handling, and migration logic for index status data.

# Classes

## TestBatchedProcessing

This class contains tests for the batched processing functionality of the indexer, ensuring that chunks are correctly processed in batches and that incremental updates work as expected.

### Methods

#### test_processes_chunks_in_batches
Tests that chunks are correctly processed in batches.

#### test_incremental_update_with_batching
Tests incremental update functionality with batching enabled.

#### test_empty_batch_handling
Tests handling of empty batches during processing.

## TestSchemaMigration

This class contains tests for schema migration logic, ensuring that index status data can be properly migrated between schema versions.

### Methods

#### test_current_schema_version_exists
Verifies that the current schema version constant is defined correctly.

#### test_needs_migration_old_version
Tests that migration is triggered for old schema versions.

#### test_needs_migration_current_version
Tests that migration is not triggered for current schema versions.

#### test_migrate_status_updates_version
Tests that migration updates the schema version correctly.

#### test_migrate_status_preserves_data
Tests that migration preserves existing data.

#### test_load_status_handles_legacy_files
Tests that loading status handles legacy files correctly.

#### test_save_status_includes_schema_version
Tests that saving status includes the schema version.

#### test_index_status_model_default_schema_version
Tests that the IndexStatus model defaults to schema_version=1.

#### test_migration_triggered_on_load
Tests that migration is triggered when loading legacy status files.

# Functions

## _migrate_status

Migrates an IndexStatus object to the current schema version.

### Parameters
- `status` (IndexStatus): The status object to migrate.

### Returns
- `tuple`: A tuple containing the migrated status and a boolean indicating if migration occurred.

## _needs_migration

Determines if an IndexStatus object needs migration to the current schema version.

### Parameters
- `status` (IndexStatus): The status object to check.

### Returns
- `bool`: True if migration is needed, False otherwise.

# Usage Examples

## Testing Batched Processing

```python
# Test that chunks are processed in batches
def test_processes_chunks_in_batches():
    # This test would mock the relevant methods and verify batch behavior
    pass
```

## Testing Schema Migration

```python
# Test that migration preserves existing data
def test_migrate_status_preserves_data():
    status = IndexStatus(
        repo_path="/test/repo",
        indexed_at=1234567890.0,
        total_files=10,
        total_chunks=100,
        languages={"python": 8, "javascript": 2},
        schema_version=1,
    )
    migrated, _ = _migrate_status(status)
    
    assert migrated.repo_path == "/test/repo"
    assert migrated.indexed_at == 1234567890.0
    assert migrated.total_files == 10
    assert migrated.total_chunks == 100
```

# Related Components

This file works with the following components:

- `RepositoryIndexer` from `local_deepwiki.core.indexer`
- `IndexStatus` from `local_deepwiki.models`
- [`ChunkingConfig`](../src/local_deepwiki/config.md) from `local_deepwiki.config`
- `CodeChunk` from `local_deepwiki.models`
- `Language` from `local_deepwiki.models`
- `ChunkType` from `local_deepwiki.models`

## API Reference

### class `TestChunkingConfigBatchSize`

Tests for batch_size configuration.

**Methods:**

#### `test_default_batch_size`

```python
def test_default_batch_size()
```

Test that default batch size is 500.

#### `test_custom_batch_size`

```python
def test_custom_batch_size()
```

Test that batch size can be customized.


### class `TestBatchedProcessing`

Tests for batched chunk processing in the indexer.

**Methods:**

#### `test_processes_chunks_in_batches`

```python
async def test_processes_chunks_in_batches(tmp_path)
```

Test that chunks are processed in batches to limit memory usage.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `mock_create_or_update_table`

```python
async def mock_create_or_update_table(chunks)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunks` | - | - | - |

#### `mock_add_chunks`

```python
async def mock_add_chunks(chunks)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunks` | - | - | - |

#### `mock_delete_chunks_by_file`

```python
async def mock_delete_chunks_by_file(file_path)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | - | - | - |

#### `test_incremental_update_with_batching`

```python
async def test_incremental_update_with_batching(tmp_path)
```

Test that incremental updates work with batched processing.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `mock_add_chunks`

```python
async def mock_add_chunks(chunks)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunks` | - | - | - |

#### `mock_delete_chunks_by_file`

```python
async def mock_delete_chunks_by_file(file_path)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | - | - | - |

#### `mock_create_or_update_table`

```python
async def mock_create_or_update_table(chunks)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunks` | - | - | - |

#### `test_empty_batch_handling`

```python
async def test_empty_batch_handling(tmp_path)
```

Test that empty repositories are handled correctly.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |


### class `TestBatchSizeConfiguration`

Tests for batch size in config.

**Methods:**

#### `test_batch_size_in_full_config`

```python
def test_batch_size_in_full_config()
```

Test that batch size is accessible in full config.

#### `test_batch_size_validation`

```python
def test_batch_size_validation()
```

Test that batch size accepts positive integers.


### class `TestSchemaMigration`

Tests for schema version migration.

**Methods:**

#### `test_current_schema_version_exists`

```python
def test_current_schema_version_exists()
```

Test that CURRENT_SCHEMA_VERSION is defined.

#### `test_needs_migration_old_version`

```python
def test_needs_migration_old_version()
```

Test that old schema versions need migration.

#### `test_needs_migration_current_version`

```python
def test_needs_migration_current_version()
```

Test that current schema version doesn't need migration.

#### `test_migrate_status_updates_version`

```python
def test_migrate_status_updates_version()
```

Test that migration updates the schema version.

#### `test_migrate_status_preserves_data`

```python
def test_migrate_status_preserves_data()
```

Test that migration preserves existing data.

#### `test_load_status_handles_legacy_files`

```python
async def test_load_status_handles_legacy_files(tmp_path)
```

Test that loading status handles legacy files without schema_version.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_save_status_includes_schema_version`

```python
async def test_save_status_includes_schema_version(tmp_path)
```

Test that saved status includes the current schema version.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_index_status_model_default_schema_version`

```python
async def test_index_status_model_default_schema_version()
```

Test that IndexStatus defaults to schema_version=1.

#### `test_migration_triggered_on_load`

```python
async def test_migration_triggered_on_load(tmp_path)
```

Test that migration is triggered when loading old schema version.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |



## Class Diagram

```mermaid
classDiagram
    class TestBatchSizeConfiguration {
        +test_batch_size_in_full_config()
        +test_batch_size_validation()
    }
    class TestBatchedProcessing {
        +test_processes_chunks_in_batches()
        +mock_create_or_update_table()
        +mock_add_chunks()
        +mock_delete_chunks_by_file()
        +test_incremental_update_with_batching()
        +test_empty_batch_handling()
    }
    class TestChunkingConfigBatchSize {
        +test_default_batch_size()
        +test_custom_batch_size()
    }
    class TestSchemaMigration {
        +test_current_schema_version_exists()
        +test_needs_migration_old_version()
        +test_needs_migration_current_version()
        +test_migrate_status_updates_version()
        +test_migrate_status_preserves_data()
        +test_load_status_handles_legacy_files()
        +test_save_status_includes_schema_version()
        +test_index_status_model_default_schema_version()
        +test_migration_triggered_on_load()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[AsyncMock]
    N1[ChunkingConfig]
    N2[Config]
    N3[IndexStatus]
    N4[MagicMock]
    N5[RepositoryIndexer]
    N6[TestBatchSizeConfiguration....]
    N7[TestBatchSizeConfiguration....]
    N8[TestBatchedProcessing.test_...]
    N9[TestBatchedProcessing.test_...]
    N10[TestBatchedProcessing.test_...]
    N11[TestChunkingConfigBatchSize...]
    N12[TestChunkingConfigBatchSize...]
    N13[TestSchemaMigration.test_in...]
    N14[TestSchemaMigration.test_lo...]
    N15[TestSchemaMigration.test_mi...]
    N16[TestSchemaMigration.test_mi...]
    N17[TestSchemaMigration.test_mi...]
    N18[TestSchemaMigration.test_ne...]
    N19[TestSchemaMigration.test_ne...]
    N20[TestSchemaMigration.test_sa...]
    N21[_load_status]
    N22[_migrate_status]
    N23[_needs_migration]
    N24[dumps]
    N25[load]
    N26[mkdir]
    N27[patch]
    N28[write_text]
    N12 --> N1
    N11 --> N1
    N10 --> N26
    N10 --> N28
    N10 --> N2
    N10 --> N27
    N10 --> N4
    N10 --> N0
    N10 --> N5
    N9 --> N26
    N9 --> N28
    N9 --> N2
    N9 --> N27
    N9 --> N4
    N9 --> N0
    N9 --> N5
    N8 --> N26
    N8 --> N2
    N8 --> N27
    N8 --> N4
    N8 --> N0
    N8 --> N5
    N6 --> N2
    N7 --> N1
    N19 --> N3
    N19 --> N23
    N18 --> N3
    N18 --> N23
    N16 --> N3
    N16 --> N22
    N15 --> N3
    N15 --> N22
    N14 --> N26
    N14 --> N2
    N14 --> N27
    N14 --> N4
    N14 --> N5
    N14 --> N28
    N14 --> N24
    N14 --> N21
    N20 --> N26
    N20 --> N28
    N20 --> N2
    N20 --> N27
    N20 --> N4
    N20 --> N0
    N20 --> N5
    N20 --> N25
    N13 --> N3
    N17 --> N26
    N17 --> N2
    N17 --> N27
    N17 --> N4
    N17 --> N5
    N17 --> N28
    N17 --> N24
    N17 --> N21
    N17 --> N25
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N21,N22,N23,N24,N25,N26,N27,N28 func
    classDef method fill:#fff3e0
    class N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20 method
```

## Relevant Source Files

- `tests/test_indexer.py:20-31`

## See Also

- [config](../src/local_deepwiki/config.md) - dependency
- [server](../src/local_deepwiki/server.md) - shares 5 dependencies
- [test_incremental_wiki](test_incremental_wiki.md) - shares 5 dependencies
