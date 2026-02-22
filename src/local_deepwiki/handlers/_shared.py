"""Shared helpers, constants, and common imports for handler modules."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from local_deepwiki.core.deep_research import DeepResearchPipeline
    from local_deepwiki.models import (
        DeepResearchResult,
        IndexingProgress,
        ResearchProgress,
    )

from mcp.server import Server
from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.config import get_config
from local_deepwiki.core.audit import get_audit_logger
from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.core.rate_limiter import RateLimitExceeded, get_rate_limiter
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.errors import (
    DeepWikiError,
    ExportError,
    IndexingError,
    ResearchError,
    ValidationError,
    format_error_response,
    indexing_error,
    map_exception_to_deepwiki_error,
    not_indexed_error,
    path_not_found_error,
    provider_error,
    sanitize_error_message,
)
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.handlers.types import ResearchResult
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    AnalyzeDiffArgs,
    AskAboutDiffArgs,
    AskQuestionArgs,
    BatchExplainEntitiesArgs,
    CancelResearchArgs,
    DeepResearchArgs,
    DetectSecretsArgs,
    DetectStaleDocsArgs,
    ExplainEntityArgs,
    ExportWikiHtmlArgs,
    ExportWikiPdfArgs,
    FuzzySearchArgs,
    GenerateCodemapArgs,
    GetApiDocsArgs,
    GetCallGraphArgs,
    GetChangelogArgs,
    GetComplexityMetricsArgs,
    GetCoverageArgs,
    GetDiagramsArgs,
    GetFileContextArgs,
    GetGlossaryArgs,
    GetIndexStatusArgs,
    GetInheritanceArgs,
    GetProjectManifestArgs,
    GetTestExamplesArgs,
    GetWikiStatsArgs,
    ImpactAnalysisArgs,
    IndexingProgress,
    IndexingProgressType,
    IndexRepositoryArgs,
    ListIndexedReposArgs,
    ListResearchCheckpointsArgs,
    QueryCodebaseArgs,
    ReadWikiPageArgs,
    ReadWikiStructureArgs,
    ResearchCheckpoint,
    ResumeResearchArgs,
    RunWorkflowArgs,
    SearchCodeArgs,
    SearchWikiArgs,
    ServeWikiArgs,
    StopWikiServerArgs,
    SuggestCodemapTopicsArgs,
    SuggestNextActionsArgs,
)
from local_deepwiki.progress import (
    GetOperationProgressArgs,
    OperationType,
    ProgressBuffer,
    ProgressManager,
    ProgressPhase,
    ProgressUpdate,
    get_progress_registry,
)
from local_deepwiki.providers.embeddings import get_embedding_provider
from local_deepwiki.security import (
    AccessDeniedException,
    AuthenticationException,
    Permission,
    get_access_controller,
    get_repository_access_controller,
)
from local_deepwiki.validation import (
    MAX_WIKI_PAGE_SIZE,
    validate_chunk_type,
    validate_deep_research_parameters,
    validate_index_parameters,
    validate_language,
    validate_languages_list,
    validate_path_pattern,
    validate_query_parameters,
)

logger = get_logger(__name__)

# Type alias for tool handler functions
ToolHandler: TypeAlias = Callable[..., Awaitable[list[TextContent]]]

# Forbidden directories for export operations (security: prevent writing to sensitive locations)
# Note: /var and /private/var are excluded because temp directories live there
FORBIDDEN_EXPORT_DIRS = frozenset(
    {
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/System",
        "/Library",
        "/private/etc",
        str(Path.home() / ".ssh"),
    }
)

# Additional forbidden prefixes under /var that should be blocked
# (but not /var/folders or /var/tmp which are user temp directories)
FORBIDDEN_VAR_SUBDIRS = frozenset(
    {
        "/var/log",
        "/var/db",
        "/var/root",
        "/var/run",
        "/private/var/log",
        "/private/var/db",
        "/private/var/root",
        "/private/var/run",
    }
)


def _is_test_file(file_path: str) -> bool:
    """Check if a file path looks like a test file.

    Delegates to :func:`local_deepwiki.core.path_utils.is_test_file`.
    """
    return is_test_file(file_path, check_filename=True)


def _check_forbidden_dirs(
    resolved_str: str,
    dirs: frozenset[str],
    output_path: Path,
    label: str = "system directory",
) -> None:
    """Raise ValidationError if resolved_str is inside any forbidden directory.

    Args:
        resolved_str: Resolved absolute path as string.
        dirs: Set of forbidden directory paths.
        output_path: Original output path (for error context).
        label: Label for error messages (e.g., "system directory").
    """
    for forbidden in dirs:
        if resolved_str == forbidden or resolved_str.startswith(forbidden + "/"):
            raise ValidationError(
                message=f"Cannot export to {label}: {forbidden}",
                hint="Choose an output path in your project or home directory.",
                field="output_path",
                value=str(output_path),
            )


def _validate_export_path(output_path: Path, wiki_path: Path) -> Path:
    """Validate that export output path is not in a sensitive system directory.

    Args:
        output_path: The requested output path (must be resolved to absolute).
        wiki_path: The source wiki path (for context in error messages).

    Returns:
        The validated output path.

    Raises:
        ValidationError: If the output path is in a forbidden directory.
    """
    resolved = output_path.resolve()
    resolved_str = str(resolved)

    _check_forbidden_dirs(resolved_str, FORBIDDEN_EXPORT_DIRS, output_path)
    _check_forbidden_dirs(
        resolved_str, FORBIDDEN_VAR_SUBDIRS, output_path, label="system directory"
    )

    # Check for ~/.config (allow only ~/.config/local-deepwiki)
    config_dir = Path.home() / ".config"
    local_deepwiki_config = config_dir / "local-deepwiki"
    if resolved_str.startswith(str(config_dir) + "/"):
        if (
            not resolved_str.startswith(str(local_deepwiki_config) + "/")
            and resolved != local_deepwiki_config
        ):
            raise ValidationError(
                message=f"Cannot export to config directory: {config_dir}",
                hint="Choose an output path in your project or home directory.",
                field="output_path",
                value=str(output_path),
            )

    # Ensure parent directory exists or can be created
    parent = resolved.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise ValidationError(
                message=f"Cannot create output directory: {parent}",
                hint="Ensure you have write permissions to the parent directory.",
                field="output_path",
                value=str(output_path),
            ) from e
        except OSError as e:
            raise ValidationError(
                message=f"Failed to create output directory: {e}",
                hint="Check that the path is valid and accessible.",
                field="output_path",
                value=str(output_path),
            ) from e

    return resolved


def handle_tool_errors(func: ToolHandler) -> ToolHandler:
    """Decorator for consistent error handling in tool handlers.

    Catches exceptions and returns properly formatted error responses with
    actionable hints when available:

    - DeepWikiError subclasses: Format with message and hint
    - ValueError: Input validation errors (logged at ERROR level)
    - Common exceptions: Map to DeepWikiError with appropriate hints
    - Other exceptions: Log with traceback and return generic error

    Args:
        func: The async tool handler function to wrap.

    Returns:
        Wrapped function with consistent error handling.
    """

    @wraps(func)
    async def wrapper(
        args: dict[str, Any], **kwargs: dict[str, Any]
    ) -> list[TextContent]:
        try:
            return await func(args, **kwargs)
        except AccessDeniedException as e:
            # RBAC: User lacks required permission
            logger.warning("Access denied in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=f"Access denied: {e}",
                hint="You don't have permission for this operation. Contact an administrator to request access.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except AuthenticationException as e:
            # RBAC: No authenticated subject
            logger.warning("Authentication required in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=f"Authentication required: {e}",
                hint="Please authenticate before performing this operation.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except DeepWikiError as e:
            # Our custom errors already have good messages and hints
            logger.error("DeepWiki error in %s: %s", func.__name__, e.message)
            if e.context:
                logger.debug("Error context: %s", e.context)
            return [TextContent(type="text", text=format_error_response(e))]
        except ValueError as e:
            # Wrap ValueError in ValidationError for better hints
            error = ValidationError(
                message=str(e),
                hint="Check that all input parameters are valid.",
            )
            logger.error("Validation error in %s: %s", func.__name__, e)
            return [TextContent(type="text", text=format_error_response(error))]
        except (FileNotFoundError, PermissionError) as e:
            # Map common file system errors
            error = map_exception_to_deepwiki_error(e)
            logger.error("File system error in %s: %s", func.__name__, e)
            return [TextContent(type="text", text=format_error_response(error))]
        except (ConnectionError, TimeoutError) as e:
            # Map common network errors — retryable
            error = map_exception_to_deepwiki_error(e)
            error.retryable = True
            error.retry_after_seconds = 5
            logger.error("Network error in %s: %s", func.__name__, e)
            return [TextContent(type="text", text=format_error_response(error))]
        except RateLimitExceeded as e:
            # Rate limit exceeded — retryable after cooldown
            logger.warning("Rate limit exceeded in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=str(e),
                hint="Wait for the rate limit to reset, or reduce the frequency of requests.",
                retryable=True,
                retry_after_seconds=60,
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except asyncio.CancelledError:
            # Re-raise cancellation to propagate properly
            raise
        except Exception as e:  # noqa: BLE001
            # Broad catch is intentional: top-level error handler for MCP tools
            # that converts any unhandled exception to a user-friendly error message
            logger.exception("Unexpected error in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=f"An unexpected error occurred: {e}",
                hint="Check the logs for more details. If this persists, please report the issue.",
            )
            return [TextContent(type="text", text=format_error_response(error))]

    return wrapper


async def _load_index_status(repo_path: Path) -> tuple[Any, Path, Any]:
    """Load index status for a repository, raising if not indexed.

    Args:
        repo_path: Resolved path to the repository.

    Returns:
        Tuple of (IndexStatus, wiki_path, config).

    Raises:
        ValidationError: If repository is not indexed.
    """
    from local_deepwiki.core.index_manager import IndexStatusManager

    config = get_config()
    wiki_path = config.get_wiki_path(repo_path)
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        raise not_indexed_error(str(repo_path))

    manager = IndexStatusManager()
    index_status = await asyncio.to_thread(manager.load, wiki_path)
    if index_status is None:
        raise not_indexed_error(str(repo_path))

    return index_status, wiki_path, config


def _create_vector_store(repo_path: Path, config: Any) -> VectorStore:
    """Create a VectorStore with the configured embedding provider.

    Args:
        repo_path: Resolved path to the repository.
        config: Application configuration object.

    Returns:
        Initialized VectorStore instance.
    """
    embedding_provider = get_embedding_provider(config.embedding)
    return VectorStore(config.get_vector_db_path(repo_path), embedding_provider)


def _format_research_results(result: "DeepResearchResult") -> ResearchResult:
    """Format the research results for return.

    Args:
        result: The ResearchResult from the pipeline.

    Returns:
        Formatted dictionary ready for JSON serialization.
    """
    return {
        "question": result.question,
        "answer": result.answer,
        "sub_questions": [
            {"question": sq.question, "category": sq.category}
            for sq in result.sub_questions
        ],
        "sources": [
            {
                "file": src.file_path,
                "lines": f"{src.start_line}-{src.end_line}",
                "type": src.chunk_type,
                "name": src.name,
                "relevance": round(src.relevance_score, 3),
            }
            for src in result.sources
        ],
        "research_trace": [
            {
                "step": step.step_type.value,
                "description": step.description,
                "duration_ms": step.duration_ms,
            }
            for step in result.reasoning_trace
        ],
        "stats": {
            "chunks_analyzed": result.total_chunks_analyzed,
            "llm_calls": result.total_llm_calls,
        },
    }


class ProgressNotifier:
    """Helper class for sending buffered MCP progress notifications.

    Integrates ProgressManager with MCP server notifications,
    handling buffering and async notification delivery.
    """

    def __init__(
        self,
        progress_manager: ProgressManager,
        server: Server | None,
        progress_token: str | int | None,
        buffer_interval: float = 0.5,
    ):
        """Initialize the notifier.

        Args:
            progress_manager: The ProgressManager to use for tracking.
            server: MCP server instance.
            progress_token: Progress token from MCP request.
            buffer_interval: Minimum seconds between notifications.
        """
        self.progress_manager = progress_manager
        self.server = server
        self.progress_token = progress_token
        self.buffer = ProgressBuffer(flush_interval=buffer_interval)
        self._messages: list[str] = []

    async def update(
        self,
        current: int | None = None,
        total: int | None = None,
        message: str = "",
        phase: ProgressPhase | None = None,
        step_type: IndexingProgressType | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update progress and send buffered notification.

        Args:
            current: Current progress value.
            total: Total items.
            message: Status message.
            phase: Current phase.
            step_type: IndexingProgressType for backward compatibility.
            metadata: Additional metadata.
        """
        # Track message history
        if message:
            self._messages.append(message)

        # Update progress manager
        update = self.progress_manager.update(
            current=current,
            total=total,
            message=message,
            phase=phase,
            metadata=metadata,
        )

        # Add to buffer
        updates_to_send = self.buffer.add(update)

        # Send notifications if buffer flushed
        if updates_to_send:
            await self._send_notifications(updates_to_send)

    async def flush(self) -> None:
        """Flush any pending notifications."""
        updates = self.buffer.flush()
        if updates:
            await self._send_notifications(updates)

    async def _send_notifications(self, updates: list[ProgressUpdate]) -> None:
        """Send MCP progress notifications.

        Args:
            updates: List of progress updates to send.
        """
        if not self.progress_token or not self.server:
            return

        # Send the most recent update (MCP expects single progress per notification)
        latest = updates[-1]

        try:
            request_ctx = self.server.request_context

            # Build backward-compatible progress message
            progress_data = {
                "step": latest.current,
                "total_steps": latest.total or 0,
                "step_type": latest.phase.value,
                "message": latest.message,
                "eta_seconds": latest.eta_seconds,
                **latest.metadata,
            }

            await request_ctx.session.send_progress_notification(
                progress_token=self.progress_token,
                progress=float(latest.current),
                total=float(latest.total) if latest.total else None,
                message=json.dumps(progress_data),
            )
        except (RuntimeError, OSError, AttributeError, LookupError) as e:
            logger.warning("Failed to send progress notification: %s", e)

    @property
    def messages(self) -> list[str]:
        """Get accumulated progress messages."""
        return self._messages


def wrap_tool_response(
    tool_name: str,
    data: dict[str, Any],
    *,
    hints: dict[str, Any] | None = None,
) -> str:
    """Wrap tool output in a structured JSON envelope.

    Merges ``tool`` (and optionally ``hints``) into the data dict so that
    existing fields like ``status``, ``message``, etc. remain at the top
    level for backward-compatible parsing.

    Args:
        tool_name: Name of the tool that produced this response.
        data: The tool's result payload.
        hints: Optional follow-up suggestions for agents.

    Returns:
        JSON string with standard envelope.
    """
    envelope: dict[str, Any] = {**data, "tool": tool_name}
    if "status" not in envelope:
        envelope["status"] = "success"
    if hints is not None:
        envelope["hints"] = hints
    return json.dumps(envelope, indent=2)


def make_tool_text_content(
    tool_name: str,
    data: dict[str, Any],
    *,
    hints: dict[str, Any] | None = None,
) -> list[TextContent]:
    """Produce a list[TextContent] wrapped in a standard JSON envelope.

    Convenience wrapper combining ``wrap_tool_response`` with the
    ``TextContent`` construction that every handler needs.

    Args:
        tool_name: Name of the tool that produced this response.
        data: The tool's result payload.
        hints: Optional follow-up suggestions for agents.

    Returns:
        Single-element list of TextContent with the JSON envelope.
    """
    return [
        TextContent(type="text", text=wrap_tool_response(tool_name, data, hints=hints))
    ]


def build_wiki_resource_uri(wiki_path: Path, page_relative: str) -> str:
    """Build a deepwiki:// resource URI for a wiki page.

    Args:
        wiki_path: Absolute path to the wiki directory.
        page_relative: Page path relative to wiki root.

    Returns:
        URI string like 'deepwiki:///path/to/.deepwiki/index.md'.
    """
    return f"deepwiki://{wiki_path}/{page_relative}"


def create_progress_notifier(
    operation_type: OperationType,
    server: Server | None,
    total: int | None = None,
) -> tuple[ProgressNotifier | None, str]:
    """Create a ProgressNotifier for an MCP operation.

    Args:
        operation_type: Type of operation.
        server: MCP server instance.
        total: Total items to process.

    Returns:
        Tuple of (ProgressNotifier or None, operation_id).
    """
    operation_id = str(uuid.uuid4())
    registry = get_progress_registry()

    # Extract progress token from MCP request context
    progress_token: str | int | None = None
    if server is not None:
        try:
            request_ctx = server.request_context
            if request_ctx.meta and request_ctx.meta.progressToken:
                progress_token = request_ctx.meta.progressToken
        except LookupError:
            logger.debug(
                "No MCP request context available for progress token extraction"
            )

    # Create progress manager
    progress_manager = registry.start_operation(
        operation_id=operation_id,
        operation_type=operation_type,
        total=total,
    )

    # Create notifier
    notifier = ProgressNotifier(
        progress_manager=progress_manager,
        server=server,
        progress_token=progress_token,
    )

    return notifier, operation_id
