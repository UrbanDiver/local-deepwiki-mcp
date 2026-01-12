# Module: `local_deepwiki`

## Module Purpose

The `local_deepwiki` module is a Python package designed to generate documentation from source code, particularly for Python projects. It supports features such as parsing code, generating wiki pages, managing source references, and creating diagrams. The module is structured into core components for code processing, documentation generation, and integration with external providers like LLMs and embeddings.

## Key Classes and Functions

### Core Components

- **CodeChunk**: Represents a chunk of code, likely used for processing and indexing code files.
- **WikiPage**: Represents a single page in the generated wiki, containing metadata like title, path, and content.
- **WikiPageStatus**: Enum or class representing the status of a wiki page (e.g., draft, published).
- **[ProjectManifest](../files/src/local_deepwiki/generators/manifest.md)**: Represents a project manifest, used for parsing configuration files like `pyproject.toml`, `setup.py`, `requirements.txt`, etc.

### Functions

#### `src/local_deepwiki/generators/diagrams.py`

- `_path_to_module(file_path: str) -> str | None`
  - Converts a file path to a module name.
  - Example: `_path_to_module('src/local_deepwiki/core/indexer.py')` returns `'core.indexer'`.

#### `src/local_deepwiki/core/chunker.py`

- `_create_module_chunk(self, root: Node, source: bytes, language: Language, file_path: str) -> CodeChunk`
  - Creates a chunk for a module or file overview.

#### `src/local_deepwiki/generators/see_also.py`

- `_module_matches_file(module: str, file_path: str) -> bool`
  - Checks if a module name refers to a file path.

#### `src/local_deepwiki/generators/wiki.py`

- `_generate_modules_index(self, module_pages: list[WikiPage]) -> str`
  - Generates an index page listing all modules.

#### `src/local_deepwiki/generators/manifest.py`

- `parse_manifest(file_path: Path) -> ProjectManifest`
  - Parses a manifest file (e.g., `pyproject.toml`) into a structured [`ProjectManifest`](../files/src/local_deepwiki/generators/manifest.md).
- `_parse_pyproject_toml(file_path: Path) -> dict[str, Any]`
  - Parses `pyproject.toml` into a dictionary.
- `_parse_python_dep(dep: str) -> dict[str, str]`
  - Parses a Python dependency string into a dictionary.
- `_parse_setup_py(file_path: Path) -> dict[str, Any]`
  - Parses `setup.py` into a dictionary.
- `_parse_requirements_txt(file_path: Path) -> list[dict[str, str]]`
  - Parses `requirements.txt` into a list of dependencies.
- `_parse_package_json(file_path: Path) -> dict[str, Any]`
  - Parses `package.json` into a dictionary.
- `_parse_xml(file_path: Path) -> dict[str, Any]`
  - Parses XML files (used for parsing `pom.xml` or similar).

#### `src/local_deepwiki/generators/source_refs.py`

- `build_file_to_wiki_map(file_paths: list[Path]) -> dict[Path, str]`
  - Builds a mapping from file paths to wiki page names.
- `_relative_path(base: Path, path: Path) -> Path`
  - Computes a relative path from a base path.
- `_format_file_entry(file_path: Path, page_name: str) -> str`
  - Formats a file entry for inclusion in a source reference section.
- `generate_source_refs_section(file_path: Path, wiki_page: WikiPage) -> str`
  - Generates a section listing source references for a file.
- `add_source_refs_sections(wiki_pages: list[WikiPage]) -> None`
  - Adds source reference sections to wiki pages.

### Providers

#### `src/local_deepwiki/providers/llm/anthropic.py`

- **AnthropicProvider**: A class that implements the `LLMProvider` interface for the Anthropic API.

## How Components Interact

1. The [`ProjectManifest`](../files/src/local_deepwiki/generators/manifest.md) class parses project configuration files to extract dependencies and metadata.
2. The `CodeChunk` and `_create_module_chunk` function are used to process code files and create structured chunks for documentation.
3. The `WikiPage` and `WikiPageStatus` are used to represent and manage documentation pages.
4. The `source_refs` module links code files to wiki pages and generates reference sections.
5. The `diagrams` module helps in mapping file paths to module names, which is useful for generating diagrams or cross-references.
6. The `see_also` module ensures that module names match file paths, improving navigation.
7. The `wiki` module generates an index page listing all modules.
8. The `AnthropicProvider` integrates with LLMs for generating documentation content.

## Usage Examples

### Parsing a Manifest File

```python
from local_deepwiki.generators.manifest import parse_manifest
from pathlib import Path

manifest = parse_manifest(Path("pyproject.toml"))
```

### Generating a Source Reference Section

```python
from local_deepwiki.generators.source_refs import generate_source_refs_section
from local_deepwiki.models import WikiPage

wiki_page = WikiPage(title="Example", path="example.md", content="...")
section = generate_source_refs_section(Path("src/example.py"), wiki_page)
```

### Generating a Module Index

```python
from local_deepwiki.generators.wiki import _generate_modules_index
from local_deepwiki.models import WikiPage

pages = [WikiPage(title="Chunker", path="core/chunker.md", content="...")]
index = _generate_modules_index(pages)
```

## Dependencies

- `pathlib`
- `typing`
- `re`
- `json`
- `dataclasses`
- `xml.etree.ElementTree`
- `tomllib` or `tomli`
- `anthropic` (for `AnthropicProvider`)
- `local_deepwiki.models`
- `local_deepwiki.providers.base`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/server.py:24-162`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/config.py:11-14`](../files/src/local_deepwiki/config.md)
- `src/local_deepwiki/models.py:10-21`
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/watcher.py:26-213`](../files/src/local_deepwiki/watcher.md)
- `src/local_deepwiki/tools/__init__.py`
- [`src/local_deepwiki/core/chunker.py:121-509`](../files/src/local_deepwiki/core/chunker.md)
- [`src/local_deepwiki/core/vectorstore.py:14-326`](../files/src/local_deepwiki/core/vectorstore.md)
- `src/local_deepwiki/core/__init__.py`
- [`src/local_deepwiki/core/parser.py:56-156`](../files/src/local_deepwiki/core/parser.md)


*Showing 10 of 35 source files.*
