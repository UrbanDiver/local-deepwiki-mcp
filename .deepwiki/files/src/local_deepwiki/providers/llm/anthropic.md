# Anthropic Provider Module

## File Overview

This module implements an Anthropic LLM provider for the local_deepwiki system. It provides an interface to Anthropic's language models through their AsyncAnthropic client, implementing both regular and streaming text generation capabilities.

## Classes

### AnthropicProvider

The AnthropicProvider class extends the [LLMProvider](../base.md) base class to provide integration with Anthropic's language models. This class handles authentication, request formatting, and response processing for Anthropic's API.

**Methods:**

- `__init__`: Initializes the provider with necessary configuration
- `generate`: Performs standard text generation requests
- `generate_stream`: Performs streaming text generation requests that yield results incrementally
- `name`: Returns the provider's identifier name

## Key Features

- **Asynchronous Operations**: Built on AsyncAnthropic for non-blocking API calls
- **Streaming Support**: Implements `AsyncIterator` for real-time response streaming
- **Error Handling**: Utilizes the [`with_retry`](../base.md) [decorator](../base.md) for robust request handling
- **Logging Integration**: Uses the local_deepwiki logging system for monitoring and debugging

## Related Components

This module integrates with several other components in the local_deepwiki system:

- **[LLMProvider](../base.md)**: Base class that defines the interface for all LLM providers
- **Logging System**: Uses [`get_logger`](../../logging.md) for consistent logging across the application
- **Retry Mechanism**: Leverages [`with_retry`](../base.md) [decorator](../base.md) for handling transient failures

## Environment Dependencies

The module relies on the `os` module for environment variable access, typically for API key configuration and other Anthropic-specific settings.

## Usage Context

This provider is designed to be used within the larger local_deepwiki framework as one of the available LLM backend options. It follows the standard provider pattern, allowing it to be swapped with other LLM providers while maintaining consistent interfaces for text generation tasks.

## API Reference

### class `AnthropicProvider`

**Inherits from:** [`LLMProvider`](../base.md)

LLM provider using Anthropic API.

**Methods:**


<details>
<summary>View Source (lines 14-144) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/better-search/src/local_deepwiki/providers/llm/anthropic.py#L14-L144">GitHub</a></summary>

```python
class AnthropicProvider(LLMProvider):
    # Methods: __init__, generate, generate_stream, name
```

</details>

#### `__init__`

```python
def __init__(model: str = "claude-sonnet-4-20250514", api_key: str | None = None)
```

Initialize the Anthropic provider.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"claude-sonnet-4-20250514"` | Anthropic model name. |
| `api_key` | `str | None` | `None` | Optional API key. Uses ANTHROPIC_API_KEY env var if not provided. |


<details>
<summary>View Source (lines 17-25) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/better-search/src/local_deepwiki/providers/llm/anthropic.py#L17-L25">GitHub</a></summary>

```python
def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        """Initialize the Anthropic provider.

        Args:
            model: Anthropic model name.
            api_key: Optional API key. Uses ANTHROPIC_API_KEY env var if not provided.
        """
        self._model = model
        self._client = AsyncAnthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
```

</details>

#### `generate`

```python
async def generate(prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> str
```

Generate text from a prompt.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | - | The user prompt. |
| `system_prompt` | `str | None` | `None` | Optional system prompt. |
| `max_tokens` | `int` | `4096` | Maximum tokens to generate. |
| `temperature` | `float` | `0.7` | Sampling temperature. |


<details>
<summary>View Source (lines 28-83) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/better-search/src/local_deepwiki/providers/llm/anthropic.py#L28-L83">GitHub</a></summary>

```python
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
        """
        logger.debug(f"Generating with Anthropic model {self._model}, prompt length: {len(prompt)}")

        # Use explicit arguments to satisfy type checker
        if system_prompt and temperature > 0:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt,
                temperature=temperature,
            )
        elif system_prompt:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt,
            )
        elif temperature > 0:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
        else:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

        # Get text from the first content block (should be TextBlock)
        first_block = response.content[0]
        content = first_block.text if hasattr(first_block, "text") else ""

        logger.debug(f"Anthropic response length: {len(content)}")
        return content
```

</details>

#### `generate_stream`

```python
async def generate_stream(prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> AsyncIterator[str]
```

Generate text from a prompt with streaming.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | - | The user prompt. |
| `system_prompt` | `str | None` | `None` | Optional system prompt. |
| `max_tokens` | `int` | `4096` | Maximum tokens to generate. |
| `temperature` | `float` | `0.7` | Sampling temperature. |


<details>
<summary>View Source (lines 85-139) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/better-search/src/local_deepwiki/providers/llm/anthropic.py#L85-L139">GitHub</a></summary>

```python
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
        """
        # Use explicit arguments to satisfy type checker
        if system_prompt and temperature > 0:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt,
                temperature=temperature,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        elif system_prompt:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                system=system_prompt,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        elif temperature > 0:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        else:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
```

</details>

#### `name`

```python
def name() -> str
```

Get the provider name.




<details>
<summary>View Source (lines 142-144) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/feature/better-search/src/local_deepwiki/providers/llm/anthropic.py#L142-L144">GitHub</a></summary>

```python
def name(self) -> str:
        """Get the provider name."""
        return f"anthropic:{self._model}"
```

</details>

## Class Diagram

```mermaid
classDiagram
    class AnthropicProvider {
        -__init__(model: str, api_key: str | None)
        +generate(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float) str
        +generate_stream(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float) AsyncIterator[str]
        +name() str
    }
    AnthropicProvider --|> LLMProvider
```

## Call Graph

```mermaid
flowchart TD
    N0[AnthropicProvider.__init__]
    N1[AnthropicProvider.generate]
    N2[AnthropicProvider.generate_...]
    N3[AsyncAnthropic]
    N4[create]
    N5[stream]
    N0 --> N3
    N1 --> N4
    N2 --> N5
    classDef func fill:#e1f5fe
    class N3,N4,N5 func
    classDef method fill:#fff3e0
    class N0,N1,N2 method
```

## Used By

Functions and methods in this file and their callers:

- **`AsyncAnthropic`**: called by `AnthropicProvider.__init__`
- **`create`**: called by `AnthropicProvider.generate`
- **`stream`**: called by `AnthropicProvider.generate_stream`

## Relevant Source Files

- `src/local_deepwiki/providers/llm/anthropic.py:14-144`
