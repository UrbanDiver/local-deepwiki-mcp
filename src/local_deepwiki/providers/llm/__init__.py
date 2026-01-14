"""LLM providers."""

from pathlib import Path

from local_deepwiki.config import LLMCacheConfig, LLMConfig, get_config
from local_deepwiki.providers.base import EmbeddingProvider, LLMProvider
from local_deepwiki.providers.llm.ollama import OllamaConnectionError, OllamaModelNotFoundError


def get_llm_provider(config: LLMConfig | None = None) -> LLMProvider:
    """Get the configured LLM provider.

    Args:
        config: Optional LLM config. Uses global config if not provided.

    Returns:
        The configured LLM provider instance.
    """
    if config is None:
        config = get_config().llm

    if config.provider == "ollama":
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        return OllamaProvider(
            model=config.ollama.model,
            base_url=config.ollama.base_url,
        )
    elif config.provider == "anthropic":
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        return AnthropicProvider(model=config.anthropic.model)
    elif config.provider == "openai":
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        return OpenAILLMProvider(model=config.openai.model)
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")


def get_cached_llm_provider(
    cache_path: Path,
    embedding_provider: EmbeddingProvider,
    cache_config: LLMCacheConfig | None = None,
    llm_config: LLMConfig | None = None,
) -> LLMProvider:
    """Get an LLM provider wrapped with caching.

    Args:
        cache_path: Path to the LanceDB cache database.
        embedding_provider: Provider for generating prompt embeddings.
        cache_config: Optional cache config. Uses global config if not provided.
        llm_config: Optional LLM config. Uses global config if not provided.

    Returns:
        A caching LLM provider wrapping the configured provider.
    """
    from local_deepwiki.core.llm_cache import LLMCache
    from local_deepwiki.providers.llm.cached import CachingLLMProvider

    if cache_config is None:
        cache_config = get_config().llm_cache

    # Get the underlying provider
    provider = get_llm_provider(llm_config)

    # If caching is disabled, return the provider as-is
    if not cache_config.enabled:
        return provider

    # Wrap with caching
    cache = LLMCache(cache_path, embedding_provider, cache_config)
    return CachingLLMProvider(provider, cache)


__all__ = [
    "get_llm_provider",
    "get_cached_llm_provider",
    "LLMProvider",
    "OllamaConnectionError",
    "OllamaModelNotFoundError",
]
