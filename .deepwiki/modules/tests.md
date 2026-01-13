# Tests Module

## Module Purpose

The tests module contains the test suite for the local_deepwiki project, providing comprehensive unit and integration tests for various components including parsers, generators, web interfaces, and external service integrations.

## Key Classes and Functions

### Parser Testing

**[TestCodeParser](../files/tests/test_parser.md)**
Tests the [CodeParser](../files/src/local_deepwiki/core/parser.md) functionality, including language detection capabilities. The test suite verifies that the parser can correctly identify Python files by their extensions.

**TestPathToModule**
Tests the `_path_to_module` function which converts file paths to module names. Includes tests for basic path conversion and handling of special files like `__init__.py`.

### Generator Testing

**[TestProjectManifest](../files/tests/test_manifest.md)**
Tests manifest generation functionality for project metadata extraction.

**TestAddSourceRefsSections**
Tests the addition of source reference sections to generated documentation pages. Verifies proper handling of different page types including file pages, index pages, and module pages.

### Web Interface Testing

**TestBuildBreadcrumb**
Tests breadcrumb navigation generation for the web interface.

**TestFlaskApp**
Tests Flask application functionality and routing.

**TestTemplateConfiguration**
Tests template configuration for the web interface.

### Server Handler Testing

**TestHandleIndexRepository**
Tests repository indexing functionality.

**TestHandleAskQuestion**
Tests question handling capabilities.

**TestHandleSearchCode**
Tests code search functionality.

**TestHandleReadWikiStructure**
Tests wiki structure reading operations.

**TestHandleReadWikiPage**
Tests individual wiki page reading operations.

**TestHandleExportWikiHtml**
Tests HTML export functionality.

### External Service Testing

**TestOllamaConnectionError**
Tests error handling for Ollama connection issues.

**TestOllamaModelNotFoundError**
Tests error handling when Ollama models are not found.

**TestOllamaProviderHealthCheck**
Tests health checking for the Ollama service provider.

**TestOllamaProviderGenerate**
Tests text generation via the Ollama provider.

**TestOllamaProviderGenerateStream**
Tests streaming text generation via the Ollama provider.

### Cross-linking and Analysis Testing

**[TestEntityRegistry](../files/tests/test_crosslinks.md)**
Tests entity registration and lookup functionality for cross-linking between documentation pages. Includes tests for entity registration, name filtering, and alias lookup.

**TestExtractCallsPython**
Tests call graph extraction from Python code, including function calls, method calls, and nested call detection.

## How Components Interact

The test classes work together to provide comprehensive coverage of the application's functionality:

1. **Parser tests** verify that code analysis components correctly process source files
2. **Generator tests** ensure that documentation generation works properly
3. **Web interface tests** validate the user-facing components
4. **Server handler tests** verify API endpoints and request processing
5. **External service tests** ensure proper integration with services like Ollama

## Usage Examples

### Running Parser Tests

```python
# Test language detection
parser = CodeParser()
result = parser.detect_language(Path("test.py"))
assert result == Language.PYTHON
```

### Testing WikiPage Model

```python
# Test WikiPage representation
page = WikiPage(
    path="modules/core.md",
    title="Core Module", 
    content="# Core Module\n\nContent here.",
    generated_at=1234567890.0,
)
result = repr(page)
assert "WikiPage" in result
```

### Testing Web Interface

```python
# Test breadcrumb generation
breadcrumb = build_breadcrumb("/modules/core/parser")
# Verify breadcrumb structure
```

## Dependencies

Based on the imports shown, the tests module depends on:

- **Standard library**: `json`, `tempfile`, `time`, `pathlib.Path`
- **Testing framework**: `pytest`
- **Mocking**: `unittest.mock` (AsyncMock, patch, MagicMock)
- **Application modules**:
  - `local_deepwiki.generators.manifest`
  - `local_deepwiki.providers.llm.ollama`
  - `local_deepwiki.web.app`
  - `local_deepwiki.server`

The test suite uses pytest as the primary testing framework with extensive use of mocking for external dependencies and asynchronous operations.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`tests/test_parser.py:24-123`](../files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](../files/tests/test_retry.md)
- `tests/test_ollama_health.py:13-32`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- [`tests/test_vectorstore.py:9-28`](../files/tests/test_vectorstore.md)
- [`tests/test_pdf_export.py:21-80`](../files/tests/test_pdf_export.md)
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`
- `tests/test_incremental_wiki.py:20-47`


*Showing 10 of 26 source files.*
