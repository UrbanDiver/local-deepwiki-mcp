# Module: tool_defs

## Module Purpose

The `tool_defs` module provides MCP (Model Control Protocol) tool definitions for the Local DeepWiki MCP Server. It organizes various tool implementations into logical groups for maintainability and re-exports them for use by the server's [`list_tools`](../files/src/local_deepwiki/server.md) handler.

The module serves as a central registry of available tools, with each sub-module containing specific tool definitions grouped by functionality:
- Core tools (repository indexing, Q&A, wiki reading/exporting)
- Generator tools (documentation generation, research analysis)
- Analysis and search tools (wiki search, code context, complexity metrics)
- Workflow and agentic tools (codemap generation, workflow execution)
- Annotations for tool categorization

## Key Classes and Functions

### Module: `tool_defs.__init__`

This is the main module that re-exports all tool definitions from submodules.

**Re-exports:**
- `Tool` from `mcp.types`
- `CORE_TOOLS` from `local_deepwiki.tool_defs.core`
- `ANALYSIS_TOOLS` from `local_deepwiki.tool_defs.analysis`
- `GENERATOR_TOOLS` from `local_deepwiki.tool_defs.generators`
- `WORKFLOW_TOOLS` from `local_deepwiki.tool_defs.workflow`
- Tool annotation constants from `local_deepwiki.tool_defs.annotations`

### Module: `tool_defs.core`

Contains core MCP tools for repository indexing, Q&A, and wiki operations.

**Tools:**
- `index_repository` - Indexes a repository for documentation generation
- `ask_question` - Answers questions about the codebase using RAG
- `deep_research` - Performs multi-step reasoning research on the codebase
- `read_wiki_structure` - Reads the wiki's directory structure
- `read_wiki_page` - Reads a specific wiki page content
- `search_code` - Searches code files for specific patterns or concepts
- `export_wiki_html` - Exports the wiki as static HTML
- `export_wiki_pdf` - Exports the wiki as PDF

**Annotations:**
- `_READ_ONLY` - Tool annotation indicating read-only access
- `_STATEFUL` - Tool annotation indicating stateful operations
- `_WRITE_SAFE` - Tool annotation indicating safe write operations

### Module: `tool_defs.analysis`

Contains analysis and search MCP tools for querying and understanding the codebase.

**Tools:**
- `search_wiki` - Searches wiki content for relevant information
- `get_project_manifest` - Retrieves project manifest information
- `get_file_context` - Gets context around a specific file or code entity
- `fuzzy_search` - Performs fuzzy name matching for search suggestions
- `get_wiki_stats` - Retrieves statistics about the wiki content
- `explain_entity` - Explains a specific code entity in detail
- `impact_analysis` - Analyzes the impact of changes or modifications
- `get_complexity_metrics` - Gets complexity metrics for code entities
- `analyze_diff` - Analyzes differences between code versions
- `ask_about_diff` - Answers questions about code changes or diffs
- `get_layer_dependencies` - Gets dependencies between architectural layers
- `get_architecture_summary` - Gets a summary of the project's architecture

**Annotations:**
- `_READ_ONLY` - Tool annotation indicating read-only access

### Module: `tool_defs.generators`

Contains generator and research MCP tools for documentation generation and code analysis.

**Tools:**
- [`list_research_checkpoints`](../files/src/local_deepwiki/core/deep_research/checkpoints.md) - Lists research checkpoints for ongoing work
- [`cancel_research`](../files/src/local_deepwiki/core/deep_research/checkpoints.md) - Cancels a running research task
- `resume_research` - Resumes a paused research task
- `get_operation_progress` - Gets progress information for ongoing operations
- `get_glossary` - Generates or retrieves a project glossary
- `get_diagrams` - Generates diagrams (e.g., architecture, class diagrams)
- `get_inheritance` - Retrieves inheritance relationships in code
- `get_call_graph` - Generates call graphs showing function relationships
- `get_coverage` - Gets code coverage information
- `detect_stale_docs` - Detects outdated documentation
- `get_changelog` - Retrieves project changelog information
- `detect_secrets` - Scans for hardcoded secrets or credentials
- `get_test_examples` - Retrieves test examples for code entities
- `get_api_docs` - Generates API documentation
- `list_indexed_repos` - Lists repositories that have been indexed
- `get_index_status` - Gets the status of indexing operations

**Annotations:**
- `_READ_ONLY` - Tool annotation indicating read-only access
- `_STATEFUL` - Tool annotation indicating stateful operations

### Module: `tool_defs.workflow`

Contains workflow, codemap, agentic, and web server MCP tools.

**Tools:**
- [`generate_codemap`](../files/src/local_deepwiki/generators/codemap/generator.md) - Generates a codemap for the codebase
- `suggest_codemap_topics` - Suggests topics for codemap generation
- `suggest_next_actions` - Suggests next actions based on current state
- `run_workflow` - Executes a predefined workflow (e.g., security audit)
- `batch_explain_entities` - Explains multiple code entities in batch
- `query_codebase` - Queries the entire codebase for information
- `find_tools` - Finds tools relevant to a specific query or task
- `serve_wiki` - Starts a web server to serve the wiki
- `stop_wiki_server` - Stops the running wiki web server

**Annotations:**
- `_READ_ONLY` - Tool annotation indicating read-only access
- `_SIDE_EFFECT` - Tool annotation indicating side-effect operations

### Module: `tool_defs.annotations`

Provides shared MCP tool annotation constants used across other modules.

**Constants:**
- `_READ_ONLY` - Annotation for tools that only read data
- `_SIDE_EFFECT` - Annotation for tools that have side effects (e.g., modify state)
- `_STATEFUL` - Annotation for tools that maintain state between calls
- `_WRITE_SAFE` - Annotation for tools that perform safe write operations

## How Components Interact

The `tool_defs` module acts as a centralized registry for all MCP tools available in the Local DeepWiki server. The main `__init__.py` file imports and re-exports tool definitions from specialized submodules, creating a unified interface for the server to expose tools via its [`list_tools`](../files/src/local_deepwiki/server.md) handler.

Each submodule contains specific tool definitions grouped by functionality:
1. **Core tools** (`core.py`) handle fundamental repository operations and Q&A
2. **Analysis tools** (`analysis.py`) provide code understanding and search capabilities
3. **Generator tools** (`generators.py`) focus on documentation generation and research
4. **Workflow tools** (`workflow.py`) manage codemap generation, agentic workflows, and web server operations

The annotation constants in `annotations.py` are used throughout the other modules to categorize tool behavior, helping the system understand whether a tool should be treated as read-only, stateful, or having side effects.

## Usage Examples

### Importing All Tools```python
from local_deepwiki.tool_defs import (
    CORE_TOOLS,
    ANALYSIS_TOOLS,
    GENERATOR_TOOLS,
    WORKFLOW_TOOLS
)

# Combine all tools for server registration
all_tools = CORE_TOOLS + ANALYSIS_TOOLS + GENERATOR_TOOLS + WORKFLOW_TOOLS
```
### Using Specific Tool Groups```python
from local_deepwiki.tool_defs import CORE_TOOLS, ANALYSIS_TOOLS

# Register core tools with MCP server
server.register_tools(CORE_TOOLS)

# Register analysis tools for code understanding
server.register_tools(ANALYSIS_TOOLS)
```
### Accessing Annotations```python
from local_deepwiki.tool_defs.annotations import _READ_ONLY, _STATEFUL

# Use annotations when defining new tools
tool = Tool(
    name="my_tool",
    description="A sample tool",
    inputSchema={...},
    annotations=[_READ_ONLY, _STATEFUL]
)
```
## Dependencies

This module depends on:
- `mcp.types` - Provides the `Tool` and `ToolAnnotations` types
- `local_deepwiki.tool_defs.core` - Core repository indexing and Q&A tools
- `local_deepwiki.tool_defs.analysis` - Analysis and search tools
- `local_deepwiki.tool_defs.generators` - Documentation generation and research tools
- `local_deepwiki.tool_defs.workflow` - Workflow, codemap, and web server tools
- `local_deepwiki.tool_defs.annotations` - Shared tool annotation constants

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/tool_defs/analysis.py`](../files/src/local_deepwiki/tool_defs/analysis.md)
- `src/local_deepwiki/tool_defs/__init__.py`
- [`src/local_deepwiki/tool_defs/generators.py`](../files/src/local_deepwiki/tool_defs/generators.md)
- [`src/local_deepwiki/tool_defs/core.py`](../files/src/local_deepwiki/tool_defs/core.md)
- [`src/local_deepwiki/tool_defs/annotations.py`](../files/src/local_deepwiki/tool_defs/annotations.md)
- [`src/local_deepwiki/tool_defs/workflow.py`](../files/src/local_deepwiki/tool_defs/workflow.md)
