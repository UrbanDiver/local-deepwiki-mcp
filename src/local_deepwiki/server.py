"""MCP server for local DeepWiki functionality."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from local_deepwiki.handlers import (
    ToolHandler,
    handle_analyze_diff,
    handle_analyze_architecture,
    handle_ask_about_diff,
    handle_ask_question,
    handle_batch_explain_entities,
    handle_cancel_research,
    handle_compare_architecture,
    handle_find_tools,
    handle_deep_research,
    handle_detect_secrets,
    handle_detect_stale_docs,
    handle_explain_entity,
    handle_export_wiki_html,
    handle_export_wiki_pdf,
    handle_fuzzy_search,
    handle_generate_codemap,
    handle_get_api_docs,
    handle_get_architecture_health,
    handle_get_architecture_summary,
    handle_get_call_graph,
    handle_get_changelog,
    handle_get_complexity_metrics,
    handle_get_coupling_metrics,
    handle_get_coverage,
    handle_get_cross_module_dependencies,
    handle_get_design_smells,
    handle_get_diagrams,
    handle_get_file_context,
    handle_get_glossary,
    handle_get_hotspots,
    handle_get_index_status,
    handle_get_inheritance,
    handle_get_layer_dependencies,
    handle_get_module_health,
    handle_get_operation_progress,
    handle_get_project_manifest,
    handle_get_status,
    handle_get_test_examples,
    handle_get_wiki_stats,
    handle_impact_analysis,
    handle_index_repository,
    handle_list_indexed_repos,
    handle_list_research_checkpoints,
    handle_query_codebase,
    handle_read_wiki_page,
    handle_read_wiki_structure,
    handle_resume_research,
    handle_run_workflow,
    handle_search_code,
    handle_search_wiki,
    handle_serve_wiki,
    handle_stop_wiki_server,
    handle_suggest_codemap_topics,
    handle_suggest_next_actions,
)
from local_deepwiki.handlers.prompts import register_prompt_handlers
from local_deepwiki.handlers.resources import register_resource_handlers
from local_deepwiki.logging import get_logger
from local_deepwiki.server_tool_defs import TOOL_DEFINITIONS

logger = get_logger(__name__)


# Create the MCP server
server = Server("local-deepwiki")

# Register MCP Resource protocol handlers
register_resource_handlers(server)

# Register MCP Prompt protocol handlers
register_prompt_handlers(server)


@server.list_tools()
async def list_tools() -> list:
    """List available tools."""
    return list(TOOL_DEFINITIONS)


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
    "search_wiki": handle_search_wiki,
    "get_project_manifest": handle_get_project_manifest,
    "get_file_context": handle_get_file_context,
    "fuzzy_search": handle_fuzzy_search,
    "get_status": handle_get_status,
    "get_wiki_stats": handle_get_wiki_stats,
    "explain_entity": handle_explain_entity,
    "impact_analysis": handle_impact_analysis,
    "get_complexity_metrics": handle_get_complexity_metrics,
    "get_layer_dependencies": handle_get_layer_dependencies,
    "get_architecture_summary": handle_get_architecture_summary,
    "get_hotspots": handle_get_hotspots,
    "get_cross_module_dependencies": handle_get_cross_module_dependencies,
    "get_coupling_metrics": handle_get_coupling_metrics,
    "get_design_smells": handle_get_design_smells,
    "get_architecture_health": handle_get_architecture_health,
    "analyze_architecture": handle_analyze_architecture,
    "compare_architecture": handle_compare_architecture,
    "get_module_health": handle_get_module_health,
    "analyze_diff": handle_analyze_diff,
    "ask_about_diff": handle_ask_about_diff,
    "generate_codemap": handle_generate_codemap,
    "suggest_codemap_topics": handle_suggest_codemap_topics,
    "suggest_next_actions": handle_suggest_next_actions,
    "run_workflow": handle_run_workflow,
    "batch_explain_entities": handle_batch_explain_entities,
    "query_codebase": handle_query_codebase,
    "find_tools": handle_find_tools,
    "serve_wiki": handle_serve_wiki,
    "stop_wiki_server": handle_stop_wiki_server,
}

# Tools that need server context for progress streaming
PROGRESS_ENABLED_TOOLS = frozenset(
    {"index_repository", "deep_research", "resume_research"}
)


def _validate_tool_handler_consistency() -> None:
    """Verify that every tool definition has a handler and vice-versa.

    Raises ``RuntimeError`` at startup if the sets diverge, preventing
    silent regressions where a new tool is defined but never dispatched
    (or a handler exists for a tool that was removed).
    """
    handler_names = set(TOOL_HANDLERS.keys()) | set(PROGRESS_ENABLED_TOOLS)
    definition_names = {t.name for t in TOOL_DEFINITIONS}

    missing_handlers = definition_names - handler_names
    extra_handlers = handler_names - definition_names

    errors: list[str] = []
    if missing_handlers:
        errors.append(f"Tool definitions without a handler: {sorted(missing_handlers)}")
    if extra_handlers:
        errors.append(f"Handlers without a tool definition: {sorted(extra_handlers)}")
    if errors:
        raise RuntimeError(
            "Tool-handler consistency check failed:\n  " + "\n  ".join(errors)
        )
    logger.debug(
        "Tool-handler consistency OK: %d tools validated", len(definition_names)
    )


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    from local_deepwiki.handlers.session_state import record_tool_call

    logger.info("Tool call received: %s", name)
    logger.debug("Tool arguments: %s", arguments)
    record_tool_call(name)

    # Special handling for tools that need server context for progress streaming
    if name == "index_repository":
        return await handle_index_repository(arguments, server=server)

    if name == "deep_research":
        return await handle_deep_research(arguments, server=server)

    if name == "resume_research":
        return await handle_resume_research(arguments, server=server)

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        logger.warning("Unknown tool requested: %s", name)
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return await handler(arguments)


def _log_security_posture() -> None:
    """Log the current security configuration at startup."""
    from local_deepwiki.security.access_control import RBACMode, get_access_controller

    controller = get_access_controller()
    mode = controller.mode
    if mode == RBACMode.DISABLED:
        logger.warning(
            "SECURITY: RBAC is DISABLED — no permission checks will be performed"
        )
    elif mode == RBACMode.PERMISSIVE:
        logger.info(
            "SECURITY: RBAC is PERMISSIVE — unauthenticated requests are allowed"
        )
    else:
        logger.info("SECURITY: RBAC is ENFORCED — all requests require authentication")


def main() -> None:
    """Main entry point for the MCP server."""
    logger.info("Starting local-deepwiki MCP server")
    _validate_tool_handler_consistency()
    _log_security_posture()

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
