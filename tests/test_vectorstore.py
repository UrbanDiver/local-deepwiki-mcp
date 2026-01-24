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
