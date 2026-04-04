# Module: local_deepwiki

## Module Purpose

The `local_deepwiki` module provides the core functionality for a local code intelligence and documentation system. It serves as the foundation for analyzing codebases, generating wikis, and providing intelligent code search and analysis capabilities. The module is structured around an MCP (Model Control Protocol) server that exposes various tools for code analysis, documentation generation, and project understanding.

## Key Classes and Functions

### Core Server Components

- **[`list_tools`](../files/src/local_deepwiki/server.md)** - Asynchronously lists all available tools in the system
- **[`call_tool`](../files/src/local_deepwiki/server.md)** - Handles tool calls by routing them to appropriate handlers
- **`main`** - Main entry point for starting the MCP server
- **`run`** - Async function that runs the server using stdio transport

### Tool Definitions

- **`TOOL_DEFINITIONS`** - Collection of all available tool definitions
- **`TOOL_HANDLERS`** - Mapping of tool names to their handler functions
- **`PROGRESS_ENABLED_TOOLS`** - Set of tools that support progress reporting

### Analysis and Generation Functions

- **[`analyze_duplication`](../files/src/local_deepwiki/generators/analysis/duplication.md)** - Main function for detecting code duplication (both Type 1 and Type 2 clones)
- **[`detect_type1_clones`](../files/src/local_deepwiki/generators/analysis/duplication.md)** - Detects exact code clones using line-based fingerprinting
- **[`detect_type2_clones`](../files/src/local_deepwiki/generators/analysis/duplication.md)** - Detects structural clones by comparing function AST structure
- **`_normalize_line`** - Normalizes source lines for fingerprinting
- **`_build_fingerprints`** - Builds hash-to-location mappings from files
- **`_deduplicate_clone_group`** - Removes overlapping windows from clone groups
- **`_collect_node_types`** - Collects AST node types for structural analysis

### Data Models

The module re-exports various data models through `local_deepwiki.models`:
- **[`IndexRepositoryArgs`](../files/src/local_deepwiki/models/tool_args.md)** - Arguments for indexing repository operations
- **[`ProgressCallback`](../files/src/local_deepwiki/models/foundation.md)** - Callback for progress reporting
- **`ToolHandler`** - Type definition for tool handlers
- **[`WikiPage`](../files/src/local_deepwiki/export/streaming.md)** - Model for wiki page data
- And many others for various tool arguments and results

## How Components Interact

The module operates as an MCP server that:
1. Defines a collection of tools in `TOOL_DEFINITIONS`
2. Maps tool names to handler functions in `TOOL_HANDLERS`
3. Validates tool-handler consistency at startup
4. Receives tool calls through the [`call_tool`](../files/src/local_deepwiki/server.md) function
5. Routes calls to appropriate handlers, with special handling for tools that require server context (like indexing and research)
6. Provides analysis capabilities through functions like [`analyze_duplication`](../files/src/local_deepwiki/generators/analysis/duplication.md) that perform code analysis
7. Uses data models for consistent data flow between components

The server framework handles the communication layer while the core logic resides in the analysis and generation functions that process code repositories and generate insights.

## Usage Examples

### Starting the Server
```python
# Start the MCP server
if __name__ == "__main__":
    main()
```

### Using Analysis Functions
```python
from local_deepwiki.generators.analysis.duplication import analyze_duplication

# Analyze code duplication in a repository
result = analyze_duplication(
    repo_path="/path/to/repo",
    min_lines=10,
    top_n=10,
    exclude_tests=True
)
print(result["stats"])
```

### Listing Available Tools
```python
import asyncio
from local_deepwiki.server import list_tools

# Get list of available tools
tools = asyncio.run(list_tools())
print(tools)
```

## Dependencies

This module depends on:
- `asyncio` - For asynchronous operations
- `mcp` - Model Control Protocol server implementation
- `local_deepwiki.handlers` - Tool handler implementations
- `local_deepwiki.models` - Data models and tool argument definitions
- `local_deepwiki.tool_defs` - Tool definitions
- `local_deepwiki.logging` - Logging configuration
- `local_deepwiki.security.access_control` - Security and access control
- `local_deepwiki.handlers.session_state` - Session state management
- `local_deepwiki.generators.analysis.duplication` - Duplication analysis functions
- `local_deepwiki.core.chunk_extractors` - Code chunk extraction utilities
- `local_deepwiki.core.parser.ast_utils` - AST utilities
- `local_deepwiki.core.parser.code_parser` - Code parsing utilities
- `local_deepwiki.generators.analysis.source_filter` - Source file filtering utilities

The module also imports various standard library modules including `argparse`, `collections`, `contextlib`, `dataclasses`, `datetime`, `enum`, `json`, `logging`, `math`, `operator`, and `typing` for general functionality.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/server.py:98-100`](../files/src/local_deepwiki/server.md)
- `src/local_deepwiki/models/__init__.py`
- [`src/local_deepwiki/tool_defs/analysis.py`](../files/src/local_deepwiki/tool_defs/analysis.md)
- [`src/local_deepwiki/generators/analysis/duplication.py:26-37`](../files/src/local_deepwiki/generators/analysis/duplication.md)
- [`src/local_deepwiki/generators/analysis/architecture_health.py:55-123`](../files/src/local_deepwiki/generators/analysis/architecture_health.md)
- [`src/local_deepwiki/generators/analysis/maintainability.py:69-79`](../files/src/local_deepwiki/generators/analysis/maintainability.md)
- [`src/local_deepwiki/models/tool_args.py:15-49`](../files/src/local_deepwiki/models/tool_args.md)
- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](../files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:34-39`](../files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/generators/analysis/churn.py:25-38`](../files/src/local_deepwiki/generators/analysis/churn.md)


*Showing 10 of 268 source files.*
