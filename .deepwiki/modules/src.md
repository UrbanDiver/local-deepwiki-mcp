# Module: `src.local_deepwiki`

## Module Purpose

The `src.local_deepwiki` module is a core component for generating and managing local documentation wikis from source code. It provides functionality for parsing code, creating documentation pages, managing module references, and building project manifests. It also includes tools for integrating with LLMs and embedding providers to enhance documentation generation.

## Key Classes and Functions

### Core Components

- **CodeChunk**: Represents a chunk of code for documentation.
- **WikiPage**: Represents a documentation page.
- **WikiPageStatus**: Enum representing the status of a documentation page.
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)**: Class for managing project manifest data (e.g., from `pyproject.toml`, `setup.py`, etc.)

### Functions

- `_path_to_module(file_path: str) -> str | None`: Converts a file path to a module name.
- `_create_module_chunk(...)`: Creates a chunk for a module/file overview.
- `_relative_path(file_path: str, base_path: str) -> str`: Computes a relative path.
- `_format_file_entry(file_path: str, base_path: str) -> str`: Formats a file entry for display.
- `build_file_to_wiki_map(...)`: Builds a mapping from source files to wiki pages.
- `generate_source_refs_section(...)`: Generates a section referencing source files.
- `add_source_refs_sections(...)`: Adds source reference sections to wiki pages.
- `parse_manifest(...)`: Parses a project manifest file.
- `_parse_pyproject_toml(...)`: Parses a `pyproject.toml` file.
- `_parse_python_dep(...)`: Parses a Python dependency.
- `_parse_setup_py(...)`: Parses a `setup.py` file.
- `_parse_requirements_txt(...)`: Parses a `requirements.txt` file.
- `_parse_package_json(...)`: Parses a `package.json` file.
- `_module_matches_file(module: str, file_path: str) -> bool`: Checks if a module name refers to a file path.
- `_generate_modules_index(module_pages: list[WikiPage]) -> str`: Generates an index page for modules.

### Classes

- **AnthropicProvider**: LLM provider for Anthropic's models.
- **EmbeddingProvider**: Base class for embedding providers.
- **LLMProvider**: Base class for LLM providers.

## How Components Interact

1. The `core` module handles code parsing and chunking using ASTs.
2. The `generators` module creates documentation pages and manages references between source files and wiki pages.
3. The `manifest` module parses project metadata from various configuration files (`pyproject.toml`, `setup.py`, etc.).
4. The `providers` module integrates with external services like LLMs and embedding providers.
5. The `watcher` module may monitor changes to source files and trigger documentation updates.
6. The `server` module likely hosts the documentation web interface.
7. The `tools` module provides utility functions for documentation generation.

## Usage Examples

### Generating a Module Index

```python
from local_deepwiki.generators.wiki import WikiGenerator

generator = WikiGenerator()
module_pages = [...]  # List of WikiPage objects
index_content = generator._generate_modules_index(module_pages)
```

### Parsing a Manifest

```python
from local_deepwiki.generators.manifest import parse_manifest

manifest = parse_manifest("pyproject.toml")
```

### Using the Anthropic Provider

```python
from local_deepwiki.providers.llm.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="your-api-key")
```

## Dependencies

- `pathlib.Path`
- `typing` (for type hints)
- `dataclasses`
- `json`
- `re`
- `xml.etree.ElementTree`
- `tomllib` / `tomli`
- `anthropic` (for AnthropicProvider)
- `local_deepwiki.models`
- `local_deepwiki.core.chunker`
- `local_deepwiki.core.parser`
- `local_deepwiki.core.vectorstore`
- `local_deepwiki.tools`
- `local_deepwiki.server`
- `local_deepwiki.watcher`
- `local_deepwiki.config`
- `local_deepwiki.generators.source_refs`
- `local_deepwiki.generators.see_also`
- `local_deepwiki.generators.manifest`
- `local_deepwiki.generators.diagrams`
- `local_deepwiki.generators/wiki`
- `local_deepwiki.providers.base`
- `local_deepwiki.web`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/server.py:24-162`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:11-14`](../files/src/local_deepwiki/config.md)
- `src/local_deepwiki/models.py:10-24`
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:26-213`](../files/src/local_deepwiki/watcher.md)
- `src/local_deepwiki/tools/__init__.py`
- [`src/local_deepwiki/core/chunker.py:162-550`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/core/vectorstore.py:14-326`](../files/src/local_deepwiki/core/vectorstore.md)
- `src/local_deepwiki/core/__init__.py`
- [`src/local_deepwiki/core/parser.py:69-173`](../files/src/local_deepwiki/core/parser.md)


*Showing 10 of 35 source files.*
