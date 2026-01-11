# `src/local_deepwiki/server.py` Documentation

## File Overview

This file implements the main server logic for the Local DeepWiki application. It provides a tool-based interface for indexing repositories, generating wiki documentation, and querying the generated content using the MCP (Model Control Protocol) standard.

The server exposes tools for:
- Indexing repositories and generating wiki documentation
- Reading wiki structure and individual pages
- Searching code content
- Asking questions about the indexed repository

## Dependencies

This file imports the following modules and components:

- `asyncio` - For asynchronous operations
- `json` - For JSON serialization
- `pathlib.Path` - For path manipulation
- `typing.Any` - For type annotations
- `mcp.server.Server` - MCP server implementation
- `mcp.server.stdio.stdio_server` - For stdio-based server communication
- `mcp.types.TextContent` and `Tool` - MCP types for content and tools
- `local_deepwiki.config.Config` - Configuration management
- `local_deepwiki.core.indexer.RepositoryIndexer` - Repository indexing logic
- `local_deepwiki.core.vectorstore.VectorStore` - Vector storage implementation
- `local_deepwiki.generators.wiki.generate_wiki` - Wiki generation function
- `local_deepwiki.models.WikiStructure` - Wiki structure model
- `local_deepwiki.providers.embeddings.get_embedding_provider` - Embedding provider factory
- `local_deepwiki.providers.llm.get_llm_provider` - LLM provider factory

## Functions

### `list_tools()`

**Purpose**: Returns a list of available tools for the MCP server.

**Parameters**: None

**Return Value**: `list[Tool]` - List of tool definitions with names, descriptions, and input schemas.

**Usage**:
```python
tools = await list_tools()
```

### `call_tool()`

**Purpose**: Dispatches tool calls to their respective handlers.

**Parameters**:
- `tool_name` (str): Name of the tool to call
- `args` (dict): Arguments for the tool call

**Return Value**: `Any` - Result of the tool execution

**Usage**:
```python
result = await call_tool("index_repository", {"repo_path": "/path/to/repo"})
```

### `handle_index_repository()`

**Purpose**: Handles the `index_repository` tool call, which indexes a repository and generates wiki documentation.

**Parameters**:
- `args` (dict): Dictionary containing:
  - `repo_path` (str): Absolute path to the repository to index
  - `wiki_path` (str): Path where wiki files should be stored
  - `config` (dict, optional): Configuration overrides

**Return Value**: `list[TextContent]` - Result text content indicating success or error

**Usage**:
```python
result = await handle_index_repository({
    "repo_path": "/home/user/project",
    "wiki_path": "/home/user/project/wiki"
})
```

### `progress_callback()`

**Purpose**: Callback function to report indexing progress.

**Parameters**:
- `message` (str): Progress message to report

**Return Value**: None

**Usage**:
```python
# Called internally during indexing operations
```

### `handle_ask_question()`

**Purpose**: Handles the `ask_question` tool call, which answers questions about the indexed repository.

**Parameters**:
- `args` (dict): Dictionary containing:
  - `question` (str): Question to ask
  - `wiki_path` (str): Path to the wiki documentation

**Return Value**: `list[TextContent]` - Result text content with answer or error

**Usage**:
```python
result = await handle_ask_question({
    "question": "How does the authentication work?",
    "wiki_path": "/home/user/project/wiki"
})
```

### `handle_read_wiki_structure()`

**Purpose**: Handles the `read_wiki_structure` tool call, which returns the structure of wiki files.

**Parameters**:
- `args` (dict): Dictionary containing:
  - `wiki_path` (str): Path to the wiki directory

**Return Value**: `list[TextContent]` - Result text content with wiki structure or error

**Usage**:
```python
result = await handle_read_wiki_structure({
    "wiki_path": "/home/user/project/wiki"
})
```

### `handle_read_wiki_page()`

**Purpose**: Handles the `read_wiki_page` tool call, which reads and returns the content of a specific wiki page.

**Parameters**:
- `args` (dict): Dictionary containing:
  - `wiki_path` (str): Path to the wiki directory
  - `page` (str): Relative path to the wiki page

**Return Value**: `list[TextContent]` - Result text content with page content or error

**Usage**:
```python
result = await handle_read_wiki_page({
    "wiki_path": "/home/user/project/wiki",
    "page": "installation.md"
})
```

### `handle_search_code()`

**Purpose**: Handles the `search_code` tool call, which searches for code snippets in the indexed repository.

**Parameters**:
- `args` (dict): Dictionary containing:
  - `query` (str): Search query
  - `wiki_path` (str): Path to the wiki directory

**Return Value**: `list[TextContent]` - Result text content with search results or error

**Usage**:
```python
result = await handle_search_code({
    "query": "authentication logic",
    "wiki_path": "/home/user/project/wiki"
})
```

### `main()`

**Purpose**: Main entry point for the server application.

**Parameters**: None

**Return Value**: None

**Usage**:
```python
if __name__ == "__main__":
    asyncio.run(main())
```

### `run()`

**Purpose**: Runs the MCP server with configured tools.

**Parameters**: None

**Return Value**: None

**Usage**:
```python
await run()
```

## Usage Examples

### Starting the Server

```python
# Run the server
if __name__ == "__main__":
    asyncio.run(main())
```

### Using Tools

#### Indexing a Repository
```python
await call_tool("index_repository", {
    "repo_path": "/path/to/repo",
    "wiki_path": "/path/to/wiki"
})
```

#### Asking a Question
```python
await call_tool("ask_question", {
    "question": "What is the purpose of this function?",
    "wiki_path": "/path/to/wiki"
})
```

#### Reading Wiki Structure
```python
await call_tool("read_wiki_structure", {
    "wiki_path": "/path/to/wiki"
})
```

#### Reading a Wiki Page
```python
await call_tool("read_wiki_page", {
    "wiki_path": "/path/to/wiki",
    "page": "installation.md"
})
```

#### Searching Code
```python
await call_tool("search_code", {
    "query": "database connection",
    "wiki_path": "/path/to/wiki"
})
```