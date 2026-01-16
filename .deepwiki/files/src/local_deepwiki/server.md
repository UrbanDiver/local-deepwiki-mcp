# server.py

## File Overview

The `server.py` file implements an MCP (Model Context Protocol) server for the local_deepwiki application. It serves as the main entry point that exposes various wiki and code analysis tools through the MCP protocol, handling tool registration and request routing.

## Functions

### list_tools()

Returns a list of available tools that can be called through the MCP server. Based on the imports, this function registers tools for:

- Repository indexing
- Code searching
- Wiki page operations
- Question answering
- Deep research
- Export functionality

### call_tool(name: str, arguments: dict)

Handles incoming tool calls by routing them to appropriate handler functions. Takes a tool name and arguments dictionary, then delegates to the corresponding handler from the `local_deepwiki.handlers` module.

**Parameters:**
- `name`: The name of the tool to execute
- `arguments`: Dictionary containing the arguments for the tool

### main()

The main entry point function that sets up and runs the MCP server using stdio transport.

### run()

Executes the server application by calling the main function.

## Related Components

This file integrates with several other components:

- **ToolHandler**: Main handler class from the handlers module
- **Handler Functions**: Various specific handlers including:
  - [`handle_ask_question`](handlers.md)
  - [`handle_deep_research`](handlers.md)
  - [`handle_export_wiki_html`](handlers.md)
  - [`handle_export_wiki_pdf`](handlers.md)
  - [`handle_index_repository`](handlers.md)
  - [`handle_read_wiki_page`](handlers.md)
  - [`handle_read_wiki_structure`](handlers.md)
  - [`handle_search_code`](handlers.md)
- **Logging**: Uses the logging module for application logging
- **MCP Framework**: Built on the Model Context Protocol server framework with stdio transport

## Usage

The server is designed to be run as a standalone application that communicates through standard input/output, making it compatible with MCP clients that can spawn and communicate with subprocess-based servers.

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
<summary>View Source (lines 31-222)</summary>

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
            description="Perform deep research on a codebase question using multi-step reasoning. Unlike ask_question (single retrieval), this performs query decomposition, parallel retrieval, gap analysis, and comprehensive synthesis. Best for complex architectural questions.",
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
            description="Semantic search across the indexed codebase. Returns relevant code chunks with similarity scores.",
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
                        "description": "Optional language filter",
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
    ]
```

</details>

#### `call_tool`

`@server.call_tool()`

```python
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]
```

Handle tool calls.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | - | - |
| `arguments` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`



<details>
<summary>View Source (lines 240-254)</summary>

```python
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"Tool call received: {name}")
    logger.debug(f"Tool arguments: {arguments}")

    # Special handling for deep_research (needs server context for progress)
    if name == "deep_research":
        return await handle_deep_research(arguments, server=server)

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
<summary>View Source (lines 257-269)</summary>

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
<summary>View Source (lines 261-267)</summary>

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
    N5[handler]
    N6[list_tools]
    N7[main]
    N8[run]
    N9[stdio_server]
    N6 --> N1
    N2 --> N4
    N2 --> N0
    N2 --> N5
    N7 --> N9
    N7 --> N8
    N7 --> N3
    N8 --> N9
    N8 --> N8
    N8 --> N3
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9 func
```

## Relevant Source Files

- `src/local_deepwiki/server.py:31-222`
