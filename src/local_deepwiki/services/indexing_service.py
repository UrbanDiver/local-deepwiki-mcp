"""Indexing service: repository indexing pipeline business logic.

Extracted from handlers/indexing.py _run_indexing_pipeline.
RBAC, audit logging, and MCP progress notifications remain in the handler.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_deepwiki.config import Config
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.logging import get_logger

from .models import IndexPipelineResult

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IndexPipelineRequest:
    """Immutable parameters for the indexing pipeline."""

    repo_path: Path
    full_rebuild: bool = False
    embedding_provider: str | None = None
    llm_provider: str | None = None
    generation_mode: str = "eager"
    progress_callback: Callable[[str, float], None] | None = None


class IndexingService:
    """Encapsulates the repository indexing pipeline.

    Depends only on Config; constructs RepositoryIndexer internally
    since the indexer manages its own embedding provider and vector store.
    """

    __slots__ = ("_config",)

    def __init__(self, config: Config) -> None:
        self._config = config

    async def run_pipeline(
        self,
        request: IndexPipelineRequest,
    ) -> IndexPipelineResult:
        """Execute the full indexing pipeline.

        Orchestrates: parse -> chunk -> embed -> store -> generate wiki.

        Args:
            request: Immutable request containing repo path, rebuild flag,
                provider overrides, generation mode, and progress callback.

        Returns:
            IndexPipelineResult with indexing statistics.
        """
        indexer = RepositoryIndexer(
            repo_path=request.repo_path,
            config=self._config,
            embedding_provider_name=request.embedding_provider,
        )

        progress_messages: list[str] = []
        cb = request.progress_callback

        def sync_progress(msg: str, current: int, total: int) -> None:
            progress_messages.append(f"[{current}/{total}] {msg}")
            if cb is not None:
                fraction = current / total if total > 0 else 0.0
                cb(msg, fraction)

        status = await indexer.index(
            full_rebuild=request.full_rebuild,
            progress_callback=sync_progress,
        )

        indexer.vector_store.stabilize()

        wiki_structure = await self._generate_wiki(
            repo_path=request.repo_path,
            indexer=indexer,
            status=status,
            llm_provider=request.llm_provider,
            sync_progress_callback=sync_progress,
            full_rebuild=request.full_rebuild,
        )

        return IndexPipelineResult(
            files_indexed=status.total_files,
            chunks_created=status.total_chunks,
            wiki_pages_generated=len(wiki_structure.pages),
            generation_mode=self._config.wiki.generation_mode.value,
            wiki_path=str(indexer.wiki_path),
            languages=dict(status.languages),
            messages=tuple(progress_messages),
        )

    async def _generate_wiki(
        self,
        repo_path: Path,
        indexer: RepositoryIndexer,
        status: Any,
        llm_provider: str | None,
        sync_progress_callback: Callable[[str, int, int], None],
        full_rebuild: bool,
    ) -> Any:
        """Dispatch wiki generation based on configured mode."""
        from local_deepwiki.config import GenerationMode
        from local_deepwiki.generators.wiki import generate_wiki

        gen_mode = self._config.wiki.generation_mode

        match gen_mode:
            case GenerationMode.LAZY:
                return self._generate_wiki_lazy(indexer, status)

            case GenerationMode.HYBRID:
                return await self._generate_wiki_hybrid(
                    repo_path,
                    indexer,
                    status,
                    llm_provider,
                    sync_progress_callback,
                    full_rebuild,
                )

            case _:
                return await generate_wiki(
                    repo_path=repo_path,
                    wiki_path=indexer.wiki_path,
                    vector_store=indexer.vector_store,
                    index_status=status,
                    config=self._config,
                    llm_provider=llm_provider,
                    progress_callback=sync_progress_callback,
                    full_rebuild=full_rebuild,
                )

    @staticmethod
    def _generate_wiki_lazy(
        indexer: RepositoryIndexer,
        status: Any,
    ) -> Any:
        """Lazy mode: build entity registry only, defer page generation."""
        from local_deepwiki.generators.crosslinks import (
            build_entity_registry_from_store,
        )
        from local_deepwiki.generators.wiki.files import filter_significant_files
        from local_deepwiki.models import WikiStructure

        config = indexer.config
        significant = filter_significant_files(status.files, config.wiki.max_file_docs)
        sig_paths = {f.path for f in significant}
        entity_reg = build_entity_registry_from_store(
            indexer.vector_store.get_all_chunks(), sig_paths
        )
        entity_reg.save(indexer.wiki_path / "entity_registry.json")

        return WikiStructure(root=str(indexer.wiki_path), pages=[])

    async def _generate_wiki_hybrid(
        self,
        repo_path: Path,
        indexer: RepositoryIndexer,
        status: Any,
        llm_provider: str | None,
        sync_progress_callback: Callable[[str, int, int], None],
        full_rebuild: bool,
    ) -> Any:
        """Hybrid mode: generate eager pages, then build entity registry."""
        from local_deepwiki.generators.crosslinks import (
            build_entity_registry_from_store,
        )
        from local_deepwiki.generators.wiki import generate_wiki
        from local_deepwiki.generators.wiki.files import filter_significant_files

        eager_limit = self._config.wiki.hybrid_eager_pages
        wiki_structure = await generate_wiki(
            repo_path=repo_path,
            wiki_path=indexer.wiki_path,
            vector_store=indexer.vector_store,
            index_status=status,
            config=self._config,
            llm_provider=llm_provider,
            progress_callback=sync_progress_callback,
            full_rebuild=full_rebuild,
            max_file_pages=eager_limit,
        )

        significant = filter_significant_files(
            status.files, self._config.wiki.max_file_docs
        )
        sig_paths = {f.path for f in significant}
        entity_reg = build_entity_registry_from_store(
            indexer.vector_store.get_all_chunks(), sig_paths
        )
        entity_reg.save(indexer.wiki_path / "entity_registry.json")

        remaining = len(significant) - eager_limit
        if remaining > 0:
            logger.info(
                "Hybrid mode: %d pages generated eagerly, %d deferred",
                eager_limit,
                remaining,
            )
            if self._config.wiki.prefetch_drain:
                from local_deepwiki.generators.lazy_generator import (
                    get_lazy_generator,
                )

                lazy_gen = get_lazy_generator(indexer.wiki_path, self._config)
                lazy_gen.kickstart_drain()

        return wiki_structure
