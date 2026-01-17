# Tests Module

## Module Purpose

The tests module contains comprehensive test suites for the local_deepwiki application. Based on the code shown, it focuses heavily on testing wiki generation functionality, provider factories, and various utility components. The tests use pytest and unittest.mock for creating isolated test environments.

## Key Classes and Functions

### TestGenerateModuleDocs

A test class that validates the module documentation generation functionality. This class contains multiple test methods that verify different aspects of the wiki module generation process:

- **mock_llm**: Creates a mock LLM provider that returns standardized test responses
- **test_generates_multiple_modules**: Tests the generation of documentation for multiple code modules
- **test_generates_modules_index**: Validates the creation of a modules index page
- Various other test methods for handling edge cases like empty directories and cache management

### TestProviderExports  

Tests module exports for provider functionality, specifically validating that the LLM module exports expected components like `get_llm_provider`, `get_cached_llm_provider`, [`LLMProvider`](../files/src/local_deepwiki/providers/base.md), and `OllamaConnect`.

### TestPathToModule

Tests path-to-module conversion functionality:

- **test_converts_simple_path**: Validates basic file path to module name conversion
- **test_skips_init_files**: Ensures `__init__.py` files are handled appropriately

### TestAddSourceRefsSections

Tests the addition of source reference sections to wiki pages:

- Handles different page types (file pages, index pages, module pages, architecture pages)
- Manages section insertion and formatting
- Deals with missing status information

### TestGetFileExamples

Tests example extraction from test files:

- **test_get_file_examples_returns_markdown**: Validates markdown output generation
- **test_get_file_examples_no_test_file**: Handles cases where no test file exists
- **test_get_file_examples_filters_short_names**: Tests filtering logic for test names

## How Components Interact

The test classes work together to validate the complete wiki generation pipeline:

1. **Mock Creation**: Test classes like TestGenerateModuleDocs create mock objects for LLM providers, vector stores, and status managers
2. **Data Flow Testing**: Tests validate how code chunks flow through the system, from file parsing to wiki page generation
3. **Integration Validation**: Components test the interaction between different parts of the system, such as how the module generator uses vector store search results

## Usage Examples

### Creating Mock LLM Provider

```python
@pytest.fixture
def mock_llm(self):
    """Create a mock LLM provider."""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value="## Module Purpose\n\nTest module.")
    return mock
```

### Testing Module Generation

```python
async def test_generates_multiple_modules(
    self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
):
    """Test generates pages for multiple modules."""
    src_chunk = make_code_chunk(file_path="src/main.py", name="main")
    tests_chunk = make_code_chunk(file_path="tests/test_main.py", name="test_main")
    
    async def search_side_effect(query, **_kwargs):
        # Test implementation
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

Based on the imports shown in the code context:

- **pytest**: Testing framework
- **unittest.mock**: For creating AsyncMock and MagicMock objects
- **pathlib.Path**: File system path handling
- **textwrap.dedent**: Text formatting utilities
- **time**: Time-related functionality

### Internal Dependencies

- **local_deepwiki.generators.wiki_modules**: Module documentation generation
- **local_deepwiki.generators.test_examples**: Test example extraction
- **local_deepwiki.models**: Core data models ([ChunkType](../files/src/local_deepwiki/models.md), [CodeChunk](../files/src/local_deepwiki/models.md), [FileInfo](../files/src/local_deepwiki/models.md), [IndexStatus](../files/src/local_deepwiki/models.md), [Language](../files/src/local_deepwiki/models.md), [SearchResult](../files/src/local_deepwiki/models.md), [WikiPage](../files/src/local_deepwiki/models.md))
- **local_deepwiki.providers**: Provider factory functionality

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


*Showing 10 of 47 source files.*
