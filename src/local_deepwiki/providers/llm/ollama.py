"""Ollama LLM provider."""

from __future__ import annotations

from typing import AsyncIterator, cast

from ollama import AsyncClient, ResponseError

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import (
    LLMProvider,
    LLMProviderCapabilities,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    with_retry,
)

logger = get_logger(__name__)


# Keep legacy exception classes for backward compatibility
class OllamaConnectionError(ProviderConnectionError):
    """Raised when Ollama server is not accessible.

    This is a specialized version of ProviderConnectionError for Ollama.
    """

    def __init__(self, base_url: str, original_error: Exception | None = None):
        self.base_url = base_url
        message = (
            f"Cannot connect to Ollama at {base_url}. "
            "Please ensure Ollama is running:\n"
            "  1. Install Ollama: https://ollama.ai/download\n"
            "  2. Start Ollama: `ollama serve`\n"
            "  3. Verify it's running: `curl {base_url}/api/tags`"
        )
        super().__init__(message, provider_name="ollama", original_error=original_error)


class OllamaModelNotFoundError(ProviderModelNotFoundError):
    """Raised when the requested model is not available in Ollama.

    This is a specialized version of ProviderModelNotFoundError for Ollama.
    """

    def __init__(self, model: str, available_models: list[str] | None = None):
        # Build a custom message with pull command
        self.model = model
        self.available_models = available_models or []
        if available_models:
            models_str = ", ".join(available_models[:10])
            if len(available_models) > 10:
                models_str += f"... ({len(available_models)} total)"
            message = (
                f"Model '{model}' not found in Ollama. "
                f"Available models: {models_str}\n"
                f"To download the model, run: `ollama pull {model}`"
            )
        else:
            message = (
                f"Model '{model}' not found in Ollama.\n"
                f"To download the model, run: `ollama pull {model}`"
            )
        # Call ProviderError.__init__ directly to set message
        super(ProviderModelNotFoundError, self).__init__(
            message, provider_name="ollama"
        )
        # Re-set attributes since parent __init__ may overwrite
        self.model = model
        self.available_models = available_models or []


class OllamaProvider(LLMProvider):
    """LLM provider using local Ollama."""

    def __init__(
        self, model: str = "llama3.2", base_url: str = "http://localhost:11434"
    ):
        """Initialize the Ollama provider.

        Args:
            model: Ollama model name.
            base_url: Ollama API base URL.
        """
        self._model = model
        self._base_url = base_url
        self._client = AsyncClient(host=base_url)
        self._health_checked = False
        self._available_models: list[str] = []

    async def check_health(self) -> bool:
        """Check if Ollama is running and the model is available.

        Returns:
            True if Ollama is healthy and model is available.

        Raises:
            OllamaConnectionError: If Ollama server is not accessible.
            OllamaModelNotFoundError: If the requested model is not available.
        """
        logger.debug("Checking Ollama health at %s", self._base_url)

        try:
            # Try to list models to verify connection
            models_response = await self._client.list()
            # ollama library returns typed objects with .models list and .model attribute
            self._available_models = [
                m.model for m in models_response.models if m.model is not None
            ]
            logger.debug("Ollama available models: %s", self._available_models)

            # Check if our model is available (handle both "model" and "model:tag" formats)
            model_base = self._model.split(":")[0]
            model_found = any(
                m == self._model
                or m.startswith(f"{self._model}:")
                or m.split(":")[0] == model_base
                for m in self._available_models
            )

            if not model_found:
                logger.error("Model '%s' not found in Ollama", self._model)
                raise OllamaModelNotFoundError(self._model, self._available_models)

            logger.info("Ollama health check passed: model '%s' available", self._model)
            self._health_checked = True
            return True

        except OllamaModelNotFoundError:
            raise
        except (ConnectionError, TimeoutError, OSError, ResponseError) as e:
            # Connection errors, timeouts, network errors, and Ollama API errors
            logger.error("Failed to connect to Ollama at %s: %s", self._base_url, e)
            raise OllamaConnectionError(self._base_url, e) from e

    async def _ensure_healthy(self) -> None:
        """Ensure Ollama is healthy before making requests.

        Only performs the check once per instance.
        """
        if not self._health_checked:
            await self.check_health()

    async def validate_connectivity(self) -> bool:
        """Test that Ollama is reachable and configured correctly.

        Returns:
            True if Ollama is accessible.

        Raises:
            ProviderConnectionError: If Ollama cannot be reached.
        """
        try:
            await self._client.list()
            return True
        except (ConnectionError, TimeoutError, OSError, ResponseError) as e:
            raise OllamaConnectionError(self._base_url, e) from e

    async def validate_model(self, model_name: str) -> bool:
        """Test that a specific model is available in Ollama.

        Args:
            model_name: The model name to validate.

        Returns:
            True if the model is available.

        Raises:
            ProviderModelNotFoundError: If the model is not available.
            ProviderConnectionError: If Ollama cannot be reached.
        """
        try:
            models_response = await self._client.list()
            available_models = [
                m.model for m in models_response.models if m.model is not None
            ]

            model_base = model_name.split(":")[0]
            model_found = any(
                m == model_name
                or m.startswith(f"{model_name}:")
                or m.split(":")[0] == model_base
                for m in available_models
            )

            if not model_found:
                raise OllamaModelNotFoundError(model_name, available_models)

            return True
        except OllamaModelNotFoundError:
            raise
        except (ConnectionError, TimeoutError, OSError, ResponseError) as e:
            # Connection errors, timeouts, network errors, and Ollama API errors
            raise OllamaConnectionError(self._base_url, e) from e

    @property
    def capabilities(self) -> LLMProviderCapabilities:
        """Return Ollama provider capabilities.

        Returns:
            LLMProviderCapabilities with Ollama-specific information.
        """
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_system_prompt=True,
            max_tokens=4096,  # Depends on model
            max_context_length=128000,  # Depends on model
            models=self._available_models,
            supports_function_calling=False,
            supports_vision=False,  # Some models support it
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
            OllamaConnectionError: If Ollama server is not accessible.
            OllamaModelNotFoundError: If the requested model is not available.
        """
        # Check health on first call
        await self._ensure_healthy()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(
            "Generating with Ollama model %s, prompt length: %d",
            self._model,
            len(prompt),
        )

        try:
            response = await self._client.chat(
                model=self._model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
                keep_alive="60m",
            )

            content = cast(str, response["message"]["content"])
            logger.debug("Ollama response length: %s", len(content))
            return content

        except ResponseError as e:
            # Handle model not found during generation (e.g., model was deleted)
            if "not found" in str(e).lower():
                logger.error("Model '%s' not found during generation", self._model)
                raise OllamaModelNotFoundError(self._model) from e
            raise
        except (ConnectionError, TimeoutError, OSError) as e:
            # Connection errors, timeouts, and network-related OS errors
            logger.error("Lost connection to Ollama: %s", e)
            self._health_checked = False  # Reset health check
            raise OllamaConnectionError(self._base_url, e) from e

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
            OllamaConnectionError: If Ollama server is not accessible.
            OllamaModelNotFoundError: If the requested model is not available.
        """
        # Check health on first call
        await self._ensure_healthy()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            async for chunk in await self._client.chat(
                model=self._model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
                keep_alive="60m",
                stream=True,
            ):
                if chunk["message"]["content"]:
                    yield chunk["message"]["content"]

        except ResponseError as e:
            if "not found" in str(e).lower():
                logger.error("Model '%s' not found during streaming", self._model)
                raise OllamaModelNotFoundError(self._model) from e
            raise
        except (ConnectionError, TimeoutError, OSError) as e:
            # Connection errors, timeouts, and network-related OS errors
            logger.error("Lost connection to Ollama during streaming: %s", e)
            self._health_checked = False
            raise OllamaConnectionError(self._base_url, e) from e

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"ollama:{self._model}"
