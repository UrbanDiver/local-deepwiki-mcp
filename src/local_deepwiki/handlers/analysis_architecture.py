"""Architecture analysis handlers: layer dependencies and architecture summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.errors import path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import GetArchitectureSummaryArgs, GetLayerDependenciesArgs
from local_deepwiki.security import Permission, get_access_controller

logger = get_logger(__name__)

# Threshold for flagging large files (lines).
_LARGE_FILE_LINE_THRESHOLD = 800

# Maximum number of largest files to include in the summary.
_TOP_LARGEST_FILES = 10


@handle_tool_errors
async def handle_get_layer_dependencies(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_layer_dependencies tool call.

    Runs static layer dependency analysis on Python files in the repository,
    categorizing them into architectural layers and detecting upward
    dependency violations.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetLayerDependenciesArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.layer_analysis import (
        analyze_layer_dependencies,
    )
    from local_deepwiki.generators.manifest import get_cached_manifest

    manifest = get_cached_manifest(repo_path)
    project_name = manifest.name or repo_path.name

    layer_result = analyze_layer_dependencies(repo_path, project_name)

    result: dict[str, Any] = {
        "status": "success",
        "project_name": project_name,
        **layer_result,
    }

    logger.info(
        "Layer dependencies: %d violations in %s",
        layer_result["total_violations"],
        repo_path,
    )
    return make_tool_text_content("get_layer_dependencies", result)


def _collect_file_metrics(repo_path: Path) -> dict[str, Any]:
    """Scan .py files and compute file-level metrics.

    Returns a dict with total_files, total_lines, largest_files (sorted
    descending by line count), and files_over_threshold (count of files
    exceeding ``_LARGE_FILE_LINE_THRESHOLD`` lines).
    """
    file_sizes: list[dict[str, Any]] = []
    total_lines = 0
    files_over_threshold = 0

    for py_file in sorted(repo_path.rglob("*.py")):
        try:
            rel_path = py_file.relative_to(repo_path)
        except ValueError:
            continue

        # Skip hidden dirs and common non-source trees
        rel_parts = rel_path.parts
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__")
            for part in rel_parts
        ):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        line_count = content.count("\n") + (
            1 if content and not content.endswith("\n") else 0
        )
        total_lines += line_count

        file_sizes.append({"file": str(rel_path), "lines": line_count})
        if line_count > _LARGE_FILE_LINE_THRESHOLD:
            files_over_threshold += 1

    # Sort by line count descending, take top N
    file_sizes.sort(key=lambda f: f["lines"], reverse=True)
    largest_files = file_sizes[:_TOP_LARGEST_FILES]

    return {
        "total_files": len(file_sizes),
        "total_lines": total_lines,
        "largest_files": largest_files,
        "files_over_threshold": files_over_threshold,
        "threshold_lines": _LARGE_FILE_LINE_THRESHOLD,
    }


@handle_tool_errors
async def handle_get_architecture_summary(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_architecture_summary tool call.

    Composite tool that combines layer dependency analysis with file metrics
    to give a high-level architecture overview.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetArchitectureSummaryArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.layer_analysis import (
        analyze_layer_dependencies,
    )
    from local_deepwiki.generators.manifest import get_cached_manifest

    manifest = get_cached_manifest(repo_path)
    project_name = manifest.name or repo_path.name

    layer_analysis = analyze_layer_dependencies(repo_path, project_name)
    file_metrics = _collect_file_metrics(repo_path)

    result: dict[str, Any] = {
        "status": "success",
        "project_name": project_name,
        "layer_analysis": layer_analysis,
        "file_metrics": file_metrics,
    }

    logger.info(
        "Architecture summary: %d violations, %d files in %s",
        layer_analysis["total_violations"],
        file_metrics["total_files"],
        repo_path,
    )
    return make_tool_text_content("get_architecture_summary", result)
