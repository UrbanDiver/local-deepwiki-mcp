"""Tool handlers for the MCP server."""

import asyncio
import json
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from local_deepwiki.core.deep_research import DeepResearchPipeline
    from local_deepwiki.models import ResearchProgress

from mcp.types import TextContent

from local_deepwiki.config import get_config
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.embeddings import get_embedding_provider
from local_deepwiki.validation import (
    DEFAULT_DEEP_RESEARCH_CHUNKS,
    MAX_CONTEXT_CHUNKS,
    MAX_DEEP_RESEARCH_CHUNKS,
    MAX_SEARCH_LIMIT,
    MAX_WIKI_PAGE_SIZE,
    MIN_CONTEXT_CHUNKS,
    MIN_DEEP_RESEARCH_CHUNKS,
    MIN_SEARCH_LIMIT,
    VALID_EMBEDDING_PROVIDERS,
    VALID_LLM_PROVIDERS,
    validate_chunk_type,
    validate_fuzzy_weight,
    validate_language,
    validate_languages_list,
    validate_non_empty_string,
    validate_path_pattern,
    validate_positive_int,
    validate_provider,
)

logger = get_logger(__name__)

# Type alias for tool handler functions
ToolHandler = Callable[[dict[str, Any]], Awaitable[list[TextContent]]]


def handle_tool_errors(func: ToolHandler) -> ToolHandler:
    """Decorator for consistent error handling in tool handlers.

    Catches common exceptions and returns properly formatted error responses:
    - ValueError: Input validation errors (logged at ERROR level)
    - Exception: Unexpected errors (logged with full traceback)

    Args:
        func: The async tool handler function to wrap.

    Returns:
        Wrapped function with consistent error handling.
    """

    @wraps(func)
    async def wrapper(args: dict[str, Any]) -> list[TextContent]:
        try:
            return await func(args)
        except ValueError as e:
            logger.error(f"Invalid input in {func.__name__}: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]
        except asyncio.CancelledError:
            # Re-raise cancellation to propagate properly
            raise
        except Exception as e:  # noqa: BLE001
            # Broad catch is intentional: top-level error handler for MCP tools
            # that converts any unhandled exception to a user-friendly error message
            logger.exception(f"Error in {func.__name__}: {e}")
            return [TextContent(type="text", text=f"Error: {e}")]

    return wrapper


@handle_tool_errors
async def handle_index_repository(args: dict[str, Any]) -> list[TextContent]:
    """Handle index_repository tool call."""
    repo_path = Path(args["repo_path"]).resolve()
    logger.info(f"Indexing repository: {repo_path}")

    if not repo_path.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    # Validate optional parameters
    languages = validate_languages_list(args.get("languages"))
    llm_provider = validate_provider(args.get("llm_provider"), VALID_LLM_PROVIDERS, "llm_provider")
    embedding_provider = validate_provider(
        args.get("embedding_provider"), VALID_EMBEDDING_PROVIDERS, "embedding_provider"
    )

    # Get config (immutable, create copy with any overrides)
    base_config = get_config()
    config_updates: dict = {}

    # Override languages if specified
    if languages:
        new_parsing = base_config.parsing.model_copy(update={"languages": languages})
        config_updates["parsing"] = new_parsing

    # Override use_cloud_for_github if specified
    use_cloud_for_github = args.get("use_cloud_for_github")
    if use_cloud_for_github is not None:
        new_wiki = base_config.wiki.model_copy(update={"use_cloud_for_github": use_cloud_for_github})
        config_updates["wiki"] = new_wiki

    # Create modified config or use base if no overrides
    if config_updates:
        config = base_config.model_copy(update=config_updates)
    else:
        config = base_config

    # Create indexer
    indexer = RepositoryIndexer(
        repo_path=repo_path,
        config=config,
        embedding_provider_name=embedding_provider,
    )

    # Index the repository
    full_rebuild = args.get("full_rebuild", False)

    messages = []

    def progress_callback(msg: str, current: int, total: int):
        messages.append(f"[{current}/{total}] {msg}")

    status = await indexer.index(
        full_rebuild=full_rebuild,
        progress_callback=progress_callback,
    )

    # Generate wiki documentation
    messages.append("Generating wiki documentation...")

    wiki_structure = await generate_wiki(
        repo_path=repo_path,
        wiki_path=indexer.wiki_path,
        vector_store=indexer.vector_store,
        index_status=status,
        config=config,
        llm_provider=llm_provider,
        progress_callback=progress_callback,
        full_rebuild=full_rebuild,
    )

    result = {
        "status": "success",
        "repo_path": str(repo_path),
        "wiki_path": str(indexer.wiki_path),
        "files_indexed": status.total_files,
        "chunks_created": status.total_chunks,
        "languages": status.languages,
        "wiki_pages": len(wiki_structure.pages),
        "messages": messages,
    }

    logger.info(
        f"Indexing complete: {status.total_files} files, {status.total_chunks} chunks, {len(wiki_structure.pages)} wiki pages"
    )
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


@handle_tool_errors
async def handle_ask_question(args: dict[str, Any]) -> list[TextContent]:
    """Handle ask_question tool call."""
    repo_path = Path(args["repo_path"]).resolve()

    # Validate inputs
    question = validate_non_empty_string(args.get("question", ""), "question")
    max_context = validate_positive_int(
        args.get("max_context"),
        "max_context",
        MIN_CONTEXT_CHUNKS,
        MAX_CONTEXT_CHUNKS,
        default=5,
    )

    logger.info(f"Question about {repo_path}: {question[:100]}...")
    logger.debug(f"Max context chunks: {max_context}")

    config = get_config()
    wiki_path = config.get_wiki_path(repo_path)
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        raise ValueError("Repository not indexed. Run index_repository first.")

    # Create vector store
    embedding_provider = get_embedding_provider(config.embedding)
    vector_store = VectorStore(vector_db_path, embedding_provider)

    # Search for relevant context
    search_results = await vector_store.search(question, limit=max_context)

    if not search_results:
        return [TextContent(type="text", text="No relevant code found for your question.")]

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

    system_prompt = (
        "You are a helpful code assistant. Answer questions about code clearly and accurately."
    )

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

    logger.info(f"Generated answer with {len(search_results)} sources")
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


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
    try:
        return await _handle_deep_research_impl(args, server)
    except ValueError as e:
        logger.error(f"Invalid input in handle_deep_research: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        # Broad catch is intentional: top-level error handler for deep_research
        # that converts any unhandled exception to a user-friendly error message
        logger.exception(f"Error in handle_deep_research: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]


class _DeepResearchContext:
    """Context object holding state for deep research execution."""

    def __init__(
        self,
        repo_path: Path,
        question: str,
        max_chunks: int,
        preset: str | None,
        server: Any,
    ):
        self.repo_path = repo_path
        self.question = question
        self.max_chunks = max_chunks
        self.preset = preset
        self.server = server
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
    repo_path = Path(args["repo_path"]).resolve()

    # Validate inputs
    question = validate_non_empty_string(args.get("question", ""), "question")
    max_chunks = validate_positive_int(
        args.get("max_chunks"),
        "max_chunks",
        MIN_DEEP_RESEARCH_CHUNKS,
        MAX_DEEP_RESEARCH_CHUNKS,
        default=DEFAULT_DEEP_RESEARCH_CHUNKS,
    )

    # Get preset parameter (optional)
    preset = args.get("preset")

    logger.info(f"Deep research on {repo_path}: {question[:100]}...")
    logger.debug(f"Max chunks: {max_chunks}, preset: {preset or 'default'}")

    # Create context
    ctx = _DeepResearchContext(
        repo_path=repo_path,
        question=question,
        max_chunks=max_chunks,
        preset=preset,
        server=server,
    )

    # Validate repository is indexed
    vector_db_path = ctx.config.get_vector_db_path(repo_path)
    if not vector_db_path.exists():
        raise ValueError("Repository not indexed. Run index_repository first.")

    # Extract progress token from MCP request context
    if server is not None:
        try:
            request_ctx = server.request_context
            if request_ctx.meta and request_ctx.meta.progressToken:
                ctx.progress_token = request_ctx.meta.progressToken
        except LookupError:
            # Not in a request context (e.g., testing)
            pass

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
        ctx.max_chunks if args.get("max_chunks") is not None else dr_config.max_total_chunks
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
    )

    return pipeline, vector_store, llm


def _create_progress_callbacks(
    ctx: _DeepResearchContext,
) -> tuple[Callable[[], bool], Callable[["ResearchProgress"], Awaitable[None]], Callable[[str], Awaitable[None]]]:
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
            {"question": sq.question, "category": sq.category} for sq in result.sub_questions
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
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "cancelled",
                        "message": f"Research cancelled during {e.step}",
                    }
                ),
            )
        ]

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
    # Step 1: Setup config and validate inputs
    ctx = _setup_deep_research_config(args, server)

    # Step 2: Create the research pipeline with providers
    pipeline, *_ = _create_research_pipeline(ctx, args)

    # Step 3: Create progress and cancellation callbacks
    is_cancelled, progress_callback, send_cancellation_notification = _create_progress_callbacks(ctx)

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
    wiki_path = Path(args["wiki_path"]).resolve()

    if not wiki_path.exists():
        raise ValueError(f"Wiki path does not exist: {wiki_path}")

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
            title = first_line.lstrip("#").strip() if first_line.startswith("#") else rel_path
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
    wiki_path = Path(args["wiki_path"]).resolve()
    page = args["page"]

    # Resolve the full path and validate it's within the wiki directory
    # This prevents path traversal attacks (e.g., "../../etc/passwd")
    page_path = (wiki_path / page).resolve()
    if not page_path.is_relative_to(wiki_path):
        raise ValueError("Invalid page path")

    if not page_path.exists():
        raise ValueError(f"Page not found: {page}")

    # Check file size to prevent memory exhaustion
    file_size = page_path.stat().st_size
    if file_size > MAX_WIKI_PAGE_SIZE:
        raise ValueError(
            f"Page too large: {file_size:,} bytes (max {MAX_WIKI_PAGE_SIZE:,} bytes)"
        )

    content = await asyncio.to_thread(page_path.read_text)
    return [TextContent(type="text", text=content)]


@handle_tool_errors
async def handle_search_code(args: dict[str, Any]) -> list[TextContent]:
    """Handle search_code tool call.

    Supports both vector similarity search and optional fuzzy matching,
    with filters for language, chunk type, and file path patterns.
    """
    repo_path = Path(args["repo_path"]).resolve()

    # Validate inputs
    query = validate_non_empty_string(args.get("query", ""), "query")
    limit = validate_positive_int(
        args.get("limit"),
        "limit",
        MIN_SEARCH_LIMIT,
        MAX_SEARCH_LIMIT,
        default=10,
    )
    language = validate_language(args.get("language"))
    chunk_type = validate_chunk_type(args.get("type"))
    path_pattern = validate_path_pattern(args.get("path"))
    use_fuzzy = bool(args.get("fuzzy", False))
    fuzzy_weight = validate_fuzzy_weight(args.get("fuzzy_weight"))

    logger.info(f"Code search in {repo_path}: {query[:50]}...")
    logger.debug(
        f"Search limit: {limit}, language: {language}, type: {chunk_type}, "
        f"path: {path_pattern}, fuzzy: {use_fuzzy}"
    )

    config = get_config()
    vector_db_path = config.get_vector_db_path(repo_path)

    if not vector_db_path.exists():
        raise ValueError("Repository not indexed. Run index_repository first.")

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
                chunk.content[:300] + "..." if len(chunk.content) > 300 else chunk.content
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
    """Handle export_wiki_html tool call."""
    from local_deepwiki.export.html import export_to_html

    wiki_path = Path(args["wiki_path"]).resolve()
    output_path = args.get("output_path")

    if not wiki_path.exists():
        raise ValueError(f"Wiki path does not exist: {wiki_path}")

    if output_path:
        output_path = Path(output_path).resolve()

    result = export_to_html(wiki_path, output_path)

    # Get actual output path for the response
    actual_output = output_path or (wiki_path.parent / f"{wiki_path.name}_html")

    response = {
        "status": "success",
        "message": result,
        "output_path": str(actual_output),
        "open_with": f"open {actual_output}/index.html",
    }

    return [TextContent(type="text", text=json.dumps(response, indent=2))]


@handle_tool_errors
async def handle_export_wiki_pdf(args: dict[str, Any]) -> list[TextContent]:
    """Handle export_wiki_pdf tool call."""
    from local_deepwiki.export.pdf import export_to_pdf

    wiki_path = Path(args["wiki_path"]).resolve()
    output_path = args.get("output_path")
    single_file = args.get("single_file", True)

    if not wiki_path.exists():
        raise ValueError(f"Wiki path does not exist: {wiki_path}")

    if output_path:
        output_path = Path(output_path).resolve()

    result = export_to_pdf(wiki_path, output_path, single_file=single_file)

    # Get actual output path for the response
    if single_file:
        actual_output = output_path or (wiki_path.parent / f"{wiki_path.name}.pdf")
    else:
        actual_output = output_path or (wiki_path.parent / f"{wiki_path.name}_pdfs")

    response = {
        "status": "success",
        "message": result,
        "output_path": str(actual_output),
    }

    return [TextContent(type="text", text=json.dumps(response, indent=2))]
