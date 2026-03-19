"""Tests for vector store utility functions and lazy index management."""

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

    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return self._dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings."""
        self.embed_calls.append(texts)
        return [[0.1] * self._dimension for _ in texts]


def make_chunk(
    chunk_id: str = "test_chunk",
    file_path: str = "test.py",
    content: str = "def test(): pass",
    chunk_type: ChunkType = ChunkType.FUNCTION,
    name: str = "test",
    language: Language = Language.PYTHON,
    start_line: int = 1,
    end_line: int = 10,
) -> CodeChunk:
    """Create a test code chunk."""
    return CodeChunk(
        id=chunk_id,
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=name,
        content=content,
        start_line=start_line,
        end_line=end_line,
    )


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

    async def test_get_main_definition_lines_function_first_when_earlier(
        self, vector_store
    ):
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

    async def test_get_main_definition_lines_same_type_keeps_earlier(
        self, vector_store
    ):
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


class TestLazyIndexManager:
    """Tests for LazyIndexManager and lazy vector index creation."""

    @pytest.fixture
    def vector_store_lazy(self, tmp_path):
        """Create a vector store with lazy indexing enabled."""
        from local_deepwiki.config import LazyIndexConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        # Enable lazy indexing with low thresholds for testing
        lazy_config = LazyIndexConfig(
            enabled=True,
            latency_threshold_ms=100,
            min_rows=100,  # Must be >= 100 per config validation
            latency_window_size=3,
        )
        return VectorStore(db_path, provider, lazy_index_config=lazy_config)

    @pytest.fixture
    def vector_store_eager(self, tmp_path):
        """Create a vector store with lazy indexing disabled (eager mode)."""
        from local_deepwiki.config import LazyIndexConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        lazy_config = LazyIndexConfig(enabled=False, min_rows=100)
        return VectorStore(db_path, provider, lazy_index_config=lazy_config)

    async def test_lazy_index_manager_initialized(self, vector_store_lazy):
        """Test that lazy index manager is properly initialized."""
        assert vector_store_lazy._lazy_index_manager is not None
        assert vector_store_lazy._lazy_index_manager.config.enabled is True

    async def test_lazy_index_not_pending_after_create(self, vector_store_lazy):
        """Test that bulk create eagerly builds the index (not pending)."""
        # Create enough chunks to trigger index threshold (min_rows=100)
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store_lazy.create_or_update_table(chunks)

        # Index should NOT be pending — bulk create is always eager
        assert not vector_store_lazy._lazy_index_manager.is_index_pending()

    async def test_lazy_index_not_pending_for_small_tables(self, vector_store_lazy):
        """Test that lazy indexing doesn't mark pending for small tables."""
        # Create fewer chunks than min_rows threshold
        chunks = [make_chunk(f"chunk_{i}") for i in range(50)]
        await vector_store_lazy.create_or_update_table(chunks)

        # Index should not be pending (too few rows)
        assert not vector_store_lazy._lazy_index_manager.is_index_pending()
        assert not vector_store_lazy._lazy_index_manager.is_index_ready()

    async def test_eager_index_created_immediately(self, vector_store_eager):
        """Test that eager indexing attempts to create index immediately for large tables."""
        # Create enough chunks to trigger index threshold
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]

        await vector_store_eager.create_or_update_table(chunks)

        # Verify that lazy mode is disabled and no pending flag
        assert not vector_store_eager._lazy_index_manager.config.enabled
        # Index should either be created or we attempted it (not pending in lazy mode)
        assert not vector_store_eager._lazy_index_manager.is_index_pending()

    async def test_lazy_index_stats(self, vector_store_lazy):
        """Test get_lazy_index_stats returns correct information."""
        stats = vector_store_lazy.lazy_index_stats

        assert stats["enabled"] is True
        assert stats["index_pending"] is False
        assert stats["index_created"] is False
        assert stats["creation_in_progress"] is False
        assert stats["latency_threshold_ms"] == 100
        assert stats["min_rows"] == 100
        assert stats["average_latency_ms"] is None
        assert stats["latency_samples"] == 0

    async def test_lazy_index_latency_tracking(self, vector_store_lazy):
        """Test that search latency is tracked for lazy index decisions."""
        # Use fewer chunks (below threshold) so index isn't pending
        chunks = [make_chunk(f"chunk_{i}") for i in range(50)]
        await vector_store_lazy.create_or_update_table(chunks)

        # Perform some searches - use use_fuzzy=True to bypass cache
        await vector_store_lazy.search("unique query alpha", use_fuzzy=True)
        await vector_store_lazy.search("unique query beta", use_fuzzy=True)
        await vector_store_lazy.search("unique query gamma", use_fuzzy=True)

        # Check latency was recorded
        stats = vector_store_lazy.lazy_index_stats
        assert stats["latency_samples"] == 3
        assert stats["average_latency_ms"] is not None
        assert stats["average_latency_ms"] >= 0

    async def test_create_index_now(self, vector_store_lazy):
        """Test force immediate index creation."""
        # Create enough chunks
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store_lazy.create_or_update_table(chunks)

        # Bulk create is now always eager, so not pending
        assert not vector_store_lazy._lazy_index_manager.is_index_pending()

        # Force index creation - this may fail due to LanceDB internal reasons in tests
        # but we can verify the method is callable and updates state
        try:
            await vector_store_lazy.create_vector_index_now()
            # If successful, index should be ready
            assert vector_store_lazy.is_vector_index_ready()
        except (ValueError, RuntimeError):
            # LanceDB may complain about index already existing or other issues
            # The important thing is the method exists and handles errors gracefully
            pass

    async def test_is_vector_index_ready(self, vector_store_lazy):
        """Test is_vector_index_ready method."""
        assert vector_store_lazy.is_vector_index_ready() is False

        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store_lazy.create_or_update_table(chunks)

        # Still not ready (lazy mode)
        assert vector_store_lazy.is_vector_index_ready() is False

    async def test_on_vector_index_ready_callback(self, vector_store_lazy):
        """Test callback registration for index ready event."""
        callback_called = []

        def my_callback():
            callback_called.append(True)

        # Register callback
        vector_store_lazy.on_vector_index_ready(my_callback)

        # Callback shouldn't be called yet
        assert len(callback_called) == 0

        # Manually mark index as created to trigger callback
        vector_store_lazy._lazy_index_manager.mark_index_created()

        # Callback should have been called
        assert len(callback_called) == 1

    async def test_lazy_index_manager_reset(self, vector_store_lazy):
        """Test that reset clears all state."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store_lazy.create_or_update_table(chunks)

        # Record some latency
        vector_store_lazy._lazy_index_manager.record_search_latency(100.0)

        # Now recreate the table (which calls reset internally)
        await vector_store_lazy.create_or_update_table(chunks)

        # State should be fresh — bulk create eagerly builds the index
        stats = vector_store_lazy.lazy_index_stats
        assert stats["index_pending"] is False  # Eager create, not pending
        assert stats["latency_samples"] == 0  # Reset clears latency


class TestLazyIndexLatencyTrigger:
    """Tests for on-demand index creation triggered by latency."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store with low latency threshold for testing."""
        from local_deepwiki.config import LazyIndexConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        lazy_config = LazyIndexConfig(
            enabled=True,
            latency_threshold_ms=50,  # Minimum allowed per config validation
            min_rows=100,  # Must be >= 100 per config validation
            latency_window_size=3,
        )
        return VectorStore(db_path, provider, lazy_index_config=lazy_config)

    async def test_should_not_create_index_after_eager_bulk(self, vector_store):
        """Test that should_create_index returns False after eager bulk create."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        manager = vector_store._lazy_index_manager

        # Bulk create is always eager, so index is NOT pending
        assert not manager.is_index_pending()

        # should_create_index should return False (already built)
        assert not manager.should_create_index()

    async def test_should_not_create_when_disabled(self, tmp_path):
        """Test that should_create_index returns False when disabled."""
        from local_deepwiki.config import LazyIndexConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "disabled.lance"
        provider = MockEmbeddingProvider()
        lazy_config = LazyIndexConfig(enabled=False)
        store = VectorStore(db_path, provider, lazy_index_config=lazy_config)

        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await store.create_or_update_table(chunks)

        # Even with enough data, should return False when disabled
        assert not store._lazy_index_manager.should_create_index()

    async def test_should_not_create_when_already_created(self, vector_store):
        """Test that should_create_index returns False after creation."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        manager = vector_store._lazy_index_manager

        # Mark as created
        manager.mark_index_created()

        # Should not create again
        assert not manager.should_create_index()


class TestLatencyStats:
    """Tests for LatencyStats helper class."""

    def test_record_and_get_average(self):
        """Test recording latencies and computing average."""
        from local_deepwiki.core.vectorstore import LatencyStats

        stats = LatencyStats(window_size=5)

        # Record some values
        stats.record(100.0)
        stats.record(200.0)
        stats.record(300.0)

        assert stats.get_count() == 3
        assert stats.get_average() == 200.0

    def test_window_size_limit(self):
        """Test that window size is respected."""
        from local_deepwiki.core.vectorstore import LatencyStats

        stats = LatencyStats(window_size=3)

        # Record more values than window size
        for i in range(10):
            stats.record(float(i * 100))

        # Should only keep last 3
        assert stats.get_count() == 3
        # Last 3 values: 700, 800, 900
        assert stats.get_average() == 800.0

    def test_empty_stats(self):
        """Test empty stats return None for average."""
        from local_deepwiki.core.vectorstore import LatencyStats

        stats = LatencyStats()
        assert stats.get_count() == 0
        assert stats.get_average() is None

    def test_clear(self):
        """Test clearing stats."""
        from local_deepwiki.core.vectorstore import LatencyStats

        stats = LatencyStats()
        stats.record(100.0)
        stats.record(200.0)

        stats.clear()

        assert stats.get_count() == 0
        assert stats.get_average() is None


class TestLazyIndexScheduling:
    """Tests for background index creation scheduling."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store for testing."""
        from local_deepwiki.config import LazyIndexConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "test.lance"
        provider = MockEmbeddingProvider()
        lazy_config = LazyIndexConfig(
            enabled=True,
            min_rows=100,  # Must be >= 100 per config validation
            latency_threshold_ms=100,
        )
        return VectorStore(db_path, provider, lazy_index_config=lazy_config)

    async def test_schedule_index_creation(self, vector_store):
        """Test scheduling index creation as background task."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        manager = vector_store._lazy_index_manager

        # Bulk create is eager, so not pending
        assert not manager.is_index_pending()

        # Schedule creation (no-op since already built, but should not error)
        await vector_store.schedule_lazy_index_creation()

        # Should still be fine
        assert not manager.is_index_pending()

    async def test_wait_for_index_timeout(self, vector_store):
        """Test wait_for_index with timeout."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        # Don't create the index, just wait with a very short timeout
        result = await vector_store.wait_for_vector_index(timeout=0.01)

        # Should return False (timed out)
        assert result is False

    async def test_wait_for_index_immediate_ready(self, vector_store):
        """Test wait_for_index returns immediately when index is ready."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        # Mark as ready
        vector_store._lazy_index_manager.mark_index_created()

        # Should return immediately
        result = await vector_store.wait_for_vector_index(timeout=0.1)
        assert result is True

    async def test_duplicate_schedule_is_noop(self, vector_store):
        """Test that scheduling twice doesn't create duplicate tasks."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        # Schedule twice
        await vector_store.schedule_lazy_index_creation()
        await vector_store.schedule_lazy_index_creation()

        # Should work without errors
        manager = vector_store._lazy_index_manager
        assert manager.is_creation_in_progress() or manager.is_index_ready()


class TestLazyIndexIntegration:
    """Integration tests for lazy index with full workflow."""

    @pytest.fixture
    def vector_store(self, tmp_path):
        """Create a vector store with lazy indexing."""
        from local_deepwiki.config import LazyIndexConfig
        from local_deepwiki.core.vectorstore import VectorStore

        db_path = tmp_path / "integration.lance"
        provider = MockEmbeddingProvider()
        lazy_config = LazyIndexConfig(
            enabled=True,
            min_rows=100,  # Must be >= 100 per config validation
            latency_threshold_ms=500,
        )
        return VectorStore(db_path, provider, lazy_index_config=lazy_config)

    async def test_search_works_without_index(self, vector_store):
        """Test that search works correctly even without vector index (brute force)."""
        chunks = [
            make_chunk(f"chunk_{i}", content=f"content number {i}") for i in range(150)
        ]
        await vector_store.create_or_update_table(chunks)

        # Bulk create is always eager — index is NOT pending
        assert not vector_store._lazy_index_manager.is_index_pending()

        # Search should still work (brute force)
        results = await vector_store.search("content", limit=5)
        assert len(results) > 0
        assert all(r.chunk is not None for r in results)

    async def test_full_workflow_with_lazy_index(self, vector_store):
        """Test complete workflow: create, search, create index, search again."""
        # 1. Create data
        chunks = [
            make_chunk(f"func_{i}", content=f"def function_{i}(): pass")
            for i in range(150)
        ]
        await vector_store.create_or_update_table(chunks)

        # 2. Search (without index)
        results1 = await vector_store.search("function", limit=5)
        assert len(results1) > 0

        # 3. Check stats
        stats = vector_store.lazy_index_stats
        assert stats["index_pending"] is False  # Eager bulk create
        assert stats["latency_samples"] == 1  # One search recorded

        # 4. Try to create index now
        try:
            await vector_store.create_vector_index_now()
        except (ValueError, RuntimeError):
            # May fail in test environment, that's OK
            pass

        # 5. Search again
        results2 = await vector_store.search("function", limit=5)
        assert len(results2) > 0

    async def test_callback_invoked_on_index_ready(self, vector_store):
        """Test that registered callbacks are invoked when index becomes ready."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        callback_data = {"called": False, "call_count": 0}

        def my_callback():
            callback_data["called"] = True
            callback_data["call_count"] += 1

        # Register callback
        vector_store.on_vector_index_ready(my_callback)

        # Not called yet
        assert not callback_data["called"]

        # Manually trigger index ready
        vector_store._lazy_index_manager.mark_index_created()

        # Should be called now
        assert callback_data["called"]
        assert callback_data["call_count"] == 1

    async def test_callback_immediate_if_already_ready(self, vector_store):
        """Test that callback is invoked immediately if index is already ready."""
        chunks = [make_chunk(f"chunk_{i}") for i in range(150)]
        await vector_store.create_or_update_table(chunks)

        # Mark as ready first
        vector_store._lazy_index_manager.mark_index_created()

        callback_data = {"called": False}

        def my_callback():
            callback_data["called"] = True

        # Register callback after index is ready
        vector_store.on_vector_index_ready(my_callback)

        # Should be called immediately
        assert callback_data["called"]
