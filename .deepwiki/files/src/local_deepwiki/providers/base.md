# Base Provider Module

## File Overview

This module defines abstract base classes for embedding and language model providers. It establishes the interface contract that concrete implementations must follow, ensuring consistency across different provider implementations while maintaining asynchronous operation capabilities.

## Classes

### EmbeddingProvider

Abstract base class for embedding providers. This class defines the interface that all embedding providers must implement.

#### Methods

##### `embed`
```python
async def embed(self, texts: list[str]) -> list[list[float]]
```

Generate embeddings for a list of texts.

**Parameters:**
- `texts` (list[str]): List of text strings to embed

**Returns:**
- `list[list[float]]`: List of embedding vectors

**Example:**
```python
# This would be implemented by concrete classes
async def embed(self, texts: list[str]) -> list[list[float]]:
    # Implementation would generate embeddings for the provided texts
    pass
```

##### `get_dimension`
```python
def get_dimension(self) -> int
```

Get the embedding dimension.

**Returns:**
- `int`: The dimension of the embedding vectors

**Example:**
```python
# This would be implemented by concrete classes
def get_dimension(self) -> int:
    # Implementation would return the dimension of the embeddings
    pass
```

##### `dimension` (Property)
```python
@property
@abstractmethod
def dimension(self) -> int
```

Get the embedding dimension as a property.

**Returns:**
- `int`: The dimension of the embedding vectors

**Note:** This is an abstract property that must be implemented by subclasses.

## Usage Examples

### Creating a Concrete Implementation

```python
from base import EmbeddingProvider

class MyEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self._dimension = 768
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Implementation would generate embeddings
        return [[0.1] * self._dimension for _ in texts]
    
    def get_dimension(self) -> int:
        return self._dimension
    
    @property
    def dimension(self) -> int:
        return self._dimension
```

### Using the Provider

```python
# Assuming MyEmbeddingProvider is implemented
provider = MyEmbeddingProvider()

# Generate embeddings
texts = ["Hello world", "How are you?"]
embeddings = await provider.embed(texts)
print(f"Embedding dimension: {provider.get_dimension()}")
```

## Dependencies

- `abc.ABC`: Abstract base class functionality
- `typing.AsyncIterator`: Type hint for asynchronous iterators
- `typing.list`: Type hint for list types

**Note:** The file appears to be incomplete as it references a `LLMProvider` class that is not defined in the provided code snippet, and the `EmbeddingProvider` class definition is cut off after the `dimension` property.