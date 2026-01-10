# Local Deep Wiki
=================

The `src` module is the core of the Local Deep Wiki project, providing tools for generating documentation from code.

## Module Purpose
---------------

The primary purpose of this module is to provide a set of generators and parsers that can extract information from code and generate documentation in various formats. It also includes providers for different programming languages and tools.

## Key Classes/Functions
----------------------

### `ChunkType` (models.py)

*   A class that defines the types of code chunks.
*   Used to categorize code into different types such as functions, classes, methods, modules, imports, comments, and others.

### `_create_module_chunk` (core/chunker.py)

*   A method that creates a chunk for the module/file overview.
*   Takes in an AST root node, source bytes, programming language, and file path as arguments.
*   Returns a `CodeChunk` object containing information about the module or file.

### `generate_architecture_diagram` (generators/diagrams.py)

*   A function that generates a Mermaid architecture diagram from code chunks.
*   Takes in a list of code chunks as an argument and returns a Mermaid diagram string.

### `_generate_modules_index` (generators/wiki.py)

*   A method that generates index pages for modules.
*   Takes in a list of module pages as an argument and returns a string containing the index page content.

### `EmbeddingProvider`, `LLMProvider` (providers/base.py, providers/llm/anthropic.py, providers/llm/ollama.py)

*   Base classes for embedding and language model providers.
*   Used to provide interfaces for different providers.

## Usage Examples
----------------

### Generating an Architecture Diagram

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram

# Load code chunks
chunks = [CodeChunk(file_path="path/to/module.py", source=b"code"), CodeChunk(file_path="path/to/class.py", source=b"class_code")]

# Generate architecture diagram
diagram = generate_architecture_diagram(chunks)

# Render Mermaid diagram
print(diagram)
```

### Generating Index Page for Modules

```python
from local_deepwiki.generators/wiki import _generate_modules_index

# Load module pages
module_pages = [WikiPage(path="modules/module1.py"), WikiPage(path="modules/module2.py")]

# Generate index page content
index_page_content = _generate_modules_index(module_pages)

# Print index page content
print(index_page_content)
```

## Dependencies
--------------

This module depends on the following modules:

*   `models`: Provides the `ChunkType` class.
*   `core/chunker.py`: Provides the `_create_module_chunk` method.
*   `generators/diagrams.py`: Provides the `generate_architecture_diagram` function.
*   `generators/wiki.py`: Provides the `_generate_modules_index` method.
*   `providers/base.py`, `providers/llm/anthropic.py`, `providers/llm/ollama.py`: Provide classes for embedding and language model providers.

Note: The dependencies are not exhaustive, as this module may depend on other modules that are not listed here.