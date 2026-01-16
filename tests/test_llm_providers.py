"""Tests for LLM provider implementations."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        client = MagicMock()
        client.messages = MagicMock()
        return client

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")
        assert provider.name == "anthropic:claude-sonnet-4-20250514"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_initialization_with_custom_api_key(self):
        """Test provider initialization with custom API key."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514", api_key="custom-key")
        assert provider.name == "anthropic:claude-sonnet-4-20250514"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_basic(self):
        """Test basic text generation."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")

        # Mock the response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated response")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.generate("Test prompt")

        assert result == "Generated response"
        provider._client.messages.create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_with_system_prompt(self):
        """Test generation with system prompt."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        await provider.generate("User prompt", system_prompt="System prompt")

        call_kwargs = provider._client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "System prompt"
        assert call_kwargs["messages"] == [{"role": "user", "content": "User prompt"}]

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_with_zero_temperature(self):
        """Test generation with zero temperature (deterministic)."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Response")]
        provider._client.messages.create = AsyncMock(return_value=mock_response)

        await provider.generate("Prompt", temperature=0)

        call_kwargs = provider._client.messages.create.call_args.kwargs
        # Temperature should not be set when 0
        assert "temperature" not in call_kwargs

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream(self):
        """Test streaming text generation."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")

        # Create async iterator for text_stream
        async def mock_text_stream():
            for chunk in ["Hello", " ", "world"]:
                yield chunk

        # Create mock stream context manager
        mock_stream = MagicMock()
        mock_stream.text_stream = mock_text_stream()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        chunks = []
        async for chunk in provider.generate_stream("Test prompt"):
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world"]

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    async def test_generate_stream_with_system_prompt(self):
        """Test streaming with system prompt."""
        from local_deepwiki.providers.llm.anthropic import AnthropicProvider

        provider = AnthropicProvider(model="claude-sonnet-4-20250514")

        async def mock_text_stream():
            yield "Response"

        mock_stream = MagicMock()
        mock_stream.text_stream = mock_text_stream()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        provider._client.messages.stream = MagicMock(return_value=mock_stream)

        chunks = []
        async for chunk in provider.generate_stream("User prompt", system_prompt="System"):
            chunks.append(chunk)

        call_kwargs = provider._client.messages.stream.call_args.kwargs
        assert call_kwargs["system"] == "System"


class TestOpenAILLMProvider:
    """Tests for OpenAILLMProvider."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")
        assert provider.name == "openai:gpt-4o"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_initialization_with_custom_api_key(self):
        """Test provider initialization with custom API key."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o", api_key="custom-key")
        assert provider.name == "openai:gpt-4o"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_generate_basic(self):
        """Test basic text generation."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Mock the response
        mock_message = MagicMock()
        mock_message.content = "Generated response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.generate("Test prompt")

        assert result == "Generated response"
        provider._client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_generate_with_system_prompt(self):
        """Test generation with system prompt."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        await provider.generate("User prompt", system_prompt="System prompt")

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User prompt"},
        ]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_generate_without_system_prompt(self):
        """Test generation without system prompt."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        await provider.generate("User prompt")

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        # Should only have user message, no system message
        assert call_kwargs["messages"] == [{"role": "user", "content": "User prompt"}]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_generate_with_none_content(self):
        """Test generation when response content is None."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        mock_message = MagicMock()
        mock_message.content = None  # None content
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.generate("Test prompt")

        # Should return empty string when content is None
        assert result == ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_generate_stream(self):
        """Test streaming text generation."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        # Create mock chunks
        def make_chunk(content):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = content
            return chunk

        async def mock_stream():
            for content in ["Hello", " ", "world", None]:  # None for empty chunk
                yield make_chunk(content)

        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        chunks = []
        async for chunk in provider.generate_stream("Test prompt"):
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world"]

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_generate_stream_with_system_prompt(self):
        """Test streaming with system prompt."""
        from local_deepwiki.providers.llm.openai import OpenAILLMProvider

        provider = OpenAILLMProvider(model="gpt-4o")

        def make_chunk(content):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = content
            return chunk

        async def mock_stream():
            yield make_chunk("Response")

        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream())

        chunks = []
        async for chunk in provider.generate_stream("User prompt", system_prompt="System"):
            chunks.append(chunk)

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"][0] == {"role": "system", "content": "System"}
        assert call_kwargs["stream"] is True
