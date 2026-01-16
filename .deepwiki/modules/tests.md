# Tests Module

## Module Purpose

The tests module contains comprehensive test suites for various components of the local_deepwiki system. The tests cover core functionality including wiki generation, parsing, provider factories, diagram generation, source references, test examples extraction, and more.

## Key Classes and Functions

### TestGenerateModuleDocs

This test class focuses on testing module documentation generation functionality. It includes several test methods that verify different aspects of the module documentation process:

- **mock_llm**: Creates a mock LLM provider for testing purposes
- **test_generates_multiple_modules**: Tests the generation of documentation pages for multiple modules
- **test_generates_modules_index**: Tests the creation of a modules index page

### TestProviderExports

This test class verifies that the provider modules export the expected components correctly. It ensures that the LLM module exports required names like `get_llm_provider`, `get_cached_llm_provider`, [`LLMProvider`](../files/src/local_deepwiki/providers/base.md), and `OllamaConnect`.

### TestPathToModule

This test class validates path-to-module conversion functionality:

- **test_converts_simple_path**: Tests basic path conversion from file paths to module names
- **test_skips_init_files**: Verifies that `__init__.py` files return None during conversion

### TestCodeParser

This test class provides comprehensive testing for the [CodeParser](../files/src/local_deepwiki/core/parser.md) component:

- **setup_method**: Sets up test fixtures with a [CodeParser](../files/src/local_deepwiki/core/parser.md) instance
- **test_detect_language_python**: Tests Python language detection for `.py` and `.pyi` files

### TestAddSourceRefsSections

This test class validates the addition of source reference sections to wiki pages, including handling of different page types and proper insertion logic.

### TestGetFileExamples

This test class focuses on testing file example extraction functionality, including markdown generation, handling of missing test files, and filtering logic.

## How Components Interact

The test classes work together to provide comprehensive coverage of the local_deepwiki system:

1. **Mock Infrastructure**: The TestGenerateModuleDocs class creates mock objects for LLM providers, vector stores, and status managers to isolate testing
2. **Integration Testing**: Tests verify that components like parsers, generators, and providers work correctly with each other
3. **Data Flow Testing**: Tests ensure proper handling of code chunks, search results, and wiki pages throughout the system

## Usage Examples

### Running Module Documentation Tests

```python
# Test mock LLM creation
mock = TestGenerateModuleDocs().mock_llm()
result = await mock.generate("test query")
assert result == "## Module Purpose\n\nTest module."
```

### Testing Language Detection

```python
parser = CodeParser()
language = parser.detect_language(Path("test.py"))
assert language == Language.PYTHON
```

### Testing Provider Exports

```python
from local_deepwiki.providers import llm

# Verify expected exports are available
assert hasattr(llm, "get_llm_provider")
assert hasattr(llm, "LLMProvider")
```

## Dependencies

Based on the imports shown, the tests module depends on:

- **unittest.mock**: For creating AsyncMock and MagicMock objects
- **pytest**: Testing framework
- **time**: For timing-related functionality
- **local_deepwiki.generators.wiki_modules**: For module documentation generation functions
- **local_deepwiki.models**: For data models like [ChunkType](../files/src/local_deepwiki/models.md), [CodeChunk](../files/src/local_deepwiki/models.md), [FileInfo](../files/src/local_deepwiki/models.md), [IndexStatus](../files/src/local_deepwiki/models.md), [Language](../files/src/local_deepwiki/models.md), [SearchResult](../files/src/local_deepwiki/models.md), and [WikiPage](../files/src/local_deepwiki/models.md)
- **local_deepwiki.providers**: For LLM provider functionality

The tests are designed to validate the core functionality while maintaining isolation through mocking and fixture setup.

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


*Showing 10 of 46 source files.*
