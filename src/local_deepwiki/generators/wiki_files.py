"""File documentation generation for wiki."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from local_deepwiki.config import Config
from local_deepwiki.core.git_utils import (
    GitRepoInfo,
    build_source_url,
    format_blame_date,
    get_file_entity_blame,
    get_repo_info,
)
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.api_docs import get_file_api_docs
from local_deepwiki.generators.callgraph import get_file_call_graph, get_file_callers
from local_deepwiki.generators.context_builder import build_file_context, format_context_for_llm
from local_deepwiki.generators.crosslinks import EntityRegistry
from local_deepwiki.generators.diagrams import generate_class_diagram
from local_deepwiki.generators.test_examples import get_file_examples
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    FileInfo,
    IndexStatus,
    ProgressCallback,
    WikiPage,
)
from local_deepwiki.providers.base import LLMProvider

if TYPE_CHECKING:
    from local_deepwiki.generators.progress_tracker import GenerationProgress
    from local_deepwiki.generators.wiki_status import WikiStatusManager

logger = get_logger(__name__)


def _get_syntax_lang(language: str | None) -> str:
    """Get syntax highlighting language string.

    Args:
        language: Programming language name.

    Returns:
        Language string for markdown code blocks.
    """
    lang_map = {
        "python": "python",
        "javascript": "javascript",
        "typescript": "typescript",
        "tsx": "tsx",
        "go": "go",
        "rust": "rust",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "swift": "swift",
        "ruby": "ruby",
        "php": "php",
        "kotlin": "kotlin",
        "csharp": "csharp",
    }
    return lang_map.get(language or "", "")


def _create_source_details(
    chunk: CodeChunk, syntax_lang: str, github_url: str | None = None
) -> str:
    """Create a collapsible source code block for a chunk.

    Args:
        chunk: The code chunk.
        syntax_lang: Syntax highlighting language.
        github_url: Optional GitHub URL to link to source.

    Returns:
        Markdown details block with source code.
    """
    if github_url:
        summary = f'View Source (lines {chunk.start_line}-{chunk.end_line}) | <a href="{github_url}">GitHub</a>'
    else:
        summary = f"View Source (lines {chunk.start_line}-{chunk.end_line})"

    return f"""<details>
<summary>{summary}</summary>

```{syntax_lang}
{chunk.content}
```

</details>
"""


@dataclass
class _ChunkMaps:
    """Maps for looking up chunks by name."""

    chunk_map: dict[str, CodeChunk]
    class_map: dict[str, CodeChunk]
    all_chunk_ids: set[str]


def _build_chunk_maps(chunks: list[CodeChunk]) -> _ChunkMaps:
    """Build lookup maps for chunks by name.

    Args:
        chunks: List of code chunks.

    Returns:
        ChunkMaps with name-to-chunk mappings.
    """
    chunk_map: dict[str, CodeChunk] = {}
    class_map: dict[str, CodeChunk] = {}
    all_chunk_ids: set[str] = set()

    for chunk in chunks:
        if chunk.name and chunk.chunk_type in (
            ChunkType.CLASS,
            ChunkType.FUNCTION,
            ChunkType.METHOD,
        ):
            all_chunk_ids.add(chunk.id)
            chunk_map[chunk.name] = chunk
            if chunk.parent_name:
                qualified_name = f"{chunk.parent_name}.{chunk.name}"
                chunk_map[qualified_name] = chunk
            if chunk.chunk_type == ChunkType.CLASS:
                class_map[chunk.name] = chunk

    return _ChunkMaps(chunk_map, class_map, all_chunk_ids)


def _extract_entity_from_heading(line: str) -> tuple[str | None, bool]:
    """Extract entity name from a markdown heading.

    Args:
        line: Heading line like "#### `name`" or "### class `name`".

    Returns:
        Tuple of (entity_name, is_class_heading).
    """
    start = line.find("`") + 1
    end = line.find("`", start)
    if start <= 0 or end <= start:
        return None, False

    entity_name = line[start:end]

    # Normalize: strip signature
    if "(" in entity_name:
        entity_name = entity_name.split("(")[0]

    # Check if class heading
    is_class = entity_name.startswith("class ")
    if is_class:
        entity_name = entity_name[6:].strip()

    return entity_name, is_class


def _find_matching_chunk(
    entity_name: str,
    current_class: str | None,
    maps: _ChunkMaps,
) -> CodeChunk | None:
    """Find the chunk that matches an entity name.

    Args:
        entity_name: Name of the entity to find.
        current_class: Current class context, if any.
        maps: Chunk lookup maps.

    Returns:
        Matching chunk or None.
    """
    matched_chunk: CodeChunk | None = None

    # Try qualified name first for methods
    if current_class and entity_name != current_class:
        qualified_name = f"{current_class}.{entity_name}"
        matched_chunk = maps.chunk_map.get(qualified_name)

    # Try simple name
    if matched_chunk is None:
        candidate = maps.chunk_map.get(entity_name)
        if candidate is not None:
            if candidate.parent_name is None or candidate.parent_name == current_class:
                matched_chunk = candidate

    # Fallback to class source for unmatched methods
    if matched_chunk is None and current_class and entity_name != current_class:
        matched_chunk = maps.class_map.get(current_class)

    return matched_chunk


def _find_insertion_point(
    lines: list[str],
    start_idx: int,
    result_lines: list[str],
    chunk: CodeChunk,
    syntax_lang: str,
    chunk_url: str | None,
) -> int:
    """Find where to insert source code and add it.

    Args:
        lines: All content lines.
        start_idx: Starting line index.
        result_lines: Result lines to append to.
        chunk: Chunk to insert source for.
        syntax_lang: Syntax highlighting language.
        chunk_url: Optional GitHub URL.

    Returns:
        New line index to continue from.
    """
    j = start_idx
    found_returns = False

    while j < len(lines):
        next_line = lines[j]

        # Stop at next heading of same or higher level
        if next_line.startswith(("#### ", "### ", "## ")):
            if not found_returns:
                result_lines.append("")
                result_lines.append(
                    _create_source_details(chunk, syntax_lang, chunk_url)
                )
            return j - 1

        # Track if we found Returns
        if next_line.startswith("**Returns:**"):
            found_returns = True
            result_lines.append(lines[j])
            j += 1
            # Skip blank lines after Returns
            while j < len(lines) and lines[j].strip() == "":
                result_lines.append(lines[j])
                j += 1
            # Insert source code here
            result_lines.append("")
            result_lines.append(_create_source_details(chunk, syntax_lang, chunk_url))
            return j - 1

        result_lines.append(lines[j])
        j += 1

    # Reached end of file
    if not found_returns:
        result_lines.append("")
        result_lines.append(_create_source_details(chunk, syntax_lang, chunk_url))
    return j - 1


def _append_unused_chunks(
    result_lines: list[str],
    chunks: list[CodeChunk],
    all_chunk_ids: set[str],
    used_chunks: set[str],
    syntax_lang: str,
    get_url: Callable[[CodeChunk], str | None],
) -> None:
    """Append unused chunks as additional source code section.

    Args:
        result_lines: Lines to append to.
        chunks: All chunks.
        all_chunk_ids: Set of all chunk IDs.
        used_chunks: Set of already-used chunk IDs.
        syntax_lang: Syntax highlighting language.
        get_url: Function to get GitHub URL for a chunk.
    """
    unused = [c for c in chunks if c.id in all_chunk_ids and c.id not in used_chunks]
    if not unused:
        return

    result_lines.append("")
    result_lines.append("## Additional Source Code")
    result_lines.append("")
    result_lines.append(
        "Source code for functions and methods not listed in the API Reference above."
    )
    result_lines.append("")

    for chunk in sorted(unused, key=lambda c: c.start_line):
        heading = "###" if chunk.chunk_type == ChunkType.CLASS else "####"
        result_lines.append(f"{heading} `{chunk.name}`")
        result_lines.append("")
        result_lines.append(_create_source_details(chunk, syntax_lang, get_url(chunk)))
        result_lines.append("")


def _inject_inline_source_code(
    content: str,
    chunks: list[CodeChunk],
    language: str | None,
    repo_info: GitRepoInfo | None = None,
) -> str:
    """Inject collapsible source code after each function/class in the API Reference.

    Args:
        content: The markdown content to process.
        chunks: List of code chunks from the file.
        language: Programming language for syntax highlighting.
        repo_info: Optional git repo info for GitHub links.

    Returns:
        Content with inline source code blocks injected.
    """
    maps = _build_chunk_maps(chunks)
    if not maps.chunk_map:
        return content

    syntax_lang = _get_syntax_lang(language)
    used_chunks: set[str] = set()

    def get_chunk_url(chunk: CodeChunk) -> str | None:
        if repo_info is None:
            return None
        return build_source_url(
            repo_info, chunk.file_path, chunk.start_line, chunk.end_line
        )

    lines = content.split("\n")
    result_lines: list[str] = []
    current_class: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]
        result_lines.append(line)

        # Track class context
        if line.startswith("### class `"):
            entity, _ = _extract_entity_from_heading(line)
            if entity:
                current_class = entity

        # Look for API Reference headings
        if line.startswith(("#### `", "### `", "### class `")):
            entity_name, is_class = _extract_entity_from_heading(line)
            if entity_name:
                if is_class:
                    current_class = entity_name

                matched_chunk = _find_matching_chunk(entity_name, current_class, maps)
                if matched_chunk is not None:
                    used_chunks.add(matched_chunk.id)
                    i = _find_insertion_point(
                        lines,
                        i + 1,
                        result_lines,
                        matched_chunk,
                        syntax_lang,
                        get_chunk_url(matched_chunk),
                    )

        i += 1

    _append_unused_chunks(
        result_lines,
        chunks,
        maps.all_chunk_ids,
        used_chunks,
        syntax_lang,
        get_chunk_url,
    )

    return "\n".join(result_lines)


async def _gather_file_context(
    file_info: FileInfo,
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> tuple[list[CodeChunk], str, str] | None:
    """Collect chunks, imports, and related context for the file.

    Args:
        file_info: File status information.
        index_status: Index status with repo information.
        vector_store: Vector store with indexed code.

    Returns:
        Tuple of (chunks_list, context_text, rich_context_text) or None if no content.
    """
    # Get all chunks for this file using direct lookup (efficient scalar index)
    file_chunks = await vector_store.get_chunks_by_file(file_info.path)

    if not file_chunks:
        return None  # No content to document

    # Build context from chunks
    context_parts = []
    for chunk in file_chunks[:15]:  # Limit context size
        context_parts.append(
            f"Type: {chunk.chunk_type.value}\n"
            f"Name: {chunk.name}\n"
            f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"```\n{chunk.content[:600]}\n```"
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
1. **File Overview**: Purpose of this file based on the code shown and its dependencies
2. **Classes**: Document each class visible in the code with its purpose and key methods
3. **Functions**: Document each function with parameters and return values as shown
4. **Integration**: How this file fits into the larger codebase (based on imports and callers)
5. **Usage Examples**: Show how to use the components (based on their actual signatures)

CRITICAL CONSTRAINTS:
- ONLY document classes, methods, and functions that appear in the code above
- Do NOT invent additional methods or parameters not shown
- Do NOT fabricate usage examples with APIs not visible in the code
- Write class names as plain text (e.g., "The WikiGenerator class") for cross-linking
- Use the dependency and caller information to explain integration, but don't fabricate details
- Only use backticks for actual code snippets

Format as markdown with clear sections.
Do NOT include mermaid class diagrams - they will be auto-generated."""


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

    # Strip any LLM-generated class diagram sections (we add our own)
    content = re.sub(
        r"\n*##\s*Class\s*Diagram\s*\n+```mermaid\s*\n+classDiagram.*?```",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return content


def _generate_file_enrichments(
    content: str,
    abs_file_path: Path,
    repo_path: Path,
    file_path: str,
    all_file_chunks: list[CodeChunk],
) -> str:
    """Generate diagrams, call graphs, examples, and blame info.

    Args:
        content: The base documentation content.
        abs_file_path: Absolute path to the source file.
        repo_path: Path to the repository root.
        file_path: Relative path to the source file.
        all_file_chunks: All code chunks from the file.

    Returns:
        The enriched documentation content.
    """
    # Generate API reference section with type signatures
    if abs_file_path.exists():
        api_docs = get_file_api_docs(abs_file_path)
        if api_docs:
            content += "\n\n## API Reference\n\n" + api_docs

    # Generate class diagram if file has classes
    class_diagram = generate_class_diagram(all_file_chunks)
    if class_diagram:
        content += "\n\n## Class Diagram\n\n" + class_diagram

    # Generate call graph diagram and used-by information
    if abs_file_path.exists():
        call_graph = get_file_call_graph(abs_file_path, repo_path)
        if call_graph:
            content += "\n\n## Call Graph\n\n```mermaid\n" + call_graph + "\n```"

        # Add "Used by" section showing callers for each function
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
                content += "\n\n" + "\n".join(used_by_lines)

    # Add usage examples from test files
    entity_names = [
        chunk.name for chunk in all_file_chunks if chunk.name and len(chunk.name) > 2
    ]
    if entity_names:
        examples_md = get_file_examples(
            source_file=abs_file_path,
            repo_root=repo_path,
            entity_names=entity_names,
            max_examples=5,
        )
        if examples_md:
            content += "\n\n" + examples_md

    # Add git blame "Last Modified" section
    blame_section = _generate_blame_section(
        repo_path=repo_path,
        file_path=file_path,
        chunks=all_file_chunks,
    )
    if blame_section:
        content += "\n\n" + blame_section

    return content


async def generate_single_file_doc(
    file_info: FileInfo,
    index_status: IndexStatus,
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    status_manager: "WikiStatusManager",
    entity_registry: EntityRegistry,
    config: Config,
    full_rebuild: bool,
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
        index_status: Index status with repo information.
        vector_store: Vector store with indexed code.
        llm: LLM provider for generation.
        system_prompt: System prompt for LLM.
        status_manager: Wiki status manager for incremental updates.
        entity_registry: Entity registry for cross-linking.
        config: Configuration.
        full_rebuild: If True, regenerate even if unchanged.

    Returns:
        Tuple of (WikiPage or None, was_skipped).
        Returns (None, False) if file should be skipped entirely.
        Returns (page, True) if existing page was reused.
        Returns (page, False) if new page was generated.
    """
    file_path = Path(file_info.path)
    repo_path = Path(index_status.repo_path)

    # Create nested path structure: files/module/filename.md
    parts = file_path.parts
    if len(parts) > 1:
        wiki_path = f"files/{'/'.join(parts[:-1])}/{file_path.stem}.md"
    else:
        wiki_path = f"files/{file_path.stem}.md"

    source_files = [file_info.path]

    # Check if this file page needs regeneration
    if not full_rebuild and not status_manager.needs_regeneration(
        wiki_path, source_files
    ):
        existing_page = await status_manager.load_existing_page(wiki_path)
        if existing_page is not None:
            # Still need to register entities for cross-linking
            all_file_chunks = await vector_store.get_chunks_by_file(file_info.path)
            entity_registry.register_from_chunks(all_file_chunks, wiki_path)
            status_manager.record_page_status(existing_page, source_files)
            return existing_page, True  # Skipped (reused existing)

    # Step 1: Gather file context (chunks, imports, related context)
    context_result = await _gather_file_context(
        file_info=file_info,
        index_status=index_status,
        vector_store=vector_store,
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
        llm=llm,
        system_prompt=system_prompt,
    )

    # Step 4: Generate enrichments (diagrams, call graphs, examples, blame)
    abs_file_path = repo_path / file_info.path
    content = _generate_file_enrichments(
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
    entity_registry.register_from_chunks(file_chunks, wiki_path)

    page = WikiPage(
        path=wiki_path,
        title=f"{file_path.name}",
        content=content,
        generated_at=time.time(),
    )
    status_manager.record_page_status(page, source_files)
    return page, False  # Generated new


# Type alias for async write callback
WriteCallback = Callable[[WikiPage], Awaitable[None]]


def _is_test_file(path: str) -> bool:
    """Check if a file is a test file in tests/ directory.

    Note: Don't skip test_*.py in src/ (e.g., test_examples.py is a source file).

    Args:
        path: File path to check.

    Returns:
        True if file is in tests/ directory.
    """
    parts = path.split("/")
    return "tests" in parts


def _filter_significant_files(files: list[FileInfo], max_files: int) -> list[FileInfo]:
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
    status_manager: "WikiStatusManager",
    entity_registry: EntityRegistry,
    config: Config,
    progress_callback: ProgressCallback | None = None,
    full_rebuild: bool = False,
    write_callback: WriteCallback | None = None,
    generation_progress: "GenerationProgress | None" = None,
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
    significant_files = _filter_significant_files(
        index_status.files, config.wiki.max_file_docs
    )
    if not significant_files:
        return [], 0, 0

    # Use semaphore to limit concurrent LLM calls
    max_concurrent = config.wiki.max_concurrent_llm_calls
    semaphore = asyncio.Semaphore(max_concurrent)
    logger.info(
        f"Generating file docs for {len(significant_files)} files "
        f"(max {max_concurrent} concurrent)"
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
                index_status=index_status,
                vector_store=vector_store,
                llm=llm,
                system_prompt=system_prompt,
                status_manager=status_manager,
                entity_registry=entity_registry,
                config=config,
                full_rebuild=full_rebuild,
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

        except Exception as e:
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
            f"{pages_failed} file docs failed to generate out of {len(tasks)} total"
        )
    return pages, pages_generated, pages_skipped


def _generate_blame_section(
    repo_path: Path,
    file_path: str,
    chunks: list[CodeChunk],
) -> str | None:
    """Generate a "Last Modified" section with git blame info.

    Args:
        repo_path: Path to the repository root.
        file_path: Relative path to the source file.
        chunks: Code chunks from the file.

    Returns:
        Markdown section or None if no blame info available.
    """
    # Build entity list for blame lookup
    entities: list[tuple[str, str, int, int]] = []

    for chunk in chunks:
        if chunk.name and chunk.chunk_type in (
            ChunkType.CLASS,
            ChunkType.FUNCTION,
            ChunkType.METHOD,
        ):
            entities.append(
                (
                    chunk.name,
                    chunk.chunk_type.value,
                    chunk.start_line,
                    chunk.end_line,
                )
            )

    if not entities:
        return None

    # Get blame info for all entities
    blame_infos = get_file_entity_blame(repo_path, file_path, entities)

    if not blame_infos:
        return None

    # Sort by most recently modified first
    blame_infos.sort(key=lambda b: b.last_modified_date, reverse=True)

    # Build the section
    lines = [
        "## Last Modified",
        "",
        "| Entity | Type | Author | Date | Commit |",
        "|--------|------|--------|------|--------|",
    ]

    for blame in blame_infos:
        entity_name = blame.entity_name
        entity_type = blame.entity_type
        author = blame.last_modified_by
        date_str = format_blame_date(blame.last_modified_date)
        commit_short = blame.commit_hash[:7]

        # Truncate long author names
        if len(author) > 20:
            author = author[:17] + "..."

        # Add commit summary if available (truncated)
        commit_info = f"`{commit_short}`"
        if blame.commit_summary:
            summary = blame.commit_summary
            if len(summary) > 30:
                summary = summary[:27] + "..."
            commit_info = f"`{commit_short}` {summary}"

        lines.append(
            f"| `{entity_name}` | {entity_type} | {author} | {date_str} | {commit_info} |"
        )

    return "\n".join(lines)


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
