# Tests Module

## Module Purpose

The tests module contains comprehensive test suites for validating the functionality of the local_deepwiki project components. It includes tests for core parsing, configuration, documentation generation, and various utility functions used throughout the system.

## Key Classes and Functions

### TestCodeParser

Test suite for the [CodeParser](../files/src/local_deepwiki/core/parser.md) class that validates code parsing functionality.

**Key Methods:**
- `setup_method()` - Sets up test fixtures by initializing a [CodeParser](../files/src/local_deepwiki/core/parser.md) instance
- `test_detect_language_python()` - Validates Python language detection for `.py` and `.pyi` files

### TestConfig

Comprehensive test suite for configuration management and validation.

**Key Methods:**
- `test_default_config()` - Tests default configuration settings
- `test_embedding_config()` - Validates embedding configuration
- `test_llm_config()` - Tests LLM provider configuration
- `test_parsing_config()` - Validates parsing configuration options
- `test_chunking_config()` - Tests chunking configuration
- `test_wiki_config()` - Validates wiki generation settings
- `test_deep_research_config()` - Tests deep research configuration
- `test_get_wiki_path()` - Validates wiki path generation
- `test_get_vector_db_path()` - Tests vector database path configuration
- `test_config_get_prompts_uses_current_provider()` - Ensures prompts are retrieved for the current LLM provider

### TestProjectManifest

Test suite for project manifest functionality, validating how project metadata is parsed and managed.

### TestAddSourceRefsSections

Tests for adding source reference sections to documentation pages.

**Key Methods:**
- `test_adds_sections_to_file_pages()` - Validates source reference addition to file pages
- `test_skips_index_pages()` - Ensures index pages are skipped appropriately
- `test_inserts_before_see_also()` - Tests proper insertion order relative to "See Also" sections
- `test_handles_missing_status()` - Validates handling of missing status information
- `test_adds_section_to_module_pages()` - Tests source reference addition to module pages
- `test_adds_section_to_architecture_page()` - Validates architecture page handling

### TestPathToModule

Tests for the `_path_to_module` function that converts file paths to module names.

**Key Methods:**
- `test_converts_simple_path()` - Tests basic path to module conversion
- `test_skips_init_files()` - Validates that `__init__.py` files return None

### TestModuleToWikiPath

Tests for the `_module_to_wiki_path` function that converts module names to wiki paths.

**Key Methods:**
- `test_simple_module()` - Tests simple module path conversion
- `test_nested_module()` - Validates nested module path handling

### TestFindTestFile, TestExtractExamplesForEntities, TestFormatExamplesMarkdown, TestGetFileExamples

Test suites for the test examples functionality that extracts usage examples from test files.

**Key Methods in [TestGetFileExamples](../files/tests/test_test_examples.md):**
- `test_get_file_examples_returns_markdown()` - Validates markdown generation from test examples
- `test_get_file_examples_no_test_file()` - Tests behavior when no test file exists
- `test_get_file_examples_non_python()` - Validates handling of non-Python files
- `test_get_file_examples_filters_short_names()` - Tests filtering of short test names
- `test_get_file_examples_no_matching_tests()` - Validates behavior with no matching tests

### Test Functions

- `test_wiki_page_repr()` - Tests the string representation of [WikiPage](../files/src/local_deepwiki/models.md) objects, validating that the repr includes the path, title, and class name

## How Components Interact

The test module components work together to validate the entire local_deepwiki system:

1. **Configuration Testing**: [TestConfig](../files/tests/test_config.md) ensures all configuration options work correctly and integrate properly with different providers
2. **Parser Testing**: [TestCodeParser](../files/tests/test_parser.md) validates that code parsing works across different file types and languages
3. **Documentation Generation**: Various test classes validate the wiki generation pipeline, from manifest creation to final output
4. **Path Conversion**: [TestPathToModule](../files/tests/test_diagrams.md) and [TestModuleToWikiPath](../files/tests/test_diagrams.md) ensure proper conversion between file paths, module names, and wiki paths
5. **Example Extraction**: Test example classes validate the extraction and formatting of usage examples from test files

## Usage Examples

### Running Parser Tests

```python
# Set up and test code parser
parser = CodeParser()
language = parser.detect_language(Path("test.py"))
assert language == Language.PYTHON
```

### Testing Configuration

```python
# Test configuration retrieval
config = Config()
prompts = config.get_prompts()
assert prompts == config.prompts.ollama  # Default provider
```

### Testing WikiPage Representation

```python
# Create and test WikiPage
page = WikiPage(
    path="modules/core.md",
    title="Core Module", 
    content="# Core Module\n\nContent here.",
    generated_at=1234567890.0,
)
result = repr(page)
assert "WikiPage" in result
assert "modules/core.md" in result
```

## Dependencies

Based on the imports shown, the tests module depends on:

- **Standard Library**: `json`, `tempfile`, `time`, `pathlib.Path`, `textwrap.dedent`
- **Testing Framework**: `pytest`
- **Core Modules**:
  - `local_deepwiki.generators.manifest` - For manifest generation testing
  - `local_deepwiki.generators.test_examples` - For test example extraction
  - Various other local_deepwiki modules for comprehensive testing

The test suite provides comprehensive coverage of the local_deepwiki system's core functionality, ensuring reliable operation across all major components.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`tests/test_parser.py:24-123`](../files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](../files/tests/test_retry.md)
- [`tests/test_ollama_health.py:16-19`](../files/tests/test_ollama_health.md)
- [`tests/test_server_handlers.py:15-69`](../files/tests/test_server_handlers.md)
- [`tests/test_chunker.py:11-182`](../files/tests/test_chunker.md)
- [`tests/test_changelog.py:18-96`](../files/tests/test_changelog.md)
- [`tests/test_vectorstore.py:9-28`](../files/tests/test_vectorstore.md)
- [`tests/test_pdf_export.py:21-80`](../files/tests/test_pdf_export.md)
- [`tests/test_search.py:20-53`](../files/tests/test_search.md)
- [`tests/test_toc.py:17-43`](../files/tests/test_toc.md)


*Showing 10 of 31 source files.*
