"""Anthropic LLM provider."""

from __future__ import annotations

from typing import Any, AsyncIterator

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic, AuthenticationError

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import (
    LLMProvider,
    LLMProviderCapabilities,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    validate_provider_credentials,
    with_retry,
)
from local_deepwiki.providers.credentials import CredentialManager

logger = get_logger(__name__)


# Known Anthropic models with their context lengths
ANTHROPIC_MODELS = {
    "claude-opus-4-20250514": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
}


class AnthropicProvider(LLMProvider):
    """LLM provider using Anthropic API."""

    def __init__(
        self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None
    ):
        """Initialize the Anthropic provider.

        Args:
            model: Anthropic model name.
            api_key: Optional API key. Uses ANTHROPIC_API_KEY env var if not provided.

        Raises:
            ProviderAuthenticationError: If no API key is configured or format is invalid.
        """
        self._model = model

        # Get API key without storing in instance variable
        api_key = api_key or CredentialManager.get_api_key(
            "ANTHROPIC_API_KEY", "anthropic"
        )

        # Validate credentials using shared helper
        api_key = validate_provider_credentials(
            provider_name="anthropic:claude",
            api_key=api_key,
            key_type="anthropic",
            env_var="ANTHROPIC_API_KEY",
            display_name="Anthropic",
        )

        # Pass directly to client, don't store in self
        self._client = AsyncAnthropic(api_key=api_key)

    def _build_kwargs(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        """Build kwargs for Anthropic API calls.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Dict of kwargs for messages.create/stream.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if temperature > 0:
            kwargs["temperature"] = temperature
        return kwargs

    def _handle_api_error(self, e: Exception) -> None:
        """Convert Anthropic API errors to standardized provider errors.

        Args:
            e: The exception from the Anthropic API.

        Raises:
            ProviderAuthenticationError: If authentication fails.
            ProviderRateLimitError: If rate limited.
            ProviderModelNotFoundError: If model not found.
            ProviderConnectionError: If connection fails.
        """
        if isinstance(e, AuthenticationError):
            raise ProviderAuthenticationError(
                "Anthropic API authentication failed. Check your ANTHROPIC_API_KEY.",
                provider_name=self.name,
            ) from e

        if isinstance(e, APIStatusError):
            error_str = str(e).lower()
            if e.status_code == 429 or "rate" in error_str:
                # Try to extract retry-after header
                retry_after = None
                if hasattr(e, "response") and e.response:
                    retry_after_str = e.response.headers.get("retry-after")
                    if retry_after_str:
                        try:
                            retry_after = float(retry_after_str)
                        except ValueError:
                            pass
                raise ProviderRateLimitError(
                    f"Anthropic API rate limit exceeded: {e}",
                    provider_name=self.name,
                    retry_after=retry_after,
                ) from e

            if e.status_code == 404 or "not found" in error_str:
                raise ProviderModelNotFoundError(
                    self._model,
                    provider_name=self.name,
                    available_models=list(ANTHROPIC_MODELS.keys()),
                ) from e

        if isinstance(e, APIConnectionError):
            raise ProviderConnectionError(
                f"Failed to connect to Anthropic API: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

        # Re-raise unknown errors
        raise

    async def validate_connectivity(self) -> bool:
        """Test that the Anthropic API is reachable and configured correctly.

        Returns:
            True if the API is accessible.

        Raises:
            ProviderConnectionError: If the API cannot be reached.
            ProviderAuthenticationError: If authentication fails.
        """
        try:
            # Make a minimal API call to verify connectivity
            await self._client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            ConnectionError,
            TimeoutError,
        ) as e:
            self._handle_api_error(e)
            raise ProviderConnectionError(
                f"Failed to validate Anthropic connectivity: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

    async def validate_model(self, model_name: str) -> bool:
        """Test that a specific model is available.

        Args:
            model_name: The model name to validate.

        Returns:
            True if the model is available.

        Raises:
            ProviderModelNotFoundError: If the model is not available.
        """
        if model_name in ANTHROPIC_MODELS:
            return True

        # Try to make a call with the model to verify
        try:
            await self._client.messages.create(
                model=model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            ConnectionError,
            TimeoutError,
        ) as e:
            # API-specific exceptions - delegate to error handler or check error message
            error_str = str(e).lower()
            if "not found" in error_str or "invalid" in error_str:
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(ANTHROPIC_MODELS.keys()),
                ) from e
            self._handle_api_error(e)
            raise
        except (ValueError, KeyError) as e:
            # Data validation errors - check if model-related
            error_str = str(e).lower()
            if "not found" in error_str or "invalid" in error_str:
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(ANTHROPIC_MODELS.keys()),
                ) from e
            raise
        except Exception as e:
            # Catch-all for library exceptions that don't match known types
            # Only handle model-related errors, re-raise everything else
            error_str = str(e).lower()
            if "not found" in error_str or "invalid" in error_str:
                logger.warning(
                    f"Caught generic exception in validate_model, treating as model error: {e}"
                )
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(ANTHROPIC_MODELS.keys()),
                ) from e
            # For unknown errors, try the error handler first
            self._handle_api_error(e)
            raise

    def get_capabilities(self) -> LLMProviderCapabilities:
        """Return Anthropic provider capabilities.

        Returns:
            LLMProviderCapabilities with Anthropic-specific information.
        """
        context_length = ANTHROPIC_MODELS.get(self._model, 200000)
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_system_prompt=True,
            max_tokens=8192,  # Output limit for most Claude models
            max_context_length=context_length,
            models=list(ANTHROPIC_MODELS.keys()),
            supports_function_calling=True,  # Claude supports tools
            supports_vision=True,  # Claude 3+ supports vision
        )

    @with_retry()
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Generated text.

        Raises:
            ProviderConnectionError: If the API cannot be reached.
            ProviderAuthenticationError: If authentication fails.
            ProviderRateLimitError: If rate limited.
            ProviderModelNotFoundError: If the model is not available.
        """
        logger.debug(
            f"Generating with Anthropic model {self._model}, prompt length: {len(prompt)}"
        )

        try:
            kwargs = self._build_kwargs(prompt, system_prompt, max_tokens, temperature)
            response = await self._client.messages.create(**kwargs)

            # Get text from the first content block (should be TextBlock)
            first_block = response.content[0]
            content = first_block.text if hasattr(first_block, "text") else ""

            logger.debug(f"Anthropic response length: {len(content)}")
            return content

        except (
            ProviderConnectionError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
            ProviderModelNotFoundError,
        ):
            raise
        except (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            ConnectionError,
            TimeoutError,
        ) as e:
            self._handle_api_error(e)
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate text from a prompt with streaming.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Yields:
            Generated text chunks.

        Raises:
            ProviderConnectionError: If the API cannot be reached.
            ProviderAuthenticationError: If authentication fails.
            ProviderRateLimitError: If rate limited.
            ProviderModelNotFoundError: If the model is not available.
        """
        try:
            kwargs = self._build_kwargs(prompt, system_prompt, max_tokens, temperature)
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except (
            ProviderConnectionError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
            ProviderModelNotFoundError,
        ):
            raise
        except (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            ConnectionError,
            TimeoutError,
        ) as e:
            self._handle_api_error(e)
            raise

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"anthropic:{self._model}"
