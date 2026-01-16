# Ollama Provider Documentation

## File Overview

The `ollama.py` file implements an Ollama-based language model provider for the local-deepwiki system. It provides integration with Ollama's local LLM server, handling connection management, health checks, and text generation capabilities.

## Classes

### OllamaConnectionError

A custom exception class for handling Ollama server connectivity issues.

**Purpose**: Raised when the Ollama server is not accessible or connection fails.

**Constructor Parameters**:
- `base_url` (str): The Ollama server URL that failed to connect
- `original_error` (Exception | None, optional): The underlying exception that caused the connection failure

The exception provides helpful error messages with setup instructions for users, including links to Ollama installation and verification commands.

### OllamaModelNotFoundError

A custom exception class for handling cases where a requested model is not available on the Ollama server.

### OllamaProvider

The [main](../../export/html.md) provider class that implements LLM functionality using Ollama as the backend.

**Purpose**: Provides language model capabilities through Ollama's local server, implementing the [LLMProvider](../base.md) interface.

**Constructor Parameters**:
- `model` (str, optional): Ollama model name. Defaults to "llama3.2"
- `base_url` (str, optional): Ollama API base URL. Defaults to "http://localhost:11434"

**Key Methods**:
- `check_health`: Verifies Ollama server connectivity and model availability
- `generate`: Generates text responses from prompts
- `generate_stream`: Provides streaming text generation
- `name`: Returns the provider name

## Usage Examples

### Basic Provider Initialization

```python
from local_deepwiki.providers.llm.ollama import OllamaProvider

# Initialize with default settings
provider = OllamaProvider()

# Initialize with custom model and URL
provider = OllamaProvider(
    model="llama3.1", 
    base_url="http://localhost:11434"
)
```

### Error Handling

```python
from local_deepwiki.providers.llm.ollama import (
    OllamaProvider, 
    OllamaConnectionError, 
    OllamaModelNotFoundError
)

try:
    provider = OllamaProvider()
    # Use provider...
except OllamaConnectionError as e:
    print(f"Cannot connect to Ollama at {e.base_url}")
except OllamaModelNotFoundError as e:
    print(f"Model not found: {e}")
```

## Related Components

This file integrates with several other components:

- **[LLMProvider](../base.md)**: Base class that OllamaProvider extends, providing the interface contract
- **AsyncClient**: From the `ollama` package, used for communicating with the Ollama server
- **[with_retry](../base.md)**: Decorator from the base providers module for handling retries
- **[get_logger](../../logging.md)**: Logging utility from the local_deepwiki logging module

The provider uses async/await patterns and supports both single-response and streaming generation modes through the underlying Ollama client.

## API Reference

### class `OllamaConnectionError`

**Inherits from:** `Exception`

Raised when Ollama server is not accessible.

**Methods:**


<details>
<summary>View Source (lines 13-26)</summary>

```python
class OllamaConnectionError(Exception):
    """Raised when Ollama server is not accessible."""

    def __init__(self, base_url: str, original_error: Exception | None = None):
        self.base_url = base_url
        self.original_error = original_error
        message = (
            f"Cannot connect to Ollama at {base_url}. "
            "Please ensure Ollama is running:\n"
            "  1. Install Ollama: https://ollama.ai/download\n"
            "  2. Start Ollama: `ollama serve`\n"
            "  3. Verify it's running: `curl {base_url}/api/tags`"
        )
        super().__init__(message)
```

</details>

#### `__init__`

```python
def __init__(base_url: str, original_error: Exception | None = None)
```


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | - | - |
| `original_error` | `Exception | None` | `None` | - |



<details>
<summary>View Source (lines 13-26)</summary>

```python
class OllamaConnectionError(Exception):
    """Raised when Ollama server is not accessible."""

    def __init__(self, base_url: str, original_error: Exception | None = None):
        self.base_url = base_url
        self.original_error = original_error
        message = (
            f"Cannot connect to Ollama at {base_url}. "
            "Please ensure Ollama is running:\n"
            "  1. Install Ollama: https://ollama.ai/download\n"
            "  2. Start Ollama: `ollama serve`\n"
            "  3. Verify it's running: `curl {base_url}/api/tags`"
        )
        super().__init__(message)
```

</details>

### class `OllamaModelNotFoundError`

**Inherits from:** `Exception`

Raised when the requested model is not available in Ollama.

**Methods:**


<details>
<summary>View Source (lines 29-49)</summary>

```python
class OllamaModelNotFoundError(Exception):
    """Raised when the requested model is not available in Ollama."""

    def __init__(self, model: str, available_models: list[str] | None = None):
        self.model = model
        self.available_models = available_models or []
        if available_models:
            models_str = ", ".join(available_models[:10])
            if len(available_models) > 10:
                models_str += f"... ({len(available_models)} total)"
            message = (
                f"Model '{model}' not found in Ollama. "
                f"Available models: {models_str}\n"
                f"To download the model, run: `ollama pull {model}`"
            )
        else:
            message = (
                f"Model '{model}' not found in Ollama.\n"
                f"To download the model, run: `ollama pull {model}`"
            )
        super().__init__(message)
```

</details>

#### `__init__`

```python
def __init__(model: str, available_models: list[str] | None = None)
```


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | - | - |
| `available_models` | `list[str] | None` | `None` | - |



<details>
<summary>View Source (lines 29-49)</summary>

```python
class OllamaModelNotFoundError(Exception):
    """Raised when the requested model is not available in Ollama."""

    def __init__(self, model: str, available_models: list[str] | None = None):
        self.model = model
        self.available_models = available_models or []
        if available_models:
            models_str = ", ".join(available_models[:10])
            if len(available_models) > 10:
                models_str += f"... ({len(available_models)} total)"
            message = (
                f"Model '{model}' not found in Ollama. "
                f"Available models: {models_str}\n"
                f"To download the model, run: `ollama pull {model}`"
            )
        else:
            message = (
                f"Model '{model}' not found in Ollama.\n"
                f"To download the model, run: `ollama pull {model}`"
            )
        super().__init__(message)
```

</details>

### class `OllamaProvider`

**Inherits from:** [`LLMProvider`](../base.md)

LLM provider using local Ollama.

**Methods:**


<details>
<summary>View Source (lines 52-241)</summary>

```python
class OllamaProvider(LLMProvider):
    # Methods: __init__, check_health, _ensure_healthy, generate, generate_stream, name
```

</details>

#### `__init__`

```python
def __init__(model: str = "llama3.2", base_url: str = "http://localhost:11434")
```

Initialize the Ollama provider.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"llama3.2"` | Ollama model name. |
| `base_url` | `str` | `"http://localhost:11434"` | Ollama API base URL. |


<details>
<summary>View Source (lines 55-65)</summary>

```python
def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        """Initialize the Ollama provider.

        Args:
            model: Ollama model name.
            base_url: Ollama API base URL.
        """
        self._model = model
        self._base_url = base_url
        self._client = AsyncClient(host=base_url)
        self._health_checked = False
```

</details>

#### `check_health`

```python
async def check_health() -> bool
```

Check if Ollama is running and the model is available.


<details>
<summary>View Source (lines 67-110)</summary>

```python
async def check_health(self) -> bool:
        """Check if Ollama is running and the model is available.

        Returns:
            True if Ollama is healthy and model is available.

        Raises:
            OllamaConnectionError: If Ollama server is not accessible.
            OllamaModelNotFoundError: If the requested model is not available.
        """
        logger.debug(f"Checking Ollama health at {self._base_url}")

        try:
            # Try to list models to verify connection
            models_response = await self._client.list()
            # ollama library returns typed objects with .models list and .model attribute
            available_models: list[str] = [
                m.model for m in models_response.models if m.model is not None
            ]
            logger.debug(f"Ollama available models: {available_models}")

            # Check if our model is available (handle both "model" and "model:tag" formats)
            model_base = self._model.split(":")[0]
            model_found = any(
                m == self._model or m.startswith(f"{self._model}:") or m.split(":")[0] == model_base
                for m in available_models
            )

            if not model_found:
                logger.error(f"Model '{self._model}' not found in Ollama")
                raise OllamaModelNotFoundError(self._model, available_models)

            logger.info(f"Ollama health check passed: model '{self._model}' available")
            self._health_checked = True
            return True

        except OllamaModelNotFoundError:
            raise
        except (
            Exception
        ) as e:  # noqa: BLE001 - Wrap any connection/library error in OllamaConnectionError
            # Connection errors, timeouts, etc.
            logger.error(f"Failed to connect to Ollama at {self._base_url}: {e}")
            raise OllamaConnectionError(self._base_url, e) from e
```

</details>

#### `generate`

```python
async def generate(prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> str
```

Generate text from a prompt.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | - | The user prompt. |
| `system_prompt` | `str | None` | `None` | Optional system prompt. |
| `max_tokens` | `int` | `4096` | Maximum tokens to generate. |
| `temperature` | `float` | `0.7` | Sampling temperature. |


<details>
<summary>View Source (lines 121-180)</summary>

```python
async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Generated text.

        Raises:
            OllamaConnectionError: If Ollama server is not accessible.
            OllamaModelNotFoundError: If the requested model is not available.
        """
        # Check health on first call
        await self._ensure_healthy()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.debug(f"Generating with Ollama model {self._model}, prompt length: {len(prompt)}")

        try:
            response = await self._client.chat(
                model=self._model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )

            content = cast(str, response["message"]["content"])
            logger.debug(f"Ollama response length: {len(content)}")
            return content

        except ResponseError as e:
            # Handle model not found during generation (e.g., model was deleted)
            if "not found" in str(e).lower():
                logger.error(f"Model '{self._model}' not found during generation")
                raise OllamaModelNotFoundError(self._model) from e
            raise
        except Exception as e:  # noqa: BLE001 - Wrap connection errors, re-raise others
            # Check if it's a connection error
            error_str = str(e).lower()
            if any(x in error_str for x in ["connection", "refused", "timeout", "unreachable"]):
                logger.error(f"Lost connection to Ollama: {e}")
                self._health_checked = False  # Reset health check
                raise OllamaConnectionError(self._base_url, e) from e
            raise
```

</details>

#### `generate_stream`

```python
async def generate_stream(prompt: str, system_prompt: str | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> AsyncIterator[str]
```

Generate text from a prompt with streaming.


| [Parameter](../../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | - | The user prompt. |
| `system_prompt` | `str | None` | `None` | Optional system prompt. |
| `max_tokens` | `int` | `4096` | Maximum tokens to generate. |
| `temperature` | `float` | `0.7` | Sampling temperature. |


<details>
<summary>View Source (lines 182-236)</summary>

```python
async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate text from a prompt with streaming.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Yields:
            Generated text chunks.

        Raises:
            OllamaConnectionError: If Ollama server is not accessible.
            OllamaModelNotFoundError: If the requested model is not available.
        """
        # Check health on first call
        await self._ensure_healthy()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            async for chunk in await self._client.chat(
                model=self._model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
                stream=True,
            ):
                if chunk["message"]["content"]:
                    yield chunk["message"]["content"]

        except ResponseError as e:
            if "not found" in str(e).lower():
                logger.error(f"Model '{self._model}' not found during streaming")
                raise OllamaModelNotFoundError(self._model) from e
            raise
        except Exception as e:  # noqa: BLE001 - Wrap connection errors, re-raise others
            error_str = str(e).lower()
            if any(x in error_str for x in ["connection", "refused", "timeout", "unreachable"]):
                logger.error(f"Lost connection to Ollama during streaming: {e}")
                self._health_checked = False
                raise OllamaConnectionError(self._base_url, e) from e
            raise
```

</details>

#### `name`

```python
def name() -> str
```

Get the provider name.




<details>
<summary>View Source (lines 239-241)</summary>

```python
def name(self) -> str:
        """Get the provider name."""
        return f"ollama:{self._model}"
```

</details>

## Class Diagram

```mermaid
classDiagram
    class OllamaConnectionError {
        +base_url
        +original_error
        -__init__()
    }
    class OllamaModelNotFoundError {
        +model
        +available_models
        -__init__()
    }
    class OllamaProvider {
        -__init__(model: str, base_url: str)
        +check_health() bool
        -_ensure_healthy() None
        +generate(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float) str
        +generate_stream(prompt: str, system_prompt: str | None, max_tokens: int, temperature: float) AsyncIterator[str]
        +name() str
    }
    OllamaConnectionError --|> Exception
    OllamaModelNotFoundError --|> Exception
    OllamaProvider --|> LLMProvider
```

## Call Graph

```mermaid
flowchart TD
    N0[AsyncClient]
    N1[OllamaConnectionError]
    N2[OllamaConnectionError.__init__]
    N3[OllamaModelNotFoundError]
    N4[OllamaModelNotFoundError.__...]
    N5[OllamaProvider.__init__]
    N6[OllamaProvider._ensure_healthy]
    N7[OllamaProvider.check_health]
    N8[OllamaProvider.generate]
    N9[OllamaProvider.generate_stream]
    N10[__init__]
    N11[_ensure_healthy]
    N12[cast]
    N13[chat]
    N14[check_health]
    N2 --> N10
    N4 --> N10
    N5 --> N0
    N7 --> N3
    N7 --> N1
    N6 --> N14
    N8 --> N11
    N8 --> N13
    N8 --> N12
    N8 --> N3
    N8 --> N1
    N9 --> N11
    N9 --> N13
    N9 --> N3
    N9 --> N1
    classDef func fill:#e1f5fe
    class N0,N1,N3,N10,N11,N12,N13,N14 func
    classDef method fill:#fff3e0
    class N2,N4,N5,N6,N7,N8,N9 method
```

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_ensure_healthy`

<details>
<summary>View Source (lines 112-118)</summary>

```python
async def _ensure_healthy(self) -> None:
        """Ensure Ollama is healthy before making requests.

        Only performs the check once per instance.
        """
        if not self._health_checked:
            await self.check_health()
```

</details>

## Relevant Source Files

- `src/local_deepwiki/providers/llm/ollama.py:13-26`
