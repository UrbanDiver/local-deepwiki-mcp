"""Provider factory: centralized construction of LLM and embedding providers.

Eliminates duplicated provider setup scattered across handler modules.
Each handler now calls ProviderFactory instead of inline construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from local_deepwiki.config import Config
    from local_deepwiki.config.models_embedding import EmbeddingConfig
    from local_deepwiki.config.models_llm import LLMCacheConfig, LLMConfig
    from local_deepwiki.providers.base import EmbeddingProvider, LLMProvider

logger = get_logger(__name__)


class ProviderFactory:
    """Centralized factory for creating LLM and embedding providers.

    Replaces the duplicated inline construction of providers that was
    scattered across handler modules (core.py, codemap.py, research.py,
    analysis_diff.py).
    """

    __slots__ = ()

    @staticmethod
    def create_embedding_provider(
        config: "EmbeddingConfig | None" = None,
        *,
        enable_cache: bool | None = None,
        cache_dir: Path | None = None,
    ) -> "EmbeddingProvider":
        """Create an embedding provider from configuration.

        Args:
            config: Optional embedding config. Uses global config if not provided.
            enable_cache: Whether to wrap with caching. Uses config default if None.
            cache_dir: Optional cache directory override.

        Returns:
            Configured embedding provider instance.
        """
        from local_deepwiki.providers.embeddings import get_embedding_provider

        return get_embedding_provider(
            config, enable_cache=enable_cache, cache_dir=cache_dir
        )

    @staticmethod
    def create_llm_provider(
        llm_config: "LLMConfig | None" = None,
    ) -> "LLMProvider":
        """Create an LLM provider from configuration.

        Args:
            llm_config: Optional LLM config. Uses global config if not provided.

        Returns:
            Configured LLM provider instance.
        """
        from local_deepwiki.providers.llm import get_llm_provider

        return get_llm_provider(llm_config)

    @staticmethod
    def create_cached_llm_provider(
        cache_path: Path,
        embedding_provider: "EmbeddingProvider",
        *,
        cache_config: "LLMCacheConfig | None" = None,
        llm_config: "LLMConfig | None" = None,
    ) -> "LLMProvider":
        """Create an LLM provider wrapped with semantic caching.

        This is the most common pattern used in handlers: an LLM provider
        that caches responses using embedding similarity.

        Args:
            cache_path: Path to the LanceDB cache database.
            embedding_provider: Provider for generating prompt embeddings.
            cache_config: Optional cache config. Uses global config if not provided.
            llm_config: Optional LLM config. Uses global config if not provided.

        Returns:
            A caching LLM provider wrapping the configured provider.
        """
        from local_deepwiki.providers.llm import get_cached_llm_provider

        return get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=embedding_provider,
            cache_config=cache_config,
            llm_config=llm_config,
        )

    @staticmethod
    def create_providers_for_repo(
        config: "Config",
        wiki_path: Path,
    ) -> tuple["LLMProvider", "EmbeddingProvider"]:
        """Create both LLM and embedding providers for a repository.

        Convenience method that combines the common pattern of creating
        an embedding provider and then a cached LLM provider for a repo.

        Args:
            config: Application configuration object.
            wiki_path: Path to the wiki directory (for LLM cache location).

        Returns:
            Tuple of (cached_llm_provider, embedding_provider).
        """
        embedding_provider = ProviderFactory.create_embedding_provider(config.embedding)
        cache_path = wiki_path / "llm_cache.lance"
        llm = ProviderFactory.create_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=embedding_provider,
            cache_config=config.llm_cache,
            llm_config=config.llm,
        )
        return llm, embedding_provider
