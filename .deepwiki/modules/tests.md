# Tests Module Documentation

## Module Purpose

The tests module contains unit and integration tests for various components of the local_deepwiki project. These tests verify the functionality of code parsing, manifest handling, cross-linking, TOC generation, and other core features.

## Key Classes and Functions

### TestCodeParser
The TestCodeParser class tests the [CodeParser](../files/src/local_deepwiki/core/parser.md) functionality, including language detection for Python files.

### TestProjectManifest
The TestProjectManifest class tests the [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) dataclass, verifying its behavior with and without data.

### TestPathToModule
The [TestPathToModule](../files/tests/test_diagrams.md) class tests the `_path_to_module` function, which converts file paths to module names while skipping `__init__.py` files.

### TestAddSourceRefsSections
The [TestAddSourceRefsSections](../files/tests/test_source_refs.md) class tests the addition of source references sections to wiki pages, handling various scenarios including index pages and see also sections.

### TestEntityRegistry
The [TestEntityRegistry](../files/tests/test_crosslinks.md) class tests the entity registry functionality, including entity registration, alias handling, and lookup behavior.

### TestCrossLinker
The [TestCrossLinker](../files/tests/test_crosslinks.md) class tests cross-linking functionality, including linking prose, code blocks, qualified names, and handling of existing links.

### TestTocIntegration
The TestTocIntegration class performs integration tests for table of contents (TOC) generation with realistic wiki structures.

### TestWatchedExtensions
The [TestWatchedExtensions](../files/tests/test_watcher.md) class verifies that watched file extensions include Python and JavaScript/TypeScript extensions.

### TestRelationshipAnalyzer
The TestRelationshipAnalyzer class tests the relationship analysis functionality for determining file relationships.

### TestBuildFileToWikiMap
The [TestBuildFileToWikiMap](../files/tests/test_source_refs.md) class tests the creation of mappings between files and wiki pages.

### TestGenerateSeeAlsoSection
The TestGenerateSeeAlsoSection class tests the generation of "See Also" sections for wiki pages.

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
The TestGetDirectoryTree class tests the directory tree generation functionality.

### TestMultipleManifests
The TestMultipleManifests class tests handling of multiple manifest files.

## How Components Interact

The components in this module work together to provide comprehensive testing coverage for the local_deepwiki project. The test classes for parsing, manifest handling, and cross-linking verify core functionality, while integration tests like TestTocIntegration ensure that components work together properly in realistic scenarios. The test suite validates both individual functions and end-to-end workflows.

## Usage Examples

```python
# Run all tests in the module
pytest tests/

# Run specific test class
pytest tests/test_parser.py::TestCodeParser

# Run specific test method
pytest tests/test_manifest.py::TestProjectManifest::test_has_data_empty
```

## Dependencies

The tests module depends on:
- `pytest` for test execution
- `local_deepwiki.generators.manifest` for manifest-related functionality
- `local_deepwiki.generators.see_also` for see also section generation
- `local_deepwiki.models` for data models
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.wiki` for wiki generation
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.diagrams` for diagram generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.watcher` for file watching functionality
- `local_deepwiki.generators.toc` for table of contents generation
- `local_deepwiki.generators.incremental_wiki` for incremental wiki generation
- `local_deepwiki.generators.web` for web-related functionality
- `local_deepwiki.generators.api_docs` for API documentation generation
- `local_deepwiki.generators.chunker` for chunking functionality
- `local_deepwiki.generators.search` for search functionality
- `local_deepwiki.generators.diagrams` for diagram generation
- `local_deepwiki.generators.source_refs` for source reference handling
- `local_deepwiki.generators.watcher` for file watching functionality

## Relevant Source Files

The following source files were used to generate this documentation:

- `tests/test_parser.py:12-111`
- `tests/test_chunker.py:11-182`
- `tests/test_search.py:20-53`
- `tests/test_toc.py:16-44`
- [`tests/test_incremental_wiki.py:20-47`](../files/tests/test_incremental_wiki.md)
- `tests/test_web.py:39-103`
- `tests/__init__.py`
- `tests/test_manifest.py:14-56`
- [`tests/test_api_docs.py:31-53`](../files/tests/test_api_docs.md)
- `tests/test_see_also.py:16-177`


*Showing 10 of 17 source files.*
