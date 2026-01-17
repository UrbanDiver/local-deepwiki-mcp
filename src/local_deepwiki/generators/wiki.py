"""Wiki documentation generator using LLM providers."""

import hashlib
import json
import time
from pathlib import Path

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.coverage import generate_coverage_page
from local_deepwiki.generators.crosslinks import EntityRegistry, add_cross_links
from local_deepwiki.generators.stale_detection import generate_stale_report_page
from local_deepwiki.generators.glossary import generate_glossary_page
from local_deepwiki.generators.inheritance import generate_inheritance_page
from local_deepwiki.generators.manifest import ProjectManifest, get_cached_manifest
from local_deepwiki.generators.progress_tracker import GenerationProgress
from local_deepwiki.generators.search import write_full_search_index
from local_deepwiki.generators.see_also import RelationshipAnalyzer, add_see_also_sections
from local_deepwiki.generators.source_refs import add_source_refs_sections
from local_deepwiki.generators.toc import generate_toc, write_toc
from local_deepwiki.generators.wiki_files import generate_file_docs
from local_deepwiki.generators.wiki_modules import generate_module_docs
from local_deepwiki.generators.wiki_pages import (
    generate_architecture_page,
    generate_changelog_page,
    generate_dependencies_page,
    generate_overview_page,
)
from local_deepwiki.generators.wiki_status import WikiStatusManager
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    IndexStatus,
    ProgressCallback,
    WikiGenerationStatus,
    WikiPage,
    WikiStructure,
)
from local_deepwiki.providers.llm import get_llm_provider

logger = get_logger(__name__)


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

        # Get provider-specific system prompt
        self._system_prompt = self.config.get_prompts().wiki_system

        # Entity registry for cross-linking
        self.entity_registry = EntityRegistry()

        # Relationship analyzer for See Also sections
        self.relationship_analyzer = RelationshipAnalyzer()

        # Status manager for incremental updates
        self.status_manager = WikiStatusManager(wiki_path)

        # Cached project manifest (parsed from package files)
        self._manifest: ProjectManifest | None = None

        # Repository path (set during generation)
        self._repo_path: Path | None = None

    def _get_main_definition_lines(self) -> dict[str, tuple[int, int]]:
        """Get line range of main definition (first class or function) per file.

        Returns:
            Dict mapping file_path to (start_line, end_line) tuple.
        """
        table = self.vector_store._get_table()
        if table is None:
            return {}

        df = table.to_pandas()
        result: dict[str, tuple[int, int]] = {}

        for file_path, group in df.groupby("file_path"):
            # Sort by start_line to get first definitions
            classes = group[group["chunk_type"] == "class"].sort_values(by="start_line")  # type: ignore[call-overload]
            functions = group[group["chunk_type"] == "function"].sort_values(by="start_line")  # type: ignore[call-overload]

            if not classes.empty:
                # Use first class definition
                row = classes.iloc[0]
                result[str(file_path)] = (int(row["start_line"]), int(row["end_line"]))
            elif not functions.empty:
                # Use first function definition
                row = functions.iloc[0]
                result[str(file_path)] = (int(row["start_line"]), int(row["end_line"]))

        return result

    async def generate(
        self,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None = None,
        full_rebuild: bool = False,
    ) -> WikiStructure:
        """Generate wiki documentation for the indexed repository.

        Args:
            index_status: The index status with file information.
            progress_callback: Optional progress callback.
            full_rebuild: If True, regenerate all pages. Otherwise, only regenerate changed pages.

        Returns:
            WikiStructure with generated pages.
        """
        logger.info(f"Starting wiki generation for {index_status.repo_path}")
        logger.debug(f"Full rebuild: {full_rebuild}, Total files: {index_status.total_files}")

        # Initialize live progress tracker
        self._progress = GenerationProgress(wiki_path=self.wiki_path)
        self._progress.start_phase("initializing", total=0)

        pages: list[WikiPage] = []
        total_steps = 13  # overview, architecture, modules, files, dependencies, changelog, inheritance, glossary, coverage, cross-links, see-also, search, freshness
        pages_generated = 0
        pages_skipped = 0

        # Store repo path and parse manifest for grounded generation (with caching)
        self._repo_path = Path(index_status.repo_path)
        self._manifest = get_cached_manifest(self._repo_path, cache_dir=self.wiki_path)

        # Build file hash map for incremental generation
        self.status_manager.file_hashes = {f.path: f.hash for f in index_status.files}
        all_source_files = list(self.status_manager.file_hashes.keys())

        # Load previous wiki status for incremental updates
        if not full_rebuild:
            await self.status_manager.load_status()

        # Pre-compute line info for source files (for source refs with line numbers)
        self.status_manager.file_line_info = self._get_main_definition_lines()

        # Generate index page (overview) - depends on all files
        if progress_callback:
            progress_callback("Generating overview", 0, total_steps)

        overview_path = "index.md"
        overview_page: WikiPage
        if full_rebuild or self.status_manager.needs_regeneration(overview_path, all_source_files):
            overview_page = await self._generate_overview(index_status)
            pages_generated += 1
        else:
            existing_page = await self.status_manager.load_existing_page(overview_path)
            if existing_page is None:
                overview_page = await self._generate_overview(index_status)
                pages_generated += 1
            else:
                overview_page = existing_page
                pages_skipped += 1

        pages.append(overview_page)
        self.status_manager.record_page_status(overview_page, all_source_files)
        await self._write_page(overview_page)

        # Generate architecture page - depends on all files
        if progress_callback:
            progress_callback("Generating architecture docs", 1, total_steps)

        architecture_path = "architecture.md"
        architecture_page: WikiPage
        if full_rebuild or self.status_manager.needs_regeneration(
            architecture_path, all_source_files
        ):
            architecture_page = await self._generate_architecture(index_status)
            pages_generated += 1
        else:
            existing_arch_page = await self.status_manager.load_existing_page(architecture_path)
            if existing_arch_page is None:
                architecture_page = await self._generate_architecture(index_status)
                pages_generated += 1
            else:
                architecture_page = existing_arch_page
                pages_skipped += 1

        pages.append(architecture_page)
        self.status_manager.record_page_status(architecture_page, all_source_files)
        await self._write_page(architecture_page)

        # Collect import chunks for relationship analysis (needed for See Also)
        import_results = await self.vector_store.search(
            "import require include",
            limit=self.config.wiki.import_search_limit,
        )
        import_chunks = [r.chunk for r in import_results if r.chunk.chunk_type.value == "import"]
        self.relationship_analyzer.analyze_chunks(import_chunks)

        # Generate module pages
        if progress_callback:
            progress_callback("Generating module documentation", 2, total_steps)

        # Track module docs phase
        self._progress.start_phase("modules", total=0)

        module_pages, gen_count, skip_count = await generate_module_docs(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._system_prompt,
            status_manager=self.status_manager,
            full_rebuild=full_rebuild,
        )
        pages_generated += gen_count
        pages_skipped += skip_count

        # Update module stats and write pages
        self._progress._phase_stats["modules"].items_completed = len(module_pages)
        self._progress.complete_phase()

        for page in module_pages:
            pages.append(page)
            await self._write_page(page)

        # Generate file-level documentation
        if progress_callback:
            progress_callback("Generating file documentation", 3, total_steps)

        file_pages, gen_count, skip_count = await generate_file_docs(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._system_prompt,
            status_manager=self.status_manager,
            entity_registry=self.entity_registry,
            config=self.config,
            progress_callback=progress_callback,
            full_rebuild=full_rebuild,
            write_callback=self._write_page,  # Write pages as they complete
            generation_progress=self._progress,  # Live status tracking
        )
        pages_generated += gen_count
        pages_skipped += skip_count
        # Pages already written by write_callback, just add to list
        pages.extend(file_pages)

        # Generate dependencies page - depends on all files
        if progress_callback:
            progress_callback("Generating dependencies", 4, total_steps)

        deps_path = "dependencies.md"
        deps_page: WikiPage
        deps_source_files: list[str]
        if full_rebuild or self.status_manager.needs_regeneration(deps_path, all_source_files):
            deps_page, deps_source_files = await self._generate_dependencies(index_status)
            pages_generated += 1
        else:
            existing_deps_page = await self.status_manager.load_existing_page(deps_path)
            if existing_deps_page is None:
                deps_page, deps_source_files = await self._generate_dependencies(index_status)
                pages_generated += 1
            else:
                deps_page = existing_deps_page
                # Use source files from previous status if available
                prev_status = self.status_manager.page_statuses.get(deps_path) or (
                    self.status_manager.previous_status.pages.get(deps_path)
                    if self.status_manager.previous_status
                    else None
                )
                deps_source_files = prev_status.source_files if prev_status else all_source_files
                pages_skipped += 1

        pages.append(deps_page)
        self.status_manager.record_page_status(deps_page, deps_source_files)
        await self._write_page(deps_page)

        # Generate changelog page from git history
        if progress_callback:
            progress_callback("Generating changelog", 5, total_steps)

        changelog_page = await self._generate_changelog()
        if changelog_page:
            pages.append(changelog_page)
            self.status_manager.record_page_status(changelog_page, all_source_files)
            await self._write_page(changelog_page)
            pages_generated += 1

        # Generate inheritance page
        if progress_callback:
            progress_callback("Generating inheritance tree", 6, total_steps)

        inheritance_content = await generate_inheritance_page(index_status, self.vector_store)
        if inheritance_content:
            inheritance_page = WikiPage(
                path="inheritance.md",
                title="Class Inheritance",
                content=inheritance_content,
                generated_at=time.time(),
            )
            pages.append(inheritance_page)
            self.status_manager.record_page_status(inheritance_page, all_source_files)
            await self._write_page(inheritance_page)
            pages_generated += 1

        # Generate glossary page
        if progress_callback:
            progress_callback("Generating glossary", 7, total_steps)

        glossary_content = await generate_glossary_page(index_status, self.vector_store)
        if glossary_content:
            glossary_page = WikiPage(
                path="glossary.md",
                title="Glossary",
                content=glossary_content,
                generated_at=time.time(),
            )
            pages.append(glossary_page)
            self.status_manager.record_page_status(glossary_page, all_source_files)
            await self._write_page(glossary_page)
            pages_generated += 1

        # Generate coverage report page
        if progress_callback:
            progress_callback("Generating coverage report", 8, total_steps)

        coverage_content = await generate_coverage_page(index_status, self.vector_store)
        if coverage_content:
            coverage_page = WikiPage(
                path="coverage.md",
                title="Documentation Coverage",
                content=coverage_content,
                generated_at=time.time(),
            )
            pages.append(coverage_page)
            self.status_manager.record_page_status(coverage_page, all_source_files)
            await self._write_page(coverage_page)
            pages_generated += 1

        # Apply cross-links to all pages
        if progress_callback:
            progress_callback("Adding cross-links", 9, total_steps)

        pages = add_cross_links(pages, self.entity_registry)

        # Add Relevant Source Files sections with local wiki links
        pages = add_source_refs_sections(pages, self.status_manager.page_statuses, self.wiki_path)

        # Add See Also sections
        if progress_callback:
            progress_callback("Adding See Also sections", 10, total_steps)

        pages = add_see_also_sections(pages, self.relationship_analyzer)

        # Re-write pages with cross-links and See Also sections
        for page in pages:
            await self._write_page(page)

        # Generate search index with entity-level entries
        if progress_callback:
            progress_callback("Generating search index", 11, total_steps)

        await write_full_search_index(self.wiki_path, pages, index_status, self.vector_store)

        # Generate table of contents with hierarchical numbering
        page_list = [{"path": p.path, "title": p.title} for p in pages]
        toc = generate_toc(page_list)
        write_toc(toc, self.wiki_path)

        # Build wiki generation status
        wiki_status = WikiGenerationStatus(
            repo_path=index_status.repo_path,
            generated_at=time.time(),
            total_pages=len(pages),
            index_status_hash=hashlib.sha256(
                json.dumps(index_status.model_dump(), sort_keys=True).encode()
            ).hexdigest()[:16],
            pages=self.status_manager.page_statuses,
        )

        # Generate freshness report (stale documentation detection)
        freshness_page = generate_stale_report_page(
            repo_path=self._repo_path,
            wiki_status=wiki_status,
            stale_threshold_days=0,
        )
        pages.append(freshness_page)
        self.status_manager.record_page_status(freshness_page, all_source_files)
        await self._write_page(freshness_page)
        pages_generated += 1

        # Update wiki status with freshness page
        wiki_status.pages[freshness_page.path] = self.status_manager.page_statuses[freshness_page.path]
        wiki_status.total_pages = len(pages)

        await self.status_manager.save_status(wiki_status)

        if progress_callback:
            progress_callback(
                f"Wiki generation complete ({pages_generated} generated, {pages_skipped} unchanged)",
                total_steps,
                total_steps,
            )

        logger.info(
            f"Wiki generation complete: {pages_generated} pages generated, "
            f"{pages_skipped} pages unchanged, {len(pages)} total pages"
        )

        # Finalize progress tracker and print summary
        summary = self._progress.finalize(success=True)
        print(summary)

        return WikiStructure(root=str(self.wiki_path), pages=pages)

    async def _generate_overview(self, index_status: IndexStatus) -> WikiPage:
        """Generate the main overview/index page with grounded facts."""
        return await generate_overview_page(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._system_prompt,
            manifest=self._manifest,
            repo_path=self._repo_path,
        )

    async def _generate_architecture(self, index_status: IndexStatus) -> WikiPage:
        """Generate architecture documentation with diagrams and grounded facts."""
        return await generate_architecture_page(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._system_prompt,
            manifest=self._manifest,
            repo_path=self._repo_path,
        )

    async def _generate_dependencies(self, index_status: IndexStatus) -> tuple[WikiPage, list[str]]:
        """Generate dependencies documentation with grounded facts from manifest."""
        return await generate_dependencies_page(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._system_prompt,
            manifest=self._manifest,
            import_search_limit=self.config.wiki.import_search_limit,
        )

    async def _generate_changelog(self) -> WikiPage | None:
        """Generate changelog page from git history."""
        return await generate_changelog_page(self._repo_path)

    async def _write_page(self, page: WikiPage) -> None:
        """Write a wiki page to disk asynchronously."""
        import asyncio

        page_path = self.wiki_path / page.path
        content = page.content

        def _sync_write() -> None:
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(content)

        await asyncio.to_thread(_sync_write)


async def generate_wiki(
    repo_path: Path,
    wiki_path: Path,
    vector_store: VectorStore,
    index_status: IndexStatus,
    config: Config | None = None,
    llm_provider: str | None = None,
    progress_callback: ProgressCallback | None = None,
    full_rebuild: bool = False,
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
        full_rebuild: If True, regenerate all pages. Otherwise, only regenerate changed pages.

    Returns:
        WikiStructure with generated pages.
    """
    from local_deepwiki.core.git_utils import is_github_repo

    config = config or get_config()

    # Auto-switch to cloud provider for GitHub repos if configured
    effective_provider = llm_provider
    if effective_provider is None and config.wiki.use_cloud_for_github:
        if is_github_repo(repo_path):
            effective_provider = config.wiki.github_llm_provider
            logger.info(f"GitHub repo detected, using cloud provider: {effective_provider}")

    generator = WikiGenerator(
        wiki_path=wiki_path,
        vector_store=vector_store,
        config=config,
        llm_provider_name=effective_provider,
    )
    return await generator.generate(index_status, progress_callback, full_rebuild)
