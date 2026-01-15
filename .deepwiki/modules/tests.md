# Tests Module

## Module Purpose

The tests module contains comprehensive test suites for validating the functionality of the local_deepwiki project components. It includes unit tests for various core features including parsing, configuration management, manifest handling, diagram generation, source references, and test example extraction.

## Key Classes and Functions

### Test Configuration Classes

**TestConfig**
Tests configuration management functionality including default settings, embedding configuration, LLM configuration, parsing settings, chunking parameters, and wiki configuration validation.

### Test Parser Classes

**TestCodeParser**
Test suite for the CodeParser functionality, including language detection capabilities for Python files. Contains setup methods for test fixtures and validation of language detection for `.py` and `.pyi` files.

### Test Manifest Classes

**TestProjectManifest**
Tests project manifest functionality including parsing of various configuration files like `pyproject.toml`, `package.json`, and `requirements.txt`. Validates manifest caching, directory tree generation, and cache validity checking.

### Test Diagram Classes

**TestPathToModule**
Tests the `_path_to_module` function for converting file paths to module names. Validates basic path conversion and proper handling of `__init__.py` files.

**TestModuleToWikiPath**
Tests the `_module_to_wiki_path` function for converting module names to wiki page paths. Handles both simple and nested module path conversions.

### Test Source Reference Classes

**TestAddSourceRefsSections**
Tests functionality for adding source reference sections to wiki pages. Validates section addition to file pages, module pages, and architecture pages while properly handling index pages and missing status conditions.

### Test Example Classes

**TestFindTestFile**
Tests the functionality for locating test files corresponding to source files.

**TestExtractExamplesForEntities**
Tests extraction of usage examples from test files for specific code entities.

**TestFormatExamplesMarkdown**
Tests formatting of extracted examples into markdown format.

**TestGetFileExamples**
Tests the complete workflow of getting file examples, including markdown generation, handling of non-existent test files, filtering of short test names, and validation of matching test patterns.

## How Components Interact

The test classes work together to validate the entire documentation generation pipeline:

1. **Configuration Testing**: TestConfig ensures proper configuration loading and validation
2. **Parsing Testing**: TestCodeParser validates code analysis capabilities
3. **Manifest Testing**: TestProjectManifest ensures project structure detection works correctly
4. **Path Conversion Testing**: TestPathToModule and TestModuleToWikiPath validate the conversion between file paths and wiki page paths
5. **Content Enhancement Testing**: TestAddSourceRefsSections and test example classes ensure proper enhancement of generated documentation with references and examples

## Usage Examples

### Running Configuration Tests
```python
# Test configuration management
config = Config()
assert config.llm.provider == "ollama"
prompts = config.get_prompts()
assert prompts == config.prompts.ollama
```

### Testing Code Parser
```python
# Test language detection
parser = CodeParser()
assert parser.detect_language(Path("test.py")) == Language.PYTHON
```

### Testing Path Conversion
```python
# Test module path conversion
result = _module_to_wiki_path("core.parser", "local_deepwiki")
assert result == "src/local_deepwiki/core/parser.md"
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
assert "modules/core.md" in result
```

## Dependencies

Based on the imports shown in the code context:

- **json**: For JSON data handling in manifest tests
- **tempfile**: For temporary file operations during testing
- **time**: For timestamp operations in manifest caching tests
- **pathlib.Path**: For file path operations
- **textwrap.dedent**: For formatting test strings
- **pytest**: Testing framework for test execution and fixtures

### Internal Dependencies
- **local_deepwiki.generators.manifest**: Manifest generation components
- **local_deepwiki.generators.test_examples**: Test example extraction functionality

## Relevant Source Files

The following source files were used to generate this documentation:

- [`tests/test_parser.py:24-123`](../files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](../files/tests/test_retry.md)
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- `tests/test_changelog.py:18-96`
- [`tests/test_vectorstore.py:9-28`](../files/tests/test_vectorstore.md)
- `tests/test_pdf_export.py:21-80`
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`


*Showing 10 of 31 source files.*
