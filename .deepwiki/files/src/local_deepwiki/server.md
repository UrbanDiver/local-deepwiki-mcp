# File Overview

This file implements the main server logic for the Local DeepWiki application. It sets up the MCP (Model Communication Protocol) server that handles various tools for indexing repositories, asking questions, reading wiki structures and pages, searching code, and exporting wiki content as HTML.

# Classes

## Config

The [Config](config.md) class holds configuration settings for the Local DeepWiki application. It manages parameters needed for repository indexing, embedding providers, LLM providers, and other core functionality.

## RepositoryIndexer

The RepositoryIndexer class is responsible for indexing repository content. It processes files and creates a searchable index that can be used for question answering and code search.

## VectorStore

The [VectorStore](core/vectorstore.md) class manages vector embeddings and provides search capabilities over indexed repository content. It stores and retrieves embeddings for efficient similarity search.

# Functions

## list_tools

```python
async def list_tools() -> list[Tool]
```

Returns a list of available tools that can be called by the MCP server.

## call_tool

```python
async def call_tool(tool_name: str, tool_arguments: dict[str, Any]) -> Any
```

Calls a specific tool with the given arguments. This function routes tool calls to their respective handlers.

## handle_index_repository

```python
async def handle_index_repository(
    repo_path: str,
    config_path: str | None = None
) -> dict[str, Any]
```

Indexes a repository at the specified path. Returns a dictionary with indexing results.

Parameters:
- `repo_path` (str): Path to the repository to index
- `config_path` (str | None): Optional path to configuration file

## handle_ask_question

```python
async def handle_ask_question(
    question: str,
    repo_path: str
) -> dict[str, Any]
```

Answers a question about the indexed repository content.

Parameters:
- `question` (str): The question to answer
- `repo_path` (str): Path to the repository that was indexed

## handle_read_wiki_structure

```python
async def handle_read_wiki_structure(
    repo_path: str
) -> dict[str, Any]
```

Reads the wiki structure for the specified repository.

Parameters:
- `repo_path` (str): Path to the repository

## handle_read_wiki_page

```python
async def handle_read_wiki_page(
    repo_path: str,
    page_path: str
) -> dict[str, Any]
```

Reads a specific wiki page from the repository.

Parameters:
- `repo_path` (str): Path to the repository
- `page_path` (str): Path to the wiki page to read

## handle_search_code

```python
async def handle_search_code(
    query: str,
    repo_path: str
) -> dict[str, Any]
```

Searches for code snippets matching the query in the repository.

Parameters:
- `query` (str): Search query
- `repo_path` (str): Path to the repository to search

## handle_export_wiki_html

```python
async def handle_export_wiki_html(
    repo_path: str,
    output_path: str
) -> dict[str, Any]
```

Exports the wiki content as HTML.

Parameters:
- `repo_path` (str): Path to the repository
- `output_path` (str): Path where the HTML output should be saved

## progress_callback

```python
def progress_callback(progress: float, total: float, message: str) -> None
```

Callback function for reporting indexing progress.

Parameters:
- `progress` (float): Current progress value
- `total` (float): Total progress value
- `message` (str): Progress message

# Usage Examples

## Starting the Server

```python
async def main():
    server = Server("local_deepwiki")

    # Register the tools
    server.tool("index_repository", handle_index_repository)
    server.tool("ask_question", handle_ask_question)
    server.tool("read_wiki_structure", handle_read_wiki_structure)
    server.tool("read_wiki_page", handle_read_wiki_page)
    server.tool("search_code", handle_search_code)
    server.tool("export_wiki_html", handle_export_wiki_html)

    # Run the server
    async with stdio_server():
        await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## Indexing a Repository

```python
result = await handle_index_repository(
    repo_path="/path/to/repo",
    config_path="/path/to/config.json"
)
```

## Asking a Question

```python
result = await handle_ask_question(
    question="What is the purpose of this repository?",
    repo_path="/path/to/repo"
)
```

# Related Components

This file works with several core components:

- **[WikiGenerator](generators/wiki.md)**: Used for generating wiki content (imported but not directly implemented in this file)
- **[Config](config.md)**: Configuration management (imported and used)
- **RepositoryIndexer**: Repository indexing functionality (imported and used)
- **[VectorStore](core/vectorstore.md)**: Vector storage and search (imported and used)
- **get_embedding_provider**: Embedding provider factory (imported and used)
- **get_llm_provider**: LLM provider factory (imported and used)
- **WikiStructure**: Wiki structure model (imported and used)

The file also depends on the `mcp` library for implementing the Model Communication Protocol server functionality.

## API Reference

### Functions

#### `list_tools`

`@server.list_tools()`

```python
async def list_tools() -> list[Tool]
```

List available tools.

**Returns:** `list[Tool]`


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


#### `handle_index_repository`

```python
async def handle_index_repository(args: dict[str, Any]) -> list[TextContent]
```

Handle index_repository tool call.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`


#### `progress_callback`

```python
def progress_callback(msg: str, current: int, total: int)
```


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `msg` | `str` | - | - |
| `current` | `int` | - | - |
| `total` | `int` | - | - |


#### `handle_ask_question`

```python
async def handle_ask_question(args: dict[str, Any]) -> list[TextContent]
```

Handle ask_question tool call.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`


#### `handle_read_wiki_structure`

```python
async def handle_read_wiki_structure(args: dict[str, Any]) -> list[TextContent]
```

Handle read_wiki_structure tool call.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`


#### `handle_read_wiki_page`

```python
async def handle_read_wiki_page(args: dict[str, Any]) -> list[TextContent]
```

Handle read_wiki_page tool call.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`


#### `handle_search_code`

```python
async def handle_search_code(args: dict[str, Any]) -> list[TextContent]
```

Handle search_code tool call.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`


#### `handle_export_wiki_html`

```python
async def handle_export_wiki_html(args: dict[str, Any]) -> list[TextContent]
```

Handle export_wiki_html tool call.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | `dict[str, Any]` | - | - |

**Returns:** `list[TextContent]`


#### `main`

```python
def main()
```

Main entry point for the MCP server.


#### `run`

```python
async def run()
```



## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[RepositoryIndexer]
    N2[TextContent]
    N3[Tool]
    N4[VectorStore]
    N5[call_tool]
    N6[create_initialization_options]
    N7[dumps]
    N8[exists]
    N9[generate]
    N10[generate_wiki]
    N11[get_config]
    N12[get_embedding_provider]
    N13[get_llm_provider]
    N14[get_vector_db_path]
    N15[get_wiki_path]
    N16[handle_ask_question]
    N17[handle_export_wiki_html]
    N18[handle_index_repository]
    N19[handle_read_wiki_page]
    N20[handle_read_wiki_structure]
    N21[handle_search_code]
    N22[is_dir]
    N23[list_tools]
    N24[main]
    N25[read_text]
    N26[resolve]
    N27[run]
    N28[search]
    N29[stdio_server]
    N23 --> N3
    N5 --> N18
    N5 --> N16
    N5 --> N20
    N5 --> N19
    N5 --> N21
    N5 --> N17
    N5 --> N2
    N18 --> N26
    N18 --> N0
    N18 --> N8
    N18 --> N2
    N18 --> N22
    N18 --> N11
    N18 --> N1
    N18 --> N10
    N18 --> N7
    N16 --> N26
    N16 --> N0
    N16 --> N11
    N16 --> N15
    N16 --> N14
    N16 --> N8
    N16 --> N2
    N16 --> N12
    N16 --> N4
    N16 --> N28
    N16 --> N13
    N16 --> N9
    N16 --> N7
    N20 --> N26
    N20 --> N0
    N20 --> N8
    N20 --> N2
    N20 --> N25
    N20 --> N7
    N19 --> N26
    N19 --> N0
    N19 --> N2
    N19 --> N8
    N19 --> N25
    N21 --> N26
    N21 --> N0
    N21 --> N11
    N21 --> N14
    N21 --> N8
    N21 --> N2
    N21 --> N12
    N21 --> N4
    N21 --> N28
    N21 --> N7
    N17 --> N26
    N17 --> N0
    N17 --> N8
    N17 --> N2
    N17 --> N7
    N24 --> N29
    N24 --> N27
    N24 --> N6
    N27 --> N29
    N27 --> N27
    N27 --> N6
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
```

## Relevant Source Files

- `src/local_deepwiki/server.py:24-162`

## See Also

- [wiki](generators/wiki.md) - dependency
- [vectorstore](core/vectorstore.md) - dependency
- [config](config.md) - dependency
- [html](export/html.md) - dependency
- [chunker](core/chunker.md) - shares 4 dependencies
