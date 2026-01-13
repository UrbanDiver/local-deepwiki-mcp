# File Overview

This file contains tests for the incremental wiki generation functionality. It tests the models and helper methods used to track wiki page generation status and determine whether regeneration is needed based on source file changes.

# Classes

## TestWikiPageStatus

Test class for the WikiPageStatus model.

### Methods

#### test_create_page_status
Test creating a WikiPageStatus.

## TestWikiGenerationStatus

Test class for the WikiGenerationStatus model.

### Methods

#### test_create_generation_status
Test creating a WikiGenerationStatus.

#### test_generation_status_with_pages
Test generation status with page statuses.

## TestWikiGeneratorHelpers

Test class for helper methods in [WikiGenerator](../src/local_deepwiki/generators/wiki.md).

### Methods

#### mock_wiki_generator
Create a mock [WikiGenerator](../src/local_deepwiki/generators/wiki.md).

#### test_compute_content_hash
Test computing content hash.

#### test_needs_regeneration_no_previous_status
Test needs_regeneration when no previous status exists.

#### test_needs_regeneration_page_not_in_status
Test needs_regeneration when page not in previous status.

#### test_needs_regeneration_source_hash_changed
Test needs_regeneration when source file hash changed.

#### test_needs_regeneration_no_changes
Test needs_regeneration when nothing changed.

#### test_needs_regeneration_source_files_changed
Test needs_regeneration when source files list changed.

#### test_record_page_status
Test recording page status.

## TestWikiStatusPersistence

Test class for wiki status file persistence.

### Methods

#### test_save_and_load_wiki_status
Test saving and loading wiki status.

## TestLoadExistingPage

Test class for loading existing wiki pages.

### Methods

#### test_load_existing_page
Test loading an existing page from disk.

# Functions

## mock_wiki_generator

Create a mock [WikiGenerator](../src/local_deepwiki/generators/wiki.md).

**Returns**: A mock [WikiGenerator](../src/local_deepwiki/generators/wiki.md) instance with predefined attributes.

# Usage Examples

## Testing WikiPageStatus Creation

```python
def test_create_page_status(self):
    status = WikiPageStatus(
        path="files/test.md",
        source_files=["src/test.py"],
        source_hashes={"src/test.py": "abc123"},
        content_hash="def456",
        generated_at=time.time(),
    )
    assert status.path == "files/test.md"
```

## Testing WikiGenerationStatus Creation

```python
def test_create_generation_status(self):
    status = WikiGenerationStatus(
        repo_path="/path/to/repo",
        generated_at=time.time(),
        total_pages=5,
        index_status_hash="abc123",
        pages={},
    )
    assert status.repo_path == "/path/to/repo"
    assert status.total_pages == 5
```

## Testing Page Status Recording

```python
def test_record_page_status(self, mock_wiki_generator):
    page = WikiPage(
        path="test.md",
        title="Test",
        content="# Test\nContent here",
        generated_at=time.time(),
    )
    mock_wiki_generator._record_page_status(page, ["src/test.py"])
    assert "test.md" in mock_wiki_generator._page_statuses
```

# Related Components

This file works with the following components:

- [WikiGenerator](../src/local_deepwiki/generators/wiki.md) class
- WikiPageStatus model
- WikiGenerationStatus model
- WikiPage model
- FileInfo model
- IndexStatus model
- Language model

The tests use mocking to isolate the functionality being tested, particularly the [WikiGenerator](../src/local_deepwiki/generators/wiki.md) class and its helper methods.

## API Reference

### class `TestWikiPageStatus`

Test WikiPageStatus model.

**Methods:**

#### `test_create_page_status`

```python
def test_create_page_status()
```

Test creating a WikiPageStatus.

#### `test_page_status_multiple_sources`

```python
def test_page_status_multiple_sources()
```

Test page status with multiple source files.


### class `TestWikiGenerationStatus`

Test WikiGenerationStatus model.

**Methods:**

#### `test_create_generation_status`

```python
def test_create_generation_status()
```

Test creating a WikiGenerationStatus.

#### `test_generation_status_with_pages`

```python
def test_generation_status_with_pages()
```

Test generation status with page statuses.


### class `TestWikiGeneratorHelpers`

Test [WikiGenerator](../src/local_deepwiki/generators/wiki.md) helper methods.

**Methods:**

#### `mock_wiki_generator`

```python
def mock_wiki_generator()
```

Create a mock [WikiGenerator](../src/local_deepwiki/generators/wiki.md).

#### `test_compute_content_hash`

```python
def test_compute_content_hash(mock_wiki_generator)
```

Test content hash computation.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |

#### `test_needs_regeneration_no_previous_status`

```python
def test_needs_regeneration_no_previous_status(mock_wiki_generator)
```

Test needs_regeneration when no previous status exists.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |

#### `test_needs_regeneration_page_not_in_status`

```python
def test_needs_regeneration_page_not_in_status(mock_wiki_generator)
```

Test needs_regeneration when page not in previous status.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |

#### `test_needs_regeneration_source_hash_changed`

```python
def test_needs_regeneration_source_hash_changed(mock_wiki_generator)
```

Test needs_regeneration when source file hash changed.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |

#### `test_needs_regeneration_no_changes`

```python
def test_needs_regeneration_no_changes(mock_wiki_generator)
```

Test needs_regeneration when nothing changed.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |

#### `test_needs_regeneration_source_files_changed`

```python
def test_needs_regeneration_source_files_changed(mock_wiki_generator)
```

Test needs_regeneration when source files list changed.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |

#### `test_record_page_status`

```python
def test_record_page_status(mock_wiki_generator)
```

Test recording page status.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `mock_wiki_generator` | - | - | - |


### class `TestWikiStatusPersistence`

Test wiki status file persistence.

**Methods:**

#### `test_save_and_load_wiki_status`

```python
async def test_save_and_load_wiki_status(tmp_path)
```

Test saving and loading wiki status.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_load_missing_status`

```python
async def test_load_missing_status(tmp_path)
```

Test loading when status file doesn't exist.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_load_corrupted_status`

```python
async def test_load_corrupted_status(tmp_path)
```

Test loading when status file is corrupted.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |


### class `TestLoadExistingPage`

Test loading existing wiki pages.

**Methods:**

#### `test_load_existing_page`

```python
async def test_load_existing_page(tmp_path)
```

Test loading an existing page from disk.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_load_missing_page`

```python
async def test_load_missing_page(tmp_path)
```

Test loading a page that doesn't exist.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_load_page_uses_previous_timestamp`

```python
async def test_load_page_uses_previous_timestamp(tmp_path)
```

Test that loaded page uses timestamp from previous status.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |



## Class Diagram

```mermaid
classDiagram
    class TestLoadExistingPage {
        +test_load_existing_page()
        +test_load_missing_page()
        +test_load_page_uses_previous_timestamp()
    }
    class TestWikiGenerationStatus {
        +test_create_generation_status()
        +test_generation_status_with_pages()
    }
    class TestWikiGeneratorHelpers {
        +mock_wiki_generator()
        +test_compute_content_hash()
        +test_needs_regeneration_no_previous_status()
        +test_needs_regeneration_page_not_in_status()
        +test_needs_regeneration_source_hash_changed()
        +test_needs_regeneration_no_changes()
        +test_needs_regeneration_source_files_changed()
        +test_record_page_status()
    }
    class TestWikiPageStatus {
        +test_create_page_status()
        +test_page_status_multiple_sources()
    }
    class TestWikiStatusPersistence {
        +test_save_and_load_wiki_status()
        +test_load_missing_status()
        +test_load_corrupted_status()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[TestLoadExistingPage.test_l...]
    N2[TestLoadExistingPage.test_l...]
    N3[TestLoadExistingPage.test_l...]
    N4[TestWikiGenerationStatus.te...]
    N5[TestWikiGenerationStatus.te...]
    N6[TestWikiGeneratorHelpers.mo...]
    N7[TestWikiGeneratorHelpers.te...]
    N8[TestWikiGeneratorHelpers.te...]
    N9[TestWikiGeneratorHelpers.te...]
    N10[TestWikiGeneratorHelpers.te...]
    N11[TestWikiGeneratorHelpers.te...]
    N12[TestWikiGeneratorHelpers.te...]
    N13[TestWikiGeneratorHelpers.te...]
    N14[TestWikiPageStatus.test_cre...]
    N15[TestWikiPageStatus.test_pag...]
    N16[TestWikiStatusPersistence.t...]
    N17[TestWikiStatusPersistence.t...]
    N18[TestWikiStatusPersistence.t...]
    N19[WikiGenerationStatus]
    N20[WikiPage]
    N21[WikiPageStatus]
    N22[__new__]
    N23[_compute_content_hash]
    N24[_load_existing_page]
    N25[_load_wiki_status]
    N26[_needs_regeneration]
    N27[object]
    N28[time]
    N29[write_text]
    N14 --> N21
    N14 --> N28
    N15 --> N21
    N15 --> N28
    N4 --> N19
    N4 --> N28
    N5 --> N21
    N5 --> N28
    N5 --> N19
    N6 --> N27
    N6 --> N22
    N6 --> N0
    N7 --> N23
    N9 --> N26
    N10 --> N19
    N10 --> N28
    N10 --> N26
    N12 --> N19
    N12 --> N28
    N12 --> N21
    N12 --> N26
    N8 --> N19
    N8 --> N28
    N8 --> N21
    N8 --> N26
    N11 --> N19
    N11 --> N28
    N11 --> N21
    N11 --> N26
    N13 --> N20
    N13 --> N28
    N18 --> N27
    N18 --> N22
    N18 --> N21
    N18 --> N28
    N18 --> N19
    N18 --> N25
    N17 --> N27
    N17 --> N22
    N17 --> N25
    N16 --> N27
    N16 --> N22
    N16 --> N29
    N16 --> N25
    N1 --> N27
    N1 --> N22
    N1 --> N29
    N1 --> N24
    N2 --> N27
    N2 --> N22
    N2 --> N24
    N3 --> N27
    N3 --> N22
    N3 --> N19
    N3 --> N28
    N3 --> N21
    N3 --> N29
    N3 --> N24
    classDef func fill:#e1f5fe
    class N0,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18 method
```

## Relevant Source Files

- `tests/test_incremental_wiki.py:20-47`

## See Also

- [test_indexer](test_indexer.md) - shares 5 dependencies
- [server](../src/local_deepwiki/server.md) - shares 4 dependencies
