"""OpenAI embedding provider."""

from __future__ import annotations

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, AuthenticationError

from local_deepwiki.providers.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderRateLimitError,
    handle_api_status_error,
    with_retry,
)
from local_deepwiki.providers.credentials import CredentialManager

# Embedding dimensions and max tokens for OpenAI models
OPENAI_EMBEDDING_MODELS = {
    "text-embedding-3-small": {"dimension": 1536, "max_tokens": 8191},
    "text-embedding-3-large": {"dimension": 3072, "max_tokens": 8191},
    "text-embedding-ada-002": {"dimension": 1536, "max_tokens": 8191},
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using OpenAI API."""

    def __init__(
        self, model: str = "text-embedding-3-small", api_key: str | None = None
    ):
        """Initialize the OpenAI embedding provider.

        Args:
            model: OpenAI embedding model name.
            api_key: Optional API key. Uses OPENAI_API_KEY env var if not provided.

        Raises:
            ProviderAuthenticationError: If no API key is configured or format is invalid.
        """
        self._model = model

        # Get API key without storing in instance variable
        api_key = api_key or CredentialManager.get_api_key("OPENAI_API_KEY", "openai")

        if not api_key:
            raise ProviderAuthenticationError(
                "No OpenAI API key configured. Set OPENAI_API_KEY environment variable.",
                provider_name="openai:embedding",
            )

        # Validate format
        if not CredentialManager.validate_key_format(api_key, "openai"):
            raise ProviderAuthenticationError(
                "OpenAI API key format appears invalid.",
                provider_name="openai:embedding",
            )

        # Pass directly to client, don't store in self
        self._client = AsyncOpenAI(api_key=api_key)
        model_info = OPENAI_EMBEDDING_MODELS.get(model, {})
        self._dimension = model_info.get("dimension", 1536)

    def _handle_api_error(self, e: Exception) -> None:
        """Convert OpenAI API errors to standardized provider errors."""
        handle_api_status_error(
            e,
            provider_name=self.name,
            api_label="OpenAI API",
            auth_error_type=AuthenticationError,
            status_error_type=APIStatusError,
            connection_error_type=APIConnectionError,
        )
        # Re-raise unknown errors
        raise

    @with_retry()
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.

        Raises:
            ProviderConnectionError: If the API cannot be reached.
            ProviderAuthenticationError: If authentication fails.
            ProviderRateLimitError: If rate limited.
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except (
            ProviderConnectionError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
        ):
            raise
        except (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            ValueError,
            RuntimeError,
        ) as e:
            # APIConnectionError: Network connection failures
            # APIStatusError: HTTP 4xx/5xx responses from API
            # AuthenticationError: Invalid API key
            # ValueError: API parameter validation failures
            # RuntimeError: OpenAI SDK internal errors
            self._handle_api_error(e)
            raise

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        return self._dimension

    async def validate_connectivity(self) -> bool:
        """Test that the OpenAI API is reachable and configured correctly.

        Returns:
            True if the API is accessible.

        Raises:
            ProviderConnectionError: If the API cannot be reached.
            ProviderAuthenticationError: If authentication fails.
        """
        try:
            # Make a minimal API call to verify connectivity
            await self._client.embeddings.create(
                model=self._model,
                input=["test"],
            )
            return True
        except (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            ValueError,
            RuntimeError,
        ) as e:
            # APIConnectionError: Network connection failures
            # APIStatusError: HTTP 4xx/5xx responses from API
            # AuthenticationError: Invalid API key
            # ValueError: API parameter validation failures
            # RuntimeError: OpenAI SDK internal errors
            self._handle_api_error(e)
            raise ProviderConnectionError(
                f"Failed to validate OpenAI embedding connectivity: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

    def get_max_batch_size(self) -> int:
        """Return maximum number of texts that can be embedded in a single call.

        Returns:
            Maximum batch size for OpenAI embeddings.
        """
        return 2048  # OpenAI allows up to 2048 inputs per request

    def get_max_tokens(self) -> int:
        """Return maximum tokens per text.

        Returns:
            Maximum tokens per text for this model.
        """
        model_info = OPENAI_EMBEDDING_MODELS.get(self._model, {})
        return model_info.get("max_tokens", 8191)

    def get_capabilities(self) -> EmbeddingProviderCapabilities:
        """Return provider capabilities.

        Returns:
            EmbeddingProviderCapabilities with OpenAI-specific information.
        """
        return EmbeddingProviderCapabilities(
            max_batch_size=self.get_max_batch_size(),
            max_tokens_per_text=self.get_max_tokens(),
            dimension=self._dimension,
            models=list(OPENAI_EMBEDDING_MODELS.keys()),
            supports_truncation=True,  # OpenAI API handles truncation
        )

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"openai:{self._model}"
