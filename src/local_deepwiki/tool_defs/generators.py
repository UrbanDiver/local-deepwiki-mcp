"""Generator and research MCP tool definitions.

Tools: list_research_checkpoints, cancel_research, resume_research,
get_operation_progress, get_glossary, get_diagrams, get_inheritance,
get_call_graph, get_coverage, detect_stale_docs, get_changelog,
detect_secrets, get_test_examples, get_api_docs, list_indexed_repos,
get_index_status.
"""

from __future__ import annotations

from mcp.types import Tool

from local_deepwiki.tool_defs.annotations import _READ_ONLY, _STATEFUL

GENERATOR_TOOLS: list[Tool] = [
    Tool(
        name="list_research_checkpoints",
        description=(
            "List all research checkpoints for a repository. Shows incomplete "
            "and cancelled research sessions that can be resumed using the "
            "deep_research tool with resume_research_id."
            "\n\nRequires: index_repository must be called first."
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="cancel_research",
        description=(
            "Cancel an active deep research session and save its checkpoint. "
            "The research can be resumed later using the deep_research tool "
            "with resume_research_id."
            "\n\nRequires: index_repository must be called first."
        ),
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
        annotations=_STATEFUL,
    ),
    Tool(
        name="resume_research",
        description=(
            "Resume a previously interrupted deep research session from its "
            "checkpoint. This is a convenience wrapper - you can also use "
            "deep_research with resume_research_id directly."
            "\n\nRequires: index_repository must be called first."
        ),
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
        annotations=_STATEFUL,
    ),
    Tool(
        name="get_operation_progress",
        description=(
            "Get progress for active long-running operations. Supports "
            "polling-based progress tracking for clients that cannot receive "
            "push notifications. Returns current progress, ETA, and phase information."
            "\n\nNo prior indexing required."
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_glossary",
        description=(
            "Get a searchable glossary of all code entities (classes, functions, "
            "methods) in an indexed repository. Useful for discovering what's in "
            "the codebase."
            "\n\nRequires: index_repository must be called first."
        ),
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
                "file_path": {
                    "type": "string",
                    "description": "Filter to entities from a specific file (relative path)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum entities to return (default: 100, max: 5000)",
                    "default": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of entities to skip for pagination (default: 0)",
                    "default": 0,
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_diagrams",
        description=(
            "Generate Mermaid diagrams for an indexed repository. Supports class "
            "diagrams, dependency graphs, module overviews, language distribution "
            "pie charts, and sequence diagrams."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "diagram_type": "class"}'
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_inheritance",
        description=(
            "Get class inheritance hierarchy trees for an indexed repository. "
            "Shows parent-child relationships, abstract classes, and generates "
            "a Mermaid inheritance diagram."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "search": {
                    "type": "string",
                    "description": "Filter classes by name (case-insensitive substring)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum classes to return (default: 100, max: 5000)",
                    "default": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of classes to skip for pagination (default: 0)",
                    "default": 0,
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_call_graph",
        description=(
            "Get function call graphs showing which functions call which. Can "
            "analyze a specific file or the entire repository. Returns a "
            "Mermaid flowchart."
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
                    "description": "Specific file to analyze (relative to repo root). If omitted, analyzes entire repo.",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_coverage",
        description=(
            "Get documentation coverage report for an indexed repository. "
            "Shows which classes, functions, and methods have docstrings "
            "and which don't."
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
        name="detect_stale_docs",
        description=(
            "Find wiki pages that may be outdated because their source files "
            "have been modified since the documentation was generated."
            "\n\nRequires: index_repository must be called first."
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_changelog",
        description=(
            "Extract recent git commit history as a formatted changelog. "
            "Groups commits by date and includes file change information."
            "\n\nNo prior indexing required."
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="detect_secrets",
        description=(
            "Scan a repository for hardcoded credentials and secrets (API keys, "
            "tokens, passwords, private keys). Returns findings with type, "
            "location, confidence, and remediation advice."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to scan",
                },
                "exclude_tests": {
                    "type": "boolean",
                    "description": "Exclude test files from scan results (files matching test_*, *_test.*, tests/, etc.). Default: false",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_test_examples",
        description=(
            "Find usage examples for a function or class by searching test "
            "files in the indexed repository. Returns code snippets showing "
            "how the entity is used in tests."
            "\n\nRequires: index_repository must be called first."
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
                    "description": "Name of the function or class to find examples for",
                },
                "max_examples": {
                    "type": "integer",
                    "description": "Maximum number of examples to return (default: 5)",
                },
            },
            "required": ["repo_path", "entity_name"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_api_docs",
        description=(
            "Get API documentation with function signatures, parameters, return "
            "types, and docstrings for a specific file. Uses tree-sitter AST "
            "parsing for accuracy."
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
                    "description": "File path relative to repo root to get API docs for",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="list_indexed_repos",
        description=(
            "Discover all indexed repositories under a given directory. "
            "Searches for .deepwiki directories and returns index metadata "
            "for each."
            "\n\nNo prior indexing required."
        ),
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
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_index_status",
        description=(
            "Get index statistics for a repository without re-indexing. "
            "Shows file count, chunk count, languages, and when it was "
            "last indexed."
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
]
