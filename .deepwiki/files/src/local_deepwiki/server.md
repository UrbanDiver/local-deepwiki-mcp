# File Overview

This file, `src/local_deepwiki/server.py`, implements the main entry point for a Model Control Protocol (MCP) server that provides a set of tools for repository indexing, documentation generation, and research capabilities. It integrates with the `mcp` library for communication over stdio and uses handlers from `local_deepwiki.handlers` to perform specific tasks.

## Dependencies

The file imports:
- `asyncio` for asynchronous operations
- `typing.Any` for type hints
- `mcp.server.Server` and `mcp.server.stdio.stdio_server` for MCP server functionality
- `mcp.types.TextContent` and `mcp.types.Tool` for MCP types
- `local_deepwiki.handlers` which provides various tool handlers for different operations

## Related Files

This file is related to:
- `src/local_deepwiki/cli/__init__.py`
- `src/local_deepwiki/core/__init__.py`
- `src/local_deepwiki/generators/source_refs.py`
- `src/local_deepwiki/generators/wiki.py`
- `tests/test_plugins.py`

## Integration

Functions and classes in this file are called from:
- `list_tools`: used by `test_server`

---

# Classes

## ToolHandler

The `ToolHandler` class is a base class for handling tool execution. It provides a common interface for processing tool calls and managing progress reporting.

### Methods

- `__init__(self, server: Server)`  
  Initializes the `ToolHandler` with a reference to the server.

- `handle(self, arguments: dict[str, Any]) -> list[TextContent]`  
  Abstract method to be implemented by subclasses for handling tool-specific logic.

---

# Functions

## list_tools

```python
async def list_tools() -> list[Tool]
```

**Purpose**:  
Lists all available tools for the MCP server.

**Returns**:  
A list of `Tool` objects that define the tools available for use.

---

## call_tool

```python
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]
```

**Purpose**:  
Handles tool calls by routing them to the appropriate handler functions.

**Parameters**:
- `name`: The name of the tool to call.
- `arguments`: A dictionary of arguments for the tool.

**Returns**:  
A list of `TextContent` objects as the result of the tool execution.

---

## main

```python
def main()
```

**Purpose**:  
Main entry point for starting the MCP server.

**Behavior**:  
Initializes and runs the MCP server using stdio for communication.

---

## run

```python
async def run()
```

**Purpose**:  
Asynchronously runs the MCP server.

**Behavior**:  
Sets up stdio communication and starts the server with initialization options.

---

# Usage Examples

### Starting the Server

To start the server, run the `main` function:

```python
if __name__ == "__main__":
    main()
```

This will initialize and start the MCP server, listening for tool calls over stdio.

### Listing Tools

To list all available tools:

```python
tools = await list_tools()
```

This returns a list of `Tool` objects that can be used by an MCP client.

### Calling a Tool

To call a specific tool:

```python
result = await call_tool("index_repository", {"repo_path": "/path/to/repo"})
```

This will execute the `index_repository` tool with the specified arguments and return the result as a list of `TextContent`.

## API Reference

### Functions

#### `list_tools`

`@server.list_tools()`

```python
async def list_tools() -> list[Tool]
```

List available tools.

**Returns:** `list[Tool]`



<details>
<summary>View Source (lines 47-558) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/server.py#L47-L558">GitHub</a></summary>

```python
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="index_repository",
            description="Index a repository and generate wiki documentation. This parses all source files, extracts semantic code chunks, generates embeddings, and creates wiki markdown files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Absolute path to the repository to index",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional output directory for wiki (default: {repo}/.deepwiki)",
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of languages to include (default: all supported)",
                    },
                    "full_rebuild": {
                        "type": "boolean",
                        "description": "Force full rebuild instead of incremental update (default: false)",
                    },
                    "llm_provider": {
                        "type": "string",
                        "enum": ["ollama", "anthropic", "openai"],
                        "description": "LLM provider for wiki generation (default: from config)",
                    },
                    "embedding_provider": {
                        "type": "string",
                        "enum": ["local", "openai"],
                        "description": "Embedding provider for semantic search (default: from config)",
                    },
                    "use_cloud_for_github": {
                        "type": "boolean",
                        "description": "Use cloud LLM (Anthropic Claude) for GitHub repos. Faster and higher quality but requires API key. (default: from config)",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="ask_question",
            description="Ask a question about an indexed repository using RAG. Returns an answer based on relevant code context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the codebase",
                    },
                    "max_context": {
                        "type": "integer",
                        "description": "Maximum number of code chunks for context (default: 5)",
                    },
                },
                "required": ["repo_path", "question"],
            },
        ),
        Tool(
            name="deep_research",
            description="Perform deep research on a codebase question using multi-step reasoning. Unlike ask_question (single retrieval), this performs query decomposition, parallel retrieval, gap analysis, and comprehensive synthesis. Best for complex architectural questions. Supports checkpointing for long-running research that can be resumed if interrupted.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "question": {
                        "type": "string",
                        "description": "Complex architectural question about the codebase",
                    },
                    "max_chunks": {
                        "type": "integer",
                        "description": "Maximum total code chunks to analyze (default: 30)",
                    },
                    "preset": {
                        "type": "string",
                        "enum": ["quick", "default", "thorough"],
                        "description": "Research mode preset: 'quick' (fast, fewer sub-questions), 'default' (balanced), 'thorough' (comprehensive, more analysis)",
                    },
                    "resume_research_id": {
                        "type": "string",
                        "description": "Optional checkpoint ID to resume an interrupted research session. Use list_research_checkpoints to see available checkpoints.",
                    },
                },
                "required": ["repo_path", "question"],
            },
        ),
        Tool(
            name="read_wiki_structure",
            description="Get the table of contents and structure of a generated wiki.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                    },
                },
                "required": ["wiki_path"],
            },
        ),
        Tool(
            name="read_wiki_page",
            description="Read a specific wiki page content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory",
                    },
                    "page": {
                        "type": "string",
                        "description": "Page path relative to wiki root (e.g., 'index.md', 'modules/auth.md')",
                    },
                },
                "required": ["wiki_path", "page"],
            },
        ),
        Tool(
            name="search_code",
            description="Semantic search across the indexed codebase with optional fuzzy matching and filters. Returns relevant code chunks with similarity scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "query": {
                        "type": "string",
                        "description": "Semantic search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                    },
                    "language": {
                        "type": "string",
                        "enum": [
                            "python",
                            "javascript",
                            "typescript",
                            "tsx",
                            "go",
                            "rust",
                            "java",
                            "c",
                            "cpp",
                            "swift",
                            "ruby",
                            "php",
                            "kotlin",
                            "csharp",
                        ],
                        "description": "Filter by programming language",
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "function",
                            "class",
                            "method",
                            "module",
                            "import",
                            "comment",
                            "other",
                        ],
                        "description": "Filter by chunk type (e.g., function, class, method)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Filter by file path pattern (e.g., 'src/**/*.py', 'tests/*')",
                    },
                    "fuzzy": {
                        "type": "boolean",
                        "description": "Enable fuzzy matching to improve results for exact name matches (default: false)",
                    },
                    "fuzzy_weight": {
                        "type": "number",
                        "description": "Weight for fuzzy matching score (0.0-1.0, default: 0.3). Higher values favor exact text matches over semantic similarity.",
                    },
                },
                "required": ["repo_path", "query"],
            },
        ),
        Tool(
            name="export_wiki_html",
            description="Export wiki documentation to static HTML files. Creates a self-contained website that can be viewed without a server.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output directory for HTML files (default: {wiki_path}_html)",
                    },
                },
                "required": ["wiki_path"],
            },
        ),
        Tool(
            name="export_wiki_pdf",
            description="Export wiki documentation to PDF format. Creates a printable PDF document with proper formatting, page numbers, and table of contents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "wiki_path": {
                        "type": "string",
                        "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output path for PDF file (default: {wiki_path}.pdf)",
                    },
                    "single_file": {
                        "type": "boolean",
                        "description": "If true, combine all pages into one PDF. If false, create separate PDFs for each page. Default: true",
                    },
                },
                "required": ["wiki_path"],
            },
        ),
        Tool(
            name="list_research_checkpoints",
            description="List all research checkpoints for a repository. Shows incomplete and cancelled research sessions that can be resumed using the deep_research tool with resume_research_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the repository to list checkpoints for",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="cancel_research",
            description="Cancel an active deep research session and save its checkpoint. The research can be resumed later using the deep_research tool with resume_research_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the repository",
                    },
                    "research_id": {
                        "type": "string",
                        "description": "ID of the research session to cancel (from list_research_checkpoints)",
                    },
                },
                "required": ["repo_path", "research_id"],
            },
        ),
        Tool(
            name="resume_research",
            description="Resume a previously interrupted deep research session from its checkpoint. This is a convenience wrapper - you can also use deep_research with resume_research_id directly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the repository",
                    },
                    "research_id": {
                        "type": "string",
                        "description": "ID of the research checkpoint to resume (from list_research_checkpoints)",
                    },
                },
                "required": ["repo_path", "research_id"],
            },
        ),
        Tool(
            name="get_operation_progress",
            description="Get progress for active long-running operations. Supports polling-based progress tracking for clients that cannot receive push notifications. Returns current progress, ETA, and phase information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "Specific operation ID to get progress for. If not provided, returns all active operations.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_glossary",
            description="Get a searchable glossary of all code entities (classes, functions, methods) in an indexed repository. Useful for discovering what's in the codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional search term to filter entities by name or docstring",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="get_diagrams",
            description="Generate Mermaid diagrams for an indexed repository. Supports class diagrams, dependency graphs, module overviews, language distribution pie charts, and sequence diagrams.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "diagram_type": {
                        "type": "string",
                        "enum": [
                            "class",
                            "dependency",
                            "module",
                            "sequence",
                            "language_pie",
                        ],
                        "description": "Type of diagram to generate (default: class)",
                    },
                    "entry_point": {
                        "type": "string",
                        "description": "Entry point function name (required for sequence diagrams)",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="get_inheritance",
            description="Get class inheritance hierarchy trees for an indexed repository. Shows parent-child relationships, abstract classes, and generates a Mermaid inheritance diagram.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="get_call_graph",
            description="Get function call graphs showing which functions call which. Can analyze a specific file or the entire repository. Returns a Mermaid flowchart.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Specific file to analyze (relative to repo root). If omitted, analyzes entire repo.",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="get_coverage",
            description="Get documentation coverage report for an indexed repository. Shows which classes, functions, and methods have docstrings and which don't.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="detect_stale_docs",
            description="Find wiki pages that may be outdated because their source files have been modified since the documentation was generated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "threshold_days": {
                        "type": "integer",
                        "description": "Minimum days since source changed to consider stale (default: 0)",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="get_changelog",
            description="Extract recent git commit history as a formatted changelog. Groups commits by date and includes file change information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the repository (must be a git repo)",
                    },
                    "max_commits": {
                        "type": "integer",
                        "description": "Maximum number of commits to include (default: 30, max: 200)",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="detect_secrets",
            description="Scan a repository for hardcoded credentials and secrets (API keys, tokens, passwords, private keys). Returns findings with type, location, confidence, and remediation advice.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the repository to scan",
                    },
                },
                "required": ["repo_path"],
            },
        ),
        Tool(
            name="get_test_examples",
            description="Find usage examples for a function or class by searching test files in the indexed repository. Returns code snippets showing how the entity is used in tests.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                    "entity_name": {
                        "type": "string",
                        "description": "Name of the function or class to find examples for",
                    },
                    "max_examples": {
                        "type": "integer",
                        "description": "Maximum number of examples to return (default: 5)",
                    },
                },
                "required": ["repo_path", "entity_name"],
            },
        ),
        Tool(
            name="get_api_docs",
            description="Get API documentation with function signatures, parameters, return types, and docstrings for a specific file. Uses tree-sitter AST parsing for accuracy.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the repository",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "File path relative to repo root to get API docs for",
                    },
                },
                "required": ["repo_path", "file_path"],
            },
        ),
        Tool(
            name="list_indexed_repos",
            description="Discover all indexed repositories under a given directory. Searches for .deepwiki directories and returns index metadata for each.",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_path": {
                        "type": "string",
                        "description": "Base directory to search for indexed repos (default: current directory)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_index_status",
            description="Get index statistics for a repository without re-indexing. Shows file count, chunk count, languages, and when it was last indexed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to the indexed repository",
                    },
                },
                "required": ["repo_path"],
            },
        ),
    ]
```

</details>

#### `call_tool`

`@server.call_tool()`

```python
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]
```

Handle tool calls.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | - | - |
| `arguments` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`



<details>
<summary>View Source (lines 593-613) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/server.py#L593-L613">GitHub</a></summary>

```python
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call received: {name}")
    logger.debug(f"Tool arguments: {arguments}")

    # Special handling for tools that need server context for progress streaming
    if name == "index_repository":
        return await handle_index_repository(arguments, server=server)

    if name == "deep_research":
        return await handle_deep_research(arguments, server=server)

    if name == "resume_research":
        return await handle_resume_research(arguments, server=server)

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        logger.warning(f"Unknown tool requested: {name}")
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return await handler(arguments)
```

</details>

#### `main`

```python
def main()
```

Main entry point for the MCP server.



<details>
<summary>View Source (lines 616-628) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/server.py#L616-L628">GitHub</a></summary>

```python
def main():
    """Main entry point for the MCP server."""
    logger.info("Starting local-deepwiki MCP server")

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())
```

</details>

#### `run`

```python
async def run()
```




<details>
<summary>View Source (lines 620-626) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/server.py#L620-L626">GitHub</a></summary>

```python
async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
```

</details>

## Call Graph

```mermaid
flowchart TD
    N0[TextContent]
    N1[Tool]
    N2[call_tool]
    N3[create_initialization_options]
    N4[handle_deep_research]
    N5[handle_index_repository]
    N6[handle_resume_research]
    N7[handler]
    N8[list_tools]
    N9[main]
    N10[run]
    N11[stdio_server]
    N8 --> N1
    N2 --> N5
    N2 --> N4
    N2 --> N6
    N2 --> N0
    N2 --> N7
    N9 --> N11
    N9 --> N10
    N9 --> N3
    N10 --> N11
    N10 --> N10
    N10 --> N3
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11 func
```

## Used By

Functions and methods in this file and their callers:

- **`TextContent`**: called by `call_tool`
- **`Tool`**: called by `list_tools`
- **`create_initialization_options`**: called by `main`, `run`
- **`handle_deep_research`**: called by `call_tool`
- **`handle_index_repository`**: called by `call_tool`
- **`handle_resume_research`**: called by `call_tool`
- **`handler`**: called by `call_tool`
- **`run`**: called by `main`, `run`
- **`stdio_server`**: called by `main`, `run`

## Usage Examples

*Examples extracted from test files*

### Test that the server is properly initialized

From `test_server.py::TestServer::test_server_is_initialized`:

```python
assert server is not None
assert server.name == "local-deepwiki"
```

### Test that list_tools returns a list of Tool objects

From `test_server.py::TestListTools::test_list_tools_returns_list`:

```python
tools = await list_tools()
assert isinstance(tools, list)
assert len(tools) > 0
```

### Test that all expected tools are returned

From `test_server.py::TestListTools::test_list_tools_returns_all_expected_tools`:

```python
tools = await list_tools()
tool_names = [t.name for t in tools]

expected_tools = [
    "index_repository",
    "ask_question",
    "deep_research",
    "read_wiki_structure",
    "read_wiki_page",
    "search_code",
    "export_wiki_html",
    "export_wiki_pdf",
]

for expected in expected_tools:
    assert expected in tool_names, f"Missing tool: {expected}"
```

### Test that unknown tools return an error message

From `test_server.py::TestCallTool::test_unknown_tool_returns_error`:

```python
result = await call_tool("nonexistent_tool", {})

assert len(result) == 1
assert isinstance(result[0], TextContent)
assert "Unknown tool" in result[0].text
assert "nonexistent_tool" in result[0].text
```

### Test that real handler validates inputs (no mocking)

From `test_server.py::TestToolHandlersIntegration::test_index_repository_real_handler_validation`:

```python
nonexistent = tmp_path / "nonexistent"
result = await call_tool("index_repository", {"repo_path": str(nonexistent)})

assert len(result) == 1
assert "Error" in result[0].text
assert "does not exist" in result[0].text
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `list_tools` | function | Brian Breidenbach | today | `21d245e` feat: Add 12 new MCP tools ... |
| `call_tool` | function | Brian Breidenbach | 1 week ago | `e899c6c` Add three high-value enhanc... |
| `main` | function | Brian Breidenbach | 3 weeks ago | `c568951` Add input validation, type ... |
| `run` | function | Brian Breidenbach | 3 weeks ago | `cdae76f` Initial commit: Local DeepW... |