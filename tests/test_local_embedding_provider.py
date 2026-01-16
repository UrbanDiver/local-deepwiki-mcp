"""Tests for LocalEmbeddingProvider."""

from unittest.mock import MagicMock, patch

import pytest


class TestLocalEmbeddingProvider:
    """Tests for LocalEmbeddingProvider."""

    def test_initialization(self):
        """Test provider initialization."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        assert provider.name == "local:all-MiniLM-L6-v2"
        assert provider._model is None  # Lazy loaded

    def test_initialization_default_model(self):
        """Test provider initialization with default model."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.name == "local:all-MiniLM-L6-v2"

    @patch("local_deepwiki.providers.embeddings.local.SentenceTransformer")
    def test_load_model(self, mock_transformer_class):
        """Test lazy model loading."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider(model_name="test-model")

        # Model not loaded yet
        assert provider._model is None

        # Trigger load
        model = provider._load_model()

        assert model is mock_model
        mock_transformer_class.assert_called_once_with("test-model")
        mock_model.get_sentence_embedding_dimension.assert_called_once()
        assert provider._dimension == 384

    @patch("local_deepwiki.providers.embeddings.local.SentenceTransformer")
    def test_load_model_cached(self, mock_transformer_class):
        """Test that model is only loaded once."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        # Load twice
        provider._load_model()
        provider._load_model()

        # Should only be called once
        mock_transformer_class.assert_called_once()

    @patch("local_deepwiki.providers.embeddings.local.SentenceTransformer")
    async def test_embed(self, mock_transformer_class):
        """Test embedding generation."""
        import numpy as np

        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        result = await provider.embed(["text1", "text2"])

        mock_model.encode.assert_called_once_with(["text1", "text2"], convert_to_numpy=True)
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @patch("local_deepwiki.providers.embeddings.local.SentenceTransformer")
    def test_get_dimension(self, mock_transformer_class):
        """Test getting embedding dimension."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        # Should trigger model load
        dimension = provider.get_dimension()

        assert dimension == 768
        mock_transformer_class.assert_called_once()

    @patch("local_deepwiki.providers.embeddings.local.SentenceTransformer")
    def test_get_dimension_cached(self, mock_transformer_class):
        """Test that dimension is cached after first load."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        # First call loads model
        dim1 = provider.get_dimension()
        # Second call should use cached value
        dim2 = provider.get_dimension()

        assert dim1 == dim2 == 384
        # Model only loaded once
        mock_transformer_class.assert_called_once()
