"""MCP Prompt handlers for guided multi-step workflows.

Provides pre-built prompt sequences that guide agents through common tasks
like onboarding to a new codebase, running security audits, and investigating
specific code areas.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
)

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from mcp.server import Server

logger = get_logger(__name__)


_PROMPTS = [
    Prompt(
        name="onboarding",
        description="Get started with a new codebase. Indexes the repository (if needed), explores the wiki structure, and shows key stats.",
        arguments=[
            PromptArgument(
                name="repo_path",
                description="Absolute path to the repository",
                required=True,
            ),
        ],
    ),
    Prompt(
        name="security_audit",
        description="Run a security review. Scans for hardcoded secrets, checks dependency metadata, and identifies complexity hotspots.",
        arguments=[
            PromptArgument(
                name="repo_path",
                description="Absolute path to the repository",
                required=True,
            ),
        ],
    ),
    Prompt(
        name="investigate_area",
        description="Deep-dive into a specific code area. Searches for relevant code, generates a codemap, and explains key entities.",
        arguments=[
            PromptArgument(
                name="repo_path",
                description="Absolute path to the repository",
                required=True,
            ),
            PromptArgument(
                name="query",
                description="What to investigate (e.g., 'authentication flow', 'database layer')",
                required=True,
            ),
        ],
    ),
]


def _make_tool_message(tool_name: str, args: dict[str, str]) -> PromptMessage:
    """Build a user PromptMessage instructing the agent to call a tool.

    Args:
        tool_name: Name of the tool to call.
        args: Arguments to pass as JSON.

    Returns:
        A PromptMessage with role="user".
    """
    import json

    args_str = json.dumps(args, indent=2)
    return PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=f"Call the `{tool_name}` tool with these arguments:\n```json\n{args_str}\n```",
        ),
    )


def _get_onboarding_messages(repo_path: str) -> list[PromptMessage]:
    """Build the onboarding prompt sequence."""
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"I want to understand the codebase at `{repo_path}`. "
                "Please index it (if not already indexed), then show me the wiki structure and key stats.",
            ),
        ),
        _make_tool_message("index_repository", {"repo_path": repo_path}),
        _make_tool_message(
            "read_wiki_structure", {"wiki_path": f"{repo_path}/.deepwiki"}
        ),
        _make_tool_message("get_wiki_stats", {"repo_path": repo_path}),
    ]


def _get_security_audit_messages(repo_path: str) -> list[PromptMessage]:
    """Build the security audit prompt sequence."""
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"Run a security review of `{repo_path}`. "
                "Scan for hardcoded secrets, check project dependencies, and identify complexity hotspots.",
            ),
        ),
        _make_tool_message("detect_secrets", {"repo_path": repo_path}),
        _make_tool_message("get_project_manifest", {"repo_path": repo_path}),
        _make_tool_message(
            "run_workflow",
            {"repo_path": repo_path, "workflow": "security_audit"},
        ),
    ]


def _get_investigate_area_messages(repo_path: str, query: str) -> list[PromptMessage]:
    """Build the investigate_area prompt sequence."""
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=f"I want to investigate '{query}' in `{repo_path}`. "
                "Search for relevant code, generate a codemap, and explain key entities.",
            ),
        ),
        _make_tool_message("search_code", {"repo_path": repo_path, "query": query}),
        _make_tool_message(
            "generate_codemap", {"repo_path": repo_path, "query": query}
        ),
    ]


def register_prompt_handlers(server: Server) -> None:
    """Register MCP Prompt protocol handlers on the server.

    Args:
        server: The MCP Server instance to register handlers on.
    """

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return list(_PROMPTS)

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        arguments = arguments or {}

        if name == "onboarding":
            repo_path = arguments.get("repo_path", "")
            if not repo_path:
                raise ValueError("repo_path argument is required")
            return GetPromptResult(
                description="Onboard to a new codebase",
                messages=_get_onboarding_messages(repo_path),
            )

        if name == "security_audit":
            repo_path = arguments.get("repo_path", "")
            if not repo_path:
                raise ValueError("repo_path argument is required")
            return GetPromptResult(
                description="Security audit of the codebase",
                messages=_get_security_audit_messages(repo_path),
            )

        if name == "investigate_area":
            repo_path = arguments.get("repo_path", "")
            query = arguments.get("query", "")
            if not repo_path:
                raise ValueError("repo_path argument is required")
            if not query:
                raise ValueError("query argument is required")
            return GetPromptResult(
                description=f"Investigate: {query}",
                messages=_get_investigate_area_messages(repo_path, query),
            )

        raise ValueError(f"Unknown prompt: {name}")
