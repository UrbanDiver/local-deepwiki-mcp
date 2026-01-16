# Tests Module

## Module Purpose

The tests module provides comprehensive test coverage for the local_deepwiki application. It contains unit tests for various components including wiki generation, code parsing, provider factories, and documentation coverage functionality.

## Key Classes and Functions

### TestGenerateModuleDocs

A test class that validates the module documentation generation functionality. Contains methods for testing various scenarios of module documentation creation:

- **mock_llm**: Creates a mock LLM provider that returns standardized test responses
- **test_generates_multiple_modules**: Tests the generation of documentation for multiple modules
- **test_generates_modules_index**: Validates creation of the modules index page
- Various other test methods for edge cases like empty files, single file directories, and caching behavior

### TestProviderExports

Tests module exports for provider functionality, specifically validating that the LLM module exports expected names and interfaces.

### TestPathToModule

Tests path-to-module conversion functionality, including:
- **test_converts_simple_path**: Validates basic path conversion logic
- **test_skips_init_files**: Ensures `__init__.py` files are properly handled

### TestAddSourceRefsSections

Tests the addition of source reference sections to documentation pages, with methods for handling different page types and insertion logic.

### TestGetFileExamples

Tests file example extraction functionality, including validation of markdown generation and filtering logic.

### TestCodeParser

Test suite for the [CodeParser](../files/src/local_deepwiki/core/parser.md) component, including:
- **setup_method**: Initializes test fixtures
- **test_detect_language_python**: Tests Python language detection

## How Components Interact

The test classes work together to validate the complete documentation generation pipeline:

1. **Mock Setup**: Test classes like TestGenerateModuleDocs use mock objects for LLM providers and vector stores to isolate functionality
2. **Integration Testing**: Tests validate how components like code parsing, wiki generation, and provider factories work together
3. **Coverage Validation**: Multiple test classes ensure comprehensive coverage of the documentation generation process

## Usage Examples

```python
# Example test setup pattern used across test classes
@pytest.fixture
def mock_llm(self):
    """Create a mock LLM provider."""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value="## Module Purpose\n\nTest module.")
    return mock

# Example async test pattern
async def test_generates_modules_index(
    self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
):
    """Test generates modules index page."""
    chunk = make_code_chunk(file_path="src/main.py", name="main")
    mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
    # Test implementation continues...
```

## Dependencies

Based on the imports shown, the tests module depends on:

- **pytest**: Testing framework
- **unittest.mock**: For creating AsyncMock and MagicMock objects
- **time**: For timing-related test functionality
- **local_deepwiki.generators.wiki_modules**: Module documentation generation functions
- **local_deepwiki.models**: Core data models including [ChunkType](../files/src/local_deepwiki/models.md), [CodeChunk](../files/src/local_deepwiki/models.md), [FileInfo](../files/src/local_deepwiki/models.md), [IndexStatus](../files/src/local_deepwiki/models.md), [Language](../files/src/local_deepwiki/models.md), [SearchResult](../files/src/local_deepwiki/models.md), and [WikiPage](../files/src/local_deepwiki/models.md)
- **local_deepwiki.providers**: Provider interfaces and implementations

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


*Showing 10 of 45 source files.*
