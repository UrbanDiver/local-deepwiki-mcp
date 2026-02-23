"""Search-related analysis handlers: wiki search and fuzzy search."""

from __future__ import annotations

import asyncio
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

# Maximum file suggestions in fuzzy search
FILE_SUGGESTIONS_LIMIT = 3

from local_deepwiki.errors import path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._index_helpers import (
    _create_vector_store,
    _load_index_status,
)
from local_deepwiki.handlers._response import (
    build_wiki_resource_uri,
    make_tool_text_content,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import FuzzySearchArgs, SearchWikiArgs
from local_deepwiki.security import Permission, get_access_controller
from local_deepwiki.validation import validate_query_parameters

logger = get_logger(__name__)


def _score_page_match(page: dict[str, Any], query: str) -> float:
    """Score a wiki page against a lowercased *query*."""
    title = (page.get("title") or "").lower()
    if query in title:
        return 1.0
    if any(query in h.lower() for h in page.get("headings", [])):
        return 0.8
    if any(query in t.lower() for t in page.get("terms", [])):
        return 0.6
    if query in (page.get("snippet") or "").lower():
        return 0.4
    return 0.0


def _score_entity_match(entity: dict[str, Any], query: str) -> float:
    """Score a code entity against a lowercased *query*."""
    name = (entity.get("name") or "").lower()
    display_name = (entity.get("display_name") or "").lower()
    if query == name or query == display_name:
        return 1.0
    if query in name or query in display_name:
        return 0.85
    description = (entity.get("description") or "").lower()
    if query in description:
        return 0.6
    keywords = [k.lower() for k in entity.get("keywords", [])]
    if any(query in k for k in keywords):
        return 0.5
    return 0.0


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
            score = _score_page_match(page, query)
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

            score = _score_entity_match(entity, query)
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

    matches = sorted(matches, key=itemgetter("score"), reverse=True)[:limit]

    result = {
        "status": "success",
        "query": validated.query,
        "total_matches": len(matches),
        "matches": matches,
    }

    logger.info(
        "Wiki search: %d results for '%s' in %s",
        len(matches),
        validated.query,
        repo_path,
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
        "Fuzzy search: %d matches for '%s' in %s",
        len(match_results),
        validated.query,
        repo_path,
    )
    return make_tool_text_content("fuzzy_search", result)
