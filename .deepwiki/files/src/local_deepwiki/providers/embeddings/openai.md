# OpenAI Embedding Provider

## File Overview

This file provides an implementation of an embedding provider that uses the OpenAI API. It enables generating vector embeddings for text using OpenAI's embedding models, which are commonly used for semantic search, similarity calculations, and other NLP tasks.

## Classes

### `OpenAIEmbeddingProvider`

**Purpose**: An embedding provider that interfaces with OpenAI's embedding API to generate vector representations of text.

**Key Methods**:
- `__init__(model: str = "text-embedding-3-small", api_key: str | None = None)`: Initializes the provider with a model and API key
- `embed(text: str) -> list[float]`: Generates embeddings for a given text (async)

**Usage**:
```python
provider = OpenAIEmbeddingProvider(model="text-embedding-3-small")
embeddings = await provider.embed("Hello world")
```

**Constructor Parameters**:
- `model` (str): The OpenAI embedding model to use. Defaults to `"text-embedding-3-small"`
- `api_key` (str | None): Optional API key. If not provided, uses the `OPENAI_API_KEY` environment variable

## Functions

### `__init__(self, model: str = "text-embedding-3-small", api_key: str | None = None)`

Initializes the OpenAI embedding provider.

**Parameters**:
- `model` (str): OpenAI embedding model name
- `api_key` (str | None): Optional API key. Uses `OPENAI_API_KEY` environment variable if not provided

**Returns**: None

### `embed(self, text: str) -> list[float]`

Generates embeddings for the given text.

**Parameters**:
- `text` (str): The text to embed

**Returns**:
- `list[float]`: The embedding vector as a list of floats

## Usage Examples

### Basic Usage

```python
from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

# Initialize with default model
provider = OpenAIEmbeddingProvider()

# Generate embeddings
embeddings = await provider.embed("Hello world")
print(embeddings)
```

### Custom Model and API Key

```python
from local_deepwiki.providers.embeddings.openai import OpenAIEmbeddingProvider

# Initialize with custom model and API key
provider = OpenAIEmbeddingProvider(
    model="text-embedding-3-large",
    api_key="your-api-key-here"
)

# Generate embeddings
embeddings = await provider.embed("Hello world")
print(embeddings)
```

### Environment Variable Setup

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Dependencies

- `os`: For accessing environment variables
- `openai.AsyncOpenAI`: OpenAI client for asynchronous API calls
- `local_deepwiki.providers.base.EmbeddingProvider`: Base class for embedding providers

**Note**: The code references `OPENAI_EMBEDDING_DIMENSIONS` which is expected to be defined elsewhere in the codebase, mapping model names to their respective embedding dimensions.