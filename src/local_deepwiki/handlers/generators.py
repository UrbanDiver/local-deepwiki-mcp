"""Generator tool handlers: diagrams, call graphs, glossary, inheritance, coverage, etc."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    DetectSecretsArgs,
    DetectStaleDocsArgs,
    GetApiDocsArgs,
    GetCallGraphArgs,
    GetChangelogArgs,
    GetCoverageArgs,
    GetDiagramsArgs,
    GetGlossaryArgs,
    GetIndexStatusArgs,
    GetInheritanceArgs,
    GetTestExamplesArgs,
    ListIndexedReposArgs,
    Permission,
    ValidationError,
    _create_vector_store,
    _is_test_file,
    _load_index_status,
    get_access_controller,
    handle_tool_errors,
    logger,
    make_tool_text_content,
    path_not_found_error,
)


@handle_tool_errors
async def handle_get_glossary(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_glossary tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetGlossaryArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    search_term = validated.search

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.generators.glossary import collect_all_entities

    vector_store = _create_vector_store(repo_path, config)

    entities = await collect_all_entities(index_status, vector_store)

    if search_term:
        search_lower = search_term.lower()
        entities = [
            e
            for e in entities
            if search_lower in e.name.lower()
            or (e.docstring and search_lower in e.docstring.lower())
        ]

    if validated.file_path:
        filter_path = validated.file_path
        entities = [e for e in entities if e.file_path.endswith(filter_path)]

    total_entities = len(entities)
    entities = entities[validated.offset : validated.offset + validated.limit]

    result = {
        "status": "success",
        "total_entities": total_entities,
        "returned": len(entities),
        "offset": validated.offset,
        "limit": validated.limit,
        "has_more": validated.offset + validated.limit < total_entities,
        "entities": [
            {
                "name": e.name,
                "type": e.entity_type,
                "file_path": e.file_path,
                "docstring": e.docstring,
            }
            for e in entities
        ],
    }

    logger.info(
        "Glossary: %s/%s entities for %s", len(entities), total_entities, repo_path
    )
    return make_tool_text_content("get_glossary", result)


@handle_tool_errors
async def handle_get_diagrams(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_diagrams tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetDiagramsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    diagram_type = validated.diagram_type
    entry_point = validated.entry_point

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.generators.callgraph import CallGraphExtractor
    from local_deepwiki.generators.diagrams import (
        generate_class_diagram,
        generate_dependency_graph,
        generate_language_pie_chart,
        generate_module_overview,
        generate_sequence_diagram,
    )

    vector_store = _create_vector_store(repo_path, config)

    # Collect chunks from vector store for diagram generation
    all_chunks = list(vector_store.get_all_chunks())

    project_name = Path(repo_path).name.lower().replace("-", "_")

    # Lazy dict dispatch — only the requested generator runs
    simple_generators: dict[str, Callable[[], str | None]] = {
        "class": lambda: generate_class_diagram(all_chunks),
        "dependency": lambda: generate_dependency_graph(
            all_chunks,
            project_name=project_name,
            detect_circular=True,
            exclude_tests=True,
        ),
        "module": lambda: generate_module_overview(index_status),
        "language_pie": lambda: generate_language_pie_chart(index_status),
    }

    dtype = diagram_type.value
    generator = simple_generators.get(dtype)
    if generator is not None:
        diagram = generator()
    elif dtype == "sequence":
        if not entry_point:
            raise ValidationError(
                message="entry_point is required for sequence diagrams",
                hint="Provide the name of the function to use as the sequence diagram entry point.",
                field="entry_point",
            )
        # Build call graph first
        extractor = CallGraphExtractor()
        combined_graph: dict[str, list[str]] = {}
        for file_info in index_status.files:
            file_path = repo_path / file_info.path
            if file_path.exists():
                graph = extractor.extract_from_file(file_path, repo_path)
                for k, v in graph.items():
                    combined_graph.setdefault(k, []).extend(v)
        diagram = generate_sequence_diagram(combined_graph, entry_point=entry_point)
    else:
        diagram = None

    if diagram is None:
        return make_tool_text_content(
            "get_diagrams",
            {
                "message": f"No {diagram_type.value} diagram could be generated (no relevant data found)",
            },
        )

    result = {
        "status": "success",
        "diagram_type": diagram_type.value,
        "mermaid": diagram,
    }

    logger.info("Generated %s diagram for %s", diagram_type.value, repo_path)
    return make_tool_text_content("get_diagrams", result)


@handle_tool_errors
async def handle_get_inheritance(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_inheritance tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetInheritanceArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.generators.inheritance import (
        collect_class_hierarchy,
        generate_inheritance_diagram,
    )

    vector_store = _create_vector_store(repo_path, config)

    classes = await collect_class_hierarchy(index_status, vector_store)

    if not classes:
        return make_tool_text_content(
            "get_inheritance",
            {
                "message": "No class hierarchies found in the codebase",
                "classes": [],
            },
        )

    diagram = generate_inheritance_diagram(classes)

    class_list = list(classes.values())

    if validated.search:
        search_lower = validated.search.lower()
        class_list = [c for c in class_list if search_lower in c.name.lower()]

    total_classes = len(class_list)
    class_list = class_list[validated.offset : validated.offset + validated.limit]

    result = {
        "status": "success",
        "total_classes": total_classes,
        "returned": len(class_list),
        "offset": validated.offset,
        "limit": validated.limit,
        "has_more": validated.offset + validated.limit < total_classes,
        "classes": [
            {
                "name": node.name,
                "file_path": node.file_path,
                "parents": node.parents,
                "children": node.children,
                "is_abstract": node.is_abstract,
                "docstring": node.docstring,
            }
            for node in class_list
        ],
        "mermaid_diagram": diagram,
    }

    logger.info(
        f"Inheritance: {len(class_list)}/{total_classes} classes for {repo_path}"
    )
    return make_tool_text_content("get_inheritance", result)


@handle_tool_errors
async def handle_get_call_graph(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_call_graph tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetCallGraphArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    file_path = validated.file_path

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.callgraph import (
        CallGraphExtractor,
        generate_call_graph_diagram,
    )

    extractor = CallGraphExtractor()

    if file_path:
        # Validate file path is within repo (prevent traversal)
        target = (repo_path / file_path).resolve()
        if not target.is_relative_to(repo_path):
            raise ValidationError(
                message="Invalid file path: path traversal not allowed",
                hint="The file path must be within the repository.",
                field="file_path",
                value=file_path,
            )
        if not target.exists():
            raise path_not_found_error(file_path, "file")

        graph = extractor.extract_from_file(target, repo_path)
        diagram = generate_call_graph_diagram(graph, title=file_path)
    else:
        # Build combined call graph for entire repo
        index_status, wiki_path, config = await _load_index_status(repo_path)
        combined_graph: dict[str, list[str]] = {}
        for file_info in index_status.files:
            fp = repo_path / file_info.path
            if fp.exists():
                graph = extractor.extract_from_file(fp, repo_path)
                for k, v in graph.items():
                    combined_graph.setdefault(k, []).extend(v)
        diagram = generate_call_graph_diagram(combined_graph)

    if diagram is None:
        return make_tool_text_content(
            "get_call_graph",
            {"message": "No call relationships found"},
        )

    result = {
        "status": "success",
        "mermaid": diagram,
        "scope": file_path or "full_repository",
    }

    logger.info("Call graph generated for %s", file_path or repo_path)
    return make_tool_text_content("get_call_graph", result)


@handle_tool_errors
async def handle_get_coverage(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_coverage tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetCoverageArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.generators.coverage import analyze_project_coverage

    vector_store = _create_vector_store(repo_path, config)

    stats, file_coverages = await analyze_project_coverage(index_status, vector_store)

    result = {
        "status": "success",
        "overall": {
            "total_entities": stats.total_entities,
            "documented": stats.documented_entities,
            "undocumented": stats.total_entities - stats.documented_entities,
            "coverage_percent": round(stats.coverage_percent, 1),
        },
        "files": [
            {
                "file_path": fc.file_path,
                "coverage_percent": round(fc.stats.coverage_percent, 1),
                "undocumented": fc.undocumented,
            }
            for fc in file_coverages
            if fc.undocumented  # Only include files with gaps
        ],
    }

    logger.info("Coverage: %.1f%% for %s", stats.coverage_percent, repo_path)
    return make_tool_text_content("get_coverage", result)


@handle_tool_errors
async def handle_detect_stale_docs(args: dict[str, Any]) -> list[TextContent]:
    """Handle detect_stale_docs tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = DetectStaleDocsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    threshold_days = validated.threshold_days

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    _index_status, wiki_path, _config = await _load_index_status(repo_path)

    from local_deepwiki.generators.stale_detection import analyze_staleness
    from local_deepwiki.generators.wiki_status import WikiStatusManager

    manager = WikiStatusManager(wiki_path)
    wiki_status = await manager.load_status()

    if wiki_status is None:
        return make_tool_text_content(
            "detect_stale_docs",
            {
                "message": "No wiki generation status found. Run index_repository first.",
                "stale_pages": [],
            },
        )

    report = analyze_staleness(repo_path, wiki_status, threshold_days)

    result = {
        "status": "success",
        "total_pages": report.total_pages,
        "stale_count": report.stale_pages,
        "stale_pages": [
            {
                "page_path": info.page_path,
                "days_stale": info.days_stale,
                "source_files": info.source_files,
                "newest_source_date": info.newest_source_date.isoformat(),
                "generated_at": info.generated_at.isoformat(),
            }
            for info in report.stale_info
        ],
    }

    logger.info(
        f"Stale detection: {report.stale_pages}/{report.total_pages} stale for {repo_path}"
    )
    return make_tool_text_content("detect_stale_docs", result)


@handle_tool_errors
async def handle_get_changelog(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_changelog tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetChangelogArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    max_commits = validated.max_commits

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.changelog import generate_changelog_content

    content = await asyncio.to_thread(
        generate_changelog_content, repo_path, max_commits
    )

    if content is None:
        return make_tool_text_content(
            "get_changelog",
            {"message": "No git history found. Is this a git repository?"},
        )

    result = {
        "status": "success",
        "changelog": content,
    }

    logger.info("Changelog generated for %s", repo_path)
    return make_tool_text_content("get_changelog", result)


@handle_tool_errors
async def handle_detect_secrets(args: dict[str, Any]) -> list[TextContent]:
    """Handle detect_secrets tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = DetectSecretsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    if not repo_path.is_dir():
        raise ValidationError(
            message=f"Path is not a directory: {repo_path}",
            hint="Provide a path to a directory, not a file.",
            field="repo_path",
            value=str(repo_path),
        )

    from local_deepwiki.core.secret_detector import scan_repository_for_secrets

    findings_by_file = await asyncio.to_thread(scan_repository_for_secrets, repo_path)

    if validated.exclude_tests:
        findings_by_file = {
            path: findings
            for path, findings in findings_by_file.items()
            if not _is_test_file(path)
        }

    total_findings = sum(len(findings) for findings in findings_by_file.values())

    result = {
        "status": "success",
        "files_with_secrets": len(findings_by_file),
        "total_findings": total_findings,
        "exclude_tests": validated.exclude_tests,
        "findings": [
            {
                "file_path": file_path,
                "is_test_file": _is_test_file(file_path),
                "secrets": [
                    {
                        "type": f.secret_type.value,
                        "line": f.line_number,
                        "confidence": round(f.confidence, 2),
                        "recommendation": f.recommendation,
                    }
                    for f in findings
                ],
            }
            for file_path, findings in findings_by_file.items()
        ],
    }

    logger.info(
        f"Secret scan: {total_findings} findings in {len(findings_by_file)} files for {repo_path}"
    )
    return make_tool_text_content("detect_secrets", result)


@handle_tool_errors
async def handle_get_test_examples(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_test_examples tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = GetTestExamplesArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    entity_name = validated.entity_name
    max_examples = validated.max_examples

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = await _load_index_status(repo_path)

    from local_deepwiki.generators.test_examples import CodeExampleExtractor

    vector_store = _create_vector_store(repo_path, config)

    extractor = CodeExampleExtractor(vector_store, repo_path=repo_path)

    # Try function first, then class
    examples = await extractor.extract_examples_for_function(
        entity_name, max_examples=max_examples
    )
    if not examples:
        examples = await extractor.extract_examples_for_class(
            entity_name, max_examples=max_examples
        )

    if not examples:
        return make_tool_text_content(
            "get_test_examples",
            {
                "message": f"No test examples found for '{entity_name}'",
                "examples": [],
            },
        )

    result = {
        "status": "success",
        "entity_name": entity_name,
        "total_examples": len(examples),
        "examples": [
            {
                "source": e.source,
                "code": e.code,
                "description": e.description,
                "test_file": e.test_file,
                "language": e.language,
            }
            for e in examples
        ],
    }

    logger.info(
        "Test examples: %s for '%s' in %s", len(examples), entity_name, repo_path
    )
    return make_tool_text_content("get_test_examples", result)


@handle_tool_errors
async def handle_get_api_docs(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_api_docs tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetApiDocsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    file_path = validated.file_path

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    # Validate file path is within repo (prevent traversal)
    target = (repo_path / file_path).resolve()
    if not target.is_relative_to(repo_path):
        raise ValidationError(
            message="Invalid file path: path traversal not allowed",
            hint="The file path must be within the repository.",
            field="file_path",
            value=file_path,
        )

    if not target.exists():
        raise path_not_found_error(file_path, "file")

    from local_deepwiki.generators.api_docs import get_file_api_docs

    api_docs = await asyncio.to_thread(get_file_api_docs, target)

    if api_docs is None:
        return make_tool_text_content(
            "get_api_docs",
            {
                "message": f"No API documentation could be extracted from '{file_path}'",
            },
        )

    result = {
        "status": "success",
        "file_path": file_path,
        "api_docs": api_docs,
    }

    logger.info("API docs generated for %s", file_path)
    return make_tool_text_content("get_api_docs", result)


@handle_tool_errors
async def handle_list_indexed_repos(args: dict[str, Any]) -> list[TextContent]:
    """Handle list_indexed_repos tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = ListIndexedReposArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    base_path = (
        Path(validated.base_path).resolve() if validated.base_path else Path.cwd()
    )

    if not base_path.exists():
        raise path_not_found_error(str(base_path), "directory")

    from local_deepwiki.core.index_manager import IndexStatusManager

    manager = IndexStatusManager()
    repos: list[dict[str, Any]] = []

    # Search for .deepwiki directories
    for deepwiki_dir in base_path.rglob(".deepwiki"):
        if not deepwiki_dir.is_dir():
            continue
        status = manager.load(deepwiki_dir)
        if status is not None:
            repos.append(
                {
                    "repo_path": status.repo_path,
                    "wiki_path": str(deepwiki_dir),
                    "total_files": status.total_files,
                    "total_chunks": status.total_chunks,
                    "languages": status.languages,
                    "indexed_at": status.indexed_at,
                }
            )

    result = {
        "status": "success",
        "total_repos": len(repos),
        "repos": repos,
    }

    logger.info("Found %s indexed repos under %s", len(repos), base_path)
    return make_tool_text_content("list_indexed_repos", result)


@handle_tool_errors
async def handle_get_index_status(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_index_status tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetIndexStatusArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, wiki_path, config = await _load_index_status(repo_path)

    from datetime import datetime

    result = {
        "status": "success",
        "repo_path": index_status.repo_path,
        "wiki_path": str(wiki_path),
        "indexed_at": index_status.indexed_at,
        "indexed_at_human": datetime.fromtimestamp(index_status.indexed_at).isoformat(),
        "total_files": index_status.total_files,
        "total_chunks": index_status.total_chunks,
        "languages": index_status.languages,
        "schema_version": index_status.schema_version,
    }

    logger.info(
        f"Index status: {index_status.total_files} files, {index_status.total_chunks} chunks for {repo_path}"
    )
    return make_tool_text_content("get_index_status", result)
