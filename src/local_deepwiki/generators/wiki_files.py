"""File documentation generation for wiki."""

import asyncio
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.config import Config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.api_docs import get_file_api_docs
from local_deepwiki.generators.callgraph import get_file_call_graph
from local_deepwiki.generators.crosslinks import EntityRegistry
from local_deepwiki.generators.diagrams import generate_class_diagram
from local_deepwiki.generators.test_examples import get_file_examples
from local_deepwiki.logging import get_logger
from local_deepwiki.models import FileInfo, IndexStatus, ProgressCallback, WikiPage
from local_deepwiki.providers.base import LLMProvider

if TYPE_CHECKING:
    from local_deepwiki.generators.wiki_status import WikiStatusManager

logger = get_logger(__name__)


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

    # Create nested path structure: files/module/filename.md
    parts = file_path.parts
    if len(parts) > 1:
        wiki_path = f"files/{'/'.join(parts[:-1])}/{file_path.stem}.md"
    else:
        wiki_path = f"files/{file_path.stem}.md"

    source_files = [file_info.path]

    # Check if this file page needs regeneration
    if not full_rebuild and not status_manager.needs_regeneration(wiki_path, source_files):
        existing_page = await status_manager.load_existing_page(wiki_path)
        if existing_page is not None:
            # Still need to register entities for cross-linking
            all_file_chunks = await vector_store.get_chunks_by_file(file_info.path)
            entity_registry.register_from_chunks(all_file_chunks, wiki_path)
            status_manager.record_page_status(existing_page, source_files)
            return existing_page, True  # Skipped (reused existing)

    # Get all chunks for this file
    search_results = await vector_store.search(
        f"file:{file_info.path}",
        limit=config.wiki.context_search_limit,
    )

    # Filter to chunks from this specific file
    file_chunks = [r for r in search_results if r.chunk.file_path == file_info.path]

    if not file_chunks:
        # Fallback: search by filename
        search_results = await vector_store.search(
            file_path.stem,
            limit=config.wiki.fallback_search_limit,
        )
        file_chunks = [r for r in search_results if r.chunk.file_path == file_info.path]

    if not file_chunks:
        return None, False  # No content to document

    # Build context from chunks
    context_parts = []
    for r in file_chunks[:15]:  # Limit context size
        chunk = r.chunk
        context_parts.append(
            f"Type: {chunk.chunk_type.value}\n"
            f"Name: {chunk.name}\n"
            f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            f"```\n{chunk.content[:600]}\n```"
        )

    context = "\n\n".join(context_parts)

    prompt = f"""Generate documentation for the file '{file_info.path}' based ONLY on the code provided.

Language: {file_info.language}
Total code chunks: {file_info.chunk_count}

Code contents:
{context}

Generate documentation that includes:
1. **File Overview**: Purpose of this file based on the code shown
2. **Classes**: Document each class visible in the code with its purpose and key methods
3. **Functions**: Document each function with parameters and return values as shown
4. **Usage Examples**: Show how to use the components (based on their actual signatures)
5. **Related Components**: Mention other classes this file works with (based on imports/references shown)

CRITICAL CONSTRAINTS:
- ONLY document classes, methods, and functions that appear in the code above
- Do NOT invent additional methods or parameters not shown
- Do NOT fabricate usage examples with APIs not visible in the code
- Write class names as plain text (e.g., "The WikiGenerator class") for cross-linking
- Only use backticks for actual code snippets

Format as markdown with clear sections.
Do NOT include mermaid class diagrams - they will be auto-generated."""

    content = await llm.generate(prompt, system_prompt=system_prompt)

    # Strip any LLM-generated class diagram sections (we add our own)
    content = re.sub(
        r"\n*##\s*Class\s*Diagram\s*\n+```mermaid\s*\n+classDiagram.*?```",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Generate API reference section with type signatures
    abs_file_path = Path(index_status.repo_path) / file_info.path
    if abs_file_path.exists():
        api_docs = get_file_api_docs(abs_file_path)
        if api_docs:
            content += "\n\n## API Reference\n\n" + api_docs

    # Generate class diagram if file has classes
    all_file_chunks = await vector_store.get_chunks_by_file(file_info.path)
    class_diagram = generate_class_diagram(all_file_chunks)
    if class_diagram:
        content += "\n\n## Class Diagram\n\n" + class_diagram

    # Generate call graph diagram
    if abs_file_path.exists():
        call_graph = get_file_call_graph(abs_file_path, Path(index_status.repo_path))
        if call_graph:
            content += "\n\n## Call Graph\n\n```mermaid\n" + call_graph + "\n```"

    # Add usage examples from test files
    entity_names = [
        chunk.name for chunk in all_file_chunks
        if chunk.name and len(chunk.name) > 2
    ]
    if entity_names:
        examples_md = get_file_examples(
            source_file=abs_file_path,
            repo_root=Path(index_status.repo_path),
            entity_names=entity_names,
            max_examples=5,
        )
        if examples_md:
            content += "\n\n" + examples_md

    # Register entities for cross-linking
    entity_registry.register_from_chunks(all_file_chunks, wiki_path)

    page = WikiPage(
        path=wiki_path,
        title=f"{file_path.name}",
        content=content,
        generated_at=time.time(),
    )
    status_manager.record_page_status(page, source_files)
    return page, False  # Generated new


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
) -> tuple[list[WikiPage], int, int]:
    """Generate documentation for individual source files.

    Uses parallel LLM calls for faster generation, controlled by
    config.wiki.max_concurrent_llm_calls.

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

    Returns:
        Tuple of (pages list, generated count, skipped count).
    """
    # Filter files: skip __init__.py and test files
    def is_test_file(path: str) -> bool:
        """Check if a file is a test file."""
        parts = path.split("/")
        # Skip files in tests/ directory only
        # Don't skip test_*.py in src/ (e.g., test_examples.py is a source file)
        return "tests" in parts

    significant_files = [
        f
        for f in index_status.files
        if not f.path.endswith("__init__.py")
        and not is_test_file(f.path)
        and f.chunk_count >= 2  # Has meaningful content
    ]

    # Limit test files separately if we want them later
    # For source files, include all of them (no limit)
    max_files = config.wiki.max_file_docs
    if len(significant_files) > max_files:
        # Only limit if we have way too many files
        # Prioritize files with more chunks (more complex)
        significant_files = sorted(
            significant_files, key=lambda x: x.chunk_count, reverse=True
        )[:max_files]

    if not significant_files:
        return [], 0, 0

    # Use semaphore to limit concurrent LLM calls
    max_concurrent = config.wiki.max_concurrent_llm_calls
    semaphore = asyncio.Semaphore(max_concurrent)
    logger.info(
        f"Generating file docs for {len(significant_files)} files "
        f"(max {max_concurrent} concurrent)"
    )

    async def generate_with_semaphore(
        file_info: FileInfo,
    ) -> tuple[WikiPage | None, bool]:
        async with semaphore:
            logger.debug(f"Generating doc for {file_info.path}")
            return await generate_single_file_doc(
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

    # Run all file doc generations concurrently (limited by semaphore)
    results = await asyncio.gather(
        *[generate_with_semaphore(f) for f in significant_files],
        return_exceptions=True,
    )

    # Process results
    pages = []
    pages_generated = 0
    pages_skipped = 0

    for file_info, result in zip(significant_files, results):
        if isinstance(result, BaseException):
            logger.error(f"Error generating doc for {file_info.path}: {result}")
            continue

        page, was_skipped = result
        if page is not None:
            pages.append(page)
            if was_skipped:
                pages_skipped += 1
            else:
                pages_generated += 1

    # Create files index (always regenerate since it depends on all file pages)
    if pages:
        all_file_paths = [f.path for f in significant_files]
        files_index = WikiPage(
            path="files/index.md",
            title="Source Files",
            content=_generate_files_index(pages),
            generated_at=time.time(),
        )
        pages.insert(0, files_index)
        status_manager.record_page_status(files_index, all_file_paths)

    logger.info(
        f"File docs complete: {pages_generated} generated, {pages_skipped} skipped"
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
