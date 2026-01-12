# tests Module Documentation

## Module Purpose

The tests module contains unit and integration tests for various components of the local-deepwiki project. It provides test suites for parsing code, managing manifests, generating tables of contents, handling cross-links, and other core functionality. The tests ensure that the various generators and utilities behave as expected.

## Key Classes and Functions

### TestCodeParser
Test suite for [CodeParser](../files/src/local_deepwiki/core/parser.md).

Methods:
- `setup_method`: Sets up test fixtures.
- `test_detect_language_python`: Tests Python language detection.

### TestProjectManifest
Tests for [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) dataclass.

Methods:
- `test_has_data_empty`: Tests that empty manifest has no data.
- `test_has_data_with_name`: Tests that manifest with name has data.

### TestParsePyprojectToml
Tests for parsing pyproject.toml files.

### TestParsePackageJson
Tests for parsing package.json files.

### TestParseRequirementsTxt
Tests for parsing requirements.txt files.

### TestParseCargoToml
Tests for parsing Cargo.toml files.

### TestParseGoMod
Tests for parsing go.mod files.

### TestGetDirectoryTree
Tests for getting directory tree structure.

### TestMultipleManifests
Tests for handling multiple manifest files.

### TestPathToModule
Tests for `_path_to_module` function.

Methods:
- `test_converts_simple_path`: Tests basic path conversion.
- `test_skips_init_files`: Tests that __init__.py files return None.

### TestAddSourceRefsSections
Tests for adding source references sections.

Methods:
- `test_adds_sections_to_file_pages`
- `test_skips_index_pages`
- `test_inserts_before_see_also`
- `test_handles_missing_status`
- `test_adds_section_to_module_pages`
- `test_adds_section_to_architecture_page`

### TestEntityRegistry
Tests for entity registry functionality.

Methods:
- `test_register_entity`
- `test_skips_short_names`
- `test_skips_private_names`
- `test_skips_excluded_names`
- `test_register_from_chunks`
- `test_get_page_entities`
- `test_registers_camelcase_aliases`
- `test_alias_lookup`

### TestCrossLinker
Tests for cross-linking functionality.

Methods:
- `test_adds_links_to_prose`
- `test_does_not_link_in_code_blocks`
- `test_does_not_self_link`
- `test_relative_paths`
- `test_links_backticked_entities`
- `test_does_not_link_non_entity_inline_code`
- `test_links_qualified_names`
- `test_links_simple_qualified_names`
- `test_preserves_existing_links`
- `test_links_bold_text`
- `test_links_spaced_aliases`
- `test_links_bold_spaced_aliases`

### TestTocIntegration
Integration tests for TOC generation.

Methods:
- `test_full_wiki_structure`: Tests TOC generation with a realistic wiki structure.

### TestWatchedExtensions
Tests for watched file extensions.

Methods:
- `test_python_extensions`: Tests that Python extensions are watched.
- `test_javascript_extensions`: Tests that JavaScript/TypeScript extensions are watched.

### TestRelationshipAnalyzer
Tests for [RelationshipAnalyzer](../files/src/local_deepwiki/generators/see_also.md).

### TestBuildFileToWikiMap
Tests for [build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md) function.

### TestGenerateSeeAlsoSection
Tests for [generate_see_also_section](../files/src/local_deepwiki/generators/see_also.md) function.

### TestIncrementalWiki
Tests for incremental wiki generation.

### TestWeb
Tests for web-related functionality.

### TestApiDocs
Tests for API documentation generation.

## How Components Interact

The tests module provides comprehensive test coverage for various components of the local-deepwiki system. The tests are organized by functionality:

- **Manifest parsing tests** (`TestProjectManifest`, `TestParsePyprojectToml`, etc.) validate how different project manifest files are parsed and handled.
- **Parser tests** (`TestCodeParser`) ensure that code language detection works correctly.
- **Cross-linking tests** ([`TestEntityRegistry`](../files/tests/test_crosslinks.md), [`TestCrossLinker`](../files/tests/test_crosslinks.md)) verify that entity registration and linking functions work properly.
- **TOC generation tests** (`TestTocIntegration`) test the integration of table of contents generation within a full wiki structure.
- **Path and utility tests** ([`TestPathToModule`](../files/tests/test_diagrams.md), [`TestWatchedExtensions`](../files/tests/test_watcher.md)) validate helper functions and configuration settings.

## Usage Examples

```python
# Example of running a specific test class
# python -m pytest tests/test_parser.py::TestCodeParser::test_detect_language_python

# Example of running all manifest-related tests
# python -m pytest tests/test_manifest.py
```

## Dependencies

The tests module depends on:
- `pytest` for test execution
- `local_deepwiki.generators.manifest` for manifest-related functionality
- `local_deepwiki.generators.see_also` for see also section generation
- `local_deepwiki.generators.crosslinks` for cross-linking functionality
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.models` for data models like ChunkType, CodeChunk, WikiPage, Language
- `pathlib.Path` for path manipulation
- `json` for JSON handling
- `tempfile` for temporary file handling

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
