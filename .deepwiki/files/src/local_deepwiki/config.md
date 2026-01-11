# Configuration Module Documentation

## File Overview

This module defines configuration classes and utilities for the Local DeepWiki application. It provides structured configuration management for embedding models, language models, parsing, chunking, and output settings using Pydantic for validation.

## Classes

### `OutputConfig`
Configuration for output directory and vector database settings.

```python
class OutputConfig(BaseModel):
    """Output configuration."""

    wiki_dir: str = Field(default=".deepwiki", description="Wiki output directory name")
    vector_db_name: str = Field(default="vectors.lance", description="Vector DB filename")
```

**Fields:**
- `wiki_dir` (str): Wiki output directory name, defaults to ".deepwiki"
- `vector_db_name` (str): Vector DB filename, defaults to "vectors.lance"

### `ChunkingConfig`
Configuration for text chunking settings.

```python
class ChunkingConfig(BaseModel):
    """Chunking configuration."""
    
    chunk_size: int = Field(default=1000, description="Maximum chunk size in characters")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks in characters")
```

### `ParsingConfig`
Configuration for document parsing settings.

```python
class ParsingConfig(BaseModel):
    """Parsing configuration."""
    
    parser: str = Field(default="markdown", description="Parser type")
    max_workers: int = Field(default=4, description="Maximum number of parsing workers")
```

### `LLMConfig`
Base configuration for language model settings.

```python
class LLMConfig(BaseModel):
    """Base LLM configuration."""
    
    model: str = Field(default="gpt-3.5-turbo", description="Language model name")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=1000, description="Maximum tokens to generate")
```

### `OpenAILLMConfig`
Configuration for OpenAI language model settings.

```python
class OpenAILLMConfig(LLMConfig):
    """OpenAI LLM configuration."""
    
    api_key: str = Field(default="", description="OpenAI API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI API base URL")
```

### `AnthropicConfig`
Configuration for Anthropic language model settings.

```python
class AnthropicConfig(LLMConfig):
    """Anthropic LLM configuration."""
    
    api_key: str = Field(default="", description="Anthropic API key")
    base_url: str = Field(default="https://api.anthropic.com/v1", description="Anthropic API base URL")
```

### `OllamaConfig`
Configuration for Ollama language model settings.

```python
class OllamaConfig(LLMConfig):
    """Ollama LLM configuration."""
    
    base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
```

### `EmbeddingConfig`
Base configuration for embedding model settings.

```python
class EmbeddingConfig(BaseModel):
    """Base embedding configuration."""
    
    model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model name")
    dimensions: int = Field(default=384, description="Embedding dimensions")
```

### `LocalEmbeddingConfig`
Configuration for local embedding models.

```python
class LocalEmbeddingConfig(EmbeddingConfig):
    """Local embedding configuration."""
    
    model_path: str = Field(default="", description="Path to local model")
```

### `OpenAIEmbeddingConfig`
Configuration for OpenAI embedding models.

```python
class OpenAIEmbeddingConfig(EmbeddingConfig):
    """OpenAI embedding configuration."""
    
    api_key: str = Field(default="", description="OpenAI API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI API base URL")
```

### `Config`
Main configuration class that aggregates all other configuration components.

```python
class Config(BaseModel):
    """Main configuration class."""
    
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
```

## Functions

### `get_config`
Retrieves the current configuration instance.

```python
def get_config() -> Config:
    """Get the current configuration instance."""
    pass
```

**Returns:**
- `Config`: Current configuration instance

### `set_config`
Sets the global configuration instance.

```python
def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    pass
```

**Parameters:**
- `config` (Config): Configuration instance to set

## Usage Examples

### Basic Configuration Setup
```python
from src.local_deepwiki.config import Config, get_config, set_config

# Create a new configuration
config = Config(
    embedding=LocalEmbeddingConfig(model_path="/path/to/model"),
    llm=OpenAILLMConfig(api_key="your-api-key"),
    output=OutputConfig(wiki_dir="my_wiki", vector_db_name="custom_vectors.lance")
)

# Set the global configuration
set_config(config)

# Retrieve the configuration
current_config = get_config()
print(current_config.embedding.model)
```

### Using Default Configuration
```python
from src.local_deepwiki.config import Config, get_config

# Get default configuration
config = Config()
set_config(config)

# Access configuration values
print(config.output.wiki_dir)  # ".deepwiki"
print(config.chunking.chunk_size)  # 1000
```

## Dependencies

This module depends on:
- `os` - Standard library for operating system interfaces
- `pathlib.Path` - Standard library for path manipulation
- `typing.Any` - Standard library for type hints
- `typing.Literal` - Standard library for literal type hints
- `yaml` - PyYAML library for YAML parsing
- `pydantic.BaseModel` - Pydantic for data validation and settings management
- `pydantic.Field` - Pydantic field definition utility