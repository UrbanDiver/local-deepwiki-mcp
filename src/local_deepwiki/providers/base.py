"""Base classes for providers."""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, AsyncIterator, Callable

from local_deepwiki.errors import ProviderError as BaseProviderError

logger = logging.getLogger(__name__)


# =============================================================================
# Standardized Provider Exceptions
# =============================================================================


class ProviderError(BaseProviderError):
    """Base exception for all provider errors.

    Inherits from local_deepwiki.errors.ProviderError (DeepWikiError subclass)
    to provide consistent error handling with hints and context.

    This class maintains backward compatibility with existing code that uses
    the simpler (message, provider_name) signature while also supporting
    the richer DeepWikiError features (hint, context, original_error).
    """

    def __init__(
        self,
        message: str,
        provider_name: str | None = None,
        *,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        # Call the parent (BaseProviderError) __init__ with all parameters
        super().__init__(
            message=message,
            hint=hint,
            context=context,
            provider_name=provider_name,
            original_error=original_error,
        )


class ProviderConnectionError(ProviderError):
    """Raised when a provider cannot be reached or connected to."""

    def __init__(
        self,
        message: str,
        provider_name: str | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(
            message,
            provider_name,
            original_error=original_error,
            hint="Check your network connection and verify the service is accessible.",
        )


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rate limits the request."""

    def __init__(
        self,
        message: str,
        provider_name: str | None = None,
        retry_after: float | None = None,
    ):
        self.retry_after = retry_after
        hint = "Wait a few minutes and try again, or consider upgrading your API plan."
        if retry_after:
            hint = f"Rate limited. Retry after {retry_after} seconds."
        super().__init__(message, provider_name, hint=hint)


class ProviderModelNotFoundError(ProviderError):
    """Raised when the requested model is not available."""

    def __init__(
        self,
        model: str,
        provider_name: str | None = None,
        available_models: list[str] | None = None,
    ):
        self.model = model
        self.available_models = available_models or []
        if available_models:
            models_str = ", ".join(available_models[:10])
            if len(available_models) > 10:
                models_str += f"... ({len(available_models)} total)"
            message = f"Model '{model}' not found. Available models: {models_str}"
            hint = f"Try one of the available models: {models_str}"
        else:
            message = f"Model '{model}' not found"
            hint = "Check the model name and ensure it's accessible in your account."
        super().__init__(message, provider_name, hint=hint)


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication with the provider fails."""

    pass


class ProviderConfigurationError(ProviderError):
    """Raised when the provider is misconfigured."""

    pass


# =============================================================================
# Provider Capabilities
# =============================================================================


@dataclass
class LLMProviderCapabilities:
    """Capabilities of an LLM provider."""

    supports_streaming: bool = True
    supports_system_prompt: bool = True
    max_tokens: int = 4096
    max_context_length: int = 128000
    models: list[str] = field(default_factory=list)
    supports_function_calling: bool = False
    supports_vision: bool = False


@dataclass
class EmbeddingProviderCapabilities:
    """Capabilities of an embedding provider."""

    max_batch_size: int = 100
    max_tokens_per_text: int = 8192
    dimension: int = 0
    models: list[str] = field(default_factory=list)
    supports_truncation: bool = True


# =============================================================================
# Retry Logic
# =============================================================================


# Exception types that should trigger a retry
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Covers network-related OS errors
    ProviderConnectionError,
    ProviderRateLimitError,
)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for adding retry logic with exponential backoff to async functions.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        exponential_base: Base for exponential backoff calculation.
        jitter: Whether to add random jitter to delays.

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.warning(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} attempt {attempt} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                except Exception as e:  # noqa: BLE001
                    # Broad catch is intentional: different API providers (Anthropic, OpenAI,
                    # Ollama) raise different exception types for rate limits. We inspect
                    # the error message to determine retry behavior, and re-raise immediately
                    # if not a recognized retryable condition.
                    error_str = str(e).lower()
                    if "rate" in error_str and "limit" in error_str:
                        last_exception = e
                        if attempt == max_attempts:
                            logger.warning(
                                f"{func.__name__} rate limited after {max_attempts} attempts"
                            )
                            raise

                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(f"{func.__name__} rate limited. Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                    elif "overloaded" in error_str or "503" in error_str or "502" in error_str:
                        # Server overloaded - retry with backoff
                        last_exception = e
                        if attempt == max_attempts:
                            raise

                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            f"{func.__name__} server overloaded. Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        # Non-retryable error
                        raise

            # Should not reach here, but just in case
            if last_exception:  # pragma: no cover
                raise last_exception  # pragma: no cover
            raise RuntimeError(f"{func.__name__} failed unexpectedly")

        return wrapper

    return decorator


# =============================================================================
# Base Provider Classes
# =============================================================================


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    All embedding providers must implement the abstract methods defined here.
    The base class provides default implementations for optional methods.
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ProviderConnectionError: If the provider cannot be reached.
            ProviderRateLimitError: If rate limited by the provider.
            ProviderAuthenticationError: If authentication fails.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the provider name.

        Returns:
            A string identifier for this provider (e.g., "openai:text-embedding-3-small").
        """
        pass

    async def validate_connectivity(self) -> bool:
        """Test that the provider is reachable and configured correctly.

        Returns:
            True if the provider is accessible and properly configured.

        Raises:
            ProviderConnectionError: If the provider cannot be reached.
            ProviderAuthenticationError: If authentication fails.
            ProviderConfigurationError: If misconfigured.
        """
        # Default implementation: try to embed a simple text
        try:
            await self.embed(["test"])
            return True
        except Exception as e:
            raise ProviderConnectionError(
                f"Failed to validate connectivity: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

    def get_max_batch_size(self) -> int:
        """Return maximum number of texts that can be embedded in a single call.

        Returns:
            Maximum batch size. Default is 100.
        """
        return 100

    def get_max_tokens(self) -> int:
        """Return maximum tokens per text.

        Returns:
            Maximum tokens per text. Default is 8192.
        """
        return 8192

    def get_capabilities(self) -> EmbeddingProviderCapabilities:
        """Return provider capabilities.

        Returns:
            EmbeddingProviderCapabilities dataclass with provider information.
        """
        return EmbeddingProviderCapabilities(
            max_batch_size=self.get_max_batch_size(),
            max_tokens_per_text=self.get_max_tokens(),
            dimension=self.get_dimension(),
        )


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers must implement the abstract methods defined here.
    The base class provides default implementations for optional methods.
    """

    @abstractmethod
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
            temperature: Sampling temperature (0.0 to 1.0+).

        Returns:
            Generated text.

        Raises:
            ProviderConnectionError: If the provider cannot be reached.
            ProviderRateLimitError: If rate limited by the provider.
            ProviderAuthenticationError: If authentication fails.
            ProviderModelNotFoundError: If the model is not available.
        """
        pass

    @abstractmethod
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
            ProviderConnectionError: If the provider cannot be reached.
            ProviderRateLimitError: If rate limited by the provider.
            ProviderAuthenticationError: If authentication fails.
            ProviderModelNotFoundError: If the model is not available.
        """
        # Make this an async generator for proper typing
        if False:  # pragma: no cover
            yield ""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the provider name.

        Returns:
            A string identifier for this provider (e.g., "anthropic:claude-sonnet-4-20250514").
        """
        pass

    async def validate_connectivity(self) -> bool:
        """Test that the provider is reachable and configured correctly.

        Returns:
            True if the provider is accessible and properly configured.

        Raises:
            ProviderConnectionError: If the provider cannot be reached.
            ProviderAuthenticationError: If authentication fails.
            ProviderConfigurationError: If misconfigured.
        """
        # Default implementation: try a simple generation
        try:
            await self.generate("Say 'OK'", max_tokens=10)
            return True
        except ProviderModelNotFoundError:
            # Model not found is a valid response - connectivity works
            raise
        except Exception as e:
            raise ProviderConnectionError(
                f"Failed to validate connectivity: {e}",
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
            ProviderConnectionError: If the provider cannot be reached.
        """
        # Default implementation - subclasses should override for better validation
        # This just checks if the current model matches
        current_model = self.name.split(":")[-1] if ":" in self.name else self.name
        if current_model == model_name:
            return True
        raise ProviderModelNotFoundError(model_name, provider_name=self.name)

    def get_capabilities(self) -> LLMProviderCapabilities:
        """Return provider capabilities.

        Returns:
            LLMProviderCapabilities dataclass with provider information.
        """
        return LLMProviderCapabilities()
