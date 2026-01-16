# src Module Documentation

## Module Purpose

The `src` module contains the core functionality for Local DeepWiki, a documentation generation system. Based on the code shown, this module provides capabilities for parsing code into chunks, generating wiki documentation, managing project manifests, and creating source reference mappings.

## Key Classes and Functions

### Core Components

#### CodeChunk Creation (`core/chunker.py`)

The chunker module contains methods for creating structured code chunks:

- **_create_module_chunk** - Creates a chunk representing a module or file overview by processing AST root nodes and source code

#### Project Manifest Management (`generators/manifest.py`)

The manifest module handles project configuration and metadata:

- **[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)** - Data class for caching manifest information
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)** - Main class representing project configuration and metadata
- **_get_manifest_mtimes** - Retrieves modification times for manifest files
- **_is_cache_valid** - Validates whether cached manifest data is still current
- **_load_manifest_cache** - Loads cached manifest data from storage
- **_save_** - Saves manifest data (function name truncated in context)

#### Wiki Generation (`generators/wiki_modules.py`)

Functions for generating wiki documentation:

- **_generate_modules_index** - Creates an index page listing all module documentation pages

#### Source References (`generators/source_refs.py`)

Tools for managing source code references in wiki pages:

- **[build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md)** - Creates mapping between source files and wiki pages
- **_relative_path** - Converts file paths to relative format
- **_format_file_entry** - Formats file entries for display
- **[generate_source_refs_section](../files/src/local_deepwiki/generators/source_refs.md)** - Generates source reference sections for wiki pages
- **_strip_existing_source_refs** - Removes existing source reference sections
- **[add_source_refs_sections](../files/src/local_deepwiki/generators/source_refs.md)** - Adds source reference sections to wiki pages

#### Utility Functions (`generators/diagrams.py`)

Helper functions for processing file paths:

- **_path_to_module** - Converts file paths to module names, filtering out non-Python files and special files starting with `__`

## How Components Interact

The components work together to create a documentation generation pipeline:

1. The **chunker** processes source code files and creates structured code chunks for analysis
2. The **manifest** system manages project configuration and caches metadata for performance
3. The **wiki_modules** generator creates organized documentation pages from the processed chunks
4. The **source_refs** system maintains bidirectional links between source files and generated documentation
5. Utility functions like **_path_to_module** provide common path processing functionality across generators

## Usage Examples

### Converting File Paths to Module Names

```python
from local_deepwiki.generators.diagrams import _path_to_module

# Convert a Python file path to module name
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"

# Non-Python files return None
result = _path_to_module("README.md")
# Returns: None
```

### Generating Module Index

```python
from local_deepwiki.generators.wiki_modules import _generate_modules_index

# Generate index from module pages
module_pages = [...]  # List of WikiPage objects
index_content = _generate_modules_index(module_pages)
# Returns markdown content for the modules index
```

### Building File-to-Wiki Mappings

```python
from local_deepwiki.generators.source_refs import build_file_to_wiki_map

# Create mapping between source files and wiki pages
file_map = build_file_to_wiki_map(wiki_pages, source_files)
```

## Dependencies

Based on the imports shown, this module depends on:

### Standard Library
- `json` - JSON data handling
- `re` - Regular expressions
- `pathlib.Path` - Path manipulation
- `dataclasses` - Data class definitions
- `typing` - Type annotations

### TOML Processing
- `tomllib` / `tomli` - TOML configuration file parsing (with fallback support)

### Internal Dependencies
- `local_deepwiki.logging` - Logging functionality via [get_logger](../files/src/local_deepwiki/logging.md)
- `local_deepwiki.models` - Data models including [WikiPage](../files/src/local_deepwiki/models.md) and [WikiPageStatus](../files/src/local_deepwiki/models.md)

The module uses conditional imports for TOML processing to handle different Python versions and available libraries.

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


*Showing 10 of 52 source files.*
