"""Metadata-related analysis handlers: manifest, file context, wiki stats, complexity."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

# Threshold for considering wiki pages as stale (30 days in seconds)
STALE_DOCS_THRESHOLD_SECONDS = 30 * 24 * 60 * 60

from local_deepwiki.core.path_utils import validate_file_in_repo
from local_deepwiki.errors import ValidationError, path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._index_helpers import (
    _create_vector_store,
    _load_index_status,
)
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    GetComplexityMetricsArgs,
    GetFileContextArgs,
    GetProjectManifestArgs,
    GetWikiStatsArgs,
)
from local_deepwiki.security import Permission, get_access_controller

logger = get_logger(__name__)


def _build_index_stats_dict(index_status: Any) -> dict[str, Any]:
    """Build the ``index`` section dict from an IndexStatus object.

    Args:
        index_status: Loaded IndexStatus for the repository.

    Returns:
        Dict with indexed_at, total_files, total_chunks, languages, and
        schema_version fields.
    """
    from datetime import datetime, timezone

    return {
        "indexed_at": index_status.indexed_at,
        "indexed_at_human": datetime.fromtimestamp(
            index_status.indexed_at, tz=timezone.utc
        ).isoformat(),
        "total_files": index_status.total_files,
        "total_chunks": index_status.total_chunks,
        "languages": index_status.languages,
        "schema_version": index_status.schema_version,
    }


async def _build_toc_stats(wiki_path: Path) -> dict[str, Any]:
    """Read toc.json and return a ``wiki_pages`` stats dict.

    Args:
        wiki_path: Path to the wiki directory.

    Returns:
        Dict with ``total_pages`` key.
    """
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        toc_content = await asyncio.to_thread(toc_path.read_text)
        toc_data = json.loads(toc_content)
        pages = toc_data if isinstance(toc_data, list) else toc_data.get("pages", [])
        return {"total_pages": len(pages)}
    return {"total_pages": 0}


async def _build_search_index_stats(wiki_path: Path) -> dict[str, Any]:
    """Read search.json and return a ``search_index`` stats dict.

    Args:
        wiki_path: Path to the wiki directory.

    Returns:
        Dict with ``total_page_entries`` and ``total_entity_entries``, or
        ``{"available": False}`` when the file is absent.
    """
    search_path = wiki_path / "search.json"
    if search_path.exists():
        search_content = await asyncio.to_thread(search_path.read_text)
        search_data = json.loads(search_content)
        meta = search_data.get("meta", {})
        return {
            "total_page_entries": meta.get(
                "total_pages", len(search_data.get("pages", []))
            ),
            "total_entity_entries": meta.get(
                "total_entities", len(search_data.get("entities", []))
            ),
        }
    return {"available": False}


async def _curate_wiki_status(wiki_path: Path) -> dict[str, Any] | None:
    """Read wiki_status.json and return a curated summary dict.

    Drops verbose page lists; keeps high-level metrics plus stale/up-to-date counts.

    Args:
        wiki_path: Path to the wiki directory.

    Returns:
        Curated dict, or ``None`` if wiki_status.json does not exist.
    """
    wiki_status_path = wiki_path / "wiki_status.json"
    if not wiki_status_path.exists():
        return None

    wiki_status_content = await asyncio.to_thread(wiki_status_path.read_text)
    wiki_status_data = json.loads(wiki_status_content)
    curated: dict[str, Any] = {
        "total_pages": wiki_status_data.get(
            "total_pages", wiki_status_data.get("generated_pages", 0)
        ),
        "last_updated": wiki_status_data.get("generated_at"),
    }
    pages_dict = wiki_status_data.get("pages", {})
    if pages_dict:
        now = time.time()
        stale_count = sum(
            1
            for p in pages_dict.values()
            if now - p.get("generated_at", now) > STALE_DOCS_THRESHOLD_SECONDS
        )
        curated["stale_pages"] = stale_count
        curated["up_to_date_pages"] = len(pages_dict) - stale_count
    return curated


async def _compute_coverage_stats(wiki_path: Path) -> dict[str, Any] | None:
    """Read coverage.json and return a curated coverage dict.

    Handles both the new format (``overall`` key) and legacy format.

    Args:
        wiki_path: Path to the wiki directory.

    Returns:
        Dict with ``documented_percentage``, ``total_entities``,
        ``documented_entities``, and ``undocumented_entities``, or
        ``None`` if coverage.json does not exist.
    """
    coverage_path = wiki_path / "coverage.json"
    if not coverage_path.exists():
        return None

    coverage_content = await asyncio.to_thread(coverage_path.read_text)
    coverage_data = json.loads(coverage_content)

    if "overall" in coverage_data:
        # New format from handle_get_coverage
        overall = coverage_data["overall"]
        return {
            "documented_percentage": overall.get("coverage_percent", 0.0),
            "total_entities": overall.get("total_entities", 0),
            "documented_entities": overall.get("documented", 0),
            "undocumented_entities": overall.get("undocumented", 0),
        }

    # Legacy format or direct stats
    return {
        "documented_percentage": coverage_data.get(
            "coverage_percent",
            coverage_data.get("coverage", 0.0) * 100
            if "coverage" in coverage_data
            else 0.0,
        ),
        "total_entities": coverage_data.get(
            "total_entities", coverage_data.get("total_files", 0)
        ),
        "documented_entities": coverage_data.get(
            "documented_entities", coverage_data.get("documented_files", 0)
        ),
        "undocumented_entities": coverage_data.get(
            "undocumented_entities",
            coverage_data.get("total_files", 0)
            - coverage_data.get("documented_files", 0)
            if "total_files" in coverage_data and "documented_files" in coverage_data
            else 0,
        ),
    }


@handle_tool_errors
async def handle_get_project_manifest(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_project_manifest tool call.

    Returns parsed project metadata from package manifest files
    (pyproject.toml, package.json, Cargo.toml, etc.).
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetProjectManifestArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.manifest import get_cached_manifest, parse_manifest

    if validated.use_cache:
        manifest = get_cached_manifest(repo_path)
    else:
        manifest = parse_manifest(repo_path)

    if not manifest.has_data():
        return make_tool_text_content(
            "get_project_manifest",
            {
                "message": "No recognized package manifest files found in repository.",
                "manifest": {},
            },
        )

    manifest_dict = {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "language": manifest.language,
        "language_version": manifest.language_version,
        "repository": manifest.repository,
        "license": manifest.license,
        "authors": manifest.authors,
        "manifest_files": manifest.manifest_files,
        "dependencies": manifest.dependencies,
        "dev_dependencies": manifest.dev_dependencies,
        "entry_points": manifest.entry_points,
        "scripts": manifest.scripts,
        "tech_stack_summary": manifest.get_tech_stack_summary(),
    }

    result = {
        "status": "success",
        "manifest": manifest_dict,
    }

    logger.info("Project manifest: %s for %s", manifest.name or "unknown", repo_path)
    return make_tool_text_content("get_project_manifest", result)


@handle_tool_errors
async def handle_get_file_context(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_file_context tool call.

    Returns imports, callers, related files, and type definitions for a source file.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetFileContextArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    file_path = validated.file_path

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    validate_file_in_repo(repo_path, file_path)

    index_status, _wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.generators.context_builder import build_file_context

    vector_store = _create_vector_store(repo_path, config)

    # Get chunks for the file
    chunks = await vector_store.get_chunks_by_file(file_path)

    if not chunks:
        return make_tool_text_content(
            "get_file_context",
            {
                "message": f"No indexed chunks found for '{file_path}'. The file may not have been indexed.",
                "context": {"file_path": file_path},
            },
        )

    context = await build_file_context(
        file_path=file_path,
        chunks=chunks,
        repo_path=repo_path,
        vector_store=vector_store,
    )

    result_context: dict[str, Any] = {
        "file_path": context.file_path,
        "imports": context.imports,
        "imported_modules": context.imported_modules,
        "callers": context.callers,
        "related_files": context.related_files,
        "type_definitions": context.type_definitions,
    }
    if context.warnings:
        result_context["warnings"] = context.warnings

    result = {
        "status": "success",
        "context": result_context,
    }

    logger.info(
        "File context: %d imports, %d callers for %s",
        len(context.imports),
        len(context.callers),
        file_path,
    )
    return make_tool_text_content("get_file_context", result)


@handle_tool_errors
async def handle_get_wiki_stats(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_wiki_stats tool call.

    Returns a single-call wiki health dashboard aggregating index status,
    coverage, staleness, and search index metadata.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetWikiStatsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, _config = await _load_index_status(repo_path)

    stats: dict[str, Any] = {
        "status": "success",
        "repo_path": index_status.repo_path,
        "wiki_dir": wiki_path.name,
    }

    # Index stats
    stats["index"] = _build_index_stats_dict(index_status)

    # Wiki page stats from toc.json
    stats["wiki_pages"] = await _build_toc_stats(wiki_path)

    # Search index stats from search.json
    stats["search_index"] = await _build_search_index_stats(wiki_path)

    # Wiki status from wiki_status.json (curated)
    curated_wiki_status = await _curate_wiki_status(wiki_path)
    if curated_wiki_status is not None:
        stats["wiki_status"] = curated_wiki_status

    # Coverage from coverage.json (curated)
    coverage = await _compute_coverage_stats(wiki_path)
    if coverage is not None:
        stats["coverage"] = coverage

    # Manifest cache info
    manifest_path = wiki_path / "manifest_cache.json"
    stats["manifest_cached"] = manifest_path.exists()

    # Count wiki markdown files
    wiki_files = await asyncio.to_thread(lambda: list(wiki_path.glob("**/*.md")))
    stats["total_wiki_files"] = len(wiki_files)

    # Drain status (if lazy generator is active for this wiki)
    from local_deepwiki.generators.lazy_generator import get_active_generators

    active = get_active_generators()
    lazy_key = str(wiki_path.resolve())
    if lazy_key in active:
        stats["drain"] = active[lazy_key].get_drain_status()

    logger.info("Wiki stats for %s", repo_path)
    return make_tool_text_content("get_wiki_stats", stats)


@handle_tool_errors
async def handle_get_status(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_status tool call with scope-based dispatch.

    Supports three scopes:
    - ``"all"`` (default): Returns both index status and wiki stats.
    - ``"index"``: Index status only (file count, chunks, languages).
    - ``"wiki"``: Wiki health dashboard only (pages, coverage, staleness).

    The old ``get_index_status`` and ``get_wiki_stats`` tools are aliases.
    """
    scope = args.get("scope", "all")

    if scope == "index":
        from local_deepwiki.handlers.generators import handle_get_index_status

        return await handle_get_index_status(args)

    if scope == "wiki":
        return await handle_get_wiki_stats(args)

    # scope == "all": combine both responses
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetWikiStatsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, _config = await _load_index_status(repo_path)

    # Build combined result
    result: dict[str, Any] = {
        "status": "success",
        "repo_path": index_status.repo_path,
        "scope": "all",
    }

    # Index section
    result["index"] = {
        **_build_index_stats_dict(index_status),
        "wiki_path": str(wiki_path),
    }

    # Wiki section
    wiki_section: dict[str, Any] = {"wiki_dir": wiki_path.name}
    wiki_section["wiki_pages"] = await _build_toc_stats(wiki_path)
    wiki_section["search_index"] = await _build_search_index_stats(wiki_path)

    curated = await _curate_wiki_status(wiki_path)
    if curated is not None:
        wiki_section["wiki_status"] = curated

    wiki_files = await asyncio.to_thread(lambda: list(wiki_path.glob("**/*.md")))
    wiki_section["total_wiki_files"] = len(wiki_files)

    result["wiki"] = wiki_section

    logger.info("Combined status for %s", repo_path)
    return make_tool_text_content("get_status", result)


@handle_tool_errors
async def handle_get_complexity_metrics(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_complexity_metrics tool call.

    Analyzes code complexity using tree-sitter AST parsing. Returns
    function/class counts, line metrics, cyclomatic complexity,
    nesting depth, and parameter counts.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetComplexityMetricsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    file_path = validated.file_path

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    # Detect directory paths early and give a helpful error with suggestions
    resolved = (repo_path / file_path).resolve()
    if resolved.is_dir():
        py_files = sorted(
            f.name for f in resolved.glob("*.py") if not f.name.startswith("__")
        )
        suggestions = py_files[:5]
        message = (
            f"Path is a directory, not a file. "
            f"Files in '{file_path}': {', '.join(suggestions)}"
            if suggestions
            else "Path is a directory, not a file."
        )
        raise ValidationError(
            message=message,
            hint="Provide a path to a specific .py file, not a directory.",
            field="file_path",
            value=file_path,
        )

    validate_file_in_repo(repo_path, file_path)

    from local_deepwiki.generators.analysis.complexity import compute_complexity_metrics

    # Compute complexity metrics using the generator
    result = await compute_complexity_metrics(Path(file_path), repo_path)

    return make_tool_text_content("get_complexity_metrics", result)
