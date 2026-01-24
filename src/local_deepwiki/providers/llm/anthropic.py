"""Anthropic LLM provider."""

import os
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import LLMProvider, with_retry

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """LLM provider using Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        """Initialize the Anthropic provider.

        Args:
            model: Anthropic model name.
            api_key: Optional API key. Uses ANTHROPIC_API_KEY env var if not provided.
        """
        self._model = model
        self._client = AsyncAnthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def _build_kwargs(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        """Build kwargs for Anthropic API calls.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Dict of kwargs for messages.create/stream.
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if temperature > 0:
            kwargs["temperature"] = temperature
        return kwargs

    @with_retry(max_attempts=3, base_delay=1.0, max_delay=30.0)
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
        logger.debug(f"Generating with Anthropic model {self._model}, prompt length: {len(prompt)}")

        kwargs = self._build_kwargs(prompt, system_prompt, max_tokens, temperature)
        response = await self._client.messages.create(**kwargs)

        # Get text from the first content block (should be TextBlock)
        first_block = response.content[0]
        content = first_block.text if hasattr(first_block, "text") else ""

        logger.debug(f"Anthropic response length: {len(content)}")
        return content

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
        kwargs = self._build_kwargs(prompt, system_prompt, max_tokens, temperature)
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    @property
    def name(self) -> str:
        """Get the provider name."""
        return f"anthropic:{self._model}"
