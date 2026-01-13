# Tests Module Documentation

## Module Purpose

The tests module contains unit tests for various components of the local_deepwiki system. It includes tests for code parsing, manifest handling, model representations, cross-linking, call graphs, Ollama health checks, web application functionality, and server handlers. The tests ensure the correct behavior of core functionalities such as language detection, file processing, and API interactions.

## Key Classes and Functions

### TestCodeParser
The [TestCodeParser](../files/tests/test_parser.md) class contains tests for the [CodeParser](../files/src/local_deepwiki/core/parser.md) class, which is responsible for parsing code files and detecting programming languages.

Methods:
- `test_detect_language_python`: Tests Python language detection for files with .py and .pyi extensions

### TestProjectManifest
The [TestProjectManifest](../files/tests/test_manifest.md) class tests the [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) class, which handles project manifest data including caching and parsing of various manifest files.

Methods:
- `test_get_manifest_mtimes`: Tests getting modification times of manifest files
- `test_is_cache_valid`: Tests cache validity checking
- `test_get_cached_manifest`: Tests retrieving cached manifests
- `test_get_directory_tree`: Tests directory tree generation
- `test_parse_manifest`: Tests manifest parsing functionality

### TestAddSourceRefsSections
The TestAddSourceRefsSections class tests functionality for adding source references sections to wiki pages.

Methods:
- `test_adds_sections_to_file_pages`: Tests adding sections to file pages
- `test_skips_index_pages`: Tests skipping index pages
- `test_inserts_before_see_also`: Tests inserting sections before "See Also" sections
- `test_handles_missing_status`: Tests handling of missing status information
- `test_adds_section_to_module_pages`: Tests adding sections to module pages
- `test_adds_section_to_architecture_page`: Tests adding sections to architecture pages

### TestPathToModule
The TestPathToModule class tests the `_path_to_module` function, which converts file paths to Python module names.

Methods:
- `test_converts_simple_path`: Tests basic path conversion
- `test_skips_init_files`: Tests that __init__.py files return None

### TestEntityRegistry
The [TestEntityRegistry](../files/tests/test_crosslinks.md) class tests the [EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md) class, which manages entity registration and lookup for cross-linking.

Methods:
- `test_register_entity`: Tests entity registration
- `test_skips_short_names`: Tests skipping short names
- `test_skips_private_names`: Tests skipping private names
- `test_skips_excluded_names`: Tests skipping excluded names
- `test_register_from_chunks`: Tests registering entities from chunks
- `test_get_page_entities`: Tests getting page entities
- `test_registers_camelcase_aliases`: Tests registering camelcase aliases
- `test_alias_lookup`: Tests alias lookup functionality

### TestExtractCallsPython
The [TestExtractCallsPython](../files/tests/test_callgraph.md) class tests the Python call extraction functionality.

Methods:
- `test_simple_function_call`: Tests simple function call extraction
- `test_multiple_function_calls`: Tests multiple function calls extraction
- `test_method_call`: Tests method call extraction
- `test_nested_calls`: Tests nested calls extraction
- `test_filters_builtins`: Tests filtering of built-in calls
- `test_deduplicates_calls`: Tests deduplication of calls

### TestOllamaConnectionError
The TestOllamaConnectionError class tests the OllamaConnectionError exception handling.

### TestOllamaModelNotFoundError
The TestOllamaModelNotFoundError class tests the OllamaModelNotFoundError exception handling.

### TestOllamaProviderHealthCheck
The TestOllamaProviderHealthCheck class tests the health check functionality of the OllamaProvider.

### TestOllamaProviderGenerate
The TestOllamaProviderGenerate class tests the generate functionality of the OllamaProvider.

### TestOllamaProviderGenerateStream
The TestOllamaProviderGenerateStream class tests the stream generation functionality of the OllamaProvider.

### TestBuildBreadcrumb
The TestBuildBreadcrumb class tests the breadcrumb building functionality in the web application.

### TestFlaskApp
The TestFlaskApp class tests the Flask web application functionality.

### TestTemplateConfiguration
The TestTemplateConfiguration class tests template configuration handling in the web application.

### TestHandleIndexRepository
The TestHandleIndexRepository class tests the index repository handler.

### TestHandleAskQuestion
The TestHandleAskQuestion class tests the ask question handler.

### TestHandleSearchCode
The TestHandleSearchCode class tests the search code handler.

### TestHandleReadWikiStructure
The TestHandleReadWikiStructure class tests the read wiki structure handler.

### TestHandleReadWikiPage
The TestHandleReadWikiPage class tests the read wiki page handler.

### TestHandleExportWikiHtml
The TestHandleExportWikiHtml class tests the export wiki HTML handler.

### test_wiki_page_repr
The test_wiki_page_repr function tests the string representation of WikiPage objects.

## How Components Interact

The test components work together to provide comprehensive testing for the local_deepwiki system. The test suite covers parsing functionality, manifest handling, cross-linking systems, LLM provider health checks, web application components, and server API handlers. Each test class focuses on a specific component or functionality area, ensuring that individual parts of the system work correctly in isolation and together.

## Usage Examples

```python
# Example of testing code language detection
def test_language_detection():
    parser = CodeParser()
    assert parser.detect_language(Path("test.py")) == Language.PYTHON
```

```python
# Example of testing manifest parsing
def test_manifest_parsing():
    manifest = parse_manifest("pyproject.toml")
    assert manifest is not None
```

```python
# Example of testing web application functionality
def test_breadcrumb_building():
    breadcrumb = build_breadcrumb("modules/core.md")
    assert breadcrumb is not None
```

## Dependencies

The tests module depends on:
- `local_deepwiki.generators.manifest` - For manifest handling tests
- `local_deepwiki.providers.llm.ollama` - For Ollama provider tests
- `local_deepwiki.web.app` - For web application tests
- `local_deepwiki.server` - For server handler tests
- `local_deepwiki.generators.parser` - For parser tests
- `local_deepwiki.models.wiki` - For WikiPage tests
- `local_deepwiki.crosslinks` - For cross-linking tests
- `local_deepwiki.callgraph` - For call graph tests
- `pytest` - Testing framework
- `unittest.mock` - For mocking in tests
- `pathlib.Path` - For path handling
- `json` - For JSON handling
- `tempfile` - For temporary file handling
- `time` - For time handling

## Relevant Source Files

The following source files were used to generate this documentation:

- [`tests/test_parser.py:24-123`](../files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](../files/tests/test_retry.md)
- `tests/test_ollama_health.py:13-32`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- [`tests/test_vectorstore.py:9-28`](../files/tests/test_vectorstore.md)
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`
- [`tests/test_incremental_wiki.py:20-47`](../files/tests/test_incremental_wiki.md)
- `tests/test_web.py:40-104`


*Showing 10 of 25 source files.*
