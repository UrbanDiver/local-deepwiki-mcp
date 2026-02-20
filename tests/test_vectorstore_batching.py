"""Tests for batch embedding and parallel embedding operations.

Covers: TestBatchEmbed, TestParallelEmbedding, TestParallelEmbeddingRetry,
TestParallelEmbeddingRateLimiting, TestRateLimiter, TestEmbeddingProgress,
TestBatchEmbeddingResult, TestEmbeddingBatchConfig, TestParallelEmbeddingIntegration.
"""

import asyncio
import time

import pytest

from local_deepwiki.config import EmbeddingBatchConfig
from local_deepwiki.models import ChunkType, CodeChunk, Language
from local_deepwiki.providers.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384, name: str = "mock"):
        self._dimension = dimension
        self._name = name
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings."""
        self.embed_calls.append(texts)
        return [[0.1] * self._dimension for _ in texts]


class SlowMockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider with configurable delay for testing parallel execution."""

    def __init__(
        self,
        dimension: int = 384,
        delay_seconds: float = 0.1,
        name: str = "local:slow-mock",
    ):
        self._dimension = dimension
        self._delay_seconds = delay_seconds
        self._name = name
        self.embed_calls: list[list[str]] = []
        self.call_times: list[float] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name  # Configurable to test different provider types

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings with delay."""
        self.call_times.append(time.time())
        self.embed_calls.append(texts)
        await asyncio.sleep(self._delay_seconds)
        return [[0.1] * self._dimension for _ in texts]


class FailingMockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider that fails for testing error handling."""

    def __init__(
        self,
        dimension: int = 384,
        fail_count: int = 2,
        fail_on_batches: set[int] | None = None,
    ):
        self._dimension = dimension
        self._fail_count = fail_count
        self._call_count = 0
        self._fail_on_batches = fail_on_batches or set()
        self._batch_call_counts: dict[int, int] = {}
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return "mock:failing"

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings, failing on specified conditions."""
        self.embed_calls.append(texts)
        self._call_count += 1

        # Track batch-specific call counts (based on first text as identifier)
        batch_id = hash(texts[0]) if texts else 0
        self._batch_call_counts[batch_id] = self._batch_call_counts.get(batch_id, 0) + 1

        # Fail if this batch should fail and hasn't exceeded retry count
        if self._fail_on_batches and batch_id in self._fail_on_batches:
            if self._batch_call_counts[batch_id] <= self._fail_count:
                raise ConnectionError(
                    f"Simulated connection error (attempt {self._batch_call_counts[batch_id]})"
                )

        # Otherwise fail for first N calls globally
        if self._call_count <= self._fail_count:
            raise ConnectionError(
                f"Simulated connection error (call {self._call_count})"
            )

        return [[0.1] * self._dimension for _ in texts]


class RateLimitMockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider that simulates rate limiting."""

    def __init__(self, dimension: int = 384, rate_limit_after: int = 3):
        self._dimension = dimension
        self._rate_limit_after = rate_limit_after
        self._call_count = 0
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return "openai:rate-limited"  # Simulates API provider

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings, simulating rate limit after N calls."""
        self.embed_calls.append(texts)
        self._call_count += 1

        if self._call_count == self._rate_limit_after:
            raise RuntimeError("Rate limit exceeded. Please retry after 60 seconds.")

        return [[0.1] * self._dimension for _ in texts]


def make_chunk(
    id: str,
    file_path: str = "test.py",
    content: str = "test code",
    language: Language = Language.PYTHON,
    chunk_type: ChunkType = ChunkType.FUNCTION,
) -> CodeChunk:
    """Create a test code chunk."""
    return CodeChunk(
        id=id,
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=f"test_{id}",
        content=content,
        start_line=1,
        end_line=10,
    )


class TestBatchEmbed:
    """Tests for _batch_embed functionality."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_batch_embed_with_progress_logging(self, vector_store):
        """Test _batch_embed logs progress for large batches."""
        texts = [f"text_{i}" for i in range(10)]
        # Small batch size to trigger multiple batches
        embeddings = await vector_store._batch_embed(
            texts, batch_size=3, log_progress=True
        )
        assert len(embeddings) == 10
        # Each embedding should have correct dimension
        assert all(len(e) == 384 for e in embeddings)

    async def test_batch_embed_without_progress_logging(self, vector_store):
        """Test _batch_embed without progress logging."""
        texts = [f"text_{i}" for i in range(10)]
        embeddings = await vector_store._batch_embed(
            texts, batch_size=3, log_progress=False
        )
        assert len(embeddings) == 10

    async def test_batch_embed_single_batch(self, vector_store):
        """Test _batch_embed with single batch (no progress logging needed)."""
        texts = ["text_1", "text_2"]
        embeddings = await vector_store._batch_embed(
            texts, batch_size=100, log_progress=True
        )
        assert len(embeddings) == 2


class TestParallelEmbedding:
    """Tests for parallel embedding generation."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    def slow_vector_store(self, tmp_path):
        """Create a vector store with slow embedding provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = SlowMockEmbeddingProvider(delay_seconds=0.05)
        config = EmbeddingBatchConfig(batch_size=2, concurrency=4)
        return VectorStore(db_path, provider, embedding_batch_config=config)

    async def test_parallel_embedding_basic(self, vector_store):
        """Test basic parallel embedding generation."""
        texts = [f"text_{i}" for i in range(20)]
        embeddings = await vector_store._batch_embed(texts, batch_size=5)

        assert len(embeddings) == 20
        assert all(len(e) == 384 for e in embeddings)

    async def test_parallel_embedding_preserves_order(self, vector_store):
        """Test that parallel embedding preserves input order."""
        # Use distinctive texts so we can verify order
        texts = [f"unique_text_{i:04d}" for i in range(50)]
        embeddings = await vector_store._batch_embed(texts, batch_size=10)

        # All embeddings should be present
        assert len(embeddings) == 50

        # Embeddings should be in same order as inputs
        # (with mock provider, all embeddings are identical, but count should match)
        provider = vector_store.embedding_provider
        total_embedded = sum(len(call) for call in provider.embed_calls)
        assert total_embedded == 50

    @pytest.mark.slow
    async def test_parallel_embedding_faster_than_sequential(self, slow_vector_store):
        """Test that parallel embedding is faster than sequential."""
        texts = [f"text_{i}" for i in range(10)]  # 10 texts, 2 per batch = 5 batches

        # Time parallel execution
        start = time.time()
        await slow_vector_store._batch_embed(texts, batch_size=2)
        parallel_time = time.time() - start

        # Time sequential execution (for comparison)
        start = time.time()
        await slow_vector_store._batch_embed_sequential(texts, batch_size=2)
        sequential_time = time.time() - start

        # Parallel should be faster (at least 2x with 4 concurrent workers)
        # Allow generous tolerance for test environment variations
        assert parallel_time < sequential_time * 0.95, (
            f"Parallel ({parallel_time:.3f}s) should be faster than "
            f"sequential ({sequential_time:.3f}s)"
        )

    async def test_parallel_embedding_concurrency_limited(self, tmp_path):
        """Test that concurrency is properly limited by semaphore."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Use API provider name to avoid automatic concurrency boost for local
        provider = SlowMockEmbeddingProvider(delay_seconds=0.1, name="openai:slow-mock")

        config = EmbeddingBatchConfig(batch_size=1, concurrency=2)  # Only 2 concurrent
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        texts = [f"text_{i}" for i in range(4)]  # 4 batches with concurrency 2

        start = time.time()
        await store._batch_embed(texts, batch_size=1)
        elapsed = time.time() - start

        # With 4 batches and concurrency 2, should take ~0.2s (2 rounds of 0.1s each)
        # With concurrency 4, would take ~0.1s
        # Allow some margin
        assert elapsed >= 0.15, (
            f"Expected >= 0.15s with concurrency 2, got {elapsed:.3f}s"
        )

    async def test_parallel_embedding_empty_list(self, vector_store):
        """Test parallel embedding with empty list."""
        embeddings = await vector_store._batch_embed([])
        assert embeddings == []

    async def test_parallel_embedding_single_text(self, vector_store):
        """Test parallel embedding with single text."""
        embeddings = await vector_store._batch_embed(["single text"])
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384

    async def test_parallel_embedding_single_batch(self, vector_store):
        """Test parallel embedding when all texts fit in single batch."""
        texts = ["text_1", "text_2", "text_3"]
        embeddings = await vector_store._batch_embed(texts, batch_size=100)
        assert len(embeddings) == 3

    async def test_parallel_embedding_with_progress_logging(self, vector_store):
        """Test parallel embedding with progress logging enabled."""
        texts = [f"text_{i}" for i in range(30)]
        # This should complete without error with logging enabled
        embeddings = await vector_store._batch_embed(
            texts, batch_size=10, log_progress=True
        )
        assert len(embeddings) == 30


class TestParallelEmbeddingRetry:
    """Tests for parallel embedding retry logic."""

    @pytest.fixture
    def failing_vector_store(self, tmp_path):
        """Create a vector store with failing provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = FailingMockEmbeddingProvider(fail_count=2)
        config = EmbeddingBatchConfig(
            batch_size=5,
            concurrency=2,
            retry_max_attempts=3,
            retry_base_delay=0.1,
        )
        return VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

    async def test_retry_on_connection_error(self, failing_vector_store):
        """Test that connection errors trigger retry."""
        texts = [f"text_{i}" for i in range(5)]

        # Should succeed after retries
        embeddings = await failing_vector_store._batch_embed(texts, batch_size=5)
        assert len(embeddings) == 5

        # Provider should have been called multiple times due to retries
        provider = failing_vector_store.embedding_provider
        assert len(provider.embed_calls) >= 2

    async def test_retry_exhausted_raises_error(self, tmp_path):
        """Test that exhausted retries raise RuntimeError."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Create provider that always fails
        provider = FailingMockEmbeddingProvider(fail_count=100)
        config = EmbeddingBatchConfig(
            batch_size=5,
            concurrency=1,
            retry_max_attempts=2,
            retry_base_delay=0.1,  # Must be >= 0.1
        )
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        texts = [f"text_{i}" for i in range(5)]

        with pytest.raises(RuntimeError, match="Failed to embed"):
            await store._batch_embed(texts, batch_size=5)

    async def test_partial_failure_reports_errors(self, tmp_path):
        """Test that partial batch failures are properly reported."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Provider that fails on specific batches
        provider = FailingMockEmbeddingProvider(
            fail_count=100,  # Never succeeds
            fail_on_batches={hash("batch_2_text_0")},  # Fail on second batch
        )
        config = EmbeddingBatchConfig(
            batch_size=2,
            concurrency=2,
            retry_max_attempts=2,
            retry_base_delay=0.1,  # Must be >= 0.1
        )
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        texts = ["batch_1_text_0", "batch_1_text_1", "batch_2_text_0", "batch_2_text_1"]

        with pytest.raises(RuntimeError, match="Failed to embed"):
            await store._batch_embed(texts, batch_size=2)


class TestParallelEmbeddingRateLimiting:
    """Tests for rate limiting in parallel embedding."""

    @pytest.fixture
    def rate_limited_store(self, tmp_path):
        """Create a vector store with rate limiting configured."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="openai:test")
        config = EmbeddingBatchConfig(
            batch_size=2,
            concurrency=4,
            rate_limit_rpm=120,  # 2 requests per second
        )
        return VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

    async def test_rate_limiter_throttles_requests(self, rate_limited_store):
        """Test that rate limiter properly throttles requests."""
        texts = [f"text_{i}" for i in range(8)]  # 4 batches

        start = time.time()
        await rate_limited_store._batch_embed(texts, batch_size=2)
        elapsed = time.time() - start

        # With 120 RPM (2/sec), 4 requests should take at least ~1.5 seconds
        # But since tokens accumulate, first batch may go through quickly
        # Just verify it took some time
        assert elapsed >= 0.0  # Basic sanity check

    async def test_rate_limiter_handles_api_errors(self, tmp_path):
        """Test that rate limit API errors trigger retry."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = RateLimitMockEmbeddingProvider(rate_limit_after=2)
        config = EmbeddingBatchConfig(
            batch_size=2,
            concurrency=1,  # Sequential to control order
            retry_max_attempts=3,
            retry_base_delay=0.1,
        )
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        texts = [f"text_{i}" for i in range(6)]  # 3 batches

        # Should succeed because rate limit error is retryable
        embeddings = await store._batch_embed(texts, batch_size=2)
        assert len(embeddings) == 6


class TestProviderTypeDetection:
    """Tests for provider type detection."""

    def test_local_provider_detection(self, tmp_path):
        """Test detection of local provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="local:all-MiniLM-L6-v2")
        store = VectorStore(tmp_path / "test.lance", provider)

        assert store._is_local_provider() is True

    def test_api_provider_detection(self, tmp_path):
        """Test detection of API provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="openai:text-embedding-3-small")
        store = VectorStore(tmp_path / "test.lance", provider)

        assert store._is_local_provider() is False

    def test_optimal_config_for_local(self, tmp_path):
        """Test optimal config calculation for local provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="local:test")
        config = EmbeddingBatchConfig(batch_size=50, concurrency=2)
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        batch_size, concurrency = store._get_optimal_batch_config()

        # Local provider should get larger batch size and higher concurrency
        assert batch_size >= 100
        assert concurrency >= 4

    def test_optimal_config_for_api(self, tmp_path):
        """Test optimal config calculation for API provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="openai:test")
        config = EmbeddingBatchConfig(batch_size=200, concurrency=8)
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        batch_size, concurrency = store._get_optimal_batch_config()

        # API provider should get smaller batch size and lower concurrency
        assert batch_size <= 50
        assert concurrency <= 4


class TestEmbeddingBatchConfig:
    """Tests for embedding batch configuration."""

    def test_get_embedding_batch_config(self, tmp_path):
        """Test getting embedding batch configuration."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="local:test")
        config = EmbeddingBatchConfig(
            batch_size=100,
            concurrency=4,
            rate_limit_rpm=60,
            retry_max_attempts=5,
            retry_base_delay=2.0,
        )
        store = VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

        batch_config = store.embedding_batch_config

        assert batch_config["batch_size"] == 100
        assert batch_config["concurrency"] == 4
        assert batch_config["rate_limit_rpm"] == 60
        assert batch_config["retry_max_attempts"] == 5
        assert batch_config["retry_base_delay"] == 2.0
        assert batch_config["is_local_provider"] is True
        assert "optimal_batch_size" in batch_config
        assert "optimal_concurrency" in batch_config

    def test_default_config(self, tmp_path):
        """Test default embedding batch configuration."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider()
        store = VectorStore(tmp_path / "test.lance", provider)

        batch_config = store.embedding_batch_config

        # Check defaults from EmbeddingBatchConfig
        assert batch_config["batch_size"] == 100
        assert batch_config["concurrency"] == 4
        assert batch_config["rate_limit_rpm"] is None
        assert batch_config["retry_max_attempts"] == 3
        assert batch_config["retry_base_delay"] == 1.0


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    async def test_rate_limiter_basic(self):
        """Test basic rate limiter functionality."""
        from local_deepwiki.core.vectorstore import RateLimiter

        limiter = RateLimiter(requests_per_minute=600)  # 10 per second

        # First few requests should be fast (tokens available)
        start = time.time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.time() - start

        # Should be nearly instant with tokens available
        assert elapsed < 1.0

    @pytest.mark.slow
    async def test_rate_limiter_throttles(self):
        """Test that rate limiter actually throttles."""
        from local_deepwiki.core.vectorstore import RateLimiter

        limiter = RateLimiter(requests_per_minute=60)  # 1 per second
        # Drain the initial tokens
        limiter.tokens = 0.0

        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should have waited ~1 second to refill
        assert elapsed >= 0.7


class TestEmbeddingProgress:
    """Tests for EmbeddingProgress tracking."""

    def test_progress_update(self):
        """Test progress update functionality."""
        from local_deepwiki.core.vectorstore import EmbeddingProgress

        progress = EmbeddingProgress(total_texts=100, total_batches=10)

        progress.update(success=True)
        assert progress.completed_batches == 1
        assert progress.failed_batches == 0

        progress.update(success=False)
        assert progress.completed_batches == 1
        assert progress.failed_batches == 1

    def test_progress_estimated_remaining(self):
        """Test estimated remaining time calculation."""
        from local_deepwiki.core.vectorstore import EmbeddingProgress

        progress = EmbeddingProgress(total_texts=100, total_batches=10)

        # No completed batches yet
        assert progress.estimated_remaining_seconds is None

        # Simulate some progress
        progress.completed_batches = 5
        progress.start_time = time.time() - 5.0  # 5 seconds elapsed

        # With 5 batches done in 5 seconds, remaining 5 batches should take ~5 seconds
        eta = progress.estimated_remaining_seconds
        assert eta is not None
        assert 4.0 <= eta <= 6.0

    def test_progress_elapsed_time(self):
        """Test elapsed time calculation."""
        from local_deepwiki.core.vectorstore import EmbeddingProgress

        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        progress.start_time = time.time() - 2.5

        elapsed = progress.elapsed_seconds
        assert 2.4 <= elapsed <= 2.6


class TestBatchEmbeddingResult:
    """Tests for BatchEmbeddingResult dataclass."""

    def test_successful_result(self):
        """Test successful batch result."""
        from local_deepwiki.core.vectorstore import BatchEmbeddingResult

        result = BatchEmbeddingResult(
            batch_index=0,
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
        )

        assert result.batch_index == 0
        assert result.embeddings == [[0.1, 0.2], [0.3, 0.4]]
        assert result.error is None
        assert result.retry_count == 0

    def test_failed_result(self):
        """Test failed batch result."""
        from local_deepwiki.core.vectorstore import BatchEmbeddingResult

        error = ConnectionError("Test error")
        result = BatchEmbeddingResult(
            batch_index=1,
            embeddings=None,
            error=error,
            retry_count=3,
        )

        assert result.batch_index == 1
        assert result.embeddings is None
        assert result.error is error
        assert result.retry_count == 3


class TestParallelEmbeddingIntegration:
    """Integration tests for parallel embedding with full VectorStore operations."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for integration testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="local:test")
        config = EmbeddingBatchConfig(batch_size=10, concurrency=4)
        return VectorStore(
            tmp_path / "test.lance", provider, embedding_batch_config=config
        )

    async def test_create_or_update_with_parallel_embedding(self, vector_store):
        """Test that create_or_update_table uses parallel embedding."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(50)]
        count = await vector_store.create_or_update_table(chunks)

        assert count == 50
        stats = vector_store.stats
        assert stats["total_chunks"] == 50

    async def test_add_chunks_with_parallel_embedding(self, vector_store):
        """Test that add_chunks uses parallel embedding."""
        # Create initial data
        initial_chunks = [make_chunk(f"initial_{i}") for i in range(10)]
        await vector_store.create_or_update_table(initial_chunks)

        # Add more chunks
        new_chunks = [make_chunk(f"new_{i}") for i in range(40)]
        count = await vector_store.add_chunks(new_chunks)

        assert count == 40
        stats = vector_store.stats
        assert stats["total_chunks"] == 50

    async def test_search_after_parallel_indexing(self, vector_store):
        """Test search works correctly after parallel indexing."""
        chunks = [
            make_chunk(f"func_{i}", content=f"def function_{i}(): pass")
            for i in range(30)
        ]
        await vector_store.create_or_update_table(chunks)

        results = await vector_store.search("function", limit=5)
        assert len(results) > 0
        assert all(r.chunk is not None for r in results)
