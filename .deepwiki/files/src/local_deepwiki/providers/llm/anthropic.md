# Anthropic Provider

## File Overview

This file implements an Anthropic LLM provider for the local_deepwiki system. It provides integration with Anthropic's Claude models through their AsyncAnthropic client, implementing the [LLMProvider](../base.md) interface for consistent usage across the application.

## Classes

### AnthropicProvider

The AnthropicProvider class serves as the [main](../../export/pdf.md) interface for interacting with Anthropic's language models. It inherits from the [LLMProvider](../base.md) base class and implements the required methods for LLM operations.

**Key Features:**
- Asynchronous operation support through AsyncAnthropic
- Built-in retry mechanism via the [with_retry](../base.md) [decorator](../base.md)
- Environment-based configuration
- Logging integration

## Dependencies

The module relies on several key components:

- **AsyncAnthropic**: The official Anthropic client for async operations
- **[LLMProvider](../base.md)**: Base class that defines the provider interface
- **[with_retry](../base.md)**: Decorator for implementing retry logic on failed requests
- **[get_logger](../../logging.md)**: Logging utility for the local_deepwiki system

## Environment Configuration

The provider uses environment variables for configuration, accessed through the `os` module. This allows for flexible deployment without hardcoded credentials.

## Related Components

This provider works within the broader local_deepwiki ecosystem:

- Implements the [LLMProvider](../base.md) interface for consistent provider switching
- Uses the application's logging system through [get_logger](../../logging.md)
- Leverages the retry mechanism from the base provider module

## Usage Context

As an LLM provider implementation, this class would typically be instantiated and used by higher-level components that need to interact with Anthropic's models. The async nature of the implementation makes it suitable for handling multiple concurrent requests efficiently.

## API Reference

### class `AnthropicProvider`

**Inherits from:** [`LLMProvider`](../base.md)

LLM provider using Anthropic API.

**Methods:**

#### `__init__`

```python
def __init__(model: str = "claude-sonnet-4-20250514", api_key: str | None = None)
```

Initialize the Anthropic provider.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"claude-sonnet-4-20250514"` | Anthropic model name. |
| `api_key` | `str | None` | `None` | Optional API key. Uses ANTHROPIC_API_KEY env var if not provided. |

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

#### `name`

```python
def name() -> str
```

Get the provider name.



## Class Diagram

```mermaid
classDiagram
    class AnthropicProvider {
        -_model
        -_client
        -__init__()
        +generate() -> str
        +generate_stream() -> AsyncIterator[str]
        +name() -> str
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

## Relevant Source Files

- `src/local_deepwiki/providers/llm/anthropic.py:14-99`
