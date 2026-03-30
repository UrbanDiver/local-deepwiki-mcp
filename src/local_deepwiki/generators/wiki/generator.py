"""Wiki documentation generator using LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from local_deepwiki.generators.wiki.context import WikiPipelineContext

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.analysis.coverage import generate_coverage_page  # noqa: F401 — namespace target for phases.py
from local_deepwiki.generators.crosslinks import EntityRegistry
from local_deepwiki.generators.analysis.dependency_graph import (  # noqa: F401 — namespace target for phases.py
    generate_dependency_graph_page,
)
from local_deepwiki.generators.analysis.glossary import generate_glossary_page  # noqa: F401 — namespace target for phases.py
from local_deepwiki.generators.analysis.inheritance import generate_inheritance_page  # noqa: F401 — namespace target for phases.py
from local_deepwiki.generators.manifest import ProjectManifest
from local_deepwiki.generators.manifest import get_cached_manifest  # noqa: F401 — test patch target
from local_deepwiki.generators.see_also import RelationshipAnalyzer
from local_deepwiki.generators.wiki.files import generate_file_docs  # noqa: F401 — test patch target
from local_deepwiki.generators.wiki.modules import generate_module_docs  # noqa: F401 — test patch target
from local_deepwiki.generators.wiki.pages import (
    generate_architecture_page,
    generate_changelog_page,
    generate_dependencies_page,
    generate_overview_page,
)
from local_deepwiki.generators.wiki.status import WikiStatusManager
from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    IndexStatus,
    ProgressCallback,
    WikiPage,
    WikiStructure,
)
from local_deepwiki.prompts import PromptManager
from local_deepwiki.providers.llm import get_cached_llm_provider

logger = get_logger(__name__)


@runtime_checkable
class WikiGeneratorProtocol(Protocol):
    """Protocol defining the interface for wiki documentation generators.

    Components that trigger wiki generation should accept this Protocol so
    that lightweight test stubs and alternative implementations (e.g. a no-op
    generator for CI) can be substituted without inheriting from the concrete
    ``WikiGenerator`` class.
    """

    async def generate(
        self,
        index_status: IndexStatus,
        progress_callback: ProgressCallback | None = None,
        full_rebuild: bool = False,
        max_file_pages: int | None = None,
    ) -> WikiStructure:
        """Generate wiki documentation and return the resulting structure."""
        ...


@dataclass(frozen=True, slots=True)
class WikiGenerationOptions:
    """Options for wiki generation, replacing the large function signature.

    Encapsulates all parameters needed by ``generate_wiki()`` into a single
    frozen dataclass.  The function still accepts individual keyword arguments
    for backward compatibility, but new callers should prefer passing an
    ``options`` instance.
    """

    repo_path: Path
    wiki_path: Path
    vector_store: "VectorStore"
    index_status: "IndexStatus"
    config: Config | None = None
    llm_provider: str | None = None
    progress_callback: ProgressCallback | None = None
    full_rebuild: bool = False
    max_file_pages: int | None = None


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
        "index_status",
        "progress_callback",
        "pipeline_ctx",
    )

    def __init__(
        self,
        pages: list["WikiPage"],
        pages_generated: int,
        pages_skipped: int,
        all_source_files: list[str],
        full_rebuild: bool,
        index_status: "IndexStatus | None" = None,
        progress_callback: "ProgressCallback | None" = None,
        pipeline_ctx: "WikiPipelineContext | None" = None,
    ):
        self.pages = pages
        self.pages_generated = pages_generated
        self.pages_skipped = pages_skipped
        self.all_source_files = all_source_files
        self.full_rebuild = full_rebuild
        self.warnings: list[str] = []
        self.index_status = index_status
        self.progress_callback = progress_callback
        self.pipeline_ctx = pipeline_ctx


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
            self.config = base_config.with_llm_provider(llm_provider_name)
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
        """Generate wiki documentation for the indexed repository.

        Delegates the full multi-phase pipeline to
        :func:`~local_deepwiki.generators.wiki.pipeline.run_generation_pipeline`.
        """
        from local_deepwiki.generators.wiki.pipeline import run_generation_pipeline

        return await run_generation_pipeline(
            generator=self,
            index_status=index_status,
            progress_callback=progress_callback,
            full_rebuild=full_rebuild,
            max_file_pages=max_file_pages,
        )

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
            pass

    async def _init_generation_context(
        self, index_status: IndexStatus, full_rebuild: bool
    ) -> _GenerationContext:
        """Initialize the generation context with tracking state."""
        from local_deepwiki.generators.wiki.pipeline import init_generation_context

        return await init_generation_context(self, index_status, full_rebuild)

    def _ensure_pipeline_ctx(
        self, ctx: _GenerationContext, index_status: IndexStatus
    ) -> None:
        """Lazily build ``pipeline_ctx`` on *ctx* when tests bypass init."""
        if ctx.pipeline_ctx is not None:
            return
        from local_deepwiki.generators.wiki.context import WikiPipelineContext

        # Fallback for tests that skip init_generation_context.
        # Use getattr throughout because __new__-created instances may
        # lack attributes that __init__ normally sets.
        repo_path = getattr(self, "_repo_path", None) or Path(index_status.repo_path)
        config = getattr(self, "config", None)
        wiki_config = getattr(config, "wiki", None)
        ctx.pipeline_ctx = WikiPipelineContext(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=getattr(self, "llm", None),  # type: ignore[arg-type]
            system_prompt=getattr(self, "_system_prompt", ""),
            repo_path=repo_path,
            wiki_path=self.wiki_path,
            config=config,  # type: ignore[arg-type]
            wiki_config=wiki_config,  # type: ignore[arg-type]
            manifest=getattr(self, "_manifest", None),
            status_manager=self.status_manager,
            full_rebuild=ctx.full_rebuild,
            max_chunk_content_chars=(
                wiki_config.max_chunk_content_chars if wiki_config else 15000
            ),
        )

    def _build_pipeline_context(
        self,
        index_status: IndexStatus,
        *,
        system_prompt: str | None = None,
        full_rebuild: bool = False,
    ) -> "WikiPipelineContext":
        """Build an immutable pipeline context from generator state.

        Args:
            index_status: Current repository index status.
            system_prompt: Override system prompt (defaults to ``self._system_prompt``).
            full_rebuild: Whether this is a full rebuild.

        Returns:
            A frozen ``WikiPipelineContext`` dataclass.
        """
        from local_deepwiki.generators.wiki.context import WikiPipelineContext

        assert self._repo_path is not None, (
            "Repository path must be set before building pipeline context"
        )
        return WikiPipelineContext(
            index_status=index_status,
            vector_store=self.vector_store,
            llm=self.llm,
            system_prompt=system_prompt
            if system_prompt is not None
            else self._system_prompt,
            repo_path=self._repo_path,
            wiki_path=self.wiki_path,
            config=self.config,
            wiki_config=self.config.wiki,
            manifest=self._manifest,
            status_manager=self.status_manager,
            full_rebuild=full_rebuild,
            max_chunk_content_chars=self.config.wiki.max_chunk_content_chars,
        )

    async def _generate_overview(self, index_status: IndexStatus) -> WikiPage:
        """Generate the main overview/index page with grounded facts."""
        return await generate_overview_page(
            self._build_pipeline_context(
                index_status,
                system_prompt=self._page_prompts.get("overview", self._system_prompt),
            )
        )

    async def _generate_architecture(self, index_status: IndexStatus) -> WikiPage:
        """Generate architecture documentation with diagrams and grounded facts."""
        return await generate_architecture_page(
            self._build_pipeline_context(
                index_status,
                system_prompt=self._page_prompts.get(
                    "architecture", self._system_prompt
                ),
            )
        )

    async def _generate_dependencies(
        self, index_status: IndexStatus
    ) -> tuple[WikiPage, list[str]]:
        """Generate dependencies documentation with grounded facts from manifest."""
        return await generate_dependencies_page(
            self._build_pipeline_context(index_status),
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
    repo_path: Path | None = None,
    wiki_path: Path | None = None,
    vector_store: VectorStore | None = None,
    index_status: IndexStatus | None = None,
    *,
    options: WikiGenerationOptions | None = None,
    config: Config | None = None,
    llm_provider: str | None = None,
    progress_callback: ProgressCallback | None = None,
    full_rebuild: bool = False,
    max_file_pages: int | None = None,
) -> WikiStructure:
    """Convenience function to generate wiki documentation.

    Accepts either a ``WikiGenerationOptions`` instance via ``options`` or
    individual keyword arguments for backward compatibility.  When ``options``
    is provided, its values take precedence and individual keyword arguments
    are ignored.
    """
    from local_deepwiki.core.git_utils import is_github_repo

    # Build options from individual kwargs when not provided directly
    if options is not None:
        opts = options
    else:
        if repo_path is None:
            raise TypeError("repo_path is required when options is not provided")
        if wiki_path is None:
            raise TypeError("wiki_path is required when options is not provided")
        if vector_store is None:
            raise TypeError("vector_store is required when options is not provided")
        if index_status is None:
            raise TypeError("index_status is required when options is not provided")
        opts = WikiGenerationOptions(
            repo_path=repo_path,
            wiki_path=wiki_path,
            vector_store=vector_store,
            index_status=index_status,
            config=config,
            llm_provider=llm_provider,
            progress_callback=progress_callback,
            full_rebuild=full_rebuild,
            max_file_pages=max_file_pages,
        )

    resolved_config = opts.config or get_config()

    # Auto-switch to cloud provider for GitHub repos if configured
    effective_provider = opts.llm_provider
    if effective_provider is None and resolved_config.wiki.use_cloud_for_github:
        if is_github_repo(opts.repo_path):
            effective_provider = resolved_config.wiki.github_llm_provider
            logger.info(
                "GitHub repo detected, using cloud provider: %s", effective_provider
            )

    generator = WikiGenerator(
        wiki_path=opts.wiki_path,
        vector_store=opts.vector_store,
        config=resolved_config,
        llm_provider_name=effective_provider,
    )
    return await generator.generate(
        opts.index_status,
        opts.progress_callback,
        opts.full_rebuild,
        max_file_pages=opts.max_file_pages,
    )
