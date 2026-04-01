"""Agentic workflow runners: multi-step workflow execution via existing handlers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.errors import path_not_found_error
from local_deepwiki.handlers._error_handling import ToolHandler, handle_tool_errors
from local_deepwiki.handlers._response import wrap_tool_response
from local_deepwiki.logging import get_logger
from local_deepwiki.models import RunWorkflowArgs
from local_deepwiki.security import Permission, get_access_controller

logger = get_logger(__name__)
from local_deepwiki.handlers.agentic_data import (
    WORKFLOW_PRESETS,
    _WORKFLOW_RUNNER_NAMES,
)


async def _run_step(
    handler_func: ToolHandler, step_name: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Run a single workflow step with error handling.

    Args:
        handler_func: The async handler function to call.
        step_name: Human-readable step name for the result.
        args: Arguments to pass to the handler.

    Returns:
        Step result dict with status, name, and data or error.
    """
    try:
        result = await handler_func(args)
        # Extract text content from the result
        text = result[0].text if result else ""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": text[:500]}
        return {"step": step_name, "status": "success", "data": data}
    except Exception as e:  # noqa: BLE001
        logger.warning("Workflow step '%s' failed: %s", step_name, e)
        return {"step": step_name, "status": "error", "error": str(e)}


async def _run_onboarding(repo_path: str) -> list[dict[str, Any]]:
    """Run the onboarding workflow.

    Project manifest runs in parallel with wiki-dependent steps.
    The three wiki steps are also independent of each other.
    """
    from local_deepwiki.handlers.analysis_metadata import (
        handle_get_project_manifest,
        handle_get_wiki_stats,
    )
    from local_deepwiki.handlers.codemap import handle_suggest_codemap_topics
    from local_deepwiki.handlers.core import handle_read_wiki_structure

    # Check if wiki exists before reading structure
    from local_deepwiki.config import get_config

    config = get_config()
    wiki_path = config.get_wiki_path(Path(repo_path).resolve())

    if wiki_path.exists():
        # All four steps are independent — run in parallel
        results = await asyncio.gather(
            _run_step(
                handle_get_project_manifest,
                "get_project_manifest",
                {"repo_path": repo_path},
            ),
            _run_step(
                handle_read_wiki_structure,
                "read_wiki_structure",
                {"wiki_path": str(wiki_path)},
            ),
            _run_step(
                handle_get_wiki_stats, "get_wiki_stats", {"repo_path": repo_path}
            ),
            _run_step(
                handle_suggest_codemap_topics,
                "suggest_codemap_topics",
                {"repo_path": repo_path},
            ),
        )
        return list(results)

    # Wiki not indexed — manifest only, skip wiki steps
    manifest_step = await _run_step(
        handle_get_project_manifest,
        "get_project_manifest",
        {"repo_path": repo_path},
    )
    return [
        manifest_step,
        {
            "step": "read_wiki_structure",
            "status": "skipped",
            "reason": "Wiki not indexed yet",
        },
    ]


async def _run_security_audit(repo_path: str) -> list[dict[str, Any]]:
    """Run the security audit workflow.

    Secret detection and complexity metrics are independent, so they
    run in parallel.  Individual complexity-metrics calls are also
    independent of each other.
    """
    from local_deepwiki.handlers.analysis_metadata import handle_get_complexity_metrics
    from local_deepwiki.handlers.generators import handle_detect_secrets

    # Try to find top-level source files for complexity analysis
    repo = Path(repo_path)
    source_files: list[Path] = []
    for ext in ("*.py", "*.ts", "*.js", "*.go", "*.rs"):
        source_files.extend(repo.rglob(ext))
        if len(source_files) >= 5:
            break

    # Build all coroutines — secrets + per-file complexity — then run in parallel
    coros = [
        _run_step(handle_detect_secrets, "detect_secrets", {"repo_path": repo_path}),
    ]
    for src_file in source_files[:3]:
        rel_path = str(src_file.relative_to(repo))
        coros.append(
            _run_step(
                handle_get_complexity_metrics,
                f"complexity:{rel_path}",
                {"repo_path": repo_path, "file_path": rel_path},
            )
        )

    results = await asyncio.gather(*coros)
    return list(results)


async def _run_full_analysis(repo_path: str) -> list[dict[str, Any]]:
    """Run the full analysis workflow.

    All four steps are independent, so they run in parallel.
    """
    from local_deepwiki.handlers.analysis_metadata import handle_get_wiki_stats
    from local_deepwiki.handlers.generators import (
        handle_detect_secrets,
        handle_detect_stale_docs,
        handle_get_coverage,
    )

    steps = await asyncio.gather(
        _run_step(handle_get_wiki_stats, "get_wiki_stats", {"repo_path": repo_path}),
        _run_step(handle_get_coverage, "get_coverage", {"repo_path": repo_path}),
        _run_step(
            handle_detect_stale_docs, "detect_stale_docs", {"repo_path": repo_path}
        ),
        _run_step(handle_detect_secrets, "detect_secrets", {"repo_path": repo_path}),
    )
    return list(steps)


async def _run_quick_refresh(repo_path: str) -> list[dict[str, Any]]:
    """Run the quick refresh workflow.

    Both steps are independent, so they run in parallel.
    """
    from local_deepwiki.handlers.generators import (
        handle_detect_stale_docs,
        handle_get_changelog,
    )

    steps = await asyncio.gather(
        _run_step(
            handle_detect_stale_docs, "detect_stale_docs", {"repo_path": repo_path}
        ),
        _run_step(handle_get_changelog, "get_changelog", {"repo_path": repo_path}),
    )
    return list(steps)


@handle_tool_errors
async def handle_run_workflow(args: dict[str, Any]) -> list[TextContent]:
    """Run a pre-built multi-step workflow by calling existing handlers.

    Each step has independent error handling — failures produce an error
    entry but the workflow continues.
    """
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    try:
        validated = RunWorkflowArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    workflow = validated.workflow

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    runner_name = _WORKFLOW_RUNNER_NAMES.get(workflow)
    if runner_name is None:
        from local_deepwiki.errors import ValidationError

        raise ValidationError(
            message=f"Unknown workflow: {workflow}",
            hint=f"Available workflows: {', '.join(sorted(WORKFLOW_PRESETS))}",
            field="workflow",
            value=workflow,
        )

    import local_deepwiki.handlers.agentic_workflows as _self_module

    runner = getattr(_self_module, runner_name)
    logger.info("Running workflow '%s' for %s", workflow, repo_path)
    steps = await runner(str(repo_path))

    data = {
        "workflow": workflow,
        "repo_path": str(repo_path),
        "steps": steps,
        "completed": sum(1 for s in steps if s.get("status") == "success"),
        "failed": sum(1 for s in steps if s.get("status") == "error"),
    }

    return [TextContent(type="text", text=wrap_tool_response("run_workflow", data))]
