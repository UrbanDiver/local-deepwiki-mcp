# `src/local_deepwiki/core/indexer.py`

## File Overview

This file implements the core indexing functionality for the `local_deepwiki` system. It provides the `RepositoryIndexer` class, which is responsible for indexing code repositories by parsing files, chunking code, generating embeddings, and storing the results in a vector store. The indexer supports both full rebuilds and incremental updates, and can track indexing status across runs.

## Classes

### `RepositoryIndexer`

The `RepositoryIndexer` class is the main entry point for indexing code repositories. It handles parsing, chunking, embedding, and vector storage of code files.

#### Constructor

```python
def __init__(
    self,
    repo_path: Path,
    config: Config | None = None,
    embedding_provider_name: str | None = None,
)
```

**Parameters:**
- `repo_path` (`Path`): Path to the root of the repository to index.
- `config` (`Config | None`, optional): Configuration object. If not provided, defaults to `get_config()`.
- `embedding_provider_name` (`str | None`, optional): Override embedding provider ("local" or "openai").

**Purpose:**
Initializes the indexer with the repository path and configuration.

#### Methods

##### `index(full_rebuild: bool = False, progress_callback: Callable[[str, int, int], None] | None = None) -> IndexStatus`

**Parameters:**
- `full_rebuild` (`bool`, optional): If `True`, rebuilds the entire index. If `False`, performs an incremental update.
- `progress_callback` (`Callable[[str, int, int], None] | None`, optional): Callback function to report progress updates. Signature: `(message: str, current: int, total: int)`.

**Returns:**
`IndexStatus`: Object containing indexing results and status information.

**Purpose:**
Indexes the repository by parsing files, chunking code, generating embeddings, and storing in vector store. Supports full rebuilds and incremental updates.

##### `_load_status() -> IndexStatus | None`

**Returns:**
`IndexStatus | None`: Previous indexing status if found, otherwise `None`.

**Purpose:**
Loads the indexing status from a saved file to determine what needs to be indexed.

##### `_save_status(status: IndexStatus) -> None`

**Parameters:**
- `status` (`IndexStatus`): Indexing status to save.

**Purpose:**
Saves the current indexing status to a file for future incremental updates.

##### `_should_index_file(file_path: Path) -> bool`

**Parameters:**
- `file_path` (`Path`): Path to the file to check.

**Returns:**
`bool`: `True` if the file should be indexed based on the configuration's file patterns.

**Purpose:**
Determines if a file should be indexed based on configured include/exclude patterns.

##### `_parse_file(file_path: Path) -> FileInfo`

**Parameters:**
- `file_path` (`Path`): Path to the file to parse.

**Returns:**
`FileInfo`: Parsed file information including code chunks and metadata.

**Purpose:**
Parses a single file and returns structured information about it.

##### `_chunk_file(file_info: FileInfo) -> list[CodeChunk]`

**Parameters:**
- `file_info` (`FileInfo`): Parsed file information.

**Returns:**
`list[CodeChunk]`: List of code chunks extracted from the file.

**Purpose:**
Chunks the code in a parsed file into manageable segments for embedding.

##### `_embed_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]`

**Parameters:**
- `chunks` (`list[CodeChunk]`): List of code chunks to embed.

**Returns:**
`list[CodeChunk]`: List of code chunks with embedded vectors.

**Purpose:**
Generates embeddings for code chunks using the configured embedding provider.

##### `_store_chunks(chunks: list[CodeChunk]) -> None`

**Parameters:**
- `chunks` (`list[CodeChunk]`): List of code chunks with embeddings to store.

**Purpose:**
Stores the embedded code chunks in the vector store.

##### `_update_index_status(status: IndexStatus, file_path: Path) -> None`

**Parameters:**
- `status` (`IndexStatus`): Current indexing status.
- `file_path` (`Path`): Path to the file that was indexed.

**Purpose:**
Updates the indexing status with information about a processed file.

## Usage Examples

### Basic Indexing

```python
from pathlib import Path
from local_deepwiki.core.indexer import RepositoryIndexer

# Initialize indexer
indexer = RepositoryIndexer(
    repo_path=Path("/path/to/repo"),
    embedding_provider_name="local"  # Optional override
)

# Index the repository
status = await indexer.index()

# Check status
print(f"Indexed {status.files_indexed} files")
```

### Full Rebuild

```python
# Force a full rebuild
status = await indexer.index(full_rebuild=True)
```

### Progress Tracking

```python
def progress_callback(message: str, current: int, total: int):
    print(f"{message}: {current}/{total}")

status = await indexer.index(
    full_rebuild=True,
    progress_callback=progress_callback
)
```

## Dependencies

This file imports the following modules and components:

- `fnmatch`: For file pattern matching
- `json`: For loading/saving index status
- `time`: For timing operations
- `pathlib.Path`: For path manipulation
- `typing.Callable`: For type hints
- `rich.progress.Progress, TaskID`: For progress reporting
- `local_deepwiki.config.Config, get_config`: For configuration management
- `local_deepwiki.core.chunker.CodeChunker`: For code chunking
- `local_deepwiki.core.parser.CodeParser`: For parsing code files
- `local_deepwiki.core.vectorstore.VectorStore`: For vector storage
- `local_deepwiki.models.CodeChunk, FileInfo, IndexStatus`: Data models
- `local_deepwiki.providers.embeddings.get_embedding_provider`: For embedding generation

## Constants

- `INDEX_STATUS_FILE`: Name of the file used to store indexing status (default: `"index_status.json"`)

## Notes

- The indexer tracks indexing status in a JSON file to support incremental updates.
- File inclusion/exclusion is controlled via configuration patterns.
- The indexer uses a `CodeParser` to parse files and a `CodeChunker` to split code into chunks.
- Embeddings are generated using the configured embedding provider.
- Vector storage is handled by the `VectorStore` class.
- Progress reporting is optional but supported via the `progress_callback` parameter.