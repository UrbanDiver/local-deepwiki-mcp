# src Module Documentation

## Module Purpose

The `src` module contains the core implementation of a documentation generation system that processes code files and generates wiki-style documentation. Based on the code shown, this system can parse code structures, generate module documentation, create diagrams, and manage project manifests.

## Key Classes and Functions

### Core Processing

#### CodeChunk Creation
The `_create_module_chunk` method in the chunker module creates documentation chunks for module/file overviews by processing AST nodes and source code.

#### Path to Module Conversion
The `_path_to_module` function converts file paths (like `src/local_deepwiki/core/indexer.py`) into module names (like `core.indexer`). It filters out non-Python files and special files starting with double underscores.

### Documentation Generation

#### Module Index Generation
The `_generate_modules_index` function creates an index page for modules by processing a list of [WikiPage](../files/src/local_deepwiki/models.md) objects and generating markdown content.

#### Source References
The source_refs module provides functionality to build mappings between files and wiki pages, and can add source reference sections to documentation.

### Project Management

#### ManifestCacheEntry and ProjectManifest Classes
The manifest module contains classes for managing project metadata and caching information, supporting both TOML parsing libraries (`tomllib` and `tomli`).

#### Cache Management Functions
Several functions handle manifest caching including `_get_manifest_mtimes`, `_is_cache_valid`, `_load_manifest_cache`, and `_save_` (function name appears truncated in the provided context).

## How Components Interact

The system follows a pipeline approach:

1. **Path Processing**: File paths are converted to module names using `_path_to_module`
2. **Code Parsing**: The chunker processes source code and creates [CodeChunk](../files/src/local_deepwiki/models.md) objects for modules
3. **Wiki Generation**: Module pages are generated and indexed using `_generate_modules_index`
4. **Reference Linking**: The source_refs module builds mappings between source files and wiki pages
5. **Project Metadata**: The manifest system manages project configuration and caching

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
from local_deepwiki.models import WikiPage

# Create module pages list
module_pages = [
    WikiPage(path="modules/core.md", title="Core Module"),
    WikiPage(path="modules/generators.md", title="Generators Module")
]

# Generate index content
index_content = _generate_modules_index(module_pages)
# Returns markdown content with module links
```

### Building Source Reference Maps

```python
from local_deepwiki.generators.source_refs import build_file_to_wiki_map
from local_deepwiki.models import WikiPage

wiki_pages = [WikiPage(path="api/core.md", title="Core API")]
file_map = build_file_to_wiki_map(wiki_pages)
```

## Dependencies

Based on the imports shown, this module depends on:

- **Standard Library**: `json`, `re`, `pathlib.Path`, `dataclasses`, `typing`
- **TOML Parsing**: `tomllib` and `tomli` (with fallback handling)
- **Internal Modules**: 
  - `local_deepwiki.logging` (for logging functionality)
  - `local_deepwiki.models` (for [WikiPage](../files/src/local_deepwiki/models.md) and [WikiPageStatus](../files/src/local_deepwiki/models.md) classes)

The module structure suggests a modular design with clear separation between core processing, generation, and utility functions.

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
- [`src/local_deepwiki/core/chunker.py:200-600`](../files/src/local_deepwiki/core/chunker.md)


*Showing 10 of 52 source files.*
