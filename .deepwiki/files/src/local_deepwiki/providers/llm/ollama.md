# Ollama Provider Module

## File Overview

The `ollama.py` module provides an LLM provider implementation for integrating with Ollama, a local language model server. This module implements the [LLMProvider](../base.md) interface to enable communication with Ollama models through its API, including connection management, health checking, and text generation capabilities.

## Classes

### OllamaConnectionError

A custom exception class that handles connection failures to the Ollama server.

**Purpose**: Provides detailed error messages and troubleshooting guidance when the Ollama server cannot be reached.

**Constructor Parameters**:
- `base_url` (str): The URL of the Ollama server that failed to connect
- `original_error` (Exception | None): The underlying exception that caused the connection failure (optional)

**Features**:
- Stores the base URL and original error for debugging
- Provides helpful error messages with setup instructions including installation and verification steps

### OllamaModelNotFoundError

A custom exception class for handling cases where a requested Ollama model is not available on the server.

### OllamaProvider

The [main](../../export/pdf.md) provider class that implements the [LLMProvider](../base.md) interface for Ollama integration.

**Purpose**: Manages communication with an Ollama server, including model operations, health checking, and text generation.

#### Methods

##### `__init__(model: str = "llama3.2", base_url: str = "http://localhost:11434")`

Initializes the Ollama provider with connection and model configuration.

**Parameters**:
- `model` (str): The Ollama model name to use (defaults to "llama3.2")
- `base_url` (str): The Ollama API base URL (defaults to "http://localhost:11434")

**Behavior**:
- Creates an AsyncClient instance for API communication
- Stores model and URL configuration
- Initializes health check tracking

##### `check_health()`

Performs a health check to verify the Ollama server is accessible and the specified model is available.

##### `_ensure_healthy()`

Internal method that ensures the provider has passed health checks before performing operations.

##### `generate()`

Generates text responses using the configured Ollama model.

##### `generate_stream()`

Provides streaming text generation capabilities, returning an AsyncIterator for real-time response processing.

##### `name`

Property that returns the provider's name identifier.

## Usage Examples

### Basic Provider Setup

```python
from local_deepwiki.providers.llm.ollama import OllamaProvider

# Initialize with default settings
provider = OllamaProvider()

# Initialize with custom model and URL
provider = OllamaProvider(
    model="codellama",
    base_url="http://192.168.1.100:11434"
)
```

### Error Handling

```python
from local_deepwiki.providers.llm.ollama import OllamaConnectionError, OllamaModelNotFoundError

try:
    provider = OllamaProvider(base_url="http://localhost:11434")
    await provider.check_health()
except OllamaConnectionError as e:
    print(f"Connection failed to {e.base_url}")
    if e.original_error:
        print(f"Underlying error: {e.original_error}")
except OllamaModelNotFoundError as e:
    print("Requested model not available")
```

## Related Components

This module integrates with several other components:

- **[LLMProvider](../base.md)**: Base class that defines the provider interface (imported from `local_deepwiki.providers.base`)
- **[with_retry](../base.md)**: Decorator for retry functionality (imported from `local_deepwiki.providers.base`)
- **AsyncClient**: Ollama's async client for API communication (imported from `ollama`)
- **ResponseError**: Ollama's error handling (imported from `ollama`)
- **Logging**: Uses the application's logging system (imported from `local_deepwiki.logging`)

The module follows the provider pattern established by the base [LLMProvider](../base.md) class and integrates with the broader local_deepwiki system for logging and error handling.

## API Reference

### class `OllamaConnectionError`

**Inherits from:** `Exception`

Raised when Ollama server is not accessible.

**Methods:**

#### `__init__`

```python
def __init__(base_url: str, original_error: Exception | None = None)
```


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | - | - |
| `original_error` | `Exception | None` | `None` | - |


### class `OllamaModelNotFoundError`

**Inherits from:** `Exception`

Raised when the requested model is not available in Ollama.

**Methods:**

#### `__init__`

```python
def __init__(model: str, available_models: list[str] | None = None)
```


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | - | - |
| `available_models` | `list[str] | None` | `None` | - |


### class `OllamaProvider`

**Inherits from:** [`LLMProvider`](../base.md)

LLM provider using local Ollama.

**Methods:**

#### `__init__`

```python
def __init__(model: str = "llama3.2", base_url: str = "http://localhost:11434")
```

Initialize the Ollama provider.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"llama3.2"` | Ollama model name. |
| `base_url` | `str` | `"http://localhost:11434"` | Ollama API base URL. |

#### `check_health`

```python
async def check_health() -> bool
```

Check if Ollama is running and the model is available.

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
    class OllamaConnectionError {
        +base_url
        +original_error
        -__init__()
    }
    class OllamaModelNotFoundError {
        +model
        +available_models
        -__init__()
    }
    class OllamaProvider {
        -__init__(model: str, base_url: str)
        +check_health() bool
        -_ensure_healthy() None
        +generate(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float) str
        +generate_stream(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float) AsyncIterator[str]
        +name() str
    }
    OllamaConnectionError --|> Exception
    OllamaModelNotFoundError --|> Exception
    OllamaProvider --|> LLMProvider
```

## Call Graph

```mermaid
flowchart TD
    N0[AsyncClient]
    N1[OllamaConnectionError]
    N2[OllamaConnectionError.__init__]
    N3[OllamaModelNotFoundError]
    N4[OllamaModelNotFoundError.__...]
    N5[OllamaProvider.__init__]
    N6[OllamaProvider._ensure_healthy]
    N7[OllamaProvider.check_health]
    N8[OllamaProvider.generate]
    N9[OllamaProvider.generate_stream]
    N10[__init__]
    N11[_ensure_healthy]
    N12[chat]
    N13[check_health]
    N2 --> N10
    N4 --> N10
    N5 --> N0
    N7 --> N3
    N7 --> N1
    N6 --> N13
    N8 --> N11
    N8 --> N12
    N8 --> N3
    N8 --> N1
    N9 --> N11
    N9 --> N12
    N9 --> N3
    N9 --> N1
    classDef func fill:#e1f5fe
    class N0,N1,N3,N10,N11,N12,N13 func
    classDef method fill:#fff3e0
    class N2,N4,N5,N6,N7,N8,N9 method
```

## Relevant Source Files

- `src/local_deepwiki/providers/llm/ollama.py:13-26`
