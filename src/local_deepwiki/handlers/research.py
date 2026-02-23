"""Research tool handlers: deep research, checkpoints, cancellation, progress."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.models.foundation import CancellationChecker, ProgressReporter

from mcp.server import Server
from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

if TYPE_CHECKING:
    from local_deepwiki.core.deep_research import DeepResearchPipeline
    from local_deepwiki.models import ResearchProgress

from local_deepwiki.config import get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import not_indexed_error, path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._index_helpers import _format_research_results
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    CancelResearchArgs,
    DeepResearchArgs,
    ListResearchCheckpointsArgs,
    ResumeResearchArgs,
)
from local_deepwiki.progress import GetOperationProgressArgs, get_progress_registry
from local_deepwiki.providers.embeddings import get_embedding_provider
from local_deepwiki.security import Permission, get_access_controller
from local_deepwiki.validation import validate_deep_research_parameters

logger = get_logger(__name__)


class _DeepResearchContext:
    """Context object holding state for deep research execution."""

    def __init__(
        self,
        repo_path: Path,
        question: str,
        max_chunks: int,
        preset: str | None,
        server: Server | None,
        resume_research_id: str | None = None,
    ):
        self.repo_path = repo_path
        self.question = question
        self.max_chunks = max_chunks
        self.preset = preset
        self.server = server
        self.resume_research_id = resume_research_id
        self.config = get_config()
        self.progress_token: str | int | None = None
        self.cancellation_event = asyncio.Event()


def _setup_deep_research_config(
    args: dict[str, Any],
    server: Server | None = None,
) -> _DeepResearchContext:
    """Handle config setup and input validation for deep research.

    Args:
        args: Tool arguments containing repo_path, question, max_chunks, preset.
        server: Optional MCP server instance for progress notifications.

    Returns:
        DeepResearchContext with validated inputs and config.

    Raises:
        ValueError: If inputs are invalid or repository not indexed.
    """
    # Validate with Pydantic
    try:
        validated = DeepResearchArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    question = validated.question
    max_chunks = validated.max_chunks
    preset = validated.preset
    resume_research_id = validated.resume_research_id

    # Validate input size limits (CWE-400 prevention)
    validate_deep_research_parameters(question, preset, max_chunks)

    logger.info("Deep research on %s: %s...", repo_path, question[:100])
    logger.debug(
        "Max chunks: %d, preset: %s, resume: %s",
        max_chunks,
        preset or "default",
        resume_research_id or "new",
    )

    # Create context
    ctx = _DeepResearchContext(
        repo_path=repo_path,
        question=question,
        max_chunks=max_chunks,
        preset=preset,
        server=server,
        resume_research_id=resume_research_id,
    )

    # Validate repository is indexed
    vector_db_path = ctx.config.get_vector_db_path(repo_path)
    if not vector_db_path.exists():
        raise not_indexed_error(str(repo_path))

    # Extract progress token from MCP request context
    if server is not None:
        try:
            request_ctx = server.request_context
            if request_ctx.meta and request_ctx.meta.progressToken:
                ctx.progress_token = request_ctx.meta.progressToken
        except LookupError:
            # Not in a request context (e.g., testing or direct API calls)
            logger.debug(
                "No MCP request context available for deep research progress token"
            )

    return ctx


def _create_research_pipeline(
    ctx: _DeepResearchContext,
    args: dict[str, Any],
) -> tuple["DeepResearchPipeline", "VectorStore", Any]:
    """Create the DeepResearchPipeline instance with providers.

    Args:
        ctx: Deep research context with config and settings.
        args: Original tool arguments for max_chunks override check.

    Returns:
        Tuple of (pipeline, vector_store, llm_provider).
    """
    from local_deepwiki.core.deep_research import DeepResearchPipeline
    from local_deepwiki.providers.llm import get_cached_llm_provider

    # Create vector store and LLM provider
    embedding_provider = get_embedding_provider(ctx.config.embedding)
    vector_db_path = ctx.config.get_vector_db_path(ctx.repo_path)
    vector_store = VectorStore(vector_db_path, embedding_provider)

    cache_path = ctx.config.get_wiki_path(ctx.repo_path) / "llm_cache.lance"
    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=embedding_provider,
        cache_config=ctx.config.llm_cache,
        llm_config=ctx.config.llm,
    )

    # Apply preset if specified (overrides config file values)
    dr_config = ctx.config.deep_research.with_preset(ctx.preset)

    # Use max_chunks from args if provided, otherwise use preset/config value
    effective_max_chunks = (
        ctx.max_chunks
        if args.get("max_chunks") is not None
        else dr_config.max_total_chunks
    )

    # Get provider-specific prompts
    prompts = ctx.config.get_prompts()

    pipeline = DeepResearchPipeline(
        vector_store=vector_store,
        llm_provider=llm,
        max_sub_questions=dr_config.max_sub_questions,
        chunks_per_subquestion=dr_config.chunks_per_subquestion,
        max_total_chunks=effective_max_chunks,
        max_follow_up_queries=dr_config.max_follow_up_queries,
        synthesis_temperature=dr_config.synthesis_temperature,
        synthesis_max_tokens=dr_config.synthesis_max_tokens,
        decomposition_prompt=prompts.research_decomposition,
        gap_analysis_prompt=prompts.research_gap_analysis,
        synthesis_prompt=prompts.research_synthesis,
        repo_path=ctx.repo_path,  # Enable checkpointing
    )

    return pipeline, vector_store, llm


def _create_progress_callbacks(
    ctx: _DeepResearchContext,
) -> tuple[
    CancellationChecker,
    ProgressReporter,
    Callable[[str], Awaitable[None]],
]:
    """Create cancellation checker and progress callback functions.

    Args:
        ctx: Deep research context with server and progress token.

    Returns:
        Tuple of (is_cancelled, progress_callback, send_cancellation_notification).
    """
    from local_deepwiki.models import ResearchProgress, ResearchProgressType

    def is_cancelled() -> bool:
        """Check if the research should be cancelled."""
        # Check both our event and the current task's cancellation state
        if ctx.cancellation_event.is_set():
            return True
        # Check if current asyncio task is being cancelled
        try:
            task = asyncio.current_task()
            if task and task.cancelled():
                return True
        except RuntimeError:
            logger.debug(
                "Failed to check asyncio task cancellation state", exc_info=True
            )
        return False

    async def progress_callback(progress: ResearchProgress) -> None:
        """Send MCP progress notifications."""
        if ctx.progress_token is None or ctx.server is None:
            return
        try:
            request_ctx = ctx.server.request_context
            await request_ctx.session.send_progress_notification(
                progress_token=ctx.progress_token,
                progress=float(progress.step),
                total=float(progress.total_steps),
                message=progress.model_dump_json(),
            )
        except (RuntimeError, OSError, AttributeError) as e:
            # RuntimeError: Session or context issues
            # OSError: Network communication failures
            # AttributeError: Missing session/context attributes
            logger.warning("Failed to send progress notification: %s", e)

    async def send_cancellation_notification(step: str) -> None:
        """Send a cancellation progress notification."""
        if ctx.progress_token is None or ctx.server is None:
            return
        try:
            request_ctx = ctx.server.request_context
            progress = ResearchProgress(
                step=0,
                step_type=ResearchProgressType.CANCELLED,
                message=f"Research cancelled during {step}",
            )
            await request_ctx.session.send_progress_notification(
                progress_token=ctx.progress_token,
                progress=0.0,
                total=5.0,
                message=progress.model_dump_json(),
            )
        except (RuntimeError, OSError, AttributeError) as e:
            # RuntimeError: Session or context issues
            # OSError: Network communication failures
            # AttributeError: Missing session/context attributes
            logger.warning("Failed to send cancellation notification: %s", e)

    return is_cancelled, progress_callback, send_cancellation_notification


async def _execute_research_phases(
    ctx: _DeepResearchContext,
    pipeline: "DeepResearchPipeline",
    is_cancelled: CancellationChecker,
    progress_callback: ProgressReporter,
    send_cancellation_notification: Callable[[str], Awaitable[None]],
) -> list[TextContent]:
    """Execute the research phases with progress tracking.

    Args:
        ctx: Deep research context.
        pipeline: The configured DeepResearchPipeline.
        is_cancelled: Function to check if research is cancelled.
        progress_callback: Function to send progress updates.
        send_cancellation_notification: Function to send cancellation notifications.

    Returns:
        List of TextContent with research results.

    Raises:
        asyncio.CancelledError: If the task is cancelled.
    """
    from local_deepwiki.core.deep_research import ResearchCancelledError

    try:
        result = await pipeline.research(
            ctx.question,
            progress_callback=progress_callback,
            cancellation_check=is_cancelled,
            resume_id=ctx.resume_research_id,
            cancellation_event=ctx.cancellation_event,
        )

        response = _format_research_results(result)

        logger.info(
            "Deep research complete: %d chunks, %d LLM calls",
            result.total_chunks_analyzed,
            result.total_llm_calls,
        )
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    except ResearchCancelledError as e:
        logger.info("Deep research cancelled: %s", e)
        await send_cancellation_notification(e.step)
        response = {
            "status": "cancelled",
            "message": f"Research cancelled during {e.step}",
        }
        if e.checkpoint_id:
            response["checkpoint_id"] = e.checkpoint_id
            response["hint"] = (
                "Use resume_research_id to continue from where you left off"
            )
        return [TextContent(type="text", text=json.dumps(response))]

    except asyncio.CancelledError:
        logger.info("Deep research task cancelled")
        await send_cancellation_notification("task_cancellation")
        raise  # Re-raise to properly propagate cancellation


async def _handle_deep_research_impl(
    args: dict[str, Any],
    server: Server | None = None,
) -> list[TextContent]:
    """Internal implementation of deep_research handler.

    Coordinates the deep research process by delegating to focused helper functions:
    1. Setup and validation via _setup_deep_research_config()
    2. Pipeline creation via _create_research_pipeline()
    3. Progress callbacks via _create_progress_callbacks()
    4. Execution via _execute_research_phases()

    Args:
        args: Tool arguments.
        server: Optional MCP server instance for progress notifications.

    Returns:
        List of TextContent with research results.
    """
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_DEEP_RESEARCH)

    # Step 1: Setup config and validate inputs
    ctx = _setup_deep_research_config(args, server)

    # Step 2: Create the research pipeline with providers
    pipeline, *_ = _create_research_pipeline(ctx, args)

    # Step 3: Create progress and cancellation callbacks
    is_cancelled, progress_callback, send_cancellation_notification = (
        _create_progress_callbacks(ctx)
    )

    # Step 4: Execute research phases with progress tracking
    return await _execute_research_phases(
        ctx,
        pipeline,
        is_cancelled,
        progress_callback,
        send_cancellation_notification,
    )


@handle_tool_errors
async def handle_deep_research(
    args: dict[str, Any],
    server: Server | None = None,
) -> list[TextContent]:
    """Handle deep_research tool call for multi-step reasoning.

    Args:
        args: Tool arguments.
        server: Optional MCP server instance for progress notifications.

    Returns:
        List of TextContent with research results.
    """
    return await _handle_deep_research_impl(args, server)


@handle_tool_errors
async def handle_list_research_checkpoints(args: dict[str, Any]) -> list[TextContent]:
    """Handle list_research_checkpoints tool call.

    Lists all research checkpoints for a repository, including incomplete
    and cancelled research sessions that can be resumed.
    """
    from local_deepwiki.core.deep_research import list_research_checkpoints

    # Validate with Pydantic
    try:
        validated = ListResearchCheckpointsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    checkpoints = list_research_checkpoints(repo_path)

    if not checkpoints:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "No research checkpoints found",
                        "checkpoints": [],
                    },
                    indent=2,
                ),
            )
        ]

    # Format checkpoints for output
    checkpoint_list = []
    for cp in checkpoints:
        checkpoint_list.append(
            {
                "research_id": cp.research_id,
                "question": cp.question[:100] + "..."
                if len(cp.question) > 100
                else cp.question,
                "current_step": cp.current_step.value,
                "completed_steps": cp.completed_steps,
                "started_at": cp.started_at,
                "updated_at": cp.updated_at,
                "can_resume": cp.current_step.value not in ("complete", "error"),
                "error": cp.error,
            }
        )

    response = {
        "status": "success",
        "checkpoint_count": len(checkpoints),
        "checkpoints": checkpoint_list,
    }

    logger.info("Listed %s research checkpoints for %s", len(checkpoints), repo_path)
    return [TextContent(type="text", text=json.dumps(response, indent=2))]


@handle_tool_errors
async def handle_cancel_research(args: dict[str, Any]) -> list[TextContent]:
    """Handle cancel_research tool call.

    Cancels an active research session and saves its checkpoint for
    potential resumption later.
    """
    from local_deepwiki.core.deep_research import cancel_research

    # Validate with Pydantic
    try:
        validated = CancelResearchArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    research_id = validated.research_id

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    checkpoint = cancel_research(repo_path, research_id)

    if not checkpoint:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": f"Research checkpoint {research_id} not found",
                    },
                    indent=2,
                ),
            )
        ]

    response = {
        "status": "success",
        "message": f"Research {research_id} cancelled and checkpointed",
        "research_id": checkpoint.research_id,
        "question": checkpoint.question,
        "completed_steps": checkpoint.completed_steps,
        "hint": "Use deep_research with resume_research_id to continue later",
    }

    logger.info("Cancelled research %s", research_id)
    return [TextContent(type="text", text=json.dumps(response, indent=2))]


@handle_tool_errors
async def handle_resume_research(
    args: dict[str, Any],
    server: Server | None = None,
) -> list[TextContent]:
    """Handle resume_research tool call.

    Resumes a previously interrupted research session from its checkpoint.
    This is a convenience wrapper around deep_research with resume_research_id.
    """
    from local_deepwiki.core.deep_research import get_research_checkpoint

    # Validate with Pydantic
    try:
        validated = ResumeResearchArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    research_id = validated.research_id

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    # Load the checkpoint to get the original question
    checkpoint = get_research_checkpoint(repo_path, research_id)

    if not checkpoint:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": f"Research checkpoint {research_id} not found",
                    },
                    indent=2,
                ),
            )
        ]

    if checkpoint.current_step.value == "complete":
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": f"Research {research_id} is already complete",
                    },
                    indent=2,
                ),
            )
        ]

    # Delegate to deep_research handler with resume_research_id
    deep_research_args = {
        "repo_path": str(repo_path),
        "question": checkpoint.question,
        "resume_research_id": research_id,
    }

    return await handle_deep_research(deep_research_args, server)


@handle_tool_errors
async def handle_get_operation_progress(args: dict[str, Any]) -> list[TextContent]:
    """Handle get_operation_progress tool call.

    Returns current progress for active operations, supporting the
    pull-based progress model for clients that cannot receive push notifications.
    """
    # Validate with Pydantic
    try:
        validated = GetOperationProgressArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    registry = get_progress_registry()
    operation_id = validated.operation_id

    if operation_id:
        # Get progress for specific operation
        progress = registry.get_operation_progress(operation_id)
        if not progress:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "not_found",
                            "message": f"Operation {operation_id} not found or already completed",
                        },
                        indent=2,
                    ),
                )
            ]
        return [TextContent(type="text", text=json.dumps(progress, indent=2))]
    else:
        # List all active operations
        operations = registry.list_operations()
        response = {
            "status": "success",
            "active_operations": len(operations),
            "operations": operations,
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]
