# Ollama Provider Documentation

## File Overview

This file implements an LLM provider that integrates with the local Ollama service. It provides a wrapper around the Ollama AsyncClient to enable asynchronous generation of text responses using locally hosted language models.

## Classes

### `OllamaProvider`

**Purpose**: 
An asynchronous LLM provider that communicates with a local Ollama server to generate text responses using locally hosted language models.

**Key Methods**:
- `__init__(model: str, base_url: str)`: Initializes the provider with model name and Ollama server URL
- `generate(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float)`: Asynchronously generates text responses

**Usage**:
```python
provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434")
response = await provider.generate("Hello, world!")
```

## Functions

### `__init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434")`

**Parameters**:
- `model` (str): Ollama model name to use for generation (default: "llama3.2")
- `base_url` (str): Ollama API base URL (default: "http://localhost:11434")

**Purpose**: 
Initializes the Ollama provider with the specified model and server configuration.

### `generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7)`

**Parameters**:
- `prompt` (str): The user prompt to generate a response for
- `system_prompt` (str | None): Optional system prompt to guide model behavior
- `max_tokens` (int): Maximum number of tokens to generate (default: 4096)
- `temperature` (float): Sampling temperature for response randomness (default: 0.7)

**Return Value**:
- `AsyncIterator[str]`: Asynchronous iterator yielding generated text chunks

**Purpose**: 
Asynchronously generates text responses from the Ollama model based on the provided prompt and parameters.

## Usage Examples

### Basic Usage
```python
from local_deepwiki.providers.llm.ollama import OllamaProvider

# Initialize provider
provider = OllamaProvider()

# Generate response
async for chunk in provider.generate("What is Python?"):
    print(chunk, end="")
```

### Custom Configuration
```python
from local_deepwiki.providers.llm.ollama import OllamaProvider

# Initialize with custom model and URL
provider = OllamaProvider(
    model="mistral",
    base_url="http://192.168.1.100:11434"
)

# Generate with custom parameters
async for chunk in provider.generate(
    prompt="Explain quantum computing",
    max_tokens=1024,
    temperature=0.8
):
    print(chunk, end="")
```

## Dependencies

This file imports:
- `AsyncIterator` from `typing` - For type hinting asynchronous iterators
- `AsyncClient` from `ollama` - For Ollama API communication
- `LLMProvider` from `local_deepwiki.providers.base` - Base provider class for inheritance

The provider requires a running Ollama server instance accessible at the specified base URL.