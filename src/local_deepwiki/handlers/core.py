"""Core tool handlers: indexing, querying, wiki reading, search, and export."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.handlers._shared import (
    MAX_WIKI_PAGE_SIZE,
    AskQuestionArgs,
    ExportWikiHtmlArgs,
    ExportWikiPdfArgs,
    IndexingProgressType,
    IndexRepositoryArgs,
    OperationType,
    Permission,
    ProgressPhase,
    ReadWikiPageArgs,
    ReadWikiStructureArgs,
    RepositoryIndexer,
    SearchCodeArgs,
    ValidationError,
    _create_vector_store,
    _load_index_status,
    _validate_export_path,
    build_wiki_resource_uri,
    create_progress_notifier,
    generate_wiki,
    get_access_controller,
    get_audit_logger,
    get_config,
    get_embedding_provider,
    get_progress_registry,
    get_rate_limiter,
    get_repository_access_controller,
    handle_tool_errors,
    logger,
    make_tool_text_content,
    path_not_found_error,
    validate_chunk_type,
    validate_index_parameters,
    validate_language,
    validate_languages_list,
    validate_path_pattern,
    validate_query_parameters,
)
from local_deepwiki.models import WikiStructure


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


def _validate_and_build_config(
    validated: IndexRepositoryArgs,
) -> tuple[Path, Any, str | None, str | None]:
    """Validate inputs and build configuration for indexing.

    Returns:
        Tuple of (repo_path, config, llm_provider, embedding_provider).
    """
    repo_path = Path(validated.repo_path).resolve()

    # Check repository access (allowlist/denylist)
    repo_access = get_repository_access_controller()
    repo_access.require_access(repo_path)

    # Validate input size limits (CWE-400 prevention)
    total_size, file_count = validate_index_parameters(str(repo_path))
    logger.info(
        f"Indexing repository: {repo_path} ({total_size:,} bytes, {file_count:,} files)"
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

    languages = validate_languages_list(validated.languages)
    llm_provider = validated.llm_provider.value if validated.llm_provider else None
    embedding_provider = (
        validated.embedding_provider.value if validated.embedding_provider else None
    )

    # Build config with any overrides
    base_config = get_config()
    config_updates: dict = {}

    if languages:
        config_updates["parsing"] = base_config.parsing.model_copy(
            update={"languages": languages}
        )

    if validated.use_cloud_for_github is not None:
        config_updates["wiki"] = base_config.wiki.model_copy(
            update={"use_cloud_for_github": validated.use_cloud_for_github}
        )

    # Override generation_mode if specified (or skip_wiki forces lazy)
    effective_mode = validated.generation_mode
    if validated.skip_wiki:
        effective_mode = "lazy"
    wiki_overrides: dict = {}
    if effective_mode is not None:
        from local_deepwiki.config import GenerationMode

        wiki_overrides["generation_mode"] = GenerationMode(effective_mode)
    if validated.prefetch_drain is not None:
        wiki_overrides["prefetch_drain"] = validated.prefetch_drain
    if wiki_overrides:
        if "wiki" in config_updates:
            config_updates["wiki"] = config_updates["wiki"].model_copy(
                update=wiki_overrides
            )
        else:
            config_updates["wiki"] = base_config.wiki.model_copy(update=wiki_overrides)

    config = (
        base_config.model_copy(update=config_updates) if config_updates else base_config
    )

    return repo_path, config, llm_provider, embedding_provider


async def _run_indexing_pipeline(
    repo_path: Path,
    config: Any,
    llm_provider: str | None,
    embedding_provider: str | None,
    full_rebuild: bool,
    server: Any,
) -> tuple[Any, Any, Any, list[str], str]:
    """Run the indexing and wiki generation pipeline with progress tracking.

    Returns:
        Tuple of (indexer, status, wiki_structure, progress_messages, operation_id).
    """
    registry = get_progress_registry()
    wiki_path = config.get_wiki_path(repo_path)
    progress_data_path = wiki_path / "progress_history.json"
    registry.set_data_path(progress_data_path)

    notifier, operation_id = create_progress_notifier(
        operation_type=OperationType.INDEX_REPOSITORY,
        server=server,
        total=6,
    )

    indexer = RepositoryIndexer(
        repo_path=repo_path,
        config=config,
        embedding_provider_name=embedding_provider,
    )

    progress_messages: list[str] = []

    def sync_progress_callback(msg: str, current: int, total: int) -> None:
        progress_messages.append(f"[{current}/{total}] {msg}")

    try:
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

        if notifier:
            await notifier.update(
                current=5,
                phase=ProgressPhase.WIKI_GENERATION,
                message="Generating wiki documentation...",
            )

        from local_deepwiki.config import GenerationMode

        gen_mode = config.wiki.generation_mode

        if gen_mode == GenerationMode.LAZY:
            from local_deepwiki.generators.crosslinks import (
                build_entity_registry_from_store,
            )
            from local_deepwiki.generators.wiki_files import filter_significant_files

            significant = filter_significant_files(
                status.files, config.wiki.max_file_docs
            )
            sig_paths = {f.path for f in significant}
            registry = build_entity_registry_from_store(
                indexer.vector_store.get_all_chunks(), sig_paths
            )
            registry.save(indexer.wiki_path / "entity_registry.json")

            wiki_structure = WikiStructure(root=str(indexer.wiki_path), pages=[])

        elif gen_mode == GenerationMode.HYBRID:
            from local_deepwiki.generators.crosslinks import (
                build_entity_registry_from_store,
            )
            from local_deepwiki.generators.wiki_files import filter_significant_files

            eager_limit = config.wiki.hybrid_eager_pages
            wiki_structure = await generate_wiki(
                repo_path=repo_path,
                wiki_path=indexer.wiki_path,
                vector_store=indexer.vector_store,
                index_status=status,
                config=config,
                llm_provider=llm_provider,
                progress_callback=sync_progress_callback,
                full_rebuild=full_rebuild,
                max_file_pages=eager_limit,
            )

            significant = filter_significant_files(
                status.files, config.wiki.max_file_docs
            )
            sig_paths = {f.path for f in significant}
            entity_reg = build_entity_registry_from_store(
                indexer.vector_store.get_all_chunks(), sig_paths
            )
            entity_reg.save(indexer.wiki_path / "entity_registry.json")

            remaining = len(significant) - eager_limit
            if remaining > 0:
                logger.info(
                    "Hybrid mode: %d pages generated eagerly, %d deferred to lazy/drain",
                    eager_limit,
                    remaining,
                )
                if config.wiki.prefetch_drain:
                    from local_deepwiki.generators.lazy_generator import (
                        get_lazy_generator,
                    )

                    lazy_gen = get_lazy_generator(indexer.wiki_path, config)
                    lazy_gen.kickstart_drain()

        else:
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

        registry.complete_operation(operation_id, record_timing=True)

    except Exception:
        registry.complete_operation(operation_id, record_timing=False)
        raise

    all_messages = (notifier.messages if notifier else []) + progress_messages
    return indexer, status, wiki_structure, all_messages, operation_id


async def _handle_index_repository_impl(
    args: dict[str, Any],
    server: Any = None,
) -> list[TextContent]:
    """Internal implementation of index_repository with progress streaming and ETA."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_WRITE)

    try:
        validated = IndexRepositoryArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"

    audit_logger = get_audit_logger()
    start_time = time.time()
    audit_logger.log_index_operation(
        subject_id=subject_id,
        repo_path=validated.repo_path,
        operation="started",
        success=True,
    )

    repo_path, config, llm_provider, embedding_provider = await asyncio.to_thread(
        _validate_and_build_config, validated
    )

    try:
        (
            indexer,
            status,
            wiki_structure,
            all_messages,
            operation_id,
        ) = await _run_indexing_pipeline(
            repo_path=repo_path,
            config=config,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            full_rebuild=validated.full_rebuild,
            server=server,
        )
    except Exception as e:
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
        f"Indexing complete: {status.total_files} files, {status.total_chunks} chunks, "
        f"{len(wiki_structure.pages)} wiki pages"
    )

    # Record in session state so downstream tools know this repo is indexed
    from local_deepwiki.handlers.session_state import record_index

    record_index(str(repo_path), str(indexer.wiki_path))

    return make_tool_text_content("index_repository", result)


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
    logger.debug("Max context chunks: %s", max_context)

    _index_status, wiki_path, config = await _load_index_status(repo_path)

    # Create vector store
    vector_store = _create_vector_store(repo_path, config)

    # Generate LLM provider (needed for both paths)
    from local_deepwiki.providers.llm import get_cached_llm_provider

    cache_path = wiki_path / "llm_cache.lance"
    llm = get_cached_llm_provider(
        cache_path=cache_path,
        embedding_provider=get_embedding_provider(config.embedding),
        cache_config=config.llm_cache,
        llm_config=config.llm,
    )

    # Agentic RAG path: grade relevance and optionally rewrite query
    agentic_metadata = None
    if validated.agentic_rag:
        from local_deepwiki.core.agentic_rag import agentic_retrieve

        rag_result = await agentic_retrieve(
            question, vector_store, llm, max_context=max_context
        )
        search_results = rag_result.results
        agentic_metadata = rag_result.metadata
    else:
        # Standard retrieval path
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

    prompt = f"""Based on the following code context, answer this question: {question}

Code Context:
{context}

Provide a clear, accurate answer based only on the code provided. If the code doesn't contain enough information to answer fully, say so."""

    system_prompt = "You are a helpful code assistant. Answer questions about code clearly and accurately."

    # Acquire rate limit before LLM call
    rate_limiter = get_rate_limiter()
    async with rate_limiter:
        answer = await llm.generate(prompt, system_prompt=system_prompt)

    # Build source entries with optional wiki_resource URIs
    sources = []
    for r in search_results:
        entry: dict[str, Any] = {
            "file": r.chunk.file_path,
            "lines": f"{r.chunk.start_line}-{r.chunk.end_line}",
            "type": r.chunk.chunk_type.value,
            "score": r.score,
        }
        # Add wiki_resource URI if a matching wiki page exists
        file_wiki_page = f"files/{r.chunk.file_path}.md"
        if (wiki_path / file_wiki_page).exists():
            entry["wiki_resource"] = build_wiki_resource_uri(wiki_path, file_wiki_page)
        sources.append(entry)

    result: dict[str, Any] = {
        "question": question,
        "answer": answer,
        "sources": sources,
    }
    if agentic_metadata is not None:
        result["agentic_rag"] = agentic_metadata

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

    logger.info("Generated answer with %s sources", len(search_results))
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

    if not wiki_path.exists():
        entity_reg = wiki_path / "entity_registry.json"
        index_status_file = wiki_path / "index_status.json"
        if entity_reg.exists() or index_status_file.exists():
            from local_deepwiki.generators.lazy_generator import get_lazy_generator

            generator = get_lazy_generator(wiki_path)
            structure = generator.get_virtual_structure()
            return make_tool_text_content("read_wiki_structure", structure)
        raise path_not_found_error(str(wiki_path), "wiki")

    # Check for toc.json (numbered hierarchical structure)
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        try:
            toc_content = await asyncio.to_thread(toc_path.read_text)
            toc_data = json.loads(toc_content)
            structure_data = (
                toc_data if isinstance(toc_data, dict) else {"pages": toc_data}
            )
            return make_tool_text_content("read_wiki_structure", structure_data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"toc.json exists but could not be read, falling back to dynamic generation: {e}"
            )

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
            logger.debug("Could not read title from %s: %s", md_file, e)
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
        entity_reg = wiki_path / "entity_registry.json"
        index_status_file = wiki_path / "index_status.json"
        if entity_reg.exists() or index_status_file.exists():
            from local_deepwiki.generators.lazy_generator import get_lazy_generator

            generator = get_lazy_generator(wiki_path)
            page_relative = str(page_path.relative_to(wiki_path))
            content = await generator.get_page(page_relative)
            return [TextContent(type="text", text=content)]
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

    logger.info("Code search in %s: %s...", repo_path, query[:50])
    logger.debug(
        f"Search limit: {limit}, language: {language}, type: {chunk_type}, "
        f"path: {path_pattern}, fuzzy: {use_fuzzy}"
    )

    _index_status, _wiki_path, config = await _load_index_status(repo_path)

    # Create vector store
    vector_store = _create_vector_store(repo_path, config)

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

    logger.info("Search returned %s results", len(results))
    if not results:
        return make_tool_text_content(
            "search_code",
            {
                "message": "No results found.",
                "total_results": 0,
                "results": [],
            },
        )

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

    return make_tool_text_content(
        "search_code",
        {
            "total_results": len(output),
            "results": output,
        },
    )


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

    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    # Determine and validate output path
    raw_output = validated.output_path
    if raw_output:
        resolved_output = _validate_export_path(Path(raw_output), wiki_path)
    else:
        resolved_output = _validate_export_path(
            wiki_path.parent / f"{wiki_path.name}_html", wiki_path
        )

    # Get subject ID for audit logging
    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    # Audit: Log export operation started
    actual_output = resolved_output
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

    result = export_to_html(wiki_path, resolved_output)

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

    return make_tool_text_content("export_wiki_html", response)


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
    single_file = validated.single_file

    if not wiki_path.exists():
        raise path_not_found_error(str(wiki_path), "wiki")

    # Determine and validate output path
    raw_output = validated.output_path
    if raw_output:
        resolved_output = _validate_export_path(Path(raw_output), wiki_path)
    else:
        # Determine default path based on single_file mode
        if single_file:
            default_path = wiki_path.parent / f"{wiki_path.name}.pdf"
        else:
            default_path = wiki_path.parent / f"{wiki_path.name}_pdfs"
        resolved_output = _validate_export_path(default_path, wiki_path)

    # Get subject ID for audit logging
    subject = controller.get_current_subject()
    subject_id = subject.identifier if subject else "anonymous"
    audit_logger = get_audit_logger()
    start_time = time.time()

    actual_output = resolved_output

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

    result = export_to_pdf(wiki_path, resolved_output, single_file=single_file)

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

    return make_tool_text_content("export_wiki_pdf", response)
