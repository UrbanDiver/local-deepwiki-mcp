# Module Purpose

The `src` module is part of a larger project, specifically focused on generating and managing documentation for local deepwiki applications. It includes various components that handle tasks such as parsing files, creating module indices, and managing source references.

# Key Classes and Functions

## `generators/diagrams.py`
- **Function: `_path_to_module`**
  - Converts a file path to a module name.
  - **Args**: 
    - `file_path`: Path like `'src/local_deepwiki/core/indexer.py'`.
  - **Returns**: Module name like `'core.indexer'`, or `None` if not applicable.

## `core/chunker.py`
- **Method: `_create_module_chunk`**
  - Creates a chunk for the module/file overview.
  - **Args**:
    - `root`: AST root node.
    - `source`: Source bytes.
    - `language`: Programming language.
    - `file_path`: Relative file path.
  - **Returns**: A [`CodeChunk`](../files/src/local_deepwiki/models.md) object.

## `generators/wiki_modules.py`
- **Function: `_generate_modules_index`**
  - Generates an index page for modules.
  - **Args**:
    - `module_pages`: List of module wiki pages.
  - **Returns**: Markdown content for modules index.

## `generators/manifest.py`
- **Module: `manifest`**
  - Handles project manifest operations.
  - **Classes**:
    - [`ManifestCacheEntry`](../files/src/local_deepwiki/generators/manifest.md)
    - [`ProjectManifest`](../files/src/local_deepwiki/generators/manifest.md)
  - **Functions**:
    - `_get_manifest_mtimes`
    - `_is_cache_valid`
    - `_load_manifest_cache`
    - `_save_`

## `generators/__init__.py`
- **Module: `__init__`**
  - An empty initialization file for the generators package.

## `generators/source_refs.py`
- **Module: `source_refs`**
  - Manages source references in wiki pages.
  - **Functions**:
    - [`build_file_to_wiki_map`](../files/src/local_deepwiki/generators/see_also.md)
    - `_relative_path`
    - `_format_file_entry`
    - [`generate_source_refs_section`](../files/src/local_deepwiki/generators/source_refs.md)
    - `_strip_existing_source_refs`
    - [`add_source_refs_sections`](../files/src/local_deepwiki/generators/source_refs.md)

# How Components Interact

The components within the `src` module work together to generate comprehensive documentation for local deepwiki applications. For instance, the `generators/diagrams.py` and `core/chunker.py` modules handle parsing files and creating module chunks based on their structure. The `generators/wiki_modules.py` module then uses these chunks to generate an index page for all modules.

The `generators/manifest.py` module manages project manifest operations, ensuring that the documentation is up-to-date by checking modification times of relevant files. The `source_refs.py` module handles source references within wiki pages, allowing for seamless integration of code snippets and their corresponding documentation.

# Usage Examples

## Example: Generating a Module Index
```python
from local_deepwiki.generators import _generate_modules_index
from local_deepwiki.models import WikiPage

module_pages = [
    WikiPage(path="modules/core/indexer.md", content="# Indexer"),
    WikiPage(path="modules/core/chunker.md", content="# Chunker")
]

index_content = _generate_modules_index(module_pages)
print(index_content)
```

## Example: Creating a Module Chunk
```python
from local_deepwiki.core import _create_module_chunk
from ast import parse

source_code = "def example_function(): pass"
language = Language.PYTHON
file_path = "src/local_deepwiki/core/example.py"

root = parse(source_code)
chunk = _create_module_chunk(root, source_code.encode(), language, file_path)
print(chunk)
```

# Dependencies

The `src` module depends on several other modules and libraries:
- **Internal Modules**:
  - `local_deepwiki.logging`
  - `local_deepwiki.models`
- **External Libraries**:
  - `json`
  - `re`
  - `dataclasses`
  - `pathlib`
  - `tomli`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/logging.py:18-72`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:31-222`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/models.py:11-26`](../files/src/local_deepwiki/models.md)
- [`src/local_deepwiki/config.py:14-19`](../files/src/local_deepwiki/config.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/handlers.py:40-70`](../files/src/local_deepwiki/handlers.md)
- [`src/local_deepwiki/watcher.py:35-235`](../files/src/local_deepwiki/watcher.md)
- [`src/local_deepwiki/core/chunker.py:498-906`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/validation.py:22-42`](../files/src/local_deepwiki/validation.md)
- `src/local_deepwiki/tools/__init__.py`


*Showing 10 of 54 source files.*
