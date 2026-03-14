"""File documentation generation for wiki."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from local_deepwiki.config import Config
from local_deepwiki.core.git_utils import get_repo_info
from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.analysis.api_docs import get_file_api_docs
from local_deepwiki.generators.analysis.callgraph import (
    get_file_call_graph,
    get_file_callers,
)
from local_deepwiki.generators.context_builder import (
    build_file_context,
    format_context_for_llm,
)
from local_deepwiki.generators.crosslinks import EntityRegistry
from local_deepwiki.generators.diagrams import generate_class_diagram
from local_deepwiki.generators.examples.orchestrator import get_file_examples
from local_deepwiki.generators.wiki.source_formatter import (
    _ChunkMaps,
    _append_unused_chunks,
    _build_chunk_maps,
    _create_source_details,
    _extract_entity_from_heading,
    _find_insertion_point,
    _find_matching_chunk,
    _generate_blame_section,
    _get_syntax_lang,
    _inject_inline_source_code,
    _prioritize_chunks,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    CodeChunk,
    FileInfo,
    IndexStatus,
    ProgressCallback,
    WikiPage,
)
from local_deepwiki.providers.base import LLMProvider

if TYPE_CHECKING:
    from local_deepwiki.generators.progress_tracker import GenerationProgress
    from local_deepwiki.generators.wiki.status import WikiStatusManager

logger = get_logger(__name__)

# Re-export extracted helpers so existing imports continue to work
__all__ = [
    # Underscore-prefixed names exposed for test access only
    "_ChunkMaps",
    "_append_unused_chunks",
    "_build_chunk_maps",
    "_create_source_details",
    "_extract_entity_from_heading",
    "_find_insertion_point",
    "_find_matching_chunk",
    "_generate_blame_section",
    "_get_syntax_lang",
    "_inject_inline_source_code",
    "_prioritize_chunks",
]


def _adaptive_context_limits(
    chunk_count: int,
    max_chunk_content_chars: int,
    max_chunks_per_file: int,
) -> tuple[int, int]:
    """Scale context limits based on file complexity.

    Simple files (few chunks) get smaller prompts for faster LLM generation.
    Complex files get the full configured limits.

    Args:
        chunk_count: Number of chunks in the file.
        max_chunk_content_chars: Configured max chars.
        max_chunks_per_file: Configured max chunks.

    Returns:
        Tuple of (effective_chars, effective_chunks).
    """
    if chunk_count <= 5:
        # Simple file: use ~1/3 of limits
        return max(500, max_chunk_content_chars // 3), min(chunk_count, 10)
    if chunk_count <= 15:
        # Medium file: use ~2/3 of limits
        return max(500, max_chunk_content_chars * 2 // 3), min(max_chunks_per_file, 30)
    # Complex file: full limits
    return max_chunk_content_chars, max_chunks_per_file


async def _gather_file_context(
    file_info: FileInfo,
    index_status: IndexStatus,
    vector_store: VectorStore,
    max_chunk_content_chars: int = 15000,
    max_chunks_per_file: int = 60,
) -> tuple[list[CodeChunk], str, str] | None:
    """Collect chunks, imports, and related context for the file.

    Args:
        file_info: File status information.
        index_status: Index status with repo information.
        vector_store: Vector store with indexed code.
        max_chunk_content_chars: Max characters of chunk content in LLM prompt.
        max_chunks_per_file: Max chunks to include in LLM prompt context.

    Returns:
        Tuple of (chunks_list, context_text, rich_context_text) or None if no content.
    """
    # Get all chunks for this file using direct lookup (efficient scalar index)
    file_chunks = await vector_store.get_chunks_by_file(file_info.path)

    if not file_chunks:
        return None  # No content to document

    # Scale context limits based on file complexity
    effective_chars, effective_chunks = _adaptive_context_limits(
        len(file_chunks), max_chunk_content_chars, max_chunks_per_file
    )

    # Prioritize chunks by documentation value: functions/methods first,
    # then classes, then module summaries, then imports
    prioritized = _prioritize_chunks(file_chunks, effective_chunks)

    # Build context from prioritized chunks
    context_parts = []
    for chunk in prioritized:
        context_parts.append(
            f"Type: {chunk.chunk_type.value}\n"
            f"Name: {chunk.name}\n"
            f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"```\n{chunk.content[:effective_chars]}\n```"
        )

    context = "\n\n".join(context_parts)

    # Build rich context with imports, callers, and related files
    rich_context = await build_file_context(
        file_path=file_info.path,
        chunks=file_chunks,
        repo_path=Path(index_status.repo_path),
        vector_store=vector_store,
    )
    rich_context_text = format_context_for_llm(rich_context)

    return file_chunks, context, rich_context_text


def _build_llm_prompt(
    file_info: FileInfo,
    context: str,
    rich_context_text: str,
) -> str:
    """Construct the LLM prompt with all context.

    Args:
        file_info: File status information.
        context: Code context text.
        rich_context_text: Rich context with imports and callers.

    Returns:
        The formatted LLM prompt string.
    """
    return f"""Generate documentation for the file '{file_info.path}' based on the code and context provided.

Language: {file_info.language}
Total code chunks: {file_info.chunk_count}

{rich_context_text}
## Code Contents
{context}

Generate documentation that includes:
1. **File Overview**: Purpose, responsibility, and design rationale of this file
2. **Key Concepts**: Important abstractions, patterns, or algorithms and WHY they were chosen
3. **Integration**: How this file fits into the larger codebase (based on imports and callers)
4. **Design Notes**: Trade-offs, edge cases handled, or non-obvious implementation choices

Do NOT include these sections — they are auto-generated from the AST and will be appended:
- Classes or Functions reference (auto-generated as "API Reference")
- Class diagrams (auto-generated from AST)
- Usage examples (auto-extracted from test files)
- Call graphs (auto-generated from static analysis)

CRITICAL CONSTRAINTS:
- ONLY describe components that appear in the code above
- Do NOT invent additional methods or parameters not shown
- Write class names as plain text (e.g., "The WikiGenerator class") for cross-linking
- Use the dependency and caller information to explain integration, but don't fabricate details
- Focus on the WHY (design rationale) not just the WHAT (listing classes/functions)
- Only use backticks for actual code snippets

Format as markdown with clear sections."""


async def _generate_and_format_doc(
    prompt: str,
    llm: LLMProvider,
    system_prompt: str,
) -> str:
    """Call LLM and format the response.

    Args:
        prompt: The LLM prompt.
        llm: LLM provider for generation.
        system_prompt: System prompt for LLM.

    Returns:
        The formatted documentation content.
    """
    content = await llm.generate(prompt, system_prompt=system_prompt)

    # Safety-net: strip LLM-generated sections that duplicate AST enrichments.
    # Even though the prompt says not to generate these, LLMs sometimes do anyway.
    content = _strip_enrichment_duplicates(content)

    return content


# Patterns matching LLM-generated sections that duplicate AST enrichments.
# Each pattern matches from the section heading to the next heading or end.
_DUPLICATE_SECTION_PATTERNS: list[re.Pattern[str]] = [
    # Class diagrams (we generate our own from AST)
    re.compile(
        r"\n*##\s*Class\s*Diagram\s*\n+```mermaid\s*\n+classDiagram.*?```",
        re.DOTALL | re.IGNORECASE,
    ),
    # Classes section (duplicates API Reference)
    re.compile(
        r"\n*##\s*Classes\s*\n(?:(?!^##\s).)*",
        re.DOTALL | re.MULTILINE,
    ),
    # Functions section (duplicates API Reference)
    re.compile(
        r"\n*##\s*Functions\s*\n(?:(?!^##\s).)*",
        re.DOTALL | re.MULTILINE,
    ),
    # Usage Examples section (duplicates test-extracted examples)
    re.compile(
        r"\n*##\s*Usage\s+Examples?\s*\n(?:(?!^##\s).)*",
        re.DOTALL | re.MULTILINE,
    ),
    # API Reference (duplicates our AST-generated API Reference)
    re.compile(
        r"\n*##\s*API\s+Reference\s*\n(?:(?!^##\s).)*",
        re.DOTALL | re.MULTILINE,
    ),
]


def _strip_enrichment_duplicates(content: str) -> str:
    """Remove LLM-generated sections that duplicate AST enrichments.

    The prompt instructs the LLM not to generate Classes, Functions,
    Usage Examples, or Class Diagram sections, but LLMs sometimes
    ignore instructions. This safety net strips those sections so
    only the authoritative AST-derived versions appear.
    """
    for pattern in _DUPLICATE_SECTION_PATTERNS:
        content = pattern.sub("", content)
    return content


def _add_api_reference_section(abs_file_path: Path) -> str:
    """Generate API reference section with type signatures."""
    if not abs_file_path.exists():
        return ""
    api_docs = get_file_api_docs(abs_file_path)
    return ("\n\n## API Reference\n\n" + api_docs) if api_docs else ""


def _add_class_diagram_section(all_file_chunks: list[CodeChunk]) -> str:
    """Generate class diagram if file has classes."""
    class_diagram = generate_class_diagram(all_file_chunks)
    return ("\n\n## Class Diagram\n\n" + class_diagram) if class_diagram else ""


def _add_call_graph_section(abs_file_path: Path, repo_path: Path) -> str:
    """Generate call graph diagram and used-by information."""
    if not abs_file_path.exists():
        return ""

    parts: list[str] = []

    call_graph = get_file_call_graph(abs_file_path, repo_path)
    if call_graph:
        parts.append("\n\n## Call Graph\n\n```mermaid\n" + call_graph + "\n```")

    callers_map = get_file_callers(abs_file_path, repo_path)
    if callers_map:
        used_by_lines = [
            "## Used By",
            "",
            "Functions and methods in this file and their callers:",
            "",
        ]
        for callee in sorted(callers_map.keys()):
            callers = callers_map[callee]
            if callers:
                caller_list = ", ".join(f"`{c}`" for c in sorted(callers))
                used_by_lines.append(f"- **`{callee}`**: called by {caller_list}")
        if len(used_by_lines) > 4:  # More than just the header
            parts.append("\n\n" + "\n".join(used_by_lines))

    return "".join(parts)


def _add_examples_section(
    abs_file_path: Path,
    repo_path: Path,
    all_file_chunks: list[CodeChunk],
) -> str:
    """Add usage examples from test files."""
    entity_names = [
        chunk.name for chunk in all_file_chunks if chunk.name and len(chunk.name) > 2
    ]
    if not entity_names:
        return ""
    examples_md = get_file_examples(
        source_file=abs_file_path,
        repo_root=repo_path,
        entity_names=entity_names,
        max_examples=5,
    )
    return ("\n\n" + examples_md) if examples_md else ""


def _add_blame_section(
    repo_path: Path,
    file_path: str,
    all_file_chunks: list[CodeChunk],
) -> str:
    """Add git blame "Last Modified" section."""
    blame_section = _generate_blame_section(
        repo_path=repo_path,
        file_path=file_path,
        chunks=all_file_chunks,
    )
    return ("\n\n" + blame_section) if blame_section else ""


async def _generate_file_enrichments(
    content: str,
    abs_file_path: Path,
    repo_path: Path,
    file_path: str,
    all_file_chunks: list[CodeChunk],
) -> str:
    """Generate diagrams, call graphs, examples, and blame info concurrently.

    Each enrichment is independent and involves file I/O or subprocess calls,
    so they run in parallel via ``asyncio.to_thread``.

    Args:
        content: The base documentation content.
        abs_file_path: Absolute path to the source file.
        repo_path: Path to the repository root.
        file_path: Relative path to the source file.
        all_file_chunks: All code chunks from the file.

    Returns:
        The enriched documentation content.
    """
    results = await asyncio.gather(
        asyncio.to_thread(_add_api_reference_section, abs_file_path),
        asyncio.to_thread(_add_class_diagram_section, all_file_chunks),
        asyncio.to_thread(_add_call_graph_section, abs_file_path, repo_path),
        asyncio.to_thread(
            _add_examples_section, abs_file_path, repo_path, all_file_chunks
        ),
        asyncio.to_thread(_add_blame_section, repo_path, file_path, all_file_chunks),
    )
    return content + "".join(results)


async def generate_single_file_doc(
    file_info: FileInfo,
    ctx: FileDocContext,
) -> tuple[WikiPage | None, bool]:
    """Generate documentation for a single source file.

    Coordinates the documentation generation pipeline:
    1. Check if regeneration is needed
    2. Gather file context (chunks, imports, related context)
    3. Build LLM prompt with all context
    4. Generate and format documentation via LLM
    5. Add enrichments (diagrams, call graphs, examples, blame)
    6. Inject inline source code and register entities

    Args:
        file_info: File status information.
        ctx: Bundled context with all generation dependencies.

    Returns:
        Tuple of (WikiPage or None, was_skipped).
        Returns (None, False) if file should be skipped entirely.
        Returns (page, True) if existing page was reused.
        Returns (page, False) if new page was generated.
    """
    file_path = Path(file_info.path)
    repo_path = Path(ctx.index_status.repo_path)

    # Create nested path structure: files/module/filename.md
    parts = file_path.parts
    if len(parts) > 1:
        wiki_path = f"files/{'/'.join(parts[:-1])}/{file_path.stem}.md"
    else:
        wiki_path = f"files/{file_path.stem}.md"

    source_files = [file_info.path]

    # Check if this file page needs regeneration
    if not ctx.full_rebuild and not ctx.status_manager.needs_regeneration(
        wiki_path, source_files
    ):
        existing_page = await ctx.status_manager.load_existing_page(wiki_path)
        if existing_page is not None:
            # Still need to register entities for cross-linking
            all_file_chunks = await ctx.vector_store.get_chunks_by_file(file_info.path)
            ctx.entity_registry.register_from_chunks(all_file_chunks, wiki_path)
            ctx.status_manager.record_page_status(existing_page, source_files)
            return existing_page, True  # Skipped (reused existing)

    # Step 1: Gather file context (chunks, imports, related context)
    context_result = await _gather_file_context(
        file_info=file_info,
        index_status=ctx.index_status,
        vector_store=ctx.vector_store,
        max_chunk_content_chars=ctx.config.wiki.max_chunk_content_chars,
        max_chunks_per_file=ctx.config.wiki.max_chunks_per_file,
    )

    if context_result is None:
        return None, False  # No content to document

    file_chunks, context, rich_context_text = context_result

    # Step 2: Build the LLM prompt
    prompt = _build_llm_prompt(
        file_info=file_info,
        context=context,
        rich_context_text=rich_context_text,
    )

    # Step 3: Generate and format the documentation
    content = await _generate_and_format_doc(
        prompt=prompt,
        llm=ctx.llm,
        system_prompt=ctx.system_prompt,
    )

    # Step 4: Generate enrichments (diagrams, call graphs, examples, blame)
    abs_file_path = repo_path / file_info.path
    content = await _generate_file_enrichments(
        content=content,
        abs_file_path=abs_file_path,
        repo_path=repo_path,
        file_path=file_info.path,
        all_file_chunks=file_chunks,
    )

    # Inject inline source code after each function/class in API Reference
    lang_str = file_info.language.value if file_info.language else None
    repo_info = get_repo_info(repo_path)
    content = _inject_inline_source_code(content, file_chunks, lang_str, repo_info)

    # Register entities for cross-linking
    ctx.entity_registry.register_from_chunks(file_chunks, wiki_path)

    page = WikiPage(
        path=wiki_path,
        title=f"{file_path.name}",
        content=content,
        generated_at=time.time(),
    )
    ctx.status_manager.record_page_status(page, source_files)
    return page, False  # Generated new


# Type alias for async write callback
WriteCallback: TypeAlias = Callable[[WikiPage], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class FileDocContext:
    """Bundled context for file documentation generation.

    Groups the parameters shared between generate_file_docs and
    generate_single_file_doc to reduce parameter counts.
    """

    index_status: IndexStatus
    vector_store: VectorStore
    llm: LLMProvider
    system_prompt: str
    status_manager: "WikiStatusManager"
    entity_registry: EntityRegistry
    config: Config
    full_rebuild: bool = False


def _is_test_file(path: str) -> bool:
    """Check if a file is in a test directory.

    Delegates to :func:`local_deepwiki.core.path_utils.is_test_file`
    with ``check_filename=False`` (directory membership only).
    """
    return is_test_file(path, check_filename=False)


def filter_significant_files(files: list[FileInfo], max_files: int) -> list[FileInfo]:
    """Filter and limit files for documentation generation.

    Args:
        files: All indexed files.
        max_files: Maximum files to document (0 = unlimited).

    Returns:
        Filtered and prioritized list of files.
    """
    # Filter: skip __init__.py, test files, and files with minimal content
    significant = [
        f
        for f in files
        if not f.path.endswith("__init__.py")
        and not _is_test_file(f.path)
        and f.chunk_count >= 2
    ]

    # Limit and prioritize by complexity (chunk count)
    if max_files > 0 and len(significant) > max_files:
        significant = sorted(significant, key=lambda x: x.chunk_count, reverse=True)[
            :max_files
        ]

    return significant


def _create_files_index_page(
    pages: list[WikiPage],
    significant_files: list[FileInfo],
    status_manager: "WikiStatusManager",
) -> WikiPage:
    """Create the files index page.

    Args:
        pages: All generated file pages.
        significant_files: Files that were documented.
        status_manager: Status manager for recording.

    Returns:
        Files index WikiPage.
    """
    all_file_paths = [f.path for f in significant_files]
    files_index = WikiPage(
        path="files/index.md",
        title="Source Files",
        content=_generate_files_index(pages),
        generated_at=time.time(),
    )
    status_manager.record_page_status(files_index, all_file_paths)
    return files_index


async def generate_file_docs(
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    *,
    status_manager: "WikiStatusManager",
    entity_registry: EntityRegistry,
    config: Config,
    progress_callback: ProgressCallback | None = None,
    full_rebuild: bool = False,
    write_callback: WriteCallback | None = None,
    generation_progress: "GenerationProgress | None" = None,
    max_files: int | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[list[WikiPage], int, int]:
    """Generate documentation for individual source files.

    Uses parallel LLM calls for faster generation, controlled by
    config.wiki.max_concurrent_llm_calls. Pages are written to disk
    immediately as they complete if write_callback is provided.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with indexed code.
        llm: LLM provider for generation.
        system_prompt: System prompt for LLM.
        status_manager: Wiki status manager for incremental updates.
        entity_registry: Entity registry for cross-linking.
        config: Configuration.
        progress_callback: Optional progress callback.
        full_rebuild: If True, regenerate all pages.
        write_callback: Optional async callback to write pages immediately as they complete.
        generation_progress: Optional live progress tracker for status updates.

    Returns:
        Tuple of (pages list, generated count, skipped count).
    """
    significant_files = filter_significant_files(
        index_status.files, config.wiki.max_file_docs
    )
    if not significant_files:
        return [], 0, 0
    if max_files is not None and max_files < len(significant_files):
        significant_files = significant_files[:max_files]

    ctx = FileDocContext(
        index_status=index_status,
        vector_store=vector_store,
        llm=llm,
        system_prompt=system_prompt,
        status_manager=status_manager,
        entity_registry=entity_registry,
        config=config,
        full_rebuild=full_rebuild,
    )

    # Use semaphore to limit concurrent LLM calls (provider-aware)
    max_concurrent = config.effective_llm_concurrency
    semaphore = semaphore or asyncio.Semaphore(max_concurrent)
    logger.info(
        "Generating file docs for %d files (max %d concurrent)",
        len(significant_files),
        max_concurrent,
    )

    if generation_progress:
        generation_progress.start_phase("file_docs", total=len(significant_files))

    async def generate_with_semaphore(
        file_info: FileInfo,
    ) -> tuple[FileInfo, WikiPage | None, bool]:
        """Generate doc for a file, returning file_info for tracking."""
        async with semaphore:
            logger.debug("Generating doc for %s", file_info.path)
            page, was_skipped = await generate_single_file_doc(
                file_info=file_info,
                ctx=ctx,
            )
            return file_info, page, was_skipped

    # Create and process tasks
    tasks = [asyncio.create_task(generate_with_semaphore(f)) for f in significant_files]
    pages: list[WikiPage] = []
    pages_generated = 0
    pages_skipped = 0
    pages_failed = 0

    for coro in asyncio.as_completed(tasks):
        try:
            file_info, page, was_skipped = await coro

            if page is not None:
                pages.append(page)
                if was_skipped:
                    pages_skipped += 1
                else:
                    pages_generated += 1

                if write_callback:
                    await write_callback(page)

                if progress_callback:
                    progress_callback(
                        f"Generated {file_info.path}", len(pages), len(tasks)
                    )

            if generation_progress:
                generation_progress.complete_file(file_info.path)

        except Exception as e:  # noqa: BLE001 — file generation isolation: one file failure must not abort entire wiki build
            logger.error("Error generating file doc: %s", e)
            pages_failed += 1
            if generation_progress:
                generation_progress.complete_file()

    # Create files index
    if pages:
        files_index = _create_files_index_page(pages, significant_files, status_manager)
        pages.insert(0, files_index)

    if generation_progress:
        generation_progress.complete_phase()

    log_msg = (
        f"File docs complete: {pages_generated} generated, {pages_skipped} skipped"
    )
    if pages_failed:
        log_msg += f", {pages_failed} failed"
    logger.info(log_msg)
    if pages_failed:
        logger.warning(
            "%d file docs failed to generate out of %d total",
            pages_failed,
            len(tasks),
        )
    return pages, pages_generated, pages_skipped


def _generate_files_index(file_pages: list[WikiPage]) -> str:
    """Generate index page for file documentation.

    Args:
        file_pages: List of file wiki pages.

    Returns:
        Markdown content for files index.
    """
    lines = [
        "# Source Files\n",
        "Detailed documentation for individual source files.\n",
    ]

    # Group by directory
    by_dir: dict[str, list[WikiPage]] = {}
    for page in file_pages:
        if page.path == "files/index.md":
            continue
        parts = Path(page.path).parts
        if len(parts) > 2:
            dir_name = parts[1]  # files/DIR/file.md -> DIR
        else:
            dir_name = "root"
        by_dir.setdefault(dir_name, []).append(page)

    for dir_name, dir_pages in sorted(by_dir.items()):
        lines.append(f"\n## {dir_name}\n")
        for page in sorted(dir_pages, key=lambda p: p.title):
            # Make relative link from files/index.md
            rel_path = page.path.replace("files/", "")
            lines.append(f"- [{page.title}]({rel_path})")

    return "\n".join(lines)
