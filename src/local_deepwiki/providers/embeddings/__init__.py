"""Embedding providers."""

from pathlib import Path

from local_deepwiki.config import EmbeddingConfig, get_config
from local_deepwiki.providers.base import EmbeddingProvider
from local_deepwiki.providers.embeddings.cache import (
    CachedEmbeddingProvider,
    EmbeddingCacheConfig,
)


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
    if config.provider == "local":
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name=config.local.model)
    elif config.provider == "openai":
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model=config.openai.model)
    else:
        raise ValueError(f"Unknown embedding provider: {config.provider}")

    # Wrap with caching if enabled
    if enable_cache:
        # Use config values from global config
        cache_config = EmbeddingCacheConfig(
            cache_dir=cache_dir,
            ttl_seconds=global_config.embedding_cache.ttl_seconds,
            max_entries=global_config.embedding_cache.max_entries,
        )
        provider = CachedEmbeddingProvider(provider, cache_config)

    return provider


__all__ = [
    "get_embedding_provider",
    "EmbeddingProvider",
    "CachedEmbeddingProvider",
    "EmbeddingCacheConfig",
]
