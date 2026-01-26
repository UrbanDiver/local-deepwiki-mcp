"""Comprehensive tests for AnthropicProvider to achieve 90%+ coverage.

Tests cover:
- Initialization with valid/invalid API keys
- API key format validation
- Text generation (basic and with system prompt)
- Streaming generation
- Error handling for various API errors
- Retry logic
- validate_connectivity and validate_model methods
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from anthropic import APIConnectionError, APIStatusError, AuthenticationError

from local_deepwiki.providers.base import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
)


def create_mock_request():
    """Create a mock httpx.Request for APIConnectionError."""
    return MagicMock(spec=httpx.Request)


class TestAnthropicProviderInitialization:
    """Tests for AnthropicProvider initialization."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization_default_model(self):
        """Test provider initialization with default model."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        assert provider.name == "anthropic:claude-sonnet-4-20250514"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization_custom_model(self):
        """Test provider initialization with custom model."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-3-opus-20240229")
        assert provider.name == "anthropic:claude-3-opus-20240229"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization_with_custom_api_key(self):
        """Test provider initialization with custom API key."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key="custom-key")
        assert provider.name == "anthropic:claude-sonnet-4-20250514"

    @patch.dict(os.environ, {}, clear=True)
    def test_initialization_missing_api_key(self):
        """Test provider raises error when no API key is available."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        # Remove any existing key
        os.environ.pop("ANTHROPIC_API_KEY", None)

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            AnthropicProvider()

        assert "No Anthropic API key configured" in str(exc_info.value)
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization_invalid_api_key_format(self):
        """Test provider raises error when API key format is invalid."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider
        from local_deepwiki.providers.credentials import CredentialManager

        # Mock validate_key_format to return False (after get_api_key returns the key)
        with patch.object(CredentialManager, "validate_key_format", return_value=False):
            with pytest.raises(ProviderAuthenticationError) as exc_info:
                AnthropicProvider()

            assert "format appears invalid" in str(exc_info.value)


class TestAnthropicProviderCapabilities:
    """Tests for AnthropicProvider capabilities."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_capabilities_default_model(self):
        """Test capabilities for default model."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        capabilities = provider.get_capabilities()

        assert capabilities.supports_streaming is True
        assert capabilities.supports_system_prompt is True
        assert capabilities.max_tokens == 8192
        assert capabilities.max_context_length == 200000
        assert capabilities.supports_function_calling is True
        assert capabilities.supports_vision is True
        assert "claude-sonnet-4-20250514" in capabilities.models

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_capabilities_unknown_model(self):
        """Test capabilities fallback for unknown model."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="unknown-model")
        capabilities = provider.get_capabilities()

        # Should default to 200000 for unknown models
        assert capabilities.max_context_length == 200000


class TestAnthropicProviderBuildKwargs:
    """Tests for _build_kwargs method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_build_kwargs_basic(self):
        """Test building kwargs without system prompt."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        kwargs = provider._build_kwargs("test prompt", None, 1000, 0.5)

        assert kwargs["model"] == "claude-sonnet-4-20250514"
        assert kwargs["max_tokens"] == 1000
        assert kwargs["messages"] == [{"role": "user", "content": "test prompt"}]
        assert kwargs["temperature"] == 0.5
        assert "system" not in kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_build_kwargs_with_system_prompt(self):
        """Test building kwargs with system prompt."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        kwargs = provider._build_kwargs("test", "system instruction", 1000, 0.5)

        assert kwargs["system"] == "system instruction"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_build_kwargs_zero_temperature(self):
        """Test building kwargs with zero temperature (deterministic)."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()
        kwargs = provider._build_kwargs("test", None, 1000, 0)

        # Temperature should not be included when 0
        assert "temperature" not in kwargs


class TestAnthropicProviderHandleApiError:
    """Tests for _handle_api_error method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_authentication_error(self):
        """Test handling AuthenticationError."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Create a real AuthenticationError
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}},
        )

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            provider._handle_api_error(auth_error)

        assert "authentication failed" in str(exc_info.value)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_rate_limit_error_429(self):
        """Test handling rate limit error with 429 status."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Create APIStatusError with 429 status
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "30"}
        status_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(status_error)

        assert "rate limit exceeded" in str(exc_info.value).lower()
        assert exc_info.value.retry_after == 30.0

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_rate_limit_error_by_message(self):
        """Test handling rate limit error detected by message content."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Create APIStatusError without 429 but with rate in message
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        status_error = APIStatusError(
            message="Request rate limited",
            response=mock_response,
            body={"error": {"message": "Request rate limited"}},
        )

        with pytest.raises(ProviderRateLimitError):
            provider._handle_api_error(status_error)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_rate_limit_error_invalid_retry_after(self):
        """Test handling rate limit error with invalid retry-after header."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "invalid"}
        status_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(status_error)

        # retry_after should be None due to invalid value
        assert exc_info.value.retry_after is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_rate_limit_error_no_response(self):
        """Test handling rate limit error without response object."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        status_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )
        # Remove response attribute
        status_error.response = None

        with pytest.raises(ProviderRateLimitError):
            provider._handle_api_error(status_error)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_model_not_found_404(self):
        """Test handling model not found error with 404 status."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        status_error = APIStatusError(
            message="Model not found",
            response=mock_response,
            body={"error": {"message": "Model not found"}},
        )

        with pytest.raises(ProviderModelNotFoundError) as exc_info:
            provider._handle_api_error(status_error)

        assert exc_info.value.available_models is not None
        assert len(exc_info.value.available_models) > 0

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_model_not_found_by_message(self):
        """Test handling model not found error detected by message."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        status_error = APIStatusError(
            message="The model xyz was not found",
            response=mock_response,
            body={"error": {"message": "The model xyz was not found"}},
        )

        with pytest.raises(ProviderModelNotFoundError):
            provider._handle_api_error(status_error)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_handle_connection_error(self):
        """Test handling APIConnectionError."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        conn_error = APIConnectionError(
            message="Connection refused",
            request=create_mock_request(),
        )

        with pytest.raises(ProviderConnectionError) as exc_info:
            provider._handle_api_error(conn_error)

        assert "Failed to connect to Anthropic API" in str(exc_info.value)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_handle_unknown_error_reraises_via_generate(self):
        """Test that unknown errors are re-raised through generate."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Create a generic exception that's not an API error
        provider._client.messages.create = AsyncMock(
            side_effect=ValueError("Unknown error")
        )

        # The method uses bare "raise" so the original error is re-raised
        with pytest.raises(ValueError) as exc_info:
            await provider.generate("Test")

        assert "Unknown error" in str(exc_info.value)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_handle_api_status_error_unknown_via_generate(self):
        """Test that unknown APIStatusError is re-raised through generate."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        status_error = APIStatusError(
            message="Internal server error",
            response=mock_response,
            body={"error": {"message": "Internal server error"}},
        )
        provider._client.messages.create = AsyncMock(side_effect=status_error)

        # Should re-raise since it's not rate limit or not found
        with pytest.raises(APIStatusError):
            await provider.generate("Test")


class TestAnthropicProviderValidateConnectivity:
    """Tests for validate_connectivity method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_connectivity_success(self):
        """Test successful connectivity validation."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hi")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.validate_connectivity()
        assert result is True

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_connectivity_auth_error(self):
        """Test connectivity validation with authentication error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}},
        )
        provider._client.messages.create = AsyncMock(side_effect=auth_error)

        with pytest.raises(ProviderAuthenticationError):
            await provider.validate_connectivity()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_connectivity_connection_error(self):
        """Test connectivity validation with connection error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        conn_error = APIConnectionError(
            message="Connection refused",
            request=create_mock_request(),
        )
        provider._client.messages.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.validate_connectivity()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_connectivity_generic_error(self):
        """Test connectivity validation with generic error.

        When a non-API error occurs, _handle_api_error re-raises it.
        The original error propagates out.
        """
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Use an APIStatusError with unknown status code (500)
        # _handle_api_error will re-raise it since it's not rate limit or 404
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        status_error = APIStatusError(
            message="Internal server error",
            response=mock_response,
            body={"error": {"message": "Internal server error"}},
        )
        provider._client.messages.create = AsyncMock(side_effect=status_error)

        # The APIStatusError gets re-raised by _handle_api_error's bare raise
        with pytest.raises(APIStatusError):
            await provider.validate_connectivity()


class TestAnthropicProviderValidateModel:
    """Tests for validate_model method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_model_known_model(self):
        """Test validating a known model."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Known model should return True immediately
        result = await provider.validate_model("claude-sonnet-4-20250514")
        assert result is True

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_model_unknown_success(self):
        """Test validating an unknown model that exists."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hi")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.validate_model("unknown-but-valid-model")
        assert result is True

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_model_not_found(self):
        """Test validating a model that doesn't exist."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        provider._client.messages.create = AsyncMock(
            side_effect=ValueError("model xyz not found or invalid")
        )

        with pytest.raises(ProviderModelNotFoundError):
            await provider.validate_model("xyz")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_model_invalid_error(self):
        """Test validating a model with 'invalid' in error message."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        provider._client.messages.create = AsyncMock(
            side_effect=ValueError("The model is invalid")
        )

        with pytest.raises(ProviderModelNotFoundError):
            await provider.validate_model("bad-model")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_model_api_error(self):
        """Test validating a model with API error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        conn_error = APIConnectionError(
            message="Connection refused",
            request=create_mock_request(),
        )
        provider._client.messages.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.validate_model("some-model")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_validate_model_other_error(self):
        """Test validating a model with non-model-related error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Error without 'not found' or 'invalid' in message
        provider._client.messages.create = AsyncMock(
            side_effect=RuntimeError("Some other runtime error")
        )

        with pytest.raises(RuntimeError):
            await provider.validate_model("some-model")


class TestAnthropicProviderGenerate:
    """Tests for generate method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_basic(self):
        """Test basic text generation."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated text")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.generate("Test prompt")

        assert result == "Generated text"
        provider._client.messages.create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_with_system_prompt(self):
        """Test generation with system prompt."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        await provider.generate("User prompt", system_prompt="Be helpful")

        call_kwargs = provider._client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "Be helpful"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_content_without_text_attr(self):
        """Test generation when content block lacks text attribute."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Create a content block without text attribute
        mock_block = MagicMock(spec=[])  # Empty spec means no text attribute
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.generate("Test")

        assert result == ""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_reraises_provider_errors(self):
        """Test that provider errors are re-raised directly."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Simulate a provider error being raised
        provider._client.messages.create = AsyncMock(
            side_effect=ProviderRateLimitError("Rate limited", provider_name="test")
        )

        with pytest.raises(ProviderRateLimitError):
            await provider.generate("Test")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_connection_error(self):
        """Test generation with connection error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        conn_error = APIConnectionError(
            message="Connection refused",
            request=create_mock_request(),
        )
        provider._client.messages.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.generate("Test")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_auth_error(self):
        """Test generation with authentication error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}},
        )
        provider._client.messages.create = AsyncMock(side_effect=auth_error)

        with pytest.raises(ProviderAuthenticationError):
            await provider.generate("Test")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_model_not_found_error(self):
        """Test generation with model not found error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        status_error = APIStatusError(
            message="Model not found",
            response=mock_response,
            body={"error": {"message": "Model not found"}},
        )
        provider._client.messages.create = AsyncMock(side_effect=status_error)

        with pytest.raises(ProviderModelNotFoundError):
            await provider.generate("Test")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_unknown_error_reraises(self):
        """Test generation re-raises unknown errors after handling."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        # Unknown error type
        provider._client.messages.create = AsyncMock(
            side_effect=RuntimeError("Unknown error")
        )

        with pytest.raises(RuntimeError):
            await provider.generate("Test")


class TestAnthropicProviderGenerateStream:
    """Tests for generate_stream method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_basic(self):
        """Test basic streaming generation."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        async def mock_text_stream():
            for chunk in ["Hello", " ", "world"]:
                yield chunk

        mock_stream = MagicMock()
        mock_stream.text_stream = mock_text_stream()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        chunks = []
        async for chunk in provider.generate_stream("Test"):
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world"]

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_with_system_prompt(self):
        """Test streaming with system prompt."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        async def mock_text_stream():
            yield "Response"

        mock_stream = MagicMock()
        mock_stream.text_stream = mock_text_stream()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        chunks = []
        async for chunk in provider.generate_stream("Test", system_prompt="System"):
            chunks.append(chunk)

        call_kwargs = provider._client.messages.stream.call_args.kwargs
        assert call_kwargs["system"] == "System"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_reraises_provider_errors(self):
        """Test that provider errors are re-raised in streaming."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(
            side_effect=ProviderConnectionError("Connection lost", provider_name="test")
        )

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.generate_stream("Test"):
                pass

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_connection_error(self):
        """Test streaming with connection error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(
            side_effect=APIConnectionError(
                message="Connection refused",
                request=create_mock_request(),
            )
        )

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.generate_stream("Test"):
                pass

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_auth_error(self):
        """Test streaming with authentication error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}},
        )

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(side_effect=auth_error)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(ProviderAuthenticationError):
            async for _ in provider.generate_stream("Test"):
                pass

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_rate_limit_error(self):
        """Test streaming with rate limit error."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        rate_limit_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}},
        )

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(side_effect=rate_limit_error)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(ProviderRateLimitError):
            async for _ in provider.generate_stream("Test"):
                pass

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_unknown_error_reraises(self):
        """Test streaming re-raises unknown errors."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(
            side_effect=RuntimeError("Unknown error")
        )

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(RuntimeError):
            async for _ in provider.generate_stream("Test"):
                pass

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_error_during_iteration(self):
        """Test streaming error that occurs during iteration."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        async def failing_stream():
            yield "First"
            raise APIConnectionError(
                message="Connection lost",
                request=create_mock_request(),
            )

        mock_stream = MagicMock()
        mock_stream.text_stream = failing_stream()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        chunks = []
        with pytest.raises(ProviderConnectionError):
            async for chunk in provider.generate_stream("Test"):
                chunks.append(chunk)

        # Should have received first chunk before error
        assert chunks == ["First"]


class TestAnthropicProviderRetry:
    """Tests for retry behavior in generate method."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_retries_on_connection_error(self):
        """Test that generate retries on connection errors."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        call_count = 0

        async def flaky_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIConnectionError(
                    message="Connection refused",
                    request=create_mock_request(),
                )
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Success")]
            return mock_response

        provider._client.messages.create = flaky_create

        # Patch sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await provider.generate("Test")

        assert result == "Success"
        assert call_count == 3

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_gives_up_after_max_retries(self):
        """Test that generate gives up after max retry attempts."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider()

        call_count = 0

        async def always_fails(**kwargs):
            nonlocal call_count
            call_count += 1
            raise APIConnectionError(
                message="Connection refused",
                request=create_mock_request(),
            )

        provider._client.messages.create = always_fails

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ProviderConnectionError):
                await provider.generate("Test")

        assert call_count == 3  # max_attempts is 3


class TestAnthropicModelsConstant:
    """Tests for ANTHROPIC_MODELS constant."""

    def test_anthropic_models_contains_expected_models(self):
        """Test that ANTHROPIC_MODELS contains expected models."""
        from local_deepwiki.providers.llm.anthropic import ANTHROPIC_MODELS

        expected_models = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]

        for model in expected_models:
            assert model in ANTHROPIC_MODELS
            assert ANTHROPIC_MODELS[model] == 200000
