# Tests Module

## Module Purpose

The tests module provides comprehensive test coverage for the local_deepwiki project. It contains unit tests for various components including parsers, configuration, manifest generation, documentation generators, and utility functions. The tests ensure the reliability and correctness of the wiki generation system.

## Key Classes and Functions

### TestCodeParser

The [TestCodeParser](../files/tests/test_parser.md) class tests the CodeParser functionality, specifically focusing on language detection capabilities. It includes setup methods and tests for detecting Python file types based on file extensions.

### TestPathToModule

The TestPathToModule class tests the `_path_to_module` function, which converts file paths to module names. It verifies basic path conversion and ensures that `__init__.py` files are properly handled by returning None.

### TestAddSourceRefsSections

The TestAddSourceRefsSections class tests functionality for adding source reference sections to documentation pages. It includes tests for adding sections to different page types, handling missing status information, and proper insertion placement.

### TestGetFileExamples

The TestGetFileExamples class tests the file examples extraction system. It verifies that examples are returned in markdown format, handles cases where test files don't exist, filters out short test names, and manages non-Python files appropriately.

### TestProjectManifest

The [TestProjectManifest](../files/tests/test_manifest.md) class tests the project manifest generation system, which appears to handle project metadata and dependency information.

### TestConfig

The [TestConfig](../files/tests/test_config.md) class provides comprehensive testing for the configuration system. It includes tests for various configuration sections including embedding, LLM, parsing, chunking, wiki, and deep research configurations. It also tests configuration validation and path resolution methods.

## How Components Interact

The test classes work together to ensure the entire documentation generation pipeline functions correctly:

1. **Configuration Testing**: [TestConfig](../files/tests/test_config.md) validates that all configuration options work properly and that the system can resolve paths and provider-specific settings
2. **Parser Testing**: [TestCodeParser](../files/tests/test_parser.md) ensures that source code can be properly analyzed and categorized by language
3. **Content Generation**: TestAddSourceRefsSections and TestGetFileExamples verify that documentation content is properly generated and formatted
4. **Project Analysis**: [TestProjectManifest](../files/tests/test_manifest.md) ensures that project structure and dependencies are correctly identified

## Usage Examples

### Running Parser Tests

```python
# Test language detection
parser = CodeParser()
result = parser.detect_language(Path("test.py"))
assert result == Language.PYTHON
```

### Testing Configuration

```python
# Test default configuration
config = Config()
assert config.llm.provider == "ollama"

# Test prompt retrieval
prompts = config.get_prompts()
assert prompts == config.prompts.ollama
```

### Testing File Examples

```python
# Test example extraction
examples = get_file_examples("path/to/file.py")
# Verify markdown format and content filtering
```

## Dependencies

Based on the imports shown in the code context, the tests module depends on:

- **Standard Library**: `json`, `tempfile`, `time`, `pathlib.Path`, `textwrap.dedent`
- **Testing Framework**: `pytest`
- **Local Modules**:
  - `local_deepwiki.generators.manifest` - For manifest generation functionality
  - `local_deepwiki.generators.test_examples` - For test example extraction
  - Various parser and configuration modules from the [main](../files/src/local_deepwiki/web/app.md) codebase

The tests use pytest as the testing framework and include both unit tests and integration tests to ensure comprehensive coverage of the documentation generation system.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`tests/test_parser.py:24-123`](../files/tests/test_parser.md)
- [`tests/test_retry.py:8-144`](../files/tests/test_retry.md)
- `tests/test_ollama_health.py:16-19`
- `tests/test_server_handlers.py:15-69`
- `tests/test_chunker.py:11-182`
- `tests/test_changelog.py:18-96`
- [`tests/test_vectorstore.py:9-28`](../files/tests/test_vectorstore.md)
- [`tests/test_pdf_export.py:21-80`](../files/tests/test_pdf_export.md)
- `tests/test_search.py:20-53`
- `tests/test_toc.py:17-43`


*Showing 10 of 31 source files.*
