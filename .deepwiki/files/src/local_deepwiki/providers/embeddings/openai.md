# OpenAI Embedding Provider

## File Overview

This file implements an OpenAI-based embedding provider for the local_deepwiki system. It provides functionality to generate text embeddings using OpenAI's embedding models through their API.

## Classes

### OpenAIEmbeddingProvider

The OpenAIEmbeddingProvider class extends the base [EmbeddingProvider](../base.md) to provide OpenAI-specific embedding functionality.

**Constructor Parameters:**
- `model` (str, optional): The OpenAI embedding model name. Defaults to `"text-embedding-3-small"`
- `api_key` (str | None, optional): Optional API key for OpenAI. If not provided, uses the `OPENAI_API_KEY` environment variable

**Key Features:**
- Inherits from [EmbeddingProvider](../base.md) base class
- Uses AsyncOpenAI client for asynchronous operations
- Automatically determines embedding dimensions based on the selected model
- Falls back to environment variable for API key configuration

## Implementation Details

The class initializes with:
- A configurable OpenAI embedding model
- An AsyncOpenAI client instance configured with the provided or environment-based API key
- Automatic dimension detection using a `OPENAI_EMBEDDING_DIMENSIONS` mapping (referenced but not shown in the provided code)

## Usage Example

```python
from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

# Using default model with environment API key
provider = OpenAIEmbeddingProvider()

# Using custom model and explicit API key
provider = OpenAIEmbeddingProvider(
    model="text-embedding-3-small",
    api_key="your-api-key-here"
)
```

## Related Components

- **[EmbeddingProvider](../base.md)**: The base class that OpenAIEmbeddingProvider extends
- **AsyncOpenAI**: The OpenAI client library used for API interactions

## Dependencies

- `os`: For environment variable access
- `openai.AsyncOpenAI`: For asynchronous OpenAI API operations
- [`local_deepwiki.providers.base.EmbeddingProvider`](../base.md): Base embedding provider interface

## API Reference

### class `OpenAIEmbeddingProvider`

**Inherits from:** [`EmbeddingProvider`](../base.md)

Embedding provider using OpenAI API.

**Methods:**

#### `__init__`

```python
def __init__(model: str = "text-embedding-3-small", api_key: str | None = None)
```

Initialize the OpenAI embedding provider.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"text-embedding-3-small"` | OpenAI embedding model name. |
| `api_key` | `str | None` | `None` | Optional API key. Uses OPENAI_API_KEY env var if not provided. |

#### `embed`

```python
async def embed(texts: list[str]) -> list[list[float]]
```

Generate embeddings for a list of texts.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
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



## Class Diagram

```mermaid
classDiagram
    class OpenAIEmbeddingProvider {
        -_model
        -_client
        -_dimension
        -__init__()
        +embed() -> list[list[float]]
        +get_dimension() -> int
        +name() -> str
    }
    OpenAIEmbeddingProvider --|> EmbeddingProvider
```

## Call Graph

```mermaid
flowchart TD
    N0[AsyncOpenAI]
    N1[OpenAIEmbeddingProvider.__i...]
    N2[OpenAIEmbeddingProvider.embed]
    N3[create]
    N1 --> N0
    N2 --> N3
    classDef func fill:#e1f5fe
    class N0,N3 func
    classDef method fill:#fff3e0
    class N1,N2 method
```

## Relevant Source Files

- `src/local_deepwiki/providers/embeddings/openai.py:17-57`
