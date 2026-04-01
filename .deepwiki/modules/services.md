# services Module Documentation

## Module Purpose

The `services` module provides the business logic layer for the Local DeepWiki MCP Server. It encapsulates core operations such as querying, wiki management, and indexing with explicit dependency injection, leaving RBAC, audit logging, and MCP response formatting in the handler layer.

## Key Classes and Functions

### SourceEntry
A dataclass representing a single source reference from a RAG query result.
- `file`: Path to the source file
- `lines`: Relevant lines from the source
- `chunk_type`: Type of chunk (e.g., function, class)
- `score`: Relevance score
- `wiki_resource`: Optional wiki resource reference

### QueryResult
A dataclass representing the result of a RAG query.
- `answer`: The LLM-synthesized answer
- `sources`: Tuple of [SourceEntry](../files/src/local_deepwiki/services/models.md) objects that informed the answer
- `agentic_metadata`: Optional metadata from agentic RAG pipeline
- `trace`: Reserved for Phase 5 RAG tracing

### ExportResult
A dataclass representing the result of a wiki export operation.
- `output_path`: Path to the exported file
- `pages_exported`: Number of pages exported
- `format`: Export format ("html" or "pdf")

### IndexPipelineResult
A dataclass representing the result of the indexing pipeline.
- `files_indexed`: Number of files processed
- `chunks_created`: Number of chunks generated
- `wiki_pages_generated`: Number of wiki pages created
- `generation_mode`: Mode used for generation
- `wiki_path`: Path to generated wiki
- `languages`: Dictionary mapping language to count
- `messages`: Tuple of status messages
- `operation_id`: Unique identifier for the operation

### WikiService
The [WikiService](../files/src/local_deepwiki/services/wiki_service.md) class provides functionality for:
- Reading wiki structure and pages
- Exporting wiki to HTML or PDF formats

#### Methods:
- `__init__(config: Config) -> None`
- `read_structure(wiki_path: Path) -> dict[str, Any]`: Reads wiki table of contents and structure
- `read_page(wiki_path: Path, page: str) -> str`: Reads a single wiki page's content
- `export_html(wiki_path: Path, output: Path) -> ExportResult`: Exports wiki to static HTML
- `export_pdf(wiki_path: Path, output: Path, *, single_file: bool = True) -> ExportResult`: Exports wiki to PDF
- `_build_structure_from_files(wiki_path: Path) -> dict[str, Any]`: Builds wiki structure by scanning markdown files

### IndexingService
The [IndexingService](../files/src/local_deepwiki/services/indexing_service.md) class handles repository indexing operations.

#### Methods:
- `__init__(config: Config) -> None`
- `index_repository(repo_path: Path, force: bool = False) -> IndexPipelineResult`: Indexes a repository

### QueryService
The [QueryService](../files/src/local_deepwiki/services/query_service.md) class provides query and search functionality.

#### Methods:
- `__init__(config: Config) -> None`
- `ask_question(query: str, repo_path: Path) -> QueryResult`: Answers questions about the codebase
- `search_code(query: str, repo_path: Path) -> list[SourceEntry]`: Searches for code matches

### expand_with_graph
An async function that optionally expands vector search results with graph-discovered chunks.
```python
async def expand_with_graph(
    search_results: list[SearchResult],
    vector_store: VectorStore,
    config: Config,
    repo_path: Path,
) -> list[SearchResult]
```
## How Components Interact

The services module components work together to provide a complete codebase documentation and querying solution:

1. **[IndexingService](../files/src/local_deepwiki/services/indexing_service.md)** orchestrates repository indexing, creating chunks and wiki pages
2. **[QueryService](../files/src/local_deepwiki/services/query_service.md)** handles RAG queries using both vector search and optional graph expansion
3. **[WikiService](../files/src/local_deepwiki/services/wiki_service.md)** manages wiki structure reading, page retrieval, and export operations
4. **[expand_with_graph](../files/src/local_deepwiki/services/graph_expansion.md)** function provides optional graph-augmented search expansion that can be called from query services

The service layer maintains clean separation of concerns by handling business logic while leaving security and response formatting to the handler layer.

## Usage Examples

### Using WikiService```python
from local_deepwiki.services import WikiService
from local_deepwiki.config import Config

config = Config()
wiki_service = WikiService(config)

# Read wiki structure
structure = await wiki_service.read_structure(Path(".deepwiki"))

# Read a specific page
content = await wiki_service.read_page(Path(".deepwiki"), "README.md")

# Export to HTML
result = await wiki_service.export_html(Path(".deepwiki"), Path("./export"))
```
### Using QueryService```python
from local_deepwiki.services import QueryService
from local_deepwiki.config import Config

config = Config()
query_service = QueryService(config)

# Ask a question about the codebase
result = await query_service.ask_question("What is the main entry point?", Path("/path/to/repo"))
```
### Using IndexingService```python
from local_deepwiki.services import IndexingService
from local_deepwiki.config import Config

config = Config()
indexing_service = IndexingService(config)

# Index a repository
result = await indexing_service.index_repository(Path("/path/to/repo"))
```
### Using expand_with_graph```python
from local_deepwiki.services.graph_expansion import expand_with_graph
from local_deepwiki.config import Config
from local_deepwiki.core.vectorstore.store import VectorStore

# Expand search results with graph data
expanded_results = await expand_with_graph(
    search_results,
    vector_store,
    config,
    Path("/path/to/repo")
)
```
## Dependencies

- `asyncio`
- `collections`
- `dataclasses`
- `json`
- `pathlib`
- `time`
- `typing`
- `local_deepwiki.config`
- `local_deepwiki.core.path_utils`
- `local_deepwiki.errors`
- `local_deepwiki.logging`
- `local_deepwiki.validation`
- `local_deepwiki.generators.lazy_generator`
- `local_deepwiki.export.html`
- `local_deepwiki.export.streaming`
- `local_deepwiki.export.pdf`
- `local_deepwiki.core.graph_rag.retriever`
- `local_deepwiki.core.graph_rag.store`
- `local_deepwiki.core.vectorstore.store`
- `local_deepwiki.models.chunks`

## Relevant Source Files

The following source files were used to generate this documentation:

- `src/local_deepwiki/services/__init__.py`
- [`src/local_deepwiki/services/wiki_service.py:26-227`](../files/src/local_deepwiki/services/wiki_service.md)
- [`src/local_deepwiki/services/graph_expansion.py:27-84`](../files/src/local_deepwiki/services/graph_expansion.md)
- [`src/local_deepwiki/services/models.py:14-21`](../files/src/local_deepwiki/services/models.md)
- [`src/local_deepwiki/services/indexing_service.py:22-216`](../files/src/local_deepwiki/services/indexing_service.md)
- [`src/local_deepwiki/services/query_service.py:26-318`](../files/src/local_deepwiki/services/query_service.md)
