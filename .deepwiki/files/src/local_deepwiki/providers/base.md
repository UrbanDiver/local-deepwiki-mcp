# Base Provider Module

## File Overview

This file defines the abstract base class for embedding providers in the local_deepwiki system. It establishes the interface that all concrete embedding provider implementations must follow.

## Classes

### EmbeddingProvider

An abstract base class that defines the contract for embedding providers. This class uses Python's ABC (Abstract Base Class) mechanism to ensure that all concrete implementations provide the required methods.

#### Abstract Methods

##### embed

```python
async def embed(self, texts: list[str]) -> list[list[float]]
```

Generate embeddings for a list of texts.

**Parameters:**
- `texts` (list[str]): List of text strings to embed

**Returns:**
- list[list[float]]: List of embedding vectors

This method is asynchronous and must be implemented by all concrete embedding provider classes.

##### get_dimension

```python
def get_dimension(self) -> int
```

Get the embedding dimension.

**Returns:**
- int: The dimension of the embedding vectors

This method returns the dimensionality of the embedding vectors produced by the provider.

#### Abstract Properties

The class also defines abstract properties (implementation not shown in the provided code), which concrete implementations must provide.

## Usage Examples

To create a concrete embedding provider, inherit from EmbeddingProvider and implement all abstract methods:

```python
from src.local_deepwiki.providers.base import EmbeddingProvider

class MyEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Implementation here
        pass
    
    def get_dimension(self) -> int:
        # Return the dimension of your embeddings
        return 768
```

## Implementation Notes

- All embedding providers must inherit from this base class
- The `embed` method is asynchronous, allowing for efficient batch processing of texts
- Concrete implementations must specify the exact dimension of their embedding vectors
- The class follows Python's ABC pattern to enforce interface compliance at runtime

## API Reference

### class `EmbeddingProvider`

**Inherits from:** `ABC`

Abstract base class for embedding providers.

**Methods:**

#### `embed`

```python
async def embed(texts: list[str]) -> list[list[float]]
```

Generate embeddings for a list of texts.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `texts` | `list[str]` | - | List of text strings to embed. |

#### `get_dimension`

```python
def get_dimension() -> int
```

Get the embedding dimension.

#### `name`

```python
def name() -> str
```

Get the provider name.


### class `LLMProvider`

**Inherits from:** `ABC`

Abstract base class for LLM providers.

**Methods:**

#### `generate`

```python
async def generate(prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> str
```

Generate text from a prompt.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
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


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
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


---

### Functions

#### `with_retry`

```python
def with_retry(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0, exponential_base: float = 2.0, jitter: bool = True) -> Callable[[Callable[..., Any]], Callable[..., Any]]
```

Decorator for adding retry logic with exponential backoff to async functions.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_attempts` | `int` | `3` | Maximum number of attempts before giving up. |
| `base_delay` | `float` | `1.0` | Initial delay between retries in seconds. |
| `max_delay` | `float` | `30.0` | Maximum delay between retries in seconds. |
| `exponential_base` | `float` | `2.0` | Base for exponential backoff calculation. |
| `jitter` | `bool` | `True` | Whether to add random jitter to delays. |

**Returns:** `Callable[[Callable[..., Any]], Callable[..., Any]]`


#### `decorator`

```python
def decorator(func: Callable[..., Any]) -> Callable[..., Any]
```


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `func` | `Callable[..., Any]` | - | - |

**Returns:** `Callable[..., Any]`


#### `wrapper`

`@wraps(func)`

```python
async def wrapper() -> Any
```

**Returns:** `Any`



## Class Diagram

```mermaid
classDiagram
    class EmbeddingProvider {
        <<abstract>>
        +embed() -> list[list[float]]
        +get_dimension() -> int
        +name() -> str
    }
    class LLMProvider {
        <<abstract>>
        +generate() -> str
        +generate_stream() -> AsyncIterator[str]
        +name() -> str
    }
    EmbeddingProvider --|> ABC
    LLMProvider --|> ABC
```

## Call Graph

```mermaid
flowchart TD
    N0[RuntimeError]
    N1[decorator]
    N2[func]
    N3[random]
    N4[sleep]
    N5[with_retry]
    N6[wrapper]
    N7[wraps]
    N5 --> N7
    N5 --> N2
    N5 --> N3
    N5 --> N4
    N5 --> N0
    N1 --> N7
    N1 --> N2
    N1 --> N3
    N1 --> N4
    N1 --> N0
    N6 --> N2
    N6 --> N3
    N6 --> N4
    N6 --> N0
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7 func
```

## Relevant Source Files

- `src/local_deepwiki/providers/base.py:110-138`

## See Also

- [local](embeddings/local.md) - uses this
- [openai](embeddings/openai.md) - uses this
- [vectorstore](../core/vectorstore.md) - uses this
- [llm_cache](../core/llm_cache.md) - uses this
