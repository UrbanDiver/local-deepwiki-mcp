"""LLM providers."""

from local_deepwiki.config import LLMConfig, get_config
from local_deepwiki.providers.base import LLMProvider


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


__all__ = ["get_llm_provider", "LLMProvider"]
