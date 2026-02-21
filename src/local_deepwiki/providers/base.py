"""Base classes for providers."""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, AsyncIterator, Callable

from local_deepwiki.errors import BaseProviderError
from local_deepwiki.logging import get_logger

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderCapabilities",
    "LLMProvider",
    "LLMProviderCapabilities",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderModelNotFoundError",
    "ProviderRateLimitError",
    "RETRYABLE_EXCEPTIONS",
    "handle_api_status_error",
    "validate_provider_credentials",
    "with_retry",
]

logger = get_logger(__name__)


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
# Credential Validation
# =============================================================================


def validate_provider_credentials(
    provider_name: str,
    api_key: str | None,
    key_type: str,
    env_var: str,
    *,
    display_name: str | None = None,
) -> str:
    """Validate and return an API key, raising ProviderAuthenticationError if invalid.

    Consolidates the repeated credential validation pattern used by OpenAI and
    Anthropic providers: get key -> check presence -> validate format.

    Args:
        provider_name: Provider identifier for the exception
                       (e.g. ``"openai:gpt"``).
        api_key: The API key to validate (may be None).
        key_type: Provider key type passed to
                  ``CredentialManager.validate_key_format``
                  (e.g. ``"openai"``, ``"anthropic"``).
        env_var: Environment variable name for the error hint
                 (e.g. ``"OPENAI_API_KEY"``).
        display_name: Human-readable provider name used in error messages
                      (e.g. ``"OpenAI"``).  Defaults to *key_type* with
                      its first letter capitalised.

    Returns:
        The validated API key string.

    Raises:
        ProviderAuthenticationError: If no key is provided or the format
            is invalid.
    """
    from local_deepwiki.providers.credentials import CredentialManager

    label = display_name if display_name is not None else key_type.capitalize()

    if not api_key:
        raise ProviderAuthenticationError(
            f"No {label} API key configured. Set {env_var} environment variable.",
            provider_name=provider_name,
        )

    if not CredentialManager.validate_key_format(api_key, key_type):
        raise ProviderAuthenticationError(
            f"{label} API key format appears invalid.",
            provider_name=provider_name,
        )

    return api_key


# =============================================================================
# Shared API Error Handling
# =============================================================================


def handle_api_status_error(
    e: Exception,
    *,
    provider_name: str,
    api_label: str,
    model: str | None = None,
    available_models: list[str] | None = None,
    not_found_extra_patterns: tuple[str, ...] = (),
    auth_error_type: type | None = None,
    status_error_type: type | None = None,
    connection_error_type: type | None = None,
) -> None:
    """Convert SDK-specific API errors to standardized provider errors.

    This consolidates the duplicated error-handling logic shared by the
    Anthropic, OpenAI LLM, and OpenAI embedding providers.

    Args:
        e: The original exception from the SDK.
        provider_name: Provider name for error messages.
        api_label: Human label (e.g. "Anthropic API", "OpenAI API").
        model: Model name (enables model-not-found handling when set).
        available_models: Known models to suggest on model-not-found.
        not_found_extra_patterns: Additional lowered substrings that indicate
            a model-not-found error (e.g. ``("does not exist",)``).
        auth_error_type: SDK's AuthenticationError class.
        status_error_type: SDK's APIStatusError class.
        connection_error_type: SDK's APIConnectionError class.
    """
    if auth_error_type and isinstance(e, auth_error_type):
        raise ProviderAuthenticationError(
            f"{api_label} authentication failed. Check your API key.",
            provider_name=provider_name,
        ) from e

    if status_error_type and isinstance(e, status_error_type):
        error_str = str(e).lower()
        status_code = getattr(e, "status_code", None)

        if status_code == 429 or "rate" in error_str:
            retry_after = None
            response = getattr(e, "response", None)
            if response:
                retry_after_str = response.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = float(retry_after_str)
                    except ValueError:
                        pass
            raise ProviderRateLimitError(
                f"{api_label} rate limit exceeded: {e}",
                provider_name=provider_name,
                retry_after=retry_after,
            ) from e

        if model is not None:
            not_found_patterns = ("not found", *not_found_extra_patterns)
            if status_code == 404 or any(p in error_str for p in not_found_patterns):
                raise ProviderModelNotFoundError(
                    model,
                    provider_name=provider_name,
                    available_models=available_models or [],
                ) from e

    if connection_error_type and isinstance(e, connection_error_type):
        raise ProviderConnectionError(
            f"Failed to connect to {api_label}: {e}",
            provider_name=provider_name,
            original_error=e,
        ) from e


# =============================================================================
# Provider Capabilities
# =============================================================================


@dataclass(frozen=True, slots=True)
class LLMProviderCapabilities:
    """Capabilities of an LLM provider."""

    supports_streaming: bool = True
    supports_system_prompt: bool = True
    max_tokens: int = 4096
    max_context_length: int = 128000
    models: list[str] = field(default_factory=list)
    supports_function_calling: bool = False
    supports_vision: bool = False


@dataclass(frozen=True, slots=True)
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
    *,
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
                        logger.warning(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            max_attempts,
                            e,
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)), max_delay
                    )
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        "%s attempt %d failed: %s. Retrying in %.2fs...",
                        func.__name__,
                        attempt,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                except Exception as e:  # noqa: BLE001 - Intentional broad catch for API resilience: different providers (Anthropic, OpenAI, Ollama) raise different exception types for rate limits and server errors. We inspect error messages to detect retryable conditions and re-raise immediately if not recognized.
                    error_str = str(e).lower()
                    if "rate" in error_str and "limit" in error_str:
                        last_exception = e
                        if attempt == max_attempts:
                            logger.warning(
                                "%s rate limited after %d attempts",
                                func.__name__,
                                max_attempts,
                            )
                            raise

                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            "%s rate limited. Retrying in %.2fs...",
                            func.__name__,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    elif (
                        "overloaded" in error_str
                        or "503" in error_str
                        or "502" in error_str
                    ):
                        # Server overloaded - retry with backoff
                        last_exception = e
                        if attempt == max_attempts:
                            raise

                        delay = min(base_delay * (exponential_base**attempt), max_delay)
                        if jitter:
                            delay = delay * (0.5 + random.random())

                        logger.warning(
                            "%s server overloaded. Retrying in %.2fs...",
                            func.__name__,
                            delay,
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

    @property
    @abstractmethod
    def dimension(self) -> int:
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
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ProviderConnectionError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
        ) as e:
            raise ProviderConnectionError(
                f"Failed to validate connectivity: {e}",
                provider_name=self.name,
                original_error=e,
            ) from e

    @property
    def max_batch_size(self) -> int:
        """Return maximum number of texts that can be embedded in a single call.

        Returns:
            Maximum batch size. Default is 100.
        """
        return 100

    @property
    def max_tokens(self) -> int:
        """Return maximum tokens per text.

        Returns:
            Maximum tokens per text. Default is 8192.
        """
        return 8192

    @property
    def capabilities(self) -> EmbeddingProviderCapabilities:
        """Return provider capabilities.

        Returns:
            EmbeddingProviderCapabilities dataclass with provider information.
        """
        return EmbeddingProviderCapabilities(
            max_batch_size=self.max_batch_size,
            max_tokens_per_text=self.max_tokens,
            dimension=self.dimension,
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
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ProviderConnectionError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
        ) as e:
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

    @property
    def capabilities(self) -> LLMProviderCapabilities:
        """Return provider capabilities.

        Returns:
            LLMProviderCapabilities dataclass with provider information.
        """
        return LLMProviderCapabilities()
