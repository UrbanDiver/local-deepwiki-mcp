# Local Embedding Provider

## File Overview

This file implements a local embedding provider using the sentence-transformers library. It provides a concrete implementation of the `EmbeddingProvider` base class that generates dense vector embeddings for text using pre-trained transformer models.

## Classes

### LocalEmbeddingProvider

**Purpose**: A concrete implementation of `EmbeddingProvider` that generates sentence embeddings using pre-trained transformer models from sentence-transformers.

**Key Methods**:

- `__init__(model_name: str = "all-MiniLM-L6-v2")`: Initializes the provider with a specified transformer model
- `encode(texts: list[str]) -> list[list[float]]`: Converts text inputs into dense vector embeddings
- `get_embedding_dimension() -> int`: Returns the dimensionality of the generated embeddings

**Usage**:
```python
from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

# Initialize provider with default model
provider = LocalEmbeddingProvider()

# Generate embeddings for text
texts = ["Hello world", "How are you?"]
embeddings = provider.encode(texts)
```

## Functions

### `__init__(model_name: str = "all-MiniLM-L6-v2")`

**Parameters**:
- `model_name` (str): Name of the sentence-transformers model to use. Defaults to "all-MiniLM-L6-v2"

**Purpose**: Initializes the LocalEmbeddingProvider with a specific transformer model for embedding generation

### `encode(texts: list[str]) -> list[list[float]]`

**Parameters**:
- `texts` (list[str]): List of text strings to be converted to embeddings

**Return Value**: 
- `list[list[float]]`: List of embedding vectors, where each vector is a list of floats

**Purpose**: Converts input text strings into dense vector representations using the configured transformer model

### `get_embedding_dimension() -> int`

**Return Value**:
- `int`: The dimensionality of the generated embeddings

**Purpose**: Returns the number of dimensions in the embedding vectors produced by this provider

## Usage Examples

```python
from local_deepwiki.providers.embeddings.local import LocalEmbeddingProvider

# Basic usage with default model
provider = LocalEmbeddingProvider()
texts = ["The quick brown fox", "Jumped over the lazy dog"]
embeddings = provider.encode(texts)

# Using custom model
custom_provider = LocalEmbeddingProvider(model_name="all-mpnet-base-v2")
embeddings = custom_provider.encode(["Hello", "World"])

# Get embedding dimension
dimension = provider.get_embedding_dimension()
print(f"Embedding dimension: {dimension}")
```

## Dependencies

- **sentence_transformers**: Used for loading pre-trained transformer models and generating embeddings
- **local_deepwiki.providers.base.EmbeddingProvider**: Base class that this provider implements

The provider requires internet connectivity the first time a model is loaded to download it from Hugging Face, after which models are cached locally.