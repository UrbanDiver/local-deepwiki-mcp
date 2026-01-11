# OpenAI LLM Provider

## File Overview

This file implements an `OpenAILLMProvider` class that serves as a bridge between the application and the OpenAI API. It provides asynchronous text generation capabilities using OpenAI's language models, following the base `LLMProvider` interface.

## Classes

### `OpenAILLMProvider`

**Purpose**: Implements the `LLMProvider` interface to interact with OpenAI's language models asynchronously.

**Key Methods**:

- `__init__(self, model: str = "gpt-4o", api_key: str | None = None)` - Initializes the provider with a model name and optional API key
- `generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7)` - Asynchronously generates text using the OpenAI API

**Usage**:
```python
from local_deepwiki.providers.llm.openai import OpenAILLMProvider

# Initialize with default model
provider = OpenAILLMProvider()

# Initialize with custom model and API key
provider = OpenAILLMProvider(model="gpt-4", api_key="your-api-key")

# Generate text
response = await provider.generate("What is Python?")
```

## Functions

### `__init__`

Initializes the OpenAI LLM provider.

**Parameters**:
- `model` (str): OpenAI model name (default: "gpt-4o")
- `api_key` (str | None): Optional API key. If not provided, uses the `OPENAI_API_KEY` environment variable.

**Returns**: None

### `generate`

Asynchronously generates text using the OpenAI API.

**Parameters**:
- `prompt` (str): The user prompt for text generation
- `system_prompt` (str | None): Optional system prompt to guide the model's behavior
- `max_tokens` (int): Maximum number of tokens to generate (default: 4096)
- `temperature` (float): Controls randomness of generation (default: 0.7)

**Returns**: AsyncIterator[str] - Stream of generated text tokens

## Usage Examples

### Basic Usage

```python
from local_deepwiki.providers.llm.openai import OpenAILLMProvider

# Initialize provider
provider = OpenAILLMProvider()

# Generate text
async def get_response():
    async for token in provider.generate("Explain quantum computing in simple terms"):
        print(token, end="", flush=True)
```

### With Custom Model and API Key

```python
from local_deepwiki.providers.llm.openai import OpenAILLMProvider

# Initialize with custom settings
provider = OpenAILLMProvider(
    model="gpt-4-turbo",
    api_key="sk-your-api-key-here"
)

# Generate with system prompt
async def get_structured_response():
    async for token in provider.generate(
        prompt="Write a haiku about technology",
        system_prompt="You are a poet who writes haikus about technology",
        max_tokens=100,
        temperature=0.5
    ):
        print(token, end="", flush=True)
```

## Dependencies

This file imports:
- `os` - For accessing environment variables
- `AsyncIterator` - From `typing` - For type hints of async iterators
- `AsyncOpenAI` - From `openai` - OpenAI client for asynchronous operations
- `LLMProvider` - From `local_deepwiki.providers.base` - Base class interface

The provider requires the `openai` Python package to be installed and the `OPENAI_API_KEY` environment variable to be set (unless explicitly provided in the constructor).