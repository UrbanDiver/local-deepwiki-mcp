# src Module Documentation

## Module Purpose

The `src` module contains the core implementation of local_deepwiki, a documentation generation system that processes source code files and generates wiki-style documentation. Based on the code shown, this module handles code parsing, chunking, wiki page generation, project manifest management, and source reference tracking.

## Key Classes and Functions

### Code Chunking (chunker.py)

The chunker module contains methods for processing source code into structured chunks:

- **_create_module_chunk**: Creates a chunk representing the module/file overview from an AST root node, source bytes, language specification, and file path.

### Diagram Generation (diagrams.py)

- **_path_to_module**: Converts file paths to module names by processing path strings and extracting Python module identifiers. Returns module names like 'core.indexer' from paths like 'src/local_deepwiki/core/indexer.py', filtering out non-Python files and special files starting with double underscores.

### Wiki Module Generation (wiki_modules.py)

- **_generate_modules_index**: Generates an index page for modules by taking a list of [WikiPage](../files/src/local_deepwiki/models.md) objects and creating markdown content that serves as a navigation page for module documentation.

### Project Manifest Management (manifest.py)

The manifest module handles project metadata and caching:

**Classes:**
- **[ManifestCacheEntry](../files/src/local_deepwiki/generators/manifest.md)**: A dataclass for storing cached manifest data
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)**: A dataclass representing project configuration and metadata

**Functions:**
- **_get_manifest_mtimes**: Retrieves modification times for manifest files
- **_is_cache_valid**: Validates whether cached manifest data is still current
- **_load_manifest_cache**: Loads cached manifest information from storage
- **_save_**: Saves manifest data (function name appears truncated in context)

### Source References (source_refs.py)

The source_refs module manages linking between source files and wiki pages:

- **[build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md)**: Creates a mapping between source files and their corresponding wiki pages
- **_relative_path**: Converts absolute paths to relative paths for consistent referencing
- **_format_file_entry**: Formats file entries for display in documentation
- **[generate_source_refs_section](../files/src/local_deepwiki/generators/source_refs.md)**: Creates markdown sections that reference source files
- **_strip_existing_source_refs**: Removes existing source reference sections from content
- **[add_source_refs_sections](../files/src/local_deepwiki/generators/source_refs.md)**: Adds source reference sections to wiki pages

## How Components Interact

The components work together in a documentation generation pipeline:

1. **Code Processing**: The chunker processes source files using AST parsing, creating structured code chunks with the _create_module_chunk method
2. **Path Resolution**: The diagrams module converts file paths to module names for consistent referencing across the system
3. **Wiki Generation**: The wiki_modules generator creates index pages from processed module data
4. **Manifest Management**: The manifest system tracks project metadata and caches information for efficient rebuilds
5. **Source Linking**: The source_refs module maintains bidirectional links between source files and generated documentation

## Usage Examples

### Converting File Paths to Module Names

```python
from local_deepwiki.generators.diagrams import _path_to_module

# Convert a file path to module name
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
    WikiPage(path="modules/generators.md", title="Generators")
]

# Generate index content
index_content = _generate_modules_index(module_pages)
# Returns markdown content with module links
```

### Building Source Reference Maps

```python
from local_deepwiki.generators.source_refs import build_file_to_wiki_map

# Build mapping between source files and wiki pages
file_map = build_file_to_wiki_map(wiki_pages, base_path)
```

## Dependencies

Based on the imports shown, this module depends on:

**Standard Library:**
- `json` - JSON processing for manifest data
- `re` - Regular expression operations for text processing
- `pathlib.Path` - Path manipulation utilities
- `dataclasses` - Data structure definitions
- `typing` - Type annotations

**External Libraries:**
- `tomllib` / `tomli` - TOML file parsing for configuration

**Internal Dependencies:**
- `local_deepwiki.logging` - Logging functionality via [get_logger](../files/src/local_deepwiki/logging.md)
- `local_deepwiki.models` - Core data models including [WikiPage](../files/src/local_deepwiki/models.md) and [WikiPageStatus](../files/src/local_deepwiki/models.md)

The module structure suggests a modular design where each generator handles a specific aspect of documentation creation, with shared models and utilities providing common functionality across components.

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


*Showing 10 of 49 source files.*
