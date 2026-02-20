"""Comprehensive tests for OpenAIEmbeddingProvider to achieve 90%+ coverage.

This module tests the OpenAI embedding provider including:
- Initialization with various API key configurations
- Embedding generation (success and error cases)
- Error handling (_handle_api_error method)
- Validate connectivity
- Capabilities and metadata methods
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.providers.base import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderRateLimitError,
)


class TestOpenAIEmbeddingProviderInitialization:
    """Tests for OpenAIEmbeddingProvider initialization."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_initialization_with_env_var(self):
        """Test provider initialization using environment variable."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.name == "openai:text-embedding-3-small"
        assert provider._model == "text-embedding-3-small"

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_initialization_with_explicit_api_key(self):
        """Test provider initialization with explicit API key."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(
            model="text-embedding-3-small", api_key="sk-customkey1234567890abcdef"
        )
        assert provider.name == "openai:text-embedding-3-small"

    @patch.dict(os.environ, {}, clear=True)
    def test_initialization_without_api_key_raises_error(self):
        """Test that initialization without API key raises ProviderAuthenticationError."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            OpenAIEmbeddingProvider(model="text-embedding-3-small")

        assert "No OpenAI API key configured" in str(exc_info.value)
        assert exc_info.value.provider_name == "openai:embedding"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "bad"}, clear=True)
    def test_initialization_with_invalid_key_format_raises_error(self):
        """Test that initialization with invalid API key format raises error."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        # The CredentialManager validates test keys, but "bad" is too short
        # and doesn't match test key patterns
        with pytest.raises((ProviderAuthenticationError, ValueError)):
            OpenAIEmbeddingProvider(model="text-embedding-3-small")

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_initialization_all_known_models(self):
        """Test initialization with all known embedding models."""
        from local_deepwiki.providers.embeddings.openai import (
            OPENAI_EMBEDDING_MODELS,
            OpenAIEmbeddingProvider,
        )

        for model_name, model_info in OPENAI_EMBEDDING_MODELS.items():
            provider = OpenAIEmbeddingProvider(model=model_name)
            assert provider.dimension == model_info["dimension"]

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_initialization_unknown_model_uses_defaults(self):
        """Test that unknown model uses default dimension."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="unknown-future-model")
        assert provider.dimension == 1536  # Default dimension


class TestOpenAIEmbeddingProviderHandleApiError:
    """Tests for _handle_api_error method - lines 70-102."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_authentication_error(self):
        """Test handling of AuthenticationError."""
        from openai import AuthenticationError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock AuthenticationError
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API Key",
            response=mock_response,
            body={"error": {"message": "Invalid API Key"}},
        )

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            provider._handle_api_error(auth_error)

        assert "authentication failed" in str(exc_info.value).lower()
        assert exc_info.value.provider_name == "openai:text-embedding-3-small"

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_rate_limit_error_status_429(self):
        """Test handling of rate limit error with status code 429."""
        from openai import APIStatusError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock APIStatusError with 429 status
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )
        rate_error.status_code = 429

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        assert "rate limit" in str(exc_info.value).lower()
        assert exc_info.value.provider_name == "openai:text-embedding-3-small"

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_rate_limit_error_with_rate_in_message(self):
        """Test handling of rate limit error detected via message content."""
        from openai import APIStatusError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock APIStatusError with "rate" in message but different status code
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        rate_error = APIStatusError(
            message="Request rate too high",
            response=mock_response,
            body={"error": {"message": "Request rate too high"}},
        )
        rate_error.status_code = 400

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        assert "rate" in str(exc_info.value).lower()

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_rate_limit_error_with_retry_after_header(self):
        """Test handling of rate limit error with retry-after header."""
        from openai import APIStatusError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock APIStatusError with retry-after header
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "30"}
        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )
        rate_error.status_code = 429
        rate_error.response = mock_response

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        assert exc_info.value.retry_after == 30.0

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_rate_limit_error_with_invalid_retry_after(self):
        """Test handling of rate limit error with invalid retry-after header."""
        from openai import APIStatusError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock APIStatusError with invalid retry-after header
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "not-a-number"}
        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )
        rate_error.status_code = 429
        rate_error.response = mock_response

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        # retry_after should be None due to ValueError during conversion
        assert exc_info.value.retry_after is None

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_connection_error(self):
        """Test handling of APIConnectionError."""
        from openai import APIConnectionError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock APIConnectionError
        conn_error = APIConnectionError(request=MagicMock())

        with pytest.raises(ProviderConnectionError) as exc_info:
            provider._handle_api_error(conn_error)

        assert "connect" in str(exc_info.value).lower()
        assert exc_info.value.provider_name == "openai:text-embedding-3-small"

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_unknown_error_reraises(self):
        """Test that unknown errors are re-raised.

        Note: The source code uses a bare 'raise' which only works within an
        exception handler context. When called directly, it raises RuntimeError.
        This test covers line 102.
        """
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create an unknown exception type
        unknown_error = ValueError("Unknown error")

        # The bare 'raise' statement without active exception context raises RuntimeError
        with pytest.raises(RuntimeError):
            provider._handle_api_error(unknown_error)

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_handle_api_status_error_non_rate_limit(self):
        """Test handling of APIStatusError that is not a rate limit.

        The source code uses a bare 'raise' at the end which doesn't work
        when called directly (outside of an exception handler context).
        """
        from openai import APIStatusError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock APIStatusError with 500 status (server error)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        server_error = APIStatusError(
            message="Internal server error",
            response=mock_response,
            body={"error": {"message": "Internal server error"}},
        )
        server_error.status_code = 500

        # The bare 'raise' without active exception context raises RuntimeError
        with pytest.raises(RuntimeError):
            provider._handle_api_error(server_error)


class TestOpenAIEmbeddingProviderEmbed:
    """Tests for embed method - including lines 124-128."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_success(self):
        """Test successful embedding generation."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the response
        mock_embedding1 = MagicMock()
        mock_embedding1.embedding = [0.1, 0.2, 0.3]
        mock_embedding2 = MagicMock()
        mock_embedding2.embedding = [0.4, 0.5, 0.6]

        mock_response = MagicMock()
        mock_response.data = [mock_embedding1, mock_embedding2]

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed(["text1", "text2"])

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        provider._client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["text1", "text2"],
        )

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_reraises_provider_connection_error(self):
        """Test that ProviderConnectionError is re-raised directly."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the client to raise ProviderConnectionError
        provider._client.embeddings.create = AsyncMock(
            side_effect=ProviderConnectionError("Connection failed", "openai")
        )

        with pytest.raises(ProviderConnectionError) as exc_info:
            await provider.embed(["test"])

        assert "Connection failed" in str(exc_info.value)

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_reraises_provider_authentication_error(self):
        """Test that ProviderAuthenticationError is re-raised directly."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the client to raise ProviderAuthenticationError
        provider._client.embeddings.create = AsyncMock(
            side_effect=ProviderAuthenticationError("Auth failed", "openai")
        )

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider.embed(["test"])

        assert "Auth failed" in str(exc_info.value)

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_reraises_provider_rate_limit_error(self):
        """Test that ProviderRateLimitError is re-raised directly."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the client to raise ProviderRateLimitError
        provider._client.embeddings.create = AsyncMock(
            side_effect=ProviderRateLimitError("Rate limited", "openai", retry_after=30)
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            await provider.embed(["test"])

        assert "Rate limited" in str(exc_info.value)
        assert exc_info.value.retry_after == 30

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_handles_api_error_via_handler(self):
        """Test that other exceptions go through _handle_api_error."""
        from openai import AuthenticationError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the client to raise AuthenticationError
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API Key",
            response=mock_response,
            body={"error": {"message": "Invalid API Key"}},
        )

        provider._client.embeddings.create = AsyncMock(side_effect=auth_error)

        with pytest.raises(ProviderAuthenticationError):
            await provider.embed(["test"])

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_handles_connection_error_via_handler(self):
        """Test that APIConnectionError goes through _handle_api_error."""
        from openai import APIConnectionError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the client to raise APIConnectionError
        conn_error = APIConnectionError(request=MagicMock())

        provider._client.embeddings.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.embed(["test"])

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_handles_rate_limit_via_handler(self):
        """Test that rate limit APIStatusError goes through _handle_api_error."""
        from openai import APIStatusError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create a mock 429 rate limit error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "60"}
        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )
        rate_error.status_code = 429
        rate_error.response = mock_response

        provider._client.embeddings.create = AsyncMock(side_effect=rate_error)

        with pytest.raises(ProviderRateLimitError) as exc_info:
            await provider.embed(["test"])

        assert exc_info.value.retry_after == 60.0

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_unknown_error_reraises(self):
        """Test that unknown errors are re-raised after going through handler."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock the client to raise an unknown error
        provider._client.embeddings.create = AsyncMock(
            side_effect=RuntimeError("Unknown error")
        )

        with pytest.raises(RuntimeError) as exc_info:
            await provider.embed(["test"])

        assert "Unknown error" in str(exc_info.value)


class TestOpenAIEmbeddingProviderValidateConnectivity:
    """Tests for validate_connectivity method - lines 148-163."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_validate_connectivity_success(self):
        """Test successful connectivity validation."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock successful embedding response
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.validate_connectivity()
        assert result is True

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_validate_connectivity_api_error(self):
        """Test connectivity validation with API error."""
        from openai import APIConnectionError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Mock connection error
        conn_error = APIConnectionError(request=MagicMock())
        provider._client.embeddings.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.validate_connectivity()


class TestOpenAIEmbeddingProviderCapabilities:
    """Tests for capabilities and metadata methods."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_get_max_batch_size(self):
        """Test get_max_batch_size returns correct value."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.max_batch_size == 2048

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_get_max_tokens_known_model(self):
        """Test get_max_tokens for known models."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.max_tokens == 8191

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_get_max_tokens_unknown_model(self):
        """Test get_max_tokens for unknown models returns default."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="unknown-model")
        assert provider.max_tokens == 8191  # Default

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_get_capabilities(self):
        """Test get_capabilities returns correct capabilities object."""
        from local_deepwiki.providers.base import EmbeddingProviderCapabilities
        from local_deepwiki.providers.embeddings.openai import (
            OPENAI_EMBEDDING_MODELS,
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        caps = provider.capabilities

        assert isinstance(caps, EmbeddingProviderCapabilities)
        assert caps.max_batch_size == 2048
        assert caps.max_tokens_per_text == 8191
        assert caps.dimension == 1536
        assert caps.supports_truncation is True
        assert set(caps.models) == set(OPENAI_EMBEDDING_MODELS.keys())

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_get_dimension_text_embedding_3_large(self):
        """Test get_dimension for text-embedding-3-large model."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-large")
        assert provider.dimension == 3072

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_get_dimension_ada_002(self):
        """Test get_dimension for text-embedding-ada-002 model."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-ada-002")
        assert provider.dimension == 1536

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_name_property(self):
        """Test name property returns correct format."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.name == "openai:text-embedding-3-small"

        provider2 = OpenAIEmbeddingProvider(model="text-embedding-3-large")
        assert provider2.name == "openai:text-embedding-3-large"


class TestOpenAIEmbeddingProviderKeyValidation:
    """Tests for API key format validation - covering line 49."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_invalid_key_format_raises_authentication_error(self):
        """Test that invalid API key format raises ProviderAuthenticationError (line 49)."""
        from local_deepwiki.providers.credentials import CredentialManager
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        # Mock validate_key_format to return False
        with patch.object(CredentialManager, "validate_key_format", return_value=False):
            with pytest.raises(ProviderAuthenticationError) as exc_info:
                OpenAIEmbeddingProvider(model="text-embedding-3-small")

            assert "format appears invalid" in str(exc_info.value)
            assert exc_info.value.provider_name == "openai:embedding"

    @patch.dict(os.environ, {}, clear=True)
    def test_explicit_invalid_key_format(self):
        """Test with explicit API key that fails format validation."""
        from local_deepwiki.providers.credentials import CredentialManager
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        # Mock validate_key_format to return False for any key
        with patch.object(CredentialManager, "validate_key_format", return_value=False):
            with pytest.raises(ProviderAuthenticationError) as exc_info:
                OpenAIEmbeddingProvider(
                    model="text-embedding-3-small", api_key="some-key"
                )

            assert "format appears invalid" in str(exc_info.value)


class TestOpenAIEmbeddingProviderValidateConnectivityFixed:
    """Tests for validate_connectivity after _api_key bug fix."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_validate_connectivity_success(self):
        """Test that validate_connectivity returns True on successful API call."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.validate_connectivity()
        assert result is True

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_validate_connectivity_api_error_handled(self):
        """Test validate_connectivity when API connection fails."""
        from openai import APIConnectionError

        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        conn_error = APIConnectionError(request=MagicMock())
        provider._client.embeddings.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.validate_connectivity()

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_validate_connectivity_unknown_error(self):
        """Test validate_connectivity with unknown error.

        _handle_api_error re-raises unknown errors via bare 'raise'.
        """
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        unknown_error = ValueError("Unknown error")
        provider._client.embeddings.create = AsyncMock(side_effect=unknown_error)

        with pytest.raises(ValueError) as exc_info:
            await provider.validate_connectivity()

        assert "Unknown error" in str(exc_info.value)


class TestOpenAIEmbeddingProviderEdgeCases:
    """Edge case tests for OpenAIEmbeddingProvider."""

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_empty_list(self):
        """Test embedding an empty list of texts."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        mock_response = MagicMock()
        mock_response.data = []

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed([])
        assert result == []

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_single_text(self):
        """Test embedding a single text."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed(["single text"])
        assert len(result) == 1
        assert len(result[0]) == 1536

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    async def test_embed_large_batch(self):
        """Test embedding a large batch of texts."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")

        # Create mock response with 100 embeddings
        mock_embeddings = []
        for i in range(100):
            mock_embedding = MagicMock()
            mock_embedding.embedding = [float(i) / 100] * 1536
            mock_embeddings.append(mock_embedding)

        mock_response = MagicMock()
        mock_response.data = mock_embeddings

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        texts = [f"text {i}" for i in range(100)]
        result = await provider.embed(texts)

        assert len(result) == 100
        provider._client.embeddings.create.assert_called_once()

    @patch.dict(
        os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"}, clear=True
    )
    def test_default_model(self):
        """Test that default model is text-embedding-3-small."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider()
        assert provider._model == "text-embedding-3-small"
        assert provider.dimension == 1536


class TestOpenAIEmbeddingModelsDict:
    """Tests for OPENAI_EMBEDDING_MODELS dictionary."""

    def test_models_dict_has_expected_keys(self):
        """Test that models dict has all expected models."""
        from local_deepwiki.providers.embeddings.openai import OPENAI_EMBEDDING_MODELS

        expected_models = [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ]
        for model in expected_models:
            assert model in OPENAI_EMBEDDING_MODELS

    def test_models_dict_has_required_fields(self):
        """Test that each model has dimension and max_tokens."""
        from local_deepwiki.providers.embeddings.openai import OPENAI_EMBEDDING_MODELS

        for model_name, model_info in OPENAI_EMBEDDING_MODELS.items():
            assert "dimension" in model_info, f"{model_name} missing dimension"
            assert "max_tokens" in model_info, f"{model_name} missing max_tokens"
            assert isinstance(model_info["dimension"], int)
            assert isinstance(model_info["max_tokens"], int)
