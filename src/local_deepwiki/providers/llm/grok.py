"""Grok LLM provider."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, AuthenticationError, OpenAIError
from openai.types.chat import ChatCompletionMessageParam

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import (
    LLMProvider,
    LLMProviderCapabilities,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    handle_api_status_error,
    validate_provider_credentials,
    with_retry,
)
from local_deepwiki.providers.credentials import CredentialManager

logger = get_logger(__name__)


# Known Grok models with their context lengths (xAI API)
GROK_MODELS = {
    "grok-4-1-fast-reasoning": 2000000,
    "grok-4-1-fast-non-reasoning": 2000000,
}


class GrokLLMProvider(LLMProvider):
    """LLM provider using xAI Grok API (OpenAI-compatible)."""

    def __init__(self, model: str = "grok-4-1-fast-reasoning", api_key: str | None = None):
        """Initialize the Grok provider.

        Args:
            model: Grok model name.
            api_key: Optional API key. Uses GROK_API_KEY env var if not provided.

        Raises:
            ProviderAuthenticationError: If no API key is configured or format is invalid.
        """
        self._model = model

        # Get API key without storing in instance variable
        api_key = api_key or CredentialManager.get_api_key("GROK_API_KEY", "grok")

        # Validate credentials using shared helper
        api_key = validate_provider_credentials(
            provider_name=f"grok:{model}",
            api_key=api_key,
            key_type="grok",
            env_var="GROK_API_KEY",
            display_name="Grok",
        )

        # Pass directly to client, don't store in self
        # Grok uses an OpenAI-compatible API
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )

    def _handle_api_error(self, e: Exception) -> None:
        """Convert Grok API errors to standardized provider errors."""
        handle_api_status_error(
            e,
            provider_name=self.name,
            api_label="Grok API",
            model=self._model,
            available_models=list(GROK_MODELS.keys()),
            not_found_extra_patterns=("does not exist",),
            auth_error_type=AuthenticationError,
            status_error_type=APIStatusError,
            connection_error_type=APIConnectionError,
        )
        # Re-raise unknown errors
        raise

    async def validate_connectivity(self) -> bool:
        """Test that the Grok API is reachable and configured correctly.

        Returns:
            True if the API is accessible.

        Raises:
            ProviderConnectionError: If the API cannot be reached.
            ProviderAuthenticationError: If authentication fails.
        """
        try:
            # Make a minimal API call to verify connectivity
            await self._client.chat.completions.create(
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
                f"Failed to validate Grok connectivity: {e}",
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
        if model_name in GROK_MODELS:
            return True

        # Try to make a call with the model to verify
        try:
            await self._client.chat.completions.create(
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
            if "not found" in error_str or "does not exist" in error_str or "invalid" in error_str:
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(GROK_MODELS.keys()),
                ) from e
            self._handle_api_error(e)
            raise
        except (ValueError, KeyError) as e:
            # Data validation errors - check if model-related
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str or "invalid" in error_str:
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(GROK_MODELS.keys()),
                ) from e
            raise
        except OpenAIError as e:
            # Catch remaining OpenAI library exceptions (used by Grok SDK)
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str or "invalid" in error_str:
                logger.warning(
                    "Caught OpenAIError in Grok validate_model, treating as model error: %s",
                    e,
                )
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(GROK_MODELS.keys()),
                ) from e
            # For unknown errors, try the error handler first
            self._handle_api_error(e)
            raise

    @property
    def capabilities(self) -> LLMProviderCapabilities:
        """Return Grok provider capabilities.

        Returns:
            LLMProviderCapabilities with Grok-specific information.
        """
        context_length = GROK_MODELS.get(self._model, 128000)
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_system_prompt=True,
            max_tokens=4096,
            max_context_length=context_length,
            models=list(GROK_MODELS.keys()),
            supports_function_calling=True,
            supports_vision="vision" in self._model or "grok-4" in self._model,
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
        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(
            "Generating with Grok model %s, prompt length: %d",
            self._model,
            len(prompt),
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""

            logger.debug("Grok response length: %s", len(content))
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
        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

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
        return f"grok:{self._model}"
