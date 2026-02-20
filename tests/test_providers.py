"""Comprehensive tests for provider interface contracts."""

import os
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.providers.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    LLMProvider,
    LLMProviderCapabilities,
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
)


# =============================================================================
# Test Standardized Exceptions
# =============================================================================


class TestProviderExceptions:
    """Tests for standardized provider exceptions."""

    def test_provider_error_base(self):
        """Test ProviderError base class."""
        error = ProviderError("Test error", provider_name="test-provider")
        assert "Test error" in str(error)
        assert error.provider_name == "test-provider"

    def test_provider_connection_error(self):
        """Test ProviderConnectionError."""
        original = ConnectionError("Connection failed")
        error = ProviderConnectionError(
            "Cannot connect",
            provider_name="test",
            original_error=original,
        )
        assert "Cannot connect" in str(error)
        assert error.provider_name == "test"
        assert error.original_error is original

    def test_provider_rate_limit_error(self):
        """Test ProviderRateLimitError."""
        error = ProviderRateLimitError(
            "Rate limited",
            provider_name="test",
            retry_after=30.0,
        )
        assert "Rate limited" in str(error)
        assert error.retry_after == 30.0

    def test_provider_model_not_found_error_without_models(self):
        """Test ProviderModelNotFoundError without available models."""
        error = ProviderModelNotFoundError("gpt-5", provider_name="test")
        assert "gpt-5" in str(error)
        assert "not found" in str(error)
        assert error.model == "gpt-5"

    def test_provider_model_not_found_error_with_models(self):
        """Test ProviderModelNotFoundError with available models."""
        error = ProviderModelNotFoundError(
            "gpt-5",
            provider_name="test",
            available_models=["gpt-4", "gpt-3.5"],
        )
        assert "gpt-5" in str(error)
        assert "gpt-4" in str(error)
        assert "gpt-3.5" in str(error)
        assert error.available_models == ["gpt-4", "gpt-3.5"]

    def test_provider_model_not_found_error_truncates_long_list(self):
        """Test that long model list is truncated."""
        models = [f"model-{i}" for i in range(20)]
        error = ProviderModelNotFoundError("new-model", available_models=models)
        assert "20 total" in str(error)

    def test_provider_authentication_error(self):
        """Test ProviderAuthenticationError."""
        error = ProviderAuthenticationError(
            "Invalid API key",
            provider_name="test",
        )
        assert "Invalid API key" in str(error)

    def test_provider_configuration_error(self):
        """Test ProviderConfigurationError."""
        error = ProviderConfigurationError(
            "Missing config",
            provider_name="test",
        )
        assert "Missing config" in str(error)


# =============================================================================
# Test Provider Capabilities
# =============================================================================


class TestProviderCapabilities:
    """Tests for provider capability dataclasses."""

    def test_llm_provider_capabilities_defaults(self):
        """Test LLMProviderCapabilities default values."""
        caps = LLMProviderCapabilities()
        assert caps.supports_streaming is True
        assert caps.supports_system_prompt is True
        assert caps.max_tokens == 4096
        assert caps.max_context_length == 128000
        assert caps.models == []
        assert caps.supports_function_calling is False
        assert caps.supports_vision is False

    def test_llm_provider_capabilities_custom(self):
        """Test LLMProviderCapabilities with custom values."""
        caps = LLMProviderCapabilities(
            supports_streaming=False,
            supports_system_prompt=False,
            max_tokens=8192,
            max_context_length=200000,
            models=["model-1", "model-2"],
            supports_function_calling=True,
            supports_vision=True,
        )
        assert caps.supports_streaming is False
        assert caps.supports_system_prompt is False
        assert caps.max_tokens == 8192
        assert caps.max_context_length == 200000
        assert caps.models == ["model-1", "model-2"]
        assert caps.supports_function_calling is True
        assert caps.supports_vision is True

    def test_embedding_provider_capabilities_defaults(self):
        """Test EmbeddingProviderCapabilities default values."""
        caps = EmbeddingProviderCapabilities()
        assert caps.max_batch_size == 100
        assert caps.max_tokens_per_text == 8192
        assert caps.dimension == 0
        assert caps.models == []
        assert caps.supports_truncation is True

    def test_embedding_provider_capabilities_custom(self):
        """Test EmbeddingProviderCapabilities with custom values."""
        caps = EmbeddingProviderCapabilities(
            max_batch_size=500,
            max_tokens_per_text=512,
            dimension=768,
            models=["model-a", "model-b"],
            supports_truncation=False,
        )
        assert caps.max_batch_size == 500
        assert caps.max_tokens_per_text == 512
        assert caps.dimension == 768
        assert caps.models == ["model-a", "model-b"]
        assert caps.supports_truncation is False


# =============================================================================
# Test LLM Provider Contract
# =============================================================================


class TestLLMProviderContract:
    """Tests for LLM provider base class contract."""

    @patch.dict(
        os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey1234567890abcdef"}
    )
    def test_anthropic_provider_implements_interface(self):
        """Test that AnthropicProvider implements all abstract methods."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Check all required methods exist
        assert hasattr(provider, "generate")
        assert hasattr(provider, "generate_stream")
        assert hasattr(provider, "name")
        assert hasattr(provider, "validate_connectivity")
        assert hasattr(provider, "validate_model")
        assert hasattr(provider, "capabilities")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_provider_implements_interface(self):
        """Test that OpenAILLMProvider implements all abstract methods."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider()

        assert hasattr(provider, "generate")
        assert hasattr(provider, "generate_stream")
        assert hasattr(provider, "name")
        assert hasattr(provider, "validate_connectivity")
        assert hasattr(provider, "validate_model")
        assert hasattr(provider, "capabilities")

    def test_ollama_provider_implements_interface(self):
        """Test that OllamaProvider implements all abstract methods."""
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        provider = OllamaProvider()

        assert hasattr(provider, "generate")
        assert hasattr(provider, "generate_stream")
        assert hasattr(provider, "name")
        assert hasattr(provider, "validate_connectivity")
        assert hasattr(provider, "validate_model")
        assert hasattr(provider, "capabilities")

    @patch.dict(
        os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey1234567890abcdef"}
    )
    def test_anthropic_capabilities(self):
        """Test AnthropicProvider capabilities."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        caps = provider.capabilities

        assert isinstance(caps, LLMProviderCapabilities)
        assert caps.supports_streaming is True
        assert caps.supports_system_prompt is True
        assert caps.supports_function_calling is True
        assert caps.supports_vision is True
        assert len(caps.models) > 0

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_capabilities(self):
        """Test OpenAILLMProvider capabilities."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")
        caps = provider.capabilities

        assert isinstance(caps, LLMProviderCapabilities)
        assert caps.supports_streaming is True
        assert caps.supports_function_calling is True
        assert caps.supports_vision is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_o1_capabilities(self):
        """Test OpenAILLMProvider capabilities for O1 models."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="o1")
        caps = provider.capabilities

        # O1 models have different capabilities
        assert caps.supports_streaming is False
        assert caps.supports_system_prompt is False

    def test_ollama_capabilities(self):
        """Test OllamaProvider capabilities."""
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        provider = OllamaProvider()
        caps = provider.capabilities

        assert isinstance(caps, LLMProviderCapabilities)
        assert caps.supports_streaming is True
        assert caps.supports_system_prompt is True


# =============================================================================
# Test Embedding Provider Contract
# =============================================================================


class TestEmbeddingProviderContract:
    """Tests for embedding provider base class contract."""

    def test_local_provider_implements_interface(self):
        """Test that LocalEmbeddingProvider implements all abstract methods."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()

        assert hasattr(provider, "embed")
        assert hasattr(provider, "dimension")
        assert hasattr(provider, "name")
        assert hasattr(provider, "validate_connectivity")
        assert hasattr(provider, "max_batch_size")
        assert hasattr(provider, "max_tokens")
        assert hasattr(provider, "capabilities")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_embedding_provider_implements_interface(self):
        """Test that OpenAIEmbeddingProvider implements all abstract methods."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider()

        assert hasattr(provider, "embed")
        assert hasattr(provider, "dimension")
        assert hasattr(provider, "name")
        assert hasattr(provider, "validate_connectivity")
        assert hasattr(provider, "max_batch_size")
        assert hasattr(provider, "max_tokens")
        assert hasattr(provider, "capabilities")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_embedding_capabilities(self):
        """Test OpenAIEmbeddingProvider capabilities."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        caps = provider.capabilities

        assert isinstance(caps, EmbeddingProviderCapabilities)
        assert caps.dimension == 1536
        assert caps.max_batch_size == 2048
        assert caps.max_tokens_per_text == 8191
        assert len(caps.models) > 0


# =============================================================================
# Test Standardized Error Handling
# =============================================================================


class TestStandardizedErrorHandling:
    """Tests for standardized error handling across providers."""

    @patch.dict(
        os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey1234567890abcdef"}
    )
    async def test_anthropic_authentication_error(self):
        """Test Anthropic provider raises ProviderAuthenticationError."""
        from anthropic import AuthenticationError

        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Create a proper mock for AuthenticationError
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_error = AuthenticationError(
            "Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}},
        )
        provider._client.messages.create = AsyncMock(side_effect=mock_error)

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider.generate("test")

        assert "authentication" in str(exc_info.value).lower()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_openai_authentication_error(self):
        """Test OpenAI provider raises ProviderAuthenticationError."""
        from openai import AuthenticationError

        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider()

        # Create a proper mock for AuthenticationError
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_error = AuthenticationError(
            "Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}},
        )
        provider._client.chat.completions.create = AsyncMock(side_effect=mock_error)

        with pytest.raises(ProviderAuthenticationError):
            await provider.generate("test")

    def test_ollama_connection_error_is_provider_connection_error(self):
        """Test that OllamaConnectionError is a ProviderConnectionError."""
        from local_deepwiki.providers.llm.ollama import OllamaConnectionError

        error = OllamaConnectionError("http://localhost:11434")

        assert isinstance(error, ProviderConnectionError)
        assert error.provider_name == "ollama"

    def test_ollama_model_not_found_is_provider_model_not_found(self):
        """Test that OllamaModelNotFoundError is a ProviderModelNotFoundError."""
        from local_deepwiki.providers.llm.ollama import OllamaModelNotFoundError

        error = OllamaModelNotFoundError("llama3", available_models=["mistral"])

        assert isinstance(error, ProviderModelNotFoundError)
        assert error.provider_name == "ollama"
        assert error.model == "llama3"


# =============================================================================
# Test Validation Methods
# =============================================================================


class TestValidationMethods:
    """Tests for provider validation methods."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
    async def test_anthropic_validate_no_api_key(self):
        """Test Anthropic initialization fails without API key (early validation)."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        # With secure implementation, ProviderAuthenticationError is raised at init time
        with pytest.raises(ProviderAuthenticationError):
            AnthropicProvider(api_key=None)

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    async def test_openai_validate_no_api_key(self):
        """Test OpenAI initialization fails without API key (early validation)."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        # With secure implementation, ProviderAuthenticationError is raised at init time
        with pytest.raises(ProviderAuthenticationError):
            OpenAILLMProvider(api_key=None)

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    async def test_openai_embedding_validate_no_api_key(self):
        """Test OpenAI embedding initialization fails without API key (early validation)."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        # With secure implementation, ProviderAuthenticationError is raised at init time
        with pytest.raises(ProviderAuthenticationError):
            OpenAIEmbeddingProvider(api_key=None)

    @dataclass
    class MockModel:
        """Mock ollama Model object."""

        model: str

    @dataclass
    class MockListResponse:
        """Mock ollama ListResponse object."""

        models: list

    async def test_ollama_validate_connectivity_success(self):
        """Test Ollama validate_connectivity success."""
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        provider = OllamaProvider()

        with patch.object(provider._client, "list") as mock_list:
            mock_list.return_value = self.MockListResponse(
                models=[self.MockModel(model="llama3.2")]
            )
            result = await provider.validate_connectivity()
            assert result is True

    async def test_ollama_validate_connectivity_failure(self):
        """Test Ollama validate_connectivity failure."""
        from local_deepwiki.providers.llm.ollama import (
            OllamaConnectionError,
            OllamaProvider,
        )

        provider = OllamaProvider()

        with patch.object(provider._client, "list") as mock_list:
            mock_list.side_effect = ConnectionError("Connection refused")

            with pytest.raises(OllamaConnectionError):
                await provider.validate_connectivity()

    async def test_ollama_validate_model_success(self):
        """Test Ollama validate_model success."""
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        provider = OllamaProvider()

        with patch.object(provider._client, "list") as mock_list:
            mock_list.return_value = self.MockListResponse(
                models=[self.MockModel(model="llama3.2:latest")]
            )
            result = await provider.validate_model("llama3.2")
            assert result is True

    async def test_ollama_validate_model_not_found(self):
        """Test Ollama validate_model when model not found."""
        from local_deepwiki.providers.llm.ollama import (
            OllamaModelNotFoundError,
            OllamaProvider,
        )

        provider = OllamaProvider()

        with patch.object(provider._client, "list") as mock_list:
            mock_list.return_value = self.MockListResponse(
                models=[self.MockModel(model="mistral:latest")]
            )

            with pytest.raises(OllamaModelNotFoundError):
                await provider.validate_model("llama3.2")

    @patch.dict(
        os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey1234567890abcdef"}
    )
    async def test_anthropic_validate_model_known(self):
        """Test Anthropic validate_model for known model."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        result = await provider.validate_model("claude-sonnet-4-20250514")
        assert result is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_openai_validate_model_known(self):
        """Test OpenAI validate_model for known model."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider()
        result = await provider.validate_model("gpt-4o")
        assert result is True


# =============================================================================
# Test get_max_batch_size and get_max_tokens
# =============================================================================


class TestEmbeddingProviderMethods:
    """Tests for embedding provider methods."""

    def test_local_embedding_max_batch_size(self):
        """Test LocalEmbeddingProvider max batch size."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.max_batch_size == 1000

    def test_local_embedding_max_tokens(self):
        """Test LocalEmbeddingProvider max tokens."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        assert provider.max_tokens == 256

    def test_local_embedding_max_tokens_unknown_model(self):
        """Test LocalEmbeddingProvider max tokens for unknown model."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="unknown-model")
        # Should return default
        assert provider.max_tokens == 512

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_embedding_max_batch_size(self):
        """Test OpenAIEmbeddingProvider max batch size."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider()
        assert provider.max_batch_size == 2048

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_embedding_max_tokens(self):
        """Test OpenAIEmbeddingProvider max tokens."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.max_tokens == 8191

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_embedding_dimension(self):
        """Test OpenAIEmbeddingProvider dimension."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-large")
        assert provider.dimension == 3072


# =============================================================================
# Test Exception Hierarchy
# =============================================================================


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_exceptions_inherit_from_provider_error(self):
        """Test all custom exceptions inherit from ProviderError."""
        assert issubclass(ProviderConnectionError, ProviderError)
        assert issubclass(ProviderRateLimitError, ProviderError)
        assert issubclass(ProviderModelNotFoundError, ProviderError)
        assert issubclass(ProviderAuthenticationError, ProviderError)
        assert issubclass(ProviderConfigurationError, ProviderError)

    def test_provider_error_inherits_from_exception(self):
        """Test ProviderError inherits from Exception."""
        assert issubclass(ProviderError, Exception)

    def test_can_catch_all_provider_errors(self):
        """Test that all provider errors can be caught with ProviderError."""
        errors = [
            ProviderConnectionError("test"),
            ProviderRateLimitError("test"),
            ProviderModelNotFoundError("model"),
            ProviderAuthenticationError("test"),
            ProviderConfigurationError("test"),
        ]

        for error in errors:
            try:
                raise error
            except ProviderError as e:
                assert isinstance(e, ProviderError)


# =============================================================================
# Test Provider Names
# =============================================================================


class TestProviderNames:
    """Tests for provider name properties."""

    @patch.dict(
        os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey1234567890abcdef"}
    )
    def test_anthropic_provider_name(self):
        """Test AnthropicProvider name format."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        assert provider.name == "anthropic:claude-sonnet-4-20250514"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_provider_name(self):
        """Test OpenAILLMProvider name format."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")
        assert provider.name == "openai:gpt-4o"

    def test_ollama_provider_name(self):
        """Test OllamaProvider name format."""
        from local_deepwiki.providers.llm.ollama import OllamaProvider

        provider = OllamaProvider(model="llama3.2")
        assert provider.name == "ollama:llama3.2"

    def test_local_embedding_provider_name(self):
        """Test LocalEmbeddingProvider name format."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        assert provider.name == "local:all-MiniLM-L6-v2"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_openai_embedding_provider_name(self):
        """Test OpenAIEmbeddingProvider name format."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.name == "openai:text-embedding-3-small"


# =============================================================================
# Test Retry with New Exceptions
# =============================================================================


class TestRetryWithNewExceptions:
    """Tests for retry behavior with new exception types."""

    async def test_retry_on_provider_connection_error(self):
        """Test that ProviderConnectionError triggers retry."""
        from local_deepwiki.providers.base import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderConnectionError("Temporary connection issue")
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert call_count == 3

    async def test_retry_on_provider_rate_limit_error(self):
        """Test that ProviderRateLimitError triggers retry."""
        from local_deepwiki.providers.base import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def rate_limited_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderRateLimitError("Rate limited", retry_after=1.0)
            return "success"

        result = await rate_limited_function()
        assert result == "success"
        assert call_count == 3
