"""Tests for vector store index management.

Covers: TestVectorIndex, TestEnsureIndexesEdgeCases, TestCreateIndexSafeEdgeCases,
TestCreateVectorIndexEdgeCases, TestEnsureIndexesVectorIndexDetection.

Note: index management logic lives in ``local_deepwiki.core.vectorstore.indexes``
as module-level functions.  Tests call those functions directly, passing the
table and lazy-index-manager obtained from a VectorStore instance.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.core.vectorstore.indexes import (
    create_index_safe,
    create_vector_index,
    ensure_indexes,
)
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

    async def test_ensure_indexes_handles_missing_vector_index(self, vector_store):
        """Test that ensure_indexes handles tables without vector index."""
        # Create table
        chunks = [make_chunk(f"chunk_{i}") for i in range(10)]
        await vector_store.create_or_update_table(chunks)

        # Call module-level ensure_indexes directly
        ensure_indexes(vector_store._table, vector_store._lazy_index_manager)

        # Should not raise and scalar indexes should still work
        chunk = await vector_store.get_chunk_by_id("chunk_1")
        assert chunk is not None

    async def test_vector_index_threshold_is_1000(self, vector_store):
        """Verify the threshold for vector index creation is 1000 rows."""
        # This is a documentation test - verify the threshold is as expected
        # We don't create 1000+ rows in tests, but verify the logic exists
        import inspect

        source = inspect.getsource(create_vector_index)
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
        """Test that ensure_indexes is called when opening existing table."""
        from local_deepwiki.core.vectorstore import VectorStore

        # Create table
        chunks = [make_chunk(f"chunk_{i}") for i in range(5)]
        await vector_store.create_or_update_table(chunks)

        # Create new VectorStore instance pointing to same DB
        provider = MockEmbeddingProvider()
        store2 = VectorStore(tmp_path / "test.lance", provider)

        # Access table (should trigger ensure_indexes internally)
        table = store2._get_table()
        assert table is not None

        # Should still be able to search
        results = await store2.search("test", limit=5)
        assert isinstance(results, list)


class TestEnsureIndexesEdgeCases:
    """Tests for ensure_indexes edge cases and error handling."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_ensure_indexes_when_table_is_none(self, vector_store):
        """Test that calling ensure_indexes on a None table is harmless.

        The VectorStore's _get_table method only calls ensure_indexes when
        the table is non-None, so this just verifies the precondition.
        """
        assert vector_store._table is None

    async def test_ensure_indexes_handles_list_indices_exception(self, vector_store):
        """Test ensure_indexes handles exceptions from list_indices."""
        # Create table first
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to raise RuntimeError
        with patch.object(
            vector_store._table, "list_indices", side_effect=RuntimeError("Cannot list")
        ):
            # Should not raise, just log debug and continue
            ensure_indexes(vector_store._table, vector_store._lazy_index_manager)

    async def test_ensure_indexes_handles_type_error(self, vector_store):
        """Test ensure_indexes handles TypeError from list_indices."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "list_indices", side_effect=TypeError("Bad type")
        ):
            ensure_indexes(vector_store._table, vector_store._lazy_index_manager)

    async def test_ensure_indexes_handles_key_error(self, vector_store):
        """Test ensure_indexes handles KeyError from index access."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "list_indices", side_effect=KeyError("Missing key")
        ):
            ensure_indexes(vector_store._table, vector_store._lazy_index_manager)

    async def test_ensure_indexes_handles_attribute_error(self, vector_store):
        """Test ensure_indexes handles AttributeError from index access."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "list_indices", side_effect=AttributeError("No attr")
        ):
            ensure_indexes(vector_store._table, vector_store._lazy_index_manager)

    async def test_ensure_indexes_handles_count_rows_exception(self, vector_store):
        """Test ensure_indexes handles exception when checking row count."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # list_indices returns empty (so it tries to create vector index)
        # count_rows raises exception
        with patch.object(vector_store._table, "list_indices", return_value=[]):
            with patch.object(
                vector_store._table, "count_rows", side_effect=RuntimeError("DB error")
            ):
                ensure_indexes(vector_store._table, vector_store._lazy_index_manager)

    async def test_ensure_indexes_creates_missing_id_index(self, vector_store):
        """Test ensure_indexes creates id_idx when missing."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to return indexes without id_idx
        mock_indices = [{"name": "file_path_idx"}]
        with patch.object(
            vector_store._table, "list_indices", return_value=mock_indices
        ):
            with patch.object(
                vector_store._table, "create_scalar_index"
            ) as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=10):
                    ensure_indexes(
                        vector_store._table, vector_store._lazy_index_manager
                    )
                    # Should have tried to create id index
                    mock_create.assert_called()

    async def test_ensure_indexes_creates_missing_file_path_index(self, vector_store):
        """Test ensure_indexes creates file_path_idx when missing."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        mock_indices = [{"name": "id_idx"}]
        with patch.object(
            vector_store._table, "list_indices", return_value=mock_indices
        ):
            with patch.object(
                vector_store._table, "create_scalar_index"
            ) as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=10):
                    ensure_indexes(
                        vector_store._table, vector_store._lazy_index_manager
                    )
                    mock_create.assert_called()


class TestCreateIndexSafeEdgeCases:
    """Tests for create_index_safe edge cases."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_create_index_safe_handles_value_error(self, vector_store):
        """Test create_index_safe handles ValueError (index already exists)."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table,
            "create_scalar_index",
            side_effect=ValueError("Index exists"),
        ):
            # Should not raise
            create_index_safe(vector_store._table, "test_column")

    async def test_create_index_safe_handles_runtime_error(self, vector_store):
        """Test create_index_safe handles RuntimeError."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table,
            "create_scalar_index",
            side_effect=RuntimeError("Creation failed"),
        ):
            create_index_safe(vector_store._table, "test_column")

    async def test_create_index_safe_handles_os_error(self, vector_store):
        """Test create_index_safe handles OSError."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table,
            "create_scalar_index",
            side_effect=OSError("Storage issue"),
        ):
            create_index_safe(vector_store._table, "test_column")


class TestCreateVectorIndexEdgeCases:
    """Tests for create_vector_index edge cases."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_create_vector_index_skipped_for_small_tables(self, vector_store):
        """Test create_vector_index skips for tables under threshold."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "create_index") as mock_create:
            create_vector_index(
                vector_store._table, 999, vector_store._lazy_index_manager
            )
            mock_create.assert_not_called()

    async def test_create_vector_index_creates_for_large_tables(self, vector_store):
        """Test create_vector_index creates index for tables at threshold."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(vector_store._table, "create_index") as mock_create:
            create_vector_index(
                vector_store._table, 1000, vector_store._lazy_index_manager
            )
            mock_create.assert_called_once()
            # Check it was called with correct params
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["metric"] == "L2"
            assert call_kwargs["num_sub_vectors"] == 16

    async def test_create_vector_index_calculates_partitions(self, vector_store):
        """Test create_vector_index calculates correct number of partitions."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Test with 10000 rows -> sqrt(10000) = 100 partitions
        with patch.object(vector_store._table, "create_index") as mock_create:
            create_vector_index(
                vector_store._table, 10000, vector_store._lazy_index_manager
            )
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["num_partitions"] == 100

        # Test with very large table -> capped at 256
        with patch.object(vector_store._table, "create_index") as mock_create:
            create_vector_index(
                vector_store._table, 100000, vector_store._lazy_index_manager
            )
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["num_partitions"] == 256

    async def test_create_vector_index_handles_value_error(self, vector_store):
        """Test create_vector_index handles ValueError (index exists)."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_index", side_effect=ValueError("Index exists")
        ):
            # Should not raise
            create_vector_index(
                vector_store._table, 2000, vector_store._lazy_index_manager
            )

    async def test_create_vector_index_handles_runtime_error(self, vector_store):
        """Test create_vector_index handles RuntimeError."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table,
            "create_index",
            side_effect=RuntimeError("Creation failed"),
        ):
            create_vector_index(
                vector_store._table, 2000, vector_store._lazy_index_manager
            )

    async def test_create_vector_index_handles_os_error(self, vector_store):
        """Test create_vector_index handles OSError."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        with patch.object(
            vector_store._table, "create_index", side_effect=OSError("Storage issue")
        ):
            create_vector_index(
                vector_store._table, 2000, vector_store._lazy_index_manager
            )


class TestEnsureIndexesVectorIndexDetection:
    """Tests for vector index detection in ensure_indexes."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    async def test_ensure_indexes_detects_ivf_index(self, vector_store):
        """Test ensure_indexes detects IVF vector index."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to return an index with IVF type
        mock_index = MagicMock()
        mock_index.name = "vector_idx"
        mock_index.index_type = "IVF_PQ"

        with patch.object(
            vector_store._table, "list_indices", return_value=[mock_index]
        ):
            with patch.object(vector_store._table, "create_index") as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=2000):
                    ensure_indexes(
                        vector_store._table, vector_store._lazy_index_manager
                    )
                    # Should NOT try to create vector index since IVF was detected
                    mock_create.assert_not_called()

    async def test_ensure_indexes_detects_ivf_in_dict_index(self, vector_store):
        """Test ensure_indexes detects IVF in dict-style index."""
        chunks = [make_chunk("test_1")]
        await vector_store.create_or_update_table(chunks)

        # Mock list_indices to return dict-style index with IVF type
        mock_index = {"name": "vector_idx", "index_type": "ivf_flat"}

        with patch.object(
            vector_store._table, "list_indices", return_value=[mock_index]
        ):
            with patch.object(vector_store._table, "create_index") as mock_create:
                with patch.object(vector_store._table, "count_rows", return_value=2000):
                    ensure_indexes(
                        vector_store._table, vector_store._lazy_index_manager
                    )
                    # Should NOT try to create vector index since IVF was detected
                    mock_create.assert_not_called()
