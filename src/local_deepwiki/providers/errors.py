"""Standardized provider exception classes and error handling utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from local_deepwiki.errors import BaseProviderError

__all__ = [
    "ApiErrorConfig",
    "ProviderAuthenticationError",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderModelNotFoundError",
    "ProviderRateLimitError",
    "handle_api_status_error",
    "validate_provider_credentials",
]


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


@dataclass(frozen=True, slots=True)
class ApiErrorConfig:
    """Provider-specific error handling configuration."""

    provider_name: str
    api_label: str
    model: str | None = None
    available_models: list[str] | None = None
    not_found_extra_patterns: tuple[str, ...] = ()
    auth_error_type: type | None = None
    status_error_type: type | None = None
    connection_error_type: type | None = None


def _extract_retry_after(e: Exception) -> float | None:
    """Extract Retry-After header value from an API error response."""
    response = getattr(e, "response", None)
    if not response:
        return None
    retry_after_str = response.headers.get("retry-after")
    if not retry_after_str:
        return None
    try:
        return float(retry_after_str)
    except ValueError:
        return None


def _handle_status_error(e: Exception, config: ApiErrorConfig) -> None:
    """Raise the appropriate provider error for an API status error."""
    error_str = str(e).lower()
    status_code = getattr(e, "status_code", None)

    if status_code == 429 or "rate" in error_str:
        raise ProviderRateLimitError(
            f"{config.api_label} rate limit exceeded: {e}",
            provider_name=config.provider_name,
            retry_after=_extract_retry_after(e),
        ) from e

    if config.model is not None:
        not_found_patterns = ("not found", *config.not_found_extra_patterns)
        if status_code == 404 or any(p in error_str for p in not_found_patterns):
            raise ProviderModelNotFoundError(
                config.model,
                provider_name=config.provider_name,
                available_models=config.available_models or [],
            ) from e


def handle_api_status_error(e: Exception, config: ApiErrorConfig) -> None:
    """Convert SDK-specific API errors to standardized provider errors.

    This consolidates the duplicated error-handling logic shared by the
    Anthropic, OpenAI LLM, and OpenAI embedding providers.

    Args:
        e: The original exception from the SDK.
        config: Provider-specific error handling configuration.
    """
    if config.auth_error_type and isinstance(e, config.auth_error_type):
        raise ProviderAuthenticationError(
            f"{config.api_label} authentication failed. Check your API key.",
            provider_name=config.provider_name,
        ) from e

    if config.status_error_type and isinstance(e, config.status_error_type):
        _handle_status_error(e, config)

    if config.connection_error_type and isinstance(e, config.connection_error_type):
        raise ProviderConnectionError(
            f"Failed to connect to {config.api_label}: {e}",
            provider_name=config.provider_name,
            original_error=e,
        ) from e
