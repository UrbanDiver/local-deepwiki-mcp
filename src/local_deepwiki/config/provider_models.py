"""Provider configuration models for embedding and LLM providers."""

from __future__ import annotations

from pydantic import BaseModel, Field

from local_deepwiki.models.provider_types import EmbeddingProviderType, LLMProviderType


class LocalEmbeddingConfig(BaseModel):
    """Configuration for local embedding model."""

    model_config = {"frozen": True}

    model: str = Field(
        default="multi-qa-MiniLM-L6-cos-v1",
        description="Model name for sentence-transformers. "
        "Default is multi-qa-MiniLM-L6-cos-v1 (512 tokens, Q&A-optimized) which "
        "provides better semantic coverage than all-MiniLM-L6-v2 (256 tokens).",
    )


class OpenAIEmbeddingConfig(BaseModel):
    """Configuration for OpenAI embedding model."""

    model_config = {"frozen": True}

    model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration."""

    model_config = {"frozen": True, "use_enum_values": True}

    provider: EmbeddingProviderType = Field(
        default=EmbeddingProviderType.LOCAL, description="Embedding provider"
    )
    local: LocalEmbeddingConfig = Field(default_factory=LocalEmbeddingConfig)
    openai: OpenAIEmbeddingConfig = Field(default_factory=OpenAIEmbeddingConfig)


class OllamaConfig(BaseModel):
    """Configuration for Ollama LLM."""

    model_config = {"frozen": True}

    model: str = Field(default="qwen3-coder:30b", description="Ollama model name")
    base_url: str = Field(
        default="http://localhost:11434", description="Ollama API URL"
    )


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic LLM."""

    model_config = {"frozen": True}

    model: str = Field(
        default="claude-sonnet-4-20250514", description="Anthropic model name"
    )


class OpenAILLMConfig(BaseModel):
    """Configuration for OpenAI LLM."""

    model_config = {"frozen": True}

    model: str = Field(default="gpt-4o", description="OpenAI model name")


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    model_config = {"frozen": True, "use_enum_values": True}

    provider: LLMProviderType = Field(
        default=LLMProviderType.OLLAMA, description="LLM provider"
    )
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openai: OpenAILLMConfig = Field(default_factory=OpenAILLMConfig)
