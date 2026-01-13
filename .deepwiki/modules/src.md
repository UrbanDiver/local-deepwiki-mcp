# src Module Documentation

## Module Purpose

The `src` module contains the core implementation of the local_deepwiki system, a documentation generation and management tool for codebases. Based on the code structure, it provides functionality for parsing source code, generating documentation, managing vector stores, and serving content through a web interface.

## Key Classes and Functions

### Core Components

#### CodeChunk (from core/chunker.py)
The chunker module contains methods for creating code chunks from parsed source files:

- **_create_module_chunk** - Creates a chunk representing a module or file overview from an AST root node, source bytes, language information, and file path.

### Generators

#### ManifestCacheEntry and ProjectManifest (from generators/manifest.py)
Classes for managing project manifest information and caching:

- **[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)** - Dataclass for storing cached manifest entries
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)** - Handles project manifest data

The manifest module also includes utility functions:
- **_get_manifest_mtimes** - Retrieves modification times for manifest files
- **_is_cache_valid** - Validates cache validity
- **_load_manifest_cache** - Loads cached manifest data
- **_save_** - Saves manifest data (function name truncated in context)

#### Source References Generator (generators/source_refs.py)
Functions for generating source code reference sections:

- **build_file_to_wiki_map** - Creates mapping between files and wiki pages
- **_relative_path** - Converts paths to relative format
- **_format_file_entry** - Formats file entries for display
- **generate_source_refs_section** - Generates source reference sections
- **add_source_refs_sections** - Adds source reference sections to content

#### See Also Generator (generators/see_also.py)
Contains methods for generating "see also" sections:

- **_module_matches_file** - Checks if a module name corresponds to a specific file path by converting file paths to module-like format

#### Diagrams Generator (generators/diagrams.py)
Utility functions for diagram generation:

- **_path_to_module** - Converts file paths (like `src/local_deepwiki/core/indexer.py`) to module names (like `core.indexer`), filtering out non-Python files and files starting with double underscores

### Providers

#### Base Provider Classes (providers/__init__.py)
The providers module exports base classes for different service providers:

- **EmbeddingProvider** - Base class for embedding service providers
- **LLMProvider** - Base class for language model providers

## How Components Interact

The components work together to create a comprehensive documentation system:

1. **Code Processing**: The chunker processes source code files, creating CodeChunk objects that represent different parts of the codebase
2. **Manifest Management**: The manifest system tracks project configuration and caches metadata for efficient processing
3. **Reference Generation**: Source reference generators create cross-links between documentation and source files
4. **Provider Abstraction**: The provider system allows pluggable backends for embeddings and language models

## Usage Examples

### Creating Module Chunks
```python
# Example of how _create_module_chunk might be used
chunk = chunker._create_module_chunk(
    root=ast_root_node,
    source=file_contents.encode(),
    language=python_language,
    file_path="src/local_deepwiki/core/indexer.py"
)
```

### Converting Paths to Modules
```python
# Convert a file path to module name
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Checking Module-File Matches
```python
# Check if a module corresponds to a file
matches = generator._module_matches_file(
    "local_deepwiki.core.chunker",
    "src/local_deepwiki/core/chunker.py"
)
```

### Building File-Wiki Mappings
```python
# Generate mapping between source files and wiki pages
file_map = build_file_to_wiki_map(wiki_pages)
```

## Dependencies

Based on the imports shown in the code context:

- **Standard Library**: `json`, `re`, `pathlib.Path`, `dataclasses`, `typing`
- **TOML Processing**: `tomllib` (with fallback to `tomli`)
- **Internal Dependencies**: 
  - `local_deepwiki.logging` - For logging functionality
  - `local_deepwiki.models` - For WikiPage and WikiPageStatus models
  - `local_deepwiki.providers.base` - For provider base classes

The module structure suggests a well-organized codebase with clear separation between core functionality, generators for different types of content, web interface components, and pluggable provider systems.

## Relevant Source Files

The following source files were used to generate this documentation:

- `src/local_deepwiki/logging.py:19-70`
- [`src/local_deepwiki/server.py:33-53`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:13-18`](../files/src/local_deepwiki/config.md)
- `src/local_deepwiki/models.py:11-26`
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:29-223`](../files/src/local_deepwiki/watcher.md)
- `src/local_deepwiki/tools/__init__.py`
- `src/local_deepwiki/core/chunker.py:200-597`
- [`src/local_deepwiki/core/vectorstore.py:37-395`](../files/src/local_deepwiki/core/vectorstore.md)
- `src/local_deepwiki/core/__init__.py`


*Showing 10 of 37 source files.*
