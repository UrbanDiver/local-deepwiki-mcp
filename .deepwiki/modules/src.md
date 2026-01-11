# `src.local_deepwiki` Module Documentation

## Overview

The `src.local_deepwiki` module is a Python-based documentation generator for codebases. It provides tools to parse, analyze, and generate structured documentation from source code, including code chunks, diagrams, and wiki-style documentation. It supports multiple LLMs and embedding providers, and integrates with tools for chunking, parsing, and indexing code.

## Module Structure

```
src/
├── local_deepwiki/
│   ├── __init__.py
│   ├── server.py
│   ├── config.py
│   ├── models.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── chunker.py
│   │   ├── parser.py
│   │   ├── vectorstore.py
│   │   └── indexer.py
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── diagrams.py
│   │   └── wiki.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── anthropic.py
│   │   │   └── ollama.py
│   └── web/
│       └── __init__.py
```

---

## Core Modules and Functionality

### 1. `src/local_deepwiki/core/`

#### Purpose
Provides core functionality for parsing, chunking, and indexing code.

#### Key Classes/Functions

- **`Chunker`** (`chunker.py`)
  - **`_create_module_chunk`**: Creates a chunk representing the overview of a module/file.
    - **Parameters**:
      - `root`: AST root node.
      - `source`: Source code bytes.
      - `language`: Programming language.
      - `file_path`: Relative path to the file.
    - **Returns**: `CodeChunk`

- **`Parser`** (`parser.py`)
  - Parses source code into ASTs and extracts semantic information.

- **`Indexer`** (`indexer.py`)
  - Indexes code chunks for retrieval and search.

- **`VectorStore`** (`vectorstore.py`)
  - Stores and retrieves embeddings of code chunks.

---

### 2. `src/local_deepwiki/generators/`

#### Purpose
Generates structured documentation and visualizations from code chunks.

#### Key Functions

- **`generate_architecture_diagram`** (`diagrams.py`)
  - Generates a Mermaid architecture diagram from a list of `CodeChunk`.
  - **Parameters**:
    - `chunks`: List of `CodeChunk`.
  - **Returns**: Mermaid diagram string.

- **`generate_class_diagram`** (`diagrams.py`)
  - Generates a Mermaid class diagram from code chunks.

- **`generate_dependency_diagram`** (`diagrams.py`)
  - Generates a Mermaid dependency diagram from code chunks.

- **`generate_file_tree_diagram`** (`diagrams.py`)
  - Generates a Mermaid file tree diagram.

- **`render_tree`** (`diagrams.py`)
  - Helper function to render tree structures.

- **`_generate_modules_index`** (`wiki.py`)
  - Generates an index page for modules in wiki format.
  - **Parameters**:
    - `module_pages`: List of `WikiPage`.
  - **Returns**: Markdown string.

---

### 3. `src/local_deepwiki/providers/`

#### Purpose
Provides abstraction for LLM and embedding providers.

#### Key Classes

- **`LLMProvider`** (`base.py`)
  - Abstract base class for LLM providers.
  - Defines interface for generating text.

- **`EmbeddingProvider`** (`base.py`)
  - Abstract base class for embedding providers.
  - Defines interface for generating embeddings.

#### Providers

- **`AnthropicProvider`** (`providers/llm/anthropic.py`)
  - Implements `LLMProvider` for Anthropic's Claude API.

- **`OllamaProvider`** (`providers/llm/ollama.py`)
  - Implements `LLMProvider` for local Ollama LLMs.

---

### 4. `src/local_deepwiki/models.py`

#### Purpose
Defines data models used across the module.

#### Key Classes

- **`CodeChunk`**
  - Represents a chunk of code with metadata.

- **`WikiPage`**
  - Represents a documentation page.

- **`IndexStatus`**
  - Represents the indexing status of a chunk.

---

### 5. `src/local_deepwiki/config.py`

#### Purpose
Handles configuration loading and validation.

#### Key Functions

- **`load_config`**
  - Loads configuration from a file or environment.

---

### 6. `src/local_deepwiki/server.py`

#### Purpose
Provides a simple HTTP server for serving documentation.

#### Key Functions

- **`start_server`**
  - Starts the local documentation server.

---

## Usage Examples

### 1. Parsing and Chunking Code

```python
from local_deepwiki.core.chunker import Chunker
from local_deepwiki.models import CodeChunk

chunker = Chunker()
source_code = b"def hello():\n    print('Hello')\n"
root = chunker.parse(source_code, "python")
chunk = chunker._create_module_chunk(root, source_code, "python", "example.py")
print(chunk)
```

### 2. Generating Architecture Diagram

```python
from local_deepwiki.generators.diagrams import generate_architecture_diagram
from local_deepwiki.models import CodeChunk

chunks = [CodeChunk(...)]  # List of chunks
diagram = generate_architecture_diagram(chunks)
print(diagram)
```

### 3. Using LLM Provider

```python
from local_deepwiki.providers.llm.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="your-anthropic-key")
response = provider.generate("Explain code in 2 sentences")
print(response)
```

### 4. Generating Wiki Documentation

```python
from local_deepwiki.generators.wiki import WikiGenerator

wiki_gen = WikiGenerator()
index = wiki_gen._generate_modules_index(module_pages)
print(index)
```

---

## Dependencies

- `anthropic` (for `AnthropicProvider`)
- `ollama` (for `OllamaProvider`)
- `tree-sitter` (for parsing code)
- `pydantic` (for models)
- `aiohttp` (for async operations)

---

## Notes

- This module is designed to be extensible. New LLMs or embedding providers can be added by implementing the respective base classes.
- All core logic is built around AST parsing and semantic chunking to support accurate documentation generation.
- The module supports both local and remote LLMs via providers.