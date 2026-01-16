"""Tests for OpenAIEmbeddingProvider."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.name == "openai:text-embedding-3-small"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_initialization_with_custom_api_key(self):
        """Test provider initialization with custom API key."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small", api_key="custom-key")
        assert provider.name == "openai:text-embedding-3-small"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_get_dimension_known_model(self):
        """Test get_dimension for known models."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
        assert provider.get_dimension() == 1536

        provider2 = OpenAIEmbeddingProvider(model="text-embedding-3-large")
        assert provider2.get_dimension() == 3072

        provider3 = OpenAIEmbeddingProvider(model="text-embedding-ada-002")
        assert provider3.get_dimension() == 1536

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_get_dimension_unknown_model(self):
        """Test get_dimension for unknown models defaults to 1536."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider(model="unknown-model")
        assert provider.get_dimension() == 1536

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_embed(self):
        """Test embedding generation."""
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

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    async def test_embed_single_text(self):
        """Test embedding a single text."""
        from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

        provider = OpenAIEmbeddingProvider()

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        provider._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed(["single text"])

        assert len(result) == 1
        assert len(result[0]) == 1536
