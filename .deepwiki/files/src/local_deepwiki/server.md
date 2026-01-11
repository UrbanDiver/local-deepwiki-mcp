# Local DeepWiki Server Documentation

## File Overview

The `src/local_deepwiki/server.py` file implements a server that provides a set of tools for interacting with code repositories and generating wiki documentation. It serves as the core entry point for the Local DeepWiki application, exposing functionality through the MCP (Model Control Protocol) interface to enable AI agents to index repositories, search code, and generate wiki content.

## Dependencies

This file imports the following modules and components:

- `asyncio`: For asynchronous programming support
- `json`: For JSON serialization/deserialization
- `pathlib.Path`: For file system path operations
- `typing.Any`: For type annotations
- `mcp.server.Server`: MCP server interface
- `mcp.server.stdio.stdio_server`: Standard I/O server implementation
- `mcp.types.TextContent`, `mcp.types.Tool`: MCP type definitions
- `local_deepwiki.config.Config`, `get_config`, `set_config`: Configuration management
- `local_deepwiki.core.indexer.RepositoryIndexer`: Repository indexing functionality
- `local_deepwiki.core.vectorstore.VectorStore`: Vector storage and search
- `local_deepwiki.generators.wiki.generate_wiki`: Wiki generation logic
- `local_deepwiki.models.WikiStructure`: Wiki structure model
- `local_deepwiki.providers.embeddings.get_embedding_provider`: Embedding provider factory
- `local_deepwiki.providers.llm.get_llm_provider`: LLM provider factory

## Classes

### RepositoryIndexer

**Purpose**: Provides functionality to index code repositories for semantic search and documentation generation.

**Key Methods**:
- `index_repository(path: str, config: Config)`: Indexes a repository at the given path using the provided configuration

### VectorStore

**Purpose**: Manages vector embeddings for semantic search and retrieval of code content.

**Key Methods**:
- `search(query: str, top_k: int = 10)`: Searches for relevant code snippets matching the query
- `add_document(document: dict)`: Adds a document to the vector store

## Functions

### `list_tools() -> list[Tool]`

**Purpose**: Returns a list of available tools that can be called through the MCP interface.

**Parameters**: None

**Return Value**: List of `Tool` objects describing the available functionality

### `call_tool(tool_name: str, tool_input: dict) -> Any`

**Purpose**: Executes a specific tool with the given input parameters.

**Parameters**:
- `tool_name`: Name of the tool to call
- `tool_input`: Dictionary containing tool-specific input parameters

**Return Value**: Result of the tool execution

### `handle_index_repository(input_data: dict) -> dict`

**Purpose**: Handles the index repository tool call, creating a new index from a repository path.

**Parameters**:
- `input_data`: Dictionary containing repository path and optional configuration

**Return Value**: Dictionary with status and index information

### `progress_callback(progress: int, total: int, message: str)`

**Purpose**: Callback function for reporting indexing progress.

**Parameters**:
- `progress`: Current progress value
- `total`: Total expected progress
- `message`: Progress status message

**Return Value**: None

### `handle_ask_question(input_data: dict) -> dict`

**Purpose**: Handles asking questions about the indexed repository content.

**Parameters**:
- `input_data`: Dictionary containing the question and context

**Return Value**: Dictionary with the answer and related code snippets

### `handle_read_wiki_structure(input_data: dict) -> dict`

**Purpose**: Reads and returns the wiki structure for the indexed repository.

**Parameters**:
- `input_data`: Dictionary containing path information

**Return Value**: Dictionary with the wiki structure

### `handle_read_wiki_page(input_data: dict) -> dict`

**Purpose**: Reads a specific wiki page content.

**Parameters**:
- `input_data`: Dictionary containing page path information

**Return Value**: Dictionary with page content

### `handle_search_code(input_data: dict) -> dict`

**Purpose**: Searches code snippets in the indexed repository.

**Parameters**:
- `input_data`: Dictionary containing search query and parameters

**Return Value**: Dictionary with search results and code snippets

### `main() -> None`

**Purpose**: Main entry point for the server application.

**Parameters**: None

**Return Value**: None

### `run() -> None`

**Purpose**: Starts the MCP server with the defined tools.

**Parameters**: None

**Return Value**: None

## Usage Examples

### Starting the Server

```python
# Run the server
if __name__ == "__main__":
    main()
```

### Using the Index Repository Tool

```python
# Example input for index repository tool
index_input = {
    "path": "/path/to/repository",
    "config": {
        "embedding_model": "text-embedding-3-small",
        "chunk_size": 1000
    }
}

# Call the tool
result = call_tool("index_repository", index_input)
```

### Searching Code

```python
# Example input for search code tool
search_input = {
    "query": "how to implement authentication",
    "top_k": 5
}

# Call the tool
result = call_tool("search_code", search_input)
```

### Asking Questions

```python
# Example input for ask question tool
question_input = {
    "question": "What is the purpose of the User model?",
    "context": "repository_index_id"
}

# Call the tool
result = call_tool("ask_question", question_input)
```

## Server Configuration

The server uses configuration management through `local_deepwiki.config.Config` which can be accessed via `get_config()` and `set_config()` functions. Configuration includes embedding model selection, chunk size, and other repository indexing parameters.

The server implements the MCP protocol and can be run as a standard I/O server, making it compatible with AI agents that support the Model Control Protocol.

## See Also

- [vectorstore](core/vectorstore.md) - dependency
- [indexer](core/indexer.md) - dependency
- [models](models.md) - dependency
- [config](config.md) - dependency
- [wiki](generators/wiki.md) - dependency
