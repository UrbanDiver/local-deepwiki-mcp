# Test Configuration Documentation

## File Overview

This file contains the test suite for the configuration system of the local_deepwiki application. It verifies that the `Config` class and related functions behave correctly with default values and specific configurations.

## Classes

### TestConfig

Test suite for validating the `Config` class functionality.

**Methods:**

#### test_default_config
Tests that the default configuration values are set correctly.

```python
def test_default_config(self):
    """Test default configuration values."""
    config = Config()

    assert config.embedding.provider == "local"
    assert config.llm.provider == "ollama"
    assert "python" in config.parsing.languages
    assert config.chunking.max_chunk_tokens == 512
```

#### test_embedding_config
Tests embedding-specific configuration values.

```python
def test_embedding_config(self):
    """Test embedding configuration."""
    config = Config()

    assert config.embedding.local.model == "all-MiniLM-L6-v2"
    assert config.embedding.openai.model == "text-embedding-3-small"
```

## Functions

### get_config
Retrieves the current configuration instance.

### set_config
Sets the global configuration instance.

## Usage Examples

### Running Tests
```bash
pytest tests/test_config.py
```

### Basic Configuration Usage
```python
from local_deepwiki.config import Config, get_config, set_config

# Create a new config instance
config = Config()

# Access configuration values
print(config.embedding.provider)  # "local"
print(config.llm.provider)        # "ollama"

# Get current config
current_config = get_config()

# Set new config
new_config = Config()
set_config(new_config)
```

## Dependencies

This file imports:
- `pathlib.Path` - For path manipulation
- `pytest` - Testing framework
- `local_deepwiki.config.Config` - Main configuration class
- `local_deepwiki.config.get_config` - Function to retrieve config
- `local_deepwiki.config.set_config` - Function to set config

The tests validate the default configuration values for:
- Embedding provider defaults to "local"
- LLM provider defaults to "ollama"  
- Python language support in parsing
- Chunk size of 512 tokens
- Specific embedding model names for local and OpenAI providers