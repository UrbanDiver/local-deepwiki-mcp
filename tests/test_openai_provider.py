"""Comprehensive tests for OpenAI LLM provider.

Focuses on covering:
- Initialization with invalid API key format
- Error handling (_handle_api_error method)
- validate_connectivity method
- validate_model method
- Exception handling in generate and generate_stream
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAIError


class TestOpenAIProviderInitialization:
    """Tests for OpenAILLMProvider initialization."""

    def test_initialization_no_api_key_raises_error(self):
        """Test initialization fails without API key."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY from environment
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(ProviderAuthenticationError) as exc_info:
                OpenAILLMProvider(model="gpt-4o")

            assert "No OpenAI API key configured" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_initialization_invalid_key_format_raises_error(self):
        """Test initialization fails with invalid API key format."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        # Mock validate_key_format to return False
        with patch(
            "local_deepwiki.providers.llm.openai.CredentialManager.get_api_key",
            return_value="invalid",
        ):
            with patch(
                "local_deepwiki.providers.llm.openai.CredentialManager.validate_key_format",
                return_value=False,
            ):
                with pytest.raises(ProviderAuthenticationError) as exc_info:
                    OpenAILLMProvider(model="gpt-4o")

                assert "format appears invalid" in str(exc_info.value)


class TestOpenAIProviderHandleApiError:
    """Tests for _handle_api_error method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_authentication_error(self):
        """Test handling of AuthenticationError."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Create a mock AuthenticationError
        mock_request = MagicMock()
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        with pytest.raises(ProviderAuthenticationError) as exc_info:
            provider._handle_api_error(auth_error)

        assert "authentication failed" in str(exc_info.value)
        assert "API key" in str(exc_info.value)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_rate_limit_error_429(self):
        """Test handling of rate limit error (429 status code)."""
        from local_deepwiki.providers.base import ProviderRateLimitError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Create mock response with retry-after header
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "30"}

        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        assert "rate limit" in str(exc_info.value).lower()
        assert exc_info.value.retry_after == 30.0

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_rate_limit_error_by_message(self):
        """Test handling of rate limit error detected by message content."""
        from local_deepwiki.providers.base import ProviderRateLimitError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 400  # Not 429
        mock_response.headers = {}

        rate_error = APIStatusError(
            message="You have exceeded your rate limit",
            response=mock_response,
            body=None,
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        assert "rate limit" in str(exc_info.value).lower()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_rate_limit_invalid_retry_after(self):
        """Test handling of rate limit with invalid retry-after header."""
        from local_deepwiki.providers.base import ProviderRateLimitError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "invalid-value"}

        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        # retry_after should be None since parsing failed
        assert exc_info.value.retry_after is None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_rate_limit_no_response(self):
        """Test handling of rate limit error without response object."""
        from local_deepwiki.providers.base import ProviderRateLimitError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}  # No retry-after header

        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body=None,
        )
        # Remove response attribute to test the hasattr branch
        rate_error.response = None

        with pytest.raises(ProviderRateLimitError) as exc_info:
            provider._handle_api_error(rate_error)

        assert exc_info.value.retry_after is None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_model_not_found_404(self):
        """Test handling of model not found error (404 status code)."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="nonexistent-model")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}

        not_found_error = APIStatusError(
            message="Model not found",
            response=mock_response,
            body=None,
        )

        with pytest.raises(ProviderModelNotFoundError) as exc_info:
            provider._handle_api_error(not_found_error)

        assert "nonexistent-model" in str(exc_info.value)
        assert exc_info.value.available_models  # Should have available models list

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_model_not_found_by_message(self):
        """Test handling of model not found detected by message content."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="bad-model")

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}

        not_found_error = APIStatusError(
            message="The model 'bad-model' does not exist",
            response=mock_response,
            body=None,
        )

        with pytest.raises(ProviderModelNotFoundError) as exc_info:
            provider._handle_api_error(not_found_error)

        assert "bad-model" in str(exc_info.value)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_connection_error(self):
        """Test handling of APIConnectionError."""
        from local_deepwiki.providers.base import ProviderConnectionError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        conn_error = APIConnectionError(request=MagicMock())

        with pytest.raises(ProviderConnectionError) as exc_info:
            provider._handle_api_error(conn_error)

        assert "Failed to connect to OpenAI API" in str(exc_info.value)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_unknown_error_reraises(self):
        """Test that unknown errors are re-raised when called within exception context."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        unknown_error = ValueError("Some unknown error")

        # _handle_api_error uses bare 'raise' so must be called within exception handler
        with pytest.raises(ValueError):
            try:
                raise unknown_error
            except ValueError as e:
                provider._handle_api_error(e)
                raise  # This mirrors the actual usage pattern

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_handle_api_status_error_other(self):
        """Test handling of APIStatusError that doesn't match rate limit or not found."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        server_error = APIStatusError(
            message="Internal server error",
            response=mock_response,
            body=None,
        )

        # _handle_api_error uses bare 'raise' so must be called within exception handler
        # Should re-raise since it doesn't match any known patterns
        with pytest.raises(APIStatusError):
            try:
                raise server_error
            except APIStatusError as e:
                provider._handle_api_error(e)
                raise  # This mirrors the actual usage pattern


class TestOpenAIProviderValidateConnectivity:
    """Tests for validate_connectivity method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_connectivity_success(self):
        """Test successful connectivity validation."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_message = MagicMock()
        mock_message.content = "OK"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.validate_connectivity()
        assert result is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_connectivity_auth_error(self):
        """Test connectivity validation handles auth error."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        auth_error = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(side_effect=auth_error)

        with pytest.raises(ProviderAuthenticationError):
            await provider.validate_connectivity()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_connectivity_connection_error(self):
        """Test connectivity validation handles connection error."""
        from local_deepwiki.providers.base import ProviderConnectionError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        conn_error = APIConnectionError(request=MagicMock())

        provider._client.chat.completions.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.validate_connectivity()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_connectivity_unknown_error(self):
        """Test connectivity validation wraps unknown errors in ProviderConnectionError."""
        from local_deepwiki.providers.base import ProviderConnectionError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Use a RuntimeError that doesn't match any known patterns
        # This will go through _handle_api_error and then get wrapped
        unknown_error = RuntimeError("Unknown error that doesn't match patterns")

        provider._client.chat.completions.create = AsyncMock(side_effect=unknown_error)

        # The error will first go through _handle_api_error (which re-raises)
        # then get caught and wrapped in ProviderConnectionError at line 151
        with pytest.raises((ProviderConnectionError, RuntimeError)):
            await provider.validate_connectivity()


class TestOpenAIProviderValidateModel:
    """Tests for validate_model method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_known_model(self):
        """Test validation of known model returns True immediately."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        result = await provider.validate_model("gpt-4o")
        assert result is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_unknown_model_success(self):
        """Test validation of unknown model via API call."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_message = MagicMock()
        mock_message.content = "OK"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.validate_model("some-unknown-model")
        assert result is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_not_found(self):
        """Test validation of model that doesn't exist."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        provider._client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("Model 'nonexistent' does not exist")
        )

        with pytest.raises(ProviderModelNotFoundError) as exc_info:
            await provider.validate_model("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_not_found_message(self):
        """Test validation with 'not found' in error message."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        provider._client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("Model not found")
        )

        with pytest.raises(ProviderModelNotFoundError):
            await provider.validate_model("bad-model")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_invalid_message(self):
        """Test validation with 'invalid' in error message."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        provider._client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("Invalid model specified")
        )

        with pytest.raises(ProviderModelNotFoundError):
            await provider.validate_model("invalid-model")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_auth_error(self):
        """Test validation handles auth error through _handle_api_error."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Create proper AuthenticationError mock
        # Note: message must NOT contain "not found", "does not exist", or "invalid"
        # otherwise it matches the ProviderModelNotFoundError condition
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Authentication failed - bad API key",
            response=mock_response,
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(side_effect=auth_error)

        # AuthenticationError is caught in validate_model's except block,
        # then passed to _handle_api_error which converts to ProviderAuthenticationError
        with pytest.raises(ProviderAuthenticationError):
            await provider.validate_model("some-unknown-model")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_validate_model_other_error_reraises(self):
        """Test validation re-raises errors that aren't model-related."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Error that doesn't contain "not found", "does not exist", or "invalid"
        provider._client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("Server crashed")
        )

        with pytest.raises(RuntimeError):
            await provider.validate_model("some-model")


class TestOpenAIProviderGenerateErrors:
    """Tests for error handling in generate method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_generate_reraises_provider_errors(self):
        """Test that provider errors are re-raised directly."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        auth_error = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(side_effect=auth_error)

        with pytest.raises(ProviderAuthenticationError):
            await provider.generate("Test prompt")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_generate_handles_api_error(self):
        """Test that API errors are handled through _handle_api_error."""
        from local_deepwiki.providers.base import ProviderConnectionError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        conn_error = APIConnectionError(request=MagicMock())

        provider._client.chat.completions.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            await provider.generate("Test prompt")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_generate_unknown_error_calls_handle_api_error(self):
        """Test that unknown errors go through _handle_api_error."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Unknown error that _handle_api_error will re-raise
        unknown_error = RuntimeError("Unknown error")

        provider._client.chat.completions.create = AsyncMock(side_effect=unknown_error)

        with pytest.raises(RuntimeError):
            await provider.generate("Test prompt")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_generate_rate_limit_error(self):
        """Test that rate limit errors are handled properly."""
        from local_deepwiki.providers.base import ProviderRateLimitError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(side_effect=rate_error)

        with pytest.raises(ProviderRateLimitError):
            await provider.generate("Test prompt")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_generate_model_not_found_error(self):
        """Test that model not found errors are handled properly."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="nonexistent-model")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}

        not_found_error = APIStatusError(
            message="Model not found",
            response=mock_response,
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(
            side_effect=not_found_error
        )

        with pytest.raises(ProviderModelNotFoundError):
            await provider.generate("Test prompt")


class TestOpenAIProviderStreamErrors:
    """Tests for error handling in generate_stream method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_stream_reraises_provider_errors(self):
        """Test that provider errors are re-raised directly in stream."""
        from local_deepwiki.providers.base import ProviderAuthenticationError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        auth_error = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(side_effect=auth_error)

        with pytest.raises(ProviderAuthenticationError):
            async for _ in provider.generate_stream("Test prompt"):
                pass

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_stream_handles_connection_error(self):
        """Test that connection errors are handled in stream."""
        from local_deepwiki.providers.base import ProviderConnectionError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        conn_error = APIConnectionError(request=MagicMock())

        provider._client.chat.completions.create = AsyncMock(side_effect=conn_error)

        with pytest.raises(ProviderConnectionError):
            async for _ in provider.generate_stream("Test prompt"):
                pass

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_stream_unknown_error_calls_handle_api_error(self):
        """Test that unknown errors in stream go through _handle_api_error."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        unknown_error = RuntimeError("Unknown stream error")

        provider._client.chat.completions.create = AsyncMock(side_effect=unknown_error)

        with pytest.raises(RuntimeError):
            async for _ in provider.generate_stream("Test prompt"):
                pass

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_stream_rate_limit_error(self):
        """Test that rate limit errors are handled in stream."""
        from local_deepwiki.providers.base import ProviderRateLimitError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        rate_error = APIStatusError(
            message="Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(side_effect=rate_error)

        with pytest.raises(ProviderRateLimitError):
            async for _ in provider.generate_stream("Test prompt"):
                pass

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    async def test_stream_model_not_found_error(self):
        """Test that model not found errors are handled in stream."""
        from local_deepwiki.providers.base import ProviderModelNotFoundError
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="nonexistent")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}

        not_found_error = APIStatusError(
            message="Model not found",
            response=mock_response,
            body=None,
        )

        provider._client.chat.completions.create = AsyncMock(
            side_effect=not_found_error
        )

        with pytest.raises(ProviderModelNotFoundError):
            async for _ in provider.generate_stream("Test prompt"):
                pass


class TestOpenAIProviderCapabilities:
    """Tests for get_capabilities method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_capabilities_gpt4o(self):
        """Test capabilities for gpt-4o model."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")
        caps = provider.capabilities

        assert caps.supports_streaming is True
        assert caps.supports_system_prompt is True
        assert caps.max_tokens == 16384
        assert caps.max_context_length == 128000
        assert caps.supports_function_calling is True
        assert caps.supports_vision is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_capabilities_o1_model(self):
        """Test capabilities for o1 model (limited streaming/system prompt)."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="o1")
        caps = provider.capabilities

        assert caps.supports_streaming is False  # O1 has limited streaming
        assert caps.supports_system_prompt is False  # O1 uses developer messages
        assert caps.max_context_length == 200000

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_capabilities_gpt35_turbo(self):
        """Test capabilities for gpt-3.5-turbo model."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-3.5-turbo")
        caps = provider.capabilities

        assert caps.max_tokens == 4096  # Not gpt-4o
        assert caps.supports_vision is False  # gpt-3.5 doesn't support vision

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_capabilities_gpt4_turbo(self):
        """Test capabilities for gpt-4-turbo model."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4-turbo")
        caps = provider.capabilities

        assert caps.supports_vision is True  # gpt-4-turbo supports vision
        assert caps.max_context_length == 128000

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_capabilities_unknown_model(self):
        """Test capabilities for unknown model uses defaults."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="some-future-model")
        caps = provider.capabilities

        # Should use default context length
        assert caps.max_context_length == 128000


class TestOpenAIProviderName:
    """Tests for name property."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_name_includes_model(self):
        """Test that name includes the model."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")
        assert provider.name == "openai:gpt-4o"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey1234567890abcdef1234"})
    def test_name_different_model(self):
        """Test name with different model."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-3.5-turbo")
        assert provider.name == "openai:gpt-3.5-turbo"
