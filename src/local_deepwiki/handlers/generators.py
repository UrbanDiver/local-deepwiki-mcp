"""Generator tool handlers: diagrams, call graphs, glossary, inheritance, coverage, etc."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.core.path_utils import find_deepwiki_dirs, validate_file_in_repo
from local_deepwiki.errors import ValidationError, path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._index_helpers import (
    _create_vector_store,
    _is_test_file,
    _load_index_status,
)
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.handlers.types import SecretScanResult
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
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
)
from local_deepwiki.security import Permission, get_access_controller
from local_deepwiki.services.generator_service import GeneratorService

logger = get_logger(__name__)


def _build_generator_service(repo_path: Path, config: Any) -> GeneratorService:
    """Create a GeneratorService with a vector store for the given repo."""
    vector_store = _create_vector_store(repo_path, config)
    return GeneratorService(vector_store, config)


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

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, _wiki_path, config = await _load_index_status(repo_path)
    svc = _build_generator_service(repo_path, config)

    result = await svc.generate_glossary(
        index_status,
        search=validated.search,
        file_path=validated.file_path,
        offset=validated.offset,
        limit=validated.limit,
    )

    logger.info(
        "Glossary: %s/%s entities for %s",
        result.get("returned", 0),
        result.get("total_entities", 0),
        repo_path,
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

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    index_status, _wiki_path, config = await _load_index_status(repo_path)
    svc = _build_generator_service(repo_path, config)

    result = await svc.generate_diagrams(
        index_status,
        repo_path,
        validated.diagram_type.value,
        entry_point=validated.entry_point,
    )

    logger.info("Generated %s diagram for %s", validated.diagram_type.value, repo_path)
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

    index_status, _wiki_path, config = await _load_index_status(repo_path)
    svc = _build_generator_service(repo_path, config)

    result = await svc.generate_inheritance(
        index_status,
        search=validated.search,
        offset=validated.offset,
        limit=validated.limit,
    )

    logger.info(
        "Inheritance: %d/%d classes for %s",
        result.get("returned", 0),
        result.get("total_classes", 0),
        repo_path,
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

    from local_deepwiki.generators.analysis.callgraph import (
        CallGraphExtractor,
        generate_call_graph_diagram,
    )

    extractor = CallGraphExtractor()

    if file_path:
        target = validate_file_in_repo(repo_path, file_path)
        graph = extractor.extract_from_file(target, repo_path)
        diagram = generate_call_graph_diagram(graph, title=file_path)
        if diagram is None:
            result: dict[str, Any] = {"message": "No call relationships found"}
        else:
            result = {"status": "success", "mermaid": diagram, "scope": file_path}
    else:
        index_status, _wiki_path, config = await _load_index_status(repo_path)
        svc = _build_generator_service(repo_path, config)
        result = await svc.generate_call_graph(repo_path, index_status=index_status)

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

    index_status, _wiki_path, config = await _load_index_status(repo_path)
    svc = _build_generator_service(repo_path, config)

    result = await svc.generate_coverage(index_status)

    logger.info(
        "Coverage: %.1f%% for %s",
        result.get("overall", {}).get("coverage_percent", 0),
        repo_path,
    )
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

    _index_status, wiki_path, config = await _load_index_status(repo_path)
    svc = _build_generator_service(repo_path, config)

    result = await svc.detect_stale_docs(
        repo_path, wiki_path, threshold_days=validated.threshold_days
    )

    logger.info(
        "Stale detection: %d/%d stale for %s",
        result.get("stale_count", 0),
        result.get("total_pages", 0),
        repo_path,
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

    svc = GeneratorService.__new__(GeneratorService)
    result = await svc.generate_changelog(repo_path, max_commits=max_commits)

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

    svc = GeneratorService.__new__(GeneratorService)
    result = await svc.detect_secrets(repo_path, exclude_tests=validated.exclude_tests)

    logger.info(
        "Secret scan: %d findings in %d files for %s",
        result.get("total_findings", 0),
        result.get("files_with_secrets", 0),
        repo_path,
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

    _index_status, _wiki_path, config = await _load_index_status(repo_path)
    svc = _build_generator_service(repo_path, config)

    result = await svc.generate_test_examples(
        repo_path, entity_name, max_examples=max_examples
    )

    logger.info(
        "Test examples: %s for '%s' in %s",
        result.get("total_examples", 0),
        entity_name,
        repo_path,
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

    svc = GeneratorService.__new__(GeneratorService)
    result = await svc.get_api_docs(repo_path, file_path)

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

    svc = GeneratorService.__new__(GeneratorService)
    result = await svc.list_indexed_repos(base_path)

    logger.info(
        "Found %s indexed repos under %s", result.get("total_repos", 0), base_path
    )
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

    index_status, wiki_path, _config = await _load_index_status(repo_path)

    svc = GeneratorService.__new__(GeneratorService)
    result = await svc.get_index_status(index_status, wiki_path)

    logger.info(
        "Index status: %d files, %d chunks for %s",
        index_status.total_files,
        index_status.total_chunks,
        repo_path,
    )
    return make_tool_text_content("get_index_status", result)
