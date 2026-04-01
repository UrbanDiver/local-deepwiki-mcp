# Module: providers

## Module Purpose

The `providers` module provides abstractions and implementations for embedding and LLM (Large [Language](../files/src/local_deepwiki/models/foundation.md) Model) providers used by the Local DeepWiki MCP Server. It defines base interfaces and error types for providers, along with concrete implementations for local embeddings, OpenAI, and Anthropic services.

## Key Classes and Functions

### ProviderError
Base exception class for all provider-related errors, inheriting from [`local_deepwiki.errors.BaseProviderError`](../files/src/local_deepwiki/errors.md).

### ProviderConnectionError
Raised when a provider cannot be reached or connected to.

### ProviderRateLimitError
Raised when a provider rate limits the request.

### ProviderModelNotFoundError
Raised when the requested model is not available.

### ProviderAuthenticationError
Raised when authentication with the provider fails.

### ProviderConfigurationError
Raised when the provider is misconfigured.

### LLMProviderCapabilities
Data class describing capabilities of an LLM provider, including streaming support, system prompt support, token limits, and supported models.

### EmbeddingProviderCapabilities
Data class describing capabilities of an embedding provider, including batch size, token limits, and vector dimension.

### EmbeddingProvider
Abstract base class defining the interface for embedding providers with methods:
- `embed(texts: list[str]) -> list[list[float]]`
- `dimension() -> int`
- `name() -> str`
- `validate_connectivity() -> bool`
- `max_batch_size() -> int`
- `max_tokens() -> int`

### LLMProvider
Abstract base class defining the interface for LLM providers.

### CredentialManager
Secure credential management utility that retrieves API keys from environment variables without storing them in memory, preventing accidental exposure.

## How Components Interact

The module establishes a hierarchy of provider abstractions with error handling. The [`EmbeddingProvider`](../files/src/local_deepwiki/providers/base.md) and [`LLMProvider`](../files/src/local_deepwiki/providers/base.md) abstract classes define the interfaces for embedding and LLM services respectively. Concrete implementations (like [`LocalEmbeddingProvider`](../files/src/local_deepwiki/providers/embeddings/local.md), [`OpenAIEmbeddingProvider`](../files/src/local_deepwiki/providers/embeddings/openai.md), [`OpenAILLMProvider`](../files/src/local_deepwiki/providers/llm/openai.md), [`AnthropicProvider`](../files/src/local_deepwiki/providers/llm/anthropic.md)) implement these interfaces.

Error types inherit from [`ProviderError`](../files/src/local_deepwiki/providers/base.md) to provide consistent error handling across different providers. The [`CredentialManager`](../files/src/local_deepwiki/providers/credentials.md) class provides secure access to API keys without storing them in memory, supporting authentication for various providers through environment variables.

## Usage Examples

### Using CredentialManager```python
from local_deepwiki.providers.credentials import CredentialManager

# Get an OpenAI API key from environment
api_key = CredentialManager.get_api_key("OPENAI_API_KEY", "openai")
if api_key:
    print("API key found")
else:
    print("No API key found")

# Validate a key format
is_valid = CredentialManager.validate_key_format(api_key, "openai")
```
### Using EmbeddingProvider Interface```python
from local_deepwiki.providers.base import EmbeddingProvider

# Abstract usage - concrete implementations would be used in practice
async def use_embedding_provider(provider: EmbeddingProvider):
    texts = ["Hello world", "Foo bar"]
    embeddings = await provider.embed(texts)
    print(f"Generated {len(embeddings)} embeddings")
    print(f"Dimension: {provider.dimension()}")
```
### Using LLMProvider Interface```python
from local_deepwiki.providers.base import LLMProvider

# Abstract usage - concrete implementations would be used in practice
async def use_llm_provider(provider: LLMProvider):
    response = await provider.generate("Hello, world!")
    print(response)
```
## Dependencies

- `local_deepwiki.errors`
- `local_deepwiki.logging`
- `local_deepwiki.providers.credentials`
- `abc` (Python standard library)
- `asyncio` (Python standard library)
- `collections.abc` (Python standard library)
- `dataclasses` (Python standard library)
- `functools` (Python standard library)
- `typing` (Python standard library)

## Relevant Source Files

The following source files were used to generate this documentation:

- `src/local_deepwiki/providers/__init__.py`
- [`src/local_deepwiki/providers/credentials.py:12-81`](../files/src/local_deepwiki/providers/credentials.md)
- [`src/local_deepwiki/providers/base.py:41-68`](../files/src/local_deepwiki/providers/base.md)
- `src/local_deepwiki/providers/llm/__init__.py:16-19`
- [`src/local_deepwiki/providers/llm/ollama.py:23-38`](../files/src/local_deepwiki/providers/llm/ollama.md)
- [`src/local_deepwiki/providers/llm/cached.py:14-160`](../files/src/local_deepwiki/providers/llm/cached.md)
- [`src/local_deepwiki/providers/llm/anthropic.py:45-349`](../files/src/local_deepwiki/providers/llm/anthropic.md)
- [`src/local_deepwiki/providers/embeddings/local.py:31-168`](../files/src/local_deepwiki/providers/embeddings/local.md)
- [`src/local_deepwiki/providers/embeddings/openai.py:26-201`](../files/src/local_deepwiki/providers/embeddings/openai.md)
- [`src/local_deepwiki/providers/llm/openai.py:48-352`](../files/src/local_deepwiki/providers/llm/openai.md)


*Showing 10 of 12 source files.*
