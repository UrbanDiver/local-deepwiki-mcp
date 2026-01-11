# Code Chunker Documentation

## File Overview

This file implements the `CodeChunker` class responsible for extracting semantic code chunks from source files. It uses AST parsing to identify modules, classes, functions, and methods, creating structured `CodeChunk` objects that represent different semantic units within code files.

## Classes

### `CodeChunker`

The `CodeChunker` class is the core component for extracting code chunks from source files using tree-sitter parsing.

#### Constructor

```python
def __init__(self, config: ChunkingConfig | None = None)
```

**Purpose**: Initialize the chunker with optional configuration.

**Parameters**:
- `config`: Optional chunking configuration. If not provided, uses default configuration from `get_config().chunking`.

**Usage**:
```python
chunker = CodeChunker()
# or
chunker = CodeChunker(custom_config)
```

#### Methods

##### `chunk_file`

```python
def chunk_file(self, file_path: Path, repo_root: Path) -> Iterator[CodeChunk]
```

**Purpose**: Extract code chunks from a source file.

**Parameters**:
- `file_path`: Path to the source file to process
- `repo_root`: Root directory of the repository

**Returns**: Iterator of `CodeChunk` objects representing semantic units found in the file

**Usage**:
```python
chunker = CodeChunker()
for chunk in chunker.chunk_file(Path("src/main.py"), Path("/project/root")):
    print(chunk.name, chunk.type)
```

##### `_create_module_chunk`

```python
def _create_module_chunk(
    self,
    root: Node,
    source: bytes,
    language: Language,
    file_path: str,
) -> CodeChunk
```

**Purpose**: Create a chunk for the module/file overview.

**Parameters**:
- `root`: AST root node
- `source`: Source bytes
- `language`: Programming language
- `file_path`: Relative file path

**Returns**: A `CodeChunk` for the module

##### `_create_function_chunk`

```python
def _create_function_chunk(
    self,
    func_node: Node,
    source: bytes,
    language: Language,
    file_path: str,
) -> CodeChunk
```

**Purpose**: Create a chunk for a top-level function.

**Parameters**:
- `func_node`: The function AST node
- `source`: Source bytes
- `language`: Programming language
- `file_path`: Relative file path

**Returns**: A `CodeChunk` for the function

##### `_create_method_chunk`

```python
def _create_method_chunk(
    self,
    method_node: Node,
    source: bytes,
    language: Language,
    file_path: str,
    class_name: str,
) -> CodeChunk
```

**Purpose**: Create a chunk for a class method.

**Parameters**:
- `method_node`: The method AST node
- `source`: Source bytes
- `language`: Programming language
- `file_path`: Relative file path
- `class_name`: Name of the parent class

**Returns**: A `CodeChunk` for the method

## Dependencies

This file imports the following components:

- `hashlib` - For generating chunk identifiers
- `pathlib.Path` - For file path handling
- `typing.Iterator` - For type hints
- `tree_sitter.Node` - For AST node handling
- `local_deepwiki.config.ChunkingConfig` - Configuration for chunking behavior
- `local_deepwiki.config.get_config` - For retrieving default configuration
- `local_deepwiki.core.parser` - AST parsing utilities:
  - `CodeParser` - For parsing source files
  - `get_node_text` - Extract text from AST nodes
  - `get_node_name` - Extract names from AST nodes
  - `get_docstring` - Extract docstrings from nodes
  - `find_nodes_by_type` - Find nodes of specific types
- `local_deepwiki.models` - Data models:
  - `CodeChunk` - Representation of code chunks
  - `ChunkType` - Types of code chunks
  - `Language` - Supported programming languages

## Usage Examples

### Basic Usage

```python
from pathlib import Path
from local_deepwiki.core.chunker import CodeChunker

# Initialize chunker
chunker = CodeChunker()

# Process a file
file_path = Path("src/example.py")
repo_root = Path("/project/root")

for chunk in chunker.chunk_file(file_path, repo_root):
    print(f"Chunk: {chunk.name} ({chunk.type})")
    print(f"Content: {chunk.content[:100]}...")
```

### With Custom Configuration

```python
from local_deepwiki.config import ChunkingConfig
from local_deepwiki.core.chunker import CodeChunker

# Create custom configuration
config = ChunkingConfig(
    max_chunk_size=1000,
    include_docstrings=True
)

# Initialize chunker with custom config
chunker = CodeChunker(config)
```

### Processing Multiple Files

```python
from pathlib import Path
from local_deepwiki.core.chunker import CodeChunker

chunker = CodeChunker()

repo_root = Path("/project/root")
source_files = list(repo_root.rglob("*.py"))

for file_path in source_files:
    try:
        for chunk in chunker.chunk_file(file_path, repo_root):
            print(f"{chunk.file_path}:{chunk.name} - {chunk.type}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
```