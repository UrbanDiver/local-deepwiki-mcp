# src Module

The src module contains the core functionality for Local DeepWiki, a documentation generation system that processes source code and creates wiki-style documentation.

## Module Purpose

This module provides the infrastructure for analyzing source code, generating documentation pages, and managing project manifests. It includes components for chunking code into analyzable segments, generating module documentation, handling source references, creating diagrams, and managing project metadata.

## Key Classes and Functions

### Code Processing

**[CodeChunk](../files/src/local_deepwiki/models.md)** (from `core/chunker.py`)
- Represents a segment of code that has been processed and chunked for analysis
- Created by the `_create_module_chunk` method which processes AST nodes and source code

### Project Management  

**[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)** (from `generators/manifest.py`)
- Stores cached manifest data with metadata for validation

**[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)** (from `generators/manifest.py`)  
- Represents project configuration and metadata loaded from manifest files
- Supports both TOML and JSON format parsing

### Documentation Generation

**[WikiPage](../files/src/local_deepwiki/models.md)** and **[WikiPageStatus](../files/src/local_deepwiki/models.md)** (from `models.py`, used in `source_refs.py`)
- Core data structures for representing generated documentation pages
- [WikiPageStatus](../files/src/local_deepwiki/models.md) tracks the processing state of pages

## Key Functions

### Module Documentation
- `_generate_modules_index` - Creates an index page listing all module documentation pages
- `_path_to_module` - Converts file paths to module names for documentation organization

### Source References
- [`build_file_to_wiki_map`](../files/src/local_deepwiki/generators/see_also.md) - Maps source files to their corresponding wiki pages
- [`generate_source_refs_section`](../files/src/local_deepwiki/generators/source_refs.md) - Creates cross-reference sections linking source code to documentation
- [`add_source_refs_sections`](../files/src/local_deepwiki/generators/source_refs.md) - Adds source reference sections to existing wiki pages
- `_strip_existing_source_refs` - Removes existing source reference sections during updates

### Manifest Management
- `_get_manifest_mtimes` - Retrieves modification times for manifest validation
- `_is_cache_valid` - Validates cached manifest data against file timestamps  
- `_load_manifest_cache` and `_save_manifest_cache` - Handle manifest caching operations

## How Components Interact

The module follows a pipeline approach:

1. **Code Analysis**: The chunker processes source files using AST parsing, creating [CodeChunk](../files/src/local_deepwiki/models.md) objects that represent analyzable code segments

2. **Manifest Processing**: [ProjectManifest](../files/src/local_deepwiki/generators/manifest.md) loads project configuration, with caching handled by [ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md) to avoid redundant file parsing

3. **Documentation Generation**: Module generators create [WikiPage](../files/src/local_deepwiki/models.md) objects, with `_generate_modules_index` organizing them into a navigable structure

4. **Cross-Referencing**: Source reference functions create bidirectional links between source code and documentation pages

## Usage Examples

### Creating Module Documentation Index

```python
from local_deepwiki.generators.wiki_modules import _generate_modules_index

# Generate index from module pages
module_pages = [...]  # List of WikiPage objects
index_content = _generate_modules_index(module_pages)
```

### Converting File Paths to Module Names

```python
from local_deepwiki.generators.diagrams import _path_to_module

# Convert file path to module name
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Building Source-to-Wiki Mapping

```python
from local_deepwiki.generators.source_refs import build_file_to_wiki_map

wiki_pages = [...]  # List of WikiPage objects
file_map = build_file_to_wiki_map(wiki_pages)
```

### Adding Source References

```python
from local_deepwiki.generators.source_refs import add_source_refs_sections

wiki_pages = [...]  # List of WikiPage objects
file_to_wiki_map = {...}  # Mapping from build_file_to_wiki_map
updated_pages = add_source_refs_sections(wiki_pages, file_to_wiki_map)
```

## Dependencies

Based on the imports shown, this module depends on:

- **Standard Library**: `json`, `re`, `pathlib.Path`, `dataclasses`, `typing`
- **TOML Processing**: `tomllib` (with `tomli` fallback)
- **Internal Modules**: 
  - `local_deepwiki.logging` - For logging functionality
  - `local_deepwiki.models` - For [WikiPage](../files/src/local_deepwiki/models.md) and [WikiPageStatus](../files/src/local_deepwiki/models.md) data structures
- **External Libraries**: `tree_sitter` ([Language](../files/src/local_deepwiki/models.md), Node types for AST processing)

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/logging.py:18-72`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:31-222`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:14-19`](../files/src/local_deepwiki/config.md)
- [`src/local_deepwiki/models.py:11-26`](../files/src/local_deepwiki/models.md)
- [`src/local_deepwiki/handlers.py:40-70`](../files/src/local_deepwiki/handlers.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:35-235`](../files/src/local_deepwiki/watcher.md)
- [`src/local_deepwiki/validation.py:22-42`](../files/src/local_deepwiki/validation.md)
- `src/local_deepwiki/tools/__init__.py`
- [`src/local_deepwiki/core/chunker.py:498-906`](../files/src/local_deepwiki/core/chunker.md)


*Showing 10 of 53 source files.*
