# src Module Documentation

## Module Purpose

The `src` module contains the core functionality for local_deepwiki, a documentation generation system. Based on the code shown, this module handles code analysis, documentation generation, and provides utilities for converting between different representations of code structures (file paths, module names, wiki paths).

## Key Classes and Functions

### ManifestCacheEntry Class
A dataclass that represents cached manifest information with associated metadata timestamps.

### ProjectManifest Class  
A dataclass that contains project configuration and metadata information loaded from manifest files.

### Code Analysis Functions

#### _create_module_chunk
```python
def _create_module_chunk(self, root: Node, source: bytes, language: Language, file_path: str) -> CodeChunk
```
Creates a [CodeChunk](../files/src/local_deepwiki/models.md) representing a module or file overview by analyzing the AST root node and source code.

### Path and Module Conversion Utilities

#### _path_to_module
```python
def _path_to_module(file_path: str) -> str | None
```
Converts a file path like `src/local_deepwiki/core/indexer.py` to a module name like `core.indexer`. Returns None for non-Python files or files starting with double underscores.

#### _module_to_wiki_path
```python
def _module_to_wiki_path(module: str, project_name: str) -> str
```
Converts a module name like `core.parser` to a wiki file path like `src/local_deepwiki/core/parser.md`.

#### _module_matches_file
```python
def _module_matches_file(self, module: str, file_path: str) -> bool
```
Checks if a module name corresponds to a specific file path by comparing their normalized representations.

### Documentation Generation Functions

#### build_file_to_wiki_map
Maps source files to their corresponding wiki pages.

#### generate_source_refs_section
Generates source reference sections for documentation.

#### add_source_refs_sections
Adds source reference sections to existing documentation.

### Utility Functions

#### _get_manifest_mtimes
Retrieves modification times for manifest files.

#### _is_cache_valid
Validates if cached manifest data is still current.

#### _load_manifest_cache / _save_manifest_cache
Handle loading and saving of manifest cache data.

#### _relative_path
Converts absolute paths to relative paths.

#### _format_file_entry
Formats file entries for documentation display.

#### _strip_existing_source_refs
Removes existing source reference sections from documentation.

## How Components Interact

The module follows a pipeline approach where:

1. **Manifest handling** ([ProjectManifest](../files/src/local_deepwiki/generators/manifest.md), [ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)) loads and caches project configuration
2. **Code analysis** (_create_module_chunk) parses source files into structured chunks
3. **Path conversion utilities** (_path_to_module, _module_to_wiki_path, _module_matches_file) translate between different naming conventions
4. **Documentation generation** (source_refs functions) creates cross-references and documentation sections

The conversion utilities work together to maintain consistency between file system paths, Python module names, and wiki documentation paths.

## Usage Examples

### Converting file paths to module names:
```python
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Converting module names to wiki paths:
```python
wiki_path = _module_to_wiki_path("core.parser", "local_deepwiki")
# Returns: "src/local_deepwiki/core/parser.md"
```

### Checking module-file correspondence:
```python
matches = _module_matches_file("local_deepwiki.core.chunker", "src/local_deepwiki/core/chunker.py")
# Returns: True
```

## Dependencies

Based on the imports shown, this module depends on:

- **Standard library**: `json`, `re`, `pathlib.Path`, `dataclasses`, `typing`
- **TOML parsing**: `tomllib` (with fallback to `tomli`)
- **Internal modules**: 
  - `local_deepwiki.logging` (for [get_logger](../files/src/local_deepwiki/logging.md))
  - `local_deepwiki.models` (for [WikiPage](../files/src/local_deepwiki/models.md), [WikiPageStatus](../files/src/local_deepwiki/models.md))

The module structure suggests a clean separation between core functionality (chunker), generators (diagrams, manifest, source_refs, see_also), and web components.

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
