"""Analysis service: entity explanation and impact analysis business logic.

Extracted from handlers/analysis_entity.py. Encapsulates the composite
analysis patterns (parallel sub-analyses, risk computation) while the
handler layer retains RBAC, arg validation, and MCP response formatting.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import sanitize_error_message
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


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


class AnalysisService:
    """Encapsulates entity explanation and impact analysis business logic.

    Methods return plain dicts suitable for JSON serialization.
    The handler layer is responsible for RBAC, arg validation,
    and MCP response formatting.
    """

    __slots__ = ()

    async def explain_entity(
        self,
        entity_name: str,
        repo_path: Path,
        index_status: Any,
        wiki_path: Path,
        vector_store: VectorStore | None,
        *,
        include_call_graph: bool = True,
        include_inheritance: bool = True,
        include_test_examples: bool = True,
        include_api_docs: bool = True,
        max_test_examples: int = 3,
    ) -> dict[str, Any]:
        """Composite explanation of a code entity.

        Combines glossary lookup, call graph, inheritance, test examples,
        and API docs for a single named entity.

        Args:
            entity_name: Name of the entity to explain.
            repo_path: Resolved repository path.
            index_status: Loaded IndexStatus for the repository.
            wiki_path: Path to the wiki directory.
            vector_store: Optional vector store (needed for inheritance/tests).
            include_call_graph: Whether to include call graph data.
            include_inheritance: Whether to include inheritance data.
            include_test_examples: Whether to include test examples.
            include_api_docs: Whether to include API docs.
            max_test_examples: Maximum test examples to include.

        Returns:
            Dict with entity info and analysis sections.
        """
        entity_info = await _lookup_entity_in_search_index(wiki_path, entity_name)
        if entity_info is None:
            return {
                "status": "success",
                "entity_name": entity_name,
                "entity_found": False,
                "message": (
                    f"Entity '{entity_name}' not found in the search index. "
                    "Try using fuzzy_search or search_wiki to find the correct name."
                ),
            }

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

        if include_call_graph and entity_file:
            _collect_call_graph(result, repo_path, entity_name, entity_file)

        if include_inheritance and entity_type == "class" and vector_store is not None:
            await _collect_inheritance(result, entity_name, index_status, vector_store)

        if include_test_examples and vector_store is not None:
            await _collect_test_examples(
                result,
                entity_name,
                entity_type,
                max_test_examples,
                repo_path,
                vector_store,
            )

        if include_api_docs and entity_file:
            _collect_api_docs(result, repo_path, entity_name, entity_type, entity_file)

        return result

    async def impact_analysis(
        self,
        file_path: str,
        full_file: Path,
        repo_path: Path,
        index_status: Any,
        wiki_path: Path,
        vector_store: VectorStore | None,
        *,
        entity_name: str | None = None,
        include_reverse_calls: bool = True,
        include_inheritance: bool = True,
        include_dependents: bool = True,
        include_wiki_pages: bool = True,
    ) -> dict[str, Any]:
        """Analyze the blast radius of changes to a file or entity.

        Examines reverse call graph, inheritance dependents, file imports,
        and wiki pages to determine impact.

        Args:
            file_path: Relative path to the target file.
            full_file: Resolved absolute path to the target file.
            repo_path: Resolved repository path.
            index_status: Loaded IndexStatus for the repository.
            wiki_path: Path to the wiki directory.
            vector_store: Optional vector store (needed for inheritance/dependents).
            entity_name: Optional entity to scope the analysis to.
            include_reverse_calls: Whether to include reverse call graph.
            include_inheritance: Whether to include inheritance dependents.
            include_dependents: Whether to include file dependents.
            include_wiki_pages: Whether to include affected wiki pages.

        Returns:
            Dict with impact analysis results and risk level.
        """
        result: dict[str, Any] = {
            "status": "success",
            "file_path": file_path,
            "entity_name": entity_name,
        }

        affected_files: set[str] = set()
        affected_entities: set[str] = set()

        if include_reverse_calls:
            _collect_reverse_calls(
                result,
                full_file,
                repo_path,
                file_path,
                entity_name,
                affected_files,
                affected_entities,
            )

        if include_inheritance:
            await _collect_inheritance_dependents(
                result,
                file_path,
                entity_name,
                index_status,
                vector_store,
                affected_files,
                affected_entities,
            )

        if include_dependents:
            await _collect_file_dependents(
                result,
                file_path,
                repo_path,
                vector_store,
                affected_files,
            )

        if include_wiki_pages:
            await _collect_affected_wiki_pages(result, wiki_path, file_path)

        risk_level = _compute_risk_level(len(affected_files))
        result["impact_summary"] = {
            "total_affected_files": len(affected_files),
            "total_affected_entities": len(affected_entities),
            "risk_level": risk_level,
        }

        return result


# ---------------------------------------------------------------------------
# explain_entity helpers
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
        _set_section_error(
            result, "test_examples", "Test example extraction", entity_name, exc
        )


def _find_function_api_entry(
    functions: list[Any],
    classes_sigs: list[Any],
    entity_name: str,
) -> dict[str, Any] | None:
    """Find API doc entry for a function/method entity."""
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
        _set_section_error(result, "api_docs", "API doc extraction", entity_name, exc)


# ---------------------------------------------------------------------------
# impact_analysis helpers
# ---------------------------------------------------------------------------


def _has_import_of_module(content: str, module_stem: str) -> bool:
    """Check whether *content* contains an import line referencing *module_stem*."""
    pattern = (
        rf"(?:^|\n)\s*(?:from\s+\S*\.?{re.escape(module_stem)}\s+import"
        rf"|import\s+\S*\.?{re.escape(module_stem)})\b"
    )
    return re.search(pattern, content) is not None


def _find_cross_file_callers(
    extractor: Any,
    repo_path: Path,
    target_file: Path,
    module_stem: str,
    target_entities: set[str],
) -> dict[str, list[str]]:
    """Scan other source files for callers of *target_entities*."""
    from local_deepwiki.core.parser.languages import EXTENSION_MAP

    cross_callers: dict[str, list[str]] = {}
    resolved_target = target_file.resolve()
    supported_suffixes = set(EXTENSION_MAP.keys())

    for candidate in repo_path.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in supported_suffixes:
            continue
        if candidate.resolve() == resolved_target:
            continue
        rel_parts = candidate.relative_to(repo_path).parts
        if any(part.startswith(".") or part == "node_modules" for part in rel_parts):
            continue

        try:
            content = candidate.read_text(errors="ignore")
        except OSError:
            continue

        if not _has_import_of_module(content, module_stem):
            continue

        try:
            cand_call_graph = extractor.extract_from_file(
                candidate.resolve(), repo_path
            )
        except (OSError, ValueError, RuntimeError):
            continue

        rel_path = str(candidate.relative_to(repo_path))

        for caller_func, callees in cand_call_graph.items():
            for callee in callees:
                if callee in target_entities:
                    qualified = f"{rel_path}:{caller_func}"
                    if callee not in cross_callers:
                        cross_callers[callee] = []
                    if qualified not in cross_callers[callee]:
                        cross_callers[callee].append(qualified)

    return cross_callers


def _collect_reverse_calls(
    result: dict[str, Any],
    full_file: Path,
    repo_path: Path,
    file_path: str,
    entity_name: str | None,
    affected_files: set[str],
    affected_entities: set[str],
) -> None:
    """Extract reverse call graph and update affected sets."""
    try:
        from local_deepwiki.generators.analysis.callgraph import (
            CallGraphExtractor,
            build_reverse_call_graph,
        )

        extractor = CallGraphExtractor()
        call_graph = extractor.extract_from_file(full_file.resolve(), repo_path)
        reverse_graph = build_reverse_call_graph(call_graph)

        target_module_stem = Path(file_path).stem
        all_target_entities = set(call_graph.keys()) | set(reverse_graph.keys())
        if entity_name:
            all_target_entities.add(entity_name)

        cross_callers = _find_cross_file_callers(
            extractor, repo_path, full_file, target_module_stem, all_target_entities
        )

        for callee, callers in cross_callers.items():
            if callee not in reverse_graph:
                reverse_graph[callee] = []
            for caller in callers:
                if caller not in reverse_graph[callee]:
                    reverse_graph[callee].append(caller)

        if entity_name:
            reverse_graph = {k: v for k, v in reverse_graph.items() if k == entity_name}

        result["reverse_call_graph"] = reverse_graph

        for callee, callers in reverse_graph.items():
            affected_entities.add(callee)
            for caller in callers:
                affected_entities.add(caller)
                if ":" in caller:
                    rel_file = caller.split(":")[0]
                    affected_files.add(rel_file)
                elif "." in caller:
                    affected_files.add(caller.rsplit(".", 1)[0])
    except (OSError, ValueError, RuntimeError) as exc:
        _set_section_error(
            result,
            "reverse_call_graph",
            "Reverse call graph extraction",
            file_path,
            exc,
        )


async def _collect_inheritance_dependents(
    result: dict[str, Any],
    file_path: str,
    entity_name: str | None,
    index_status: Any,
    vector_store: Any,
    affected_files: set[str],
    affected_entities: set[str],
) -> None:
    """Collect classes that inherit from classes in *file_path*."""
    try:
        from local_deepwiki.generators.analysis.inheritance import (
            collect_class_hierarchy,
        )

        if vector_store is None:
            raise ValueError("Vector store required for inheritance analysis")
        classes = await collect_class_hierarchy(index_status, vector_store)

        inheritance_dependents: dict[str, list[str]] = {}
        for class_name, node in classes.items():
            if node.file_path != file_path:
                continue
            if entity_name and class_name != entity_name:
                continue
            children_with_files: list[str] = []
            for child_name in node.children:
                child_node = classes.get(child_name)
                if child_node and child_node.file_path != file_path:
                    children_with_files.append(f"{child_node.file_path}:{child_name}")
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
        _set_section_error(
            result, "inheritance_dependents", "Inheritance analysis", file_path, exc
        )


async def _collect_file_dependents(
    result: dict[str, Any],
    file_path: str,
    repo_path: Path,
    vector_store: Any,
    affected_files: set[str],
) -> None:
    """Find files that import or depend on *file_path*."""
    try:
        from local_deepwiki.generators.context_builder import build_file_context

        if vector_store is None:
            raise ValueError("Vector store required for file dependents analysis")
        chunks = await vector_store.get_chunks_by_file(file_path)

        if not chunks:
            result["file_dependents"] = {
                "importing_files": [],
                "related_files": [],
            }
            return

        context = await build_file_context(
            file_path=file_path,
            chunks=chunks,
            repo_path=repo_path,
            vector_store=vector_store,
        )

        importing_files: list[str] = []
        for _entity, caller_files in context.callers.items():
            for cf in caller_files:
                if cf != file_path and cf not in importing_files:
                    importing_files.append(cf)
                    affected_files.add(cf)

        result["file_dependents"] = {
            "importing_files": importing_files,
            "related_files": [rf for rf in context.related_files if rf != file_path],
        }
    except (OSError, ValueError, RuntimeError) as exc:
        _set_section_error(
            result, "file_dependents", "File dependents analysis", file_path, exc
        )


async def _collect_affected_wiki_pages(
    result: dict[str, Any],
    wiki_path: Path,
    file_path: str,
) -> None:
    """Find wiki pages that document *file_path*."""
    try:
        toc_path = wiki_path / "toc.json"
        matched_pages: list[dict[str, str]] = []
        if toc_path.exists():
            toc_content = await asyncio.to_thread(toc_path.read_text)
            toc_data = json.loads(toc_content)
            pages = (
                toc_data if isinstance(toc_data, list) else toc_data.get("pages", [])
            )
            for page in pages:
                if page.get("source_file", "") == file_path:
                    matched_pages.append(
                        {
                            "title": page.get("title", ""),
                            "path": page.get("path", ""),
                        }
                    )
        result["affected_wiki_pages"] = matched_pages
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        _set_section_error(
            result, "affected_wiki_pages", "Wiki page lookup", file_path, exc
        )


def _compute_risk_level(affected_file_count: int) -> str:
    """Return ``low``, ``medium``, or ``high`` based on affected file count."""
    if affected_file_count <= 2:
        return "low"
    if affected_file_count <= 10:
        return "medium"
    return "high"
