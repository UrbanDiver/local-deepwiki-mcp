"""Embedding providers."""

from local_deepwiki.config import EmbeddingConfig, get_config
from local_deepwiki.providers.base import EmbeddingProvider


def get_embedding_provider(config: EmbeddingConfig | None = None) -> EmbeddingProvider:
    """Get the configured embedding provider.

    Args:
        config: Optional embedding config. Uses global config if not provided.

    Returns:
        The configured embedding provider instance.
    """
    if config is None:
        config = get_config().embedding

    if config.provider == "local":
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        return LocalEmbeddingProvider(model_name=config.local.model)
    elif config.provider == "openai":
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(model=config.openai.model)
    else:
        raise ValueError(f"Unknown embedding provider: {config.provider}")


__all__ = ["get_embedding_provider", "EmbeddingProvider"]
