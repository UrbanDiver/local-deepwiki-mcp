"""MCP server for local DeepWiki functionality."""

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from local_deepwiki.handlers import (
    ToolHandler,
    handle_ask_question,
    handle_cancel_research,
    handle_deep_research,
    handle_detect_secrets,
    handle_detect_stale_docs,
    handle_export_wiki_html,
    handle_export_wiki_pdf,
    handle_get_api_docs,
    handle_get_call_graph,
    handle_get_changelog,
    handle_get_coverage,
    handle_get_diagrams,
    handle_get_glossary,
    handle_get_index_status,
    handle_get_inheritance,
    handle_get_operation_progress,
    handle_get_test_examples,
    handle_index_repository,
    handle_list_indexed_repos,
    handle_list_research_checkpoints,
    handle_read_wiki_page,
    handle_read_wiki_structure,
    handle_resume_research,
    handle_search_code,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


# Create the MCP server
server = Server("local-deepwiki")


@server.list_tools()
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
                        "description": "Maximum number of code chunks for context (default: 10)",
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


# Tool handler dispatch dictionary
# Maps tool names to their async handler functions
# Note: index_repository, deep_research, and resume_research are handled specially for progress streaming
TOOL_HANDLERS: dict[str, ToolHandler] = {
    "ask_question": handle_ask_question,
    "read_wiki_structure": handle_read_wiki_structure,
    "read_wiki_page": handle_read_wiki_page,
    "search_code": handle_search_code,
    "export_wiki_html": handle_export_wiki_html,
    "export_wiki_pdf": handle_export_wiki_pdf,
    "list_research_checkpoints": handle_list_research_checkpoints,
    "cancel_research": handle_cancel_research,
    "get_operation_progress": handle_get_operation_progress,
    "get_glossary": handle_get_glossary,
    "get_diagrams": handle_get_diagrams,
    "get_inheritance": handle_get_inheritance,
    "get_call_graph": handle_get_call_graph,
    "get_coverage": handle_get_coverage,
    "detect_stale_docs": handle_detect_stale_docs,
    "get_changelog": handle_get_changelog,
    "detect_secrets": handle_detect_secrets,
    "get_test_examples": handle_get_test_examples,
    "get_api_docs": handle_get_api_docs,
    "list_indexed_repos": handle_list_indexed_repos,
    "get_index_status": handle_get_index_status,
}

# Tools that need server context for progress streaming
PROGRESS_ENABLED_TOOLS = {"index_repository", "deep_research", "resume_research"}


@server.call_tool()
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


if __name__ == "__main__":
    main()
