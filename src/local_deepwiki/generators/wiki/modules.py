"""Module documentation generation for wiki."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.wiki.context import WikiPipelineContext
from local_deepwiki.logging import get_logger
from local_deepwiki.models import SearchResult, WikiPage
from local_deepwiki.providers.base import LLMProvider

logger = get_logger(__name__)


async def generate_module_docs(
    ctx: WikiPipelineContext,
    *,
    max_concurrent: int = 8,
    semaphore: asyncio.Semaphore | None = None,
) -> tuple[list[WikiPage], int, int]:
    """Generate documentation for each module/directory.

    Args:
        ctx: Immutable pipeline context bundling shared parameters.
        max_concurrent: Maximum concurrent LLM calls (ignored if semaphore provided).
        semaphore: Optional shared semaphore for concurrency control.

    Returns:
        Tuple of (pages list, generated count, skipped count).
    """
    index_status = ctx.index_status
    vector_store = ctx.vector_store
    llm = ctx.llm
    system_prompt = ctx.system_prompt
    status_manager = ctx.status_manager
    full_rebuild = ctx.full_rebuild
    max_chunk_content_chars = ctx.max_chunk_content_chars

    pages: list[WikiPage] = []
    pages_generated = 0
    pages_skipped = 0

    # Group files by top-level directory
    directories: dict[str, list[str]] = {}
    for file_info in index_status.files:
        parts = Path(file_info.path).parts
        if len(parts) > 1:
            dir_name = parts[0]
        else:
            dir_name = "root"
        directories.setdefault(dir_name, []).append(file_info.path)

    # Collect modules to generate (skip test dirs and tiny directories)
    modules_to_generate: list[tuple[str, list[str]]] = []
    for dir_name, files in directories.items():
        if len(files) < 2:
            continue
        if is_test_file(dir_name + "/dummy", check_filename=False):
            continue

        page_path = f"modules/{dir_name}.md"

        # Check if page needs regeneration (module pages depend on all files in that module)
        if not full_rebuild and not status_manager.needs_regeneration(page_path, files):
            existing_page = await status_manager.load_existing_page(page_path)
            if existing_page is not None:
                pages.append(existing_page)
                status_manager.record_page_status(existing_page, files)
                pages_skipped += 1
                continue

        modules_to_generate.append((dir_name, files))

    if modules_to_generate:
        sem = semaphore or asyncio.Semaphore(max_concurrent)
        logger.info(
            "Generating module docs for %d modules (max %d concurrent)",
            len(modules_to_generate),
            max_concurrent,
        )

        async def _gen_with_semaphore(
            dir_name: str, files: list[str]
        ) -> tuple[str, list[str], WikiPage | None]:
            async with sem:
                page = await generate_single_module_doc(
                    dir_name=dir_name,
                    files=files,
                    vector_store=vector_store,
                    llm=llm,
                    system_prompt=system_prompt,
                    repo_path=Path(index_status.repo_path),
                    max_chunk_content_chars=max_chunk_content_chars,
                )
                return dir_name, files, page

        tasks = [
            asyncio.create_task(_gen_with_semaphore(dn, fs))
            for dn, fs in modules_to_generate
        ]

        for coro in asyncio.as_completed(tasks):
            try:
                dir_name, files, page = await coro
                if page is not None:
                    pages.append(page)
                    status_manager.record_page_status(page, files)
                    pages_generated += 1
            except Exception:  # noqa: BLE001 — module failure must not abort wiki build
                logger.exception("Error generating module doc")

    # Create modules index — uses structural fingerprint since content only
    # changes when modules are added/removed
    if pages:
        index_path = "modules/index.md"
        all_module_files = [f for files in directories.values() for f in files]

        if not full_rebuild and not status_manager.needs_regeneration_structural(
            index_path, index_status
        ):
            existing = await status_manager.load_existing_page(index_path)
            if existing is not None:
                pages.insert(0, existing)
                status_manager.record_summary_page_status(
                    existing, all_module_files, index_status
                )
                pages_skipped += 1
            else:
                modules_index = WikiPage(
                    path=index_path,
                    title="Modules",
                    content=_generate_modules_index(pages),
                    generated_at=time.time(),
                )
                pages.insert(0, modules_index)
                status_manager.record_summary_page_status(
                    modules_index, all_module_files, index_status
                )
                pages_generated += 1
        else:
            modules_index = WikiPage(
                path=index_path,
                title="Modules",
                content=_generate_modules_index(pages),
                generated_at=time.time(),
            )
            pages.insert(0, modules_index)
            status_manager.record_summary_page_status(
                modules_index, all_module_files, index_status
            )
            pages_generated += 1

    return pages, pages_generated, pages_skipped


async def generate_single_module_doc(
    dir_name: str,
    files: list[str],
    vector_store: VectorStore,
    llm: LLMProvider,
    system_prompt: str,
    *,
    repo_path: Path | None = None,
    max_chunk_content_chars: int = 15000,
) -> WikiPage | None:
    """Generate documentation for a single module directory.

    Args:
        dir_name: Name of the module directory.
        files: List of file paths in this module.
        vector_store: Vector store with indexed code.
        llm: LLM provider for generation.
        system_prompt: System prompt for LLM.
        repo_path: Optional path to the repository root for authoritative docs.
        max_chunk_content_chars: Max characters of chunk content in LLM prompt.

    Returns:
        WikiPage with module documentation, or None if no relevant content.
    """
    page_path = f"modules/{dir_name}.md"

    # Fetch chunks directly from known files instead of relying on semantic
    # search which can return chunks from the wrong directory.
    all_module_chunks: list[SearchResult] = []
    for fp in files[:40]:
        file_chunks = await vector_store.get_chunks_by_file(fp)
        all_module_chunks.extend(
            SearchResult(chunk=c, score=1.0, highlights=[]) for c in file_chunks
        )
    # Fall back to semantic search only if direct lookup returned nothing
    if not all_module_chunks:
        search_results = await vector_store.search(f"module {dir_name}", limit=40)
        all_module_chunks = [
            r for r in search_results if r.chunk.file_path.startswith(dir_name)
        ]
    relevant_chunks = all_module_chunks
    if not relevant_chunks:
        return None

    context = "\n\n".join(
        [
            f"File: {r.chunk.file_path}\nType: {r.chunk.chunk_type.value}\nName: {r.chunk.name}\n{r.chunk.content[:max_chunk_content_chars]}"
            for r in relevant_chunks[:25]
        ]
    )

    # Build enriched context: file list with descriptions, imports, authoritative docs
    file_list_section = _build_file_list_section(files, relevant_chunks)
    imports_section = _build_imports_section(relevant_chunks)
    auth_section = _build_authoritative_section(repo_path)

    prompt = f"""Generate documentation for the '{dir_name}' module based ONLY on the code provided.

FILES IN MODULE:
{file_list_section}
{auth_section}{imports_section}CODE CONTEXT:
{context}

Generate documentation that includes:
1. **Module Purpose** - Explain what this module does based on the code shown
2. **Key Classes and Functions** - Describe each class/function visible in the code above. Write class names as plain text for cross-linking.
3. **How Components Interact** - Explain how the components shown work together
4. **Usage Examples** - Show how to use the components (use code blocks)
5. **Dependencies** - What other modules this depends on (based on imports shown)

CRITICAL CONSTRAINTS:
- ONLY describe classes and functions that appear in the code context above
- Do NOT invent additional components not shown
- Do NOT fabricate usage patterns or APIs not visible in the code
- Write class names as plain text (e.g., "The CodeParser class") for cross-linking

Format as markdown."""

    content = await llm.generate(prompt, system_prompt=system_prompt)

    return WikiPage(
        path=page_path,
        title=f"Module: {dir_name}",
        content=content,
        generated_at=time.time(),
    )


def _build_file_list_section(files: list[str], relevant_chunks: list) -> str:
    """Build a file list with brief descriptions from search results.

    Args:
        files: File paths in the module.
        relevant_chunks: Search results containing chunks from this module.

    Returns:
        Formatted file list string.
    """
    # Build a map of file -> first class/function name from search results
    file_entity_map: dict[str, str] = {}
    for r in relevant_chunks:
        fp = r.chunk.file_path
        if (
            fp not in file_entity_map
            and r.chunk.name
            and r.chunk.chunk_type.value in ("class", "function")
        ):
            file_entity_map[fp] = r.chunk.name

    lines: list[str] = []
    for file_path in sorted(files[:20]):
        entity_name = file_entity_map.get(file_path)
        if entity_name:
            lines.append(f"- {file_path} (defines {entity_name})")
        else:
            lines.append(f"- {file_path}")

    if len(files) > 20:
        lines.append(f"- ... and {len(files) - 20} more files")
    return "\n".join(lines) if lines else ", ".join(files[:10])


def _build_imports_section(relevant_chunks: list) -> str:
    """Extract import information from search results.

    Args:
        relevant_chunks: Search results filtered to this module.

    Returns:
        Formatted imports section for the prompt, or empty string.
    """
    try:
        from local_deepwiki.generators.context_builder import (
            extract_imports_from_chunks,
        )

        import_chunks = [
            r.chunk for r in relevant_chunks if r.chunk.chunk_type.value == "import"
        ]
        if not import_chunks:
            return ""

        names, modules = extract_imports_from_chunks(import_chunks)
        if not names and not modules:
            return ""

        parts = ["MODULE IMPORTS:\n"]
        if modules:
            parts.append(f"Imported modules: {', '.join(sorted(modules)[:20])}")
        if names:
            parts.append(f"Imported names: {', '.join(sorted(names)[:20])}")
        return "\n".join(parts) + "\n\n"
    except (ImportError, AttributeError, TypeError):
        return ""


def _build_authoritative_section(repo_path: Path | None) -> str:
    """Read authoritative project docs for LLM grounding.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Formatted authoritative docs section, or empty string.
    """
    if repo_path is None:
        return ""

    try:
        from local_deepwiki.generators.wiki.pages import _read_authoritative_docs

        docs = _read_authoritative_docs(repo_path)
        if docs:
            return f"""AUTHORITATIVE PROJECT DOCUMENTATION (HIGH PRIORITY):
{docs}

"""
    except ImportError:
        pass

    return ""


def _generate_modules_index(module_pages: list[WikiPage]) -> str:
    """Generate index page for modules.

    Args:
        module_pages: List of module wiki pages.

    Returns:
        Markdown content for modules index.
    """
    lines = ["# Modules\n", "This section contains documentation for each module.\n"]

    for page in module_pages:
        if page.path != "modules/index.md":
            name = Path(page.path).stem
            lines.append(f"- [{page.title}]({name}.md)")

    return "\n".join(lines)
