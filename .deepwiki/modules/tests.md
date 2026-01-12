# Tests Module Documentation

## Module Purpose and Responsibilities

The tests module contains comprehensive test suites for the local_deepwiki package. It ensures the correctness and reliability of core components including code parsing, chunking, search functionality, incremental wiki generation, cross-linking, and file watching capabilities.

## Key Classes and Functions

### TestCodeParser
Tests the [CodeParser](../files/src/local_deepwiki/core/parser.md) class which handles language detection and code parsing for various file types. The test suite verifies that Python files are correctly identified and processed.

### TestEntityRegistry
Tests the [EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md) class that manages entity registration and lookup for cross-linking functionality. Tests include:
- Registering entities with proper naming conventions
- Skipping short, private, and excluded names
- Registering from chunks and retrieving page entities
- Handling camelCase aliases and alias lookups

### TestCrossLinker
Tests the [CrossLinker](../files/src/local_deepwiki/generators/crosslinks.md) class responsible for creating cross-references between wiki pages. Tests cover:
- Adding links to prose text while avoiding code blocks
- Preventing self-linking and handling relative paths
- Linking backticked entities and qualified names
- Preserving existing links and handling bold text
- Managing spaced aliases and qualified names

### TestWatchedExtensions
Validates that the [RepositoryWatcher](../files/src/local_deepwiki/watcher.md) correctly identifies and watches files with specific extensions. Tests verify that Python (.py, .pyi) and JavaScript/TypeScript (.js, .ts) extensions are included in the watched extensions list.

### TestDebouncedHandler
Tests the [DebouncedHandler](../files/src/local_deepwiki/watcher.md) class which manages file system events with debouncing to prevent excessive processing. The test suite covers event handling and Python file watching behavior.

### TestRepositoryWatcher
Tests the [RepositoryWatcher](../files/src/local_deepwiki/watcher.md) class that monitors repository changes and triggers wiki regeneration when necessary.

### TestWikiGeneratorHelpers
Tests helper methods for the [WikiGenerator](../files/src/local_deepwiki/generators/wiki.md) class including:
- Content hash computation
- Regeneration logic for different scenarios (no previous status, changed sources, etc.)
- Page status recording and retrieval

### TestAPIDocExtractor
Tests the [APIDocExtractor](../files/src/local_deepwiki/generators/api_docs.md) class which extracts API documentation from source code files. The test suite verifies extraction from Python files with docstrings and type annotations.

### TestRelationshipAnalyzer
Tests the [RelationshipAnalyzer](../files/src/local_deepwiki/generators/see_also.md) class that determines relationships between files for see-also section generation.

### TestBuildFileToWikiMap
Tests the [build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md) function that creates mappings between source files and wiki pages.

### TestGenerateSeeAlsoSection
Tests the [generate_see_also_section](../files/src/local_deepwiki/generators/see_also.md) function that creates see-also sections for wiki pages.

## Component Interactions

The test module verifies how different components work together:

1. **[CodeParser](../files/src/local_deepwiki/core/parser.md)** feeds parsed code into the **[EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md)** for entity extraction
2. **[EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md)** provides data to the **[CrossLinker](../files/src/local_deepwiki/generators/crosslinks.md)** for creating cross-references
3. **[RepositoryWatcher](../files/src/local_deepwiki/watcher.md)** triggers **[WikiGenerator](../files/src/local_deepwiki/generators/wiki.md)** regeneration when files change
4. **[APIDocExtractor](../files/src/local_deepwiki/generators/api_docs.md)** works with **[WikiGenerator](../files/src/local_deepwiki/generators/wiki.md)** to include API documentation in wiki pages
5. **[RelationshipAnalyzer](../files/src/local_deepwiki/generators/see_also.md)** helps generate see-also sections that reference related files

## Usage Examples

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_parser.py

# Run specific test class
pytest tests/test_parser.py::TestCodeParser

# Run specific test method
pytest tests/test_parser.py::TestCodeParser::test_detect_language_python
```

### Example Test Structure
```python
def test_detect_language_python(self):
    """Test Python language detection."""
    assert self.parser.detect_language(Path("test.py")) == Language.PYTHON
    assert self.parser.detect_language(Path("test.pyi")) == Language.PYTHON
```

## Dependencies

This module depends on:
- `local_deepwiki.config` - Configuration management
- `local_deepwiki.parser` - Code parsing functionality
- `local_deepwiki.watcher` - File system watching capabilities
- `local_deepwiki.generators` - Wiki generation components
- `local_deepwiki.models` - Data models used throughout the system
- `pytest` - Testing framework
- `unittest.mock` - Mocking utilities for testing

The tests module ensures that all core functionality works correctly and provides confidence in the reliability of the local_deepwiki package.