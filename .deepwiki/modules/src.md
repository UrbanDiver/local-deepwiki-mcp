# src Module Documentation

## Module Purpose

The `src` module is the core implementation of the local_deepwiki system, providing functionality for code analysis, documentation generation, and wiki management. Based on the code shown, it handles source code processing, manifest management, cross-referencing, and diagram generation.

## Key Classes and Functions

### ManifestCacheEntry and ProjectManifest Classes
Located in `generators/manifest.py`, these classes handle project metadata and caching:

- **[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)** - Manages cache entries for manifest data
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)** - Represents project configuration and metadata

### Core Processing Functions

#### _create_module_chunk Method
Located in `core/chunker.py`, this method creates code chunks for module analysis:

```python
def _create_module_chunk(
    self,
    root: Node,
    source: bytes,
    language: Language,
    file_path: str,
) -> CodeChunk:
```

Creates a chunk representing a module or file overview for processing.

#### Path and Module Conversion Functions
Located in `generators/diagrams.py`:

- **_path_to_module** - Converts file paths to module names:
  ```python
  def _path_to_module(file_path: str) -> str | None:
  ```
  Takes paths like `'src/local_deepwiki/core/indexer.py'` and returns module names like `'core.indexer'`.

- **_module_to_wiki_path** - Converts module names to wiki file paths:
  ```python
  def _module_to_wiki_path(module: str, project_name: str) -> str:
  ```
  Converts module names like `'core.parser'` to wiki paths like `'src/local_deepwiki/core/parser.md'`.

#### Cross-Reference Functions
Located in `generators/source_refs.py`:

- **[build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md)** - Creates mapping between files and wiki pages
- **[generate_source_refs_section](../files/src/local_deepwiki/generators/source_refs.md)** - Generates source reference sections
- **[add_source_refs_sections](../files/src/local_deepwiki/generators/source_refs.md)** - Adds source reference sections to wiki pages
- **_relative_path**, **_format_file_entry**, **_strip_existing_source_refs** - Helper functions for reference processing

#### Module Matching
Located in `generators/see_also.py`:

- **_module_matches_file** - Checks if a module name corresponds to a file path:
  ```python
  def _module_matches_file(self, module: str, file_path: str) -> bool:
  ```

### Manifest Management Functions
Located in `generators/manifest.py`:

- **_get_manifest_mtimes** - Gets modification times for manifest files
- **_is_cache_valid** - Validates manifest cache
- **_load_manifest_cache** - Loads cached manifest data
- **_save_manifest_cache** - Saves manifest data to cache

## How Components Interact

1. **Code Processing Pipeline**: The chunker processes source files using `_create_module_chunk` to create analyzable code chunks
2. **Path Resolution**: The system converts between file paths and module names using `_path_to_module` and `_module_to_wiki_path`
3. **Cross-Referencing**: Source reference generators build mappings between source files and wiki pages, then add reference sections
4. **Module Matching**: The see-also generator uses `_module_matches_file` to create connections between related modules
5. **Manifest Caching**: Project metadata is cached and validated using the manifest management functions

## Usage Examples

### Converting File Paths to Modules
```python
# Convert a file path to module name
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Converting Modules to Wiki Paths
```python
# Convert module to wiki file path
wiki_path = _module_to_wiki_path("core.parser", "local_deepwiki")
# Returns: "src/local_deepwiki/core/parser.md"
```

### Module Matching
```python
# Check if module matches file
matches = instance._module_matches_file(
    "local_deepwiki.core.chunker",
    "src/local_deepwiki/core/chunker.py"
)
# Returns: True
```

## Dependencies

Based on the imports shown in the code:

- **Standard Library**: `json`, `re`, `pathlib.Path`, `dataclasses`, `typing`
- **TOML Processing**: `tomllib` and `tomli` (with fallback handling)
- **Internal Dependencies**: 
  - `local_deepwiki.logging` - For logging functionality
  - `local_deepwiki.models` - For [WikiPage](../files/src/local_deepwiki/models.md) and [WikiPageStatus](../files/src/local_deepwiki/models.md) classes
- **External Libraries**: Tree-sitter components (`Node`, [`Language`](../files/src/local_deepwiki/models.md)) for AST processing

The module structure includes several subpackages:
- `core/` - Core processing functionality (chunker, llm_cache, vectorstore)
- `generators/` - Documentation generation tools
- `tools/` - Utility tools
- `web/` - Web interface components

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/config.py:14-19`](../files/src/local_deepwiki/config.md)
- [`src/local_deepwiki/logging.py:19-70`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:33-53`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/models.py:11-26`](../files/src/local_deepwiki/models.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:29-223`](../files/src/local_deepwiki/watcher.md)
- `src/local_deepwiki/tools/__init__.py`
- [`src/local_deepwiki/core/chunker.py:200-597`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/core/llm_cache.py:19-357`](../files/src/local_deepwiki/core/llm_cache.md)
- [`src/local_deepwiki/core/vectorstore.py:37-395`](../files/src/local_deepwiki/core/vectorstore.md)


*Showing 10 of 43 source files.*
