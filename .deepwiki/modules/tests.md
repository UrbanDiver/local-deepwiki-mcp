# Tests Module

## Module Purpose

The tests module contains comprehensive test suites for validating the functionality of the local_deepwiki project. It includes unit tests for core components like parsing, configuration, manifest generation, diagram creation, source references, and test example extraction.

## Key Classes and Functions

### TestCodeParser
Test suite for the [CodeParser](../files/src/local_deepwiki/core/parser.md) functionality, focusing on language detection capabilities. The setup_method initializes a [CodeParser](../files/src/local_deepwiki/core/parser.md) instance for testing, and test_detect_language_python verifies that Python files (.py and .pyi extensions) are correctly identified.

### TestConfig
Comprehensive test suite for configuration management. This class validates various configuration aspects including default settings, embedding configuration, LLM configuration, parsing settings, chunking parameters, wiki configuration, and deep research settings. It also tests path generation methods and global configuration handling.

### TestProjectManifest
Test suite for project manifest functionality, working with components like [ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md), [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md), and various manifest parsing functions. This class tests manifest caching, directory tree generation, and parsing of different project file formats.

### TestPathToModule
Tests the _path_to_module function which converts file paths to module names. The test_converts_simple_path method verifies basic path conversion functionality, while test_skips_init_files ensures that __init__.py files are properly handled by returning None.

### TestModuleToWikiPath
Tests the _module_to_wiki_path function for converting module names to wiki page paths. Includes test_simple_module for basic conversions and test_nested_module for handling nested module structures.

### TestAddSourceRefsSections
Test suite for adding source reference sections to wiki pages. This class includes methods for testing section addition to different page types, handling of index pages, insertion placement, and missing status scenarios.

### TestFindTestFile, TestExtractExamplesForEntities, TestFormatExamplesMarkdown, TestGetFileExamples
Test suites for the test examples functionality. These classes validate finding test files, extracting usage examples, formatting examples as markdown, and retrieving file-specific examples with proper filtering.

## How Components Interact

The test module components work together to validate the entire local_deepwiki system:

1. **Configuration Testing**: TestConfig ensures that all configuration aspects work correctly, providing the foundation for other components
2. **Parsing Validation**: TestCodeParser verifies that code parsing works correctly for different file types
3. **Manifest Testing**: TestProjectManifest validates project structure analysis and caching mechanisms
4. **Documentation Generation**: TestPathToModule and TestModuleToWikiPath test the conversion between code structure and documentation paths
5. **Content Enhancement**: TestAddSourceRefsSections and the test examples classes ensure that generated documentation includes proper references and usage examples

## Usage Examples

### Running Parser Tests
```python
# Test language detection
parser = CodeParser()
assert parser.detect_language(Path("test.py")) == Language.PYTHON
```

### Testing Configuration
```python
# Test default configuration
config = Config()
assert config.llm.provider == "ollama"
prompts = config.get_prompts()
assert prompts == config.prompts.ollama
```

### Testing Path Conversions
```python
# Test module path conversion
result = _path_to_module("src/mypackage/core/parser.py")
assert result is not None
assert "parser" in result

# Test wiki path generation
result = _module_to_wiki_path("core.parser", "local_deepwiki")
assert result == "src/local_deepwiki/core/parser.md"
```

## Dependencies

Based on the imports shown, the tests module depends on:

- **Standard Library**: `json`, `tempfile`, `time`, `pathlib.Path`, `textwrap.dedent`
- **Testing Framework**: `pytest`
- **Internal Modules**:
  - `local_deepwiki.generators.manifest` ([ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md), [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md), parsing functions)
  - `local_deepwiki.generators.test_examples` ([UsageExample](../files/src/local_deepwiki/generators/test_examples.md), extraction and formatting functions)
  - Core parsing and configuration components ([CodeParser](../files/src/local_deepwiki/core/parser.md), [Config](../files/src/local_deepwiki/config.md), [Language](../files/src/local_deepwiki/models.md), [WikiPage](../files/src/local_deepwiki/models.md))

The test suite provides comprehensive coverage for the project's core functionality, ensuring reliability and correctness of the documentation generation system.

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_parser.py:24-123`
- `tests/test_retry.py:8-144`
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- `tests/test_changelog.py:18-96`
- `tests/test_vectorstore.py:9-28`
- `tests/test_pdf_export.py:21-80`
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`


*Showing 10 of 31 source files.*
