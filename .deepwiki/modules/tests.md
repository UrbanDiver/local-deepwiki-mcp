# Module: test_wiki_modules_coverage

## Module Purpose

This module contains tests for the wiki module documentation generation functionality. It verifies that modules are correctly identified, grouped by directory, and that documentation pages are generated for them. The tests cover scenarios like handling unchanged pages, rebuilding caches, and filtering chunks by directory.

## Key Classes and Functions

### Class: TestGenerateModuleDocs

This class contains tests for the module documentation generation logic.

**Methods:**

- `mock_llm`: Creates a mock LLM provider.
- `test_returns_empty_for_no_files`: Tests that an empty result is returned when no files are provided.
- `test_skips_single_file_directories`: Tests that directories with only one file are skipped.
- `test_groups_files_by_directory`: Tests that files are grouped by directory.
- `test_handles_root_level_files`: Tests handling of root-level files.
- `test_generates_modules_index`: Tests that a modules index page is generated.
- `test_skips_unchanged_pages`: Tests that unchanged pages are skipped.
- `test_full_rebuild_ignores_cache`: Tests that a full rebuild ignores the cache.
- `test_filters_chunks_by_directory`: Tests filtering of chunks by directory.
- `test_skips_directories_without_relevant_chunks`: Tests that directories without relevant chunks are skipped.
- `test_generates_multiple_modules`: Tests generation of documentation for multiple modules.

### Function: mock_llm

```python
def mock_llm(self):
    """Create a mock LLM provider."""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value="## Module Purpose\n\nTest module.")
    return mock
```

Creates a mock LLM provider with a predefined response for testing purposes.

## How Components Interact

The test suite uses mock objects for the LLM provider, vector store, and status manager to simulate real-world interactions without external dependencies. The tests verify that:

1. Files are correctly grouped by directory
2. Modules are generated with proper documentation
3. Caching behavior is handled correctly (skipping unchanged pages, full rebuilds)
4. Filtering logic works for chunks and directories
5. Index pages are generated for modules

The `TestGenerateModuleDocs` class methods test various aspects of module documentation generation using these mocks.

## Usage Examples

```python
# Example of using the mock LLM in a test
def test_example(self):
    mock_llm = self.mock_llm()
    result = mock_llm.generate()
    assert result == "## Module Purpose\n\nTest module."
```

```python
# Example of testing module generation
async def test_generates_multiple_modules(
    self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
):
    src_chunk = make_code_chunk(file_path="src/main.py", name="main")
    tests_chunk = make_code_chunk(file_path="tests/test_main.py", name="test_main")
    # ... test logic ...
```

## Dependencies

This module depends on:

- `local_deepwiki.generators.wiki_modules` - Contains the actual implementation being tested
- `local_deepwiki.models` - Provides data models like [`ChunkType`](../files/src/local_deepwiki/models.md), [`CodeChunk`](../files/src/local_deepwiki/models.md), [`FileInfo`](../files/src/local_deepwiki/models.md), [`IndexStatus`](../files/src/local_deepwiki/models.md), [`Language`](../files/src/local_deepwiki/models.md), [`SearchResult`](../files/src/local_deepwiki/models.md), [`WikiPage`](../files/src/local_deepwiki/models.md)
- `unittest.mock` - For creating mock objects
- `pytest` - Testing framework
- `asyncio` - For async testing
- `time` - For time-related operations

The module also imports `make_code_chunk`, `make_search_result`, and `make_index_status` helper functions, which are likely defined elsewhere in the test suite.

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_provider_factories.py:21-99`
- `tests/test_parser.py:24-123`
- `tests/test_retry.py:8-144`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-75`
- `tests/test_chunker.py:13-428`
- `tests/test_changelog.py:18-96`
- `tests/test_coverage.py:13-50`
- `tests/test_vectorstore.py:9-28`
- `tests/test_wiki_coverage.py:50-120`


*Showing 10 of 48 source files.*
