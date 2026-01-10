"""Ollama LLM provider."""

from typing import AsyncIterator

from ollama import AsyncClient

from local_deepwiki.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    """LLM provider using local Ollama."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        """Initialize the Ollama provider.

        Args:
            model: Ollama model name.
            base_url: Ollama API base URL.
        """
        self._model = model
        self._base_url = base_url
        self._client = AsyncClient(host=base_url)

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
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat(
            model=self._model,
            messages=messages,
            options={
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        )
        return response["message"]["content"]

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
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"ollama:{self._model}"
