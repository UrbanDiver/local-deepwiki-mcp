# Module: `src.local_deepwiki.generators`

## Module Purpose

The `src.local_deepwiki.generators` module is responsible for generating various documentation components from source code. It includes functionality for creating wiki pages, managing source references, generating architecture diagrams, and handling manifest files for project metadata.

## Key Classes and Functions

### `src.local_deepwiki.generators.source_refs`

#### Functions
- `build_file_to_wiki_map`: Builds a mapping between source files and wiki pages.
- `_relative_path`: Converts an absolute path to a relative path.
- `_format_file_entry`: Formats a file entry for display.
- `generate_source_refs_section`: Generates a section of source references.
- `add_source_refs_sections`: Adds source references sections to wiki pages.

### `src.local_deepwiki.generators.manifest`

#### Classes
- `ProjectManifest`: Represents a project's manifest file containing metadata.

#### Functions
- `parse_manifest`: Parses a manifest file (e.g., pyproject.toml) to extract project metadata.
- `_parse_pyproject_toml`: Parses a pyproject.toml file.
- `_parse_python_dep`: Parses a Python dependency.
- `_parse_setup_py`: Parses a setup.py file.
- `_parse_requirements_txt`: Parses a requirements.txt file.
- `_parse_package_json`: Parses a package.json file.
- `_parse_xml_manifest`: Parses an XML manifest file.

### `src.local_deepwiki.generators.see_also`

#### Methods
- `_module_matches_file`: Checks if a module name refers to a file path.

### `src.local_deepwiki.generators.diagrams`

#### Functions
- `generate_architecture_diagram`: Generates a Mermaid architecture diagram from code chunks.

### `src.local_deepwiki.generators/wiki.py`

#### Functions
- `_path_to_module`: Converts a file path to a module name.

### `src.local_deepwiki.core.chunker`

#### Methods
- `_create_module_chunk`: Creates a chunk for the module/file overview.

## How Components Interact

The components in this module work together to process source code and generate documentation artifacts:

1. The `manifest` module parses project metadata from various configuration files (pyproject.toml, setup.py, requirements.txt, etc.) and stores it in a `ProjectManifest` object.
2. The `source_refs` module maps source files to wiki pages and generates reference sections.
3. The `see_also` module helps identify relationships between modules and files.
4. The `diagrams` module generates architecture diagrams from code chunks.
5. The `wiki.py` module handles path-to-module name conversions.
6. The `chunker` module creates code chunks for documentation.

These components are typically used in a pipeline where manifest data is parsed first, followed by source reference generation, then diagram creation, and finally wiki page generation.

## Usage Examples

### Parsing a Manifest File

```python
from local_deepwiki.generators.manifest import parse_manifest

manifest = parse_manifest("pyproject.toml")
print(manifest.name)
```

### Generating Source References

```python
from local_deepwiki.generators.source_refs import add_source_refs_sections

# Assuming you have a WikiPage object
add_source_refs_sections(wiki_page)
```

### Generating an Architecture Diagram

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram
from local_deepwiki.models import CodeChunk

chunks = [CodeChunk(...)]  # List of code chunks
diagram = generate_architecture_diagram(chunks)
print(diagram)
```

## Dependencies

This module depends on:
- `pathlib` (standard library)
- `re` (standard library)
- `json` (standard library)
- `dataclasses` (standard library)
- `tomllib` or `tomli` (for TOML parsing)
- `xml.etree.ElementTree` (standard library)
- `local_deepwiki.models` (for `WikiPage`, `WikiPageStatus`, `CodeChunk`)
- `local_deepwiki.core.chunker` (for `CodeChunk`)
- `local_deepwiki.generators` (for other generator functions)