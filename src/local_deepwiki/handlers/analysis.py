"""Analysis and search tool handlers: wiki search, fuzzy search, explain, impact, diff, etc."""

import json
import time
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

# Threshold for considering wiki pages as stale (30 days in seconds)
STALE_DOCS_THRESHOLD_SECONDS = 30 * 24 * 60 * 60

# Git subprocess timeout values (seconds)
GIT_DIFF_TIMEOUT = 30
GIT_FILE_DIFF_TIMEOUT = 10

# Size limits for diff content
MAX_DIFF_CONTENT_LENGTH = 5000
MAX_DIFF_TEXT_LENGTH = 10000

# Maximum affected entities to return in diff analysis
MAX_AFFECTED_ENTITIES = 100

# Maximum file suggestions in fuzzy search
FILE_SUGGESTIONS_LIMIT = 3

from local_deepwiki.handlers._shared import (
    AnalyzeDiffArgs,
    AskAboutDiffArgs,
    ExplainEntityArgs,
    FuzzySearchArgs,
    GetComplexityMetricsArgs,
    GetFileContextArgs,
    GetProjectManifestArgs,
    GetWikiStatsArgs,
    ImpactAnalysisArgs,
    SearchWikiArgs,
    Permission,
    ValidationError,
    VectorStore,
    _create_vector_store,
    _load_index_status,
    get_access_controller,
    get_config,
    get_embedding_provider,
    get_rate_limiter,
    handle_tool_errors,
    logger,
    not_indexed_error,
    path_not_found_error,
    sanitize_error_message,
    validate_query_parameters,
)


def _set_section_error(
    result: dict[str, Any],
    field: str,
    operation: str,
    detail: str,
    exc: Exception,
) -> None:
    """Record a non-fatal section error in an explain/impact result dict."""
    logger.warning(f"{operation} failed for '{detail}': {exc}")
    result[field] = {"error": sanitize_error_message(str(exc))}


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

    _index_status, wiki_path, _config = _load_index_status(repo_path)

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

    search_data = json.loads(search_index_path.read_text())
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
                matches.append(
                    {
                        "type": "page",
                        "title": page.get("title"),
                        "path": page.get("path"),
                        "snippet": page.get("snippet", ""),
                        "score": score,
                    }
                )

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
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "No recognized package manifest files found in repository.",
                        "manifest": {},
                    },
                    indent=2,
                ),
            )
        ]

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

    logger.info(f"Project manifest: {manifest.name or 'unknown'} for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    full_file_path = (repo_path / file_path).resolve()

    # Validate file path is within repo (prevent traversal)
    if not full_file_path.is_relative_to(repo_path):
        raise ValidationError(
            message="Invalid file path: path traversal not allowed",
            hint="The file path must be within the repository.",
            field="file_path",
            value=file_path,
        )

    if not full_file_path.exists():
        raise path_not_found_error(file_path, "file")

    index_status, _wiki_path, config = _load_index_status(repo_path)

    from local_deepwiki.generators.context_builder import build_file_context

    vector_store = _create_vector_store(repo_path, config)

    # Get chunks for the file
    chunks = await vector_store.get_chunks_by_file(file_path)

    if not chunks:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": f"No indexed chunks found for '{file_path}'. The file may not have been indexed.",
                        "context": {"file_path": file_path},
                    },
                    indent=2,
                ),
            )
        ]

    context = await build_file_context(
        file_path=file_path,
        chunks=chunks,
        repo_path=repo_path,
        vector_store=vector_store,
    )

    result_context: dict = {
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
        f"File context: {len(context.imports)} imports, {len(context.callers)} callers for {file_path}"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    _index_status, _wiki_path, config = _load_index_status(repo_path)

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
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    index_status, wiki_path, _config = _load_index_status(repo_path)

    from datetime import datetime

    stats: dict[str, Any] = {
        "status": "success",
        "repo_path": index_status.repo_path,
        "wiki_dir": wiki_path.name,
    }

    # Index stats
    stats["index"] = {
        "indexed_at": index_status.indexed_at,
        "indexed_at_human": datetime.fromtimestamp(index_status.indexed_at).isoformat(),
        "total_files": index_status.total_files,
        "total_chunks": index_status.total_chunks,
        "languages": index_status.languages,
        "schema_version": index_status.schema_version,
    }

    # Wiki page stats from toc.json
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        toc_data = json.loads(toc_path.read_text())
        pages = toc_data if isinstance(toc_data, list) else toc_data.get("pages", [])
        stats["wiki_pages"] = {
            "total_pages": len(pages),
        }
    else:
        stats["wiki_pages"] = {"total_pages": 0}

    # Search index stats from search.json
    search_path = wiki_path / "search.json"
    if search_path.exists():
        search_data = json.loads(search_path.read_text())
        meta = search_data.get("meta", {})
        stats["search_index"] = {
            "total_page_entries": meta.get(
                "total_pages", len(search_data.get("pages", []))
            ),
            "total_entity_entries": meta.get(
                "total_entities", len(search_data.get("entities", []))
            ),
        }
    else:
        stats["search_index"] = {"available": False}

    # Wiki status from wiki_status.json (curated)
    wiki_status_path = wiki_path / "wiki_status.json"
    if wiki_status_path.exists():
        wiki_status_data = json.loads(wiki_status_path.read_text())
        # Curate wiki_status: keep high-level metrics, drop verbose page lists
        curated_wiki_status = {
            "total_pages": wiki_status_data.get(
                "total_pages", wiki_status_data.get("generated_pages", 0)
            ),
            "last_updated": wiki_status_data.get("generated_at"),
        }
        # Count stale vs up-to-date pages from pages dict
        pages_dict = wiki_status_data.get("pages", {})
        if pages_dict:
            import time

            now = time.time()
            # Consider pages older than 30 days as potentially stale
            stale_threshold = STALE_DOCS_THRESHOLD_SECONDS
            stale_count = sum(
                1
                for p in pages_dict.values()
                if now - p.get("generated_at", now) > stale_threshold
            )
            curated_wiki_status["stale_pages"] = stale_count
            curated_wiki_status["up_to_date_pages"] = len(pages_dict) - stale_count
        stats["wiki_status"] = curated_wiki_status

    # Coverage from coverage.json (curated)
    coverage_path = wiki_path / "coverage.json"
    if coverage_path.exists():
        coverage_data = json.loads(coverage_path.read_text())
        # Curate coverage: keep high-level metrics, drop per-file breakdowns
        if "overall" in coverage_data:
            # New format from handle_get_coverage
            overall = coverage_data["overall"]
            stats["coverage"] = {
                "documented_percentage": overall.get("coverage_percent", 0.0),
                "total_entities": overall.get("total_entities", 0),
                "documented_entities": overall.get("documented", 0),
                "undocumented_entities": overall.get("undocumented", 0),
            }
        else:
            # Legacy format or direct stats
            stats["coverage"] = {
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
                    if "total_files" in coverage_data
                    and "documented_files" in coverage_data
                    else 0,
                ),
            }

    # Manifest cache info
    manifest_path = wiki_path / "manifest_cache.json"
    stats["manifest_cached"] = manifest_path.exists()

    # Count wiki markdown files
    wiki_files = list(wiki_path.glob("**/*.md"))
    stats["total_wiki_files"] = len(wiki_files)

    logger.info(f"Wiki stats for {repo_path}")
    return [TextContent(type="text", text=json.dumps(stats, indent=2))]


@handle_tool_errors
async def handle_explain_entity(args: dict[str, Any]) -> list[TextContent]:
    """Handle explain_entity tool call.

    Composite tool that combines glossary, call graph, inheritance,
    test examples, and API docs for a single named entity.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = ExplainEntityArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    entity_name = validated.entity_name

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = _load_index_status(repo_path)

    # --- Step 1: Look up entity in search.json ---
    search_json_path = wiki_path / "search.json"
    entity_info = None
    if search_json_path.exists():
        try:
            search_data = json.loads(search_json_path.read_text())
            entities_list = search_data.get("entities", [])
            for entry in entities_list:
                if entry.get("name") == entity_name:
                    entity_info = entry
                    break
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"search.json exists but could not be read for entity lookup: {e}"
            )

    if entity_info is None:
        result = {
            "status": "success",
            "entity_name": entity_name,
            "entity_found": False,
            "message": (
                f"Entity '{entity_name}' not found in the search index. "
                "Try using fuzzy_search or search_wiki to find the correct name."
            ),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    entity_type = entity_info.get("entity_type", "unknown")
    entity_file = entity_info.get("file", "")

    result: dict[str, Any] = {
        "status": "success",
        "entity_name": entity_name,
        "entity_found": True,
        "entity_info": {
            "type": entity_type,
            "file": entity_file,
            "signature": entity_info.get("signature", ""),
            "description": entity_info.get("description", ""),
        },
    }

    # Determine if we need vector_store (inheritance or test_examples)
    needs_vector_store = (
        validated.include_inheritance and entity_type == "class"
    ) or validated.include_test_examples

    vector_store = None
    if needs_vector_store:
        vector_store = _create_vector_store(repo_path, config)

    # --- Step 2: Call graph ---
    if validated.include_call_graph and entity_file:
        try:
            from local_deepwiki.generators.callgraph import (
                CallGraphExtractor,
                build_reverse_call_graph,
            )

            full_file_path = (repo_path / entity_file).resolve()
            if full_file_path.exists() and full_file_path.is_relative_to(repo_path):
                extractor = CallGraphExtractor()
                call_graph = extractor.extract_from_file(full_file_path, repo_path)
                reverse_graph = build_reverse_call_graph(call_graph)

                calls = call_graph.get(entity_name, [])
                called_by = reverse_graph.get(entity_name, [])

                result["call_graph"] = {
                    "calls": calls,
                    "called_by": called_by,
                }
            else:
                result["call_graph"] = {
                    "calls": [],
                    "called_by": [],
                    "note": "Source file not found",
                }
        except Exception as exc:
            _set_section_error(
                result, "call_graph", "Call graph extraction", entity_name, exc
            )

    # --- Step 3: Inheritance (classes only) ---
    if (
        validated.include_inheritance
        and entity_type == "class"
        and vector_store is not None
    ):
        try:
            from local_deepwiki.generators.inheritance import collect_class_hierarchy

            classes = await collect_class_hierarchy(index_status, vector_store)
            class_node = classes.get(entity_name)

            if class_node is not None:
                result["inheritance"] = {
                    "parents": class_node.parents,
                    "children": class_node.children,
                    "is_abstract": class_node.is_abstract,
                }
            else:
                result["inheritance"] = {
                    "parents": [],
                    "children": [],
                    "is_abstract": False,
                    "note": "Class not found in inheritance hierarchy",
                }
        except Exception as exc:
            _set_section_error(
                result, "inheritance", "Inheritance lookup", entity_name, exc
            )

    # --- Step 4: Test examples ---
    if validated.include_test_examples and vector_store is not None:
        try:
            from local_deepwiki.generators.test_examples import CodeExampleExtractor

            example_extractor = CodeExampleExtractor(vector_store, repo_path=repo_path)

            if entity_type == "class":
                examples = await example_extractor.extract_examples_for_class(
                    entity_name, max_examples=validated.max_test_examples
                )
            else:
                examples = await example_extractor.extract_examples_for_function(
                    entity_name, max_examples=validated.max_test_examples
                )
                if not examples:
                    examples = await example_extractor.extract_examples_for_class(
                        entity_name, max_examples=validated.max_test_examples
                    )

            result["test_examples"] = [
                {
                    "code": ex.code,
                    "source_file": ex.test_file,
                    "description": ex.description,
                }
                for ex in examples
            ]
        except Exception as exc:
            _set_section_error(
                result, "test_examples", "Test example extraction", entity_name, exc
            )

    # --- Step 5: API docs ---
    if validated.include_api_docs and entity_file:
        try:
            from local_deepwiki.generators.api_docs import APIDocExtractor

            full_file_path = (repo_path / entity_file).resolve()
            if full_file_path.exists() and full_file_path.is_relative_to(repo_path):
                api_extractor = APIDocExtractor()
                functions, classes_sigs = api_extractor.extract_from_file(
                    full_file_path
                )

                api_entry: dict[str, Any] | None = None

                if entity_type == "class":
                    for cls_sig in classes_sigs:
                        if cls_sig.name == entity_name:
                            api_entry = {
                                "bases": cls_sig.bases,
                                "docstring": cls_sig.docstring,
                                "description": cls_sig.description,
                                "methods": [
                                    {
                                        "name": m.name,
                                        "parameters": [
                                            {
                                                "name": p.name,
                                                "type": p.type_hint,
                                                "default": p.default_value,
                                            }
                                            for p in m.parameters
                                        ],
                                        "return_type": m.return_type,
                                        "is_async": m.is_async,
                                        "docstring": m.docstring,
                                    }
                                    for m in cls_sig.methods
                                ],
                                "class_variables": [
                                    {"name": cv[0], "type": cv[1], "value": cv[2]}
                                    for cv in cls_sig.class_variables
                                ],
                            }
                            break
                else:
                    # Search top-level functions
                    for func_sig in functions:
                        if func_sig.name == entity_name:
                            api_entry = {
                                "parameters": [
                                    {
                                        "name": p.name,
                                        "type": p.type_hint,
                                        "default": p.default_value,
                                    }
                                    for p in func_sig.parameters
                                ],
                                "return_type": func_sig.return_type,
                                "docstring": func_sig.docstring,
                                "is_async": func_sig.is_async,
                                "decorators": func_sig.decorators,
                            }
                            break

                    # If not found in top-level, search class methods
                    if api_entry is None:
                        for cls_sig in classes_sigs:
                            for m in cls_sig.methods:
                                if m.name == entity_name:
                                    api_entry = {
                                        "parameters": [
                                            {
                                                "name": p.name,
                                                "type": p.type_hint,
                                                "default": p.default_value,
                                            }
                                            for p in m.parameters
                                        ],
                                        "return_type": m.return_type,
                                        "docstring": m.docstring,
                                        "is_async": m.is_async,
                                        "decorators": m.decorators,
                                        "class_name": cls_sig.name,
                                    }
                                    break
                            if api_entry is not None:
                                break

                if api_entry is not None:
                    result["api_docs"] = api_entry
                else:
                    result["api_docs"] = {
                        "note": f"No API signature found for '{entity_name}' in {entity_file}"
                    }
            else:
                result["api_docs"] = {"note": "Source file not found"}
        except Exception as exc:
            _set_section_error(
                result, "api_docs", "API doc extraction", entity_name, exc
            )

    logger.info(f"Explain entity: '{entity_name}' in {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_impact_analysis(args: dict[str, Any]) -> list[TextContent]:
    """Handle impact_analysis tool call.

    Analyzes the blast radius of changes to a file or entity by examining
    reverse call graph, inheritance dependents, file imports, and wiki pages.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = ImpactAnalysisArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    file_path = validated.file_path
    entity_name = validated.entity_name

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    full_file = repo_path / file_path

    # Validate file path is within repo (prevent traversal)
    if not full_file.resolve().is_relative_to(repo_path):
        raise ValidationError(
            message="Invalid file path: path traversal not allowed",
            hint="The file path must be within the repository.",
            field="file_path",
            value=file_path,
        )

    if not full_file.exists():
        raise path_not_found_error(file_path, "file")

    index_status, wiki_path, config = _load_index_status(repo_path)

    result: dict[str, Any] = {
        "status": "success",
        "file_path": file_path,
        "entity_name": entity_name,
    }

    affected_files: set[str] = set()
    affected_entities: set[str] = set()

    # Create VectorStore once if any section needs it
    needs_vector_store = validated.include_inheritance or validated.include_dependents
    vector_store = (
        _create_vector_store(repo_path, config) if needs_vector_store else None
    )

    # --- Section 1: Reverse call graph ---
    if validated.include_reverse_calls:
        try:
            from local_deepwiki.generators.callgraph import (
                CallGraphExtractor,
                build_reverse_call_graph,
            )

            extractor = CallGraphExtractor()
            call_graph = extractor.extract_from_file(full_file.resolve(), repo_path)
            reverse_graph = build_reverse_call_graph(call_graph)

            if entity_name:
                # Filter to just the specified entity
                filtered = {k: v for k, v in reverse_graph.items() if k == entity_name}
                reverse_graph = filtered

            result["reverse_call_graph"] = reverse_graph

            for callee, callers in reverse_graph.items():
                affected_entities.add(callee)
                for caller in callers:
                    affected_entities.add(caller)
                    # Extract file portion if caller contains a dot separator
                    # (e.g. "other_module.func" -> "other_module")
                    if "." in caller:
                        affected_files.add(caller.rsplit(".", 1)[0])
        except Exception as exc:
            _set_section_error(
                result,
                "reverse_call_graph",
                "Reverse call graph extraction",
                file_path,
                exc,
            )

    # --- Section 2: Inheritance dependents ---
    if validated.include_inheritance:
        try:
            from local_deepwiki.generators.inheritance import collect_class_hierarchy

            assert vector_store is not None
            classes = await collect_class_hierarchy(index_status, vector_store)

            inheritance_dependents: dict[str, list[str]] = {}
            for class_name, node in classes.items():
                if node.file_path == file_path:
                    if entity_name and class_name != entity_name:
                        continue
                    children_with_files = []
                    for child_name in node.children:
                        child_node = classes.get(child_name)
                        if child_node and child_node.file_path != file_path:
                            qualified = f"{child_node.file_path}:{child_name}"
                            children_with_files.append(qualified)
                            affected_files.add(child_node.file_path)
                            affected_entities.add(child_name)
                        elif child_node:
                            children_with_files.append(child_name)
                            affected_entities.add(child_name)
                    if children_with_files:
                        inheritance_dependents[class_name] = children_with_files
                        affected_entities.add(class_name)

            result["inheritance_dependents"] = inheritance_dependents
        except Exception as exc:
            _set_section_error(
                result, "inheritance_dependents", "Inheritance analysis", file_path, exc
            )

    # --- Section 3: File-level dependents ---
    if validated.include_dependents:
        try:
            from local_deepwiki.generators.context_builder import build_file_context

            assert vector_store is not None
            chunks = await vector_store.get_chunks_by_file(file_path)

            if chunks:
                context = await build_file_context(
                    file_path=file_path,
                    chunks=chunks,
                    repo_path=repo_path,
                    vector_store=vector_store,
                )

                importing_files = []
                for _entity, caller_files in context.callers.items():
                    for cf in caller_files:
                        if cf != file_path and cf not in importing_files:
                            importing_files.append(cf)
                            affected_files.add(cf)

                result["file_dependents"] = {
                    "importing_files": importing_files,
                    "related_files": [
                        rf for rf in context.related_files if rf != file_path
                    ],
                }
            else:
                result["file_dependents"] = {
                    "importing_files": [],
                    "related_files": [],
                }
        except Exception as exc:
            _set_section_error(
                result, "file_dependents", "File dependents analysis", file_path, exc
            )

    # --- Section 4: Affected wiki pages ---
    if validated.include_wiki_pages:
        try:
            toc_path = wiki_path / "toc.json"
            matched_pages: list[dict[str, str]] = []
            if toc_path.exists():
                toc_data = json.loads(toc_path.read_text())
                pages = (
                    toc_data
                    if isinstance(toc_data, list)
                    else toc_data.get("pages", [])
                )
                for page in pages:
                    source_file = page.get("source_file", "")
                    if source_file == file_path:
                        matched_pages.append(
                            {
                                "title": page.get("title", ""),
                                "path": page.get("path", ""),
                            }
                        )
            result["affected_wiki_pages"] = matched_pages
        except Exception as exc:
            _set_section_error(
                result, "affected_wiki_pages", "Wiki page lookup", file_path, exc
            )

    # --- Impact summary ---
    total_affected_files = len(affected_files)
    total_affected_entities = len(affected_entities)

    if total_affected_files <= 2:
        risk_level = "low"
    elif total_affected_files <= 10:
        risk_level = "medium"
    else:
        risk_level = "high"

    result["impact_summary"] = {
        "total_affected_files": total_affected_files,
        "total_affected_entities": total_affected_entities,
        "risk_level": risk_level,
    }

    logger.info(
        f"Impact analysis: {file_path} -> {total_affected_files} files, "
        f"risk={risk_level}"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    full_file = repo_path / file_path
    if not full_file.resolve().is_relative_to(repo_path):
        raise ValidationError(
            message="Invalid file path: path traversal not allowed",
            hint="The file path must be within the repository.",
            field="file_path",
            value=file_path,
        )
    if not full_file.exists():
        raise path_not_found_error(file_path, "file")

    from local_deepwiki.generators.complexity import compute_complexity_metrics

    # Compute complexity metrics using the generator
    result = await compute_complexity_metrics(Path(file_path), repo_path)

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_analyze_diff(args: dict[str, Any]) -> list[TextContent]:
    """Handle analyze_diff tool call.

    Analyzes git diff and maps changed files to affected wiki pages and entities.
    """
    import re
    import subprocess

    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = AnalyzeDiffArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    # Validate git refs to prevent injection
    ref_pattern = re.compile(r"^[a-zA-Z0-9_.\/\-~^]+$")
    for ref_name, ref_value in [
        ("base_ref", validated.base_ref),
        ("head_ref", validated.head_ref),
    ]:
        if not ref_pattern.match(ref_value):
            raise ValidationError(
                message=f"Invalid git ref: {ref_value}",
                hint="Git refs must contain only alphanumeric chars, /, -, _, ~, ^, and .",
                field=ref_name,
                value=ref_value,
            )

    # Run git diff --name-status
    try:
        diff_result = subprocess.run(
            [
                "git",
                "diff",
                "--name-status",
                validated.base_ref,
                validated.head_ref,
            ],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=GIT_DIFF_TIMEOUT,
        )
        if diff_result.returncode != 0:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "error": f"git diff failed: {sanitize_error_message(diff_result.stderr.strip())}",
                        },
                        indent=2,
                    ),
                )
            ]
    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"git diff timed out after {GIT_DIFF_TIMEOUT} seconds",
                    },
                    indent=2,
                ),
            )
        ]

    # Parse git diff output
    status_map = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
    }
    changed_files: list[dict[str, Any]] = []
    for line in diff_result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status_code, file_name = parts
            status = status_map.get(status_code[0], "modified")
            changed_files.append({"file": file_name, "status": status})

    if not changed_files:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "base_ref": validated.base_ref,
                        "head_ref": validated.head_ref,
                        "message": "No file changes found between the specified refs.",
                        "changed_files": [],
                        "affected_wiki_pages": [],
                        "affected_entities": [],
                    },
                    indent=2,
                ),
            )
        ]

    # Optionally get diff content per file
    if validated.include_content:
        for cf in changed_files:
            try:
                file_diff = subprocess.run(
                    [
                        "git",
                        "diff",
                        validated.base_ref,
                        validated.head_ref,
                        "--",
                        cf["file"],
                    ],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=GIT_FILE_DIFF_TIMEOUT,
                )
                cf["diff_content"] = file_diff.stdout[:MAX_DIFF_CONTENT_LENGTH]
            except (subprocess.TimeoutExpired, OSError):
                cf["diff_content"] = "(diff content unavailable)"

    # Try to load index and map to wiki pages
    affected_wiki_pages: list[dict[str, str]] = []
    affected_entities: list[dict[str, str]] = []
    try:
        _index_status, wiki_path, _config = _load_index_status(repo_path)

        # Map to wiki pages via toc.json
        toc_path = wiki_path / "toc.json"
        if toc_path.exists():
            toc_data = json.loads(toc_path.read_text())
            pages = (
                toc_data if isinstance(toc_data, list) else toc_data.get("pages", [])
            )
            changed_file_set = {cf["file"] for cf in changed_files}
            for page in pages:
                source_file = page.get("source_file", "")
                if source_file in changed_file_set:
                    affected_wiki_pages.append(
                        {
                            "title": page.get("title", ""),
                            "path": page.get("path", ""),
                            "source_file": source_file,
                        }
                    )

        # Map to entities via search.json
        search_path = wiki_path / "search.json"
        if search_path.exists():
            search_data = json.loads(search_path.read_text())
            entities = search_data.get("entities", [])
            changed_file_set = {cf["file"] for cf in changed_files}
            for entity in entities:
                if entity.get("file", "") in changed_file_set:
                    affected_entities.append(
                        {
                            "name": entity.get("display_name", entity.get("name", "")),
                            "type": entity.get("entity_type", ""),
                            "file": entity.get("file", ""),
                        }
                    )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        KeyError,
        ValidationError,
    ) as e:
        # FileNotFoundError: no index exists
        # json.JSONDecodeError: corrupted toc/search JSON
        # OSError: file read issues
        # KeyError: unexpected data format
        # ValidationError: repository not indexed
        logger.debug(f"Could not load wiki/entity mapping for diff analysis: {e}")

    # Summary
    summary = {
        "total_changed_files": len(changed_files),
        "added": sum(1 for f in changed_files if f["status"] == "added"),
        "modified": sum(1 for f in changed_files if f["status"] == "modified"),
        "deleted": sum(1 for f in changed_files if f["status"] == "deleted"),
        "affected_wiki_pages": len(affected_wiki_pages),
        "affected_entities": len(affected_entities),
    }

    result = {
        "status": "success",
        "base_ref": validated.base_ref,
        "head_ref": validated.head_ref,
        "summary": summary,
        "changed_files": changed_files,
        "affected_wiki_pages": affected_wiki_pages,
        "affected_entities": affected_entities[:MAX_AFFECTED_ENTITIES],
    }

    logger.info(
        f"Diff analysis: {len(changed_files)} files changed, "
        f"{len(affected_wiki_pages)} wiki pages affected"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_ask_about_diff(args: dict[str, Any]) -> list[TextContent]:
    """Handle ask_about_diff tool call.

    RAG-based Q&A about recent code changes, combining git diff
    with vector search context and LLM synthesis.
    """
    import re
    import subprocess

    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = AskAboutDiffArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    question = validated.question

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    # Validate git refs to prevent injection
    ref_pattern = re.compile(r"^[a-zA-Z0-9_.\/\-~^]+$")
    for ref_name, ref_value in [
        ("base_ref", validated.base_ref),
        ("head_ref", validated.head_ref),
    ]:
        if not ref_pattern.match(ref_value):
            raise ValidationError(
                message=f"Invalid git ref: {ref_value}",
                hint="Git refs must contain only alphanumeric chars, /, -, _, ~, ^, and .",
                field=ref_name,
                value=ref_value,
            )

    # Get the diff
    try:
        diff_result = subprocess.run(
            ["git", "diff", validated.base_ref, validated.head_ref],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=GIT_DIFF_TIMEOUT,
        )
        if diff_result.returncode != 0:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "error": f"git diff failed: {sanitize_error_message(diff_result.stderr.strip())}",
                        },
                        indent=2,
                    ),
                )
            ]
    except subprocess.TimeoutExpired:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "error": f"git diff timed out after {GIT_DIFF_TIMEOUT} seconds",
                    },
                    indent=2,
                ),
            )
        ]

    diff_text = diff_result.stdout
    if not diff_text.strip():
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "question": question,
                        "answer": "No changes found between the specified refs. There is nothing to analyze.",
                        "sources": [],
                    },
                    indent=2,
                ),
            )
        ]

    # Truncate diff if very large
    if len(diff_text) > MAX_DIFF_TEXT_LENGTH:
        diff_text = (
            diff_text[:MAX_DIFF_TEXT_LENGTH]
            + f"\n... (diff truncated, showing first {MAX_DIFF_TEXT_LENGTH} chars)"
        )

    # Get additional context from vector store
    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)
    wiki_path = config.get_wiki_path(repo_path)

    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []

    embedding_provider = get_embedding_provider(config.embedding)

    if vector_db_path.exists():
        vector_store = VectorStore(vector_db_path, embedding_provider)

        # Search for relevant context using the question
        search_results = await vector_store.search(
            question, limit=validated.max_context
        )

        for sr in search_results:
            chunk = sr.chunk
            context_parts.append(
                f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
                f"Type: {chunk.chunk_type.value}\n"
                f"```\n{chunk.content}\n```"
            )
            sources.append(
                {
                    "file": chunk.file_path,
                    "lines": f"{chunk.start_line}-{chunk.end_line}",
                    "type": chunk.chunk_type.value,
                    "score": sr.score,
                }
            )

    additional_context = (
        "\n\n---\n\n".join(context_parts)
        if context_parts
        else "(No additional code context available)"
    )

    # Generate answer using LLM
    from local_deepwiki.providers.llm import get_cached_llm_provider

    cache_path = wiki_path / "llm_cache.lance"
    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=embedding_provider,
        cache_config=config.llm_cache,
        llm_config=config.llm,
    )

    prompt = (
        f"You are analyzing recent code changes. Answer this question about the diff:\n\n"
        f"Question: {question}\n\n"
        f"## Git Diff (changes between {validated.base_ref} and {validated.head_ref}):\n"
        f"```diff\n{diff_text}\n```\n\n"
        f"## Additional Code Context (from the codebase):\n{additional_context}\n\n"
        f"Provide a clear, specific answer based on the diff and context. "
        f"Focus on what changed, why it might matter, and any potential issues."
    )

    system_prompt = "You are a code review assistant. Analyze code diffs and answer questions accurately."

    rate_limiter = get_rate_limiter()
    async with rate_limiter:
        answer = await llm.generate(prompt, system_prompt=system_prompt)

    result = {
        "status": "success",
        "question": question,
        "base_ref": validated.base_ref,
        "head_ref": validated.head_ref,
        "answer": answer,
        "diff_stats": {
            "diff_length": len(diff_result.stdout),
            "truncated": len(diff_result.stdout) > MAX_DIFF_TEXT_LENGTH,
        },
        "sources": sources,
    }

    logger.info(f"Ask about diff: '{question[:50]}...' for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
