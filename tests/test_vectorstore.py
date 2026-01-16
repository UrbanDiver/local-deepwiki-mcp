"""Tests for vector store functionality."""

import pytest

from local_deepwiki.models import ChunkType, CodeChunk, Language
from local_deepwiki.providers.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384):
        self._dimension = dimension
        self.embed_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        """Return provider name."""
        return "mock"

    def get_dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings."""
        self.embed_calls.append(texts)
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
        # Delete chunks for main.py
        deleted = await populated_store.delete_chunks_by_file("src/main.py")
        assert deleted == 2

        # Verify deletion
        chunks = await populated_store.get_chunks_by_file("src/main.py")
        assert len(chunks) == 0

        # Other files unaffected
        chunks = await populated_store.get_chunks_by_file("src/utils.py")
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
        deleted = await vector_store.delete_chunks_by_file("path'with'quotes.py")
        assert deleted == 1

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
        deleted = await vector_store.delete_chunks_by_file("big_file.py")
        assert deleted == 50

        # Verify deletion
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
