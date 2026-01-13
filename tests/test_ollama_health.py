"""Tests for Ollama provider health check functionality."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from local_deepwiki.providers.llm.ollama import (
    OllamaProvider,
    OllamaConnectionError,
    OllamaModelNotFoundError,
)


class TestOllamaConnectionError:
    """Tests for OllamaConnectionError."""

    def test_error_message_includes_url(self):
        """Error message should include the base URL."""
        error = OllamaConnectionError("http://localhost:11434")
        assert "http://localhost:11434" in str(error)

    def test_error_message_includes_instructions(self):
        """Error message should include helpful instructions."""
        error = OllamaConnectionError("http://localhost:11434")
        message = str(error)
        assert "ollama serve" in message
        assert "Install Ollama" in message

    def test_stores_original_error(self):
        """Should store the original exception."""
        original = ConnectionError("Connection refused")
        error = OllamaConnectionError("http://localhost:11434", original)
        assert error.original_error is original


class TestOllamaModelNotFoundError:
    """Tests for OllamaModelNotFoundError."""

    def test_error_message_includes_model_name(self):
        """Error message should include the model name."""
        error = OllamaModelNotFoundError("llama3.2")
        assert "llama3.2" in str(error)

    def test_error_message_includes_pull_command(self):
        """Error message should include the pull command."""
        error = OllamaModelNotFoundError("llama3.2")
        assert "ollama pull llama3.2" in str(error)

    def test_error_message_lists_available_models(self):
        """Error message should list available models if provided."""
        error = OllamaModelNotFoundError("llama3.2", ["mistral:latest", "codellama:7b"])
        message = str(error)
        assert "mistral:latest" in message
        assert "codellama:7b" in message

    def test_truncates_long_model_list(self):
        """Should truncate very long model lists."""
        models = [f"model{i}:latest" for i in range(20)]
        error = OllamaModelNotFoundError("llama3.2", models)
        message = str(error)
        assert "20 total" in message


class TestOllamaProviderHealthCheck:
    """Tests for OllamaProvider.check_health()."""

    @pytest.fixture
    def provider(self):
        """Create an OllamaProvider instance."""
        return OllamaProvider(model="llama3.2", base_url="http://localhost:11434")

    @pytest.mark.asyncio
    async def test_health_check_passes_when_model_available(self, provider):
        """Health check should pass when Ollama is running and model exists."""
        mock_response = {
            "models": [
                {"name": "llama3.2:latest"},
                {"name": "mistral:latest"},
            ]
        }

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_response
            result = await provider.check_health()

        assert result is True
        assert provider._health_checked is True

    @pytest.mark.asyncio
    async def test_health_check_passes_with_exact_model_match(self, provider):
        """Health check should pass with exact model name match."""
        mock_response = {"models": [{"name": "llama3.2"}]}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_response
            result = await provider.check_health()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_passes_with_tagged_model(self, provider):
        """Health check should pass when model has a tag suffix."""
        mock_response = {"models": [{"name": "llama3.2:8b"}]}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_response
            result = await provider.check_health()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_raises_when_model_not_found(self, provider):
        """Health check should raise OllamaModelNotFoundError when model doesn't exist."""
        mock_response = {"models": [{"name": "mistral:latest"}]}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_response

            with pytest.raises(OllamaModelNotFoundError) as exc_info:
                await provider.check_health()

        assert "llama3.2" in str(exc_info.value)
        assert "mistral:latest" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_raises_on_connection_error(self, provider):
        """Health check should raise OllamaConnectionError on connection failure."""
        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = ConnectionError("Connection refused")

            with pytest.raises(OllamaConnectionError) as exc_info:
                await provider.check_health()

        assert "http://localhost:11434" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_raises_on_timeout(self, provider):
        """Health check should raise OllamaConnectionError on timeout."""
        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = TimeoutError("Request timed out")

            with pytest.raises(OllamaConnectionError):
                await provider.check_health()


class TestOllamaProviderGenerate:
    """Tests for OllamaProvider.generate() with health checking."""

    @pytest.fixture
    def provider(self):
        """Create an OllamaProvider instance."""
        return OllamaProvider(model="llama3.2", base_url="http://localhost:11434")

    @pytest.mark.asyncio
    async def test_generate_checks_health_on_first_call(self, provider):
        """Generate should check health on the first call."""
        mock_list_response = {"models": [{"name": "llama3.2:latest"}]}
        mock_chat_response = {"message": {"content": "Hello!"}}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_list_response
            with patch.object(provider._client, "chat", new_callable=AsyncMock) as mock_chat:
                mock_chat.return_value = mock_chat_response

                result = await provider.generate("Hello")

        mock_list.assert_called_once()
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_generate_skips_health_check_after_first_call(self, provider):
        """Generate should skip health check on subsequent calls."""
        provider._health_checked = True  # Simulate already checked

        mock_chat_response = {"message": {"content": "Hello!"}}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            with patch.object(provider._client, "chat", new_callable=AsyncMock) as mock_chat:
                mock_chat.return_value = mock_chat_response

                await provider.generate("Hello")

        mock_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_raises_connection_error_with_helpful_message(self, provider):
        """Generate should raise helpful error when Ollama is unavailable."""
        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = ConnectionError("Connection refused")

            with pytest.raises(OllamaConnectionError) as exc_info:
                await provider.generate("Hello")

        message = str(exc_info.value)
        assert "ollama serve" in message

    @pytest.mark.asyncio
    async def test_generate_raises_model_not_found_with_suggestions(self, provider):
        """Generate should raise helpful error when model doesn't exist."""
        mock_response = {"models": [{"name": "mistral:latest"}, {"name": "codellama:7b"}]}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_response

            with pytest.raises(OllamaModelNotFoundError) as exc_info:
                await provider.generate("Hello")

        message = str(exc_info.value)
        assert "ollama pull llama3.2" in message
        assert "mistral:latest" in message


class TestOllamaProviderGenerateStream:
    """Tests for OllamaProvider.generate_stream() with health checking."""

    @pytest.fixture
    def provider(self):
        """Create an OllamaProvider instance."""
        return OllamaProvider(model="llama3.2", base_url="http://localhost:11434")

    @pytest.mark.asyncio
    async def test_generate_stream_checks_health_on_first_call(self, provider):
        """Generate stream should check health on the first call."""
        mock_list_response = {"models": [{"name": "llama3.2:latest"}]}

        async def mock_stream():
            yield {"message": {"content": "Hello"}}
            yield {"message": {"content": " World"}}

        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_list_response
            with patch.object(provider._client, "chat", new_callable=AsyncMock) as mock_chat:
                mock_chat.return_value = mock_stream()

                chunks = []
                async for chunk in provider.generate_stream("Hello"):
                    chunks.append(chunk)

        mock_list.assert_called_once()
        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_generate_stream_raises_connection_error(self, provider):
        """Generate stream should raise helpful error when Ollama is unavailable."""
        with patch.object(provider._client, "list", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = ConnectionError("Connection refused")

            with pytest.raises(OllamaConnectionError):
                async for _ in provider.generate_stream("Hello"):
                    pass
