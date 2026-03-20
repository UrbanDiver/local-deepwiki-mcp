"""Lazy resource manager for wiki page generation.

Manages lazy-loaded resources (vector store, LLM, entity registry,
cross-linker, index status, etc.) used by LazyPageGenerator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from local_deepwiki.config import Config, get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.crosslinks import (
    CrossLinker,
    EntityRegistry,
    build_entity_registry_from_store,
)
from local_deepwiki.generators.wiki.files import filter_significant_files
from local_deepwiki.generators.wiki.utils import file_path_to_wiki_path
from local_deepwiki.logging import get_logger
from local_deepwiki.models import FileInfo, IndexStatus

if TYPE_CHECKING:
    from local_deepwiki.providers.base import LLMProvider

logger = get_logger(__name__)


class LazyResourceManager:
    """Manages lazy-loaded resources for wiki page generation.

    Centralizes lazy initialization of vector store, LLM provider,
    entity registry, cross-linker, index status, and derived mappings.
    """

    def __init__(self, wiki_path: Path, config: Config | None = None) -> None:
        self._wiki_path = wiki_path
        self._config = config or get_config()
        self._repo_path: Path | None = None
        self._vector_store: VectorStore | None = None
        self._entity_registry: EntityRegistry | None = None
        self._cross_linker: CrossLinker | None = None
        self._index_status: IndexStatus | None = None
        self._wiki_to_file: dict[str, FileInfo] | None = None
        self._significant_paths: set[str] | None = None

    @property
    def config(self) -> Config:
        """Return the configuration object."""
        return self._config

    @property
    def wiki_path(self) -> Path:
        """Return the wiki output path."""
        return self._wiki_path

    def get_repo_path(self) -> Path:
        """Return the repository path, loading from index status if needed."""
        if self._repo_path is None:
            idx = self.load_index_status()
            self._repo_path = Path(idx.repo_path)
        return self._repo_path

    def load_index_status(self) -> IndexStatus:
        """Load and cache IndexStatus from the wiki's index_status.json file."""
        if self._index_status is not None:
            return self._index_status
        status_path = self._wiki_path / "index_status.json"
        data = json.loads(status_path.read_text())
        self._index_status = IndexStatus.model_validate(data)
        self._repo_path = Path(self._index_status.repo_path)
        return self._index_status

    def get_index_status(self) -> IndexStatus:
        """Return cached IndexStatus, loading from disk on first call."""
        return self.load_index_status()

    def get_significant_paths(self) -> set[str]:
        """Return the set of file paths significant enough for individual wiki pages."""
        if self._significant_paths is None:
            idx = self.get_index_status()
            significant = filter_significant_files(
                idx.files, self._config.wiki.max_file_docs
            )
            self._significant_paths = {f.path for f in significant}
        return self._significant_paths

    def get_wiki_to_file(self) -> dict[str, FileInfo]:
        """Return a mapping from wiki page paths to their source FileInfo."""
        if self._wiki_to_file is None:
            idx = self.get_index_status()
            self._wiki_to_file = {file_path_to_wiki_path(f.path): f for f in idx.files}
        return self._wiki_to_file

    async def get_vector_store(self) -> VectorStore:
        """Return the vector store, lazily initializing the embedding provider."""
        if self._vector_store is None:
            from local_deepwiki.core.vectorstore import VectorStore as VS
            from local_deepwiki.providers.embeddings import get_embedding_provider

            repo_path = self.get_repo_path()
            db_path = self._config.get_vector_db_path(repo_path)
            embedding_provider = get_embedding_provider(self._config.embedding)
            self._vector_store = VS(db_path, embedding_provider)
        return self._vector_store

    async def get_entity_registry(self) -> EntityRegistry:
        """Load the entity registry from disk or build it from the vector store."""
        if self._entity_registry is None:
            reg_path = self._wiki_path / "entity_registry.json"
            if reg_path.exists():
                self._entity_registry = EntityRegistry.load(reg_path)
            else:
                logger.info("Building entity registry from vector store")
                vs = await self.get_vector_store()
                sig = self.get_significant_paths()
                self._entity_registry = build_entity_registry_from_store(
                    vs.get_all_chunks(), sig
                )
                self._entity_registry.save(reg_path)
        return self._entity_registry

    async def get_cross_linker(self) -> CrossLinker:
        """Return the cross-linker, initializing from the entity registry if needed."""
        if self._cross_linker is None:
            self._cross_linker = CrossLinker(await self.get_entity_registry())
        return self._cross_linker

    def get_llm(self) -> LLMProvider:
        """Return a cache-wrapped LLM provider for wiki generation."""
        from local_deepwiki.providers.llm import get_cached_llm_provider

        vs = self._vector_store
        if vs is None:
            raise RuntimeError("Vector store must be initialized before LLM")
        cache_path = self._wiki_path / "llm_cache.lance"
        return get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=vs.embedding_provider,
            cache_config=self._config.llm_cache,
            llm_config=self._config.llm,
        )

    def get_system_prompt(self) -> str:
        """Build the wiki generation system prompt for the current repository."""
        from local_deepwiki.prompts import PromptManager

        pm = PromptManager(custom_dir=None, repo_path=self.get_repo_path())
        return pm.get_wiki_system_prompt(provider=self._config.llm.provider)
