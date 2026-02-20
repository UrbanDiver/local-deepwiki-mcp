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
        assert provider.name == "local:multi-qa-MiniLM-L6-cos-v1"

    @patch("sentence_transformers.SentenceTransformer")
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

    @patch("sentence_transformers.SentenceTransformer")
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

    @patch("sentence_transformers.SentenceTransformer")
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

        mock_model.encode.assert_called_once_with(
            ["text1", "text2"], convert_to_numpy=True
        )
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @patch("sentence_transformers.SentenceTransformer")
    def test_get_dimension(self, mock_transformer_class):
        """Test getting embedding dimension."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        # Should trigger model load
        dimension = provider.dimension

        assert dimension == 768
        mock_transformer_class.assert_called_once()

    @patch("sentence_transformers.SentenceTransformer")
    def test_get_dimension_cached(self, mock_transformer_class):
        """Test that dimension is cached after first load."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        # First call loads model
        dim1 = provider.dimension
        # Second call should use cached value
        dim2 = provider.dimension

        assert dim1 == dim2 == 384
        # Model only loaded once
        mock_transformer_class.assert_called_once()

    @patch("sentence_transformers.SentenceTransformer")
    def test_load_model_failure(self, mock_transformer_class):
        """Test model loading failure raises ProviderConfigurationError."""
        from local_deepwiki.providers.base import ProviderConfigurationError
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_transformer_class.side_effect = RuntimeError("Model not found")

        provider = LocalEmbeddingProvider(model_name="invalid-model")

        with pytest.raises(ProviderConfigurationError) as exc_info:
            provider._load_model()

        assert "Failed to load sentence-transformers model" in str(exc_info.value)
        assert "invalid-model" in str(exc_info.value)

    @patch("sentence_transformers.SentenceTransformer")
    async def test_validate_connectivity_success(self, mock_transformer_class):
        """Test successful connectivity validation."""
        import numpy as np

        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        result = await provider.validate_connectivity()

        assert result is True
        # Model should be loaded and test embedding created
        mock_model.encode.assert_called_once()

    @patch("sentence_transformers.SentenceTransformer")
    async def test_validate_connectivity_config_error(self, mock_transformer_class):
        """Test connectivity validation with model loading failure."""
        from local_deepwiki.providers.base import ProviderConfigurationError
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_transformer_class.side_effect = RuntimeError("Model not found")

        provider = LocalEmbeddingProvider(model_name="bad-model")

        with pytest.raises(ProviderConfigurationError):
            await provider.validate_connectivity()

    @patch("sentence_transformers.SentenceTransformer")
    async def test_validate_connectivity_other_error(self, mock_transformer_class):
        """Test connectivity validation with unexpected error raises ProviderConnectionError."""
        from local_deepwiki.providers.base import ProviderConnectionError
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        # First call loads model fine, but encode fails
        mock_model.encode.side_effect = OSError("Memory allocation failed")
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        with pytest.raises(ProviderConnectionError) as exc_info:
            await provider.validate_connectivity()

        assert "Failed to validate local embedding provider" in str(exc_info.value)

    @patch("sentence_transformers.SentenceTransformer")
    def test_get_max_batch_size(self, mock_transformer_class):
        """Test get_max_batch_size returns 1000."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()

        assert provider.max_batch_size == 1000

    def test_get_max_tokens_known_model(self):
        """Test get_max_tokens for known models."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")
        assert provider.max_tokens == 256

        provider2 = LocalEmbeddingProvider(model_name="multi-qa-MiniLM-L6-cos-v1")
        assert provider2.max_tokens == 512

        provider3 = LocalEmbeddingProvider(model_name="all-mpnet-base-v2")
        assert provider3.max_tokens == 384

    def test_get_max_tokens_unknown_model(self):
        """Test get_max_tokens defaults to 512 for unknown models."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model_name="unknown-custom-model")

        assert provider.max_tokens == 512

    @patch("sentence_transformers.SentenceTransformer")
    def test_get_capabilities(self, mock_transformer_class):
        """Test get_capabilities returns correct EmbeddingProviderCapabilities."""
        from local_deepwiki.providers.base import EmbeddingProviderCapabilities
        from local_deepwiki.providers.embeddings.local import (
            LOCAL_EMBEDDING_MODELS,
            LocalEmbeddingProvider,
        )

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider(model_name="all-MiniLM-L6-v2")

        capabilities = provider.capabilities

        assert isinstance(capabilities, EmbeddingProviderCapabilities)
        assert capabilities.max_batch_size == 1000
        assert capabilities.max_tokens_per_text == 256
        assert capabilities.dimension == 384
        assert capabilities.models == list(LOCAL_EMBEDDING_MODELS.keys())
        assert capabilities.supports_truncation is True

    @patch("sentence_transformers.SentenceTransformer")
    async def test_embed_empty_list(self, mock_transformer_class):
        """Test embedding an empty list."""
        import numpy as np

        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([]).reshape(0, 384)
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        result = await provider.embed([])

        assert result == []
        mock_model.encode.assert_called_once_with([], convert_to_numpy=True)

    @patch("sentence_transformers.SentenceTransformer")
    async def test_embed_single_text(self, mock_transformer_class):
        """Test embedding a single text."""
        import numpy as np

        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.5] * 384])
        mock_transformer_class.return_value = mock_model

        provider = LocalEmbeddingProvider()

        result = await provider.embed(["single text"])

        assert len(result) == 1
        assert len(result[0]) == 384
        assert result[0][0] == 0.5

    def test_name_property_different_models(self):
        """Test name property for different model names."""
        from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

        provider1 = LocalEmbeddingProvider(model_name="all-mpnet-base-v2")
        assert provider1.name == "local:all-mpnet-base-v2"

        provider2 = LocalEmbeddingProvider(model_name="custom/model-name")
        assert provider2.name == "local:custom/model-name"

    def test_local_embedding_models_constant(self):
        """Test LOCAL_EMBEDDING_MODELS has expected structure."""
        from local_deepwiki.providers.embeddings.local import LOCAL_EMBEDDING_MODELS

        # Check that the constant exists and has expected keys
        assert "all-MiniLM-L6-v2" in LOCAL_EMBEDDING_MODELS
        assert "all-mpnet-base-v2" in LOCAL_EMBEDDING_MODELS

        # Check structure of entries
        for model_name, model_info in LOCAL_EMBEDDING_MODELS.items():
            assert "dimension" in model_info
            assert "max_tokens" in model_info
            assert isinstance(model_info["dimension"], int)
            assert isinstance(model_info["max_tokens"], int)
