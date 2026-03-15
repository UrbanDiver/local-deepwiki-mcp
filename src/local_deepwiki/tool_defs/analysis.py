"""Analysis and search MCP tool definitions.

Tools: search_wiki, get_project_manifest, get_file_context, fuzzy_search,
get_wiki_stats, explain_entity, impact_analysis, get_complexity_metrics,
analyze_diff, ask_about_diff, get_layer_dependencies,
get_architecture_summary.
"""

from __future__ import annotations

from mcp.types import Tool

from local_deepwiki.tool_defs.annotations import _READ_ONLY

ANALYSIS_TOOLS: tuple[Tool, ...] = (
    Tool(
        name="search_wiki",
        description=(
            "Full-text search across wiki pages and code entities. Searches "
            "titles, headings, code terms, descriptions, and keywords. "
            "Returns ranked matches."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 20, max: 100)",
                },
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by type: 'page', 'function', 'class', 'method'",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_project_manifest",
        description=(
            "Get parsed project metadata from package manifest files "
            "(pyproject.toml, package.json, Cargo.toml, go.mod, etc.). "
            "Returns name, version, dependencies, scripts, tech stack summary."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Use cached manifest if available (default: true)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_file_context",
        description=(
            "Get rich context for a source file: imports, callers (who uses "
            "this file), related files, and type definitions used. Helps "
            "understand a file's role in the codebase."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root (e.g., 'src/local_deepwiki/server.py')",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="fuzzy_search",
        description=(
            "Fuzzy name matching for functions, classes, and methods using "
            "Levenshtein distance. Returns 'Did you mean?' suggestions, file "
            "locations, and similarity scores. Great for finding entities when "
            "you don't know the exact name."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": "Name to search for (function, class, method)",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum similarity score 0.0-1.0 (default: 0.6)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 10, max: 50)",
                },
                "entity_type": {
                    "type": "string",
                    "description": "Filter: 'function', 'class', 'method', or 'module'",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_wiki_stats",
        description=(
            "Get a wiki health dashboard with index stats, page counts, "
            "search index size, coverage data, and wiki status - all in "
            "a single call."
            "\n\nRequires: index_repository must be called first."
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="explain_entity",
        description=(
            "Get a comprehensive explanation of a function, class, or method "
            "by combining glossary info, call graph, inheritance tree, test "
            "examples, and API docs into a single response."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "entity_name": "MyClass"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Name of function, class, or method to explain",
                },
                "include_call_graph": {
                    "type": "boolean",
                    "description": "Include call graph info - callers and callees (default: true)",
                },
                "include_inheritance": {
                    "type": "boolean",
                    "description": "Include inheritance tree for classes (default: true)",
                },
                "include_test_examples": {
                    "type": "boolean",
                    "description": "Include usage examples from tests (default: true)",
                },
                "include_api_docs": {
                    "type": "boolean",
                    "description": "Include API signature details (default: true)",
                },
                "max_test_examples": {
                    "type": "integer",
                    "description": "Max test examples to include (default: 3, range: 1-10)",
                },
            },
            "required": ["repo_path", "entity_name"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="impact_analysis",
        description=(
            "Analyze the blast radius of changes to a file or entity. Combines "
            "reverse call graph, inheritance dependents, file-level imports, and "
            "affected wiki pages to help understand impact before making changes."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "file_path": "src/auth.py"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root to analyze impact for",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Optional: specific function/class name to narrow analysis",
                },
                "include_reverse_calls": {
                    "type": "boolean",
                    "description": "Include reverse call graph - who calls functions in this file (default: true)",
                },
                "include_dependents": {
                    "type": "boolean",
                    "description": "Include files that import from this file (default: true)",
                },
                "include_inheritance": {
                    "type": "boolean",
                    "description": "Include classes that inherit from classes in this file (default: true)",
                },
                "include_wiki_pages": {
                    "type": "boolean",
                    "description": "Include wiki pages that document this file (default: true)",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_complexity_metrics",
        description=(
            "Analyze code complexity for a source file using tree-sitter AST "
            "parsing. Returns function/class counts, line metrics, cyclomatic "
            "complexity, nesting depth, and parameter counts."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root to analyze",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="analyze_diff",
        description=(
            "Analyze git diff between two refs and map changed files to "
            "affected wiki pages and code entities. Helps understand "
            "documentation impact of code changes."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository (must be a git repo)",
                },
                "base_ref": {
                    "type": "string",
                    "description": "Git ref to diff from (default: HEAD~1)",
                },
                "head_ref": {
                    "type": "string",
                    "description": "Git ref to diff to (default: HEAD)",
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Include diff content for each file (default: false)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="ask_about_diff",
        description=(
            "Ask questions about recent code changes using RAG. Combines git "
            "diff with vector search context and LLM synthesis to answer "
            "questions like 'What changed?', 'Are there any bugs?', or "
            "'What's the impact?'."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository (must be a git repo)",
                },
                "question": {
                    "type": "string",
                    "description": "Question about the code changes",
                },
                "base_ref": {
                    "type": "string",
                    "description": "Git ref to diff from (default: HEAD~1)",
                },
                "head_ref": {
                    "type": "string",
                    "description": "Git ref to diff to (default: HEAD)",
                },
                "max_context": {
                    "type": "integer",
                    "description": "Maximum code chunks for context (default: 10, max: 30)",
                },
            },
            "required": ["repo_path", "question"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_layer_dependencies",
        description=(
            "Analyze architectural layer dependencies in a Python codebase. "
            "Categorizes files into layers (web, handlers, services, generators, "
            "core, providers, models) and detects upward dependency violations "
            "where lower layers import from higher layers. Returns layer file "
            "counts, dependency edges, and violations."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to analyze",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_architecture_summary",
        description=(
            "Get a composite architecture overview combining layer dependency "
            "analysis with file metrics. Returns layer violation counts, file "
            "counts per layer, total files and lines, largest files, and files "
            "exceeding 800 lines."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to analyze",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
)
