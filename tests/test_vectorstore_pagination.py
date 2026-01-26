"""Tests for vector store pagination and lazy loading functionality."""

import asyncio

import pytest

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


class TestSearchPagination:
    """Tests for paginated search functionality."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    @pytest.fixture
    async def populated_store(self, vector_store):
        """Create a vector store with more test data for pagination."""
        chunks = [
            make_chunk(f"chunk_{i}", f"src/file_{i % 5}.py", f"def func_{i}(): pass")
            for i in range(50)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_search_paginated_basic(self, populated_store):
        """Test basic paginated search."""
        from local_deepwiki.core.vectorstore import SearchResultPage

        page = await populated_store.search_paginated(
            query="function",
            limit=10,
            offset=0,
        )

        assert isinstance(page, SearchResultPage)
        assert len(page.results) <= 10
        assert page.offset == 0
        assert page.limit == 10
        assert page.total > 0

    async def test_search_paginated_offset(self, populated_store):
        """Test paginated search with offset."""
        # Get first page
        page1 = await populated_store.search_paginated(
            query="function",
            limit=5,
            offset=0,
        )

        # Get second page
        page2 = await populated_store.search_paginated(
            query="function",
            limit=5,
            offset=5,
        )

        # Results should be different
        if page1.results and page2.results:
            assert page1.results[0].chunk.id != page2.results[0].chunk.id

        # Offset should be correct
        assert page1.offset == 0
        assert page2.offset == 5

    async def test_search_paginated_has_more(self, populated_store):
        """Test has_more flag in pagination."""
        # Get first page with small limit
        page = await populated_store.search_paginated(
            query="function",
            limit=5,
            offset=0,
        )

        # Should have more results
        if page.total > 5:
            assert page.has_more is True
            assert page.cursor is not None
            assert page.cursor.startswith("offset:")

    async def test_search_paginated_cursor(self, populated_store):
        """Test cursor-based pagination."""
        # Get first page
        page1 = await populated_store.search_paginated(
            query="function",
            limit=5,
            offset=0,
        )

        # Use cursor for next page
        if page1.cursor:
            page2 = await populated_store.search_paginated(
                query="function",
                limit=5,
                cursor=page1.cursor,
            )

            # Results should be different (offset should be 5)
            assert page2.offset == 5

    async def test_search_paginated_with_filters(self, populated_store):
        """Test paginated search with language filter."""
        page = await populated_store.search_paginated(
            query="function",
            limit=10,
            language="python",
        )

        # All results should be Python
        for result in page.results:
            assert result.chunk.language.value == "python"

    async def test_search_paginated_empty_results(self, vector_store):
        """Test paginated search on empty store."""
        page = await vector_store.search_paginated(
            query="nonexistent",
            limit=10,
        )

        assert page.results == []
        assert page.total == 0
        assert page.has_more is False


class TestChunkIterator:
    """Tests for ChunkIterator class."""

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
            make_chunk(f"chunk_{i}", f"src/file_{i % 3}.py", f"def func_{i}(): pass")
            for i in range(30)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_chunk_iterator_count(self, populated_store):
        """Test ChunkIterator count() method."""
        iterator = populated_store.get_chunk_iterator(batch_size=10)
        assert iterator is not None
        assert iterator.count() == 30

    async def test_chunk_iterator_sync_iteration(self, populated_store):
        """Test synchronous iteration over chunks."""
        iterator = populated_store.get_chunk_iterator(batch_size=10)
        assert iterator is not None

        chunks = list(iterator)
        assert len(chunks) == 30
        # All chunks should have valid data
        for chunk in chunks:
            assert chunk.id is not None
            assert chunk.file_path is not None
            assert chunk.content is not None

    async def test_chunk_iterator_async_iteration(self, populated_store):
        """Test async iteration over chunks."""
        iterator = populated_store.get_chunk_iterator(batch_size=10)
        assert iterator is not None

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        assert len(chunks) == 30

    async def test_chunk_iterator_batches(self, populated_store):
        """Test batch iteration."""
        from local_deepwiki.core.vectorstore import ChunkBatch

        iterator = populated_store.get_chunk_iterator(batch_size=10)
        assert iterator is not None

        batches = list(iterator.batches())
        assert len(batches) == 3  # 30 chunks / 10 per batch = 3 batches

        # Check batch structure
        for i, batch in enumerate(batches):
            assert isinstance(batch, ChunkBatch)
            assert batch.batch_index == i
            assert batch.total_batches == 3
            if i < 2:
                assert batch.has_more is True
            else:
                assert batch.has_more is False

    async def test_chunk_iterator_filter(self, populated_store):
        """Test ChunkIterator with filter."""
        # Filter to only get chunks from one file
        # file_0.py has chunks 0, 3, 6, 9, 12, 15, 18, 21, 24, 27 = 10 chunks
        iterator = populated_store.get_chunk_iterator(batch_size=5)
        assert iterator is not None

        # Filter by language
        filtered_iterator = populated_store.get_chunk_iterator(
            batch_size=5,
            language="python",
        )
        assert filtered_iterator is not None
        assert filtered_iterator.count() == 30  # All are Python

    async def test_chunk_iterator_reset(self, populated_store):
        """Test iterator reset."""
        iterator = populated_store.get_chunk_iterator(batch_size=10)
        assert iterator is not None

        # Iterate halfway
        count = 0
        for chunk in iterator:
            count += 1
            if count >= 15:
                break

        # Reset and iterate again
        iterator.reset()
        chunks = list(iterator)
        assert len(chunks) == 30


class TestLazyChunkLoader:
    """Tests for LazyChunkLoader class."""

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
            make_chunk(f"chunk_{i}", f"src/file_{i % 3}.py", f"def func_{i}(): pass")
            for i in range(30)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_lazy_loader_get_chunks_by_file(self, populated_store):
        """Test lazy loading chunks by file."""
        loader = populated_store.get_lazy_chunk_loader(max_memory_mb=64)

        chunks = list(loader.get_chunks_by_file("src/file_0.py"))
        assert len(chunks) == 10  # file_0.py has 10 chunks

        for chunk in chunks:
            assert chunk.file_path == "src/file_0.py"

    async def test_lazy_loader_async_get_chunks_by_file(self, populated_store):
        """Test async lazy loading chunks by file."""
        loader = populated_store.get_lazy_chunk_loader()

        chunks = []
        async for chunk in loader.async_get_chunks_by_file("src/file_1.py"):
            chunks.append(chunk)

        assert len(chunks) == 10  # file_1.py has 10 chunks

    async def test_lazy_loader_get_all_chunks(self, populated_store):
        """Test lazy loading all chunks."""
        loader = populated_store.get_lazy_chunk_loader()

        chunks = list(loader.get_all_chunks(batch_size=10))
        assert len(chunks) == 30

    async def test_lazy_loader_count_chunks(self, populated_store):
        """Test counting chunks without loading."""
        loader = populated_store.get_lazy_chunk_loader()

        total = loader.count_chunks()
        assert total == 30

        # Count with filter
        python_count = loader.count_chunks(language="python")
        assert python_count == 30

    async def test_lazy_loader_optimal_batch_size(self, populated_store):
        """Test optimal batch size calculation."""
        loader = populated_store.get_lazy_chunk_loader(max_memory_mb=256)

        # Fixed memory calculation
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=100)
        assert batch_size >= 100  # Minimum batch size
        assert batch_size <= 10000  # Maximum batch size

    async def test_lazy_loader_empty_store(self, vector_store):
        """Test lazy loader on empty store."""
        loader = vector_store.get_lazy_chunk_loader()

        chunks = list(loader.get_all_chunks())
        assert chunks == []

        count = loader.count_chunks()
        assert count == 0


class TestStreamingStats:
    """Tests for streaming stats functionality."""

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
            make_chunk(
                f"chunk_{i}",
                f"src/file_{i % 5}.py",
                f"def func_{i}(): pass",
                chunk_type=ChunkType.FUNCTION if i % 2 == 0 else ChunkType.CLASS,
            )
            for i in range(50)
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_streaming_stats_basic(self, populated_store):
        """Test streaming stats returns correct structure."""
        stats = populated_store.get_stats_streaming(batch_size=10)

        assert "total_chunks" in stats
        assert "languages" in stats
        assert "chunk_types" in stats
        assert "files" in stats

        assert stats["total_chunks"] == 50
        assert stats["files"] == 5

    async def test_streaming_stats_matches_regular_stats(self, populated_store):
        """Test streaming stats matches regular stats."""
        regular_stats = populated_store.get_stats()
        streaming_stats = populated_store.get_stats_streaming(batch_size=10)

        assert regular_stats["total_chunks"] == streaming_stats["total_chunks"]
        assert regular_stats["languages"] == streaming_stats["languages"]
        assert regular_stats["chunk_types"] == streaming_stats["chunk_types"]
        assert regular_stats["files"] == streaming_stats["files"]

    async def test_streaming_stats_empty_store(self, vector_store):
        """Test streaming stats on empty store."""
        stats = vector_store.get_stats_streaming()

        assert stats["total_chunks"] == 0
        assert stats["languages"] == {}
        assert stats["chunk_types"] == {}
        assert stats["files"] == 0


class TestLazyMainDefinitionLines:
    """Tests for lazy main definition lines functionality."""

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
            # File 1: function then class
            CodeChunk(
                id="f1_func",
                file_path="src/file1.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="my_func",
                content="def my_func(): pass",
                start_line=5,
                end_line=10,
            ),
            CodeChunk(
                id="f1_class",
                file_path="src/file1.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="MyClass",
                content="class MyClass: pass",
                start_line=1,
                end_line=4,
            ),
            # File 2: only function
            CodeChunk(
                id="f2_func",
                file_path="src/file2.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="other_func",
                content="def other_func(): pass",
                start_line=1,
                end_line=5,
            ),
        ]
        await vector_store.create_or_update_table(chunks)
        return vector_store

    async def test_lazy_main_definition_lines(self, populated_store):
        """Test lazy iteration over main definition lines."""
        results = dict(populated_store.get_main_definition_lines_lazy(batch_size=2))

        # File 1 should prefer class (starts at line 1)
        assert "src/file1.py" in results
        assert results["src/file1.py"] == (1, 4)

        # File 2 should have the function
        assert "src/file2.py" in results
        assert results["src/file2.py"] == (1, 5)

    async def test_lazy_main_definition_lines_empty_store(self, vector_store):
        """Test lazy main definition lines on empty store."""
        results = list(vector_store.get_main_definition_lines_lazy())
        assert results == []

    async def test_lazy_main_definition_matches_regular(self, populated_store):
        """Test lazy matches regular get_main_definition_lines."""
        regular = populated_store.get_main_definition_lines()
        lazy = dict(populated_store.get_main_definition_lines_lazy())

        assert regular == lazy


class TestMemoryAwareBatching:
    """Tests for memory-aware batch sizing."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        return VectorStore(db_path, provider)

    def test_batch_size_respects_memory_limit(self, vector_store):
        """Test that batch size respects memory limit."""
        from local_deepwiki.core.vectorstore import (
            DEFAULT_MAX_MEMORY_MB,
            ESTIMATED_BYTES_PER_CHUNK,
            LazyChunkLoader,
        )

        # Create loader with small memory limit
        loader = LazyChunkLoader(vector_store, max_memory_mb=10)

        # Calculate expected batch size
        expected_max = (10 * 1024 * 1024) // ESTIMATED_BYTES_PER_CHUNK
        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=10)

        assert batch_size >= 100  # Minimum
        assert batch_size <= expected_max

    def test_batch_size_capped_at_maximum(self, vector_store):
        """Test that batch size is capped at maximum."""
        from local_deepwiki.core.vectorstore import LazyChunkLoader

        # Create loader with very large memory limit
        loader = LazyChunkLoader(vector_store, max_memory_mb=10000)

        batch_size = loader.calculate_optimal_batch_size(available_memory_mb=10000)

        # Should be capped at 10000
        assert batch_size <= 10000

    def test_max_memory_bytes_property(self, vector_store):
        """Test max_memory_bytes property."""
        from local_deepwiki.core.vectorstore import LazyChunkLoader

        loader = LazyChunkLoader(vector_store, max_memory_mb=256)

        assert loader.max_memory_bytes == 256 * 1024 * 1024


class TestSearchResultPage:
    """Tests for SearchResultPage dataclass."""

    def test_search_result_page_creation(self):
        """Test SearchResultPage creation."""
        from local_deepwiki.core.vectorstore import SearchResultPage
        from local_deepwiki.models import SearchResult

        page = SearchResultPage(
            results=[],
            total=100,
            offset=0,
            limit=10,
            has_more=True,
            cursor="offset:10",
        )

        assert page.results == []
        assert page.total == 100
        assert page.offset == 0
        assert page.limit == 10
        assert page.has_more is True
        assert page.cursor == "offset:10"

    def test_search_result_page_no_cursor(self):
        """Test SearchResultPage with no cursor."""
        from local_deepwiki.core.vectorstore import SearchResultPage

        page = SearchResultPage(
            results=[],
            total=5,
            offset=0,
            limit=10,
            has_more=False,
        )

        assert page.cursor is None


class TestChunkBatch:
    """Tests for ChunkBatch dataclass."""

    def test_chunk_batch_creation(self):
        """Test ChunkBatch creation."""
        from local_deepwiki.core.vectorstore import ChunkBatch

        batch = ChunkBatch(
            chunks=[],
            batch_index=0,
            total_batches=5,
            has_more=True,
        )

        assert batch.chunks == []
        assert batch.batch_index == 0
        assert batch.total_batches == 5
        assert batch.has_more is True
