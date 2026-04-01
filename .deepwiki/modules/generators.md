# generators Module

## Module Purpose

The `generators` module provides core functionality for generating various types of documentation and analysis data for a codebase. It includes components for:

- Cross-linking between documented entities
- Analysis and metrics generation (complexity, call graphs, stale detection)
- Wiki page generation and content processing
- Repository indexing and manifest management
- Changelog and search utilities

The module serves as the foundation for generating comprehensive documentation and analysis reports that power the Local DeepWiki MCP server's capabilities.

## Key Classes and Functions

### EntityInfo
Information about a documented entity.
- **Attributes**:
  - `name`: The entity name (e.g., "[WikiGenerator](../files/src/local_deepwiki/generators/wiki/generator.md)")
  - `entity_type`: The type of entity (class, function, etc.)
  - `wiki_path`: Path to the wiki page documenting this entity
  - `file_path`: Path to the source file containing this entity
  - `parent_name`: Parent entity name (e.g., class name for methods)

### EntityRegistry
Manages a registry of documented entities and their cross-linking information.
- **Methods**:
  - `__init__()`: Initialize an empty entity registry
  - `register_entity()`: Register a documented entity
  - `register_from_chunks()`: Register entities from a list of code chunks
  - `get_entity()`: Get entity info by name
  - `get_entity_by_alias()`: Get entity info by alias (spaced name)
  - `get_all_aliases()`: Get all registered aliases
  - `get_all_entities()`: Get all registered entities
  - `get_page_entities()`: Get all entities defined in a specific wiki page
  - `to_dict()`: Serialize registry to a JSON-compatible dict
  - `from_dict()`: Deserialize registry from a dict
  - `save()`: Persist registry to a JSON file
  - `load()`: Load registry from a JSON file

### CrossLinker
Adds cross-links between documented entities in wiki pages.
- **Methods**:
  - `__init__()`: Initialize the cross-linker with an entity registry
  - `add_links()`: Add cross-links to a wiki page
  - `_process_content()`: Process content to add cross-links
  - `_split_by_code_blocks()`: Split content into code and non-code sections
  - `_add_links_to_text()`: Add links to a text section using single-pass matching

### camel_to_spaced
Converts CamelCase names to spaced names for alias generation.

### build_entity_registry_from_store
Builds an entity registry from a store of chunks.

### add_cross_links
Adds cross-links to a wiki page using the [CrossLinker](../files/src/local_deepwiki/generators/crosslinks.md).

### CallGraphExtractor
Extracts call graph information from code files.

### compute_complexity_metrics
Computes complexity metrics for code files.

### categorize_file_layer
Categorizes files into different architectural layers.

### StaleReport
Reports on stale documentation in the repository.

### CommitInfo
Information about a git commit for changelog generation.

### FileContext
Context information for a file used in documentation generation.

### _load_gitignored_paths
Loads paths that should be ignored during indexing.

### LazyPageGenerator
Generates wiki pages lazily to improve performance.

### _sort_key
Sorting key function for text processing.

### ManifestCacheEntry
Entry in the manifest cache for storing metadata.

### _parse_pyproject_toml
Parses pyproject.toml files for project manifest data.

### DrainStatus
Tracks status of data draining operations.

### PhaseStats
Tracks statistics for different processing phases.

### extract_headings
Extracts headings from markdown content.

### FileRelationships
Represents relationships between files in the codebase.

### build_file_to_wiki_map
Builds a mapping from source files to wiki pages.

### TocEntry
Table of contents entry for documentation structure.

## How Components Interact

The `generators` module components work together in a layered fashion:

1. **Entity Registration**: The [`EntityRegistry`](../files/src/local_deepwiki/generators/crosslinks.md) collects information about documented entities (classes, functions) from code chunks during the indexing process.

2. **Cross-linking**: The [`CrossLinker`](../files/src/local_deepwiki/generators/crosslinks.md) uses the [`EntityRegistry`](../files/src/local_deepwiki/generators/crosslinks.md) to [find](../files/src/local_deepwiki/generators/manifest_parsers.md) and add links between related entities in wiki content, ensuring that references to classes, functions, and other documented items are properly linked.

3. **Analysis Generation**: Various analysis components (call graph extraction, complexity metrics, stale detection) generate additional metadata that can be included in documentation or used for quality checks.

4. **[Wiki Page](../files/src/local_deepwiki/export/streaming.md) Processing**: The [`CrossLinker`](../files/src/local_deepwiki/generators/crosslinks.md) integrates with wiki page generation to ensure that cross-references are properly maintained throughout the documentation.

5. **Data Flow**: Information flows from source code parsing through chunk extraction, entity registration, and finally to wiki generation where cross-links are applied.

## Usage Examples

### Creating and Using an Entity Registry```python
from local_deepwiki.generators.crosslinks import EntityRegistry, EntityInfo, ChunkType

# Create a registry
registry = EntityRegistry()

# Register entities
registry.register_entity(
    name="WikiGenerator",
    entity_type=ChunkType.CLASS,
    wiki_path="wiki/generator.md",
    file_path="src/wiki/generator.py"
)

registry.register_entity(
    name="generate_wiki",
    entity_type=ChunkType.FUNCTION,
    wiki_path="wiki/generator.md",
    file_path="src/wiki/generator.py",
    parent_name="WikiGenerator"
)

# Save the registry
registry.save(Path(".deepwiki/registry.json"))

# Load the registry
loaded_registry = EntityRegistry.load(Path(".deepwiki/registry.json"))
```
### Adding Cross-links to Wiki Content```python
from local_deepwiki.generators.crosslinks import CrossLinker, EntityRegistry

# Create cross-linker with registry
registry = EntityRegistry.load(Path(".deepwiki/registry.json"))
cross_linker = CrossLinker(registry)

# Process a wiki page
page_content = """
The `WikiGenerator` class handles documentation generation.
It uses the `generate_wiki` function to create content.
"""

wiki_page = WikiPage(
    path="wiki/generator.md",
    title="Wiki Generator",
    content=page_content
)

# Add cross-links
linked_page = cross_linker.add_links(wiki_page)
```
### Generating Analysis Reports```python
from local_deepwiki.generators.analysis.callgraph import CallGraphExtractor
from local_deepwiki.generators.analysis.complexity import compute_complexity_metrics
from local_deepwiki.generators.analysis.stale_detection import StaleReport

# Extract call graph
call_graph = CallGraphExtractor.extract_from_file("src/core/parser.py")

# Compute complexity metrics
complexity = compute_complexity_metrics("src/core/parser.py")

# Detect stale documentation
stale_report = StaleReport.detect_stale_docs()
```
## Dependencies

This module depends on:
- `local_deepwiki.generators.wiki.utils` - For wiki path utilities
- `local_deepwiki.models` - For [`ChunkType`](../files/src/local_deepwiki/models/foundation.md), [`CodeChunk`](../files/src/local_deepwiki/models/chunks.md), and [`WikiPage`](../files/src/local_deepwiki/export/streaming.md) models
- `json` - Standard library for JSON serialization
- `re` - Standard library for regular expressions
- `collections.abc` - Standard library for abstract base classes
- `dataclasses` - Standard library for data class definitions
- `pathlib` - Standard library for path manipulation
- `typing` - Standard library for type hints

The module also imports components from the `local_deepwiki.generators` package itself, including various analysis and utility modules.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/crosslinks.py:24-31`](../files/src/local_deepwiki/generators/crosslinks.md)
- [`src/local_deepwiki/generators/toc.py:12-29`](../files/src/local_deepwiki/generators/toc.md)
- [`src/local_deepwiki/generators/llms_txt.py:23-41`](../files/src/local_deepwiki/generators/llms_txt.md)
- `src/local_deepwiki/generators/__init__.py`
- [`src/local_deepwiki/generators/manifest.py:54-73`](../files/src/local_deepwiki/generators/manifest.md)
- [`src/local_deepwiki/generators/dir_tree.py:12-55`](../files/src/local_deepwiki/generators/dir_tree.md)
- [`src/local_deepwiki/generators/progress_tracker.py:35-55`](../files/src/local_deepwiki/generators/progress_tracker.md)
- [`src/local_deepwiki/generators/lazy_generator.py:63-592`](../files/src/local_deepwiki/generators/lazy_generator.md)
- [`src/local_deepwiki/generators/context_builder.py:31-42`](../files/src/local_deepwiki/generators/context_builder.md)
- [`src/local_deepwiki/generators/manifest_parsers.py:18-83`](../files/src/local_deepwiki/generators/manifest_parsers.md)


*Showing 10 of 59 source files.*
