"""Wiki documentation generator using LLM providers."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.plugins.base import WikiGeneratorPlugin

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.events import EventType, get_event_emitter
from local_deepwiki.generators.coverage import generate_coverage_page
from local_deepwiki.generators.crosslinks import EntityRegistry
from local_deepwiki.generators.dependency_graph import generate_dependency_graph_page
from local_deepwiki.generators.glossary import generate_glossary_page
from local_deepwiki.generators.inheritance import generate_inheritance_page
from local_deepwiki.generators.manifest import ProjectManifest, get_cached_manifest
from local_deepwiki.generators.progress_tracker import GenerationProgress
from local_deepwiki.generators.see_also import RelationshipAnalyzer
from local_deepwiki.generators.wiki_files import generate_file_docs
from local_deepwiki.generators.wiki_modules import generate_module_docs
from local_deepwiki.generators.wiki_pages import (
    generate_architecture_page,
    generate_changelog_page,
    generate_dependencies_page,
    generate_overview_page,
)
from local_deepwiki.generators.wiki_plugin_runner import (
    run_plugin_generators,
    sort_generators_by_dependencies,
)
from local_deepwiki.generators.wiki_postprocessing import (
    apply_cross_linking,
    build_wiki_status,
    generate_codemap_pages_phase,
    generate_freshness_and_finalize,
    generate_search_and_toc,
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
from local_deepwiki.prompts import PromptManager
from local_deepwiki.providers.llm import get_cached_llm_provider

logger = get_logger(__name__)


class _GenerationContext:
    """Internal context for tracking wiki generation state.

    This class encapsulates mutable state during generation to avoid
    passing many parameters between helper methods.
    """

    __slots__ = (
        "pages",
        "pages_generated",
        "pages_skipped",
        "all_source_files",
        "full_rebuild",
        "warnings",
    )

    def __init__(
        self,
        pages: list["WikiPage"],
        pages_generated: int,
        pages_skipped: int,
        all_source_files: list[str],
        full_rebuild: bool,
    ):
        self.pages = pages
        self.pages_generated = pages_generated
        self.pages_skipped = pages_skipped
        self.all_source_files = all_source_files
        self.full_rebuild = full_rebuild
        self.warnings: list[str] = []


class WikiGenerator:
    """Generate wiki documentation from indexed code."""

    def __init__(
        self,
        wiki_path: Path,
        vector_store: VectorStore,
        config: Config | None = None,
        llm_provider_name: str | None = None,
    ):
        """Initialize the wiki generator."""
        self.wiki_path = wiki_path
        self.vector_store = vector_store
        base_config = config or get_config()

        # Create a copy with overridden LLM provider if specified
        if llm_provider_name:
            self.config = base_config.with_llm_provider(llm_provider_name)  # type: ignore[arg-type]
        else:
            # Store a defensive copy to prevent external mutation
            self.config = base_config.model_copy(deep=True)

        # Use cached LLM provider for better performance on repeated generations
        cache_path = wiki_path / "llm_cache.lance"
        self.llm = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=vector_store.embedding_provider,
            cache_config=self.config.llm_cache,
            llm_config=self.config.llm,
        )

        # Initialize prompt manager for custom prompt support
        custom_prompts_dir = None
        if self.config.prompts.custom_dir:
            custom_prompts_dir = Path(self.config.prompts.custom_dir)
        self._prompt_manager = PromptManager(
            custom_dir=custom_prompts_dir,
            repo_path=None,  # Will be set during generation
        )

        # Get provider-specific system prompt (may be overridden by custom prompts)
        self._system_prompt = self._prompt_manager.get_wiki_system_prompt(
            provider=self.config.llm.provider,
        )

        # Build page-type-specific prompts
        self._page_prompts = self._build_page_prompts()

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

    def _build_page_prompts(self) -> dict[str, str]:
        """Build page-type-specific system prompts.

        Returns a dict mapping page type names to their system prompts,
        falling back to ``self._system_prompt`` for unknown types.
        """
        provider = self.config.llm.provider
        prompts: dict[str, str] = {}
        for page_type in ("overview", "architecture", "file", "module"):
            prompts[page_type] = self._prompt_manager.get_wiki_page_prompt(
                page_type=page_type,
                provider=provider,
            )
        return prompts

    def _get_main_definition_lines(self) -> dict[str, tuple[int, int]]:
        """Get line range of main definition (first class/function) per file."""
        return self.vector_store.get_main_definition_lines()

    async def generate(
        self,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None = None,
        full_rebuild: bool = False,
        max_file_pages: int | None = None,
    ) -> WikiStructure:
        """Generate wiki documentation for the indexed repository."""
        logger.info("Starting wiki generation for %s", index_status.repo_path)
        logger.debug(
            "Full rebuild: %s, Total files: %s", full_rebuild, index_status.total_files
        )

        # Emit WIKI_START event
        emitter = get_event_emitter()
        await emitter.emit(
            EventType.WIKI_START,
            {
                "repo_path": index_status.repo_path,
                "full_rebuild": full_rebuild,
                "total_files": index_status.total_files,
            },
        )

        # Initialize generation context
        ctx = await self._init_generation_context(index_status, full_rebuild)

        # Phase 1: Generate summary pages (overview, architecture)
        await self._generate_summary_pages(ctx, index_status, progress_callback)

        # Phase 2: Analyze imports for relationship tracking
        await self._analyze_imports_for_relationships()

        # Phase 3: Generate module documentation
        await self._generate_module_pages(ctx, index_status, progress_callback)

        # Phase 4: Generate file documentation
        await self._generate_file_pages(
            ctx, index_status, progress_callback, max_files=max_file_pages
        )

        # Phase 5: Generate dependencies page
        await self._generate_dependencies_page(ctx, index_status, progress_callback)

        # Phase 6: Generate changelog
        await self._generate_changelog_page(ctx, index_status, progress_callback)

        # Phase 7: Generate auxiliary pages (inheritance, glossary, coverage)
        await self._generate_auxiliary_pages(ctx, index_status, progress_callback)

        # Phase 7b: Run wiki generator plugins
        await self._run_plugin_generators(ctx, index_status, progress_callback)

        # Phase 7c: Generate codemap pages
        await self._generate_codemap_pages(ctx, index_status, progress_callback)

        # Phase 8: Apply cross-links and see-also sections
        ctx.pages = await self._apply_cross_linking(ctx.pages, progress_callback)

        # Phase 9: Generate search index and TOC
        await self._generate_search_and_toc(ctx.pages, index_status, progress_callback)

        # Phase 10: Generate freshness report and finalize
        wiki_status = self._build_wiki_status(ctx, index_status)
        await self._generate_freshness_and_finalize(
            ctx, wiki_status, index_status, progress_callback
        )

        logger.info(
            "Wiki generation complete: %d pages generated, %d pages unchanged, %d total pages",
            ctx.pages_generated,
            ctx.pages_skipped,
            len(ctx.pages),
        )

        # Log any generation warnings
        if ctx.warnings:
            logger.warning(
                "Wiki generation completed with %s warning(s)", len(ctx.warnings)
            )
            for warning in ctx.warnings:
                logger.warning("  - %s", warning)
                self._progress._log(f"WARNING: {warning}")

        # Log LLM cache statistics if available
        self._log_cache_stats()

        # Finalize progress tracker and log summary
        summary = self._progress.finalize(success=True, warnings=ctx.warnings)
        logger.info(summary)

        # Emit WIKI_COMPLETE event
        await emitter.emit(
            EventType.WIKI_COMPLETE,
            {
                "repo_path": index_status.repo_path,
                "total_pages": len(ctx.pages),
                "pages_generated": ctx.pages_generated,
                "pages_skipped": ctx.pages_skipped,
            },
        )

        return WikiStructure(root=str(self.wiki_path), pages=ctx.pages)

    def _log_cache_stats(self) -> None:
        """Log LLM cache statistics if available."""
        try:
            cache_stats = getattr(self.llm, "stats", None)
            if cache_stats is None:
                return
            hits = int(cache_stats.get("hits", 0))
            misses = int(cache_stats.get("misses", 0))
            skipped = int(cache_stats.get("skipped", 0))
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0.0
            logger.info(
                "LLM cache stats: %d hits, %d misses, %d skipped (%.1f%% hit rate)",
                hits,
                misses,
                skipped,
                hit_rate,
            )
        except (TypeError, ValueError, AttributeError):
            # Skip logging if stats are not properly available (e.g., mock objects)
            pass

    async def _init_generation_context(
        self, index_status: IndexStatus, full_rebuild: bool
    ) -> _GenerationContext:
        """Initialize the generation context with tracking state."""
        # Initialize live progress tracker
        self._progress = GenerationProgress(wiki_path=self.wiki_path)
        self._progress.start_phase("initializing", total=0)

        # Store repo path and parse manifest for grounded generation (with caching)
        self._repo_path = Path(index_status.repo_path)
        self._manifest = get_cached_manifest(self._repo_path, cache_dir=self.wiki_path)

        # Update prompt manager with repo path for per-project prompts
        self._prompt_manager.loader.repo_path = self._repo_path
        self._prompt_manager.loader.clear_cache()  # Clear cache to pick up repo prompts
        # Reload system prompt and page-type prompts in case repo has custom prompts
        self._system_prompt = self._prompt_manager.get_wiki_system_prompt(
            provider=self.config.llm.provider,
        )
        self._page_prompts = self._build_page_prompts()

        # Build file hash map for incremental generation
        self.status_manager.file_hashes = {f.path: f.hash for f in index_status.files}
        all_source_files = list(self.status_manager.file_hashes.keys())

        # Load previous wiki status for incremental updates
        if not full_rebuild:
            await self.status_manager.load_status()

            # Log regeneration summary for incremental updates
            summary = self.status_manager.get_regeneration_summary()
            if summary["is_full_rebuild"]:
                logger.info("No previous wiki status found, performing full generation")
            else:
                logger.info(
                    "Incremental update: %d files changed, %d pages to regenerate, %d pages unchanged",
                    summary["changed_file_count"],
                    summary["affected_page_count"],
                    summary["unchanged_page_count"],
                )
                if summary["changed_file_count"] <= 5:
                    for f in summary["changed_files"]:
                        logger.debug("  Changed: %s", f)

        # Pre-compute line info for source files (for source refs with line numbers)
        self.status_manager.file_line_info = self._get_main_definition_lines()

        return _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=all_source_files,
            full_rebuild=full_rebuild,
        )

    async def _generate_summary_pages(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate overview and architecture pages."""
        pages_to_generate = [
            (
                "index.md",
                "Generating overview",
                0,
                lambda: self._generate_overview(index_status),
            ),
            (
                "architecture.md",
                "Generating architecture docs",
                1,
                lambda: self._generate_architecture(index_status),
            ),
        ]
        for page_path, label, step, gen_fn in pages_to_generate:
            if progress_callback:
                progress_callback(label, step, 14)
            page, generated = await self._generate_or_load_summary_page(
                ctx=ctx,
                page_path=page_path,
                generator=gen_fn,
                index_status=index_status,
            )
            ctx.pages.append(page)
            if generated:
                ctx.pages_generated += 1
            else:
                ctx.pages_skipped += 1

    async def _generate_or_load_page(
        self,
        ctx: _GenerationContext,
        page_path: str,
        generator: "Callable[[], Awaitable[WikiPage]]",
        source_files: list[str],
    ) -> tuple[WikiPage, bool]:
        """Generate a page or load from cache if unchanged."""
        if ctx.full_rebuild or self.status_manager.needs_regeneration(
            page_path, source_files
        ):
            page = await generator()
            was_generated = True
        else:
            existing_page = await self.status_manager.load_existing_page(page_path)
            if existing_page is None:
                page = await generator()
                was_generated = True
            else:
                page = existing_page
                was_generated = False

        self.status_manager.record_page_status(page, source_files)
        await self._write_page(page)

        # Emit WIKI_PAGE_COMPLETE event
        emitter = get_event_emitter()
        await emitter.emit(
            EventType.WIKI_PAGE_COMPLETE,
            {
                "page_path": page.path,
                "page_title": page.title,
                "was_generated": was_generated,
            },
        )

        return page, was_generated

    async def _generate_or_load_summary_page(
        self,
        ctx: _GenerationContext,
        page_path: str,
        generator: "Callable[[], Awaitable[WikiPage]]",
        index_status: IndexStatus,
    ) -> tuple[WikiPage, bool]:
        """Generate a summary page or load from cache using structural fingerprint."""
        if ctx.full_rebuild or self.status_manager.needs_regeneration_structural(
            page_path, index_status
        ):
            page = await generator()
            was_generated = True
        else:
            existing_page = await self.status_manager.load_existing_page(page_path)
            if existing_page is None:
                page = await generator()
                was_generated = True
            else:
                page = existing_page
                was_generated = False

        self.status_manager.record_summary_page_status(
            page, ctx.all_source_files, index_status
        )
        await self._write_page(page)

        emitter = get_event_emitter()
        await emitter.emit(
            EventType.WIKI_PAGE_COMPLETE,
            {
                "page_path": page.path,
                "page_title": page.title,
                "was_generated": was_generated,
            },
        )

        return page, was_generated

    async def _analyze_imports_for_relationships(self) -> None:
        """Collect import chunks for relationship analysis (See Also sections)."""
        import_results = await self.vector_store.search(
            "import require include",
            limit=self.config.wiki.import_search_limit,
        )
        import_chunks = [
            r.chunk for r in import_results if r.chunk.chunk_type.value == "import"
        ]
        self.relationship_analyzer.analyze_chunks(import_chunks)

    async def _generate_module_pages(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate module documentation pages."""
        if progress_callback:
            progress_callback("Generating module documentation", 2, 14)

        self._progress.start_phase("modules", total=0)

        module_pages, gen_count, skip_count = await generate_module_docs(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._page_prompts.get("module", self._system_prompt),
            status_manager=self.status_manager,
            full_rebuild=ctx.full_rebuild,
            max_chunk_content_chars=self.config.wiki.max_chunk_content_chars,
        )
        ctx.pages_generated += gen_count
        ctx.pages_skipped += skip_count

        # Update module stats and write pages
        self._progress._phase_stats["modules"].items_completed = len(module_pages)
        self._progress.complete_phase()

        for page in module_pages:
            ctx.pages.append(page)
            await self._write_page(page)

    async def _generate_file_pages(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
        max_files: int | None = None,
    ) -> None:
        """Generate file-level documentation pages."""
        if progress_callback:
            progress_callback("Generating file documentation", 3, 14)

        file_pages, gen_count, skip_count = await generate_file_docs(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._page_prompts.get("file", self._system_prompt),
            status_manager=self.status_manager,
            entity_registry=self.entity_registry,
            config=self.config,
            progress_callback=progress_callback,
            full_rebuild=ctx.full_rebuild,
            write_callback=self._write_page,
            generation_progress=self._progress,
            max_files=max_files,
        )
        ctx.pages_generated += gen_count
        ctx.pages_skipped += skip_count
        ctx.pages.extend(file_pages)

    async def _generate_dependencies_page(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate the dependencies documentation page."""
        if progress_callback:
            progress_callback("Generating dependencies", 4, 14)

        deps_path = "dependencies.md"

        if ctx.full_rebuild or self.status_manager.needs_regeneration(
            deps_path, ctx.all_source_files
        ):
            deps_page, deps_source_files = await self._generate_dependencies(
                index_status
            )
            ctx.pages_generated += 1
        else:
            existing_deps_page = await self.status_manager.load_existing_page(deps_path)
            if existing_deps_page is None:
                deps_page, deps_source_files = await self._generate_dependencies(
                    index_status
                )
                ctx.pages_generated += 1
            else:
                deps_page = existing_deps_page
                # Use source files from previous status if available
                prev_status = self.status_manager.page_statuses.get(deps_path) or (
                    self.status_manager.previous_status.pages.get(deps_path)
                    if self.status_manager.previous_status
                    else None
                )
                deps_source_files = (
                    prev_status.source_files if prev_status else ctx.all_source_files
                )
                ctx.pages_skipped += 1

        ctx.pages.append(deps_page)
        self.status_manager.record_page_status(deps_page, deps_source_files)
        await self._write_page(deps_page)

    async def _generate_changelog_page(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate changelog page from git history."""
        if progress_callback:
            progress_callback("Generating changelog", 5, 14)

        page_path = "changelog.md"

        if (
            not ctx.full_rebuild
            and not self.status_manager.needs_regeneration_structural(
                page_path, index_status
            )
        ):
            existing_page = await self.status_manager.load_existing_page(page_path)
            if existing_page is not None:
                ctx.pages.append(existing_page)
                self.status_manager.record_summary_page_status(
                    existing_page, ctx.all_source_files, index_status
                )
                ctx.pages_skipped += 1
                return

        changelog_page = await self._generate_changelog()
        if changelog_page:
            ctx.pages.append(changelog_page)
            self.status_manager.record_summary_page_status(
                changelog_page, ctx.all_source_files, index_status
            )
            await self._write_page(changelog_page)
            ctx.pages_generated += 1

    async def _add_auxiliary_page(
        self,
        ctx: _GenerationContext,
        content: str | None,
        path: str,
        title: str,
        index_status: IndexStatus,
    ) -> None:
        """Record and write an auxiliary page if content was generated."""
        if not content:
            return
        page = WikiPage(
            path=path, title=title, content=content, generated_at=time.time()
        )
        ctx.pages.append(page)
        self.status_manager.record_summary_page_status(
            page, ctx.all_source_files, index_status
        )
        await self._write_page(page)
        ctx.pages_generated += 1

    async def _generate_auxiliary_pages(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate auxiliary pages: inheritance, glossary, coverage, dependency graph.

        All four pages are generated concurrently with ``asyncio.gather``
        since they are independent of each other.  Uses structural
        fingerprinting so content-only changes skip these pages.
        """
        import asyncio

        if progress_callback:
            progress_callback("Generating auxiliary pages", 6, 14)

        aux_pages = [
            ("inheritance.md", "Class Inheritance"),
            ("glossary.md", "Glossary"),
            ("coverage.md", "Documentation Coverage"),
            ("dependency-graph.md", "Dependency Graph"),
        ]

        # If structure unchanged, try to load all auxiliary pages from disk
        if (
            not ctx.full_rebuild
            and not self.status_manager.needs_regeneration_structural(
                aux_pages[0][0], index_status
            )
        ):
            all_loaded = True
            for page_path, _title in aux_pages:
                existing = await self.status_manager.load_existing_page(page_path)
                if existing is not None:
                    ctx.pages.append(existing)
                    self.status_manager.record_summary_page_status(
                        existing, ctx.all_source_files, index_status
                    )
                    ctx.pages_skipped += 1
                else:
                    all_loaded = False
                    break
            if all_loaded:
                return

            # Partial load failed — regenerate all; undo pages we added
            loaded_paths = {
                pp for pp, _ in aux_pages if pp in self.status_manager.page_statuses
            }
            ctx.pages = [p for p in ctx.pages if p.path not in loaded_paths]
            for pp in loaded_paths:
                self.status_manager.page_statuses.pop(pp, None)
            ctx.pages_skipped -= len(loaded_paths)

        async def _safe_dependency_graph() -> str | None:
            """Wrapper that catches dependency graph errors."""
            try:
                return await generate_dependency_graph_page(
                    index_status=index_status,
                    vector_store=self.vector_store,
                    show_external=True,
                    max_external=10,
                    wiki_base_path="files/",
                )
            except Exception as e:
                logger.debug("Failed to generate dependency graph: %s", e)
                ctx.warnings.append(f"Dependency graph generation failed: {e}")
                return None

        # Run all auxiliary generators concurrently
        (
            inheritance_content,
            glossary_content,
            coverage_content,
            dep_content,
        ) = await asyncio.gather(
            generate_inheritance_page(index_status, self.vector_store),
            generate_glossary_page(index_status, self.vector_store),
            generate_coverage_page(index_status, self.vector_store),
            _safe_dependency_graph(),
        )

        await self._add_auxiliary_page(
            ctx,
            inheritance_content,
            "inheritance.md",
            "Class Inheritance",
            index_status,
        )
        await self._add_auxiliary_page(
            ctx, glossary_content, "glossary.md", "Glossary", index_status
        )
        await self._add_auxiliary_page(
            ctx, coverage_content, "coverage.md", "Documentation Coverage", index_status
        )
        await self._add_auxiliary_page(
            ctx, dep_content, "dependency-graph.md", "Dependency Graph", index_status
        )

    @staticmethod
    def _sort_generators_by_dependencies(
        generators: list["WikiGeneratorPlugin"],
    ) -> list["WikiGeneratorPlugin"]:
        """Sort generators respecting run_after dependencies."""
        return sort_generators_by_dependencies(generators)

    async def _run_plugin_generators(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Run registered wiki generator plugins."""
        new_pages, pages_generated = await run_plugin_generators(
            pages=ctx.pages,
            all_source_files=ctx.all_source_files,
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            config=self.config,
            wiki_path=self.wiki_path,
            status_manager=self.status_manager,
            write_callback=self._write_page,
            progress_callback=progress_callback,
        )
        ctx.pages.extend(new_pages)
        ctx.pages_generated += pages_generated

    async def _generate_codemap_pages(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate codemap pages for auto-discovered entry points."""
        assert self._repo_path is not None, (
            "Repository path must be set before generating codemaps"
        )

        (
            codemap_pages,
            ctx.pages_generated,
            ctx.pages_skipped,
        ) = await generate_codemap_pages_phase(
            pages=ctx.pages,
            pages_generated=ctx.pages_generated,
            pages_skipped=ctx.pages_skipped,
            full_rebuild=ctx.full_rebuild,
            repo_path=self._repo_path,
            wiki_path=self.wiki_path,
            wiki_config=self.config.wiki,
            vector_store=self.vector_store,
            llm=self.llm,
            status_manager=self.status_manager,
            progress=self._progress,
            write_callback=self._write_page,
            progress_callback=progress_callback,
        )
        ctx.pages.extend(codemap_pages)

    async def _apply_cross_linking(
        self,
        pages: list[WikiPage],
        progress_callback: ProgressCallback | None,
    ) -> list[WikiPage]:
        """Apply cross-links, source refs, and see-also sections to pages."""
        return await apply_cross_linking(
            pages=pages,
            entity_registry=self.entity_registry,
            relationship_analyzer=self.relationship_analyzer,
            status_manager=self.status_manager,
            wiki_path=self.wiki_path,
            write_callback=self._write_page,
            progress_callback=progress_callback,
        )

    async def _generate_search_and_toc(
        self,
        pages: list[WikiPage],
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate search index and table of contents."""
        await generate_search_and_toc(
            pages=pages,
            index_status=index_status,
            vector_store=self.vector_store,
            wiki_path=self.wiki_path,
            progress_callback=progress_callback,
        )

    def _build_wiki_status(
        self,
        ctx: _GenerationContext,
        index_status: IndexStatus,
    ) -> WikiGenerationStatus:
        """Build the wiki generation status object."""
        return build_wiki_status(
            pages=ctx.pages,
            index_status=index_status,
            page_statuses=self.status_manager.page_statuses,
        )

    async def _generate_freshness_and_finalize(
        self,
        ctx: _GenerationContext,
        wiki_status: WikiGenerationStatus,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Generate freshness report and finalize wiki status."""
        assert self._repo_path is not None, (
            "Repository path must be set before generating wiki"
        )
        freshness_page, ctx.pages_generated = await generate_freshness_and_finalize(
            pages=ctx.pages,
            all_source_files=ctx.all_source_files,
            pages_generated=ctx.pages_generated,
            pages_skipped=ctx.pages_skipped,
            repo_path=self._repo_path,
            wiki_status=wiki_status,
            index_status=index_status,
            status_manager=self.status_manager,
            write_callback=self._write_page,
            progress_callback=progress_callback,
        )
        ctx.pages.append(freshness_page)

    async def _generate_overview(self, index_status: IndexStatus) -> WikiPage:
        """Generate the main overview/index page with grounded facts."""
        return await generate_overview_page(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._page_prompts.get("overview", self._system_prompt),
            manifest=self._manifest,
            repo_path=self._repo_path,
            max_chunk_content_chars=self.config.wiki.max_chunk_content_chars,
        )

    async def _generate_architecture(self, index_status: IndexStatus) -> WikiPage:
        """Generate architecture documentation with diagrams and grounded facts."""
        return await generate_architecture_page(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=self._page_prompts.get("architecture", self._system_prompt),
            manifest=self._manifest,
            repo_path=self._repo_path,
            max_chunk_content_chars=self.config.wiki.max_chunk_content_chars,
        )

    async def _generate_dependencies(
        self, index_status: IndexStatus
    ) -> tuple[WikiPage, list[str]]:
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
    max_file_pages: int | None = None,
) -> WikiStructure:
    """Convenience function to generate wiki documentation."""
    from local_deepwiki.core.git_utils import is_github_repo

    config = config or get_config()

    # Auto-switch to cloud provider for GitHub repos if configured
    effective_provider = llm_provider
    if effective_provider is None and config.wiki.use_cloud_for_github:
        if is_github_repo(repo_path):
            effective_provider = config.wiki.github_llm_provider
            logger.info(
                "GitHub repo detected, using cloud provider: %s", effective_provider
            )

    generator = WikiGenerator(
        wiki_path=wiki_path,
        vector_store=vector_store,
        config=config,
        llm_provider_name=effective_provider,
    )
    return await generator.generate(
        index_status, progress_callback, full_rebuild, max_file_pages=max_file_pages
    )
