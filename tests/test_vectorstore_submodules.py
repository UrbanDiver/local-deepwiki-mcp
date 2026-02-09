"""Tests for vectorstore submodules.

Tests schema.py, utils.py, iterators.py, and maintenance.py modules.
These tests cover functionality NOT covered in test_vectorstore.py.
"""

import asyncio
import json
import threading
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from local_deepwiki.config import LazyIndexConfig
from local_deepwiki.core.vectorstore.iterators import ChunkIterator, LazyChunkLoader
from local_deepwiki.core.vectorstore.maintenance import LazyIndexManager
from local_deepwiki.core.vectorstore.schema import (
    BatchEmbeddingResult,
    ChunkBatch,
    EmbeddingProgress,
    LatencyStats,
    SearchFeedback,
    SearchProfile,
    SearchProfileConfig,
    SearchResultPage,
    SEARCH_PROFILES,
    VALID_CHUNK_TYPES,
    VALID_LANGUAGES,
    DEFAULT_MAX_MEMORY_MB,
    ESTIMATED_BYTES_PER_CHUNK,
)
from local_deepwiki.core.vectorstore.utils import (
    RateLimiter,
    _row_to_chunk_default,
    _sanitize_string_value,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language, SearchResult


# =====================
# Schema Tests
# =====================


class TestSchemaConstants:
    """Test schema constants and enums."""

    def test_valid_languages_constant(self):
        """Test VALID_LANGUAGES contains all Language enum values."""
        expected = {lang.value for lang in Language}
        assert VALID_LANGUAGES == expected
        assert "python" in VALID_LANGUAGES
        assert "typescript" in VALID_LANGUAGES

    def test_valid_chunk_types_constant(self):
        """Test VALID_CHUNK_TYPES contains all ChunkType enum values."""
        expected = {ct.value for ct in ChunkType}
        assert VALID_CHUNK_TYPES == expected
        assert "function" in VALID_CHUNK_TYPES
        assert "class" in VALID_CHUNK_TYPES

    def test_default_max_memory_mb_constant(self):
        """Test DEFAULT_MAX_MEMORY_MB is reasonable."""
        assert DEFAULT_MAX_MEMORY_MB == 256
        assert DEFAULT_MAX_MEMORY_MB > 0

    def test_estimated_bytes_per_chunk_constant(self):
        """Test ESTIMATED_BYTES_PER_CHUNK is reasonable."""
        assert ESTIMATED_BYTES_PER_CHUNK == 10_000
        assert ESTIMATED_BYTES_PER_CHUNK > 0


class TestSearchProfile:
    """Test SearchProfile enum."""

    def test_search_profile_values(self):
        """Test SearchProfile enum values."""
        assert SearchProfile.FAST.value == "fast"
        assert SearchProfile.BALANCED.value == "balanced"
        assert SearchProfile.THOROUGH.value == "thorough"

    def test_search_profiles_config(self):
        """Test SEARCH_PROFILES configuration dict."""
        assert len(SEARCH_PROFILES) == 3
        assert SearchProfile.FAST in SEARCH_PROFILES
        assert SearchProfile.BALANCED in SEARCH_PROFILES
        assert SearchProfile.THOROUGH in SEARCH_PROFILES

    def test_fast_profile_config(self):
        """Test FAST profile configuration."""
        config = SEARCH_PROFILES[SearchProfile.FAST]
        assert config.profile == SearchProfile.FAST
        assert config.fetch_multiplier == 1.0
        assert config.rerank_candidates == 10
        assert config.use_approximate is True
        assert config.min_similarity == 0.3

    def test_balanced_profile_config(self):
        """Test BALANCED profile configuration."""
        config = SEARCH_PROFILES[SearchProfile.BALANCED]
        assert config.profile == SearchProfile.BALANCED
        assert config.fetch_multiplier == 2.0
        assert config.rerank_candidates == 50
        assert config.use_approximate is True
        assert config.min_similarity == 0.2

    def test_thorough_profile_config(self):
        """Test THOROUGH profile configuration."""
        config = SEARCH_PROFILES[SearchProfile.THOROUGH]
        assert config.profile == SearchProfile.THOROUGH
        assert config.fetch_multiplier == 5.0
        assert config.rerank_candidates == 200
        assert config.use_approximate is False
        assert config.min_similarity == 0.1


class TestSearchResultPage:
    """Test SearchResultPage dataclass."""

    def test_search_result_page_creation(self):
        """Test creating a SearchResultPage."""
        chunk = CodeChunk(
            id="chunk1",
            file_path="test.py",
            language="python",
            chunk_type="function",
            content="def test(): pass",
            name="test",
            start_line=1,
            end_line=2,
        )
        results = [SearchResult(chunk=chunk, score=0.9)]
        page = SearchResultPage(
            results=results, total=100, offset=0, limit=10, has_more=True, cursor="abc"
        )
        assert page.results == results
        assert page.total == 100
        assert page.offset == 0
        assert page.limit == 10
        assert page.has_more is True
        assert page.cursor == "abc"

    def test_search_result_page_no_cursor(self):
        """Test SearchResultPage without cursor."""
        page = SearchResultPage(results=[], total=0, offset=0, limit=10, has_more=False)
        assert page.cursor is None


class TestChunkBatch:
    """Test ChunkBatch dataclass."""

    def test_chunk_batch_creation(self):
        """Test creating a ChunkBatch."""
        chunks = [
            CodeChunk(
                id="chunk1",
                file_path="test.py",
                language="python",
                chunk_type="function",
                content="def test(): pass",
                start_line=1,
                end_line=2,
            )
        ]
        batch = ChunkBatch(chunks=chunks, batch_index=0, total_batches=5, has_more=True)
        assert batch.chunks == chunks
        assert batch.batch_index == 0
        assert batch.total_batches == 5
        assert batch.has_more is True


class TestSearchFeedback:
    """Test SearchFeedback dataclass."""

    def test_search_feedback_creation(self):
        """Test creating SearchFeedback."""
        feedback = SearchFeedback(
            query="test query", result_id="result1", relevant=True
        )
        assert feedback.query == "test query"
        assert feedback.result_id == "result1"
        assert feedback.relevant is True
        assert isinstance(feedback.timestamp, float)
        assert feedback.timestamp > 0

    def test_search_feedback_custom_timestamp(self):
        """Test SearchFeedback with custom timestamp."""
        custom_time = 1234567890.0
        feedback = SearchFeedback(
            query="test", result_id="result1", relevant=False, timestamp=custom_time
        )
        assert feedback.timestamp == custom_time


class TestBatchEmbeddingResult:
    """Test BatchEmbeddingResult dataclass."""

    def test_batch_embedding_result_success(self):
        """Test successful BatchEmbeddingResult."""
        embeddings = [[0.1, 0.2, 0.3]]
        result = BatchEmbeddingResult(batch_index=0, embeddings=embeddings)
        assert result.batch_index == 0
        assert result.embeddings == embeddings
        assert result.error is None
        assert result.retry_count == 0

    def test_batch_embedding_result_error(self):
        """Test BatchEmbeddingResult with error."""
        error = ValueError("Test error")
        result = BatchEmbeddingResult(
            batch_index=1, embeddings=None, error=error, retry_count=2
        )
        assert result.batch_index == 1
        assert result.embeddings is None
        assert result.error is error
        assert result.retry_count == 2


class TestEmbeddingProgress:
    """Test EmbeddingProgress dataclass."""

    def test_embedding_progress_creation(self):
        """Test creating EmbeddingProgress."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        assert progress.total_texts == 100
        assert progress.total_batches == 10
        assert progress.completed_batches == 0
        assert progress.failed_batches == 0
        assert isinstance(progress.start_time, float)

    def test_embedding_progress_update_success(self):
        """Test updating progress with success."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        progress.update(success=True)
        assert progress.completed_batches == 1
        assert progress.failed_batches == 0

    def test_embedding_progress_update_failure(self):
        """Test updating progress with failure."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        progress.update(success=False)
        assert progress.completed_batches == 0
        assert progress.failed_batches == 1

    def test_embedding_progress_elapsed_seconds(self):
        """Test elapsed_seconds property."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        time.sleep(0.01)
        elapsed = progress.elapsed_seconds
        assert elapsed > 0
        assert elapsed < 1.0

    def test_embedding_progress_estimated_remaining_no_completed(self):
        """Test estimated_remaining_seconds with no completed batches."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        assert progress.estimated_remaining_seconds is None

    def test_embedding_progress_estimated_remaining_with_completed(self):
        """Test estimated_remaining_seconds with completed batches."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        time.sleep(0.01)
        progress.update(success=True)
        remaining = progress.estimated_remaining_seconds
        assert remaining is not None
        assert remaining > 0

    def test_embedding_progress_thread_safety(self):
        """Test thread-safe updates."""
        progress = EmbeddingProgress(total_texts=1000, total_batches=100)

        def update_worker():
            for _ in range(10):
                progress.update(success=True)

        threads = [threading.Thread(target=update_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert progress.completed_batches == 50

    def test_embedding_progress_log_progress(self):
        """Test log_progress method."""
        progress = EmbeddingProgress(total_texts=100, total_batches=10)
        progress.update(success=True)
        # Should not raise an exception
        progress.log_progress()


class TestLatencyStats:
    """Test LatencyStats dataclass."""

    def test_latency_stats_creation(self):
        """Test creating LatencyStats."""
        stats = LatencyStats(window_size=10)
        assert stats.window_size == 10
        assert stats.latencies == []

    def test_latency_stats_record(self):
        """Test recording latencies."""
        stats = LatencyStats(window_size=10)
        stats.record(100.0)
        stats.record(200.0)
        assert len(stats.latencies) == 2
        assert stats.latencies == [100.0, 200.0]

    def test_latency_stats_window_limit(self):
        """Test window size limit."""
        stats = LatencyStats(window_size=5)
        for i in range(10):
            stats.record(float(i))
        assert len(stats.latencies) == 5
        assert stats.latencies == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_latency_stats_get_average(self):
        """Test get_average method."""
        stats = LatencyStats(window_size=10)
        stats.record(100.0)
        stats.record(200.0)
        stats.record(300.0)
        assert stats.get_average() == 200.0

    def test_latency_stats_get_average_empty(self):
        """Test get_average with no data."""
        stats = LatencyStats(window_size=10)
        assert stats.get_average() is None

    def test_latency_stats_get_count(self):
        """Test get_count method."""
        stats = LatencyStats(window_size=10)
        stats.record(100.0)
        stats.record(200.0)
        assert stats.get_count() == 2

    def test_latency_stats_clear(self):
        """Test clear method."""
        stats = LatencyStats(window_size=10)
        stats.record(100.0)
        stats.record(200.0)
        stats.clear()
        assert stats.get_count() == 0
        assert stats.get_average() is None

    def test_latency_stats_thread_safety(self):
        """Test thread-safe recording."""
        stats = LatencyStats(window_size=100)

        def record_worker():
            for i in range(10):
                stats.record(float(i))

        threads = [threading.Thread(target=record_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert stats.get_count() == 50


# =====================
# Utils Tests
# =====================


class TestSanitizeStringValue:
    """Test _sanitize_string_value function."""

    def test_sanitize_no_quotes(self):
        """Test sanitizing string without quotes."""
        result = _sanitize_string_value("hello world")
        assert result == "hello world"

    def test_sanitize_single_quote(self):
        """Test sanitizing string with single quote."""
        result = _sanitize_string_value("it's a test")
        assert result == "it''s a test"

    def test_sanitize_multiple_quotes(self):
        """Test sanitizing string with multiple quotes."""
        result = _sanitize_string_value("'it's' 'test'")
        assert result == "''it''s'' ''test''"

    def test_sanitize_empty_string(self):
        """Test sanitizing empty string."""
        result = _sanitize_string_value("")
        assert result == ""

    def test_sanitize_sql_injection_attempt(self):
        """Test sanitizing potential SQL injection."""
        malicious = "test' OR '1'='1"
        result = _sanitize_string_value(malicious)
        assert result == "test'' OR ''1''=''1"


class TestRowToChunkDefault:
    """Test _row_to_chunk_default function."""

    def test_row_to_chunk_basic(self):
        """Test converting a basic row to CodeChunk."""
        row = {
            "id": "chunk1",
            "file_path": "test.py",
            "language": "python",
            "chunk_type": "function",
            "name": "test_func",
            "content": "def test_func(): pass",
            "start_line": 1,
            "end_line": 2,
            "docstring": "Test function",
            "parent_name": "TestClass",
            "metadata": json.dumps({"key": "value"}),
        }
        chunk = _row_to_chunk_default(row)
        assert chunk.id == "chunk1"
        assert chunk.file_path == "test.py"
        assert chunk.language == "python"
        assert chunk.chunk_type == "function"
        assert chunk.name == "test_func"
        assert chunk.content == "def test_func(): pass"
        assert chunk.start_line == 1
        assert chunk.end_line == 2
        assert chunk.docstring == "Test function"
        assert chunk.parent_name == "TestClass"
        assert chunk.metadata == {"key": "value"}

    def test_row_to_chunk_null_fields(self):
        """Test converting row with null fields."""
        row = {
            "id": "chunk1",
            "file_path": "test.py",
            "language": "python",
            "chunk_type": "module",
            "name": None,
            "content": "# Module",
            "start_line": 1,
            "end_line": 10,
            "docstring": None,
            "parent_name": None,
            "metadata": None,
        }
        chunk = _row_to_chunk_default(row)
        assert chunk.name is None
        assert chunk.docstring is None
        assert chunk.parent_name is None
        assert chunk.metadata == {}

    def test_row_to_chunk_empty_metadata(self):
        """Test converting row with empty metadata JSON."""
        row = {
            "id": "chunk1",
            "file_path": "test.py",
            "language": "python",
            "chunk_type": "function",
            "name": "func",
            "content": "def func(): pass",
            "start_line": 1,
            "end_line": 2,
            "docstring": None,
            "parent_name": None,
            "metadata": "{}",
        }
        chunk = _row_to_chunk_default(row)
        assert chunk.metadata == {}


class TestRateLimiter:
    """Test RateLimiter class."""

    async def test_rate_limiter_creation(self):
        """Test creating a RateLimiter."""
        limiter = RateLimiter(requests_per_minute=60)
        assert limiter.rate == 1.0
        assert limiter.tokens == 60.0
        assert limiter.max_tokens == 60.0

    async def test_rate_limiter_acquire_immediate(self):
        """Test acquiring token immediately."""
        limiter = RateLimiter(requests_per_minute=60)
        await limiter.acquire()
        # Should have consumed 1 token
        assert limiter.tokens < 60.0

    async def test_rate_limiter_acquire_wait(self):
        """Test rate limiter waiting when out of tokens."""
        limiter = RateLimiter(requests_per_minute=60)
        limiter.tokens = 0.5  # Less than 1 token

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should have waited for tokens to refill
        assert elapsed > 0.4  # Waited for at least 0.5 tokens to refill

    async def test_rate_limiter_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter(requests_per_minute=60)
        limiter.tokens = 0.0
        limiter.last_update = time.monotonic() - 1.0  # 1 second ago

        await limiter.acquire()
        # After 1 second, should have refilled 1 token (rate = 1.0/sec)
        assert limiter.tokens >= 0.0

    async def test_rate_limiter_max_tokens(self):
        """Test tokens don't exceed max."""
        limiter = RateLimiter(requests_per_minute=60)
        limiter.last_update = time.monotonic() - 100.0  # Long time ago

        await limiter.acquire()
        # Tokens should be capped at max_tokens
        assert limiter.tokens <= limiter.max_tokens


# =====================
# Iterator Tests
# =====================


class TestChunkIterator:
    """Test ChunkIterator class."""

    def _create_mock_table(self, rows):
        """Create a mock LanceDB table."""
        table = Mock()
        table.count_rows.return_value = len(rows)

        # Mock query chain with proper to_list return value
        def mock_to_list():
            return rows

        query = Mock()
        query.where = Mock(return_value=query)
        query.select = Mock(return_value=query)
        query.limit = Mock(return_value=query)
        query.to_list = mock_to_list
        table.search = Mock(return_value=query)

        return table

    def test_chunk_iterator_count_no_filter(self):
        """Test count without filter."""
        rows = [{"id": f"chunk{i}"} for i in range(10)]
        table = self._create_mock_table(rows)
        iterator = ChunkIterator(table=table, batch_size=5)

        count = iterator.count()
        assert count == 10
        table.count_rows.assert_called_once()

    def test_chunk_iterator_count_with_filter(self):
        """Test count with filter expression."""
        rows = [{"id": f"chunk{i}"} for i in range(5)]
        table = self._create_mock_table(rows)
        iterator = ChunkIterator(
            table=table, batch_size=5, filter_expr="language = 'python'"
        )

        count = iterator.count()
        assert count == 5

    def test_chunk_iterator_reset(self):
        """Test resetting the iterator."""
        table = self._create_mock_table([])
        iterator = ChunkIterator(table=table, batch_size=5)
        iterator._offset = 10
        iterator._cached_rows = [{"id": "test"}]

        iterator.reset()
        assert iterator._offset == 0
        assert iterator._cached_rows is None

    def test_chunk_iterator_sync_iteration(self):
        """Test synchronous iteration."""
        rows = [
            {
                "id": f"chunk{i}",
                "file_path": "test.py",
                "language": "python",
                "chunk_type": "function",
                "name": f"func{i}",
                "content": f"def func{i}(): pass",
                "start_line": i * 2,
                "end_line": i * 2 + 1,
                "docstring": None,
                "parent_name": None,
                "metadata": None,
            }
            for i in range(5)
        ]
        table = self._create_mock_table(rows)
        iterator = ChunkIterator(table=table, batch_size=2)

        chunks = list(iterator)
        assert len(chunks) == 5
        assert all(isinstance(c, CodeChunk) for c in chunks)
        assert chunks[0].name == "func0"
        assert chunks[4].name == "func4"

    async def test_chunk_iterator_async_iteration(self):
        """Test asynchronous iteration."""
        rows = [
            {
                "id": f"chunk{i}",
                "file_path": "test.py",
                "language": "python",
                "chunk_type": "function",
                "name": f"func{i}",
                "content": f"def func{i}(): pass",
                "start_line": i * 2,
                "end_line": i * 2 + 1,
                "docstring": None,
                "parent_name": None,
                "metadata": None,
            }
            for i in range(5)
        ]
        table = self._create_mock_table(rows)
        iterator = ChunkIterator(table=table, batch_size=2)

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        assert len(chunks) == 5
        assert all(isinstance(c, CodeChunk) for c in chunks)

    def test_chunk_iterator_batches(self):
        """Test batch iteration."""
        rows = [
            {
                "id": f"chunk{i}",
                "file_path": "test.py",
                "language": "python",
                "chunk_type": "function",
                "name": f"func{i}",
                "content": f"def func{i}(): pass",
                "start_line": i * 2,
                "end_line": i * 2 + 1,
                "docstring": None,
                "parent_name": None,
                "metadata": None,
            }
            for i in range(7)
        ]
        table = self._create_mock_table(rows)
        iterator = ChunkIterator(table=table, batch_size=3)

        batches = list(iterator.batches())
        assert len(batches) == 3
        assert batches[0].batch_index == 0
        assert len(batches[0].chunks) == 3
        assert batches[0].has_more is True
        assert batches[1].batch_index == 1
        assert len(batches[1].chunks) == 3
        assert batches[2].batch_index == 2
        assert len(batches[2].chunks) == 1
        assert batches[2].has_more is False

    async def test_chunk_iterator_async_batches(self):
        """Test async batch iteration."""
        rows = [
            {
                "id": f"chunk{i}",
                "file_path": "test.py",
                "language": "python",
                "chunk_type": "function",
                "name": f"func{i}",
                "content": f"def func{i}(): pass",
                "start_line": i * 2,
                "end_line": i * 2 + 1,
                "docstring": None,
                "parent_name": None,
                "metadata": None,
            }
            for i in range(5)
        ]
        table = self._create_mock_table(rows)
        iterator = ChunkIterator(table=table, batch_size=2)

        batches = []
        async for batch in iterator.async_batches():
            batches.append(batch)

        assert len(batches) == 3
        assert batches[0].batch_index == 0
        assert batches[2].has_more is False

    def test_chunk_iterator_empty_table(self):
        """Test iteration over empty table."""
        table = self._create_mock_table([])
        iterator = ChunkIterator(table=table, batch_size=5)

        chunks = list(iterator)
        assert chunks == []

    def test_chunk_iterator_custom_row_to_chunk(self):
        """Test using custom row_to_chunk function."""
        rows = [{"id": "chunk1", "custom": "data"}]
        table = self._create_mock_table(rows)

        def custom_converter(row):
            return CodeChunk(
                id=row["id"],
                file_path="custom.py",
                language="python",
                chunk_type="function",
                content="custom",
                start_line=1,
                end_line=2,
            )

        iterator = ChunkIterator(
            table=table, batch_size=5, row_to_chunk_fn=custom_converter
        )
        chunks = list(iterator)
        assert len(chunks) == 1
        assert chunks[0].file_path == "custom.py"


class TestLazyChunkLoader:
    """Test LazyChunkLoader class."""

    def _create_mock_store(self):
        """Create a mock VectorStore."""
        store = Mock()
        table = Mock()
        table.count_rows.return_value = 0

        # Mock query chain
        query = Mock()
        query.where = Mock(return_value=query)
        query.select = Mock(return_value=query)
        query.limit = Mock(return_value=query)
        query.to_list = Mock(return_value=[])
        table.search = Mock(return_value=query)

        store._get_table.return_value = table
        store._row_to_chunk = _row_to_chunk_default
        return store

    def test_lazy_chunk_loader_creation(self):
        """Test creating LazyChunkLoader."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store, max_memory_mb=512)
        assert loader._store is store
        assert loader._max_memory_mb == 512
        assert loader.max_memory_bytes == 512 * 1024 * 1024

    def test_calculate_optimal_batch_size_default(self):
        """Test calculating optimal batch size."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store, max_memory_mb=256)
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=256)
        expected = 256 * 1024 * 1024 // ESTIMATED_BYTES_PER_CHUNK
        assert batch_size == min(expected, 10_000)

    def test_calculate_optimal_batch_size_small_memory(self):
        """Test batch size with small memory."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store, max_memory_mb=10)
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=10)
        # Should be at least 100
        assert batch_size >= 100

    def test_calculate_optimal_batch_size_large_memory(self):
        """Test batch size is capped at 10k."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store, max_memory_mb=10000)
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=10000)
        assert batch_size == 10_000

    @patch("psutil.virtual_memory")
    def test_calculate_optimal_batch_size_auto_detect(self, mock_vm):
        """Test auto-detecting available memory."""
        mock_vm.return_value.available = 1024 * 1024 * 1024  # 1GB
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store, max_memory_mb=512)
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=None)
        assert batch_size > 0

    @patch("psutil.virtual_memory")
    def test_calculate_optimal_batch_size_psutil_error(self, mock_vm):
        """Test fallback when psutil fails."""
        mock_vm.side_effect = OSError("Test error")
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store, max_memory_mb=256)
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=None)
        # Should use max_memory_mb as fallback
        assert batch_size > 0

    def test_get_chunks_by_file_empty(self):
        """Test get_chunks_by_file with no matching chunks."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store)
        chunks = list(loader.get_chunks_by_file("test.py"))
        assert chunks == []

    def test_count_chunks_no_filter(self):
        """Test counting chunks without filter."""
        store = self._create_mock_store()
        store._get_table.return_value.count_rows.return_value = 42
        loader = LazyChunkLoader(store=store)
        count = loader.count_chunks()
        assert count == 42

    def test_count_chunks_with_language_filter(self):
        """Test counting chunks with language filter."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store)
        # Will return 0 since table is empty
        count = loader.count_chunks(language="python")
        assert count == 0

    def test_count_chunks_invalid_language(self):
        """Test counting with invalid language raises error."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store)
        with pytest.raises(ValueError, match="Invalid language filter"):
            loader.count_chunks(language="invalid_lang")

    def test_count_chunks_invalid_chunk_type(self):
        """Test counting with invalid chunk_type raises error."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store)
        with pytest.raises(ValueError, match="Invalid chunk_type filter"):
            loader.count_chunks(chunk_type="invalid_type")

    def test_get_all_chunks_invalid_filters(self):
        """Test get_all_chunks with invalid filters."""
        store = self._create_mock_store()
        loader = LazyChunkLoader(store=store)

        with pytest.raises(ValueError, match="Invalid language filter"):
            list(loader.get_all_chunks(language="invalid"))

        with pytest.raises(ValueError, match="Invalid chunk_type filter"):
            list(loader.get_all_chunks(chunk_type="invalid"))


# =====================
# Maintenance Tests
# =====================


class TestLazyIndexManager:
    """Test LazyIndexManager class."""

    def _create_mock_vectorstore(self):
        """Create a mock VectorStore."""
        store = Mock()
        table = Mock()
        table.count_rows.return_value = 1000
        store._get_table.return_value = table
        return store

    def test_lazy_index_manager_creation(self):
        """Test creating LazyIndexManager."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        assert manager._vectorstore is store
        assert isinstance(manager.config, LazyIndexConfig)
        assert manager._index_pending is False
        assert manager._index_created is False

    def test_lazy_index_manager_custom_config(self):
        """Test creating manager with custom config."""
        store = self._create_mock_vectorstore()
        config = LazyIndexConfig(
            enabled=True,
            latency_threshold_ms=500.0,
            min_rows=2000,
            latency_window_size=20,
        )
        manager = LazyIndexManager(vectorstore=store, config=config)
        assert manager.config.latency_threshold_ms == 500.0
        assert manager.config.min_rows == 2000

    def test_mark_index_pending(self):
        """Test marking index as pending."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_pending()
        assert manager._index_pending is True
        assert manager.is_index_pending() is True

    def test_mark_index_created(self):
        """Test marking index as created."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_pending()
        manager.mark_index_created()
        assert manager._index_pending is False
        assert manager._index_created is True
        assert manager.is_index_ready() is True
        assert manager.is_index_pending() is False

    def test_is_creation_in_progress(self):
        """Test checking if creation is in progress."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        assert manager.is_creation_in_progress() is False
        manager._creation_in_progress = True
        assert manager.is_creation_in_progress() is True

    def test_record_search_latency(self):
        """Test recording search latencies."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.record_search_latency(100.0)
        manager.record_search_latency(200.0)
        assert manager._latency_stats.get_count() == 2

    def test_should_create_index_disabled(self):
        """Test should_create_index when disabled."""
        store = self._create_mock_vectorstore()
        config = LazyIndexConfig(enabled=False)
        manager = LazyIndexManager(vectorstore=store, config=config)
        assert manager.should_create_index() is False

    def test_should_create_index_pending(self):
        """Test should_create_index when pending."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_pending()
        assert manager.should_create_index() is True

    def test_should_create_index_already_created(self):
        """Test should_create_index when already created."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_created()
        assert manager.should_create_index() is False

    def test_should_create_index_by_latency(self):
        """Test should_create_index based on latency threshold."""
        store = self._create_mock_vectorstore()
        config = LazyIndexConfig(enabled=True, latency_threshold_ms=100.0)
        manager = LazyIndexManager(vectorstore=store, config=config)

        # Record high latencies
        manager.record_search_latency(150.0)
        manager.record_search_latency(160.0)
        manager.record_search_latency(170.0)

        assert manager.should_create_index() is True

    def test_should_create_index_insufficient_samples(self):
        """Test should_create_index with insufficient samples."""
        store = self._create_mock_vectorstore()
        config = LazyIndexConfig(enabled=True, latency_threshold_ms=100.0)
        manager = LazyIndexManager(vectorstore=store, config=config)

        # Only 2 samples (need 3+)
        manager.record_search_latency(150.0)
        manager.record_search_latency(160.0)

        assert manager.should_create_index() is False

    async def test_schedule_index_creation(self):
        """Test scheduling index creation."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)

        # Mock create_index_now to avoid actual creation
        manager.create_index_now = AsyncMock()

        await manager.schedule_index_creation()
        assert manager._index_task is not None
        assert manager._creation_in_progress is True

    async def test_schedule_index_creation_already_created(self):
        """Test scheduling when already created."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_created()

        await manager.schedule_index_creation()
        assert manager._index_task is None

    async def test_wait_for_index_already_ready(self):
        """Test waiting for index when already ready."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_created()

        result = await manager.wait_for_index(timeout=1.0)
        assert result is True

    async def test_wait_for_index_timeout(self):
        """Test waiting for index with timeout."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)

        result = await manager.wait_for_index(timeout=0.01)
        assert result is False

    async def test_create_index_now_no_table(self):
        """Test create_index_now when table doesn't exist."""
        store = self._create_mock_vectorstore()
        store._get_table.return_value = None
        manager = LazyIndexManager(vectorstore=store)

        with pytest.raises(RuntimeError, match="table does not exist"):
            await manager.create_index_now()

    async def test_create_index_now_insufficient_rows(self):
        """Test create_index_now with insufficient rows."""
        store = self._create_mock_vectorstore()
        table = Mock()
        table.count_rows.return_value = 100
        store._get_table.return_value = table
        config = LazyIndexConfig(min_rows=1000)
        manager = LazyIndexManager(vectorstore=store, config=config)

        await manager.create_index_now()
        # Should skip without raising error
        assert not manager.is_index_ready()

    async def test_create_index_now_success(self):
        """Test successful index creation."""
        store = self._create_mock_vectorstore()
        table = Mock()
        table.count_rows.return_value = 1000
        table.create_index = Mock()
        store._get_table.return_value = table
        manager = LazyIndexManager(vectorstore=store)

        await manager.create_index_now()
        assert manager.is_index_ready()
        table.create_index.assert_called_once()

    async def test_create_index_now_with_callback(self):
        """Test index creation with progress callback."""
        store = self._create_mock_vectorstore()
        table = Mock()
        table.count_rows.return_value = 1000
        table.create_index = Mock()
        store._get_table.return_value = table
        manager = LazyIndexManager(vectorstore=store)

        callback_messages = []

        def callback(msg):
            callback_messages.append(msg)

        await manager.create_index_now(progress_callback=callback)
        assert len(callback_messages) == 2
        assert "Creating vector index" in callback_messages[0]
        assert "successfully" in callback_messages[1]

    def test_on_index_ready_already_ready(self):
        """Test on_index_ready callback when already ready."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_created()

        callback_called = []
        manager.on_index_ready(lambda: callback_called.append(True))
        assert callback_called == [True]

    def test_on_index_ready_future(self):
        """Test on_index_ready callback for future event."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)

        callback_called = []
        manager.on_index_ready(lambda: callback_called.append(True))
        assert callback_called == []

        manager.mark_index_created()
        assert callback_called == [True]

    def test_on_index_ready_callback_error(self):
        """Test on_index_ready handles callback errors."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)

        def failing_callback():
            raise ValueError("Test error")

        # Should not raise
        manager.on_index_ready(failing_callback)
        manager.mark_index_created()

    def test_get_stats(self):
        """Test get_stats method."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_pending()
        manager.record_search_latency(100.0)

        stats = manager.get_stats()
        assert stats["enabled"] is True
        assert stats["index_pending"] is True
        assert stats["index_created"] is False
        assert stats["creation_in_progress"] is False
        assert stats["average_latency_ms"] == 100.0
        assert stats["latency_samples"] == 1

    def test_reset(self):
        """Test resetting manager state."""
        store = self._create_mock_vectorstore()
        manager = LazyIndexManager(vectorstore=store)
        manager.mark_index_pending()
        manager.mark_index_created()
        manager.record_search_latency(100.0)
        manager.on_index_ready(lambda: None)

        manager.reset()
        assert manager._index_pending is False
        assert manager._index_created is False
        assert manager._creation_in_progress is False
        assert manager._latency_stats.get_count() == 0
        assert len(manager._on_index_ready_callbacks) == 0
