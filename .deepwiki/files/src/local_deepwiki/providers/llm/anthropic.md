# Anthropic Provider Documentation

## File Overview

This file implements the Anthropic LLM provider for the local_deepwiki project. It provides an asynchronous interface to interact with Anthropic's Claude language models through the `anthropic` Python SDK. The provider extends the base `LLMProvider` class to integrate Anthropic's API into the project's LLM infrastructure.

## Classes

### AnthropicProvider

The `AnthropicProvider` class implements the LLM provider interface specifically for Anthropic's Claude models. It handles authentication, model selection, and asynchronous request execution.

**Key Methods:**

- `__init__(self, api_key: str = None)`: Initializes the provider with an optional API key
- `stream(self, prompt: str, model: str = "claude-3-haiku-20240307") -> AsyncIterator[str]`: Streams model responses asynchronously
- `complete(self, prompt: str, model: str = "claude-3-haiku-20240307") -> str`: Returns complete model responses

**Usage:**
```python
provider = AnthropicProvider(api_key="your-api-key")
async for chunk in provider.stream("Hello, world!"):
    print(chunk)
```

## Functions

### Constructor: `__init__(self, api_key: str = None)`

Initializes the Anthropic provider with an API key.

**Parameters:**
- `api_key` (str, optional): Anthropic API key. If not provided, will attempt to read from `ANTHROPIC_API_KEY` environment variable.

**Example:**
```python
provider = AnthropicProvider()
# or
provider = AnthropicProvider(api_key="sk-ant-...")
```

### Method: `stream(self, prompt: str, model: str = "claude-3-haiku-20240307") -> AsyncIterator[str]`

Asynchronously streams responses from the Anthropic model.

**Parameters:**
- `prompt` (str): The input prompt to send to the model
- `model` (str): The Anthropic model to use (default: "claude-3-haiku-20240307")

**Returns:**
- `AsyncIterator[str]`: Async iterator yielding response chunks

**Example:**
```python
async for chunk in provider.stream("Tell me a story"):
    print(chunk)
```

### Method: `complete(self, prompt: str, model: str = "claude-3-haiku-20240307") -> str`

Synchronously returns the complete response from the Anthropic model.

**Parameters:**
- `prompt` (str): The input prompt to send to the model
- `model` (str): The Anthropic model to use (default: "claude-3-haiku-20240307")

**Returns:**
- `str`: Complete model response

**Example:**
```python
response = provider.complete("Hello, world!")
print(response)
```

## Usage Examples

### Basic Usage
```python
from local_deepwiki.providers.llm.anthropic import AnthropicProvider

# Initialize provider
provider = AnthropicProvider()

# Stream response
async for chunk in provider.stream("What is AI?"):
    print(chunk)

# Get complete response
response = provider.complete("What is AI?")
print(response)
```

### With Custom API Key
```python
provider = AnthropicProvider(api_key="sk-ant-...")

async for chunk in provider.stream("Hello", model="claude-3-sonnet-20240229"):
    print(chunk)
```

## Dependencies

This file depends on:

1. **Standard Library:**
   - `os`: For reading environment variables
   - `typing.AsyncIterator`: For type hints

2. **External Libraries:**
   - `anthropic.AsyncAnthropic`: Anthropic's asynchronous client
   - `local_deepwiki.providers.base.LLMProvider`: Base provider interface

3. **Environment Variables:**
   - `ANTHROPIC_API_KEY`: Required for authentication (read automatically if not passed to constructor)

The provider requires the `anthropic` Python package to be installed in the environment.