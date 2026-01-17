# Module: `src.local_deepwiki.generators`

## Module Purpose

This module contains functionality for generating documentation artifacts from source code, such as wiki pages, module indexes, and source reference sections. It provides tools to process code files and produce structured documentation in Markdown format.

## Key Classes and Functions

### Function: `_path_to_module`

```python
def _path_to_module(file_path: str) -> str | None:
```

Converts a file path to a module name.

- **Args**:
  - `file_path`: Path like `'src/local_deepwiki/core/indexer.py'`
- **Returns**:
  - Module name like `'core.indexer'`, or `None` if not applicable.

### Function: `_create_module_chunk`

```python
def _create_module_chunk(
        self,
        root: Node,
        source: bytes,
        language: Language,
        file_path: str,
    ) -> CodeChunk:
```

Creates a chunk for the module/file overview.

- **Args**:
  - `root`: AST root node.
  - `source`: Source bytes.
  - `language`: Programming language.
  - `file_path`: Relative file path.
- **Returns**:
  - A [`CodeChunk`](../files/src/local_deepwiki/models.md) object representing the module overview.

### Function: `_generate_modules_index`

```python
def _generate_modules_index(module_pages: list[WikiPage]) -> str:
```

Generates an index page for modules.

- **Args**:
  - `module_pages`: List of module wiki pages.
- **Returns**:
  - Markdown content for modules index.

### Module: `manifest`

#### Classes

- **[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)**
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)**

#### Functions

- `_get_manifest_mtimes`
- `_is_cache_valid`
- `_load_manifest_cache`
- `_save_manifest_cache`

### Module: `source_refs`

#### Functions

- [`build_file_to_wiki_map`](../files/src/local_deepwiki/generators/see_also.md)
- `_relative_path`
- `_format_file_entry`
- [`generate_source_refs_section`](../files/src/local_deepwiki/generators/source_refs.md)
- `_strip_existing_source_refs`
- [`add_source_refs_sections`](../files/src/local_deepwiki/generators/source_refs.md)

## How Components Interact

The components in this module work together to process source code and generate documentation artifacts. The `_path_to_module` function helps resolve file paths to module names, which are used in other parts of the documentation generation pipeline. The `_create_module_chunk` function handles AST parsing and chunk creation for individual modules. The `_generate_modules_index` function compiles a list of module pages into a single index page. The `manifest` module provides caching and manifest handling for project metadata. The `source_refs` module handles mapping source files to wiki pages and generating source reference sections in documentation.

## Usage Examples

### Generate a Module Index

```python
from local_deepwiki.generators.wiki_modules import _generate_modules_index
from local_deepwiki.models import WikiPage

pages = [WikiPage(path="module1.md"), WikiPage(path="module2.md")]
index_content = _generate_modules_index(pages)
```

### Create a Module Chunk

```python
from local_deepwiki.core.chunker import _create_module_chunk
from tree_sitter import Language, Node

chunk = _create_module_chunk(
    root=node,
    source=b"def hello(): pass",
    language=Language,
    file_path="example.py"
)
```

### Process Source References

```python
from local_deepwiki.generators.source_refs import add_source_refs_sections

# Assuming `wiki_page` is a WikiPage object
add_source_refs_sections(wiki_page)
```

## Dependencies

- `local_deepwiki.logging`
- `local_deepwiki.models`
- `tree_sitter`
- `pathlib.Path`
- `dataclasses`
- `json`
- `re`
- `tomllib`
- `tomli`

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


*Showing 10 of 54 source files.*
