"""Core tool handlers: querying, wiki reading, search, and export."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.config import get_config
from local_deepwiki.core.audit import (
    ExportAuditParams,
    QueryAuditParams,
    get_audit_logger,
)
from local_deepwiki.errors import path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._export_validation import _validate_export_path
from local_deepwiki.handlers._index_helpers import (
    _create_vector_store,
    _load_index_status,
)
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    AskQuestionArgs,
    ExportWikiHtmlArgs,
    ExportWikiPdfArgs,
    ReadWikiPageArgs,
    ReadWikiStructureArgs,
    SearchCodeArgs,
)
from local_deepwiki.providers.embeddings import get_embedding_provider  # noqa: F401
from local_deepwiki.security import Permission, get_access_controller
from local_deepwiki.services.provider_factory import ProviderFactory
from local_deepwiki.validation import (
    validate_chunk_type,
    validate_language,
    validate_path_pattern,
    validate_query_parameters,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ExportCompletionContext:
    """Immutable context for audit-logging an export completion.

    Bundles the parameters of _audit_export_completed to reduce its
    parameter count.
    """

    audit_logger: Any
    subject_id: str
    wiki_path: Path
    output_path: Path
    export_type: str


def _build_ask_question_result(question: str, query_result: Any) -> dict[str, Any]:
    """Convert a QueryResult to the ask_question response dict."""
    sources = [
        {
            "file": s.file,
            "lines": s.lines,
            "type": s.chunk_type,
            "score": s.score,
            **({"wiki_resource": s.wiki_resource} if s.wiki_resource else {}),
        }
        for s in query_result.sources
    ]
    result: dict[str, Any] = {
        "question": question,
        "answer": query_result.answer,
        "sources": sources,
    }
    if query_result.agentic_metadata is not None:
        result["agentic_rag"] = query_result.agentic_metadata
    if query_result.trace is not None:
        result["_trace"] = query_result.trace
    return result


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

    logger.info("Question about %s: %s...", repo_path, question[:100])

    _index_status, wiki_path, config = await _load_index_status(repo_path)
    vector_store = _create_vector_store(repo_path, config)

    llm = ProviderFactory.create_cached_llm_provider(
        cache_path=wiki_path / "llm_cache.lance",
        embedding_provider=get_embedding_provider(config.embedding),
        cache_config=config.llm_cache,
        llm_config=config.llm,
    )

    from local_deepwiki.services.query_service import QuestionRequest, QueryService

    svc = QueryService(vector_store, llm, config)
    query_result = await svc.answer_question(
        QuestionRequest(
            repo_path=repo_path,
            question=question,
            max_context=max_context,
            agentic_rag=validated.agentic_rag,
            wiki_path=wiki_path,
            debug=validated.debug,
        )
    )

    result = _build_ask_question_result(question, query_result)

    duration_ms = int((time.time() - start_time) * 1000)
    audit_logger.log_query(
        QueryAuditParams(
            subject_id=subject_id,
            repo_path=str(repo_path),
            query=question,
            success=True,
            query_type="ask_question",
            chunks_returned=len(query_result.sources),
            duration_ms=duration_ms,
        )
    )

    logger.info("Generated answer with %s sources", len(query_result.sources))
    return make_tool_text_content("ask_question", result)


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

    from local_deepwiki.services.wiki_service import WikiService

    svc = WikiService(get_config())
    structure = await svc.read_structure(wiki_path)
    return make_tool_text_content("read_wiki_structure", structure)


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

    from local_deepwiki.services.wiki_service import WikiService

    svc = WikiService(get_config())
    content = await svc.read_page(wiki_path, validated.page)
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
    language = validate_language(validated.language)
    chunk_type = validate_chunk_type(validated.type)
    path_pattern = validate_path_pattern(validated.path)

    logger.info("Code search in %s: %s...", repo_path, query[:50])

    _index_status, _wiki_path, config = await _load_index_status(repo_path)
    vector_store = _create_vector_store(repo_path, config)

    from local_deepwiki.services.query_service import CodeSearchRequest, QueryService

    svc = QueryService(vector_store, None, config)  # type: ignore[arg-type]
    results = await svc.search_code(
        CodeSearchRequest(
            repo_path=repo_path,
            query=query,
            limit=validated.limit,
            language=language,
            chunk_type=chunk_type,
            path_filter=path_pattern,
            use_fuzzy=validated.fuzzy,
            fuzzy_weight=validated.fuzzy_weight,
        )
    )

    logger.info("Search returned %s results", len(results))
    if not results:
        return make_tool_text_content(
            "search_code",
            {"message": "No results found.", "total_results": 0, "results": []},
        )

    return make_tool_text_content(
        "search_code",
        {"total_results": len(results), "results": results},
    )


def _audit_export_started(
    audit_logger: Any,
    subject_id: str,
    wiki_path: Path,
    output_path: Path,
    export_type: str,
) -> None:
    """Log the start of an export operation."""
    audit_logger.log_export(
        ExportAuditParams(
            subject_id=subject_id,
            wiki_path=str(wiki_path),
            output_path=str(output_path),
            export_type=export_type,
            operation="started",
            success=True,
        )
    )


def _audit_export_completed(
    ctx: ExportCompletionContext,
    page_count: int,
    duration_ms: int,
) -> None:
    """Log the completion of an export operation."""
    ctx.audit_logger.log_export(
        ExportAuditParams(
            subject_id=ctx.subject_id,
            wiki_path=str(ctx.wiki_path),
            output_path=str(ctx.output_path),
            export_type=ctx.export_type,
            operation="completed",
            success=True,
            pages_exported=page_count,
            duration_ms=duration_ms,
        )
    )


@handle_tool_errors
async def handle_export_wiki_html(args: dict[str, Any]) -> list[TextContent]:
    """Handle export_wiki_html tool call with streaming support for large wikis."""
    controller = get_access_controller()
    controller.require_permission(Permission.EXPORT_HTML)

    from local_deepwiki.export.html import export_to_html
    from local_deepwiki.export.streaming import WikiPageIterator

    try:
        validated = ExportWikiHtmlArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    wiki_path = Path(validated.wiki_path).resolve()
    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    raw_output = validated.output_path
    resolved_output = (
        _validate_export_path(Path(raw_output), wiki_path)
        if raw_output
        else _validate_export_path(
            wiki_path.parent / f"{wiki_path.name}_html", wiki_path
        )
    )

    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    _audit_export_started(audit_logger, subject_id, wiki_path, resolved_output, "html")

    export_ctx = ExportCompletionContext(
        audit_logger=audit_logger,
        subject_id=subject_id,
        wiki_path=wiki_path,
        output_path=resolved_output,
        export_type="html",
    )

    iterator = WikiPageIterator(wiki_path)
    page_count = iterator.get_page_count()
    total_size_mb = iterator.get_total_size_bytes() / (1024 * 1024)
    use_streaming = iterator.should_use_streaming()
    logger.info(
        "Wiki export: %d pages, %.2fMB, streaming: %s",
        page_count,
        total_size_mb,
        use_streaming,
    )

    result = export_to_html(wiki_path, resolved_output)

    _audit_export_completed(
        export_ctx,
        page_count,
        int((time.time() - start_time) * 1000),
    )

    return make_tool_text_content(
        "export_wiki_html",
        {
            "status": "success",
            "message": result,
            "output_path": str(resolved_output),
            "open_with": f"open {resolved_output}/index.html",
            "stats": {
                "pages_exported": page_count,
                "total_size_mb": round(total_size_mb, 2),
                "streaming_mode": use_streaming,
            },
        },
    )


@handle_tool_errors
async def handle_export_wiki_pdf(args: dict[str, Any]) -> list[TextContent]:
    """Handle export_wiki_pdf tool call with streaming support for large wikis."""
    controller = get_access_controller()
    controller.require_permission(Permission.EXPORT_PDF)

    from local_deepwiki.export.pdf import export_to_pdf
    from local_deepwiki.export.streaming import WikiPageIterator

    try:
        validated = ExportWikiPdfArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    wiki_path = Path(validated.wiki_path).resolve()
    single_file = validated.single_file
    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    raw_output = validated.output_path
    if raw_output:
        resolved_output = _validate_export_path(Path(raw_output), wiki_path)
    else:
        default_path = (
            wiki_path.parent / f"{wiki_path.name}.pdf"
            if single_file
            else wiki_path.parent / f"{wiki_path.name}_pdfs"
        )
        resolved_output = _validate_export_path(default_path, wiki_path)

    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    _audit_export_started(audit_logger, subject_id, wiki_path, resolved_output, "pdf")

    export_ctx = ExportCompletionContext(
        audit_logger=audit_logger,
        subject_id=subject_id,
        wiki_path=wiki_path,
        output_path=resolved_output,
        export_type="pdf",
    )

    iterator = WikiPageIterator(wiki_path)
    page_count = iterator.get_page_count()
    total_size_mb = iterator.get_total_size_bytes() / (1024 * 1024)
    use_streaming = iterator.should_use_streaming()
    logger.info(
        "PDF export: %d pages, %.2fMB, streaming: %s",
        page_count,
        total_size_mb,
        use_streaming,
    )

    result = export_to_pdf(wiki_path, resolved_output, single_file=single_file)

    _audit_export_completed(
        export_ctx,
        page_count,
        int((time.time() - start_time) * 1000),
    )

    return make_tool_text_content(
        "export_wiki_pdf",
        {
            "status": "success",
            "message": result,
            "output_path": str(resolved_output),
            "stats": {
                "pages_exported": page_count,
                "total_size_mb": round(total_size_mb, 2),
                "streaming_mode": use_streaming,
            },
        },
    )
