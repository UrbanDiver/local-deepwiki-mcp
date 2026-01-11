# Tests Module Documentation

## Module Purpose and Responsibilities

The tests module contains all unit and integration tests for the local_deepwiki package. It ensures that core functionality works correctly and helps maintain code quality by validating behavior across different components like parsing, chunking, cross-linking, configuration, and web application features.

## Key Classes and Functions

### TestCodeParser
The TestCodeParser class tests the CodeParser class which handles parsing code files and detecting programming languages. It verifies that the parser correctly identifies Python files and extracts language information from file paths.

### TestNodeHelpers
The TestNodeHelpers class tests helper functions for working with parsed code nodes. It ensures that text can be correctly extracted from parsed code nodes and that node names are properly retrieved.

### TestEntityRegistry
The TestEntityRegistry class tests the entity registration functionality, which manages how code entities (functions, classes, etc.) are registered and looked up for cross-linking. It includes tests for registering entities with aliases, skipping short/private/excluded names, and handling camelCase aliases.

### TestCrossLinker
The TestCrossLinker class tests the cross-linking functionality that adds links between related entities in documentation. It ensures proper linking behavior in prose, code blocks, and various naming scenarios, including qualified names, bold text, and existing links.

### TestRelationshipAnalyzer
The TestRelationshipAnalyzer class tests the relationship analysis functionality that determines how files relate to each other in the documentation. It ensures that relationships between files are correctly identified and analyzed.

### TestBuildFileToWikiMap
The TestBuildFileToWikiMap class tests the functionality that maps file paths to wiki pages, which is essential for organizing documentation content.

### TestGenerateSeeAlsoSection
The TestGenerateSeeAlsoSection class tests the generation of "See Also" sections that link to related documentation.

### TestConfig
The TestConfig class tests the configuration system, ensuring that default values are correctly set and that configuration can be properly loaded and modified.

### TestCodeChunker
The TestCodeChunker class tests the code chunking functionality that splits code files into manageable chunks for processing and embedding. It verifies chunking behavior for different languages, line number handling, and unique ID generation.

### TestBuildBreadcrumb
The TestBuildBreadcrumb class tests the breadcrumb navigation building functionality in the web application.

### TestFlaskApp
The TestFlaskApp class tests the Flask web application setup and behavior.

## How Components Interact

The test suite exercises components in isolation and in combination. For example:

1. The CodeParser and CodeChunker work together in the parsing pipeline
2. The EntityRegistry and CrossLinker collaborate to create meaningful links between related code entities
3. Configuration tests ensure that all components receive correct settings
4. The web application tests validate that the UI components work correctly with the backend processing

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
- `local_deepwiki.core.parser` - for CodeParser functionality
- `local_deepwiki.models` - for Language and other data models
- `local_deepwiki.config` - for configuration testing
- `local_deepwiki.web.app` - for web application testing
- `local_deepwiki.generators.see_also` - for see also section generation
- `pytest` - for testing framework
- `tempfile` and `pathlib` - for file system operations
- `local_deepwiki.chunker` - for chunking functionality
- `local_deepwiki.crosslinks` - for cross-linking functionality

The tests module serves as the quality assurance layer for the entire local_deepwiki package, ensuring that each component functions correctly and as expected.