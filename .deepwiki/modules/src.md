# Module: local_deepwiki

## Purpose and Responsibilities

The local_deepwiki module provides a framework for generating and managing documentation for local Python projects. It supports parsing code, extracting documentation from source files, and creating structured documentation including module indexes, architecture diagrams, and manifest-based project information.

## Key Classes and Functions

### WikiGenerator

The [WikiGenerator](../files/src/local_deepwiki/generators/wiki.md) class is responsible for orchestrating the documentation generation process. It handles the parsing of source code, chunking of code into manageable sections, and generation of various documentation components including module indexes and architecture diagrams.

### CodeChunker

The [CodeChunker](../files/src/local_deepwiki/core/chunker.md) class breaks down source code into logical chunks for documentation purposes. It processes abstract syntax trees (ASTs) to identify and extract meaningful code segments, creating structured representations of code that can be used for documentation generation.

### VectorStore

The [VectorStore](../files/src/local_deepwiki/core/vectorstore.md) class manages the storage and retrieval of vector embeddings for code chunks. It provides functionality to store code representations in a vector database and perform similarity searches to [find](../files/src/local_deepwiki/generators/manifest.md) related code sections.

### CodeParser

The [CodeParser](../files/src/local_deepwiki/core/parser.md) class handles parsing of source code files into abstract syntax trees (ASTs). It identifies functions, classes, and other code constructs that are relevant for documentation generation.

### ModuleIndexer

The ModuleIndexer class creates and manages indexes of modules within a project. It tracks relationships between modules and generates navigation structures for documentation.

### WikiPage

The [WikiPage](../files/src/local_deepwiki/models.md) class represents a single documentation page. It contains the content, title, and path information for a generated documentation page.

### CodeChunk

The [CodeChunk](../files/src/local_deepwiki/models.md) class represents a segment of code that has been processed for documentation. It contains information about the source code, its location, and metadata for indexing and retrieval.

### ManifestParser

The ManifestParser class handles parsing of project manifest files (like pyproject.toml, setup.py, requirements.txt) to extract project metadata and dependencies.

### ArchitectureDiagramGenerator

The ArchitectureDiagramGenerator class creates Mermaid architecture diagrams from code chunks, visualizing the structure and relationships between different parts of the codebase.

## How Components Interact

The documentation generation process begins with the [WikiGenerator](../files/src/local_deepwiki/generators/wiki.md), which coordinates the entire workflow. It uses the [CodeParser](../files/src/local_deepwiki/core/parser.md) to parse source files into ASTs, then passes these to the [CodeChunker](../files/src/local_deepwiki/core/chunker.md) to create logical code segments. These chunks are stored in the [VectorStore](../files/src/local_deepwiki/core/vectorstore.md) for later retrieval and analysis.

The ModuleIndexer creates navigation structures that help organize the documentation, while the [WikiGenerator](../files/src/local_deepwiki/generators/wiki.md) uses this information to build module indexes and cross-references. The ArchitectureDiagramGenerator can analyze code chunks to create visual representations of the code structure.

## Usage Examples

```python
from local_deepwiki import WikiGenerator

# Initialize the generator
generator = WikiGenerator()

# Generate documentation for a project
generator.generate_docs(
    project_path=".",
    output_dir="./docs"
)
```

```python
from local_deepwiki.core.chunker import CodeChunker
from local_deepwiki.core.parser import CodeParser

# Parse a source file
parser = CodeParser()
ast = parser.parse_file("src/local_deepwiki/core/chunker.py")

# Chunk the code
chunker = CodeChunker()
chunks = chunker.chunk_file(ast, "src/local_deepwiki/core/chunker.py")
```

```python
from local_deepwiki.core.vectorstore import VectorStore

# Initialize vector store
vector_store = VectorStore()

# Add code chunks to store
vector_store.add_chunks(chunks)

# Search for related code
similar_chunks = vector_store.search("function definition", top_k=5)
```

## Dependencies

This module depends on several other components:

- `local_deepwiki.core.parser` - for parsing source code into ASTs
- `local_deepwiki.core.chunker` - for breaking code into logical chunks
- `local_deepwiki.core.vectorstore` - for storing and retrieving code embeddings
- `local_deepwiki.generators` - for generating various documentation components
- `local_deepwiki.providers` - for accessing external services like LLMs and embedding providers
- `local_deepwiki.tools` - for utility functions and tools
- `local_deepwiki.web` - for web-based components and interfaces

The module also requires standard Python libraries including `pathlib`, `typing`, and `dataclasses` for type hints and data structures.