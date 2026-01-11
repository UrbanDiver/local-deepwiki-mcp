# Module: `src.local_deepwiki`

## Purpose and Responsibilities

The `src.local_deepwiki` module is a core component for generating and managing local documentation for codebases. It provides tools to parse source code, extract semantic information, and generate structured documentation in various formats such as wikis, diagrams, and cross-referenced pages.

This module supports:
- Parsing Python files into Abstract Syntax Tree (AST) nodes.
- Chunking code into semantic units for indexing and embedding.
- Generating Mermaid architecture diagrams from code chunks.
- Creating cross-linked wiki documentation with module-level and file-level organization.
- Integrating with embedding and language model providers for advanced documentation generation.

## Key Classes and Functions

### `CodeChunker` class
Handles breaking down source code into semantic chunks for indexing and embedding. It uses AST parsing to identify code structures and generates `CodeChunk` objects that represent logical units of code.

### `CodeParser` class
Responsible for parsing source code files into AST nodes using Tree-sitter. It supports multiple programming languages and is used by the `CodeChunker` to extract meaningful code segments.

### `VectorStore` class
Manages storage and retrieval of code embeddings. It stores semantic representations of code chunks and allows for similarity search to find related code sections.

### `WikiGenerator` class
Generates structured wiki documentation from code chunks. It creates index pages, module documentation, and cross-links between related code elements.

### `CodeChunk` class
Represents a semantic unit of code, including metadata such as file path, source code, and language. It's used throughout the documentation pipeline to organize and process code.

### `generate_architecture_diagram` function
Takes a list of `CodeChunk` objects and generates a Mermaid architecture diagram showing relationships between modules and files.

### `_path_to_module` function
Converts a file path to a Python module name (e.g., `src/local_deepwiki/core/indexer.py` → `core.indexer`).

### `_module_matches_file` function
Checks whether a module name refers to a specific file path.

## How Components Interact

The workflow starts with `CodeParser` parsing source files into AST nodes. These are then processed by `CodeChunker` to create `CodeChunk` objects. The chunks are stored in a `VectorStore` for semantic search capabilities. `WikiGenerator` uses these chunks to build wiki documentation with cross-links and index pages. The `generate_architecture_diagram` function visualizes module relationships based on the chunks.

The `WikiGenerator` interacts with `CrossLinker` to resolve relative paths between documentation pages and with `VectorStore` to find related code chunks for cross-referencing.

## Usage Examples

### Generating a Mermaid Diagram

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram
from local_deepwiki.models import CodeChunk

chunks = [CodeChunk(...)]  # List of code chunks
diagram = generate_architecture_diagram(chunks)
print(diagram)
```

### Creating a Wiki Page

```python
from local_deepwiki.generators.wiki import WikiGenerator
from local_deepwiki.models import CodeChunk

generator = WikiGenerator()
chunks = [CodeChunk(...)]
wiki_page = generator.generate_module_page(chunks)
```

### Parsing a File

```python
from local_deepwiki.core.parser import CodeParser

parser = CodeParser()
ast_root = parser.parse_file("src/local_deepwiki/core/indexer.py")
```

## Dependencies

This module depends on:
- `tree_sitter` for AST parsing
- `pathlib` for path manipulation
- `local_deepwiki.core.chunker` for chunking logic
- `local_deepwiki.core.parser` for parsing logic
- `local_deepwiki.models` for data models
- `local_deepwiki.generators.crosslinks` for cross-linking
- `local_deepwiki.generators.wiki` for wiki generation
- `local_deepwiki.providers` for embedding and LLM providers

It also integrates with:
- `local_deepwiki.core.vectorstore` for semantic search
- `local_deepwiki.generators.diagrams` for diagram generation
- `local_deepwiki.generators.see_also` for related content discovery