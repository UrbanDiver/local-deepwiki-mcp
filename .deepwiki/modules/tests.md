# Tests Module Documentation

## Module Purpose and Responsibilities

The tests module contains all unit and integration tests for the local_deepwiki package. It ensures the correctness of core functionality including code parsing, chunking, search capabilities, incremental wiki generation, manifest handling, cross-linking, and file watching. The tests validate that components work as expected in isolation and together as a system.

## Key Classes and Functions

### TestCodeParser
Tests the [CodeParser](../files/src/local_deepwiki/core/parser.md) class which handles language detection and parsing of source code files. It validates that the parser correctly identifies programming languages based on file extensions.

### TestProjectManifest
Tests the [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) dataclass and related manifest parsing functions. These tests ensure that project metadata is correctly extracted from various manifest files like pyproject.toml, package.json, requirements.txt, Cargo.toml, and go.mod.

### TestEntityRegistry
Tests the [EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md) class which manages entity registration and cross-linking. This includes testing entity registration, alias handling, and lookup functionality for creating meaningful cross-references between wiki pages.

### TestCrossLinker
Tests the [CrossLinker](../files/src/local_deepwiki/generators/crosslinks.md) class which adds hyperlinks to wiki content. It validates that links are properly added to prose while avoiding linking in code blocks, self-links, and inline code, and handles various naming conventions and link formats.

### TestWatchedExtensions
Tests that the WATCHED_EXTENSIONS constant contains the correct file extensions for files that should trigger wiki regeneration events.

### TestDebouncedHandler
Tests the [DebouncedHandler](../files/src/local_deepwiki/watcher.md) class which handles file system events with debouncing to prevent excessive processing. This ensures that file changes are properly batched and processed efficiently.

### TestRepositoryWatcher
Tests the [RepositoryWatcher](../files/src/local_deepwiki/watcher.md) class which monitors repository changes and triggers wiki regeneration. This includes testing event handling, file filtering, and status tracking for incremental updates.

### TestRelationshipAnalyzer
Tests the [RelationshipAnalyzer](../files/src/local_deepwiki/generators/see_also.md) class which determines relationships between files based on code references and dependencies. This is used for generating "See Also" sections.

### TestBuildFileToWikiMap
Tests the [build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md) function which creates mappings between source files and their corresponding wiki pages.

### TestGenerateSeeAlsoSection
Tests the [generate_see_also_section](../files/src/local_deepwiki/generators/see_also.md) function which creates "See Also" content for wiki pages based on file relationships.

### TestIncrementalWiki
Tests the incremental wiki generation functionality, including status checking and regeneration logic.

### TestWeb
Tests web-related functionality including API endpoints and web interface components.

### TestSearch
Tests the search functionality, validating that search queries return correct results and that search indexes are properly maintained.

### TestChunker
Tests the chunker functionality, ensuring that source code and text content are properly segmented into manageable chunks for processing.

### TestConfig
Tests configuration loading and validation, ensuring that configuration values are correctly parsed and applied.

## How Components Interact

The test module works by directly testing individual components and their interactions:

1. The [CodeParser](../files/src/local_deepwiki/core/parser.md) tests validate that parsing works correctly before other components use it
2. The [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) tests ensure that configuration data is properly extracted from project files
3. The [EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md) and [CrossLinker](../files/src/local_deepwiki/generators/crosslinks.md) tests validate that cross-referencing works correctly
4. The [RepositoryWatcher](../files/src/local_deepwiki/watcher.md) and [DebouncedHandler](../files/src/local_deepwiki/watcher.md) tests ensure that file system monitoring works properly
5. The incremental wiki tests validate that regeneration logic works correctly
6. The search and chunker tests ensure that core processing functionality works as expected

Tests are organized by the component they test, with each test class containing multiple test methods that validate specific functionality.

## Usage Examples

```python
# Example of running tests for a specific component
pytest tests/test_parser.py::TestCodeParser::test_detect_language_python

# Example of running all tests
pytest tests/

# Example of running tests with verbose output
pytest tests/test_manifest.py -v
```

## Dependencies

This module depends on:
- `pytest` for test execution
- `unittest.mock` for mocking functionality
- `pathlib` for path handling
- `local_deepwiki` package modules including:
  - `generators.manifest` for manifest handling
  - `generators.see_also` for "See Also" functionality
  - `models` for data models
  - `config` for configuration handling
  - `watcher` for file watching functionality
  - `wiki_generator` for wiki generation
  - `chunker` for content chunking
  - `search` for search functionality
  - `crosslinker` for cross-linking functionality