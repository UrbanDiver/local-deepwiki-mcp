"""Agentic tool handlers: workflow orchestration, action suggestions, batch operations."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    BatchExplainEntitiesArgs,
    Permission,
    QueryCodebaseArgs,
    RunWorkflowArgs,
    SuggestNextActionsArgs,
    _load_index_status,
    get_access_controller,
    handle_tool_errors,
    logger,
    path_not_found_error,
    wrap_tool_response,
)

# --- Tool graph for suggest_next_actions ---

TOOL_GRAPH: dict[str, list[dict[str, str]]] = {
    "index_repository": [
        {
            "tool": "read_wiki_structure",
            "reason": "Browse the generated wiki",
            "priority": "high",
        },
        {
            "tool": "get_wiki_stats",
            "reason": "Check wiki health and coverage",
            "priority": "high",
        },
        {
            "tool": "ask_question",
            "reason": "Ask questions about the codebase",
            "priority": "medium",
        },
    ],
    "ask_question": [
        {
            "tool": "explain_entity",
            "reason": "Deep-dive on a specific entity mentioned in the answer",
            "priority": "high",
        },
        {
            "tool": "deep_research",
            "reason": "Investigate the topic more thoroughly",
            "priority": "medium",
        },
        {
            "tool": "search_code",
            "reason": "Find related code snippets",
            "priority": "medium",
        },
    ],
    "search_code": [
        {
            "tool": "explain_entity",
            "reason": "Understand a found code entity",
            "priority": "high",
        },
        {
            "tool": "get_file_context",
            "reason": "See imports, callers, and related files",
            "priority": "high",
        },
        {
            "tool": "impact_analysis",
            "reason": "Assess blast radius of changes",
            "priority": "medium",
        },
    ],
    "read_wiki_structure": [
        {
            "tool": "read_wiki_page",
            "reason": "Read a specific wiki page",
            "priority": "high",
        },
        {
            "tool": "search_wiki",
            "reason": "Search across wiki content",
            "priority": "medium",
        },
        {
            "tool": "get_coverage",
            "reason": "Check documentation coverage",
            "priority": "low",
        },
    ],
    "explain_entity": [
        {
            "tool": "get_call_graph",
            "reason": "Visualize function call relationships",
            "priority": "high",
        },
        {
            "tool": "impact_analysis",
            "reason": "Assess change impact for this entity",
            "priority": "medium",
        },
        {
            "tool": "generate_codemap",
            "reason": "Trace execution flow through this entity",
            "priority": "medium",
        },
    ],
    "deep_research": [
        {
            "tool": "generate_codemap",
            "reason": "Visualize the execution flow",
            "priority": "high",
        },
        {
            "tool": "explain_entity",
            "reason": "Deep-dive on a specific entity",
            "priority": "medium",
        },
        {
            "tool": "search_code",
            "reason": "Find additional code context",
            "priority": "low",
        },
    ],
    "read_wiki_page": [
        {
            "tool": "explain_entity",
            "reason": "Understand an entity mentioned on the page",
            "priority": "high",
        },
        {
            "tool": "search_wiki",
            "reason": "Find related wiki pages",
            "priority": "medium",
        },
        {
            "tool": "get_file_context",
            "reason": "Explore the source file's role",
            "priority": "medium",
        },
    ],
    "generate_codemap": [
        {
            "tool": "explain_entity",
            "reason": "Deep-dive on a node in the codemap",
            "priority": "high",
        },
        {
            "tool": "impact_analysis",
            "reason": "Assess change impact for mapped code",
            "priority": "medium",
        },
        {
            "tool": "ask_question",
            "reason": "Ask follow-up questions about the flow",
            "priority": "medium",
        },
    ],
    "get_wiki_stats": [
        {
            "tool": "get_coverage",
            "reason": "Check documentation coverage details",
            "priority": "high",
        },
        {
            "tool": "detect_stale_docs",
            "reason": "Find outdated documentation",
            "priority": "medium",
        },
        {
            "tool": "suggest_codemap_topics",
            "reason": "Discover interesting code flows",
            "priority": "low",
        },
    ],
}


@handle_tool_errors
async def handle_suggest_next_actions(args: dict[str, Any]) -> list[TextContent]:
    """Suggest next tools to use based on what has already been used.

    Static decision tree — no LLM calls required.
    """
    try:
        validated = SuggestNextActionsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    tools_used = validated.tools_used
    repo_path_str = validated.repo_path

    # If no tools used, suggest starting points
    if not tools_used:
        # Check if wiki exists
        has_wiki = False
        if repo_path_str:
            from local_deepwiki.config import get_config

            config = get_config()
            wiki_path = config.get_wiki_path(Path(repo_path_str).resolve())
            has_wiki = wiki_path.exists()

        if has_wiki:
            suggestions = [
                {
                    "tool": "read_wiki_structure",
                    "reason": "Browse existing wiki documentation",
                    "priority": "high",
                },
                {
                    "tool": "ask_question",
                    "reason": "Ask questions about the codebase",
                    "priority": "high",
                },
                {
                    "tool": "get_wiki_stats",
                    "reason": "Check wiki health dashboard",
                    "priority": "medium",
                },
            ]
        else:
            suggestions = [
                {
                    "tool": "index_repository",
                    "reason": "Index the repository first to generate wiki",
                    "priority": "high",
                },
                {
                    "tool": "get_project_manifest",
                    "reason": "Check project metadata",
                    "priority": "medium",
                },
            ]

        data = {"suggestions": suggestions, "based_on": "no_tools_used"}
        return [
            TextContent(
                type="text", text=wrap_tool_response("suggest_next_actions", data)
            )
        ]

    # Collect suggestions from the most recently used tools
    seen_tools: set[str] = set()
    suggestions: list[dict[str, str]] = []

    # Process in reverse order (most recent first)
    for tool_name in reversed(tools_used):
        graph_suggestions = TOOL_GRAPH.get(tool_name, [])
        for suggestion in graph_suggestions:
            if (
                suggestion["tool"] not in seen_tools
                and suggestion["tool"] not in tools_used
            ):
                seen_tools.add(suggestion["tool"])
                suggestions.append(suggestion)

    # If no specific suggestions, offer general ones
    if not suggestions:
        suggestions = [
            {
                "tool": "ask_question",
                "reason": "Ask questions about the codebase",
                "priority": "medium",
            },
            {
                "tool": "search_wiki",
                "reason": "Search across wiki content",
                "priority": "medium",
            },
            {
                "tool": "search_code",
                "reason": "Search for code snippets",
                "priority": "medium",
            },
        ]

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 2))

    data = {
        "suggestions": suggestions[:8],
        "based_on": tools_used[-3:],
    }
    return [
        TextContent(type="text", text=wrap_tool_response("suggest_next_actions", data))
    ]


# --- Workflow presets ---

WORKFLOW_PRESETS = {"onboarding", "security_audit", "full_analysis", "quick_refresh"}


@handle_tool_errors
async def handle_run_workflow(args: dict[str, Any]) -> list[TextContent]:
    """Run a pre-built multi-step workflow by calling existing handlers.

    Each step has independent error handling — failures produce an error
    entry but the workflow continues.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = RunWorkflowArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    workflow = validated.workflow

    if workflow not in WORKFLOW_PRESETS:
        from local_deepwiki.errors import ValidationError

        raise ValidationError(
            message=f"Unknown workflow: {workflow}",
            hint=f"Available workflows: {', '.join(sorted(WORKFLOW_PRESETS))}",
            field="workflow",
            value=workflow,
        )

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    logger.info("Running workflow '%s' for %s", workflow, repo_path)

    steps: list[dict[str, Any]] = []

    if workflow == "onboarding":
        steps = await _run_onboarding(str(repo_path))
    elif workflow == "security_audit":
        steps = await _run_security_audit(str(repo_path))
    elif workflow == "full_analysis":
        steps = await _run_full_analysis(str(repo_path))
    elif workflow == "quick_refresh":
        steps = await _run_quick_refresh(str(repo_path))

    data = {
        "workflow": workflow,
        "repo_path": str(repo_path),
        "steps": steps,
        "completed": sum(1 for s in steps if s.get("status") == "success"),
        "failed": sum(1 for s in steps if s.get("status") == "error"),
    }

    return [TextContent(type="text", text=wrap_tool_response("run_workflow", data))]


async def _run_step(
    handler_func: Any, step_name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Run a single workflow step with error handling.

    Args:
        handler_func: The async handler function to call.
        step_name: Human-readable step name for the result.
        args: Arguments to pass to the handler.

    Returns:
        Step result dict with status, name, and data or error.
    """
    try:
        result = await handler_func(args)
        # Extract text content from the result
        text = result[0].text if result else ""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": text[:500]}
        return {"step": step_name, "status": "success", "data": data}
    except Exception as e:  # noqa: BLE001
        logger.warning("Workflow step '%s' failed: %s", step_name, e)
        return {"step": step_name, "status": "error", "error": str(e)}


async def _run_onboarding(repo_path: str) -> list[dict[str, Any]]:
    """Run the onboarding workflow."""
    from local_deepwiki.handlers.analysis_metadata import (
        handle_get_project_manifest,
        handle_get_wiki_stats,
    )
    from local_deepwiki.handlers.codemap import handle_suggest_codemap_topics
    from local_deepwiki.handlers.core import handle_read_wiki_structure

    steps = []
    steps.append(
        await _run_step(
            handle_get_project_manifest,
            "get_project_manifest",
            {"repo_path": repo_path},
        )
    )

    # Check if wiki exists before reading structure
    from local_deepwiki.config import get_config

    config = get_config()
    wiki_path = config.get_wiki_path(Path(repo_path).resolve())

    if wiki_path.exists():
        steps.append(
            await _run_step(
                handle_read_wiki_structure,
                "read_wiki_structure",
                {"wiki_path": str(wiki_path)},
            )
        )
        steps.append(
            await _run_step(
                handle_get_wiki_stats, "get_wiki_stats", {"repo_path": repo_path}
            )
        )
        steps.append(
            await _run_step(
                handle_suggest_codemap_topics,
                "suggest_codemap_topics",
                {"repo_path": repo_path},
            )
        )
    else:
        steps.append(
            {
                "step": "read_wiki_structure",
                "status": "skipped",
                "reason": "Wiki not indexed yet",
            }
        )

    return steps


async def _run_security_audit(repo_path: str) -> list[dict[str, Any]]:
    """Run the security audit workflow."""
    from local_deepwiki.handlers.generators import handle_detect_secrets

    steps = []
    steps.append(
        await _run_step(
            handle_detect_secrets, "detect_secrets", {"repo_path": repo_path}
        )
    )

    # Get complexity metrics for the most complex files
    from local_deepwiki.handlers.analysis_metadata import handle_get_complexity_metrics

    # Try to find top-level source files
    repo = Path(repo_path)
    source_files = []
    for ext in ("*.py", "*.ts", "*.js", "*.go", "*.rs"):
        source_files.extend(repo.rglob(ext))
        if len(source_files) >= 5:
            break

    for src_file in source_files[:3]:
        rel_path = str(src_file.relative_to(repo))
        steps.append(
            await _run_step(
                handle_get_complexity_metrics,
                f"complexity:{rel_path}",
                {"repo_path": repo_path, "file_path": rel_path},
            )
        )

    return steps


async def _run_full_analysis(repo_path: str) -> list[dict[str, Any]]:
    """Run the full analysis workflow."""
    from local_deepwiki.handlers.analysis_metadata import handle_get_wiki_stats
    from local_deepwiki.handlers.generators import (
        handle_detect_secrets,
        handle_detect_stale_docs,
        handle_get_coverage,
    )

    steps = []
    steps.append(
        await _run_step(
            handle_get_wiki_stats, "get_wiki_stats", {"repo_path": repo_path}
        )
    )
    steps.append(
        await _run_step(handle_get_coverage, "get_coverage", {"repo_path": repo_path})
    )
    steps.append(
        await _run_step(
            handle_detect_stale_docs, "detect_stale_docs", {"repo_path": repo_path}
        )
    )
    steps.append(
        await _run_step(
            handle_detect_secrets, "detect_secrets", {"repo_path": repo_path}
        )
    )

    return steps


async def _run_quick_refresh(repo_path: str) -> list[dict[str, Any]]:
    """Run the quick refresh workflow."""
    from local_deepwiki.handlers.generators import (
        handle_detect_stale_docs,
        handle_get_changelog,
    )

    steps = []
    steps.append(
        await _run_step(
            handle_detect_stale_docs, "detect_stale_docs", {"repo_path": repo_path}
        )
    )
    steps.append(
        await _run_step(handle_get_changelog, "get_changelog", {"repo_path": repo_path})
    )

    return steps


@handle_tool_errors
async def handle_batch_explain_entities(args: dict[str, Any]) -> list[TextContent]:
    """Explain multiple entities in a single call.

    Loads the shared search.json once and looks up each entity.
    Uses asyncio.gather for concurrent processing.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = BatchExplainEntitiesArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    entity_names = validated.entity_names

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _index_status, wiki_path, _config = await _load_index_status(repo_path)

    # Load search.json once
    search_index_path = wiki_path / "search.json"
    if not search_index_path.exists():
        data = {
            "entities": [],
            "error": "Search index not found. Re-index the repository to generate it.",
        }
        return [
            TextContent(
                type="text", text=wrap_tool_response("batch_explain_entities", data)
            )
        ]

    search_content = search_index_path.read_text(encoding="utf-8")
    search_data = json.loads(search_content)
    all_entities = search_data.get("entities", [])

    # Build name index for fast lookups
    name_index: dict[str, list[dict]] = {}
    for entity in all_entities:
        name = (entity.get("name") or "").lower()
        display_name = (entity.get("display_name") or "").lower()
        for key in (name, display_name):
            if key:
                name_index.setdefault(key, []).append(entity)

    # Look up each requested entity
    results = []
    for entity_name in entity_names:
        matches = name_index.get(entity_name.lower(), [])
        if matches:
            results.append(
                {
                    "entity": entity_name,
                    "found": True,
                    "matches": [
                        {
                            "name": m.get("display_name", m.get("name")),
                            "type": m.get("entity_type"),
                            "file": m.get("file"),
                            "signature": m.get("signature", ""),
                            "description": m.get("description", ""),
                        }
                        for m in matches[:5]
                    ],
                }
            )
        else:
            results.append(
                {
                    "entity": entity_name,
                    "found": False,
                    "matches": [],
                }
            )

    data = {
        "repo_path": str(repo_path),
        "total_requested": len(entity_names),
        "total_found": sum(1 for r in results if r["found"]),
        "results": results,
    }

    return [
        TextContent(
            type="text", text=wrap_tool_response("batch_explain_entities", data)
        )
    ]


@handle_tool_errors
async def handle_query_codebase(args: dict[str, Any]) -> list[TextContent]:
    """Smart query that uses ask_question and optionally escalates to deep_research.

    If the initial answer is short (<200 chars) and auto_escalate is True,
    automatically escalates to deep_research for a more thorough answer.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = QueryCodebaseArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    query = validated.query
    auto_escalate = validated.auto_escalate

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.handlers.core import handle_ask_question

    # First try with ask_question (max_context=15 for more context)
    ask_result = await handle_ask_question(
        {
            "repo_path": str(repo_path),
            "question": query,
            "max_context": 15,
        }
    )

    # Parse the result
    ask_text = ask_result[0].text if ask_result else ""
    try:
        ask_data = json.loads(ask_text)
    except (json.JSONDecodeError, TypeError):
        ask_data = {"answer": ask_text}

    answer = ask_data.get("answer", "")
    escalated = False

    # Escalate if answer is short and auto_escalate is enabled
    if auto_escalate and len(answer) < 200:
        logger.info(
            "Answer too short (%d chars), escalating to deep_research", len(answer)
        )
        try:
            from local_deepwiki.handlers.research import handle_deep_research

            research_result = await handle_deep_research(
                {
                    "repo_path": str(repo_path),
                    "question": query,
                    "preset": "quick",
                }
            )
            research_text = research_result[0].text if research_result else ""
            try:
                research_data = json.loads(research_text)
            except (json.JSONDecodeError, TypeError):
                research_data = {"answer": research_text}

            ask_data = research_data
            escalated = True
        except Exception as e:  # noqa: BLE001
            logger.warning("Escalation to deep_research failed: %s", e)
            # Fall back to original answer

    data = {
        **ask_data,
        "escalated": escalated,
        "query": query,
    }

    hints = None
    if not escalated:
        hints = {
            "next_tools": [
                {"tool": "deep_research", "reason": "For more thorough analysis"},
                {
                    "tool": "explain_entity",
                    "reason": "To deep-dive on specific entities",
                },
            ]
        }

    return [
        TextContent(
            type="text", text=wrap_tool_response("query_codebase", data, hints=hints)
        )
    ]
