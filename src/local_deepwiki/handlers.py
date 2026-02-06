"""Tool handlers for the MCP server."""

import asyncio
import json
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from local_deepwiki.core.deep_research import DeepResearchPipeline
    from local_deepwiki.models import IndexingProgress, ResearchProgress

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.errors import (
    DeepWikiError,
    ExportError,
    IndexingError,
    ProviderError,
    ResearchError,
    ValidationError,
    format_error_response,
    indexing_error,
    map_exception_to_deepwiki_error,
    not_indexed_error,
    path_not_found_error,
    provider_error,
)

from local_deepwiki.models import (
    AskQuestionArgs,
    CancelResearchArgs,
    DeepResearchArgs,
    DetectSecretsArgs,
    DetectStaleDocsArgs,
    ExportWikiHtmlArgs,
    ExportWikiPdfArgs,
    GetApiDocsArgs,
    GetCallGraphArgs,
    GetChangelogArgs,
    GetCoverageArgs,
    GetDiagramsArgs,
    GetGlossaryArgs,
    GetIndexStatusArgs,
    GetInheritanceArgs,
    GetTestExamplesArgs,
    IndexingProgress,
    IndexingProgressType,
    IndexRepositoryArgs,
    ListIndexedReposArgs,
    ListResearchCheckpointsArgs,
    ReadWikiPageArgs,
    ReadWikiStructureArgs,
    ResearchCheckpoint,
    ResumeResearchArgs,
    SearchCodeArgs,
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

from local_deepwiki.config import get_config
from local_deepwiki.core.audit import get_audit_logger
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.core.rate_limiter import RateLimitExceeded, get_rate_limiter
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.logging import get_logger
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
ToolHandler = Callable[[dict[str, Any]], Awaitable[list[TextContent]]]

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

    # Check against forbidden directories
    for forbidden in FORBIDDEN_EXPORT_DIRS:
        if resolved_str == forbidden or resolved_str.startswith(forbidden + "/"):
            raise ValidationError(
                message=f"Cannot export to system directory: {forbidden}",
                hint="Choose an output path in your project or home directory.",
                field="output_path",
                value=str(output_path),
            )

    # Check against forbidden /var subdirectories (but allow /var/folders, /var/tmp for temp files)
    for forbidden in FORBIDDEN_VAR_SUBDIRS:
        if resolved_str == forbidden or resolved_str.startswith(forbidden + "/"):
            raise ValidationError(
                message=f"Cannot export to system directory: {forbidden}",
                hint="Choose an output path in your project or home directory.",
                field="output_path",
                value=str(output_path),
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
    async def wrapper(args: dict[str, Any], **kwargs: Any) -> list[TextContent]:
        try:
            return await func(args, **kwargs)
        except AccessDeniedException as e:
            # RBAC: User lacks required permission
            logger.warning(f"Access denied in {func.__name__}: {e}")
            error = DeepWikiError(
                message=f"Access denied: {e}",
                hint="You don't have permission for this operation. Contact an administrator to request access.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except AuthenticationException as e:
            # RBAC: No authenticated subject
            logger.warning(f"Authentication required in {func.__name__}: {e}")
            error = DeepWikiError(
                message=f"Authentication required: {e}",
                hint="Please authenticate before performing this operation.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except DeepWikiError as e:
            # Our custom errors already have good messages and hints
            logger.error(f"DeepWiki error in {func.__name__}: {e.message}")
            if e.context:
                logger.debug(f"Error context: {e.context}")
            return [TextContent(type="text", text=format_error_response(e))]
        except ValueError as e:
            # Wrap ValueError in ValidationError for better hints
            error = ValidationError(
                message=str(e),
                hint="Check that all input parameters are valid.",
            )
            logger.error(f"Validation error in {func.__name__}: {e}")
            return [TextContent(type="text", text=format_error_response(error))]
        except (FileNotFoundError, PermissionError) as e:
            # Map common file system errors
            error = map_exception_to_deepwiki_error(e)
            logger.error(f"File system error in {func.__name__}: {e}")
            return [TextContent(type="text", text=format_error_response(error))]
        except (ConnectionError, TimeoutError) as e:
            # Map common network errors
            error = map_exception_to_deepwiki_error(e)
            logger.error(f"Network error in {func.__name__}: {e}")
            return [TextContent(type="text", text=format_error_response(error))]
        except RateLimitExceeded as e:
            # Rate limit exceeded - provide helpful message
            logger.warning(f"Rate limit exceeded in {func.__name__}: {e}")
            error = DeepWikiError(
                message=str(e),
                hint="Wait for the rate limit to reset, or reduce the frequency of requests.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except asyncio.CancelledError:
            # Re-raise cancellation to propagate properly
            raise
        except Exception as e:  # noqa: BLE001
            # Broad catch is intentional: top-level error handler for MCP tools
            # that converts any unhandled exception to a user-friendly error message
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            error = DeepWikiError(
                message=f"An unexpected error occurred: {e}",
                hint="Check the logs for more details. If this persists, please report the issue.",
            )
            return [TextContent(type="text", text=format_error_response(error))]

    return wrapper


@handle_tool_errors
async def handle_index_repository(
    args: dict[str, Any],
    server: Any = None,
) -> list[TextContent]:
    """Handle index_repository tool call with streaming progress.

    Args:
        args: Tool arguments.
        server: Optional MCP server instance for progress notifications.

    Returns:
        List of TextContent with indexing results.
    """
    return await _handle_index_repository_impl(args, server)


async def _handle_index_repository_impl(
    args: dict[str, Any],
    server: Any = None,
) -> list[TextContent]:
    """Internal implementation of index_repository with progress streaming and ETA."""
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_WRITE)

    # Validate with Pydantic
    try:
        validated = IndexRepositoryArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()

    # Check repository access (allowlist/denylist)
    repo_access = get_repository_access_controller()
    repo_access.require_access(repo_path)

    # Validate input size limits (CWE-400 prevention)
    total_size, file_count = validate_index_parameters(str(repo_path))
    logger.info(
        f"Indexing repository: {repo_path} ({total_size:,} bytes, {file_count:,} files)"
    )

    # Get subject ID for audit logging
    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"

    # Audit: Log index operation started
    audit_logger = get_audit_logger()
    start_time = time.time()
    audit_logger.log_index_operation(
        subject_id=subject_id,
        repo_path=str(repo_path),
        operation="started",
        success=True,
    )

    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    if not repo_path.is_dir():
        raise ValidationError(
            message=f"Path is not a directory: {repo_path}",
            hint="Provide a path to a directory, not a file.",
            field="repo_path",
            value=str(repo_path),
        )

    # Use validated values
    languages = validate_languages_list(validated.languages)
    llm_provider = validated.llm_provider.value if validated.llm_provider else None
    embedding_provider = (
        validated.embedding_provider.value if validated.embedding_provider else None
    )

    # Get config (immutable, create copy with any overrides)
    base_config = get_config()
    config_updates: dict = {}

    # Override languages if specified
    if languages:
        new_parsing = base_config.parsing.model_copy(update={"languages": languages})
        config_updates["parsing"] = new_parsing

    # Override use_cloud_for_github if specified
    use_cloud_for_github = validated.use_cloud_for_github
    if use_cloud_for_github is not None:
        new_wiki = base_config.wiki.model_copy(
            update={"use_cloud_for_github": use_cloud_for_github}
        )
        config_updates["wiki"] = new_wiki

    # Create modified config or use base if no overrides
    if config_updates:
        config = base_config.model_copy(update=config_updates)
    else:
        config = base_config

    # Initialize progress registry data path for persistence
    registry = get_progress_registry()
    wiki_path = config.get_wiki_path(repo_path)
    progress_data_path = wiki_path / "progress_history.json"
    registry.set_data_path(progress_data_path)

    # Create progress notifier with ETA support
    notifier, operation_id = create_progress_notifier(
        operation_type=OperationType.INDEX_REPOSITORY,
        server=server,
        total=6,  # Total steps: scan, parse, embed, store, generate wiki, complete
    )

    # Create indexer
    indexer = RepositoryIndexer(
        repo_path=repo_path,
        config=config,
        embedding_provider_name=embedding_provider,
    )

    # Index the repository
    full_rebuild = validated.full_rebuild

    # Track indexing state for backward compatibility
    indexing_state = {
        "files_processed": 0,
        "total_files": 0,
        "chunks_created": 0,
        "pages_generated": 0,
    }

    # Capture all progress messages for backward compatibility
    progress_messages: list[str] = []

    def sync_progress_callback(msg: str, current: int, total: int) -> None:
        """Sync callback for indexer - updates state for next async notification."""
        indexing_state["files_processed"] = current
        indexing_state["total_files"] = total
        progress_messages.append(f"[{current}/{total}] {msg}")

    try:
        # Step 1: Started
        if notifier:
            await notifier.update(
                current=1,
                phase=ProgressPhase.SCANNING,
                message=f"Starting indexing of {repo_path.name}",
                metadata={
                    "files_processed": 0,
                    "total_files": 0,
                    "chunks_created": 0,
                    "pages_generated": 0,
                },
            )

        # Step 2-4: Index repository (parsing, embedding, storing)
        if notifier:
            await notifier.update(
                current=2,
                phase=ProgressPhase.PARSING,
                message="Parsing source files...",
            )

        status = await indexer.index(
            full_rebuild=full_rebuild,
            progress_callback=sync_progress_callback,
        )

        indexing_state["chunks_created"] = status.total_chunks

        if notifier:
            await notifier.update(
                current=4,
                phase=ProgressPhase.STORING,
                message=f"Indexed {status.total_files} files, {status.total_chunks} chunks",
                metadata={
                    "files_processed": status.total_files,
                    "total_files": status.total_files,
                    "chunks_created": status.total_chunks,
                },
            )

        # Step 5: Generate wiki documentation
        if notifier:
            await notifier.update(
                current=5,
                phase=ProgressPhase.WIKI_GENERATION,
                message="Generating wiki documentation...",
            )

        wiki_structure = await generate_wiki(
            repo_path=repo_path,
            wiki_path=indexer.wiki_path,
            vector_store=indexer.vector_store,
            index_status=status,
            config=config,
            llm_provider=llm_provider,
            progress_callback=sync_progress_callback,
            full_rebuild=full_rebuild,
        )

        indexing_state["pages_generated"] = len(wiki_structure.pages)

        # Step 6: Complete
        if notifier:
            await notifier.update(
                current=6,
                phase=ProgressPhase.COMPLETE,
                message=f"Complete: {status.total_files} files, {status.total_chunks} chunks, {len(wiki_structure.pages)} pages",
                metadata={
                    "files_processed": status.total_files,
                    "total_files": status.total_files,
                    "chunks_created": status.total_chunks,
                    "pages_generated": len(wiki_structure.pages),
                },
            )
            await notifier.flush()

        # Complete operation in registry (records timing for future ETA predictions)
        registry.complete_operation(operation_id, record_timing=True)

    except Exception as e:
        # Clean up operation on error
        registry.complete_operation(operation_id, record_timing=False)

        # Audit: Log index operation failed
        duration_ms = int((time.time() - start_time) * 1000)
        audit_logger.log_index_operation(
            subject_id=subject_id,
            repo_path=str(repo_path),
            operation="failed",
            success=False,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        raise

    # Audit: Log index operation completed
    duration_ms = int((time.time() - start_time) * 1000)
    audit_logger.log_index_operation(
        subject_id=subject_id,
        repo_path=str(repo_path),
        operation="completed",
        success=True,
        files_processed=status.total_files,
        chunks_created=status.total_chunks,
        duration_ms=duration_ms,
    )

    # Build result with ETA information
    # Combine notifier messages with sync callback messages for full history
    all_messages = (notifier.messages if notifier else []) + progress_messages
    result = {
        "status": "success",
        "repo_path": str(repo_path),
        "wiki_path": str(indexer.wiki_path),
        "files_indexed": status.total_files,
        "chunks_created": status.total_chunks,
        "languages": status.languages,
        "wiki_pages": len(wiki_structure.pages),
        "operation_id": operation_id,
        "messages": all_messages,
    }

    logger.info(
        f"Indexing complete: {status.total_files} files, {status.total_chunks} chunks, {len(wiki_structure.pages)} wiki pages"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_ask_question(args: dict[str, Any]) -> list[TextContent]:
    """Handle ask_question tool call."""
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    # Validate with Pydantic
    try:
        validated = AskQuestionArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    question = validated.question
    max_context = validated.max_context

    # Validate input size limits (CWE-400 prevention)
    validate_query_parameters(question, str(repo_path), max_context)

    # Get subject ID for audit logging
    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    logger.info(f"Question about {repo_path}: {question[:100]}...")
    logger.debug(f"Max context chunks: {max_context}")

    config = get_config()
    wiki_path = config.get_wiki_path(repo_path)
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        raise not_indexed_error(str(repo_path))

    # Create vector store
    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(vector_db_path, embedding_provider)

    # Search for relevant context
    search_results = await vector_store.search(question, limit=max_context)

    if not search_results:
        return [
            TextContent(type="text", text="No relevant code found for your question.")
        ]

    # Build context from search results
    context_parts = []
    for search_result in search_results:
        chunk = search_result.chunk
        context_parts.append(
            f"File: {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})\n"
            f"Type: {chunk.chunk_type.value}\n"
            f"```\n{chunk.content}\n```"
        )

    context = "\n\n---\n\n".join(context_parts)

    # Generate answer using LLM (with caching if enabled)
    from local_deepwiki.providers.llm import get_cached_llm_provider

    cache_path = wiki_path / "llm_cache.lance"
    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=embedding_provider,
        cache_config=config.llm_cache,
        llm_config=config.llm,
    )

    prompt = f"""Based on the following code context, answer this question: {question}

Code Context:
{context}

Provide a clear, accurate answer based only on the code provided. If the code doesn't contain enough information to answer fully, say so."""

    system_prompt = "You are a helpful code assistant. Answer questions about code clearly and accurately."

    # Acquire rate limit before LLM call
    rate_limiter = get_rate_limiter()
    async with rate_limiter:
        answer = await llm.generate(prompt, system_prompt=system_prompt)

    result = {
        "question": question,
        "answer": answer,
        "sources": [
            {
                "file": r.chunk.file_path,
                "lines": f"{r.chunk.start_line}-{r.chunk.end_line}",
                "type": r.chunk.chunk_type.value,
                "score": r.score,
            }
            for r in search_results
        ],
    }

    # Audit: Log query execution success
    duration_ms = int((time.time() - start_time) * 1000)
    audit_logger.log_query_execution(
        subject_id=subject_id,
        repo_path=str(repo_path),
        query=question,
        success=True,
        query_type="ask_question",
        chunks_returned=len(search_results),
        duration_ms=duration_ms,
    )

    logger.info(f"Generated answer with {len(search_results)} sources")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_deep_research(
    args: dict[str, Any],
    server: Any = None,
) -> list[TextContent]:
    """Handle deep_research tool call for multi-step reasoning.

    Args:
        args: Tool arguments.
        server: Optional MCP server instance for progress notifications.

    Returns:
        List of TextContent with research results.
    """
    return await _handle_deep_research_impl(args, server)


class _DeepResearchContext:
    """Context object holding state for deep research execution."""

    def __init__(
        self,
        repo_path: Path,
        question: str,
        max_chunks: int,
        preset: str | None,
        server: Any,
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
    server: Any = None,
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

    logger.info(f"Deep research on {repo_path}: {question[:100]}...")
    logger.debug(
        f"Max chunks: {max_chunks}, preset: {preset or 'default'}, resume: {resume_research_id or 'new'}"
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
    Callable[[], bool],
    Callable[["ResearchProgress"], Awaitable[None]],
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
            pass
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
            logger.warning(f"Failed to send progress notification: {e}")

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
            logger.warning(f"Failed to send cancellation notification: {e}")

    return is_cancelled, progress_callback, send_cancellation_notification


def _format_research_results(result: Any) -> dict[str, Any]:
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


async def _execute_research_phases(
    ctx: _DeepResearchContext,
    pipeline: "DeepResearchPipeline",
    is_cancelled: Callable[[], bool],
    progress_callback: Callable[["ResearchProgress"], Awaitable[None]],
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
            f"Deep research complete: {result.total_chunks_analyzed} chunks, "
            f"{result.total_llm_calls} LLM calls"
        )
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    except ResearchCancelledError as e:
        logger.info(f"Deep research cancelled: {e}")
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
    server: Any = None,
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
async def handle_read_wiki_structure(args: dict[str, Any]) -> list[TextContent]:
    """Handle read_wiki_structure tool call."""
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    # Validate with Pydantic
    try:
        validated = ReadWikiStructureArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    wiki_path = Path(validated.wiki_path).resolve()

    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    # Check for toc.json (numbered hierarchical structure)
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        try:
            toc_content = await asyncio.to_thread(toc_path.read_text)
            toc_data = json.loads(toc_content)
            return [TextContent(type="text", text=json.dumps(toc_data, indent=2))]
        except (json.JSONDecodeError, OSError):
            pass  # Fall back to dynamic generation

    # Fall back to dynamic generation if no toc.json
    pages = []
    for md_file in wiki_path.rglob("*.md"):
        rel_path = str(md_file.relative_to(wiki_path))
        # Read first line for title
        try:
            file_content = await asyncio.to_thread(md_file.read_text)
            first_line = file_content.split("\n", 1)[0].strip()
            title = (
                first_line.lstrip("#").strip()
                if first_line.startswith("#")
                else rel_path
            )
        except (OSError, UnicodeDecodeError) as e:
            # OSError: File access issues
            # UnicodeDecodeError: File encoding issues
            logger.debug(f"Could not read title from {md_file}: {e}")
            title = rel_path

        pages.append(
            {
                "path": rel_path,
                "title": title,
            }
        )

    # Build hierarchical structure (legacy format without numbers)
    structure: dict[str, Any] = {"pages": [], "sections": {}}

    for page in sorted(pages, key=lambda p: p["path"]):
        parts = Path(page["path"]).parts
        if len(parts) == 1:
            structure["pages"].append(page)
        else:
            section = parts[0]
            if section not in structure["sections"]:
                structure["sections"][section] = []
            structure["sections"][section].append(page)

    return [TextContent(type="text", text=json.dumps(structure, indent=2))]


@handle_tool_errors
async def handle_read_wiki_page(args: dict[str, Any]) -> list[TextContent]:
    """Handle read_wiki_page tool call."""
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    # Validate with Pydantic
    try:
        validated = ReadWikiPageArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    wiki_path = Path(validated.wiki_path).resolve()
    page = validated.page

    # Resolve the full path and validate it's within the wiki directory
    # This prevents path traversal attacks (e.g., "../../etc/passwd")
    page_path = (wiki_path / page).resolve()
    if not page_path.is_relative_to(wiki_path):
        raise ValidationError(
            message="Invalid page path: path traversal not allowed",
            hint="The page path must be within the wiki directory.",
            field="page",
            value=page,
        )

    if not page_path.exists():
        raise path_not_found_error(page, "wiki page")

    # Check file size to prevent memory exhaustion
    file_size = page_path.stat().st_size
    if file_size > MAX_WIKI_PAGE_SIZE:
        raise ValidationError(
            message=f"Page too large: {file_size:,} bytes",
            hint=f"Maximum allowed size is {MAX_WIKI_PAGE_SIZE:,} bytes. Consider splitting the content.",
            field="page",
            value=page,
            context={"file_size": file_size, "max_size": MAX_WIKI_PAGE_SIZE},
        )

    content = await asyncio.to_thread(page_path.read_text)
    return [TextContent(type="text", text=content)]


@handle_tool_errors
async def handle_search_code(args: dict[str, Any]) -> list[TextContent]:
    """Handle search_code tool call.

    Supports both vector similarity search and optional fuzzy matching,
    with filters for language, chunk type, and file path patterns.
    """
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.QUERY_SEARCH)

    # Validate with Pydantic
    try:
        validated = SearchCodeArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    query = validated.query
    limit = validated.limit
    language = validate_language(validated.language)
    chunk_type = validate_chunk_type(validated.type)
    path_pattern = validate_path_pattern(validated.path)
    use_fuzzy = validated.fuzzy
    fuzzy_weight = validated.fuzzy_weight

    logger.info(f"Code search in {repo_path}: {query[:50]}...")
    logger.debug(
        f"Search limit: {limit}, language: {language}, type: {chunk_type}, "
        f"path: {path_pattern}, fuzzy: {use_fuzzy}"
    )

    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        raise not_indexed_error(str(repo_path))

    # Create vector store
    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(vector_db_path, embedding_provider)

    # Search with filters
    results = await vector_store.search(
        query,
        limit=limit,
        language=language,
        chunk_type=chunk_type,
        path_pattern=path_pattern,
        use_fuzzy=use_fuzzy,
        fuzzy_weight=fuzzy_weight,
    )

    logger.info(f"Search returned {len(results)} results")
    if not results:
        return [TextContent(type="text", text="No results found.")]

    output = []
    for r in results:
        chunk = r.chunk
        result_entry: dict[str, Any] = {
            "file_path": chunk.file_path,
            "name": chunk.name,
            "type": chunk.chunk_type.value,
            "language": chunk.language.value,
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "score": round(r.score, 4),
            "preview": (
                chunk.content[:300] + "..."
                if len(chunk.content) > 300
                else chunk.content
            ),
            "docstring": chunk.docstring,
        }
        # Include highlights if present (from fuzzy search)
        if r.highlights:
            result_entry["highlights"] = r.highlights
        output.append(result_entry)

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


@handle_tool_errors
async def handle_export_wiki_html(args: dict[str, Any]) -> list[TextContent]:
    """Handle export_wiki_html tool call with streaming support for large wikis."""
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.EXPORT_HTML)

    from local_deepwiki.export.html import export_to_html
    from local_deepwiki.export.streaming import ExportConfig, WikiPageIterator

    # Validate with Pydantic
    try:
        validated = ExportWikiHtmlArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    wiki_path = Path(validated.wiki_path).resolve()
    output_path = validated.output_path

    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    # Determine and validate output path
    if output_path:
        output_path = _validate_export_path(Path(output_path), wiki_path)
    else:
        output_path = wiki_path.parent / f"{wiki_path.name}_html"
        # Validate default path as well
        output_path = _validate_export_path(output_path, wiki_path)

    # Get subject ID for audit logging
    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    # Audit: Log export operation started
    actual_output = output_path
    audit_logger.log_export_operation(
        subject_id=subject_id,
        wiki_path=str(wiki_path),
        output_path=str(actual_output),
        export_type="html",
        operation="started",
        success=True,
    )

    # Check wiki size and recommend streaming if large
    iterator = WikiPageIterator(wiki_path)
    page_count = iterator.get_page_count()
    total_size_mb = iterator.get_total_size_bytes() / (1024 * 1024)
    use_streaming = iterator.should_use_streaming()

    logger.info(
        f"Wiki export: {page_count} pages, {total_size_mb:.2f}MB, "
        f"streaming: {use_streaming}"
    )

    result = export_to_html(wiki_path, output_path)

    # Audit: Log export operation completed
    duration_ms = int((time.time() - start_time) * 1000)
    audit_logger.log_export_operation(
        subject_id=subject_id,
        wiki_path=str(wiki_path),
        output_path=str(actual_output),
        export_type="html",
        operation="completed",
        success=True,
        pages_exported=page_count,
        duration_ms=duration_ms,
    )

    response = {
        "status": "success",
        "message": result,
        "output_path": str(actual_output),
        "open_with": f"open {actual_output}/index.html",
        "stats": {
            "pages_exported": page_count,
            "total_size_mb": round(total_size_mb, 2),
            "streaming_mode": use_streaming,
        },
    }

    return [TextContent(type="text", text=json.dumps(response, indent=2))]


@handle_tool_errors
async def handle_export_wiki_pdf(args: dict[str, Any]) -> list[TextContent]:
    """Handle export_wiki_pdf tool call with streaming support for large wikis."""
    # RBAC check - behavior depends on controller mode (disabled/permissive/enforced)
    controller = get_access_controller()
    controller.require_permission(Permission.EXPORT_PDF)

    from local_deepwiki.export.pdf import export_to_pdf
    from local_deepwiki.export.streaming import ExportConfig, WikiPageIterator

    # Validate with Pydantic
    try:
        validated = ExportWikiPdfArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    wiki_path = Path(validated.wiki_path).resolve()
    output_path = validated.output_path
    single_file = validated.single_file

    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    # Determine and validate output path
    if output_path:
        output_path = _validate_export_path(Path(output_path), wiki_path)
    else:
        # Determine default path based on single_file mode
        if single_file:
            output_path = wiki_path.parent / f"{wiki_path.name}.pdf"
        else:
            output_path = wiki_path.parent / f"{wiki_path.name}_pdfs"
        # Validate default path as well
        output_path = _validate_export_path(output_path, wiki_path)

    # Get subject ID for audit logging
    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    actual_output = output_path

    # Audit: Log export operation started
    audit_logger.log_export_operation(
        subject_id=subject_id,
        wiki_path=str(wiki_path),
        output_path=str(actual_output),
        export_type="pdf",
        operation="started",
        success=True,
    )

    # Check wiki size for stats
    iterator = WikiPageIterator(wiki_path)
    page_count = iterator.get_page_count()
    total_size_mb = iterator.get_total_size_bytes() / (1024 * 1024)
    use_streaming = iterator.should_use_streaming()

    logger.info(
        f"PDF export: {page_count} pages, {total_size_mb:.2f}MB, "
        f"streaming: {use_streaming}"
    )

    result = export_to_pdf(wiki_path, output_path, single_file=single_file)

    # Audit: Log export operation completed
    duration_ms = int((time.time() - start_time) * 1000)
    audit_logger.log_export_operation(
        subject_id=subject_id,
        wiki_path=str(wiki_path),
        output_path=str(actual_output),
        export_type="pdf",
        operation="completed",
        success=True,
        pages_exported=page_count,
        duration_ms=duration_ms,
    )

    response = {
        "status": "success",
        "message": result,
        "output_path": str(actual_output),
        "stats": {
            "pages_exported": page_count,
            "total_size_mb": round(total_size_mb, 2),
            "streaming_mode": use_streaming,
        },
    }

    return [TextContent(type="text", text=json.dumps(response, indent=2))]


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

    logger.info(f"Listed {len(checkpoints)} research checkpoints for {repo_path}")
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

    logger.info(f"Cancelled research {research_id}")
    return [TextContent(type="text", text=json.dumps(response, indent=2))]


@handle_tool_errors
async def handle_resume_research(
    args: dict[str, Any],
    server: Any = None,
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


# =============================================================================
# New Tool Handlers
# =============================================================================


def _load_index_status(repo_path: Path) -> tuple[Any, Path, Any]:
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
    index_status = manager.load(wiki_path)
    if index_status is None:
        raise not_indexed_error(str(repo_path))

    return index_status, wiki_path, config


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

    index_status, wiki_path, config = _load_index_status(repo_path)

    from local_deepwiki.generators.glossary import collect_all_entities

    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(config.get_vector_db_path(repo_path), embedding_provider)

    entities = await collect_all_entities(index_status, vector_store)

    if search_term:
        search_lower = search_term.lower()
        entities = [
            e
            for e in entities
            if search_lower in e.name.lower()
            or (e.docstring and search_lower in e.docstring.lower())
        ]

    result = {
        "status": "success",
        "total_entities": len(entities),
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

    logger.info(f"Glossary: {len(entities)} entities for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    index_status, wiki_path, config = _load_index_status(repo_path)

    from local_deepwiki.generators.diagrams import (
        generate_class_diagram,
        generate_dependency_graph,
        generate_language_pie_chart,
        generate_module_overview,
        generate_sequence_diagram,
    )
    from local_deepwiki.generators.callgraph import CallGraphExtractor

    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(config.get_vector_db_path(repo_path), embedding_provider)

    # Collect chunks from vector store for diagram generation
    all_chunks = list(vector_store.get_all_chunks())

    diagram: str | None = None

    if diagram_type.value == "class":
        diagram = generate_class_diagram(all_chunks)
    elif diagram_type.value == "dependency":
        diagram = generate_dependency_graph(all_chunks)
    elif diagram_type.value == "module":
        diagram = generate_module_overview(index_status)
    elif diagram_type.value == "language_pie":
        diagram = generate_language_pie_chart(index_status)
    elif diagram_type.value == "sequence":
        if entry_point:
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
            raise ValidationError(
                message="entry_point is required for sequence diagrams",
                hint="Provide the name of the function to use as the sequence diagram entry point.",
                field="entry_point",
            )

    if diagram is None:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": f"No {diagram_type.value} diagram could be generated (no relevant data found)",
                    },
                    indent=2,
                ),
            )
        ]

    result = {
        "status": "success",
        "diagram_type": diagram_type.value,
        "mermaid": diagram,
    }

    logger.info(f"Generated {diagram_type.value} diagram for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    index_status, wiki_path, config = _load_index_status(repo_path)

    from local_deepwiki.generators.inheritance import (
        collect_class_hierarchy,
        generate_inheritance_diagram,
    )

    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(config.get_vector_db_path(repo_path), embedding_provider)

    classes = await collect_class_hierarchy(index_status, vector_store)

    if not classes:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "No class hierarchies found in the codebase",
                        "classes": [],
                    },
                    indent=2,
                ),
            )
        ]

    diagram = generate_inheritance_diagram(classes)

    result = {
        "status": "success",
        "total_classes": len(classes),
        "classes": [
            {
                "name": node.name,
                "file_path": node.file_path,
                "parents": node.parents,
                "children": node.children,
                "is_abstract": node.is_abstract,
                "docstring": node.docstring,
            }
            for node in classes.values()
        ],
        "mermaid_diagram": diagram,
    }

    logger.info(f"Inheritance: {len(classes)} classes for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
        index_status, wiki_path, config = _load_index_status(repo_path)
        combined_graph: dict[str, list[str]] = {}
        for file_info in index_status.files:
            fp = repo_path / file_info.path
            if fp.exists():
                graph = extractor.extract_from_file(fp, repo_path)
                for k, v in graph.items():
                    combined_graph.setdefault(k, []).extend(v)
        diagram = generate_call_graph_diagram(combined_graph)

    if diagram is None:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "No call relationships found",
                    },
                    indent=2,
                ),
            )
        ]

    result = {
        "status": "success",
        "mermaid": diagram,
        "scope": file_path or "full_repository",
    }

    logger.info(f"Call graph generated for {file_path or repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    index_status, wiki_path, config = _load_index_status(repo_path)

    from local_deepwiki.generators.coverage import analyze_project_coverage

    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(config.get_vector_db_path(repo_path), embedding_provider)

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

    logger.info(f"Coverage: {stats.coverage_percent:.1f}% for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    config = get_config()
    wiki_path = config.get_wiki_path(repo_path)

    if not wiki_path.exists():
        raise not_indexed_error(str(repo_path))

    from local_deepwiki.generators.stale_detection import analyze_staleness
    from local_deepwiki.generators.wiki_status import WikiStatusManager

    manager = WikiStatusManager(wiki_path)
    wiki_status = await manager.load_status()

    if wiki_status is None:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "No wiki generation status found. Run index_repository first.",
                        "stale_pages": [],
                    },
                    indent=2,
                ),
            )
        ]

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
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": "No git history found. Is this a git repository?",
                    },
                    indent=2,
                ),
            )
        ]

    result = {
        "status": "success",
        "changelog": content,
    }

    logger.info(f"Changelog generated for {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    total_findings = sum(len(findings) for findings in findings_by_file.values())

    result = {
        "status": "success",
        "files_with_secrets": len(findings_by_file),
        "total_findings": total_findings,
        "findings": [
            {
                "file_path": file_path,
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
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    index_status, wiki_path, config = _load_index_status(repo_path)

    from local_deepwiki.generators.test_examples import CodeExampleExtractor

    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(config.get_vector_db_path(repo_path), embedding_provider)

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
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": f"No test examples found for '{entity_name}'",
                        "examples": [],
                    },
                    indent=2,
                ),
            )
        ]

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

    logger.info(f"Test examples: {len(examples)} for '{entity_name}' in {repo_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "message": f"No API documentation could be extracted from '{file_path}'",
                    },
                    indent=2,
                ),
            )
        ]

    result = {
        "status": "success",
        "file_path": file_path,
        "api_docs": api_docs,
    }

    logger.info(f"API docs generated for {file_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    logger.info(f"Found {len(repos)} indexed repos under {base_path}")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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

    index_status, wiki_path, config = _load_index_status(repo_path)

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
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


class ProgressNotifier:
    """Helper class for sending buffered MCP progress notifications.

    Integrates ProgressManager with MCP server notifications,
    handling buffering and async notification delivery.
    """

    def __init__(
        self,
        progress_manager: ProgressManager,
        server: Any,
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
            logger.warning(f"Failed to send progress notification: {e}")

    @property
    def messages(self) -> list[str]:
        """Get accumulated progress messages."""
        return self._messages


def create_progress_notifier(
    operation_type: OperationType,
    server: Any,
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
