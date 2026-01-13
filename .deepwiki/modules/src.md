# Module: `local_deepwiki`

## Module Purpose

The `local_deepwiki` module provides tools for generating documentation from codebases, including parsing source files, creating module overviews, managing references, and building project manifests. It supports features like code chunking, vector storage for semantic search, and integration with LLMs and embedding providers.

## Key Classes and Functions

### `local_deepwiki.generators.diagrams._path_to_module`
Converts a file path into a module name.

**Arguments:**
- `file_path` (str): Path like `'src/local_deepwiki/core/indexer.py'`

**Returns:**
- Module name like `'core.indexer'`, or `None` if not applicable.

### `local_deepwiki.core.chunker._create_module_chunk`
Creates a chunk for a module/file overview.

**Arguments:**
- `root`: AST root node.
- `source`: Source bytes.
- `language`: Programming language.
- `file_path`: Relative file path.

**Returns:**
- A `CodeChunk` object representing the module chunk.

### `local_deepwiki.generators.source_refs.build_file_to_wiki_map`
Maps file paths to wiki pages.

### `local_deepwiki.generators.source_refs._relative_path`
Converts a full path to a relative path.

### `local_deepwiki.generators.source_refs._format_file_entry`
Formats a file entry for inclusion in a source reference section.

### `local_deepwiki.generators.source_refs.generate_source_refs_section`
Generates a source reference section for a given file.

### `local_deepwiki.generators.source_refs.add_source_refs_sections`
Adds source reference sections to wiki pages.

### `local_deepwiki.generators.manifest.ProjectManifest`
Represents a project manifest with metadata and dependencies.

### `local_deepwiki.generators.manifest.parse_manifest`
Parses a project manifest from various formats (e.g., `pyproject.toml`, `setup.py`).

### `local_deepwiki.generators.manifest._parse_pyproject_toml`
Parses a `pyproject.toml` file to extract project metadata.

### `local_deepwiki.generators.manifest._parse_python_dep`
Parses a Python dependency.

### `local_deepwiki.generators.manifest._parse_setup_py`
Parses a `setup.py` file to extract dependencies.

### `local_deepwiki.generators.manifest._parse_requirements_txt`
Parses a `requirements.txt` file.

### `local_deepwiki.generators.manifest._parse_package_json`
Parses a `package.json` file.

### `local_deepwiki.generators.see_also._module_matches_file`
Checks if a module name refers to a file path.

**Arguments:**
- `module` (str): Module name like `'local_deepwiki.core.chunker'`.
- `file_path` (str): File path like `'src/local_deepwiki/core/chunker.py'`.

**Returns:**
- `True` if they match.

### `local_deepwiki.generators.wiki._generate_modules_index`
Generates an index page listing all module pages.

**Arguments:**
- `module_pages` (list[WikiPage]): List of module wiki pages.

**Returns:**
- A string containing the index page content.

### `local_deepwiki.providers.llm.anthropic.AnthropicProvider`
An LLM provider using the Anthropic API.

**Methods:**
- `__init__(self, api_key: str)`
- `generate(self, prompt: str) -> str`

## How Components Interact

The components work together as follows:

1. **Parsing and Chunking:** The `chunker` module parses source code into ASTs and creates chunks using `_create_module_chunk`. These chunks are used for semantic understanding and indexing.
2. **Manifest Parsing:** The `manifest` module parses project configuration files (`pyproject.toml`, `setup.py`, etc.) to gather metadata and dependencies.
3. **Wiki Generation:** The `wiki` generator uses `_generate_modules_index` to create an index of all modules.
4. **Source References:** The `source_refs` generator builds mappings between files and wiki pages and formats source reference sections.
5. **Diagram Generation:** The `diagrams` generator uses `_path_to_module` to convert file paths into module names for diagram purposes.
6. **LLM Integration:** The `anthropic` provider allows integration with LLMs for generating content or summaries.

## Usage Examples

### Using `local_deepwiki.generators.diagrams._path_to_module`

```python
from local_deepwiki.generators.diagrams import _path_to_module

module_name = _path_to_module("src/local_deepwiki/core/chunker.py")
# Returns: "core.chunker"
```

### Using `local_deepwiki.generators.manifest.parse_manifest`

```python
from local_deepwiki.generators.manifest import parse_manifest

manifest = parse_manifest("pyproject.toml")
# Returns: ProjectManifest object
```

### Using `local_deepwiki.generators.wiki._generate_modules_index`

```python
from local_deepwiki.generators.wiki import _generate_modules_index
from local_deepwiki.models import WikiPage

pages = [WikiPage(path="modules/chunker.md", title="Chunker")]
index = _generate_modules_index(pages)
# Returns: Markdown string with module index
```

### Using `local_deepwiki.providers.llm.anthropic.AnthropicProvider`

```python
from local_deepwiki.providers.llm.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="your-api-key")
response = provider.generate("Explain code chunking.")
# Returns: Generated text response
```

## Dependencies

- `pathlib.Path`
- `typing` (for type hints)
- `re` (for regex operations)
- `json` (for JSON parsing)
- `dataclasses`
- `tomllib` / `tomli` (for TOML parsing)
- `xml.etree.ElementTree` (for XML parsing)
- `anthropic` (for LLM provider)
- `local_deepwiki.models`
- `local_deepwiki.providers.base`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/server.py:24-162`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:11-14`](../files/src/local_deepwiki/config.md)
- `src/local_deepwiki/models.py:10-25`
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:26-213`](../files/src/local_deepwiki/watcher.md)
- `src/local_deepwiki/tools/__init__.py`
- [`src/local_deepwiki/core/chunker.py:174-562`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/core/vectorstore.py:14-326`](../files/src/local_deepwiki/core/vectorstore.md)
- `src/local_deepwiki/core/__init__.py`
- [`src/local_deepwiki/core/parser.py:72-176`](../files/src/local_deepwiki/core/parser.md)


*Showing 10 of 35 source files.*
