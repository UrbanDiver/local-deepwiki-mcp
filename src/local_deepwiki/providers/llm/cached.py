"""Caching wrapper for LLM providers."""

from collections.abc import AsyncIterator

from local_deepwiki.core.llm_cache import LLMCache
from local_deepwiki.logging import get_logger
from local_deepwiki.providers.base import LLMProvider

logger = get_logger(__name__)


class CachingLLMProvider(LLMProvider):
    """LLM provider wrapper that caches responses.

    Wraps any LLMProvider implementation to add transparent caching.
    Cache lookups happen before calling the underlying provider,
    and successful responses are cached for future use.

    Only responses generated with temperature <= max_cacheable_temperature
    are cached, as higher temperatures produce non-deterministic outputs.
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMCache,
    ):
        """Initialize the caching provider.

        Args:
            provider: The underlying LLM provider to wrap.
            cache: The LLM cache instance to use.
        """
        self._provider = provider
        self._cache = cache

    @property
    def name(self) -> str:
        """Get the provider name with cache prefix."""
        return f"cached:{self._provider.name}"

    @property
    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return self._cache.stats

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Generate text with caching.

        Checks cache first, generates from provider on miss,
        and caches the response.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Generated text (from cache or provider).
        """
        # Try cache first
        cached = await self._cache.get(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            model_name=self._provider.name,
        )

        if cached is not None:
            logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
            return cached

        # Generate from provider
        logger.debug(f"Cache miss, generating for prompt: {prompt[:50]}...")
        response = await self._provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Cache the response
        await self._cache.set(
            prompt=prompt,
            response=response,
            system_prompt=system_prompt,
            temperature=temperature,
            model_name=self._provider.name,
        )

        return response

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream generation with caching.

        For cache hits, simulates streaming by yielding chunks.
        For cache misses, streams from provider and caches the complete response.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Yields:
            Text chunks.
        """
        # Try cache first
        cached = await self._cache.get(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            model_name=self._provider.name,
        )

        if cached is not None:
            logger.debug(f"Cache hit (stream) for prompt: {prompt[:50]}...")
            # Simulate streaming for cached response
            chunk_size = 100
            for i in range(0, len(cached), chunk_size):
                yield cached[i : i + chunk_size]
            return

        # Stream from provider and collect for caching
        logger.debug(f"Cache miss (stream), generating for prompt: {prompt[:50]}...")
        chunks: list[str] = []

        async for chunk in self._provider.generate_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            chunks.append(chunk)
            yield chunk

        # Cache complete response
        complete_response = "".join(chunks)
        await self._cache.set(
            prompt=prompt,
            response=complete_response,
            system_prompt=system_prompt,
            temperature=temperature,
            model_name=self._provider.name,
        )
