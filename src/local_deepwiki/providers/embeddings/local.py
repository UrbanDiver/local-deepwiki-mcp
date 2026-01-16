"""Local embedding provider using sentence-transformers."""

from typing import cast

from sentence_transformers import SentenceTransformer

from local_deepwiki.providers.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        # sentence-transformers is synchronous, but we keep async interface for consistency
        embeddings = model.encode(texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
