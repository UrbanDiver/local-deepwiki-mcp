# Tests Module

## Module Purpose

The tests module provides comprehensive test coverage for the local_deepwiki application. It contains unit tests for various components including wiki generation, parsing, provider factories, diagrams, source references, and test examples functionality.

## Key Classes and Functions

### TestGenerateModuleDocs

The TestGenerateModuleDocs class tests the module documentation generation functionality. It includes methods for testing various scenarios of module documentation creation.

**Key Methods:**
- `mock_llm` - Creates a mock LLM provider for testing with predefined responses
- `test_generates_multiple_modules` - Tests generation of documentation pages for multiple modules
- `test_generates_modules_index` - Tests creation of the modules index page

### TestProviderExports

The TestProviderExports class validates that provider modules export the expected components.

**Key Methods:**
- `test_llm_module_exports` - Verifies that the LLM module exports required names like `get_llm_provider`, `get_cached_llm_provider`, [`LLMProvider`](../files/src/local_deepwiki/providers/base.md), and `OllamaConnect`

### TestPathToModule

The TestPathToModule class tests path-to-module conversion functionality for diagram generation.

**Key Methods:**
- `test_converts_simple_path` - Tests basic file path to module name conversion
- `test_skips_init_files` - Verifies that `__init__.py` files are properly handled

### TestAddSourceRefsSections

The TestAddSourceRefsSections class tests the functionality for adding source reference sections to wiki pages.

**Key Methods:**
- `test_adds_sections_to_file_pages` - Tests adding source references to file-based pages
- `test_skips_index_pages` - Verifies that index pages are skipped appropriately
- `test_inserts_before_see_also` - Tests proper insertion order of source reference sections

### TestGetFileExamples

The TestGetFileExamples class tests the extraction of test examples from test files.

**Key Methods:**
- `test_get_file_examples_returns_markdown` - Tests that file examples are returned in markdown format
- `test_get_file_examples_no_test_file` - Tests behavior when no test file exists
- `test_get_file_examples_filters_short_names` - Tests filtering of short test names

### TestCodeParser

The TestCodeParser class provides comprehensive testing for code parsing functionality.

**Key Methods:**
- `setup_method` - Initializes the [CodeParser](../files/src/local_deepwiki/core/parser.md) instance for testing
- `test_detect_language_python` - Tests Python language detection for `.py` and `.pyi` files

## How Components Interact

The test classes work together to provide comprehensive coverage of the application:

1. **Mock Setup**: Test classes use mock objects (like `mock_llm`, `mock_vector_store`, `mock_status_manager`) to isolate components during testing
2. **Async Testing**: Many tests use `AsyncMock` and async/await patterns to test asynchronous functionality
3. **Data Generation**: Helper functions like `make_code_chunk` and `make_search_result` create test data
4. **Integration Testing**: Tests verify that components work together correctly, such as wiki generation using LLM providers and vector stores

## Usage Examples

### Running Module Documentation Tests

```python
# Test module documentation generation
async def test_generates_multiple_modules(
    self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
):
    """Test generates pages for multiple modules."""
    src_chunk = make_code_chunk(file_path="src/main.py", name="main")
    tests_chunk = make_code_chunk(file_path="tests/test_main.py", name="test_main")
    
    async def search_side_effect(query, **_kwargs):
        # Test implementation
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

### Testing Code Parser

```python
def test_detect_language_python(self):
    """Test Python language detection."""
    assert self.parser.detect_language(Path("test.py")) == Language.PYTHON
```

## Dependencies

Based on the imports shown, this module depends on:

- `time` - Standard library for time-related functionality
- `unittest.mock` - Provides `AsyncMock` and `MagicMock` for testing
- `pytest` - Testing framework
- `local_deepwiki.generators.wiki_modules` - Wiki generation functionality
- `local_deepwiki.models` - Data models including [`ChunkType`](../files/src/local_deepwiki/models.md), [`CodeChunk`](../files/src/local_deepwiki/models.md), [`FileInfo`](../files/src/local_deepwiki/models.md), [`IndexStatus`](../files/src/local_deepwiki/models.md), [`Language`](../files/src/local_deepwiki/models.md), [`SearchResult`](../files/src/local_deepwiki/models.md), and [`WikiPage`](../files/src/local_deepwiki/models.md)
- `local_deepwiki.providers` - Provider modules for LLM functionality
- `pathlib.Path` - For file path handling

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
