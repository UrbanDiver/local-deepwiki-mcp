"""Tests for provider factory functions."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.config import (
    AnthropicConfig,
    EmbeddingConfig,
    LLMCacheConfig,
    LLMConfig,
    LocalEmbeddingConfig,
    OllamaConfig,
    OpenAIEmbeddingConfig,
    OpenAILLMConfig,
)


class TestGetLLMProvider:
    """Tests for get_llm_provider factory function."""

    def test_returns_ollama_provider(self):
        """Test that ollama provider is returned when configured."""
        from local_deepwiki.providers.llm import get_llm_provider
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        config = LLMConfig(
            provider="ollama",
            ollama=OllamaConfig(model="llama3.2", base_url="http://localhost:11434"),
        )

        provider = get_llm_provider(config)

        assert isinstance(provider, OllamaProvider)
        assert provider.name == "ollama:llama3.2"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_returns_anthropic_provider(self):
        """Test that anthropic provider is returned when configured."""
        from local_deepwiki.providers.llm import get_llm_provider
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        config = LLMConfig(
            provider="anthropic",
            anthropic=AnthropicConfig(model="claude-sonnet-4-20250514"),
        )

        provider = get_llm_provider(config)

        assert isinstance(provider, AnthropicProvider)
        assert provider.name == "anthropic:claude-sonnet-4-20250514"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_returns_openai_provider(self):
        """Test that openai provider is returned when configured."""
        from local_deepwiki.providers.llm import get_llm_provider
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        config = LLMConfig(
            provider="openai",
            openai=OpenAILLMConfig(model="gpt-4o"),
        )

        provider = get_llm_provider(config)

        assert isinstance(provider, OpenAILLMProvider)
        assert provider.name == "openai:gpt-4o"

    def test_raises_for_unknown_provider(self):
        """Test that ValueError is raised for unknown provider."""
        from local_deepwiki.providers.llm import get_llm_provider

        # Create config with invalid provider by bypassing validation
        config = LLMConfig()
        # Manually set invalid provider
        object.__setattr__(config, "provider", "unknown")

        with pytest.raises(ValueError, match="Unknown LLM provider: unknown"):
            get_llm_provider(config)

    def test_uses_global_config_when_none_provided(self):
        """Test that global config is used when no config provided."""
        from local_deepwiki.providers.llm import get_llm_provider
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        # Mock get_config to return a known config
        mock_config = MagicMock()
        mock_config.llm = LLMConfig(
            provider="ollama",
            ollama=OllamaConfig(model="test-model"),
        )

        with patch("local_deepwiki.providers.llm.get_config", return_value=mock_config):
            provider = get_llm_provider()

        assert isinstance(provider, OllamaProvider)
        assert provider.name == "ollama:test-model"


class TestGetCachedLLMProvider:
    """Tests for get_cached_llm_provider factory function."""

    @pytest.fixture
    def mock_embedding_provider(self):
        """Create a mock embedding provider."""
        provider = MagicMock()
        provider.embed.return_value = [0.1] * 384
        provider.dimension = 384
        return provider

    def test_returns_caching_provider_when_enabled(self, mock_embedding_provider, tmp_path: Path):
        """Test that caching provider is returned when caching enabled."""
        from local_deepwiki.providers.llm import get_cached_llm_provider
        from local_deepwiki.providers.llm.cached import CachingLLMProvider

        cache_path = tmp_path / "cache"
        cache_config = LLMCacheConfig(enabled=True)
        llm_config = LLMConfig(provider="ollama")

        provider = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=mock_embedding_provider,
            cache_config=cache_config,
            llm_config=llm_config,
        )

        assert isinstance(provider, CachingLLMProvider)

    def test_returns_base_provider_when_caching_disabled(
        self, mock_embedding_provider, tmp_path: Path
    ):
        """Test that base provider is returned when caching disabled."""
        from local_deepwiki.providers.llm import get_cached_llm_provider
        from local_deepwiki.providers.llm.cached import CachingLLMProvider
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        cache_path = tmp_path / "cache"
        cache_config = LLMCacheConfig(enabled=False)
        llm_config = LLMConfig(provider="ollama")

        provider = get_cached_llm_provider(
            cache_path=cache_path,
            embedding_provider=mock_embedding_provider,
            cache_config=cache_config,
            llm_config=llm_config,
        )

        # Should NOT be wrapped in caching provider
        assert not isinstance(provider, CachingLLMProvider)
        assert isinstance(provider, OllamaProvider)

    def test_uses_global_config_when_none_provided(self, mock_embedding_provider, tmp_path: Path):
        """Test that global config is used when no config provided."""
        from local_deepwiki.providers.llm import get_cached_llm_provider
        from local_deepwiki.providers.llm.cached import CachingLLMProvider

        cache_path = tmp_path / "cache"

        # Mock get_config to return known configs
        mock_config = MagicMock()
        mock_config.llm = LLMConfig(provider="ollama")
        mock_config.llm_cache = LLMCacheConfig(enabled=True)

        with patch("local_deepwiki.providers.llm.get_config", return_value=mock_config):
            provider = get_cached_llm_provider(
                cache_path=cache_path,
                embedding_provider=mock_embedding_provider,
            )

        assert isinstance(provider, CachingLLMProvider)


class TestGetEmbeddingProvider:
    """Tests for get_embedding_provider factory function."""

    def test_returns_local_provider(self):
        """Test that local provider is returned when configured."""
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        config = EmbeddingConfig(
            provider="local",
            local=LocalEmbeddingConfig(model="all-MiniLM-L6-v2"),
        )

        provider = get_embedding_provider(config)

        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider.name == "local:all-MiniLM-L6-v2"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_returns_openai_provider(self):
        """Test that openai provider is returned when configured."""
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        config = EmbeddingConfig(
            provider="openai",
            openai=OpenAIEmbeddingConfig(model="text-embedding-3-small"),
        )

        provider = get_embedding_provider(config)

        assert isinstance(provider, OpenAIEmbeddingProvider)
        assert provider.name == "openai:text-embedding-3-small"

    def test_raises_for_unknown_provider(self):
        """Test that ValueError is raised for unknown provider."""
        from local_deepwiki.providers.embeddings import get_embedding_provider

        # Create config with invalid provider by bypassing validation
        config = EmbeddingConfig()
        object.__setattr__(config, "provider", "unknown")

        with pytest.raises(ValueError, match="Unknown embedding provider: unknown"):
            get_embedding_provider(config)

    def test_uses_global_config_when_none_provided(self):
        """Test that global config is used when no config provided."""
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        # Mock get_config to return a known config
        mock_config = MagicMock()
        mock_config.embedding = EmbeddingConfig(
            provider="local",
            local=LocalEmbeddingConfig(model="test-model"),
        )

        with patch("local_deepwiki.providers.embeddings.get_config", return_value=mock_config):
            provider = get_embedding_provider()

        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider.name == "local:test-model"


class TestProviderExports:
    """Tests for module exports."""

    def test_llm_module_exports(self):
        """Test that LLM module exports expected names."""
        from local_deepwiki.providers import llm

        assert hasattr(llm, "get_llm_provider")
        assert hasattr(llm, "get_cached_llm_provider")
        assert hasattr(llm, "LLMProvider")
        assert hasattr(llm, "OllamaConnectionError")
        assert hasattr(llm, "OllamaModelNotFoundError")

    def test_embeddings_module_exports(self):
        """Test that embeddings module exports expected names."""
        from local_deepwiki.providers import embeddings

        assert hasattr(embeddings, "get_embedding_provider")
        assert hasattr(embeddings, "EmbeddingProvider")
