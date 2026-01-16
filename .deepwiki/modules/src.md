# src Module Documentation

## Module Purpose

The `src` module contains the core components for local_deepwiki, a documentation generation system. Based on the code shown, this module handles wiki generation, manifest processing, source code analysis, and reference management for creating documentation from source code.

## Key Classes and Functions

### ManifestCacheEntry Class
A data class that manages cached manifest information, including modification times and validation.

### ProjectManifest Class  
Handles project manifest data and configuration loading from TOML files.

### Core Functions

#### _path_to_module Function
Converts file paths to module names for documentation organization.

```python
def _path_to_module(file_path: str) -> str | None:
    """Convert file path to module name.
    
    Args:
        file_path: Path like 'src/local_deepwiki/core/indexer.py'
        
    Returns:
        Module name like 'core.indexer', or None if not applicable.
    """
```

#### _create_module_chunk Method
Creates code chunks for module/file overviews during documentation processing.

```python
def _create_module_chunk(
    self,
    root: Node,
    source: bytes, 
    language: Language,
    file_path: str,
) -> CodeChunk:
```

#### _generate_modules_index Function
Generates index pages for module documentation.

```python
def _generate_modules_index(module_pages: list[WikiPage]) -> str:
    """Generate index page for modules.
    
    Args:
        module_pages: List of module wiki pages.
        
    Returns:
        Markdown content for modules index.
    """
```

#### Source Reference Functions
The source_refs module provides several functions for managing file-to-wiki mappings:

- **[build_file_to_wiki_map](../files/src/local_deepwiki/generators/see_also.md)** - Creates mappings between source files and wiki pages
- **[generate_source_refs_section](../files/src/local_deepwiki/generators/source_refs.md)** - Generates reference sections in documentation  
- **[add_source_refs_sections](../files/src/local_deepwiki/generators/source_refs.md)** - Adds source reference sections to existing content

#### Manifest Management Functions
The manifest module includes functions for caching and validation:

- **_get_manifest_mtimes** - Retrieves modification times for manifest files
- **_is_cache_valid** - Validates cached manifest data
- **_load_manifest_cache** - Loads cached manifest information
- **_save_** (function name truncated in context) - Saves manifest data

## How Components Interact

The components work together in a documentation generation pipeline:

1. The **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)** class loads project configuration from TOML files
2. **_path_to_module** converts file paths to standardized module names
3. **_create_module_chunk** processes source code into documentation chunks
4. **_generate_modules_index** creates navigation indexes for the generated documentation
5. The source_refs functions manage cross-references between source files and wiki pages
6. Manifest caching functions optimize performance by tracking file modification times

## Usage Examples

### Converting File Paths to Module Names
```python
module_name = _path_to_module("src/local_deepwiki/core/indexer.py")
# Returns: "core.indexer"
```

### Generating Module Index
```python
# Assuming you have a list of WikiPage objects
wiki_pages = [page1, page2, page3]
index_content = _generate_modules_index(wiki_pages)
# Returns markdown content for the modules index
```

### Building File Mappings
```python
from local_deepwiki.generators.source_refs import build_file_to_wiki_map

# Build mapping between source files and wiki pages
file_map = build_file_to_wiki_map(wiki_pages)
```

## Dependencies

Based on the imports shown, this module depends on:

### Standard Library
- `json` - JSON processing
- `re` - Regular expressions  
- `pathlib.Path` - File path handling
- `typing.Any` - Type annotations
- `dataclasses` - Data class functionality

### External Libraries
- `tomllib` / `tomli` - TOML file parsing (with fallback support)

### Internal Dependencies
- [`local_deepwiki.logging.get_logger`](../files/src/local_deepwiki/logging.md) - Logging functionality
- [`local_deepwiki.models.WikiPage`](../files/src/local_deepwiki/models.md) - Wiki page data structures
- [`local_deepwiki.models.WikiPageStatus`](../files/src/local_deepwiki/models.md) - Page status management

The module structure suggests a well-organized codebase with clear separation between generators, core functionality, and utility modules.

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
