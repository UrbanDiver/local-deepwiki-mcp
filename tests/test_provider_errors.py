"""Tests for provider error handling."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from local_deepwiki.providers.llm.ollama import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaProvider,
)


@dataclass
class MockModel:
    """Mock ollama Model object."""

    model: str


@dataclass
class MockListResponse:
    """Mock ollama ListResponse object."""

    models: list[MockModel]


def make_list_response(model_names: list[str]) -> MockListResponse:
    """Create a mock list response with the given model names."""
    return MockListResponse(models=[MockModel(model=name) for name in model_names])


class TestOllamaConnectionError:
    """Tests for OllamaConnectionError."""

    def test_error_message_includes_url(self):
        """Test that error message includes the base URL."""
        error = OllamaConnectionError("http://localhost:11434")
        assert "http://localhost:11434" in str(error)
        assert "Cannot connect to Ollama" in str(error)

    def test_error_message_includes_instructions(self):
        """Test that error message includes setup instructions."""
        error = OllamaConnectionError("http://localhost:11434")
        assert "ollama serve" in str(error)
        assert "ollama.ai/download" in str(error)

    def test_stores_original_error(self):
        """Test that original error is stored."""
        original = ConnectionError("Connection refused")
        error = OllamaConnectionError("http://localhost:11434", original)
        assert error.original_error is original


class TestOllamaModelNotFoundError:
    """Tests for OllamaModelNotFoundError."""

    def test_error_message_includes_model_name(self):
        """Test that error message includes the model name."""
        error = OllamaModelNotFoundError("llama3.2")
        assert "llama3.2" in str(error)
        assert "not found" in str(error)

    def test_error_message_includes_pull_command(self):
        """Test that error message includes pull command."""
        error = OllamaModelNotFoundError("llama3.2")
        assert "ollama pull llama3.2" in str(error)

    def test_error_message_lists_available_models(self):
        """Test that error message lists available models."""
        error = OllamaModelNotFoundError("llama3.2", ["mistral:latest", "codellama:7b"])
        assert "mistral:latest" in str(error)
        assert "codellama:7b" in str(error)

    def test_truncates_long_model_list(self):
        """Test that long model list is truncated."""
        models = [f"model{i}:latest" for i in range(20)]
        error = OllamaModelNotFoundError("llama3.2", models)
        # Should show first 10 and total count
        assert "20 total" in str(error)


class TestOllamaProviderHealthCheck:
    """Tests for OllamaProvider health check."""

    async def test_health_check_success(self):
        """Test successful health check."""
        provider = OllamaProvider(model="llama3.2")

        with patch.object(provider._client, "list") as mock_list:
            mock_list.return_value = make_list_response(["llama3.2:latest"])

            result = await provider.check_health()
            assert result is True
            assert provider._health_checked is True

    async def test_health_check_model_not_found(self):
        """Test health check when model is not available."""
        provider = OllamaProvider(model="nonexistent-model")

        with patch.object(provider._client, "list") as mock_list:
            mock_list.return_value = make_list_response(["llama3.2:latest"])

            with pytest.raises(OllamaModelNotFoundError) as exc_info:
                await provider.check_health()

            assert "nonexistent-model" in str(exc_info.value)

    async def test_health_check_connection_error(self):
        """Test health check when Ollama is not accessible."""
        provider = OllamaProvider(model="llama3.2")

        with patch.object(provider._client, "list") as mock_list:
            mock_list.side_effect = ConnectionError("Connection refused")

            with pytest.raises(OllamaConnectionError) as exc_info:
                await provider.check_health()

            assert "Cannot connect to Ollama" in str(exc_info.value)


class TestOllamaProviderGenerate:
    """Tests for OllamaProvider generate method."""

    async def test_generate_checks_health_once(self):
        """Test that generate checks health only once."""
        provider = OllamaProvider(model="llama3.2")
        provider._health_checked = True  # Skip health check

        with patch.object(provider._client, "chat") as mock_chat:
            mock_chat.return_value = {
                "message": {"content": "Generated response"}
            }

            result = await provider.generate("Test prompt")
            assert result == "Generated response"

    async def test_generate_with_system_prompt(self):
        """Test generate with system prompt."""
        provider = OllamaProvider(model="llama3.2")
        provider._health_checked = True

        with patch.object(provider._client, "chat") as mock_chat:
            mock_chat.return_value = {
                "message": {"content": "Response"}
            }

            await provider.generate("User prompt", system_prompt="System prompt")

            # Verify messages were sent correctly
            call_args = mock_chat.call_args
            messages = call_args.kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "System prompt"
            assert messages[1]["role"] == "user"


class TestOllamaProviderName:
    """Tests for OllamaProvider name property."""

    def test_name_includes_model(self):
        """Test that name includes model."""
        provider = OllamaProvider(model="llama3.2")
        assert provider.name == "ollama:llama3.2"

    def test_name_with_tag(self):
        """Test that name includes model with tag."""
        provider = OllamaProvider(model="codellama:7b")
        assert provider.name == "ollama:codellama:7b"


class TestRetryDecorator:
    """Tests for retry decorator behavior."""

    async def test_retry_on_transient_error(self):
        """Test that transient errors trigger retry."""
        from local_deepwiki.providers.base import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary error")
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert call_count == 3

    async def test_retry_gives_up_after_max_attempts(self):
        """Test that retry gives up after max attempts."""
        from local_deepwiki.providers.base import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Permanent error")

        with pytest.raises(ConnectionError):
            await always_fails()

        assert call_count == 3

    async def test_no_retry_on_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        from local_deepwiki.providers.base import with_retry

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            await raises_value_error()

        assert call_count == 1  # Should not retry
