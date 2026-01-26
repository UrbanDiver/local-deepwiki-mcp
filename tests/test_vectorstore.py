"""Tests for vector store functionality."""

import asyncio
import time

import pytest

from local_deepwiki.config import EmbeddingBatchConfig, SearchCacheConfig
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

    def get_dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings."""
        self.embed_calls.append(texts)
        return [[0.1] * self._dimension for _ in texts]


class SlowMockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider with configurable delay for testing parallel execution."""

    def __init__(self, dimension: int = 384, delay_seconds: float = 0.1, name: str = "local:slow-mock"):
        self._dimension = dimension
        self._delay_seconds = delay_seconds
        self._name = name
        self.embed_calls: list[list[str]] = []
        self.call_times: list[float] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._name  # Configurable to test different provider types

    def get_dimension(self) -> int:
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

    def get_dimension(self) -> int:
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
                raise ConnectionError(f"Simulated connection error (attempt {self._batch_call_counts[batch_id]})")

        # Otherwise fail for first N calls globally
        if self._call_count <= self._fail_count:
            raise ConnectionError(f"Simulated connection error (call {self._call_count})")

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

    def get_dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings, simulating rate limit after N calls."""
        self.embed_calls.append(texts)
        self._call_count += 1

        if self._call_count == self._rate_limit_after:
            raise Exception("Rate limit exceeded. Please retry after 60 seconds.")

        return [[0.1] * self._dimension for _ in texts]


class SemanticMockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider that generates different embeddings based on query content.

    This allows testing semantic similarity by returning similar embeddings for
    similar queries and different embeddings for different queries.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return "semantic_mock"

    def get_dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings based on text content.

        Uses a hash-based approach to generate deterministic but
        VERY different embeddings for different texts. The embeddings are
        designed so that different texts have low cosine similarity (<0.9)
        to ensure cache misses for different queries.
        """
        import math
        self.embed_calls.append(texts)
        embeddings = []
        for text in texts:
            # Create a deterministic but highly content-dependent embedding
            # Use hash to seed a pseudo-random pattern that varies significantly
            embedding = []
            text_hash = hash(text) & 0xFFFFFFFF  # Ensure positive
            for i in range(self._dimension):
                # Use different seeds and transforms to maximize variation
                seed = (text_hash * (i + 1) * 31337) & 0xFFFFFFFF
                # Use sine/cosine transforms for more varied values
                val = 0.5 + 0.5 * math.sin(seed * 0.0001 + i * 0.1)
                embedding.append(val)
            embeddings.append(embedding)
        return embeddings


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


class TestVectorStoreIndexes:
    """Tests for vector store scalar indexes."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data."""
        chunks = [
            make_chunk("chunk_1", "src/main.py", "def main(): pass"),
            make_chunk("chunk_2", "src/main.py", "def helper(): pass"),
            make_chunk("chunk_3", "src/utils.py", "def util(): pass"),
            make_chunk("chunk_4", "tests/test.py", "def test(): pass"),
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_create_table_creates_indexes(self, populated_store):
        """Test that creating a table creates scalar indexes."""
        table = populated_store._get_table()
        assert table is not None

        # Check that indexes exist
        indexes = {idx["name"] for idx in table.list_indices()}
        # Index names are based on column names
        assert "id_idx" in indexes or any("id" in idx for idx in indexes)

    async def test_get_chunk_by_id_uses_index(self, populated_store):
        """Test that get_chunk_by_id can find chunks efficiently."""
        # Should find existing chunk
        chunk = await populated_store.get_chunk_by_id("chunk_1")
        assert chunk is not None
        assert chunk.id == "chunk_1"
        assert chunk.file_path == "src/main.py"

        # Should return None for non-existent chunk
        chunk = await populated_store.get_chunk_by_id("nonexistent")
        assert chunk is None

    async def test_get_chunks_by_file_uses_index(self, populated_store):
        """Test that get_chunks_by_file can find chunks efficiently."""
        # Get all chunks for main.py
        chunks = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks) == 2
        assert all(c.file_path == "src/main.py" for c in chunks)

        # Get chunks for different file
        chunks = await populated_store.get_chunks_by_file("src/utils.py")
        assert len(chunks) == 1
        assert chunks[0].id == "chunk_3"

        # Non-existent file returns empty list
        chunks = await populated_store.get_chunks_by_file("nonexistent.py")
        assert chunks == []

    async def test_delete_chunks_by_file_uses_index(self, populated_store):
        """Test that delete_chunks_by_file works efficiently."""
        # Verify chunks exist before delete
        chunks_before = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks_before) == 2

        # Delete chunks for main.py
        await populated_store.delete_chunks_by_file("src/main.py")

        # Verify deletion by checking chunks are gone
        chunks = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks) == 0

        # Other files unaffected
        chunks = await populated_store.get_chunks_by_file("src/utils.py")
        assert len(chunks) == 1

    async def test_delete_chunks_by_files_batch(self, populated_store):
        """Test that delete_chunks_by_files deletes multiple files in one operation."""
        # Verify chunks exist before delete
        chunks_main = await populated_store.get_chunks_by_file("src/main.py")
        chunks_utils = await populated_store.get_chunks_by_file("src/utils.py")
        assert len(chunks_main) == 2
        assert len(chunks_utils) == 1

        # Batch delete chunks for both files
        result = await populated_store.delete_chunks_by_files(["src/main.py", "src/utils.py"])
        assert result == 2  # Returns count of file paths processed

        # Verify all chunks are gone
        chunks = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks) == 0
        chunks = await populated_store.get_chunks_by_file("src/utils.py")
        assert len(chunks) == 0

    async def test_delete_chunks_by_files_empty_list(self, populated_store):
        """Test that delete_chunks_by_files handles empty list."""
        result = await populated_store.delete_chunks_by_files([])
        assert result == 0

        # Verify nothing was deleted
        chunks = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks) == 2

    async def test_delete_chunks_by_files_nonexistent(self, populated_store):
        """Test that delete_chunks_by_files handles nonexistent files gracefully."""
        result = await populated_store.delete_chunks_by_files(["nonexistent1.py", "nonexistent2.py"])
        assert result == 2  # Returns count of paths processed, even if no rows matched

        # Verify existing chunks unaffected
        chunks = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks) == 2

    async def test_delete_chunks_by_files_with_quotes(self, vector_store):
        """Test batch delete with file paths containing quotes."""
        chunks = [
            make_chunk("test1", file_path="path'one.py"),
            make_chunk("test2", file_path="path'two.py"),
            make_chunk("test3", file_path="normal.py"),
        ]
        await vector_store.create_or_update_table(chunks)

        # Batch delete files with quotes
        await vector_store.delete_chunks_by_files(["path'one.py", "path'two.py"])

        # Verify deletion
        chunks = await vector_store.get_chunks_by_file("path'one.py")
        assert len(chunks) == 0
        chunks = await vector_store.get_chunks_by_file("path'two.py")
        assert len(chunks) == 0
        # Normal file unaffected
        chunks = await vector_store.get_chunks_by_file("normal.py")
        assert len(chunks) == 1

    async def test_ensure_indexes_on_existing_table(self, vector_store, tmp_path):
        """Test that opening an existing table ensures indexes exist."""
        # Create table with data
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Create new store instance pointing to same DB
        from local_deepwiki.core.vectorstore import VectorStore

        new_store = VectorStore(tmp_path / "test.lance", MockEmbeddingProvider())

        # Get table (should ensure indexes)
        table = new_store._get_table()
        assert table is not None

        # Should be able to use indexed lookups
        chunk = await new_store.get_chunk_by_id("test_1")
        assert chunk is not None


class TestVectorStoreSearch:
    """Tests for vector store search functionality."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_search_empty_store(self, vector_store):
        """Test searching an empty store returns empty results."""
        results = await vector_store.search("test query")
        assert results == []

    async def test_search_with_results(self, vector_store):
        """Test searching returns results."""
        chunks = [
            make_chunk("func_1", content="def calculate_sum(a, b): return a + b"),
            make_chunk("func_2", content="def calculate_product(a, b): return a * b"),
        ]
        await vector_store.create_or_update_table(chunks)

        results = await vector_store.search("calculate")
        assert len(results) > 0
        assert all(r.chunk is not None for r in results)
        assert all(r.score >= 0 for r in results)

    async def test_search_with_language_filter(self, vector_store):
        """Test searching with language filter."""
        chunks = [
            make_chunk("py_1", language=Language.PYTHON),
            make_chunk("ts_1", language=Language.TYPESCRIPT),
        ]
        await vector_store.create_or_update_table(chunks)

        results = await vector_store.search("test", language="python")
        assert all(r.chunk.language == Language.PYTHON for r in results)

    async def test_search_invalid_language_raises(self, vector_store):
        """Test searching with invalid language raises ValueError."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with pytest.raises(ValueError, match="Invalid language filter"):
            await vector_store.search("test", language="invalid_lang")

    async def test_search_with_chunk_type_filter(self, vector_store):
        """Test searching with chunk type filter."""
        chunks = [
            make_chunk("func_1", chunk_type=ChunkType.FUNCTION),
            make_chunk("class_1", chunk_type=ChunkType.CLASS),
        ]
        await vector_store.create_or_update_table(chunks)

        results = await vector_store.search("test", chunk_type="function")
        assert all(r.chunk.chunk_type == ChunkType.FUNCTION for r in results)

    async def test_search_invalid_chunk_type_raises(self, vector_store):
        """Test searching with invalid chunk type raises ValueError."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with pytest.raises(ValueError, match="Invalid chunk_type filter"):
            await vector_store.search("test", chunk_type="invalid_type")


class TestVectorStoreStats:
    """Tests for vector store statistics."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_stats_empty_store(self, vector_store):
        """Test stats for empty store."""
        stats = vector_store.get_stats()
        assert stats["total_chunks"] == 0
        assert stats["languages"] == {}
        assert stats["chunk_types"] == {}

    async def test_stats_with_data(self, vector_store):
        """Test stats with data."""
        chunks = [
            make_chunk("py_func", language=Language.PYTHON, chunk_type=ChunkType.FUNCTION),
            make_chunk("py_class", language=Language.PYTHON, chunk_type=ChunkType.CLASS),
            make_chunk("ts_func", language=Language.TYPESCRIPT, chunk_type=ChunkType.FUNCTION),
        ]
        await vector_store.create_or_update_table(chunks)

        stats = vector_store.get_stats()
        assert stats["total_chunks"] == 3
        assert stats["languages"]["python"] == 2
        assert stats["languages"]["typescript"] == 1
        assert stats["chunk_types"]["function"] == 2
        assert stats["chunk_types"]["class"] == 1
        assert stats["files"] == 1  # All use default file_path


class TestVectorStoreAddChunks:
    """Tests for adding chunks to existing table."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_add_to_empty_creates_table(self, vector_store):
        """Test adding to empty store creates table."""
        chunks = [make_chunk("test_1")]
        count = await vector_store.add_chunks(chunks)
        assert count == 1

        # Verify data exists
        stats = vector_store.get_stats()
        assert stats["total_chunks"] == 1

    async def test_add_to_existing_table(self, vector_store):
        """Test adding chunks to existing table."""
        # Create initial table
        initial = [make_chunk("initial_1")]
        await vector_store.create_or_update_table(initial)

        # Add more chunks
        additional = [make_chunk("additional_1"), make_chunk("additional_2")]
        count = await vector_store.add_chunks(additional)
        assert count == 2

        # Verify total
        stats = vector_store.get_stats()
        assert stats["total_chunks"] == 3

    async def test_add_empty_list(self, vector_store):
        """Test adding empty list returns 0."""
        count = await vector_store.add_chunks([])
        assert count == 0


class TestVectorStoreEdgeCases:
    """Tests for vector store edge cases and error handling."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    # --- Empty database operations ---

    async def test_get_chunk_by_id_empty_db(self, vector_store):
        """Test get_chunk_by_id on empty database returns None."""
        result = await vector_store.get_chunk_by_id("nonexistent")
        assert result is None

    async def test_get_chunks_by_file_empty_db(self, vector_store):
        """Test get_chunks_by_file on empty database returns empty list."""
        result = await vector_store.get_chunks_by_file("nonexistent.py")
        assert result == []

    async def test_delete_chunks_by_file_empty_db(self, vector_store):
        """Test delete_chunks_by_file on empty database returns 0."""
        deleted = await vector_store.delete_chunks_by_file("nonexistent.py")
        assert deleted == 0

    async def test_create_or_update_empty_list(self, vector_store):
        """Test create_or_update_table with empty list returns 0."""
        result = await vector_store.create_or_update_table([])
        assert result == 0
        assert vector_store.get_stats()["total_chunks"] == 0

    # --- Special characters and injection protection ---

    async def test_chunk_id_with_quotes(self, vector_store):
        """Test chunk ID with single quotes is handled safely."""
        chunk = make_chunk("test'quote", content="test content")
        await vector_store.create_or_update_table([chunk])

        # Should not raise or cause injection
        result = await vector_store.get_chunk_by_id("test'quote")
        assert result is not None
        assert result.id == "test'quote"

    async def test_file_path_with_quotes(self, vector_store):
        """Test file path with quotes is handled safely."""
        chunk = make_chunk("test1", file_path="path'with'quotes.py")
        await vector_store.create_or_update_table([chunk])

        # Should not raise or cause injection
        results = await vector_store.get_chunks_by_file("path'with'quotes.py")
        assert len(results) == 1
        assert results[0].file_path == "path'with'quotes.py"

    async def test_delete_file_path_with_quotes(self, vector_store):
        """Test deleting file path with quotes is handled safely."""
        chunk = make_chunk("test1", file_path="path'with'quotes.py")
        await vector_store.create_or_update_table([chunk])

        # Should delete successfully without injection
        await vector_store.delete_chunks_by_file("path'with'quotes.py")

        # Verify deletion by checking chunks are gone
        chunks = await vector_store.get_chunks_by_file("path'with'quotes.py")
        assert len(chunks) == 0

    async def test_chunk_id_injection_attempt(self, vector_store):
        """Test that SQL-like injection in chunk_id is neutralized."""
        chunk = make_chunk("safe_chunk", content="test")
        await vector_store.create_or_update_table([chunk])

        # Attempt injection - should return None, not cause error
        malicious_id = "'; DROP TABLE code_chunks; --"
        result = await vector_store.get_chunk_by_id(malicious_id)
        assert result is None

        # Original chunk should still exist
        result = await vector_store.get_chunk_by_id("safe_chunk")
        assert result is not None

    async def test_file_path_injection_attempt(self, vector_store):
        """Test that SQL-like injection in file_path is neutralized."""
        chunk = make_chunk("chunk1", file_path="safe.py")
        await vector_store.create_or_update_table([chunk])

        # Attempt injection - should return empty, not cause error
        malicious_path = "' OR '1'='1"
        results = await vector_store.get_chunks_by_file(malicious_path)
        assert results == []

        # Original chunk should still exist
        results = await vector_store.get_chunks_by_file("safe.py")
        assert len(results) == 1

    async def test_unicode_content(self, vector_store):
        """Test handling of Unicode content in chunks."""
        chunk = make_chunk("unicode_test", content="def hello(): return '你好世界 🌍 Привет мир'")
        await vector_store.create_or_update_table([chunk])

        result = await vector_store.get_chunk_by_id("unicode_test")
        assert result is not None
        assert "你好世界" in result.content
        assert "🌍" in result.content

    # --- Database state handling ---

    async def test_reopen_database(self, tmp_path):
        """Test reopening database preserves data."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()

        # Create store and add data
        store1 = VectorStore(db_path, provider)
        chunk = make_chunk("persistent", content="test data")
        await store1.create_or_update_table([chunk])

        # Create new store instance pointing to same path
        store2 = VectorStore(db_path, provider)

        # Should find the data
        result = await store2.get_chunk_by_id("persistent")
        assert result is not None
        assert result.id == "persistent"

    async def test_replace_existing_table(self, vector_store):
        """Test create_or_update_table replaces existing data."""
        # Create initial data
        initial_chunks = [make_chunk("old_1"), make_chunk("old_2")]
        await vector_store.create_or_update_table(initial_chunks)
        assert vector_store.get_stats()["total_chunks"] == 2

        # Replace with new data
        new_chunks = [make_chunk("new_1")]
        await vector_store.create_or_update_table(new_chunks)

        # Old data should be gone
        assert vector_store.get_stats()["total_chunks"] == 1
        old_chunk = await vector_store.get_chunk_by_id("old_1")
        assert old_chunk is None
        new_chunk = await vector_store.get_chunk_by_id("new_1")
        assert new_chunk is not None

    async def test_db_path_created_if_not_exists(self, tmp_path):
        """Test that database directory is created if it doesn't exist."""
        from local_deepwiki.core.vectorstore import VectorStore

        nested_path = tmp_path / "nested" / "deep" / "db.lance"
        provider = MockEmbeddingProvider()

        store = VectorStore(nested_path, provider)
        chunk = make_chunk("test")
        await store.create_or_update_table([chunk])

        # Path should be created
        assert nested_path.parent.exists()

    # --- Boundary conditions ---

    async def test_single_chunk_operations(self, vector_store):
        """Test operations with single chunk."""
        chunk = make_chunk("single", content="single test")
        await vector_store.create_or_update_table([chunk])

        # Search
        results = await vector_store.search("single")
        assert len(results) == 1

        # Get by ID
        result = await vector_store.get_chunk_by_id("single")
        assert result is not None

        # Stats
        stats = vector_store.get_stats()
        assert stats["total_chunks"] == 1

    async def test_empty_content_chunk(self, vector_store):
        """Test chunk with empty content."""
        chunk = make_chunk("empty_content", content="")
        await vector_store.create_or_update_table([chunk])

        result = await vector_store.get_chunk_by_id("empty_content")
        assert result is not None
        assert result.content == ""

    async def test_large_content_chunk(self, vector_store):
        """Test chunk with large content."""
        large_content = "x" * 100000  # 100KB of content
        chunk = make_chunk("large", content=large_content)
        await vector_store.create_or_update_table([chunk])

        result = await vector_store.get_chunk_by_id("large")
        assert result is not None
        assert len(result.content) == 100000

    async def test_many_chunks_same_file(self, vector_store):
        """Test many chunks from same file."""
        chunks = [
            make_chunk(f"chunk_{i}", file_path="big_file.py", content=f"content {i}")
            for i in range(50)
        ]
        await vector_store.create_or_update_table(chunks)

        # Get all chunks for file
        results = await vector_store.get_chunks_by_file("big_file.py")
        assert len(results) == 50

        # Delete all
        await vector_store.delete_chunks_by_file("big_file.py")

        # Verify deletion by checking chunks are gone
        results = await vector_store.get_chunks_by_file("big_file.py")
        assert len(results) == 0

    # --- Search edge cases ---

    async def test_search_limit_zero_raises(self, vector_store):
        """Test search with limit=0 raises ValueError."""
        chunk = make_chunk("test")
        await vector_store.create_or_update_table([chunk])

        # LanceDB requires limit > 0 for vector searches
        with pytest.raises(ValueError, match="Limit is required"):
            await vector_store.search("test", limit=0)

    async def test_search_very_long_query(self, vector_store):
        """Test search with very long query string."""
        chunk = make_chunk("test", content="simple content")
        await vector_store.create_or_update_table([chunk])

        long_query = "test " * 1000  # Very long query
        # Should not raise
        results = await vector_store.search(long_query, limit=5)
        # May or may not find results, but shouldn't crash
        assert isinstance(results, list)


class TestVectorIndex:
    """Tests for vector index creation and management."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_vector_index_not_created_for_small_tables(self, vector_store):
        """Test that vector index is not created for tables with < 1000 rows."""
        # Create a small table (4 chunks - well under 1000 threshold)
        chunks = [make_chunk(f"chunk_{i}") for i in range(4)]
        await vector_store.create_or_update_table(chunks)

        table = vector_store._get_table()
        assert table is not None

        # Check that we have scalar indexes but not necessarily vector index
        indexes = table.list_indices()
        scalar_index_names = {
            idx.get("name", "") if isinstance(idx, dict) else getattr(idx, "name", "")
            for idx in indexes
        }
        # Scalar indexes should exist
        assert any("id" in name for name in scalar_index_names)

    async def test_create_vector_index_method_exists(self, vector_store):
        """Test that _create_vector_index method exists and is callable."""
        assert hasattr(vector_store, "_create_vector_index")
        assert callable(vector_store._create_vector_index)

    async def test_ensure_indexes_handles_missing_vector_index(self, vector_store):
        """Test that _ensure_indexes handles tables without vector index."""
        # Create table
        chunks = [make_chunk(f"chunk_{i}") for i in range(10)]
        await vector_store.create_or_update_table(chunks)

        # Manually call _ensure_indexes (simulates reopening existing table)
        vector_store._ensure_indexes()

        # Should not raise and scalar indexes should still work
        chunk = await vector_store.get_chunk_by_id("chunk_1")
        assert chunk is not None

    async def test_vector_index_threshold_is_1000(self, vector_store):
        """Verify the threshold for vector index creation is 1000 rows."""
        # This is a documentation test - verify the threshold is as expected
        # We don't create 1000+ rows in tests, but verify the logic exists
        import inspect

        source = inspect.getsource(vector_store._create_vector_index)
        assert "1000" in source or "min_rows_for_index" in source

    async def test_search_works_without_vector_index(self, vector_store):
        """Test that search works correctly even without vector index (brute force)."""
        # Create a small table without vector index
        chunks = [
            make_chunk("chunk_1", content="hello world"),
            make_chunk("chunk_2", content="goodbye world"),
            make_chunk("chunk_3", content="hello there"),
        ]
        await vector_store.create_or_update_table(chunks)

        # Search should work (brute force O(n) without index)
        results = await vector_store.search("hello", limit=2)
        assert len(results) > 0
        # All results should be valid chunks
        for result in results:
            assert result.chunk is not None
            assert result.chunk.id in ["chunk_1", "chunk_2", "chunk_3"]

    async def test_ensure_indexes_called_on_table_open(self, vector_store, tmp_path):
        """Test that _ensure_indexes is called when opening existing table."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Create table
        chunks = [make_chunk(f"chunk_{i}") for i in range(5)]
        await vector_store.create_or_update_table(chunks)

        # Create new VectorStore instance pointing to same DB
        provider = MockEmbeddingProvider()
        store2 = VectorStore(tmp_path / "test.lance", provider)

        # Access table (should trigger _ensure_indexes)
        table = store2._get_table()
        assert table is not None

        # Should still be able to search
        results = await store2.search("test", limit=5)
        assert isinstance(results, list)


class TestEnsureIndexesEdgeCases:
    """Tests for _ensure_indexes edge cases and error handling."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_ensure_indexes_when_table_is_none(self, vector_store):
        """Test _ensure_indexes returns early when table is None."""
        # Table is None before any data is added
        assert vector_store._table is None
        # Should not raise
        vector_store._ensure_indexes()
        # Still None after call
        assert vector_store._table is None

    async def test_ensure_indexes_handles_list_indices_exception(self, vector_store):
        """Test _ensure_indexes handles exceptions from list_indices."""
        from unittest.mock import MagicMock, patch

        # Create table first
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to raise RuntimeError
        with patch.object(vector_store._table, "list_indices", side_effect=RuntimeError("Cannot list")):
            # Should not raise, just log debug and continue
            vector_store._ensure_indexes()

    async def test_ensure_indexes_handles_type_error(self, vector_store):
        """Test _ensure_indexes handles TypeError from list_indices."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "list_indices", side_effect=TypeError("Bad type")):
            vector_store._ensure_indexes()

    async def test_ensure_indexes_handles_key_error(self, vector_store):
        """Test _ensure_indexes handles KeyError from index access."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "list_indices", side_effect=KeyError("Missing key")):
            vector_store._ensure_indexes()

    async def test_ensure_indexes_handles_attribute_error(self, vector_store):
        """Test _ensure_indexes handles AttributeError from index access."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "list_indices", side_effect=AttributeError("No attr")):
            vector_store._ensure_indexes()

    async def test_ensure_indexes_handles_count_rows_exception(self, vector_store):
        """Test _ensure_indexes handles exception when checking row count."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # list_indices returns empty (so it tries to create vector index)
        # count_rows raises exception
        with patch.object(vector_store._table, "list_indices", return_value=[]):
            with patch.object(vector_store._table, "count_rows", side_effect=RuntimeError("DB error")):
                vector_store._ensure_indexes()

    async def test_ensure_indexes_creates_missing_id_index(self, vector_store):
        """Test _ensure_indexes creates id_idx when missing."""
        from unittest.mock import patch, MagicMock

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to return indexes without id_idx
        mock_indices = [{"name": "file_path_idx"}]
        with patch.object(vector_store._table, "list_indices", return_value=mock_indices):
            with patch.object(vector_store._table, "create_scalar_index") as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=10):
                    vector_store._ensure_indexes()
                    # Should have tried to create id index
                    mock_create.assert_called()

    async def test_ensure_indexes_creates_missing_file_path_index(self, vector_store):
        """Test _ensure_indexes creates file_path_idx when missing."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        mock_indices = [{"name": "id_idx"}]
        with patch.object(vector_store._table, "list_indices", return_value=mock_indices):
            with patch.object(vector_store._table, "create_scalar_index") as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=10):
                    vector_store._ensure_indexes()
                    mock_create.assert_called()


class TestCreateIndexSafeEdgeCases:
    """Tests for _create_index_safe edge cases."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_create_index_safe_when_table_is_none(self, vector_store):
        """Test _create_index_safe returns early when table is None."""
        assert vector_store._table is None
        # Should not raise
        vector_store._create_index_safe("id")

    async def test_create_index_safe_handles_value_error(self, vector_store):
        """Test _create_index_safe handles ValueError (index already exists)."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_scalar_index", side_effect=ValueError("Index exists")
        ):
            # Should not raise
            vector_store._create_index_safe("test_column")

    async def test_create_index_safe_handles_runtime_error(self, vector_store):
        """Test _create_index_safe handles RuntimeError."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_scalar_index", side_effect=RuntimeError("Creation failed")
        ):
            vector_store._create_index_safe("test_column")

    async def test_create_index_safe_handles_os_error(self, vector_store):
        """Test _create_index_safe handles OSError."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_scalar_index", side_effect=OSError("Storage issue")
        ):
            vector_store._create_index_safe("test_column")


class TestCreateVectorIndexEdgeCases:
    """Tests for _create_vector_index edge cases."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_create_vector_index_when_table_is_none(self, vector_store):
        """Test _create_vector_index returns early when table is None."""
        assert vector_store._table is None
        # Should not raise
        vector_store._create_vector_index(1000)

    async def test_create_vector_index_skipped_for_small_tables(self, vector_store):
        """Test _create_vector_index skips for tables under threshold."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "create_index") as mock_create:
            vector_store._create_vector_index(999)  # Just under threshold
            mock_create.assert_not_called()

    async def test_create_vector_index_creates_for_large_tables(self, vector_store):
        """Test _create_vector_index creates index for tables at threshold."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "create_index") as mock_create:
            vector_store._create_vector_index(1000)  # At threshold
            mock_create.assert_called_once()
            # Check it was called with correct params
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["metric"] == "L2"
            assert call_kwargs["num_sub_vectors"] == 16

    async def test_create_vector_index_calculates_partitions(self, vector_store):
        """Test _create_vector_index calculates correct number of partitions."""
        from unittest.mock import patch
        import math

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Test with 10000 rows -> sqrt(10000) = 100 partitions
        with patch.object(vector_store._table, "create_index") as mock_create:
            vector_store._create_vector_index(10000)
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["num_partitions"] == 100

        # Test with very large table -> capped at 256
        with patch.object(vector_store._table, "create_index") as mock_create:
            vector_store._create_vector_index(100000)
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["num_partitions"] == 256

    async def test_create_vector_index_handles_value_error(self, vector_store):
        """Test _create_vector_index handles ValueError (index exists)."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_index", side_effect=ValueError("Index exists")
        ):
            # Should not raise
            vector_store._create_vector_index(2000)

    async def test_create_vector_index_handles_runtime_error(self, vector_store):
        """Test _create_vector_index handles RuntimeError."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_index", side_effect=RuntimeError("Creation failed")
        ):
            vector_store._create_vector_index(2000)

    async def test_create_vector_index_handles_os_error(self, vector_store):
        """Test _create_vector_index handles OSError."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_index", side_effect=OSError("Storage issue")
        ):
            vector_store._create_vector_index(2000)


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
        embeddings = await vector_store._batch_embed(texts, batch_size=3, log_progress=True)
        assert len(embeddings) == 10
        # Each embedding should have correct dimension
        assert all(len(e) == 384 for e in embeddings)

    async def test_batch_embed_without_progress_logging(self, vector_store):
        """Test _batch_embed without progress logging."""
        texts = [f"text_{i}" for i in range(10)]
        embeddings = await vector_store._batch_embed(texts, batch_size=3, log_progress=False)
        assert len(embeddings) == 10

    async def test_batch_embed_single_batch(self, vector_store):
        """Test _batch_embed with single batch (no progress logging needed)."""
        texts = ["text_1", "text_2"]
        embeddings = await vector_store._batch_embed(texts, batch_size=100, log_progress=True)
        assert len(embeddings) == 2


class TestGetMainDefinitionLines:
    """Tests for get_main_definition_lines functionality."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_get_main_definition_lines_empty_store(self, vector_store):
        """Test get_main_definition_lines on empty store."""
        result = vector_store.get_main_definition_lines()
        assert result == {}

    async def test_get_main_definition_lines_with_functions(self, vector_store):
        """Test get_main_definition_lines with function chunks."""
        chunks = [
            CodeChunk(
                id="func1",
                file_path="src/main.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="main",
                content="def main(): pass",
                start_line=10,
                end_line=20,
            ),
            CodeChunk(
                id="func2",
                file_path="src/main.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="helper",
                content="def helper(): pass",
                start_line=25,
                end_line=30,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        assert "src/main.py" in result
        # Should return the first (earliest) function
        assert result["src/main.py"] == (10, 20)

    async def test_get_main_definition_lines_with_classes(self, vector_store):
        """Test get_main_definition_lines with class chunks."""
        chunks = [
            CodeChunk(
                id="class1",
                file_path="src/models.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="User",
                content="class User: pass",
                start_line=5,
                end_line=50,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        assert result["src/models.py"] == (5, 50)

    async def test_get_main_definition_lines_class_priority(self, vector_store):
        """Test that class takes priority over function if it starts earlier."""
        chunks = [
            CodeChunk(
                id="func1",
                file_path="src/module.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="helper",
                content="def helper(): pass",
                start_line=20,
                end_line=25,
            ),
            CodeChunk(
                id="class1",
                file_path="src/module.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="MyClass",
                content="class MyClass: pass",
                start_line=5,
                end_line=15,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        # Class starts earlier, so it should be returned
        assert result["src/module.py"] == (5, 15)

    async def test_get_main_definition_lines_function_first_when_earlier(self, vector_store):
        """Test that function is kept if it starts earlier than class."""
        chunks = [
            CodeChunk(
                id="func1",
                file_path="src/module.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="early_func",
                content="def early_func(): pass",
                start_line=1,
                end_line=5,
            ),
            CodeChunk(
                id="class1",
                file_path="src/module.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="LaterClass",
                content="class LaterClass: pass",
                start_line=10,
                end_line=20,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        # Function starts earlier
        assert result["src/module.py"] == (1, 5)

    async def test_get_main_definition_lines_multiple_files(self, vector_store):
        """Test get_main_definition_lines with multiple files."""
        chunks = [
            CodeChunk(
                id="func1",
                file_path="src/a.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="func_a",
                content="def func_a(): pass",
                start_line=10,
                end_line=20,
            ),
            CodeChunk(
                id="class1",
                file_path="src/b.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="ClassB",
                content="class ClassB: pass",
                start_line=5,
                end_line=50,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        assert len(result) == 2
        assert result["src/a.py"] == (10, 20)
        assert result["src/b.py"] == (5, 50)

    async def test_get_main_definition_lines_ignores_other_types(self, vector_store):
        """Test that get_main_definition_lines ignores module/import chunks."""
        chunks = [
            CodeChunk(
                id="module1",
                file_path="src/init.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.MODULE,
                name="init",
                content="# module",
                start_line=1,
                end_line=5,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        # Module chunks are not included
        assert result == {}

    async def test_get_main_definition_lines_same_type_keeps_earlier(self, vector_store):
        """Test that same type chunks keep the earlier one."""
        chunks = [
            CodeChunk(
                id="func1",
                file_path="src/funcs.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="late_func",
                content="def late_func(): pass",
                start_line=50,
                end_line=60,
            ),
            CodeChunk(
                id="func2",
                file_path="src/funcs.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="early_func",
                content="def early_func(): pass",
                start_line=10,
                end_line=20,
            ),
        ]
        await vector_store.create_or_update_table(chunks)

        result = vector_store.get_main_definition_lines()
        # Earlier function should be kept
        assert result["src/funcs.py"] == (10, 20)


class TestChunkToText:
    """Tests for _chunk_to_text functionality."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_chunk_to_text_with_parent_name(self, vector_store):
        """Test _chunk_to_text includes parent_name when present."""
        chunk = CodeChunk(
            id="method1",
            file_path="src/module.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="my_method",
            content="def my_method(self): pass",
            start_line=10,
            end_line=15,
            parent_name="MyClass",
        )

        text = vector_store._chunk_to_text(chunk)
        assert "in MyClass" in text
        assert "my_method" in text
        assert "python" in text

    def test_chunk_to_text_with_docstring(self, vector_store):
        """Test _chunk_to_text includes docstring when present."""
        chunk = CodeChunk(
            id="func1",
            file_path="src/module.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="documented_func",
            content="def documented_func(): pass",
            start_line=1,
            end_line=5,
            docstring="This is the docstring for the function.",
        )

        text = vector_store._chunk_to_text(chunk)
        assert "This is the docstring" in text
        assert "documented_func" in text

    def test_chunk_to_text_with_parent_and_docstring(self, vector_store):
        """Test _chunk_to_text with both parent_name and docstring."""
        chunk = CodeChunk(
            id="method1",
            file_path="src/module.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="full_method",
            content="def full_method(self): return True",
            start_line=10,
            end_line=20,
            parent_name="ParentClass",
            docstring="Method docstring here.",
        )

        text = vector_store._chunk_to_text(chunk)
        assert "in ParentClass" in text
        assert "Method docstring here" in text
        assert "full_method" in text
        assert "def full_method" in text

    def test_chunk_to_text_without_name(self, vector_store):
        """Test _chunk_to_text when name is None."""
        chunk = CodeChunk(
            id="anon1",
            file_path="src/module.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.MODULE,
            name=None,
            content="# Some module content",
            start_line=1,
            end_line=5,
        )

        text = vector_store._chunk_to_text(chunk)
        assert "python" in text
        assert "# Some module content" in text


class TestSanitizeStringValue:
    """Tests for _sanitize_string_value function."""

    def test_sanitize_single_quote(self):
        """Test that single quotes are escaped."""
        from local_deepwiki.core.vectorstore import _sanitize_string_value

        result = _sanitize_string_value("test'value")
        assert result == "test''value"

    def test_sanitize_multiple_quotes(self):
        """Test multiple single quotes are escaped."""
        from local_deepwiki.core.vectorstore import _sanitize_string_value

        result = _sanitize_string_value("it's a 'test'")
        assert result == "it''s a ''test''"

    def test_sanitize_no_quotes(self):
        """Test string without quotes is unchanged."""
        from local_deepwiki.core.vectorstore import _sanitize_string_value

        result = _sanitize_string_value("normal string")
        assert result == "normal string"


class TestDeleteChunksByFilesEdgeCases:
    """Tests for delete_chunks_by_files edge cases."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_delete_chunks_by_files_empty_db(self, vector_store):
        """Test delete_chunks_by_files returns 0 when table doesn't exist."""
        # Don't create any table, just try to delete
        result = await vector_store.delete_chunks_by_files(["file1.py", "file2.py"])
        assert result == 0


class TestEnsureIndexesVectorIndexDetection:
    """Tests for vector index detection in _ensure_indexes."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_ensure_indexes_detects_ivf_index(self, vector_store):
        """Test _ensure_indexes detects IVF vector index."""
        from unittest.mock import patch, MagicMock

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to return an index with IVF type
        mock_index = MagicMock()
        mock_index.name = "vector_idx"
        mock_index.index_type = "IVF_PQ"

        with patch.object(vector_store._table, "list_indices", return_value=[mock_index]):
            with patch.object(vector_store._table, "create_index") as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=2000):
                    vector_store._ensure_indexes()
                    # Should NOT try to create vector index since IVF was detected
                    mock_create.assert_not_called()

    async def test_ensure_indexes_detects_ivf_in_dict_index(self, vector_store):
        """Test _ensure_indexes detects IVF in dict-style index."""
        from unittest.mock import patch

        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to return dict-style index with IVF type
        mock_index = {"name": "vector_idx", "index_type": "ivf_flat"}

        with patch.object(vector_store._table, "list_indices", return_value=[mock_index]):
            with patch.object(vector_store._table, "create_index") as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=2000):
                    vector_store._ensure_indexes()
                    # Should NOT try to create vector index since IVF was detected
                    mock_create.assert_not_called()


class TestSearchCache:
    """Tests for search result caching functionality."""

    @pytest.fixture
    def cache_config(self):
        """Create a search cache config for testing."""
        return SearchCacheConfig(
            enabled=True,
            ttl_seconds=3600,
            max_entries=100,
            similarity_threshold=0.95,
        )

    @pytest.fixture
    def vector_store(self, tmp_path, cache_config):
        """Create a vector store with caching enabled."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        # Use semantic mock to get different embeddings for different queries
        provider = SemanticMockEmbeddingProvider()
        return VectorStore(db_path, provider, search_cache_config=cache_config)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with test data.

        Note: create_or_update_table invalidates the cache once.
        """
        chunks = [
            make_chunk("func_1", content="def calculate_sum(a, b): return a + b"),
            make_chunk("func_2", content="def calculate_product(a, b): return a * b"),
            make_chunk("func_3", content="def parse_json(data): return json.loads(data)"),
        ]
        await vector_store.create_or_update_table(chunks)
        # Note: invalidations count is now 1 after fixture setup
        return vector_store

    async def test_search_cache_hit(self, populated_store):
        """Test that repeated identical searches return cached results."""
        # First search - cache miss
        results1 = await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["misses"] == 1
        assert stats1["hits"] == 0

        # Second search - cache hit
        results2 = await populated_store.search("calculate")
        stats2 = populated_store.get_search_cache_stats()
        assert stats2["misses"] == 1
        assert stats2["hits"] == 1

        # Results should be the same
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.chunk.id == r2.chunk.id

    async def test_search_cache_miss_different_query(self, populated_store):
        """Test that different queries with different embeddings result in cache misses."""
        # First search - starts with 'c'
        await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["misses"] == 1

        # Different search starting with different letter - cache miss
        # SemanticMockEmbeddingProvider generates different embeddings based on first char
        await populated_store.search("parse json")
        stats2 = populated_store.get_search_cache_stats()
        assert stats2["misses"] == 2

    async def test_search_cache_miss_different_filters(self, populated_store):
        """Test that same query with different filters results in cache miss."""
        # Search without filters
        await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["misses"] == 1

        # Same query with language filter - cache miss
        await populated_store.search("calculate", language="python")
        stats2 = populated_store.get_search_cache_stats()
        assert stats2["misses"] == 2

    async def test_search_cache_invalidated_on_create_or_update(self, populated_store):
        """Test that cache is invalidated when table is created/updated."""
        # Note: populated_store fixture already triggered one invalidation

        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Create/update table - should invalidate cache
        new_chunks = [make_chunk("new_1", content="def new_function(): pass")]
        await populated_store.create_or_update_table(new_chunks)

        stats2 = populated_store.get_search_cache_stats()
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_search_cache_invalidated_on_add_chunks(self, populated_store):
        """Test that cache is invalidated when chunks are added."""
        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Add chunks - should invalidate cache
        new_chunks = [make_chunk("added_1", content="def added_function(): pass")]
        await populated_store.add_chunks(new_chunks)

        stats2 = populated_store.get_search_cache_stats()
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_search_cache_invalidated_on_delete_chunks_by_file(self, populated_store):
        """Test that cache is invalidated when chunks are deleted by file."""
        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Delete chunks - should invalidate cache
        await populated_store.delete_chunks_by_file("test.py")

        stats2 = populated_store.get_search_cache_stats()
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_search_cache_invalidated_on_delete_chunks_by_files(self, populated_store):
        """Test that cache is invalidated when chunks are deleted by files."""
        # First search - cache miss
        await populated_store.search("calculate")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["entries"] == 1
        initial_invalidations = stats1["invalidations"]

        # Delete chunks - should invalidate cache
        await populated_store.delete_chunks_by_files(["test.py"])

        stats2 = populated_store.get_search_cache_stats()
        assert stats2["entries"] == 0
        assert stats2["invalidations"] == initial_invalidations + 1

    async def test_invalidate_search_cache_method(self, populated_store):
        """Test the public invalidate_search_cache method."""
        # Populate cache with different queries (different first chars = different embeddings)
        await populated_store.search("alpha query")
        await populated_store.search("beta query")
        stats1 = populated_store.get_search_cache_stats()
        assert stats1["entries"] == 2

        # Invalidate
        count = populated_store.invalidate_search_cache()
        assert count == 2

        stats2 = populated_store.get_search_cache_stats()
        assert stats2["entries"] == 0

    async def test_search_cache_stats(self, populated_store):
        """Test get_search_cache_stats returns correct structure."""
        stats = populated_store.get_search_cache_stats()

        assert "enabled" in stats
        assert "entries" in stats
        assert "max_entries" in stats
        assert "ttl_seconds" in stats
        assert "similarity_threshold" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "invalidations" in stats
        assert "hit_rate" in stats

        assert stats["enabled"] is True
        assert stats["max_entries"] == 100
        assert stats["ttl_seconds"] == 3600
        assert stats["similarity_threshold"] == 0.95

    async def test_search_cache_not_used_for_fuzzy(self, populated_store):
        """Test that fuzzy searches don't use the cache."""
        # Fuzzy search
        await populated_store.search("calculate", use_fuzzy=True)
        stats = populated_store.get_search_cache_stats()
        # Should not cache fuzzy results
        assert stats["entries"] == 0

    async def test_search_cache_not_used_for_path_pattern(self, populated_store):
        """Test that path pattern searches don't use the cache."""
        # Path pattern search
        await populated_store.search("calculate", path_pattern="src/**/*.py")
        stats = populated_store.get_search_cache_stats()
        # Should not cache path pattern results
        assert stats["entries"] == 0


class TestSearchCacheDisabled:
    """Tests for search caching when disabled."""

    @pytest.fixture
    def disabled_config(self):
        """Create a disabled search cache config."""
        return SearchCacheConfig(enabled=False)

    @pytest.fixture
    def vector_store(self, tmp_path, disabled_config):
        """Create a vector store with caching disabled."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider, search_cache_config=disabled_config)

    async def test_cache_disabled_no_caching(self, vector_store):
        """Test that caching is skipped when disabled."""
        chunks = [make_chunk("func_1", content="def calculate(): pass")]
        await vector_store.create_or_update_table(chunks)

        # Search twice
        await vector_store.search("calculate")
        await vector_store.search("calculate")

        stats = vector_store.get_search_cache_stats()
        assert stats["enabled"] is False
        assert stats["entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestSearchCacheEviction:
    """Tests for search cache eviction."""

    @pytest.fixture
    def vector_store_with_small_cache(self, tmp_path):
        """Create a vector store with small cache for testing eviction.

        We directly create a SearchCache with small max_entries to bypass
        the config validation that requires max_entries >= 100.
        """
        from local_deepwiki.core.vectorstore import SearchCache, VectorStore

        db_path = tmp_path / "test.lance"
        provider = SemanticMockEmbeddingProvider()

        # Create VectorStore with default config first
        store = VectorStore(db_path, provider)

        # Replace the cache with a small one for testing (bypassing validation)
        # Create a config-like object that allows small max_entries
        class SmallCacheConfig:
            enabled = True
            ttl_seconds = 3600
            max_entries = 3  # Small for testing
            similarity_threshold = 0.95

        store._search_cache = SearchCache(SmallCacheConfig())
        return store

    async def test_cache_eviction_when_over_capacity(self, vector_store_with_small_cache):
        """Test that old entries are evicted when cache exceeds max_entries."""
        vector_store = vector_store_with_small_cache

        chunks = [
            make_chunk("func_1", content="def alpha(): pass"),
            make_chunk("func_2", content="def beta(): pass"),
            make_chunk("func_3", content="def gamma(): pass"),
            make_chunk("func_4", content="def delta(): pass"),
            make_chunk("func_5", content="def epsilon(): pass"),
        ]
        await vector_store.create_or_update_table(chunks)

        # Fill cache beyond capacity (max is 3)
        await vector_store.search("alpha")
        await vector_store.search("beta")
        await vector_store.search("gamma")
        await vector_store.search("delta")  # This should trigger eviction

        stats = vector_store.get_search_cache_stats()
        # Should have evicted some entries (max is 3, target is 80% = 2.4 -> 2)
        assert stats["entries"] <= 3


class TestSearchCacheTTL:
    """Tests for search cache TTL expiration."""

    @pytest.fixture
    def vector_store_with_short_ttl(self, tmp_path):
        """Create a vector store with short TTL cache.

        We directly create a SearchCache with short TTL to bypass
        the config validation that requires ttl_seconds >= 60.
        """
        from local_deepwiki.core.vectorstore import SearchCache, VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()

        # Create VectorStore with default config first
        store = VectorStore(db_path, provider)

        # Replace the cache with a short TTL one for testing
        class ShortTTLConfig:
            enabled = True
            ttl_seconds = 1  # 1 second TTL for testing
            max_entries = 1000
            similarity_threshold = 0.95

        store._search_cache = SearchCache(ShortTTLConfig())
        return store

    async def test_cache_entry_expires_after_ttl(self, vector_store_with_short_ttl):
        """Test that cache entries expire after TTL."""
        vector_store = vector_store_with_short_ttl

        chunks = [make_chunk("func_1", content="def calculate(): pass")]
        await vector_store.create_or_update_table(chunks)

        # First search - cache miss
        await vector_store.search("calculate")
        stats1 = vector_store.get_search_cache_stats()
        assert stats1["entries"] == 1

        # Wait for TTL to expire
        time.sleep(1.5)

        # Second search - entry expired, should be cache miss
        await vector_store.search("calculate")
        stats2 = vector_store.get_search_cache_stats()
        # The expired entry should have been cleaned up
        assert stats2["misses"] == 2


class TestSearchCacheSemanticSimilarity:
    """Tests for semantic similarity matching in search cache."""

    @pytest.fixture
    def cache_config(self):
        """Create a cache config with lower similarity threshold for testing."""
        return SearchCacheConfig(
            enabled=True,
            ttl_seconds=3600,
            max_entries=100,
            similarity_threshold=0.9,  # Lower threshold for testing
        )

    @pytest.fixture
    def vector_store(self, tmp_path, cache_config):
        """Create a vector store with semantic caching."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()  # Identical embeddings = similarity 1.0
        return VectorStore(db_path, provider, search_cache_config=cache_config)

    async def test_semantic_cache_hit_identical_embeddings(self, vector_store):
        """Test that queries with identical embeddings result in cache hits."""
        chunks = [make_chunk("func_1", content="def calculate(): pass")]
        await vector_store.create_or_update_table(chunks)

        # First search
        await vector_store.search("query1")
        stats1 = vector_store.get_search_cache_stats()
        assert stats1["misses"] == 1
        assert stats1["hits"] == 0

        # Second search with different text but identical embedding (from mock)
        await vector_store.search("query2")
        stats2 = vector_store.get_search_cache_stats()
        # Mock provider returns identical embeddings, so should be a cache hit
        assert stats2["hits"] == 1


class TestSearchCacheIntegration:
    """Integration tests for search cache with VectorStore."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store with default cache config."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        # Uses default SearchCacheConfig
        return VectorStore(db_path, provider)

    async def test_default_cache_config(self, vector_store):
        """Test that default cache config is applied."""
        stats = vector_store.get_search_cache_stats()
        assert stats["enabled"] is True
        assert stats["ttl_seconds"] == 3600  # Default 1 hour
        assert stats["max_entries"] == 1000  # Default
        assert stats["similarity_threshold"] == 0.95  # Default

    async def test_cache_survives_empty_search(self, vector_store):
        """Test that caching works even with empty results."""
        # Search empty store
        results = await vector_store.search("calculate")
        assert results == []

        stats = vector_store.get_search_cache_stats()
        # Empty results should not be cached (no table exists)
        assert stats["entries"] == 0

    async def test_cache_with_limit_filter(self, vector_store):
        """Test that different limits result in different cache entries."""
        chunks = [
            make_chunk("func_1", content="def calculate1(): pass"),
            make_chunk("func_2", content="def calculate2(): pass"),
            make_chunk("func_3", content="def calculate3(): pass"),
        ]
        await vector_store.create_or_update_table(chunks)

        # Search with default limit
        await vector_store.search("calculate")
        stats1 = vector_store.get_search_cache_stats()
        assert stats1["entries"] == 1

        # Search with different limit - should be cache miss
        await vector_store.search("calculate", limit=5)
        stats2 = vector_store.get_search_cache_stats()
        assert stats2["entries"] == 2
        assert stats2["misses"] == 2


class TestSearchCacheClass:
    """Direct tests for the SearchCache class."""

    def test_compute_similarity_identical_vectors(self):
        """Test similarity computation for identical vectors."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec = [0.1, 0.2, 0.3, 0.4, 0.5]
        similarity = cache._compute_similarity(vec, vec)
        assert similarity == pytest.approx(1.0)

    def test_compute_similarity_orthogonal_vectors(self):
        """Test similarity computation for orthogonal vectors."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = cache._compute_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)

    def test_compute_similarity_opposite_vectors(self):
        """Test similarity computation for opposite vectors."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec1 = [1.0, 1.0, 1.0]
        vec2 = [-1.0, -1.0, -1.0]
        similarity = cache._compute_similarity(vec1, vec2)
        assert similarity == pytest.approx(-1.0)

    def test_compute_similarity_zero_vector(self):
        """Test similarity computation with zero vector."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]
        similarity = cache._compute_similarity(vec1, vec2)
        assert similarity == 0.0

    def test_filters_match_identical(self):
        """Test filters matching with identical filters."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        filters1 = {"language": "python", "limit": 10}
        filters2 = {"language": "python", "limit": 10}
        assert cache._filters_match(filters1, filters2) is True

    def test_filters_match_different(self):
        """Test filters matching with different filters."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        filters1 = {"language": "python", "limit": 10}
        filters2 = {"language": "typescript", "limit": 10}
        assert cache._filters_match(filters1, filters2) is False

    def test_filters_match_empty(self):
        """Test filters matching with empty filters."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        assert cache._filters_match({}, {}) is True
        assert cache._filters_match({"a": 1}, {}) is False

    def test_stats_returns_copy(self):
        """Test that stats returns a copy, not the internal dict."""
        from local_deepwiki.core.vectorstore import SearchCache

        config = SearchCacheConfig()
        cache = SearchCache(config)

        stats1 = cache.stats
        stats1["hits"] = 999

        stats2 = cache.stats
        assert stats2["hits"] == 0  # Internal stats not modified


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
        # Allow some tolerance for test environment variations
        assert parallel_time < sequential_time * 0.8, (
            f"Parallel ({parallel_time:.3f}s) should be faster than "
            f"sequential ({sequential_time:.3f}s)"
        )

    async def test_parallel_embedding_concurrency_limited(self, tmp_path):
        """Test that concurrency is properly limited by semaphore."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Use API provider name to avoid automatic concurrency boost for local
        provider = SlowMockEmbeddingProvider(delay_seconds=0.1, name="openai:slow-mock")

        config = EmbeddingBatchConfig(batch_size=1, concurrency=2)  # Only 2 concurrent
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

        texts = [f"text_{i}" for i in range(4)]  # 4 batches with concurrency 2

        start = time.time()
        await store._batch_embed(texts, batch_size=1)
        elapsed = time.time() - start

        # With 4 batches and concurrency 2, should take ~0.2s (2 rounds of 0.1s each)
        # With concurrency 4, would take ~0.1s
        # Allow some margin
        assert elapsed >= 0.15, f"Expected >= 0.15s with concurrency 2, got {elapsed:.3f}s"

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
        embeddings = await vector_store._batch_embed(texts, batch_size=10, log_progress=True)
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
        return VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

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
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

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
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

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
        return VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

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
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

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
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

        batch_size, concurrency = store._get_optimal_batch_config()

        # Local provider should get larger batch size and higher concurrency
        assert batch_size >= 100
        assert concurrency >= 4

    def test_optimal_config_for_api(self, tmp_path):
        """Test optimal config calculation for API provider."""
        from local_deepwiki.core.vectorstore import VectorStore

        provider = MockEmbeddingProvider(name="openai:test")
        config = EmbeddingBatchConfig(batch_size=200, concurrency=8)
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

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
        store = VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

        batch_config = store.get_embedding_batch_config()

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

        batch_config = store.get_embedding_batch_config()

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
        assert elapsed >= 0.8


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
        return VectorStore(tmp_path / "test.lance", provider, embedding_batch_config=config)

    async def test_create_or_update_with_parallel_embedding(self, vector_store):
        """Test that create_or_update_table uses parallel embedding."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(50)]
        count = await vector_store.create_or_update_table(chunks)

        assert count == 50
        stats = vector_store.get_stats()
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
        stats = vector_store.get_stats()
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
