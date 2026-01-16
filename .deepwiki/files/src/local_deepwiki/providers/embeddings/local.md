# LocalEmbeddingProvider

## File Overview

This file implements a local embedding provider that uses sentence-transformers models for generating embeddings. It provides an implementation of the [EmbeddingProvider](../base.md) interface for running embedding models locally rather than using remote APIs.

## Classes

### LocalEmbeddingProvider

The LocalEmbeddingProvider class provides local text embedding capabilities using sentence-transformers models. It implements lazy loading of the underlying model to optimize memory usage.

**Inheritance**: Extends [EmbeddingProvider](../base.md)

**Key Features**:
- Lazy loading of sentence-transformers models
- Configurable model selection
- Local processing without external API dependencies

## Methods

### `__init__(model_name: str = "all-MiniLM-L6-v2")`

Initializes the local embedding provider with a specified model.

**Parameters**:
- `model_name` (str, optional): Name of the sentence-transformers model to use. Defaults to "all-MiniLM-L6-v2"

**Behavior**:
- Sets the model name for later loading
- Initializes internal state variables for the model and dimension
- Uses lazy loading pattern - model is not loaded until first use

### `_load_model() -> SentenceTransformer`

Private method that implements lazy loading of the sentence-transformers model.

**Returns**: 
- `SentenceTransformer`: The loaded model instance

**Behavior**:
- Loads the model only when first accessed
- Caches the loaded model for subsequent use

## Usage Examples

### Basic Initialization

```python
# Initialize with default model
provider = LocalEmbeddingProvider()

# Initialize with custom model
provider = LocalEmbeddingProvider(model_name="paraphrase-MiniLM-L6-v2")
```

## Related Components

This class works with:
- [EmbeddingProvider](../base.md): The base interface that this class implements
- SentenceTransformer: The underlying model class from the sentence-transformers library used for generating embeddings

## Implementation Notes

The class uses a lazy loading pattern where the actual sentence-transformers model is only loaded when first needed, which helps optimize memory usage and startup time. The model and its dimension are cached after first load for efficient reuse.

## API Reference

### class `LocalEmbeddingProvider`

**Inherits from:** [`EmbeddingProvider`](../base.md)

Embedding provider using local sentence-transformers models.

**Methods:**


<details>
<summary>View Source (lines 10-57)</summary>

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        # sentence-transformers is synchronous, but we keep async interface for consistency
        embeddings = model.encode(texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
```

</details>

#### `__init__`

```python
def __init__(model_name: str = "all-MiniLM-L6-v2")
```

Initialize the local embedding provider.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_name` | `str` | `"all-MiniLM-L6-v2"` | Name of the sentence-transformers model to use. |


<details>
<summary>View Source (lines 10-57)</summary>

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        # sentence-transformers is synchronous, but we keep async interface for consistency
        embeddings = model.encode(texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
```

</details>

#### `embed`

```python
async def embed(texts: list[str]) -> list[list[float]]
```

Generate embeddings for a list of texts.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `texts` | `list[str]` | - | List of text strings to embed. |


<details>
<summary>View Source (lines 10-57)</summary>

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        # sentence-transformers is synchronous, but we keep async interface for consistency
        embeddings = model.encode(texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
```

</details>

#### `get_dimension`

```python
def get_dimension() -> int
```

Get the embedding dimension.


<details>
<summary>View Source (lines 10-57)</summary>

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        # sentence-transformers is synchronous, but we keep async interface for consistency
        embeddings = model.encode(texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
```

</details>

#### `name`

```python
def name() -> str
```

Get the provider name.




<details>
<summary>View Source (lines 10-57)</summary>

```python
class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the local embedding provider.

        Args:
            model_name: Name of the sentence-transformers model to use.
        """
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    def _load_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        model = self._load_model()
        # sentence-transformers is synchronous, but we keep async interface for consistency
        embeddings = model.encode(texts, convert_to_numpy=True)
        return cast(list[list[float]], embeddings.tolist())

    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        if self._dimension is None:
            self._load_model()
        return self._dimension  # type: ignore

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"local:{self._model_name}"
```

</details>

## Class Diagram

```mermaid
classDiagram
    class LocalEmbeddingProvider {
        -_model_name
        -_model
        -_dimension
        -__init__()
        -_load_model() -> SentenceTransformer
        +embed() -> list[list[float]]
        +get_dimension() -> int
        +name() -> str
    }
    LocalEmbeddingProvider --|> EmbeddingProvider
```

## Call Graph

```mermaid
flowchart TD
    N0[LocalEmbeddingProvider._loa...]
    N1[LocalEmbeddingProvider.embed]
    N2[LocalEmbeddingProvider.get_...]
    N3[SentenceTransformer]
    N4[_load_model]
    N5[cast]
    N6[encode]
    N7[get_sentence_embedding_dime...]
    N8[tolist]
    N0 --> N3
    N0 --> N7
    N1 --> N4
    N1 --> N6
    N1 --> N5
    N1 --> N8
    N2 --> N4
    classDef func fill:#e1f5fe
    class N3,N4,N5,N6,N7,N8 func
    classDef method fill:#fff3e0
    class N0,N1,N2 method
```

## Relevant Source Files

- `src/local_deepwiki/providers/embeddings/local.py:10-57`

## See Also

- [vectorstore](../../core/vectorstore.md) - shares 2 dependencies
