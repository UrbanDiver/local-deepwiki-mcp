# Handlers Module Documentation

## Module Purpose

The handlers module contains the implementation of all MCP (Model Control Protocol) tool handlers for the Local DeepWiki MCP Server. These handlers implement the core functionality of the system, including repository indexing, Q&A capabilities, code analysis, research workflows, and web server operations.

The module organizes handlers into specialized submodules based on their function:
- Core question answering (`core.py`)
- Agentic workflows (`agentic.py`, `agentic_data.py`) 
- Analysis tools (`analysis.py`, `analysis_*` files)
- Codemap generation (`codemap.py`)
- Deep research capabilities (`research.py`)
- Session state management (`session_state.py`)
- Web server operations (`web_server.py`)

## Key Classes and Functions

### Core Handlers
- **[handle_ask_question](../files/src/local_deepwiki/handlers/core.md)** - Handles the `ask_question` tool for RAG-based Q&A
- **[handle_index_repository](../files/src/local_deepwiki/handlers/indexing.md)** - Handles repository indexing (defined in `indexing.py`)
- **[handle_deep_research](../files/src/local_deepwiki/handlers/research.md)** - Handles multi-step deep research workflows (defined in `research.py`)
- **[handle_generate_codemap](../files/src/local_deepwiki/handlers/codemap.md)** - Handles codemap generation (defined in `codemap.py`)

### Agentic Handlers
- **[handle_suggest_next_actions](../files/src/local_deepwiki/handlers/agentic.md)** - Suggests next actions based on session state and repository indexing status
- **_answer_seems_insufficient** - Helper function to determine if an answer is insufficient

### Analysis Handlers  
- **[handle_search_wiki](../files/src/local_deepwiki/handlers/analysis_search.md)** - Handles wiki search functionality
- **[handle_fuzzy_search](../files/src/local_deepwiki/handlers/analysis_search.md)** - Handles fuzzy name matching for search suggestions
- **[handle_explain_entity](../files/src/local_deepwiki/handlers/analysis_entity.md)** - Explains code entities using context and LLMs
- **[handle_impact_analysis](../files/src/local_deepwiki/handlers/analysis_entity.md)** - Analyzes impact of changes to code entities
- **[handle_analyze_diff](../files/src/local_deepwiki/handlers/analysis_diff.md)** - Analyzes git diff changes
- **[handle_ask_about_diff](../files/src/local_deepwiki/handlers/analysis_diff.md)** - Answers questions about specific diffs
- **[handle_get_project_manifest](../files/src/local_deepwiki/handlers/analysis_metadata.md)** - Retrieves project metadata and structure
- **[handle_get_file_context](../files/src/local_deepwiki/handlers/analysis_metadata.md)** - Gets contextual information for files
- **[handle_get_wiki_stats](../files/src/local_deepwiki/handlers/analysis_metadata.md)** - Gets statistics about the generated wiki
- **[handle_get_complexity_metrics](../files/src/local_deepwiki/handlers/analysis_metadata.md)** - Gets code complexity metrics

### Research Handlers
- **[handle_list_research_checkpoints](../files/src/local_deepwiki/handlers/research.md)** - Lists research checkpoints
- **[handle_cancel_research](../files/src/local_deepwiki/handlers/research.md)** - Cancels ongoing research
- **[handle_resume_research](../files/src/local_deepwiki/handlers/research.md)** - Resumes cancelled research
- **[handle_get_operation_progress](../files/src/local_deepwiki/handlers/research.md)** - Gets progress of ongoing operations

### Web Server Handlers
- **[handle_serve_wiki](../files/src/local_deepwiki/handlers/web_server.md)** - Starts the web server for wiki browsing
- **[handle_stop_wiki_server](../files/src/local_deepwiki/handlers/web_server.md)** - Stops the running web server

### Session State Management
- **[record_index](../files/src/local_deepwiki/handlers/session_state.md)** - Records that a repository was indexed during this session
- **[record_tool_call](../files/src/local_deepwiki/handlers/session_state.md)** - Records tool calls for session tracking
- **[is_repo_indexed](../files/src/local_deepwiki/handlers/session_state.md)** - Checks if a repository was indexed in current session
- **[get_session_state](../files/src/local_deepwiki/handlers/session_state.md)** - Returns snapshot of current session state

### Helper Functions
- **_check_forbidden_dirs** - Validates directory paths against forbidden patterns (defined in `_export_validation.py`)
- **_load_index_status** - Loads index status information (defined in `_index_helpers.py`)
- **[wrap_tool_response](../files/src/local_deepwiki/handlers/_response.md)** - Wraps tool responses for consistent output formatting (defined in `_response.py`)
- **_make_tool_message** - Creates tool messages for LLM prompts (defined in `prompts.py`)

## How Components Interact

The handlers module is structured around the MCP server architecture where individual tool handlers are registered and called by the server when tools are invoked. The flow typically follows:

1. An MCP client calls a tool (e.g., `ask_question`)
2. The server routes to the appropriate handler function in this module
3. The handler validates inputs, performs required operations (indexing, LLM queries, etc.)
4. Results are returned as structured responses that may include:
   - TextContent objects with JSON-formatted results
   - Progress notifications for long-running operations
   - Error handling through the `_error_handling` system

The module integrates with core components like:
- **Indexing pipeline** (via `indexing.py`) for repository processing
- **[VectorStore](../files/src/local_deepwiki/core/vectorstore/store.md)** (via `core/vectorstore.py`) for semantic search and retrieval  
- **LLM providers** (via `providers/llm.py`) for natural language generation
- **Deep research pipeline** (via `core/deep_research.py`) for complex multi-step analysis

Session state tracking allows tools like `suggest_next_actions` to provide context-aware recommendations without filesystem checks.

## Usage Examples

### Basic Question Answering```python
from local_deepwiki.handlers.core import handle_ask_question

# Ask a question about the codebase
args = {
    "repo_path": "/path/to/repo",
    "question": "What does this function do?"
}
response = await handle_ask_question(args)
print(response[0].text)  # JSON result with answer
```
### Repository Indexing```python
from local_deepwiki.handlers.indexing import handle_index_repository

args = {
    "repo_path": "/path/to/repo",
    "wiki_path": "/path/to/wiki"
}
response = await handle_index_repository(args)
# Returns success/failure status
```
### Deep Research```python
from local_deepwiki.handlers.research import handle_deep_research

args = {
    "repo_path": "/path/to/repo", 
    "question": "Analyze the security implications of this code change",
    "max_chunks": 100
}
response = await handle_deep_research(args)
# Returns multi-step research results as JSON
```
### Web Server Operations```python
from local_deepwiki.handlers.web_server import handle_serve_wiki

args = {
    "wiki_path": "/path/to/wiki",
    "port": 8080
}
response = await handle_serve_wiki(args)
# Starts web server for wiki browsing
```
## Dependencies

This module depends on several core components:

- **core modules**: `indexer.py`, `vectorstore.py`, `deep_research.py`, `git_utils.py`
- **providers**: `llm.py`, `embeddings.py`  
- **models**: `foundation.py`, `research_progress.py`, `deep_research_args.py`
- **utilities**: `audit.py`, `events.py`, `validation.py`, `rate_limiter.py`
- **external libraries**: `mcp`, `pydantic`, `tree-sitter`, `LanceDB`

The module also imports from other handler submodules to re-export functionality, such as:
- `analysis_architecture.py` for architecture analysis tools
- `analysis_diff.py` for diff analysis tools  
- `analysis_entity.py` for entity analysis tools
- `analysis_metadata.py` for metadata analysis tools
- `analysis_search.py` for search tools
- `session_state.py` for session tracking

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/handlers/session_state.py:20-27`](../files/src/local_deepwiki/handlers/session_state.md)
- [`src/local_deepwiki/handlers/agentic_data.py:108-122`](../files/src/local_deepwiki/handlers/agentic_data.md)
- [`src/local_deepwiki/handlers/analysis.py`](../files/src/local_deepwiki/handlers/analysis.md)
- [`src/local_deepwiki/handlers/research.py:41-61`](../files/src/local_deepwiki/handlers/research.md)
- [`src/local_deepwiki/handlers/agentic.py:50-186`](../files/src/local_deepwiki/handlers/agentic.md)
- `src/local_deepwiki/handlers/__init__.py`
- [`src/local_deepwiki/handlers/analysis_search.py:35-46`](../files/src/local_deepwiki/handlers/analysis_search.md)
- [`src/local_deepwiki/handlers/_response.py:11-36`](../files/src/local_deepwiki/handlers/_response.md)
- [`src/local_deepwiki/handlers/analysis_entity.py:34-43`](../files/src/local_deepwiki/handlers/analysis_entity.md)
- [`src/local_deepwiki/handlers/analysis_metadata.py:38-96`](../files/src/local_deepwiki/handlers/analysis_metadata.md)


*Showing 10 of 26 source files.*
