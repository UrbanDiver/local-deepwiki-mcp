"""Provider abstractions for embeddings and LLMs.

Submodules:
- ``errors`` -- Standardized provider exception hierarchy
- ``retry``  -- Retry decorator with exponential backoff
- ``base``   -- Abstract base classes (LLMProvider, EmbeddingProvider)
"""

from __future__ import annotations

from local_deepwiki.providers.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    LLMProvider,
    LLMProviderCapabilities,
)
from local_deepwiki.providers.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderRateLimitError,
    handle_api_status_error,
    validate_provider_credentials,
)
from local_deepwiki.providers.retry import RETRYABLE_EXCEPTIONS, with_retry

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
