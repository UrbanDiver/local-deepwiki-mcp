# Module: tests

## Module Purpose

This module contains test cases for various components of the documentation generation and processing system. It includes tests for module page processing, wiki coverage, and related functionality.

## Key Classes and Functions

### TestModulePageProcessing

The `TestModulePageProcessing` class contains tests for processing module pages in the documentation system.

**Methods:**
- `setup_generator` - Sets up the generator for testing
- `test_module_pages_written` - Tests that module pages are properly written

### TestGenerateModuleDocs

The `TestGenerateModuleDocs` class contains comprehensive tests for generating module documentation.

**Methods:**
- `mock_llm` - Mocks the LLM for testing
- `mock_vector_store` - Mocks the vector store for testing
- `mock_status_manager` - Mocks the status manager for testing
- `test_returns_empty_for_no_files` - Tests that empty results are returned when no files are present
- `test_skips_single_file_directories` - Tests that single file directories are skipped
- `test_groups_files_by_directory` - Tests that files are properly grouped by directory
- `test_handles_root_level_files` - Tests handling of root level files
- `test_generates_modules_index` - Tests generation of modules index
- `test_skips_unchanged_pages` - Tests skipping of unchanged pages
- `test_full_rebuild_ignores_cache` - Tests that full rebuild ignores cache
- `test_filters_chunks_by_directory` - Tests filtering of chunks by directory
- `test_skips_directories_without_relevant_chunks` - Tests skipping of directories without relevant chunks

## How Components Interact

The test classes in this module work together to ensure proper functionality of the documentation generation system. `TestModulePageProcessing` focuses on testing the basic module page writing functionality, while `TestGenerateModuleDocs` provides comprehensive testing of the module documentation generation process including mocking of external dependencies like LLM and vector store.

## Usage Examples

```python
# Example of running tests
import unittest
from tests.test_wiki_coverage import TestModulePageProcessing
from tests.test_wiki_modules_coverage import TestGenerateModuleDocs

# Run specific test class
if __name__ == '__main__':
    unittest.main()
```

## Dependencies

This module depends on:
- Standard Python testing framework (unittest)
- Internal modules for documentation generation and processing
- Mocking utilities for external services

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_manifest.py:19-61`
- `tests/test_provider_factories.py:21-99`
- `tests/test_streaming_export.py:48-71`
- `tests/test_parser.py:28-127`
- `tests/test_fuzzy_search.py:16-48`
- `tests/test_interactive_search.py:97-203`
- `tests/test_retry.py:8-144`
- `tests/test_access_control.py:90-132`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-77`


*Showing 10 of 83 source files.*
