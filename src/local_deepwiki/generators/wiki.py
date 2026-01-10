"""Wiki documentation generator using LLM providers."""

import time
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.models import CodeChunk, IndexStatus, WikiPage, WikiStructure
from local_deepwiki.providers.base import LLMProvider
from local_deepwiki.providers.llm import get_llm_provider


SYSTEM_PROMPT = """You are a technical documentation expert. Generate clear, concise documentation for code.
- Use markdown formatting
- Include code examples where helpful
- Focus on explaining what the code does and how to use it
- Be accurate and avoid speculation
- Keep explanations practical and actionable"""


class WikiGenerator:
    """Generate wiki documentation from indexed code."""

    def __init__(
        self,
        wiki_path: Path,
        vector_store: VectorStore,
        config: Config | None = None,
        llm_provider_name: str | None = None,
    ):
        """Initialize the wiki generator.

        Args:
            wiki_path: Path to wiki output directory.
            vector_store: Vector store with indexed code.
            config: Optional configuration.
            llm_provider_name: Override LLM provider ("ollama", "anthropic", "openai").
        """
        self.wiki_path = wiki_path
        self.vector_store = vector_store
        self.config = config or get_config()

        # Override LLM provider if specified
        if llm_provider_name:
            self.config.llm.provider = llm_provider_name  # type: ignore

        self.llm = get_llm_provider(self.config.llm)

    async def generate(
        self,
        index_status: IndexStatus,
        progress_callback: Any = None,
    ) -> WikiStructure:
        """Generate wiki documentation for the indexed repository.

        Args:
            index_status: The index status with file information.
            progress_callback: Optional progress callback.

        Returns:
            WikiStructure with generated pages.
        """
        pages: list[WikiPage] = []

        # Generate index page (overview)
        if progress_callback:
            progress_callback("Generating overview", 0, 4)

        overview_page = await self._generate_overview(index_status)
        pages.append(overview_page)
        self._write_page(overview_page)

        # Generate architecture page
        if progress_callback:
            progress_callback("Generating architecture docs", 1, 4)

        architecture_page = await self._generate_architecture(index_status)
        pages.append(architecture_page)
        self._write_page(architecture_page)

        # Generate module pages
        if progress_callback:
            progress_callback("Generating module documentation", 2, 4)

        module_pages = await self._generate_module_docs(index_status)
        for page in module_pages:
            pages.append(page)
            self._write_page(page)

        # Generate dependencies page
        if progress_callback:
            progress_callback("Generating dependencies", 3, 4)

        deps_page = await self._generate_dependencies(index_status)
        pages.append(deps_page)
        self._write_page(deps_page)

        if progress_callback:
            progress_callback("Wiki generation complete", 4, 4)

        return WikiStructure(root=str(self.wiki_path), pages=pages)

    async def _generate_overview(self, index_status: IndexStatus) -> WikiPage:
        """Generate the main overview/index page."""
        # Gather context from vector store
        stats = self.vector_store.get_stats()

        prompt = f"""Generate a README-style overview for this codebase:

Repository: {Path(index_status.repo_path).name}
Total Files: {index_status.total_files}
Languages: {', '.join(f'{lang} ({count} files)' for lang, count in index_status.languages.items())}
Total Code Chunks: {index_status.total_chunks}

Generate a clear overview that includes:
1. Project title and brief description (infer from the code structure)
2. Key features/capabilities
3. Technology stack
4. Directory structure overview
5. Quick start guide

Format as markdown with proper headings."""

        content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        return WikiPage(
            path="index.md",
            title="Overview",
            content=content,
            generated_at=time.time(),
        )

    async def _generate_architecture(self, index_status: IndexStatus) -> WikiPage:
        """Generate architecture documentation with diagrams."""
        # Get module-level chunks for architecture overview
        search_results = await self.vector_store.search(
            "architecture structure main module",
            limit=20,
        )

        context = "\n\n".join([
            f"File: {r.chunk.file_path}\n{r.chunk.content[:500]}"
            for r in search_results
        ])

        prompt = f"""Based on this codebase context, generate architecture documentation:

{context}

Generate documentation that includes:
1. System architecture overview
2. Key components and their responsibilities
3. Data flow between components
4. A Mermaid diagram showing the architecture (use ```mermaid code blocks)
5. Design patterns used

Format as markdown with clear sections."""

        content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        return WikiPage(
            path="architecture.md",
            title="Architecture",
            content=content,
            generated_at=time.time(),
        )

    async def _generate_module_docs(self, index_status: IndexStatus) -> list[WikiPage]:
        """Generate documentation for each module/directory."""
        pages = []

        # Group files by top-level directory
        directories: dict[str, list[str]] = {}
        for file_info in index_status.files:
            parts = Path(file_info.path).parts
            if len(parts) > 1:
                dir_name = parts[0]
            else:
                dir_name = "root"
            directories.setdefault(dir_name, []).append(file_info.path)

        # Generate a page for each significant directory
        for dir_name, files in directories.items():
            if len(files) < 2:
                continue

            # Get chunks for this directory
            search_results = await self.vector_store.search(
                f"module {dir_name}",
                limit=15,
            )

            # Filter to chunks from this directory
            relevant_chunks = [
                r for r in search_results
                if r.chunk.file_path.startswith(dir_name)
            ]

            if not relevant_chunks:
                continue

            context = "\n\n".join([
                f"File: {r.chunk.file_path}\nType: {r.chunk.chunk_type.value}\nName: {r.chunk.name}\n{r.chunk.content[:400]}"
                for r in relevant_chunks[:10]
            ])

            prompt = f"""Generate documentation for the '{dir_name}' module:

Files in module: {', '.join(files[:10])}{'...' if len(files) > 10 else ''}

Code context:
{context}

Generate documentation that includes:
1. Module purpose and responsibilities
2. Key classes/functions and their purposes
3. Usage examples
4. Dependencies on other modules

Format as markdown."""

            content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

            page = WikiPage(
                path=f"modules/{dir_name}.md",
                title=f"Module: {dir_name}",
                content=content,
                generated_at=time.time(),
            )
            pages.append(page)

        # Create modules index
        if pages:
            modules_index = WikiPage(
                path="modules/index.md",
                title="Modules",
                content=self._generate_modules_index(pages),
                generated_at=time.time(),
            )
            pages.insert(0, modules_index)

        return pages

    def _generate_modules_index(self, module_pages: list[WikiPage]) -> str:
        """Generate index page for modules."""
        lines = ["# Modules\n", "This section contains documentation for each module.\n"]

        for page in module_pages:
            if page.path != "modules/index.md":
                name = Path(page.path).stem
                lines.append(f"- [{page.title}]({name}.md)")

        return "\n".join(lines)

    async def _generate_dependencies(self, index_status: IndexStatus) -> WikiPage:
        """Generate dependencies documentation."""
        # Get import chunks
        search_results = await self.vector_store.search(
            "import require include dependencies",
            limit=30,
        )

        import_chunks = [r for r in search_results if r.chunk.chunk_type.value == "import"]

        context = "\n\n".join([
            f"File: {r.chunk.file_path}\n{r.chunk.content}"
            for r in import_chunks[:20]
        ])

        prompt = f"""Based on these import statements, generate a dependencies overview:

{context}

Generate documentation that includes:
1. External dependencies (libraries, packages)
2. Internal module dependencies
3. A Mermaid diagram showing dependency relationships (use ```mermaid code blocks)
4. Any notable dependency patterns

Format as markdown."""

        content = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)

        return WikiPage(
            path="dependencies.md",
            title="Dependencies",
            content=content,
            generated_at=time.time(),
        )

    def _write_page(self, page: WikiPage) -> None:
        """Write a wiki page to disk."""
        page_path = self.wiki_path / page.path
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(page.content)


async def generate_wiki(
    repo_path: Path,
    wiki_path: Path,
    vector_store: VectorStore,
    index_status: IndexStatus,
    config: Config | None = None,
    llm_provider: str | None = None,
    progress_callback: Any = None,
) -> WikiStructure:
    """Convenience function to generate wiki documentation.

    Args:
        repo_path: Path to the repository.
        wiki_path: Path for wiki output.
        vector_store: Indexed vector store.
        index_status: Index status.
        config: Optional configuration.
        llm_provider: Optional LLM provider override.
        progress_callback: Optional progress callback.

    Returns:
        WikiStructure with generated pages.
    """
    generator = WikiGenerator(
        wiki_path=wiki_path,
        vector_store=vector_store,
        config=config,
        llm_provider_name=llm_provider,
    )
    return await generator.generate(index_status, progress_callback)
