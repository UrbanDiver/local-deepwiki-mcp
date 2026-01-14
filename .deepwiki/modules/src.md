# src Module

## Module Purpose

The `src` module contains the core implementation of local_deepwiki, a system for generating documentation from source code. The module is organized into several subpackages that handle different aspects of documentation generation, including code analysis, content generation, web serving, and various provider integrations.

## Key Classes and Functions

### Code Analysis and Processing

#### _create_module_chunk (chunker.py)
Creates a code chunk representing a module or file overview from an Abstract Syntax Tree (AST).

**Parameters:**
- `root`: AST root node
- `source`: Source code as bytes
- `language`: Programming language
- `file_path`: Relative file path

**Returns:** [CodeChunk](../files/src/local_deepwiki/models.md) object

### Content Generation

#### _path_to_module (diagrams.py)
Converts a file path to a module name format.

**Parameters:**
- `file_path`: Path like 'src/local_deepwiki/core/indexer.py'

**Returns:** Module name like 'core.indexer', or None if not applicable

#### _module_matches_file (see_also.py)
Checks if a module name corresponds to a specific file path.

**Parameters:**
- `module`: Module name like 'local_deepwiki.core.chunker'
- `file_path`: File path like 'src/local_deepwiki/core/chunker.py'

**Returns:** Boolean indicating if they match

### Project Manifest Management

#### ManifestCacheEntry (manifest.py)
A dataclass for caching manifest information.

#### ProjectManifest (manifest.py)
Handles project manifest data and operations.

**Functions in manifest module:**
- `_get_manifest_mtimes`: Gets modification times for manifest files
- `_is_cache_valid`: Validates cache validity
- `_load_manifest_cache`: Loads cached manifest data
- `_save_manifest_cache`: Saves manifest data to cache

### Source Reference Generation

The source_refs module provides functions for generating source code references:

- `build_file_to_wiki_map`: Creates mapping between files and wiki pages
- `_relative_path`: Converts paths to relative format
- `_format_file_entry`: Formats file entries for display
- `generate_source_refs_section`: Generates source reference sections
- `add_source_refs_sections`: Adds source references to content

## How Components Interact

The module follows a layered architecture:

1. **Code Analysis Layer**: The chunker module processes source code into structured chunks using AST parsing
2. **Content Generation Layer**: Various generators (diagrams, see_also, source_refs) create different types of documentation content
3. **Manifest Management**: The manifest module handles project configuration and caching
4. **Provider Integration**: The providers subpackage offers base classes for different service integrations

The generators work together to create comprehensive documentation by:
- Converting file paths to module names for cross-referencing
- Matching modules to their corresponding files
- Building source code references with Git integration
- Managing project metadata through manifest files

## Usage Examples

### Converting File Paths to Module Names

```python
from local_deepwiki.generators.diagrams import _path_to_module

# Convert a file path to module format
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Building Source References

```python
from local_deepwiki.generators.source_refs import build_file_to_wiki_map

# Create mapping between files and wiki pages
file_map = build_file_to_wiki_map(wiki_pages)
```

### Using Provider Base Classes

```python
from local_deepwiki.providers import EmbeddingProvider, LLMProvider

# Use base provider classes for implementing custom providers
```

## Dependencies

Based on the imports shown in the code, this module depends on:

**Standard Library:**
- `json`: JSON processing
- `re`: Regular expressions
- `pathlib.Path`: Path manipulation
- `dataclasses`: Data structure definitions
- `typing`: Type annotations

**External Libraries:**
- `tomllib`/`tomli`: TOML file parsing (with fallback support)

**Internal Dependencies:**
- `local_deepwiki.logging`: Logging utilities
- `local_deepwiki.core.git_utils`: Git repository utilities
- `local_deepwiki.models`: Data models ([WikiPage](../files/src/local_deepwiki/models.md), [WikiPageStatus](../files/src/local_deepwiki/models.md))
- `local_deepwiki.providers.base`: Base provider classes

The module structure indicates a well-organized codebase with clear separation of concerns across core functionality, generators, providers, and web components.

## Relevant Source Files

The following source files were used to generate this documentation:

- `src/local_deepwiki/logging.py:19-70`
- [`src/local_deepwiki/server.py:33-53`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:14-19`](../files/src/local_deepwiki/config.md)
- [`src/local_deepwiki/models.py:11-26`](../files/src/local_deepwiki/models.md)
- `src/local_deepwiki/__init__.py`
- `src/local_deepwiki/watcher.py:29-223`
- `src/local_deepwiki/tools/__init__.py`
- `src/local_deepwiki/core/chunker.py:200-597`
- `src/local_deepwiki/core/llm_cache.py:19-357`
- `src/local_deepwiki/core/vectorstore.py:37-395`


*Showing 10 of 43 source files.*
