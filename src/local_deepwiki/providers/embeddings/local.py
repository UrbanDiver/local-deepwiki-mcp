"""Local embedding provider using sentence-transformers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from local_deepwiki.providers.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    ProviderConfigurationError,
    ProviderConnectionError,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


# Known model dimensions and max tokens
LOCAL_EMBEDDING_MODELS = {
    "all-MiniLM-L6-v2": {"dimension": 384, "max_tokens": 256},
    "all-MiniLM-L12-v2": {"dimension": 384, "max_tokens": 256},
    "all-mpnet-base-v2": {"dimension": 768, "max_tokens": 384},
    "multi-qa-MiniLM-L6-cos-v1": {"dimension": 384, "max_tokens": 512},
    "multi-qa-mpnet-base-dot-v1": {"dimension": 768, "max_tokens": 512},
    "paraphrase-MiniLM-L6-v2": {"dimension": 384, "max_tokens": 128},
    "paraphrase-mpnet-base-v2": {"dimension": 768, "max_tokens": 512},
}


class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "multi-qa-MiniLM-L6-cos-v1"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model.

        Returns:
            The loaded SentenceTransformer model.

        Raises:
            ProviderConfigurationError: If the model cannot be loaded.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ProviderConfigurationError(
                    "sentence-transformers is required for local embeddings "
                    "but is not installed.\n"
                    "Install with: uv pip install sentence-transformers",
                    provider_name=self.name,
                ) from None
            try:
                self._model = SentenceTransformer(self._model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except (RuntimeError, OSError, ValueError, ImportError) as e:
                # RuntimeError: Model loading failures
                # OSError: File system or model file access errors
                # ValueError: Invalid model name or configuration
                # ImportError: Missing dependencies (torch, transformers, etc.)
                raise ProviderConfigurationError(
                    f"Failed to load sentence-transformers model '{self._model_name}': {e}",
                    provider_name=self.name,
                ) from e
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.

        Raises:
            ProviderConfigurationError: If the model cannot be loaded.
        """
        model = self._load_model()
        # Run CPU-bound encoding in thread pool to avoid blocking async event loop
        embeddings = await asyncio.to_thread(model.encode, texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore[return-value]  # _dimension set in __init__ but type checker doesn't track it

    async def validate_connectivity(self) -> bool:
        """Test that the model can be loaded and used.

        Returns:
            True if the model is accessible and working.

        Raises:
            ProviderConnectionError: If the model cannot be loaded.
        """
        try:
            self._load_model()
            # Try a test embedding
            await self.embed(["test"])
            return True
        except ProviderConfigurationError:
            raise
        except (RuntimeError, OSError, ValueError) as e:
            # RuntimeError: Model inference failures
            # OSError: File system or model access errors
            # ValueError: Invalid input during validation
            raise ProviderConnectionError(
                f"Failed to validate local embedding provider: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

    def get_max_batch_size(self) -> int:
        """Return maximum number of texts that can be embedded in a single call.

        Returns:
            Maximum batch size. Local models can handle large batches.
        """
        return 1000  # Local models can handle larger batches

    def get_max_tokens(self) -> int:
        """Return maximum tokens per text.

        Returns:
            Maximum tokens per text for this model.
        """
        model_info = LOCAL_EMBEDDING_MODELS.get(self._model_name, {})
        return model_info.get("max_tokens", 512)

    def get_capabilities(self) -> EmbeddingProviderCapabilities:
        """Return provider capabilities.

        Returns:
            EmbeddingProviderCapabilities with model-specific information.
        """
        return EmbeddingProviderCapabilities(
            max_batch_size=self.get_max_batch_size(),
            max_tokens_per_text=self.get_max_tokens(),
            dimension=self.get_dimension(),
            models=list(LOCAL_EMBEDDING_MODELS.keys()),
            supports_truncation=True,  # sentence-transformers handles truncation
        )

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
