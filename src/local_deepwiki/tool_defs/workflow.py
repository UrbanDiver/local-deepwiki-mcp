"""Workflow, codemap, agentic, and web server MCP tool definitions.

Tools: generate_codemap, suggest_codemap_topics, suggest_next_actions,
run_workflow, batch_explain_entities, query_codebase, find_tools,
serve_wiki, stop_wiki_server.
"""

from __future__ import annotations

from mcp.types import Tool

from local_deepwiki.tool_defs.annotations import _READ_ONLY, _SIDE_EFFECT

WORKFLOW_TOOLS: list[Tool] = [
    Tool(
        name="generate_codemap",
        description=(
            "Generate a Windsurf-style codemap: a focused execution-flow map with "
            "Mermaid diagram and narrative trace for a question or topic. Shows how "
            "code flows across files with file paths and line numbers. Best for "
            "understanding 'How does X work?' questions."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "query": "How does request handling work?"}'
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
                    "description": (
                        "Question or topic to map (e.g., 'How does authentication work?', "
                        "'Trace the request handling pipeline')"
                    ),
                },
                "entry_point": {
                    "type": "string",
                    "description": (
                        "Optional function/class to start from (e.g., 'handle_ask_question'). "
                        "Auto-discovered if not provided."
                    ),
                },
                "focus": {
                    "type": "string",
                    "enum": ["execution_flow", "data_flow", "dependency_chain"],
                    "description": "Focus mode: execution_flow (calls), data_flow (transformations), dependency_chain (imports). Default: execution_flow",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Max call graph traversal depth (default: 5, range: 1-10)",
                },
                "max_nodes": {
                    "type": "integer",
                    "description": "Max nodes in the codemap (default: 30, range: 5-60)",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="suggest_codemap_topics",
        description=(
            "Suggest interesting codemap topics for a repository based on call graph hubs, "
            "core modules, and common entry patterns. Use before generate_codemap to discover "
            "what flows are worth exploring."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "max_suggestions": {
                    "type": "integer",
                    "description": "Maximum topic suggestions to return (default: 10, range: 1-30)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="suggest_next_actions",
        description=(
            "Suggest which tools to use next based on tools already used. "
            "Returns ranked suggestions with reasons. No LLM calls - uses a "
            "static decision tree for instant responses."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tools_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tool names the agent has already used in this session",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context about what the agent is trying to accomplish",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository (used to check if wiki exists)",
                },
            },
            "required": [],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="run_workflow",
        description=(
            "Run a pre-built multi-step workflow. Available presets: 'onboarding' "
            "(project overview), 'security_audit' (secrets + complexity), "
            "'full_analysis' (stats + coverage + stale + secrets), 'quick_refresh' "
            "(stale docs + changelog)."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "workflow": "onboarding"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "workflow": {
                    "type": "string",
                    "enum": [
                        "onboarding",
                        "security_audit",
                        "full_analysis",
                        "quick_refresh",
                    ],
                    "description": "Workflow preset to run",
                },
            },
            "required": ["repo_path", "workflow"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="batch_explain_entities",
        description=(
            "Explain multiple code entities in a single call. Loads the search "
            "index once and looks up each entity name. More efficient than "
            "calling explain_entity repeatedly."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "entity_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity names to explain (max 20)",
                    "maxItems": 20,
                },
                "depth": {
                    "type": "string",
                    "enum": ["shallow", "full"],
                    "description": "Depth of explanation: 'shallow' (search index only, default) or 'full' (calls explain_entity for each)",
                },
            },
            "required": ["repo_path", "entity_names"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="query_codebase",
        description=(
            "Smart query that combines ask_question with automatic escalation "
            "to deep_research when the initial answer is insufficient. Single "
            "entry point for codebase Q&A."
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
                    "description": "Natural language question about the codebase",
                },
                "auto_escalate": {
                    "type": "boolean",
                    "description": "Automatically escalate to deep_research if initial answer is insufficient (default: true)",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="find_tools",
        description=(
            "Search for tools by capability description. Returns ranked matches "
            "with tool name, description, and whether indexing is required. "
            "Useful when an agent needs to discover which tool to use."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Capability description to search for (e.g., 'security scanning', 'code visualization')",
                },
            },
            "required": ["query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="serve_wiki",
        description=(
            "Start the interactive wiki web server for a .deepwiki directory. "
            "Launches a Flask app with chat, search, codemap explorer, and research UI. "
            "The server runs as a subprocess and can be stopped with stop_wiki_server."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"wiki_path": "/path/to/repo/.deepwiki"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "wiki_path": {
                    "type": "string",
                    "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                },
                "host": {
                    "type": "string",
                    "description": "Host to bind to (default: 127.0.0.1, loopback only)",
                    "default": "127.0.0.1",
                },
                "port": {
                    "type": "integer",
                    "description": "Port to bind to (default: 8080, range: 1024-65535)",
                    "default": 8080,
                    "minimum": 1024,
                    "maximum": 65535,
                },
                "open_browser": {
                    "type": "boolean",
                    "description": "Open the wiki in the default browser after starting (default: false)",
                    "default": False,
                },
            },
            "required": ["wiki_path"],
        },
        annotations=_SIDE_EFFECT,
    ),
    Tool(
        name="stop_wiki_server",
        description=(
            "Stop a previously started wiki web server. Gracefully terminates "
            "the server process. If no server is found on the specified port, "
            "returns a list of currently running servers."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "description": "Port of the wiki server to stop (default: 8080)",
                    "default": 8080,
                    "minimum": 1024,
                    "maximum": 65535,
                },
                "wiki_path": {
                    "type": "string",
                    "description": "Optional wiki path to identify which server to stop",
                },
            },
            "required": [],
        },
        annotations=_SIDE_EFFECT,
    ),
]
