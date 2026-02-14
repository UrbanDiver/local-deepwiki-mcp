"""Entity-related analysis handlers: explain entity and impact analysis."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    ExplainEntityArgs,
    ImpactAnalysisArgs,
    Permission,
    ValidationError,
    _create_vector_store,
    _load_index_status,
    get_access_controller,
    handle_tool_errors,
    logger,
    make_tool_text_content,
    path_not_found_error,
    sanitize_error_message,
)


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

    # --- Step 1: Look up entity in search.json ---
    search_json_path = wiki_path / "search.json"
    entity_info = None
    if search_json_path.exists():
        try:
            search_content = await asyncio.to_thread(search_json_path.read_text)
            search_data = json.loads(search_content)
            entities_list = search_data.get("entities", [])
            for entry in entities_list:
                if entry.get("name") == entity_name:
                    entity_info = entry
                    break
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(
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
        return make_tool_text_content("explain_entity", result)

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
        except (OSError, ValueError, RuntimeError) as exc:
            # OSError: file read errors; ValueError: parsing errors; RuntimeError: tree-sitter errors
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
        except (OSError, ValueError, RuntimeError) as exc:
            # OSError: vector store errors; ValueError: data format errors; RuntimeError: collection errors
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
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            # OSError: vector store errors; ValueError: data format errors
            # RuntimeError: extraction errors; TypeError: incompatible argument types
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
        except (OSError, ValueError, RuntimeError) as exc:
            # OSError: file read errors; ValueError: parsing errors; RuntimeError: tree-sitter errors
            _set_section_error(
                result, "api_docs", "API doc extraction", entity_name, exc
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

    index_status, wiki_path, config = await _load_index_status(repo_path)

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
        except (OSError, ValueError, RuntimeError) as exc:
            # OSError: file read errors; ValueError: parsing errors; RuntimeError: tree-sitter errors
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
        except (OSError, ValueError, RuntimeError) as exc:
            # OSError: vector store errors; ValueError: data format errors; RuntimeError: collection errors
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
        except (OSError, ValueError, RuntimeError) as exc:
            # OSError: vector store errors; ValueError: data format errors; RuntimeError: context building errors
            _set_section_error(
                result, "file_dependents", "File dependents analysis", file_path, exc
            )

    # --- Section 4: Affected wiki pages ---
    if validated.include_wiki_pages:
        try:
            toc_path = wiki_path / "toc.json"
            matched_pages: list[dict[str, str]] = []
            if toc_path.exists():
                toc_content = await asyncio.to_thread(toc_path.read_text)
                toc_data = json.loads(toc_content)
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
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            # OSError: file read errors; JSONDecodeError: malformed JSON; KeyError: missing expected keys
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
    return make_tool_text_content("impact_analysis", result)
