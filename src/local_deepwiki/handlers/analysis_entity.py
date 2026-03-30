"""Entity-related analysis handlers: explain entity and impact analysis."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.core.path_utils import validate_file_in_repo
from local_deepwiki.errors import (
    path_not_found_error,
    sanitize_error_message,
)
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._index_helpers import (
    _create_vector_store,
    _load_index_status,
)
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ExplainEntityArgs, ImpactAnalysisArgs
from local_deepwiki.security import Permission, get_access_controller
from local_deepwiki.services.analysis_service import (
    AnalysisService,
    EntityAnalysisContext,
    EntityExplainRequest,
    ImpactAnalysisRequest,
    _collect_reverse_calls,
)

logger = get_logger(__name__)

# Re-export for backward compatibility (tests import from here)
__all__ = [
    "EntityAnalysisContext",
    "_collect_reverse_calls",
    "handle_explain_entity",
    "handle_impact_analysis",
]


def _set_section_error(
    result: dict[str, Any],
    field: str,
    operation: str,
    detail: str,
    exc: Exception,
) -> None:
    """Record a non-fatal section error in an explain/impact result dict."""
    logger.warning("%s failed for '%s': %s", operation, detail, exc)
    result[field] = {"error": sanitize_error_message(str(exc))}


# ---------------------------------------------------------------------------
# handle_explain_entity helpers
# ---------------------------------------------------------------------------


async def _lookup_entity_in_search_index(
    wiki_path: Path,
    entity_name: str,
) -> dict[str, Any] | None:
    """Look up *entity_name* in the pre-built ``search.json`` index."""
    search_json_path = wiki_path / "search.json"
    if not search_json_path.exists():
        return None
    try:
        search_content = await asyncio.to_thread(search_json_path.read_text)
        search_data = json.loads(search_content)
        for entry in search_data.get("entities", []):
            if entry.get("name") == entity_name:
                return entry
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(
            "search.json exists but could not be read for entity lookup: %s", e
        )
    return None


def _collect_call_graph(
    result: dict[str, Any],
    repo_path: Path,
    entity_name: str,
    entity_file: str,
) -> None:
    """Extract call graph for *entity_name* and store in *result*."""
    try:
        from local_deepwiki.generators.analysis.callgraph import (
            CallGraphExtractor,
            build_reverse_call_graph,
        )

        full_file_path = (repo_path / entity_file).resolve()
        if full_file_path.exists() and full_file_path.is_relative_to(repo_path):
            extractor = CallGraphExtractor()
            call_graph = extractor.extract_from_file(full_file_path, repo_path)
            reverse_graph = build_reverse_call_graph(call_graph)
            result["call_graph"] = {
                "calls": call_graph.get(entity_name, []),
                "called_by": reverse_graph.get(entity_name, []),
            }
        else:
            result["call_graph"] = {
                "calls": [],
                "called_by": [],
                "note": "Source file not found",
            }
    except (OSError, ValueError, RuntimeError) as exc:
        # OSError: file read errors; ValueError: parsing errors; RuntimeError: tree-sitter errors
        _set_section_error(
            result, "call_graph", "Call graph extraction", entity_name, exc
        )


async def _collect_inheritance(
    result: dict[str, Any],
    entity_name: str,
    index_status: Any,
    vector_store: Any,
) -> None:
    """Collect inheritance hierarchy for a class entity."""
    try:
        from local_deepwiki.generators.analysis.inheritance import (
            collect_class_hierarchy,
        )

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
    except (OSError, ValueError, RuntimeError) as exc:
        # OSError: vector store errors; ValueError: data format errors; RuntimeError: collection errors
        _set_section_error(
            result, "inheritance", "Inheritance lookup", entity_name, exc
        )


async def _collect_test_examples(
    result: dict[str, Any],
    entity_name: str,
    entity_type: str,
    max_examples: int,
    repo_path: Path,
    vector_store: Any,
) -> None:
    """Extract test examples for *entity_name* from test files."""
    try:
        from local_deepwiki.generators.examples.orchestrator import CodeExampleExtractor

        extractor = CodeExampleExtractor(vector_store, repo_path=repo_path)
        if entity_type == "class":
            examples = await extractor.extract_examples_for_class(
                entity_name, max_examples=max_examples
            )
        else:
            examples = await extractor.extract_examples_for_function(
                entity_name, max_examples=max_examples
            )
            if not examples:
                examples = await extractor.extract_examples_for_class(
                    entity_name, max_examples=max_examples
                )
        result["test_examples"] = [
            {
                "code": ex.code,
                "source_file": ex.test_file,
                "description": ex.description,
            }
            for ex in examples
        ]
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        # OSError: vector store errors; ValueError: data format errors
        # RuntimeError: extraction errors; TypeError: incompatible argument types
        _set_section_error(
            result, "test_examples", "Test example extraction", entity_name, exc
        )


def _find_function_api_entry(
    functions: list[Any],
    classes_sigs: list[Any],
    entity_name: str,
) -> dict[str, Any] | None:
    """Find API doc entry for a function/method entity."""
    # Search top-level functions first
    for func_sig in functions:
        if func_sig.name == entity_name:
            return {
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

    # Fall back to class methods
    for cls_sig in classes_sigs:
        for m in cls_sig.methods:
            if m.name == entity_name:
                return {
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
    return None


def _find_class_api_entry(
    classes_sigs: list[Any],
    entity_name: str,
) -> dict[str, Any] | None:
    """Find API doc entry for a class entity."""
    for cls_sig in classes_sigs:
        if cls_sig.name == entity_name:
            return {
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
    return None


def _collect_api_docs(
    result: dict[str, Any],
    repo_path: Path,
    entity_name: str,
    entity_type: str,
    entity_file: str,
) -> None:
    """Extract API docs for *entity_name* and store in *result*."""
    try:
        from local_deepwiki.generators.analysis.api_docs import APIDocExtractor

        full_file_path = (repo_path / entity_file).resolve()
        if not (full_file_path.exists() and full_file_path.is_relative_to(repo_path)):
            result["api_docs"] = {"note": "Source file not found"}
            return

        api_extractor = APIDocExtractor()
        functions, classes_sigs = api_extractor.extract_from_file(full_file_path)

        if entity_type == "class":
            api_entry = _find_class_api_entry(classes_sigs, entity_name)
        else:
            api_entry = _find_function_api_entry(functions, classes_sigs, entity_name)

        if api_entry is not None:
            result["api_docs"] = api_entry
        else:
            result["api_docs"] = {
                "note": f"No API signature found for '{entity_name}' in {entity_file}"
            }
    except (OSError, ValueError, RuntimeError) as exc:
        # OSError: file read errors; ValueError: parsing errors; RuntimeError: tree-sitter errors
        _set_section_error(result, "api_docs", "API doc extraction", entity_name, exc)


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

    index_status, wiki_path, config = await _load_index_status(repo_path)

    # Check entity existence before creating vector store (avoids unnecessary work)
    entity_info = await _lookup_entity_in_search_index(wiki_path, entity_name)
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
        return make_tool_text_content("explain_entity", result)

    entity_type = entity_info.get("entity_type", "unknown")
    needs_vector_store = (
        validated.include_inheritance and entity_type == "class"
    ) or validated.include_test_examples
    vector_store = (
        _create_vector_store(repo_path, config) if needs_vector_store else None
    )

    svc = AnalysisService()
    result = await svc.explain_entity(
        EntityExplainRequest(
            entity_name=entity_name,
            repo_path=repo_path,
            index_status=index_status,
            wiki_path=wiki_path,
            vector_store=vector_store,
            include_call_graph=validated.include_call_graph,
            include_inheritance=validated.include_inheritance,
            include_test_examples=validated.include_test_examples,
            include_api_docs=validated.include_api_docs,
            max_test_examples=validated.max_test_examples,
        )
    )

    logger.info("Explain entity: '%s' in %s", entity_name, repo_path)
    return make_tool_text_content("explain_entity", result)


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

    full_file = validate_file_in_repo(repo_path, file_path)

    index_status, wiki_path, config = await _load_index_status(repo_path)

    needs_vector_store = validated.include_inheritance or validated.include_dependents
    vector_store = (
        _create_vector_store(repo_path, config) if needs_vector_store else None
    )

    svc = AnalysisService()
    result = await svc.impact_analysis(
        ImpactAnalysisRequest(
            file_path=file_path,
            full_file=full_file,
            repo_path=repo_path,
            index_status=index_status,
            wiki_path=wiki_path,
            vector_store=vector_store,
            entity_name=entity_name,
            include_reverse_calls=validated.include_reverse_calls,
            include_inheritance=validated.include_inheritance,
            include_dependents=validated.include_dependents,
            include_wiki_pages=validated.include_wiki_pages,
        )
    )

    risk_level = result.get("impact_summary", {}).get("risk_level", "unknown")
    affected_count = result.get("impact_summary", {}).get("total_affected_files", 0)

    logger.info(
        "Impact analysis: %s -> %d files, risk=%s",
        file_path,
        affected_count,
        risk_level,
    )
    return make_tool_text_content("impact_analysis", result)
