# Tests Module

## Module Purpose

The tests module contains comprehensive test suites for validating the functionality of the local_deepwiki application. The tests cover various components including wiki generation, code parsing, provider factories, diagrams, source references, and test examples functionality.

## Key Classes and Functions

### TestGenerateModuleDocs

A test class that validates the module documentation generation functionality. This class includes multiple test methods for different scenarios:

- Tests empty file handling
- Validates directory grouping behavior  
- Tests root-level file processing
- Validates module index generation
- Tests caching and rebuild functionality
- Tests chunk filtering by directory

The class uses mock objects for LLM providers, vector stores, and status managers to isolate the functionality being tested.

### TestProviderExports

A test class that validates the proper export of provider-related functionality from the LLM module. It verifies that expected names like `get_llm_provider`, `get_cached_llm_provider`, [`LLMProvider`](../files/src/local_deepwiki/providers/base.md), and `OllamaConnect` are properly exported.

### TestPathToModule

A test class focused on testing path-to-module conversion functionality. It includes tests for:

- Basic path conversion from file paths to module names
- Proper handling of `__init__.py` files (which should return None)

### TestAddSourceRefsSections

A test class that validates the addition of source reference sections to wiki pages. It tests various scenarios including:

- Adding sections to file pages
- Skipping index pages appropriately
- Proper insertion before "See Also" sections
- Handling missing status information
- Adding sections to module and architecture pages

### TestGetFileExamples

A test class that validates file example extraction functionality. It tests:

- Markdown generation from file examples
- Handling of missing test files
- Processing of non-Python files
- Filtering of short test names
- Handling cases with no matching tests

### TestCodeParser

A test class for validating code parsing functionality. It includes language detection capabilities, specifically testing Python language detection for `.py` and `.pyi` files.

## How Components Interact

The test classes work together to provide comprehensive coverage of the wiki generation system:

1. **Mock Setup**: Test classes like TestGenerateModuleDocs use mock objects (`mock_llm`, `mock_vector_store`, `mock_status_manager`) to isolate components during testing

2. **Integration Testing**: The tests validate how different components interact, such as how the module documentation generator works with vector stores and LLM providers

3. **Data Flow Validation**: Tests verify the proper flow of data through the system, from file parsing to wiki page generation

## Usage Examples

### Running Module Documentation Tests

```python
# Example of how the mock_llm fixture is used
def mock_llm(self):
    """Create a mock LLM provider."""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value="## Module Purpose\n\nTest module.")
    return mock
```

### Testing Provider Exports

```python
def test_llm_module_exports(self):
    """Test that LLM module exports expected names."""
    from local_deepwiki.providers import llm
    
    assert hasattr(llm, "get_llm_provider")
    assert hasattr(llm, "get_cached_llm_provider")
    assert hasattr(llm, "LLMProvider")
```

### Testing Path Conversion

```python
def test_converts_simple_path(self):
    """Test basic path conversion."""
    result = _path_to_module("src/mypackage/core/parser.py")
    assert result is not None
    assert "parser" in result
```

## Dependencies

Based on the imports shown in the code context, the tests module depends on:

- **Standard Library**: `time`, `unittest.mock` (AsyncMock, MagicMock)
- **Testing Framework**: `pytest`
- **Application Modules**:
  - `local_deepwiki.generators.wiki_modules` (for `_generate_modules_index`, [`generate_module_docs`](../files/src/local_deepwiki/generators/wiki_modules.md))
  - `local_deepwiki.models` (for data models like [`ChunkType`](../files/src/local_deepwiki/models.md), [`CodeChunk`](../files/src/local_deepwiki/models.md), [`FileInfo`](../files/src/local_deepwiki/models.md), [`IndexStatus`](../files/src/local_deepwiki/models.md), [`Language`](../files/src/local_deepwiki/models.md), [`SearchResult`](../files/src/local_deepwiki/models.md), [`WikiPage`](../files/src/local_deepwiki/models.md))
  - `local_deepwiki.providers` (for provider functionality testing)

The tests are designed to validate the core functionality of the wiki generation system while maintaining proper isolation through mocking and fixtures.

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_provider_factories.py:21-99`
- `tests/test_parser.py:24-123`
- `tests/test_retry.py:8-144`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-75`
- `tests/test_chunker.py:13-428`
- `tests/test_changelog.py:18-96`
- `tests/test_vectorstore.py:9-28`
- `tests/test_wiki_coverage.py:50-120`
- `tests/test_pdf_export.py:23-82`


*Showing 10 of 42 source files.*
