# src Module Documentation

## Module Purpose

The `src` module contains the core implementation of the local_deepwiki system, organized into several submodules that handle different aspects of wiki generation, code analysis, and web serving functionality.

## Key Classes and Functions

### ManifestCacheEntry and ProjectManifest Classes

Located in `generators/manifest.py`, these classes handle project manifest data and caching:

- **[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)** - A dataclass for storing cached manifest information
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)** - Manages project configuration and metadata

### Code Analysis Functions

Several utility functions support code analysis and module management:

**_path_to_module** (in `generators/diagrams.py`)
- Converts file paths to module names
- Takes a file path like `src/local_deepwiki/core/indexer.py` and returns `core.indexer`
- Returns `None` for non-Python files or files starting with `__`

**_module_to_wiki_path** (in `generators/diagrams.py`)
- Converts module names to wiki file paths
- Takes module name like `core.parser` and project name to generate paths like `src/local_deepwiki/core/parser.md`

**_module_matches_file** (in `generators/see_also.py`)
- Checks if a module name corresponds to a specific file path
- Used for matching module references to actual source files

### Chunking and Processing

**_create_module_chunk** (in `core/chunker.py`)
- Creates code chunks for module/file overviews
- Processes AST root nodes and source bytes to generate structured chunks

### Source Reference Management

The `generators/source_refs.py` module provides functions for managing source code references:

- **[build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md)** - Creates mappings between source files and wiki pages
- **[generate_source_refs_section](../files/src/local_deepwiki/generators/source_refs.md)** - Generates reference sections for wiki pages
- **[add_source_refs_sections](../files/src/local_deepwiki/generators/source_refs.md)** - Adds source reference sections to existing content

## How Components Interact

The module components work together to analyze source code and generate wiki documentation:

1. **Path/Module Conversion**: Functions like _path_to_module and _module_to_wiki_path handle the conversion between file system paths and module names
2. **Code Analysis**: The chunker processes source files using AST parsing to create structured representations
3. **Reference Generation**: Source reference utilities create cross-links between wiki pages and source files
4. **Manifest Management**: Project manifest classes handle configuration and caching for the documentation generation process

## Usage Examples

### Converting File Paths to Module Names

```python
from local_deepwiki.generators.diagrams import _path_to_module

# Convert a file path to module name
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Converting Module Names to Wiki Paths

```python
from local_deepwiki.generators.diagrams import _module_to_wiki_path

# Generate wiki path from module name
wiki_path = _module_to_wiki_path("core.parser", "local_deepwiki")
# Returns: "src/local_deepwiki/core/parser.md"
```

## Dependencies

Based on the imports shown in the code context:

- **Standard Library**: `json`, `re`, `pathlib.Path`, `dataclasses`, `typing`
- **TOML Processing**: `tomllib` or `tomli` (with fallback handling)
- **Internal Modules**: 
  - `local_deepwiki.logging` - For logging functionality
  - `local_deepwiki.models` - For [WikiPage](../files/src/local_deepwiki/models.md) and [WikiPageStatus](../files/src/local_deepwiki/models.md) classes

The module structure indicates a well-organized codebase with clear separation between generators, core functionality, and web components, though the specific implementations of many components are not visible in the provided context.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/logging.py:19-70`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:31-222`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:14-19`](../files/src/local_deepwiki/config.md)
- [`src/local_deepwiki/models.py:11-26`](../files/src/local_deepwiki/models.md)
- [`src/local_deepwiki/handlers.py:40-68`](../files/src/local_deepwiki/handlers.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:29-223`](../files/src/local_deepwiki/watcher.md)
- `src/local_deepwiki/tools/__init__.py`
- [`src/local_deepwiki/core/chunker.py:200-597`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/core/llm_cache.py:19-357`](../files/src/local_deepwiki/core/llm_cache.md)


*Showing 10 of 45 source files.*
