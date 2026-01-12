# `src` Module Documentation

## Module Purpose and Responsibilities

The `src` module is a core component of the Local DeepWiki system, responsible for processing, analyzing, and generating documentation from source code. It provides tools for parsing code into structured chunks, creating vector representations for semantic search, and generating documentation artifacts such as wikis, diagrams, and cross-links.

This module supports both local development workflows and integration with large language models (LLMs) for intelligent code documentation generation.

---

## Key Classes and Functions

### `WikiGenerator`
Handles the generation of a structured wiki from source code files. It manages:
- Parsing files into chunks
- Generating module-level documentation
- Creating cross-links between related code elements
- Producing Mermaid architecture diagrams

```python
from local_deepwiki.generators.wiki import WikiGenerator

generator = WikiGenerator()
```

### `VectorStore`
Manages vector embeddings of code chunks for semantic search and retrieval. It supports:
- Storing and retrieving code vectors
- Searching similar code chunks using embeddings

```python
from local_deepwiki.core.vectorstore import VectorStore

vector_store = VectorStore()
```

### `CodeChunker`
Breaks down source code into logical chunks based on AST structure. It supports:
- Creating file-level overview chunks
- Chunking code by function, class, or other AST nodes

```python
from local_deepwiki.core.chunker import CodeChunker

chunker = CodeChunker()
```

### `CodeParser`
Parses source code into an Abstract Syntax Tree (AST) for semantic analysis.

```python
from local_deepwiki.core.parser import CodeParser

parser = CodeParser()
```

### `EmbeddingProvider`
Interface for providing vector embeddings for code. Used by [`VectorStore`](../files/src/local_deepwiki/core/vectorstore.md).

```python
from local_deepwiki.providers.base import EmbeddingProvider
```

### `LLMProvider`
Interface for interacting with large language models to generate natural language documentation or summaries.

```python
from local_deepwiki.providers.base import LLMProvider
```

### `generate_architecture_diagram`
Generates a Mermaid diagram visualizing the architecture of code modules.

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram
```

---

## How Components Interact

The `src` module works through a series of interconnected steps:

1. **Parsing**: [`CodeParser`](../files/src/local_deepwiki/core/parser.md) takes source files and creates ASTs.
2. **Chunking**: [`CodeChunker`](../files/src/local_deepwiki/core/chunker.md) breaks ASTs into logical chunks.
3. **Vectorization**: [`VectorStore`](../files/src/local_deepwiki/core/vectorstore.md) creates embeddings for each chunk.
4. **Documentation Generation**:
   - [`WikiGenerator`](../files/src/local_deepwiki/generators/wiki.md) uses chunks to build documentation pages.
   - `generate_architecture_diagram` visualizes module relationships.
5. **Cross-linking**: [`CrossLinker`](../files/src/local_deepwiki/generators/crosslinks.md) adds links between related documentation pages.

These components work together with external providers like `LLMProvider` and `EmbeddingProvider` to support advanced features like intelligent search and LLM-powered summarization.

---

## Usage Examples

### Index a Repository and Generate Wiki

```python
import asyncio
from pathlib import Path
from local_deepwiki.core.indexer import RepositoryIndexer

async def main():
    repo = Path("/path/to/repo")
    indexer = RepositoryIndexer(repo)

    # Index and generate wiki
    status = await indexer.index(full_rebuild=True)
    print(f"Indexed {status.total_files} files")

asyncio.run(main())
```

### Search the Codebase

```python
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.providers.embeddings import get_embedding_provider

embedding_provider = get_embedding_provider()
vector_store = VectorStore(wiki_path, embedding_provider)

# Semantic search
results = await vector_store.search("authentication logic", limit=5)
for result in results:
    print(f"{result.chunk.file_path}: {result.chunk.name}")
```

### Generate Architecture Diagram

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram

chunks = [...]  # List of CodeChunk objects
diagram = generate_architecture_diagram(chunks)
print(diagram)  # Mermaid diagram string
```

---

## Dependencies

This module depends on:

- `pathlib` – For path manipulation.
- `typing` – For type hints.
- `local_deepwiki.providers.base` – For embedding and LLM provider interfaces.
- `local_deepwiki.core.parser` – For AST parsing.
- `local_deepwiki.core.chunker` – For breaking code into chunks.
- `local_deepwiki.generators.wiki` – For wiki generation.
- `local_deepwiki.generators.diagrams` – For Mermaid diagram generation.

It also integrates with external libraries like:
- `anthropic` – For Anthropic LLM support.
- `lancedb` – For vector store implementation.
- `tree-sitter` – For code parsing (via [`CodeParser`](../files/src/local_deepwiki/core/parser.md)).