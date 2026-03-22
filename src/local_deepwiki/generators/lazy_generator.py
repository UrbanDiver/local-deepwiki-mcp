"""Lazy wiki page generator — generates pages on first read."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config, GenerationMode, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.lazy_cache import (
    append_to_search_index,
    read_cached_page,
    write_page,
)
from local_deepwiki.generators.lazy_resources import LazyResourceManager
from local_deepwiki.generators.wiki.utils import file_path_to_wiki_path
from local_deepwiki.generators.wiki.files import (
    FileDocContext,
    filter_significant_files,
    _generate_files_index,
    generate_single_file_doc,
)
from local_deepwiki.generators.wiki.modules import (
    _generate_modules_index,
    generate_single_module_doc,
)
from local_deepwiki.generators.wiki.pages import (
    generate_architecture_page,
    generate_changelog_page,
    generate_dependencies_page,
    generate_overview_page,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import WikiPage

logger = get_logger(__name__)

SUMMARY_PAGES = frozenset(
    {"index.md", "architecture.md", "dependencies.md", "changelog.md"}
)
AUXILIARY_PAGES = frozenset(
    {
        "glossary.md",
        "inheritance.md",
        "coverage.md",
        "dependency-graph.md",
    }
)


def _log_task_exception(task: asyncio.Task[Any]) -> None:
    """Log exceptions from fire-and-forget background tasks."""
    if not task.cancelled() and task.exception() is not None:
        logger.warning("Background task failed: %s", task.exception())


class LazyPageGenerator:
    """On-demand wiki page generator.

    Generates individual pages when first read, caches to disk, and
    optionally enqueues related pages for background prefetch.
    """

    def __init__(self, wiki_path: Path, config: Config | None = None) -> None:
        """Initialize the lazy generator with wiki output path and optional config."""
        self._wiki_path = wiki_path
        self._config = config or get_config()
        self._resources = LazyResourceManager(wiki_path, self._config)

        self._auxiliary_cache: dict[str, WikiPage] | None = None
        self._in_flight: dict[str, asyncio.Future[str]] = {}
        self._prefetch: Any = None

        wiki_cfg = self._config.wiki
        if (
            wiki_cfg.generation_mode != GenerationMode.EAGER
            and wiki_cfg.prefetch_workers > 0
        ):
            from local_deepwiki.generators.prefetch import PrefetchQueue

            self._prefetch = PrefetchQueue(
                generator=self,
                max_workers=wiki_cfg.prefetch_workers,
                max_queue=wiki_cfg.prefetch_max_queue,
                drain_enabled=wiki_cfg.prefetch_drain,
                drain_idle_seconds=wiki_cfg.drain_idle_seconds,
            )
            self._prefetch.start()

    def kickstart_drain(self) -> None:
        """Immediately trigger prefetch drain mode if enabled."""
        if self._prefetch is not None:
            self._prefetch.kickstart_drain()

    def get_drain_status(self) -> dict:
        """Return the current drain status as a serializable dict."""
        if self._prefetch is not None:
            return self._prefetch.drain_status.to_dict()
        return {"enabled": False, "state": "disabled"}

    async def get_page(self, page_path: str) -> str:
        """Get a wiki page, generating it on demand if needed."""
        cached = read_cached_page(self._wiki_path, page_path)
        if cached is not None:
            return cached

        if page_path in self._in_flight:
            return await self._in_flight[page_path]

        fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._in_flight[page_path] = fut
        try:
            page = await self._generate_page(page_path)
            linker = await self._resources.get_cross_linker()
            page = linker.add_links(page)
            await write_page(self._wiki_path, page)
            append_to_search_index(self._wiki_path, page)
            content = page.content
            fut.set_result(content)

            if self._prefetch is not None:
                cross_links = _extract_cross_link_targets(content)
                siblings = self._get_module_siblings(page_path)
                task = asyncio.create_task(
                    self._prefetch.enqueue_predictions(page_path, cross_links, siblings)
                )
                task.add_done_callback(_log_task_exception)

            return content
        except Exception as exc:  # noqa: BLE001 — lazy generation isolation: propagate to waiting future
            fut.set_exception(exc)
            raise
        finally:
            self._in_flight.pop(page_path, None)

    async def warm_page(self, page_path: str) -> None:
        """Generate a page in the background (no return)."""
        try:
            await self.get_page(page_path)
        except Exception:  # noqa: BLE001 — background warm-up must not propagate errors
            logger.debug("Warm failed for %s", page_path, exc_info=True)

    async def _generate_page(self, page_path: str) -> WikiPage:
        """Route to the correct generator based on page path."""
        vs = await self._resources.get_vector_store()

        if page_path in SUMMARY_PAGES:
            return await self._generate_summary(page_path, vs)

        if page_path in AUXILIARY_PAGES:
            pages = await self._generate_auxiliary_pages(vs)
            if page_path in pages:
                return pages[page_path]
            raise FileNotFoundError(f"Auxiliary page not generated: {page_path}")

        if page_path.startswith("modules/"):
            return await self._generate_module(page_path, vs)

        if page_path.startswith("files/"):
            if page_path == "files/index.md":
                return self._generate_files_index_page()
            return await self._generate_file(page_path, vs)

        raise FileNotFoundError(f"Unknown page type: {page_path}")

    async def _generate_summary(self, page_path: str, vs: VectorStore) -> WikiPage:
        """Generate a top-level summary page (overview, architecture, dependencies, or changelog)."""
        idx = self._resources.get_index_status()
        llm = self._resources.get_llm()
        prompt = self._resources.get_system_prompt()
        repo_path = self._resources.get_repo_path()

        from local_deepwiki.generators.manifest import get_cached_manifest
        from local_deepwiki.generators.wiki.context import WikiPipelineContext
        from local_deepwiki.generators.wiki.status import WikiStatusManager

        manifest = get_cached_manifest(repo_path, cache_dir=self._wiki_path)

        ctx = WikiPipelineContext(
            index_status=idx,
            vector_store=vs,
            llm=llm,
            system_prompt=prompt,
            repo_path=repo_path,
            wiki_path=self._wiki_path,
            config=self._config,
            wiki_config=self._config.wiki,
            manifest=manifest,
            status_manager=WikiStatusManager(self._wiki_path),
            full_rebuild=False,
            max_chunk_content_chars=self._config.wiki.max_chunk_content_chars,
        )

        if page_path == "index.md":
            return await generate_overview_page(ctx)
        elif page_path == "architecture.md":
            return await generate_architecture_page(ctx)
        elif page_path == "dependencies.md":
            page, _ = await generate_dependencies_page(
                ctx, import_search_limit=self._config.wiki.import_search_limit
            )
            return page
        elif page_path == "changelog.md":
            changelog_page = await generate_changelog_page(repo_path)
            if changelog_page is None:
                return WikiPage(
                    path="changelog.md",
                    title="Changelog",
                    content="# Changelog\n\nNo git history available.",
                    generated_at=time.time(),
                )
            return changelog_page
        raise FileNotFoundError(f"Unknown summary page: {page_path}")

    async def _generate_auxiliary_pages(self, vs: VectorStore) -> dict[str, WikiPage]:
        """Generate and cache all auxiliary pages (glossary, inheritance, coverage, dependency graph)."""
        if self._auxiliary_cache is not None:
            return self._auxiliary_cache

        from local_deepwiki.generators.analysis.coverage import generate_coverage_page
        from local_deepwiki.generators.analysis.dependency_graph import (
            generate_dependency_graph_page,
        )
        from local_deepwiki.generators.analysis.glossary import generate_glossary_page
        from local_deepwiki.generators.analysis.inheritance import (
            generate_inheritance_page,
        )

        idx = self._resources.get_index_status()
        pages: dict[str, WikiPage] = {}

        glossary_content = await generate_glossary_page(idx, vs)
        if glossary_content:
            pages["glossary.md"] = WikiPage(
                path="glossary.md",
                title="Glossary",
                content=glossary_content,
                generated_at=time.time(),
            )

        inheritance_content = await generate_inheritance_page(idx, vs)
        if inheritance_content:
            pages["inheritance.md"] = WikiPage(
                path="inheritance.md",
                title="Class Inheritance",
                content=inheritance_content,
                generated_at=time.time(),
            )

        coverage_content = await generate_coverage_page(idx, vs)
        if coverage_content:
            pages["coverage.md"] = WikiPage(
                path="coverage.md",
                title="Documentation Coverage",
                content=coverage_content,
                generated_at=time.time(),
            )

        try:
            dep_content = await generate_dependency_graph_page(
                index_status=idx,
                vector_store=vs,
                show_external=True,
                max_external=10,
                wiki_base_path="files/",
            )
            if dep_content:
                pages["dependency-graph.md"] = WikiPage(
                    path="dependency-graph.md",
                    title="Dependency Graph",
                    content=dep_content,
                    generated_at=time.time(),
                )
        except Exception:  # noqa: BLE001 — generator isolation: dependency graph failure must not block auxiliary pages
            logger.debug("Dependency graph generation failed", exc_info=True)

        self._auxiliary_cache = pages
        for page in pages.values():
            await write_page(self._wiki_path, page)
        return pages

    async def _generate_module(self, page_path: str, vs: VectorStore) -> WikiPage:
        """Generate a module documentation page or the modules index."""
        if page_path == "modules/index.md":
            return self._generate_modules_index_page()

        dir_name = Path(page_path).stem
        idx = self._resources.get_index_status()
        files = [
            f.path
            for f in idx.files
            if len(Path(f.path).parts) > 1 and Path(f.path).parts[0] == dir_name
        ]
        if not files:
            raise FileNotFoundError(f"No files for module: {dir_name}")

        llm = self._resources.get_llm()
        prompt = self._resources.get_system_prompt()
        page = await generate_single_module_doc(
            dir_name, files, vs, llm, prompt, repo_path=self._resources.get_repo_path()
        )
        if page is None:
            raise FileNotFoundError(f"Module generation failed: {dir_name}")
        return page

    async def _generate_file(self, page_path: str, vs: VectorStore) -> WikiPage:
        """Generate a single file documentation page from its source FileInfo."""
        w2f = self._resources.get_wiki_to_file()
        file_info = w2f.get(page_path)
        if file_info is None:
            raise FileNotFoundError(f"No source file for wiki page: {page_path}")

        idx = self._resources.get_index_status()
        llm = self._resources.get_llm()
        prompt = self._resources.get_system_prompt()
        registry = await self._resources.get_entity_registry()

        from local_deepwiki.generators.wiki.status import WikiStatusManager

        status_mgr = WikiStatusManager(self._wiki_path)
        status_mgr.file_hashes = {f.path: f.hash for f in idx.files}

        ctx = FileDocContext(
            index_status=idx,
            vector_store=vs,
            llm=llm,
            system_prompt=prompt,
            status_manager=status_mgr,
            entity_registry=registry,
            config=self._config,
            full_rebuild=True,
        )

        page, _was_skipped = await generate_single_file_doc(file_info, ctx)
        if page is None:
            raise FileNotFoundError(f"File generation produced no content: {page_path}")
        return page

    def _generate_files_index_page(self) -> WikiPage:
        """Build the files/index.md page listing all existing file documentation pages."""
        existing_pages = []
        files_dir = self._wiki_path / "files"
        if files_dir.exists():
            for md in files_dir.rglob("*.md"):
                if md.name == "index.md":
                    continue
                rel = str(md.relative_to(self._wiki_path))
                first_line = md.read_text().split("\n", 1)[0]
                title = (
                    first_line.lstrip("#").strip()
                    if first_line.startswith("#")
                    else rel
                )
                existing_pages.append(
                    WikiPage(
                        path=rel,
                        title=title,
                        content="",
                        generated_at=0,
                    )
                )
        return WikiPage(
            path="files/index.md",
            title="Source Files",
            content=_generate_files_index(existing_pages),
            generated_at=time.time(),
        )

    def _generate_modules_index_page(self) -> WikiPage:
        """Build the modules/index.md page listing all existing module documentation pages."""
        existing = []
        mods_dir = self._wiki_path / "modules"
        if mods_dir.exists():
            for md in mods_dir.glob("*.md"):
                if md.name == "index.md":
                    continue
                first_line = md.read_text().split("\n", 1)[0]
                title = (
                    first_line.lstrip("#").strip()
                    if first_line.startswith("#")
                    else md.stem
                )
                existing.append(
                    WikiPage(
                        path=f"modules/{md.name}",
                        title=title,
                        content="",
                        generated_at=0,
                    )
                )
        return WikiPage(
            path="modules/index.md",
            title="Modules",
            content=_generate_modules_index(existing),
            generated_at=time.time(),
        )

    def _get_module_siblings(self, page_path: str) -> list[str]:
        """Return wiki paths of sibling pages in the same section directory."""
        parts = Path(page_path).parts
        if len(parts) < 2:
            return []
        parent = parts[0]
        result = []
        parent_dir = self._wiki_path / parent
        if parent_dir.is_dir():
            for md in parent_dir.rglob("*.md"):
                rel = str(md.relative_to(self._wiki_path))
                if rel != page_path and rel.endswith(".md"):
                    result.append(rel)
        return result

    def get_virtual_structure(self) -> dict[str, Any]:
        """Return the full page tree without generating any pages."""
        idx = self._resources.get_index_status()
        sig = filter_significant_files(idx.files, self._config.wiki.max_file_docs)

        pages: list[dict[str, str]] = []

        for s_page in [
            "index.md",
            "architecture.md",
            "dependencies.md",
            "changelog.md",
        ]:
            pages.append({"path": s_page, "title": s_page.replace(".md", "").title()})

        for aux in sorted(AUXILIARY_PAGES):
            pages.append(
                {"path": aux, "title": aux.replace(".md", "").replace("-", " ").title()}
            )

        dirs: dict[str, list[str]] = {}
        for f in idx.files:
            parts = Path(f.path).parts
            d = parts[0] if len(parts) > 1 else "root"
            dirs.setdefault(d, []).append(f.path)
        for d, files in dirs.items():
            if len(files) >= 2:
                pages.append({"path": f"modules/{d}.md", "title": f"Module: {d}"})
        if dirs:
            pages.append({"path": "modules/index.md", "title": "Modules"})

        for f in sig:
            wp = file_path_to_wiki_path(f.path)
            pages.append({"path": wp, "title": f.path})
        pages.append({"path": "files/index.md", "title": "Source Files"})

        structure: dict[str, Any] = {"pages": [], "sections": {}}
        for page in sorted(pages, key=lambda p: p["path"]):
            parts = Path(page["path"]).parts
            if len(parts) == 1:
                structure["pages"].append(page)
            else:
                section = parts[0]
                structure.setdefault("sections", {}).setdefault(section, []).append(
                    page
                )

        return structure


def _extract_cross_link_targets(content: str) -> list[str]:
    """Extract wiki page paths from markdown links in content."""
    raw = re.findall(r"\[.*?\]\(([^)]*\.md)\)", content)
    result = []
    for p in raw:
        normalized = re.sub(r"^(\.\./)+", "", p)
        result.append(normalized)
    return result


_lazy_generators: dict[str, LazyPageGenerator] = {}


def get_active_generators() -> dict[str, LazyPageGenerator]:
    """Return the active lazy generator instances (keyed by resolved wiki path)."""
    return _lazy_generators


def get_lazy_generator(
    wiki_path: Path, config: Config | None = None
) -> LazyPageGenerator:
    """Return a shared LazyPageGenerator for the given wiki path, creating one if needed."""
    key = str(wiki_path.resolve())
    if key not in _lazy_generators:
        _lazy_generators[key] = LazyPageGenerator(wiki_path, config or get_config())
    return _lazy_generators[key]
