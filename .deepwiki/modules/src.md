# Module: `src.local_deepwiki.generators`

## Module Purpose

The `generators` module contains functionality for generating documentation-related content from source code. It includes tools for creating manifest files, source reference sections, and "see also" links between modules and files. The module also provides utilities for converting file paths to module names and managing caching of manifest data.

## Key Classes and Functions

### Function: `_path_to_module`
Converts a file path to a module name.

```python
def _path_to_module(file_path: str) -> str | None:
```

**Args:**
- `file_path`: Path like `'src/local_deepwiki/core/indexer.py'`

**Returns:**
- Module name like `'core.indexer'`, or `None` if not applicable.

### Function: `_get_manifest_mtimes`
Retrieves modification times for files in a project manifest.

```python
def _get_manifest_mtimes(manifest: ProjectManifest) -> dict[str, float]:
```

**Args:**
- `manifest`: Project manifest object.

**Returns:**
- Dictionary mapping file paths to their modification times.

### Function: `_is_cache_valid`
Checks if a manifest cache entry is still valid.

```python
def _is_cache_valid(entry: ManifestCacheEntry, manifest: ProjectManifest) -> bool:
```

**Args:**
- `entry`: Cached manifest entry.
- `manifest`: Current project manifest.

**Returns:**
- `True` if the cache is valid, otherwise `False`.

### Function: `_load_manifest_cache`
Loads manifest cache from a file.

```python
def _load_manifest_cache(cache_path: Path) -> dict[str, ManifestCacheEntry]:
```

**Args:**
- `cache_path`: Path to the cache file.

**Returns:**
- Dictionary of cached manifest entries.

### Function: `_save_manifest_cache`
Saves manifest cache to a file.

```python
def _save_manifest_cache(cache_path: Path, cache: dict[str, ManifestCacheEntry]) -> None:
```

**Args:**
- `cache_path`: Path to the cache file.
- `cache`: Dictionary of manifest cache entries to save.

### Function: `build_file_to_wiki_map`
Builds a mapping from file paths to wiki pages.

```python
def build_file_to_wiki_map(wiki_pages: list[WikiPage]) -> dict[str, WikiPage]:
```

**Args:**
- `wiki_pages`: List of wiki pages.

**Returns:**
- Dictionary mapping file paths to wiki pages.

### Function: `_relative_path`
Converts an absolute path to a relative path.

```python
def _relative_path(abs_path: str, base_path: str) -> str:
```

**Args:**
- `abs_path`: Absolute file path.
- `base_path`: Base directory path.

**Returns:**
- Relative path from `base_path` to `abs_path`.

### Function: `_format_file_entry`
Formats a file entry for display in a wiki.

```python
def _format_file_entry(file_path: str, page: WikiPage) -> str:
```

**Args:**
- `file_path`: Path to the file.
- `page`: Wiki page object.

**Returns:**
- Formatted string representation of the file entry.

### Function: `generate_source_refs_section`
Generates a section for source references in a wiki page.

```python
def generate_source_refs_section(file_path: str, page: WikiPage) -> str:
```

**Args:**
- `file_path`: Path to the file.
- `page`: Wiki page object.

**Returns:**
- Formatted source references section.

### Function: `add_source_refs_sections`
Adds source reference sections to all wiki pages.

```python
def add_source_refs_sections(wiki_pages: list[WikiPage]) -> None:
```

**Args:**
- `wiki_pages`: List of wiki pages to update.

### Method: `_module_matches_file`
Checks if a module name refers to a file path.

```python
def _module_matches_file(self, module: str, file_path: str) -> bool:
```

**Args:**
- `module`: Module name like `'local_deepwiki.core.chunker'`.
- `file_path`: File path like `'src/local_deepwiki/core/chunker.py'`.

**Returns:**
- `True` if they match.

## How Components Interact

The components in this module work together to process source code files and generate documentation artifacts such as manifest files, source reference sections, and "see also" links. The `_path_to_module` function helps map file paths to module names, which is used by other functions to build relationships between files and modules. The caching mechanism (`_load_manifest_cache`, `_save_manifest_cache`) helps optimize performance by avoiding redundant processing of unchanged files. Functions like `build_file_to_wiki_map` and `add_source_refs_sections` are used to associate source code with wiki pages, enhancing documentation with cross-references.

## Usage Examples

### Convert file path to module name

```python
from local_deepwiki.generators.diagrams import _path_to_module

module_name = _path_to_module("src/local_deepwiki/core/chunker.py")
print(module_name)  # Output: "core.chunker"
```

### Load manifest cache

```python
from local_deepwiki.generators.manifest import _load_manifest_cache
from pathlib import Path

cache = _load_manifest_cache(Path("cache/manifest.json"))
```

### Add source reference sections to wiki pages

```python
from local_deepwiki.generators.source_refs import add_source_refs_sections
from local_deepwiki.models import WikiPage

pages = [WikiPage(...), WikiPage(...)]
add_source_refs_sections(pages)
```

## Dependencies

This module depends on:
- `local_deepwiki.logging`
- `local_deepwiki.models`
- `local_deepwiki.core.chunker`
- `local_deepwiki.core.vectorstore`
- `local_deepwiki.generators.diagrams`
- `local_deepwiki.generators.manifest`
- `local_deepwiki.generators.source_refs`
- `local_deepwiki.generators.see_also`
- `local_deepwiki.providers.base`
- `dataclasses`
- `json`
- `re`
- `pathlib`
- `typing`
- `tomllib`
- `tomli`

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


*Showing 10 of 36 source files.*
