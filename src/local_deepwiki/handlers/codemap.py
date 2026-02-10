"""Codemap tool handlers: generate_codemap and suggest_codemap_topics."""

import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    GenerateCodemapArgs,
    SuggestCodemapTopicsArgs,
    Permission,
    _create_vector_store,
    _load_index_status,
    get_access_controller,
    get_embedding_provider,
    get_rate_limiter,
    handle_tool_errors,
    logger,
    path_not_found_error,
    validate_query_parameters,
)


@handle_tool_errors
async def handle_generate_codemap(args: dict[str, Any]) -> list[TextContent]:
    """Handle generate_codemap tool call.

    Generates a Windsurf-style codemap: a Mermaid diagram + narrative trace
    for a given question/topic, showing the execution flow through the codebase.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = GenerateCodemapArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    validate_query_parameters(validated.query, str(repo_path), 30)

    _index_status, wiki_path, config = _load_index_status(repo_path)

    vector_store = _create_vector_store(repo_path, config)

    from local_deepwiki.generators.codemap import CodemapFocus, generate_codemap
    from local_deepwiki.providers.llm import get_cached_llm_provider

    cache_path = wiki_path / "llm_cache.lance"
    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=get_embedding_provider(config.embedding),
        cache_config=config.llm_cache,
        llm_config=config.llm,
    )

    focus = CodemapFocus(validated.focus.value)

    rate_limiter = get_rate_limiter()
    async with rate_limiter:
        codemap_result = await generate_codemap(
            query=validated.query,
            vector_store=vector_store,
            repo_path=repo_path,
            llm=llm,
            entry_point=validated.entry_point,
            focus=focus,
            max_depth=validated.max_depth,
            max_nodes=validated.max_nodes,
        )

    result = {
        "status": "success",
        "query": codemap_result.query,
        "focus": codemap_result.focus,
        "entry_point": codemap_result.entry_point,
        "mermaid_diagram": codemap_result.mermaid_diagram,
        "narrative": codemap_result.narrative,
        "nodes": codemap_result.nodes,
        "edges": codemap_result.edges,
        "summary": {
            "files_involved": codemap_result.files_involved,
            "total_nodes": codemap_result.total_nodes,
            "total_edges": codemap_result.total_edges,
            "cross_file_edges": codemap_result.cross_file_edges,
        },
    }

    logger.info(
        f"Codemap: '{validated.query[:50]}' -> {codemap_result.total_nodes} nodes, "
        f"{len(codemap_result.files_involved)} files"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_suggest_codemap_topics(args: dict[str, Any]) -> list[TextContent]:
    """Handle suggest_codemap_topics tool call.

    Suggests interesting codemap entry points based on call graph hubs,
    core modules, and common entry patterns.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = SuggestCodemapTopicsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _index_status, _wiki_path, config = _load_index_status(repo_path)

    vector_store = _create_vector_store(repo_path, config)

    from local_deepwiki.generators.codemap import suggest_topics

    suggestions = await suggest_topics(
        vector_store=vector_store,
        repo_path=repo_path,
        max_suggestions=validated.max_suggestions,
    )

    result = {
        "status": "success",
        "suggestions": suggestions,
        "total": len(suggestions),
    }

    logger.info(f"Codemap topics: {len(suggestions)} suggestions for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
