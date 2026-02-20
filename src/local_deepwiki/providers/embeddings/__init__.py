"""Embedding providers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from local_deepwiki.config import EmbeddingConfig, get_config

if TYPE_CHECKING:
    from local_deepwiki.plugins.base import EmbeddingProviderPlugin

from local_deepwiki.logging import get_logger
from local_deepwiki.plugins.registry import get_plugin_registry
from local_deepwiki.providers.base import EmbeddingProvider
from local_deepwiki.providers.embeddings.cache import (
    CachedEmbeddingProvider,
    EmbeddingCacheConfig,
)

logger = get_logger(__name__)


class _PluginEmbeddingProviderWrapper(EmbeddingProvider):
    """Wrapper to adapt EmbeddingProviderPlugin to EmbeddingProvider interface."""

    def __init__(self, plugin: "EmbeddingProviderPlugin") -> None:
        self._plugin = plugin

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using the plugin."""
        return await self._plugin.embed(texts)

    def get_dimension(self) -> int:
        """Get embedding dimension from the plugin."""
        return self._plugin.get_dimension()

    @property
    def name(self) -> str:
        """Get provider name from the plugin."""
        return self._plugin.provider_name


def _create_local(config: EmbeddingConfig) -> EmbeddingProvider:
    from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

    return LocalEmbeddingProvider(model_name=config.local.model)


def _create_openai(config: EmbeddingConfig) -> EmbeddingProvider:
    from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

    return OpenAIEmbeddingProvider(model=config.openai.model)


_EMBEDDING_FACTORIES: dict[str, Callable[[EmbeddingConfig], EmbeddingProvider]] = {
    "local": _create_local,
    "openai": _create_openai,
}


def get_embedding_provider(
    config: EmbeddingConfig | None = None,
    enable_cache: bool | None = None,
    cache_dir: Path | None = None,
) -> EmbeddingProvider:
    """Get the configured embedding provider.

    Args:
        config: Optional embedding config. Uses global config if not provided.
        enable_cache: Whether to wrap the provider with caching.
            If None, uses the global config's embedding_cache.enabled setting.
        cache_dir: Optional cache directory. Uses default if not provided.

    Returns:
        The configured embedding provider instance, optionally wrapped with caching.
    """
    global_config = get_config()
    if config is None:
        config = global_config.embedding

    # Determine if caching should be enabled
    if enable_cache is None:
        enable_cache = global_config.embedding_cache.enabled

    # Create the base provider
    provider: EmbeddingProvider

    # Check for plugin provider first
    registry = get_plugin_registry()
    plugin_provider = registry.get_embedding_provider(config.provider)

    if plugin_provider is not None:
        logger.debug(
            "Using plugin embedding provider: %s", plugin_provider.provider_name
        )
        provider = _PluginEmbeddingProviderWrapper(plugin_provider)
    else:
        factory = _EMBEDDING_FACTORIES.get(config.provider)
        if factory is None:
            raise ValueError(f"Unknown embedding provider: {config.provider}")
        provider = factory(config)

    # Wrap with caching if enabled
    if enable_cache:
        cache_kwargs: dict[str, Any] = {
            "ttl_seconds": global_config.embedding_cache.ttl_seconds,
            "max_entries": global_config.embedding_cache.max_entries,
        }
        if cache_dir is not None:
            cache_kwargs["cache_dir"] = cache_dir
        cache_config = EmbeddingCacheConfig(**cache_kwargs)
        provider = CachedEmbeddingProvider(provider, cache_config)

    return provider


__all__ = [
    "get_embedding_provider",
    "EmbeddingProvider",
    "CachedEmbeddingProvider",
    "EmbeddingCacheConfig",
]
