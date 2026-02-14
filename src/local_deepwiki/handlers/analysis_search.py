"""Search-related analysis handlers: wiki search and fuzzy search."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

# Maximum file suggestions in fuzzy search
FILE_SUGGESTIONS_LIMIT = 3

from local_deepwiki.handlers._shared import (
    FuzzySearchArgs,
    Permission,
    SearchWikiArgs,
    _create_vector_store,
    _load_index_status,
    build_wiki_resource_uri,
    get_access_controller,
    handle_tool_errors,
    logger,
    make_tool_text_content,
    path_not_found_error,
    validate_query_parameters,
)


@handle_tool_errors
async def handle_search_wiki(args: dict[str, Any]) -> list[TextContent]:
    """Handle search_wiki tool call.

    Searches across wiki pages and code entities using the pre-built search.json index.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = SearchWikiArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    query = validated.query
    limit = validated.limit
    entity_types = validated.entity_types

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    # Validate query parameters (CWE-400 prevention)
    validate_query_parameters(query, str(repo_path), limit)

    query = query.lower()

    _index_status, wiki_path, _config = await _load_index_status(repo_path)

    search_index_path = wiki_path / "search.json"
    if not search_index_path.exists():
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "error": "Search index not found. Re-index the repository to generate it.",
                    },
                    indent=2,
                ),
            )
        ]

    search_content = await asyncio.to_thread(search_index_path.read_text)
    search_data = json.loads(search_content)
    pages = search_data.get("pages", [])
    entities = search_data.get("entities", [])

    matches: list[dict] = []

    # Search pages
    if entity_types is None or "page" in entity_types:
        for page in pages:
            score = 0.0
            title = (page.get("title") or "").lower()
            if query in title:
                score = 1.0
            elif any(query in h.lower() for h in page.get("headings", [])):
                score = 0.8
            elif any(query in t.lower() for t in page.get("terms", [])):
                score = 0.6
            elif query in (page.get("snippet") or "").lower():
                score = 0.4

            if score > 0:
                page_match: dict[str, Any] = {
                    "type": "page",
                    "title": page.get("title"),
                    "path": page.get("path"),
                    "snippet": page.get("snippet", ""),
                    "score": score,
                }
                page_path_str = page.get("path", "")
                if page_path_str:
                    page_match["wiki_resource"] = build_wiki_resource_uri(
                        wiki_path, page_path_str
                    )
                matches.append(page_match)

    # Search entities
    allowed_entity_types = None
    if entity_types is not None:
        allowed_entity_types = [t for t in entity_types if t != "page"]

    if entity_types is None or allowed_entity_types:
        for entity in entities:
            if (
                allowed_entity_types
                and entity.get("entity_type") not in allowed_entity_types
            ):
                continue

            score = 0.0
            name = (entity.get("name") or "").lower()
            display_name = (entity.get("display_name") or "").lower()
            description = (entity.get("description") or "").lower()
            keywords = [k.lower() for k in entity.get("keywords", [])]

            if query == name or query == display_name:
                score = 1.0
            elif query in name or query in display_name:
                score = 0.85
            elif query in description:
                score = 0.6
            elif any(query in k for k in keywords):
                score = 0.5

            if score > 0:
                matches.append(
                    {
                        "type": "entity",
                        "entity_type": entity.get("entity_type"),
                        "name": entity.get("display_name"),
                        "file": entity.get("file"),
                        "signature": entity.get("signature", ""),
                        "description": entity.get("description", ""),
                        "score": score,
                    }
                )

    # Sort by score descending, then limit
    matches.sort(key=lambda m: m["score"], reverse=True)
    matches = matches[:limit]

    result = {
        "status": "success",
        "query": validated.query,
        "total_matches": len(matches),
        "matches": matches,
    }

    logger.info(
        f"Wiki search: {len(matches)} results for '{validated.query}' in {repo_path}"
    )
    return make_tool_text_content("search_wiki", result)


@handle_tool_errors
async def handle_fuzzy_search(args: dict[str, Any]) -> list[TextContent]:
    """Handle fuzzy_search tool call.

    Provides Levenshtein-based name matching with 'Did you mean?' suggestions.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = FuzzySearchArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _index_status, _wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.core.fuzzy_search import FuzzySearchHelper
    from local_deepwiki.models import ChunkType

    vector_store = _create_vector_store(repo_path, config)

    helper = FuzzySearchHelper(vector_store)
    await helper.build_name_index()

    # Map entity_type string to ChunkType
    chunk_type_filter = None
    if validated.entity_type:
        type_map = {
            "function": ChunkType.FUNCTION,
            "class": ChunkType.CLASS,
            "method": ChunkType.METHOD,
            "module": ChunkType.MODULE,
        }
        chunk_type_filter = type_map.get(validated.entity_type)

    matches = helper.find_similar_names(
        query=validated.query,
        threshold=validated.threshold,
        limit=validated.limit,
        chunk_type=chunk_type_filter,
    )

    # Get file location info for each match
    match_results = []
    for name, score in matches:
        entries = helper.get_entries_for_name(name)
        locations = [
            {"file_path": e.file_path, "type": e.chunk_type.value} for e in entries[:3]
        ]
        match_results.append(
            {
                "name": name,
                "score": round(score, 4),
                "locations": locations,
            }
        )

    # Also get file suggestions
    file_suggestions = helper.get_file_suggestions(
        validated.query, limit=FILE_SUGGESTIONS_LIMIT
    )

    hint = None
    if not match_results:
        hint = (
            "No matches found. Try a shorter or less specific query, "
            "or lower the threshold (e.g. threshold=0.4)."
        )

    result: dict[str, Any] = {
        "status": "success",
        "query": validated.query,
        "total_matches": len(match_results),
        "matches": match_results,
        "file_suggestions": file_suggestions,
        "index_stats": helper.get_stats(),
    }
    if hint:
        result["hint"] = hint

    logger.info(
        f"Fuzzy search: {len(match_results)} matches for '{validated.query}' in {repo_path}"
    )
    return make_tool_text_content("fuzzy_search", result)
