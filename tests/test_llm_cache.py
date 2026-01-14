"""Tests for LLM response caching."""

import hashlib
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import LLMCacheConfig
from local_deepwiki.core.llm_cache import LLMCache
from local_deepwiki.providers.base import LLMProvider
from local_deepwiki.providers.llm.cached import CachingLLMProvider


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic embeddings based on text hash."""
        embeddings = []
        for text in texts:
            # Create deterministic embedding from text hash
            hash_bytes = hashlib.md5(text.encode()).digest()
            # Expand to dimension size
            values = []
            for i in range(self._dimension):
                byte_idx = i % len(hash_bytes)
                values.append((hash_bytes[byte_idx] - 128) / 128.0)
            embeddings.append(values)
        return embeddings

    def get_dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return "mock-embedding"


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self):
        self.calls: list[dict] = []

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        return f"Response to: {prompt[:50]}"

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        })
        response = f"Streamed response to: {prompt[:50]}"
        for chunk in response.split():
            yield chunk + " "

    @property
    def name(self) -> str:
        return "mock-llm"


class TestLLMCache:
    """Tests for the LLMCache class."""

    @pytest.fixture
    def cache_path(self, tmp_path: Path) -> Path:
        """Create a temporary cache path."""
        return tmp_path / "test_cache.lance"

    @pytest.fixture
    def embedding_provider(self) -> MockEmbeddingProvider:
        """Create a mock embedding provider."""
        return MockEmbeddingProvider()

    @pytest.fixture
    def config(self) -> LLMCacheConfig:
        """Create a cache config with default settings."""
        return LLMCacheConfig(
            enabled=True,
            ttl_seconds=3600,
            max_entries=1000,
            similarity_threshold=0.95,
            max_cacheable_temperature=0.3,
        )

    @pytest.fixture
    def cache(
        self, cache_path: Path, embedding_provider: MockEmbeddingProvider, config: LLMCacheConfig
    ) -> LLMCache:
        """Create an LLMCache instance."""
        return LLMCache(cache_path, embedding_provider, config)

    @pytest.mark.asyncio
    async def test_cache_miss_on_empty_cache(self, cache: LLMCache):
        """Test that empty cache returns None."""
        result = await cache.get(
            prompt="test prompt",
            system_prompt="test system",
            temperature=0.1,
            model_name="test-model",
        )
        assert result is None
        assert cache.stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_cache_set_and_get_exact_match(self, cache: LLMCache):
        """Test that exact same prompt returns cached response."""
        prompt = "What is the meaning of life?"
        system_prompt = "You are a philosopher"
        response = "42"

        # Set cache entry
        await cache.set(
            prompt=prompt,
            response=response,
            system_prompt=system_prompt,
            temperature=0.1,
            model_name="test-model",
        )

        # Get cache entry
        result = await cache.get(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            model_name="test-model",
        )

        assert result == response
        assert cache.stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_high_temperature_not_cached(self, cache: LLMCache):
        """Test that high temperature responses are not cached."""
        prompt = "Be creative"
        response = "Random creative output"

        # Try to cache with high temperature
        await cache.set(
            prompt=prompt,
            response=response,
            temperature=0.8,  # Above max_cacheable_temperature
            model_name="test-model",
        )

        # Should not be in cache
        result = await cache.get(
            prompt=prompt,
            temperature=0.8,
            model_name="test-model",
        )

        assert result is None
        assert cache.stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_high_temperature_get_skipped(self, cache: LLMCache):
        """Test that cache lookup is skipped for high temperature requests."""
        # First, cache something at low temperature
        await cache.set(
            prompt="test",
            response="cached",
            temperature=0.1,
            model_name="test-model",
        )

        # Try to get with high temperature - should skip cache
        result = await cache.get(
            prompt="test",
            temperature=0.8,  # Above threshold
            model_name="test-model",
        )

        assert result is None
        assert cache.stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_different_system_prompts_different_cache_entries(self, cache: LLMCache):
        """Test that different system prompts result in different cache entries."""
        prompt = "Hello"

        await cache.set(
            prompt=prompt,
            response="Response A",
            system_prompt="You are A",
            temperature=0.1,
            model_name="test-model",
        )

        await cache.set(
            prompt=prompt,
            response="Response B",
            system_prompt="You are B",
            temperature=0.1,
            model_name="test-model",
        )

        result_a = await cache.get(
            prompt=prompt,
            system_prompt="You are A",
            temperature=0.1,
            model_name="test-model",
        )

        result_b = await cache.get(
            prompt=prompt,
            system_prompt="You are B",
            temperature=0.1,
            model_name="test-model",
        )

        assert result_a == "Response A"
        assert result_b == "Response B"

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache: LLMCache):
        """Test clearing the cache."""
        # Add some entries
        await cache.set(prompt="p1", response="r1", temperature=0.1, model_name="m")
        await cache.set(prompt="p2", response="r2", temperature=0.1, model_name="m")

        assert cache.get_entry_count() == 2

        # Clear cache
        cleared = await cache.clear()
        assert cleared == 2
        assert cache.get_entry_count() == 0

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache: LLMCache):
        """Test that cache statistics are tracked correctly."""
        # Miss on empty cache
        await cache.get(prompt="p1", temperature=0.1, model_name="m")

        # Set and hit
        await cache.set(prompt="p2", response="r2", temperature=0.1, model_name="m")
        await cache.get(prompt="p2", temperature=0.1, model_name="m")

        # Skip due to high temperature
        await cache.get(prompt="p3", temperature=0.9, model_name="m")

        stats = cache.stats
        assert stats["misses"] == 1
        assert stats["hits"] == 1
        assert stats["skipped"] == 1


class TestCachingLLMProvider:
    """Tests for the CachingLLMProvider class."""

    @pytest.fixture
    def cache_path(self, tmp_path: Path) -> Path:
        """Create a temporary cache path."""
        return tmp_path / "test_cache.lance"

    @pytest.fixture
    def mock_llm(self) -> MockLLMProvider:
        """Create a mock LLM provider."""
        return MockLLMProvider()

    @pytest.fixture
    def cache(self, cache_path: Path) -> LLMCache:
        """Create an LLMCache instance."""
        config = LLMCacheConfig(
            enabled=True,
            ttl_seconds=3600,
            max_entries=1000,
            similarity_threshold=0.95,
            max_cacheable_temperature=0.3,
        )
        embedding_provider = MockEmbeddingProvider()
        return LLMCache(cache_path, embedding_provider, config)

    @pytest.fixture
    def cached_provider(
        self, mock_llm: MockLLMProvider, cache: LLMCache
    ) -> CachingLLMProvider:
        """Create a CachingLLMProvider instance."""
        return CachingLLMProvider(mock_llm, cache)

    def test_name_includes_cache_prefix(self, cached_provider: CachingLLMProvider):
        """Test that provider name includes cache prefix."""
        assert cached_provider.name == "cached:mock-llm"

    @pytest.mark.asyncio
    async def test_first_call_goes_to_provider(
        self, cached_provider: CachingLLMProvider, mock_llm: MockLLMProvider
    ):
        """Test that first call goes to underlying provider."""
        result = await cached_provider.generate(
            prompt="test prompt",
            system_prompt="test system",
            temperature=0.1,
        )

        assert len(mock_llm.calls) == 1
        assert "Response to: test prompt" in result

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(
        self, cached_provider: CachingLLMProvider, mock_llm: MockLLMProvider
    ):
        """Test that second identical call uses cache."""
        prompt = "What is 2+2?"
        system_prompt = "You are a calculator"

        # First call
        result1 = await cached_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )

        # Second call (should hit cache)
        result2 = await cached_provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
        )

        # Should only have one call to underlying provider
        assert len(mock_llm.calls) == 1
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_high_temperature_bypasses_cache(
        self, cached_provider: CachingLLMProvider, mock_llm: MockLLMProvider
    ):
        """Test that high temperature calls don't use cache."""
        prompt = "Be creative"

        # First call with high temp
        await cached_provider.generate(prompt=prompt, temperature=0.8)

        # Second call with high temp (should not hit cache)
        await cached_provider.generate(prompt=prompt, temperature=0.8)

        # Both calls should go to provider
        assert len(mock_llm.calls) == 2

    @pytest.mark.asyncio
    async def test_stats_accessible(
        self, cached_provider: CachingLLMProvider, mock_llm: MockLLMProvider
    ):
        """Test that cache stats are accessible through provider."""
        await cached_provider.generate(prompt="p1", temperature=0.1)
        await cached_provider.generate(prompt="p1", temperature=0.1)

        stats = cached_provider.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_stream_first_call_caches(
        self, cached_provider: CachingLLMProvider, mock_llm: MockLLMProvider
    ):
        """Test that streaming call caches the complete response."""
        prompt = "Tell me a story"

        # First streaming call
        chunks1 = []
        async for chunk in cached_provider.generate_stream(
            prompt=prompt,
            temperature=0.1,
        ):
            chunks1.append(chunk)

        # Should have called provider
        assert len(mock_llm.calls) == 1

        # Second streaming call (should hit cache)
        chunks2 = []
        async for chunk in cached_provider.generate_stream(
            prompt=prompt,
            temperature=0.1,
        ):
            chunks2.append(chunk)

        # Should not have made another call
        assert len(mock_llm.calls) == 1

        # Both should produce same content
        assert "".join(chunks1) == "".join(chunks2)

    @pytest.mark.asyncio
    async def test_different_prompts_different_cache_entries(
        self, cached_provider: CachingLLMProvider, mock_llm: MockLLMProvider
    ):
        """Test that different prompts get different cache entries."""
        await cached_provider.generate(prompt="Question 1", temperature=0.1)
        await cached_provider.generate(prompt="Question 2", temperature=0.1)
        await cached_provider.generate(prompt="Question 1", temperature=0.1)  # Cache hit
        await cached_provider.generate(prompt="Question 2", temperature=0.1)  # Cache hit

        # Only 2 calls to provider (first two)
        assert len(mock_llm.calls) == 2
        # 2 cache hits
        assert cached_provider.stats["hits"] == 2


class TestLLMCacheConfig:
    """Tests for LLMCacheConfig validation."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMCacheConfig()
        assert config.enabled is True
        assert config.ttl_seconds == 604800  # 7 days
        assert config.max_entries == 10000
        assert config.similarity_threshold == 0.95
        assert config.max_cacheable_temperature == 0.3

    def test_ttl_validation_min(self):
        """Test that TTL has minimum bound."""
        with pytest.raises(ValueError):
            LLMCacheConfig(ttl_seconds=30)  # Below 60

    def test_ttl_validation_max(self):
        """Test that TTL has maximum bound."""
        with pytest.raises(ValueError):
            LLMCacheConfig(ttl_seconds=3000000)  # Above 30 days

    def test_similarity_threshold_bounds(self):
        """Test similarity threshold bounds."""
        # Valid values
        LLMCacheConfig(similarity_threshold=0.0)
        LLMCacheConfig(similarity_threshold=1.0)

        # Invalid values
        with pytest.raises(ValueError):
            LLMCacheConfig(similarity_threshold=-0.1)
        with pytest.raises(ValueError):
            LLMCacheConfig(similarity_threshold=1.1)

    def test_max_entries_bounds(self):
        """Test max_entries bounds."""
        with pytest.raises(ValueError):
            LLMCacheConfig(max_entries=50)  # Below 100
        with pytest.raises(ValueError):
            LLMCacheConfig(max_entries=200000)  # Above 100000
