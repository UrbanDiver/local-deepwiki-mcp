"""OpenAI LLM provider."""

from typing import AsyncIterator

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, AuthenticationError
from openai.types.chat import ChatCompletionMessageParam

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import (
    LLMProvider,
    LLMProviderCapabilities,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    with_retry,
)
from local_deepwiki.providers.credentials import CredentialManager

logger = get_logger(__name__)


# Known OpenAI models with their context lengths
OPENAI_MODELS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-preview": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    "o1": 200000,
    "o1-mini": 128000,
    "o1-preview": 128000,
}


class OpenAILLMProvider(LLMProvider):
    """LLM provider using OpenAI API."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        """Initialize the OpenAI provider.

        Args:
            model: OpenAI model name.
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
                provider_name="openai:gpt",
            )

        # Validate format
        if not CredentialManager.validate_key_format(api_key, "openai"):
            raise ProviderAuthenticationError(
                "OpenAI API key format appears invalid.",
                provider_name="openai:gpt",
            )

        # Pass directly to client, don't store in self
        self._client = AsyncOpenAI(api_key=api_key)

    def _handle_api_error(self, e: Exception) -> None:
        """Convert OpenAI API errors to standardized provider errors.

        Args:
            e: The exception from the OpenAI API.

        Raises:
            ProviderAuthenticationError: If authentication fails.
            ProviderRateLimitError: If rate limited.
            ProviderModelNotFoundError: If model not found.
            ProviderConnectionError: If connection fails.
        """
        if isinstance(e, AuthenticationError):
            raise ProviderAuthenticationError(
                "OpenAI API authentication failed. Check your OPENAI_API_KEY.",
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
                    f"OpenAI API rate limit exceeded: {e}",
                    provider_name=self.name,
                    retry_after=retry_after,
                ) from e

            if (
                e.status_code == 404
                or "not found" in error_str
                or "does not exist" in error_str
            ):
                raise ProviderModelNotFoundError(
                    self._model,
                    provider_name=self.name,
                    available_models=list(OPENAI_MODELS.keys()),
                ) from e

        if isinstance(e, APIConnectionError):
            raise ProviderConnectionError(
                f"Failed to connect to OpenAI API: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

        # Re-raise unknown errors
        raise

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
            await self._client.chat.completions.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            self._handle_api_error(e)
            raise ProviderConnectionError(
                f"Failed to validate OpenAI connectivity: {e}",
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
        if model_name in OPENAI_MODELS:
            return True

        # Try to make a call with the model to verify
        try:
            await self._client.chat.completions.create(
                model=model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            error_str = str(e).lower()
            if (
                "not found" in error_str
                or "does not exist" in error_str
                or "invalid" in error_str
            ):
                raise ProviderModelNotFoundError(
                    model_name,
                    provider_name=self.name,
                    available_models=list(OPENAI_MODELS.keys()),
                ) from e
            self._handle_api_error(e)
            raise

    def get_capabilities(self) -> LLMProviderCapabilities:
        """Return OpenAI provider capabilities.

        Returns:
            LLMProviderCapabilities with OpenAI-specific information.
        """
        context_length = OPENAI_MODELS.get(self._model, 128000)
        # O1 models don't support system prompts or streaming the same way
        is_o1_model = self._model.startswith("o1")
        return LLMProviderCapabilities(
            supports_streaming=not is_o1_model,  # O1 models have limited streaming
            supports_system_prompt=not is_o1_model,  # O1 models use developer messages
            max_tokens=16384 if "gpt-4o" in self._model else 4096,
            max_context_length=context_length,
            models=list(OPENAI_MODELS.keys()),
            supports_function_calling=True,
            supports_vision="gpt-4o" in self._model or "gpt-4-turbo" in self._model,
        )

    @with_retry(max_attempts=3, base_delay=1.0, max_delay=30.0)
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
            f"Generating with OpenAI model {self._model}, prompt length: {len(prompt)}"
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""

            logger.debug(f"OpenAI response length: {len(content)}")
            return content

        except (
            ProviderConnectionError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
            ProviderModelNotFoundError,
        ):
            raise
        except Exception as e:
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
        except Exception as e:
            self._handle_api_error(e)
            raise

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"openai:{self._model}"
