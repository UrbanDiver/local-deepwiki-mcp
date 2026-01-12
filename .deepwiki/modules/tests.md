# Tests Module Documentation

## Module Purpose

The tests module contains unit and integration tests for various components of the local-deepwiki project. These tests validate the functionality of code parsing, manifest handling, cross-linking, TOC generation, and other core features. The tests are organized into individual files, each focusing on a specific component or functionality.

## Key Classes and Functions

### TestCodeParser
Test suite for [CodeParser](../files/src/local_deepwiki/core/parser.md).
- `setup_method`: Sets up test fixtures by creating a [CodeParser](../files/src/local_deepwiki/core/parser.md) instance.
- `test_detect_language_python`: Tests Python language detection for .py and .pyi files.

### TestProjectManifest
Tests for [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) dataclass.
- `test_has_data_empty`: Tests that an empty manifest has no data.
- `test_has_data_with_name`: Tests that a manifest with a name has data.

### TestParsePyprojectToml
Tests for parsing pyproject.toml files.
- `test_parses_pyproject_toml`: Tests parsing of a pyproject.toml file.

### TestParsePackageJson
Tests for parsing package.json files.
- `test_parses_package_json`: Tests parsing of a package.json file.

### TestParseRequirementsTxt
Tests for parsing requirements.txt files.
- `test_parses_requirements_txt`: Tests parsing of a requirements.txt file.

### TestParseCargoToml
Tests for parsing Cargo.toml files.
- `test_parses_cargo_toml`: Tests parsing of a Cargo.toml file.

### TestParseGoMod
Tests for parsing go.mod files.
- `test_parses_go_mod`: Tests parsing of a go.mod file.

### TestGetDirectoryTree
Tests for getting directory tree.
- `test_gets_directory_tree`: Tests getting directory tree from a path.

### TestMultipleManifests
Tests for handling multiple manifests.
- `test_handles_multiple_manifests`: Tests handling of multiple manifests.

### TestPathToModule
Tests for _path_to_module function.
- `test_converts_simple_path`: Tests basic path conversion.
- `test_skips_init_files`: Tests that __init__.py files return None.

### TestAddSourceRefsSections
Tests for adding source references sections.
- `test_adds_sections_to_file_pages`: Tests adding sections to file pages.
- `test_skips_index_pages`: Tests skipping index pages.
- `test_inserts_before_see_also`: Tests inserting before see also section.
- `test_handles_missing_status`: Tests handling missing status.
- `test_adds_section_to_module_pages`: Tests adding section to module pages.
- `test_adds_section_to_architecture_page`: Tests adding section to architecture page.

### TestEntityRegistry
Tests for [EntityRegistry](../files/src/local_deepwiki/generators/crosslinks.md).
- `test_register_entity`: Tests registering an entity.
- `test_skips_short_names`: Tests skipping short names.
- `test_skips_private_names`: Tests skipping private names.
- `test_skips_excluded_names`: Tests skipping excluded names.
- `test_register_from_chunks`: Tests registering from chunks.
- `test_get_page_entities`: Tests getting page entities.
- `test_registers_camelcase_aliases`: Tests registering camelcase aliases.
- `test_alias_lookup`: Tests alias lookup.

### TestCrossLinker
Tests for [CrossLinker](../files/src/local_deepwiki/generators/crosslinks.md).
- `test_adds_links_to_prose`: Tests adding links to prose.
- `test_does_not_link_in_code_blocks`: Tests that code blocks are not linked.
- `test_does_not_self_link`: Tests that self-links are not created.
- `test_relative_paths`: Tests relative paths.
- `test_links_backticked_entities`: Tests linking backticked entities.
- `test_does_not_link_non_entity_inline_code`: Tests that non-entity inline code is not linked.
- `test_links_qualified_names`: Tests linking qualified names.
- `test_links_simple_qualified_names`: Tests linking simple qualified names.
- `test_preserves_existing_links`: Tests preserving existing links.
- `test_links_bold_text`: Tests linking bold text.
- `test_links_spaced_aliases`: Tests linking spaced aliases.
- `test_links_bold_spaced_aliases`: Tests linking bold spaced aliases.

### TestTocIntegration
Integration tests for TOC generation.
- `test_full_wiki_structure`: Tests TOC generation with a realistic wiki structure.

### TestRelationshipAnalyzer
Tests for [RelationshipAnalyzer](../files/src/local_deepwiki/generators/see_also.md).
- `test_analyzes_relationships`: Tests analyzing file relationships.

### TestBuildFileToWikiMap
Tests for [build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md).
- `test_builds_file_to_wiki_map`: Tests building file to wiki map.

### TestGenerateSeeAlsoSection
Tests for [generate_see_also_section](../files/src/local_deepwiki/generators/see_also.md).
- `test_generates_see_also_section`: Tests generating see also section.

### TestWatchedExtensions
Tests for watched extensions.
- `test_python_extensions`: Tests that Python extensions are watched.
- `test_javascript_extensions`: Tests that JavaScript/TypeScript extensions are watched.

## How Components Interact

The components in this module work together to provide comprehensive testing for the local-deepwiki system. The test classes validate the functionality of parsing, manifest handling, cross-linking, and TOC generation. Each test file focuses on a specific area of functionality, ensuring that changes to the core system don't break existing features.

For example, the TestCodeParser tests the code parsing functionality, while TestProjectManifest tests the manifest handling. The [TestCrossLinker](../files/tests/test_crosslinks.md) tests cross-linking behavior, and TestTocIntegration tests TOC generation with realistic wiki structures.

## Usage Examples

```python
# Running a specific test class
pytest tests/test_parser.py::TestCodeParser::test_detect_language_python

# Running all tests in a module
pytest tests/test_manifest.py

# Running a specific test method
pytest tests/test_crosslinks.py::TestEntityRegistry::test_register_entity
```

## Dependencies

This module depends on:
- `pytest` for test execution
- `local_deepwiki.generators.manifest` for manifest handling
- `local_deepwiki.generators.see_also` for see also section generation
- `local_deepwiki.models` for data models
- `local_deepwiki.generators.crosslink` for cross-linking functionality
- `local_deepwiki.generators.toc` for TOC generation
- `local_deepwiki.generators.parser` for code parsing
- `local_deepwiki.generators.wiki` for wiki generation
- `local_deepwiki.utils` for utility functions
- `pathlib` for path manipulation
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
