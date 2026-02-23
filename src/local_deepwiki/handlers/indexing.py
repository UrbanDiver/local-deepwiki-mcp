"""Indexing tool handler: repository indexing pipeline with progress tracking."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.config import get_config
from local_deepwiki.core.audit import get_audit_logger
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.errors import ValidationError, path_not_found_error
from local_deepwiki.generators.wiki import generate_wiki
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._progress import create_progress_notifier
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import IndexRepositoryArgs, WikiStructure
from local_deepwiki.progress import OperationType, ProgressPhase, get_progress_registry
from local_deepwiki.security import (
    Permission,
    get_access_controller,
    get_repository_access_controller,
)
from local_deepwiki.validation import validate_index_parameters, validate_languages_list

logger = get_logger(__name__)


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
        "Indexing repository: %s (%s bytes, %s files)",
        repo_path,
        f"{total_size:,}",
        f"{file_count:,}",
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


async def _notify(
    notifier: Any,
    current: int,
    phase: ProgressPhase,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Send a progress notification if a notifier is available."""
    if notifier is None:
        return
    await notifier.update(
        current=current, phase=phase, message=message, metadata=metadata
    )


def _generate_wiki_lazy(
    indexer: RepositoryIndexer,
    status: Any,
    config: Any,
) -> WikiStructure:
    """Lazy mode: build entity registry only, defer all page generation."""
    from local_deepwiki.generators.crosslinks import build_entity_registry_from_store
    from local_deepwiki.generators.wiki.files import filter_significant_files

    significant = filter_significant_files(status.files, config.wiki.max_file_docs)
    sig_paths = {f.path for f in significant}
    entity_reg = build_entity_registry_from_store(
        indexer.vector_store.get_all_chunks(), sig_paths
    )
    entity_reg.save(indexer.wiki_path / "entity_registry.json")

    return WikiStructure(root=str(indexer.wiki_path), pages=[])


async def _generate_wiki_hybrid(
    repo_path: Path,
    indexer: RepositoryIndexer,
    status: Any,
    config: Any,
    llm_provider: str | None,
    sync_progress_callback: Any,
    full_rebuild: bool,
) -> WikiStructure:
    """Hybrid mode: generate eager pages, then build full entity registry."""
    from local_deepwiki.generators.crosslinks import build_entity_registry_from_store
    from local_deepwiki.generators.wiki.files import filter_significant_files

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

    significant = filter_significant_files(status.files, config.wiki.max_file_docs)
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
            from local_deepwiki.generators.lazy_generator import get_lazy_generator

            lazy_gen = get_lazy_generator(indexer.wiki_path, config)
            lazy_gen.kickstart_drain()

    return wiki_structure


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
        await _notify(
            notifier,
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

        await _notify(
            notifier,
            current=2,
            phase=ProgressPhase.PARSING,
            message="Parsing source files...",
        )

        status = await indexer.index(
            full_rebuild=full_rebuild,
            progress_callback=sync_progress_callback,
        )

        # LanceDB 0.26: compact all dataset versions into a single stable
        # snapshot so concurrent wiki-generation reads don't collide with
        # deferred fragment compaction.
        indexer.vector_store.stabilize()

        await _notify(
            notifier,
            current=4,
            phase=ProgressPhase.STORING,
            message=f"Indexed {status.total_files} files, {status.total_chunks} chunks",
            metadata={
                "files_processed": status.total_files,
                "total_files": status.total_files,
                "chunks_created": status.total_chunks,
            },
        )

        await _notify(
            notifier,
            current=5,
            phase=ProgressPhase.WIKI_GENERATION,
            message="Generating wiki documentation...",
        )

        from local_deepwiki.config import GenerationMode

        gen_mode = config.wiki.generation_mode

        match gen_mode:
            case GenerationMode.LAZY:
                wiki_structure = _generate_wiki_lazy(indexer, status, config)

            case GenerationMode.HYBRID:
                wiki_structure = await _generate_wiki_hybrid(
                    repo_path,
                    indexer,
                    status,
                    config,
                    llm_provider,
                    sync_progress_callback,
                    full_rebuild,
                )

            case _:
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

        await _notify(
            notifier,
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
        if notifier:
            await notifier.flush()

        registry.complete_operation(operation_id, record_timing=True)

    except Exception:  # noqa: BLE001 — handler boundary: ensure operation is marked complete before re-raising
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
    except Exception as e:  # noqa: BLE001 — handler boundary: audit log failure before re-raising
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
        "Indexing complete: %d files, %d chunks, %d wiki pages",
        status.total_files,
        status.total_chunks,
        len(wiki_structure.pages),
    )

    # Record in session state so downstream tools know this repo is indexed
    from local_deepwiki.handlers.session_state import record_index

    record_index(str(repo_path), str(indexer.wiki_path))

    return make_tool_text_content("index_repository", result)
