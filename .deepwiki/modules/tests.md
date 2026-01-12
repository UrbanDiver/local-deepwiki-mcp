# tests Module Documentation

## Module Purpose

The tests module contains unit and integration tests for various components of the local-deepwiki project. These tests validate the functionality of code parsing, manifest handling, cross-linking, TOC generation, and other core features.

## Key Classes and Functions

### TestCodeParser
The TestCodeParser class is a test suite for the CodeParser class. It includes methods to test language detection for Python files.

### TestProjectManifest
The TestProjectManifest class tests the ProjectManifest dataclass, validating its behavior with and without data.

### TestAddSourceRefsSections
The TestAddSourceRefsSections class tests functionality related to adding source reference sections to wiki pages, including handling of index pages, See Also sections, and different page types.

### TestEntityRegistry
The TestEntityRegistry class tests the entity registry functionality, including entity registration, alias handling, and lookup behavior.

### TestCrossLinker
The TestCrossLinker class tests cross-linking functionality, covering various scenarios like linking prose, code blocks, qualified names, and preserving existing links.

### TestTocIntegration
The TestTocIntegration class provides integration tests for table of contents (TOC) generation with realistic wiki structures.

### TestWatchedExtensions
The TestWatchedExtensions class tests that watched file extensions are correctly configured for the repository watcher.

### TestDebouncedHandler
The TestDebouncedHandler class tests the debounced file system event handling functionality.

### TestRepositoryWatcher
The TestRepositoryWatcher class tests the repository watcher functionality.

### TestDebouncedHandlerEvents
The TestDebouncedHandlerEvents class tests specific event handling behavior for the debounced handler.

### TestRelationshipAnalyzer
The TestRelationshipAnalyzer class tests the relationship analysis functionality for determining file relationships.

### TestBuildFileToWikiMap
The TestBuildFileToWikiMap class tests the functionality for building file-to-Wiki page mappings.

### TestGenerateSeeAlsoSection
The TestGenerateSeeAlsoSection class tests the generation of See Also sections for wiki pages.

### TestParsePyprojectToml
The TestParsePyprojectToml class tests parsing of pyproject.toml manifest files.

### TestParsePackageJson
The TestParsePackageJson class tests parsing of package.json manifest files.

### TestParseRequirementsTxt
The TestParseRequirementsTxt class tests parsing of requirements.txt manifest files.

### TestParseCargoToml
The TestParseCargoToml class tests parsing of Cargo.toml manifest files.

### TestParseGoMod
The TestParseGoMod class tests parsing of go.mod manifest files.

### TestGetDirectoryTree
The TestGetDirectoryTree class tests directory tree generation functionality.

### TestMultipleManifests
The TestMultipleManifests class tests handling of multiple manifest files.

## How Components Interact

The components in this module work together to provide comprehensive testing for the local-deepwiki system. The test classes validate individual components like parsers and manifest handlers, while integration tests like TestTocIntegration ensure that components work correctly together in realistic scenarios. Cross-linking tests validate that entities are properly registered and linked, and the watcher tests ensure file system monitoring works as expected.

## Usage Examples

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test class
pytest tests/test_parser.py::TestCodeParser

# Run specific test method
pytest tests/test_parser.py::TestCodeParser::test_detect_language_python
```

### Example Test Class Usage
```python
def test_manifest_has_data():
    manifest = ProjectManifest(name="test-project")
    assert manifest.has_data()
```

## Dependencies

This module depends on:
- `pytest` for test execution
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.watcher` for file system watching functionality
- `local_deepwiki.config` for configuration handling
- `local_deepwiki.models` for data models
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for See Also section generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.manifest` for