"""Architecture analysis handlers: layer dependencies and architecture summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.errors import path_not_found_error
from local_deepwiki.generators.analysis.source_filter import iter_python_files
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    CompareArchitectureArgs,
    GetArchitectureHealthArgs,
    GetArchitectureSummaryArgs,
    GetCouplingMetricsArgs,
    GetCrossModuleDependenciesArgs,
    GetDesignSmellsArgs,
    GetHotspotsArgs,
    GetLayerDependenciesArgs,
    GetModuleHealthArgs,
)
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

    if validated.summary_only:
        result: dict[str, Any] = {
            "status": "success",
            "project_name": project_name,
            "total_violations": layer_result["total_violations"],
            "tool": "get_layer_dependencies",
        }
    else:
        result = {
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


@handle_tool_errors
async def handle_get_hotspots(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_hotspots tool call.

    Ranks all functions in the repository by a chosen complexity metric
    (cyclomatic complexity, parameter count, line length, or nesting depth).
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetHotspotsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.hotspots import analyze_hotspots

    result = analyze_hotspots(
        repo_path=repo_path,
        metric=validated.metric,
        top_n=validated.top_n,
        min_threshold=validated.min_threshold,
        exclude_tests=validated.exclude_tests,
    )

    if validated.summary_only:
        result = {
            "status": result.get("status", "success"),
            "stats": result.get("stats", {}),
            "tool": result.get("tool", "get_hotspots"),
        }

    logger.info(
        "Hotspots: %d results for metric=%s in %s",
        len(result.get("hotspots", [])),
        validated.metric,
        repo_path,
    )
    return make_tool_text_content("get_hotspots", result)


def _count_smells_by_type(smells: list[dict[str, Any]]) -> dict[str, int]:
    """Count smell occurrences grouped by type.

    Returns a new dict mapping smell type to its count.
    """
    counts: dict[str, int] = {}
    for smell in smells:
        t = smell["type"]
        counts[t] = counts.get(t, 0) + 1
    return counts


def _count_module_edges(edges: list[dict[str, Any]]) -> dict[str, int]:
    """Count total edge appearances (source + target) per module name.

    Returns a new dict mapping module name to its total edge count.
    """
    counts: dict[str, int] = {}
    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        counts[src] = counts.get(src, 0) + 1
        counts[tgt] = counts.get(tgt, 0) + 1
    return counts


@handle_tool_errors
async def handle_get_cross_module_dependencies(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_cross_module_dependencies tool call.

    Builds the inter-module import graph for the repository and returns
    module nodes, weighted edges, stats, and a Mermaid diagram.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetCrossModuleDependenciesArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.module_dependencies import (
        analyze_cross_module_dependencies,
    )

    result = analyze_cross_module_dependencies(
        repo_path=repo_path,
        module_filter=validated.module_filter,
        include_external=validated.include_external,
        min_edge_weight=validated.min_edge_weight,
    )

    # Apply overflow-prevention filters (immutable — new dicts, no mutation).
    if validated.summary_only:
        result = {
            "status": result.get("status", "success"),
            "stats": result.get("stats", {}),
            "tool": result.get("tool", "get_cross_module_dependencies"),
        }
    else:
        edges = result.get("edges", [])
        edge_counts: dict[str, int] = _count_module_edges(edges)
        modules = sorted(
            result.get("modules", []),
            key=lambda m: edge_counts.get(m.get("name", ""), 0),
            reverse=True,
        )
        result = {**result, "modules": modules[: validated.top_n]}

    logger.info(
        "Cross-module deps: %d modules, %d edges in %s",
        result.get("stats", {}).get("total_modules", 0),
        result.get("stats", {}).get("total_edges", 0),
        repo_path,
    )
    return make_tool_text_content("get_cross_module_dependencies", result)


@handle_tool_errors
async def handle_get_coupling_metrics(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_coupling_metrics tool call.

    Computes Robert C. Martin coupling metrics (Ca, Ce, I, A, D) per module.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetCouplingMetricsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics

    result = analyze_coupling_metrics(
        repo_path=repo_path,
        module_filter=validated.module_filter,
    )

    # Filter out pure leaf modules (Ce == 0) unless explicitly requested.
    if not validated.include_leaves:
        metrics = result.get("metrics", [])
        filtered = [m for m in metrics if m.get("efferent_coupling", 0) > 0]
        result = {
            **result,
            "metrics": filtered,
            "stats": {
                **result.get("stats", {}),
                "filtered_modules": len(metrics) - len(filtered),
            },
        }

    # Apply overflow-prevention filters (immutable — new dicts, no mutation).
    if validated.summary_only:
        result = {
            "status": result.get("status", "success"),
            "stats": result.get("stats", {}),
            "tool": result.get("tool", "get_coupling_metrics"),
        }
    else:
        metrics = sorted(
            result.get("metrics", []),
            key=lambda m: m.get("distance", 0),
            reverse=True,
        )
        result = {**result, "metrics": metrics[: validated.top_n]}

    logger.info(
        "Coupling metrics: %d modules analyzed in %s",
        result.get("stats", {}).get("total_modules", 0),
        repo_path,
    )
    return make_tool_text_content("get_coupling_metrics", result)


@handle_tool_errors
async def handle_get_design_smells(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_design_smells tool call.

    Detects design smells (God Class, Long Method, Feature Envy, etc.) using
    heuristic AST-based thresholds.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetDesignSmellsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.design_smells import analyze_design_smells

    result = analyze_design_smells(
        repo_path=repo_path,
        severity_threshold=validated.severity_threshold,
        exclude_tests=validated.exclude_tests,
    )

    # Apply overflow-prevention filters (immutable — new dicts, no mutation).
    if validated.summary_only:
        smells = result.get("smells", [])
        smells_by_type = _count_smells_by_type(smells)
        result = {
            **{k: v for k, v in result.items() if k != "smells"},
            "smells_by_type": smells_by_type,
            "total_smells": len(smells),
        }
    elif validated.top_n is not None:
        result = {**result, "smells": result.get("smells", [])[: validated.top_n]}

    logger.info(
        "Design smells: %d smells found in %s",
        result.get("summary", {}).get("total", 0),
        repo_path,
    )
    return make_tool_text_content("get_design_smells", result)


@handle_tool_errors
async def handle_get_architecture_health(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_architecture_health tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetArchitectureHealthArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.architecture_health import (
        analyze_architecture_health,
    )
    from local_deepwiki.generators.manifest import get_cached_manifest

    manifest = get_cached_manifest(repo_path)
    project_name = manifest.name or repo_path.name
    result = analyze_architecture_health(
        repo_path,
        project_name,
        top_findings=validated.top_findings,
    )
    logger.info(
        "Architecture health: %s (%s) in %s",
        result.get("overall", {}).get("grade"),
        result.get("overall", {}).get("score"),
        repo_path,
    )
    return make_tool_text_content("get_architecture_health", result)


@handle_tool_errors
async def handle_compare_architecture(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle compare_architecture tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = CompareArchitectureArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.architecture_compare import (
        compare_architecture,
    )
    from local_deepwiki.generators.manifest import get_cached_manifest

    manifest = get_cached_manifest(repo_path)
    project_name = manifest.name or repo_path.name
    result = compare_architecture(
        repo_path,
        project_name,
        base_ref=validated.base_ref,
        head_ref=validated.head_ref,
    )
    logger.info(
        "Architecture comparison %s..%s in %s",
        validated.base_ref,
        validated.head_ref,
        repo_path,
    )
    return make_tool_text_content("compare_architecture", result)


@handle_tool_errors
async def handle_get_module_health(
    args: dict[str, Any],
) -> list[TextContent]:
    """Handle get_module_health tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = GetModuleHealthArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.module_health import analyze_module_health

    result = analyze_module_health(repo_path, validated.module_name)
    logger.info(
        "Module health for %s: score=%s in %s",
        validated.module_name,
        result.get("health", {}).get("score"),
        repo_path,
    )
    return make_tool_text_content("get_module_health", result)
