"""Agentic tool handlers: workflow orchestration, action suggestions, batch operations."""

from __future__ import annotations

import asyncio
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    BatchExplainEntitiesArgs,
    Permission,
    QueryCodebaseArgs,
    SuggestNextActionsArgs,
    _load_index_status,
    get_access_controller,
    handle_tool_errors,
    logger,
    path_not_found_error,
    wrap_tool_response,
)

# Re-export data constants and helpers for backward compatibility
from local_deepwiki.handlers.agentic_data import (  # noqa: F401
    TOOL_GRAPH,
    WORKFLOW_PRESETS,
    _INSUFFICIENT_PHRASES,
    _TOOL_KEYWORDS,
    _WORKFLOW_RUNNER_NAMES,
    _answer_seems_insufficient,
)

# Re-export workflow runners and handler for backward compatibility
from local_deepwiki.handlers.agentic_workflows import (  # noqa: F401
    _run_full_analysis,
    _run_onboarding,
    _run_quick_refresh,
    _run_security_audit,
    _run_step,
    handle_run_workflow,
)


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
        # Check if wiki exists (session state or filesystem)
        from local_deepwiki.handlers.session_state import is_repo_indexed

        has_wiki = False
        if repo_path_str:
            # Fast check: was it indexed in this session?
            if is_repo_indexed(str(Path(repo_path_str).resolve())):
                has_wiki = True
            else:
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

    # Boost suggestions matching context keywords (Item 5)
    context = validated.context
    if context:
        context_lower = context.lower()
        for suggestion in suggestions:
            tool_kws = _TOOL_KEYWORDS.get(suggestion["tool"], [])
            if any(kw in context_lower for kw in tool_kws):
                suggestion["priority"] = "high"

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 2))

    # Include session state summary for agent awareness
    from local_deepwiki.handlers.session_state import get_session_state

    session = get_session_state()

    data: dict[str, Any] = {
        "suggestions": suggestions[:8],
        "based_on": tools_used[-3:],
        "session": {
            "tool_call_count": session["tool_call_count"],
            "indexed_repos": list(session["indexed_repos"].keys()),
        },
    }
    if context:
        data["context_applied"] = True
    return [
        TextContent(type="text", text=wrap_tool_response("suggest_next_actions", data))
    ]


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
    depth = validated.depth

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _index_status, wiki_path, _config = await _load_index_status(repo_path)

    # Full depth: delegate to explain_entity for each name (Item 7)
    if depth == "full":
        from local_deepwiki.handlers.analysis_entity import handle_explain_entity

        async def _explain_one(name: str) -> dict[str, Any]:
            try:
                res = await handle_explain_entity(
                    {"repo_path": str(repo_path), "entity_name": name}
                )
                text = res[0].text if res else ""
                try:
                    return {"entity": name, "found": True, **json.loads(text)}
                except (json.JSONDecodeError, TypeError):
                    return {"entity": name, "found": True, "raw": text[:500]}
            except Exception as exc:  # noqa: BLE001
                return {"entity": name, "found": False, "error": str(exc)}

        results = await asyncio.gather(*[_explain_one(n) for n in entity_names])

        data: dict[str, Any] = {
            "repo_path": str(repo_path),
            "total_requested": len(entity_names),
            "total_found": sum(1 for r in results if r.get("found")),
            "depth": "full",
            "results": list(results),
        }
        return [
            TextContent(
                type="text",
                text=wrap_tool_response("batch_explain_entities", data),
            )
        ]

    # Shallow depth (default): search index lookup
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
    results_list = []
    for entity_name in entity_names:
        matches = name_index.get(entity_name.lower(), [])
        if matches:
            results_list.append(
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
            results_list.append(
                {
                    "entity": entity_name,
                    "found": False,
                    "matches": [],
                }
            )

    data = {
        "repo_path": str(repo_path),
        "total_requested": len(entity_names),
        "total_found": sum(1 for r in results_list if r["found"]),
        "depth": "shallow",
        "results": results_list,
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

    # First try with ask_question (max_context=15, agentic_rag for smarter retrieval)
    ask_result = await handle_ask_question(
        {
            "repo_path": str(repo_path),
            "question": query,
            "max_context": 15,
            "agentic_rag": True,
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

    # Escalate if answer seems insufficient and auto_escalate is enabled (Item 6)
    if auto_escalate and _answer_seems_insufficient(answer, query):
        logger.info("Answer seems insufficient, escalating to deep_research")
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


@handle_tool_errors
async def handle_find_tools(args: dict[str, Any]) -> list[TextContent]:
    """Search available tools by capability description.

    Scores each tool's description against the query using keyword matching.
    Returns the top-5 ranked tools with name, description, and whether they
    require prior indexing.
    """
    query = (args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")

    from local_deepwiki.server_tool_defs import TOOL_DEFINITIONS

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored: list[tuple[float, Any]] = []
    for tool_def in TOOL_DEFINITIONS:
        desc_lower = (tool_def.description or "").lower()
        name_lower = tool_def.name.lower()

        # Score: count matching query words in description + name
        score = sum(1 for w in query_words if w in desc_lower or w in name_lower)
        # Bonus for exact phrase match
        if query_lower in desc_lower:
            score += 3
        if query_lower in name_lower:
            score += 5

        if score > 0:
            requires_index = "Requires: index_repository" in (
                tool_def.description or ""
            )
            scored.append(
                (
                    score,
                    {
                        "tool": tool_def.name,
                        "description": (tool_def.description or "")[:200],
                        "requires_index": requires_index,
                        "score": score,
                    },
                )
            )

    scored.sort(key=itemgetter(0), reverse=True)
    top_results = [item for _, item in scored[:5]]

    data = {
        "query": query,
        "results": top_results,
        "total_tools": len(TOOL_DEFINITIONS),
    }
    return [TextContent(type="text", text=wrap_tool_response("find_tools", data))]
