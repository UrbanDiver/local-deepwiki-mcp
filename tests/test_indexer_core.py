"""Tests for core indexing operations: batched processing, search, and progress."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ChunkingConfig, Config, ParsingConfig
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.models import ChunkType, CodeChunk, Language


class TestBatchedProcessing:
    """Tests for batched chunk processing in the indexer."""

    async def test_processes_chunks_in_batches(self, tmp_path):
        """Test that chunks are processed in batches to limit memory usage."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        for i in range(5):
            (repo_path / f"module{i}.py").write_text(
                f'''
def function_{i}_a():
    """Function A in module {i}."""
    pass

def function_{i}_b():
    """Function B in module {i}."""
    pass

def function_{i}_c():
    """Function C in module {i}."""
    pass
'''
            )

        chunking = ChunkingConfig().model_copy(update={"batch_size": 3})
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"chunking": chunking, "parsing": parsing})

        create_calls = []
        add_calls = []

        async def mock_create_or_update_table(chunks):
            create_calls.append(len(chunks))
            return len(chunks)

        async def mock_add_chunks(chunks):
            add_calls.append(len(chunks))
            return len(chunks)

        async def mock_delete_chunks_by_file(file_path):
            return 0

        async def mock_delete_chunks_by_files(file_paths):
            return len(file_paths)

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(
                side_effect=mock_create_or_update_table
            )
            mock_store.add_chunks = AsyncMock(side_effect=mock_add_chunks)
            mock_store.delete_chunks_by_file = AsyncMock(
                side_effect=mock_delete_chunks_by_file
            )
            mock_store.delete_chunks_by_files = AsyncMock(
                side_effect=mock_delete_chunks_by_files
            )
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            status = await indexer.index(full_rebuild=True)

        total_batches = len(create_calls) + len(add_calls)
        assert total_batches > 1, "Should have processed chunks in multiple batches"
        assert len(create_calls) == 1, (
            "Should call create_or_update_table once for first batch"
        )
        assert len(add_calls) >= 1, "Should call add_chunks for subsequent batches"
        assert status.total_chunks > 0

    async def test_incremental_update_with_batching(self, tmp_path):
        """Test that incremental updates work with batched processing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "module1.py").write_text(
            """
def function_a():
    pass

def function_b():
    pass
"""
        )

        chunking = ChunkingConfig().model_copy(update={"batch_size": 2})
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"chunking": chunking, "parsing": parsing})

        delete_calls = []
        add_calls = []

        async def mock_add_chunks(chunks):
            add_calls.append(len(chunks))
            return len(chunks)

        async def mock_delete_chunks_by_file(file_path):
            delete_calls.append(file_path)
            return 0

        async def mock_delete_chunks_by_files(file_paths):
            delete_calls.extend(file_paths)
            return len(file_paths)

        async def mock_create_or_update_table(chunks):
            return len(chunks)

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(
                side_effect=mock_create_or_update_table
            )
            mock_store.add_chunks = AsyncMock(side_effect=mock_add_chunks)
            mock_store.delete_chunks_by_file = AsyncMock(
                side_effect=mock_delete_chunks_by_file
            )
            mock_store.delete_chunks_by_files = AsyncMock(
                side_effect=mock_delete_chunks_by_files
            )
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            await indexer.index(full_rebuild=True)

            delete_calls.clear()
            add_calls.clear()

            (repo_path / "module2.py").write_text(
                """
def function_c():
    pass
"""
            )

            await indexer.index(full_rebuild=False)

        assert len(add_calls) >= 1, "Should add chunks in incremental update"

    async def test_empty_batch_handling(self, tmp_path):
        """Test that empty repositories are handled correctly."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        chunking = ChunkingConfig().model_copy(update={"batch_size": 10})
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"chunking": chunking, "parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=0)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            status = await indexer.index(full_rebuild=True)

        assert status.total_files == 0
        assert status.total_chunks == 0


class TestSearch:
    """Tests for search method."""

    async def test_search_returns_results(self, tmp_path):
        """Test that search returns properly formatted results."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        mock_chunk = CodeChunk(
            id="test-id",
            file_path="test.py",
            name="test_function",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            content="def test_function(): pass",
            start_line=1,
            end_line=1,
            docstring="Test docstring",
        )

        class MockSearchResult:
            def __init__(self, chunk, score):
                self.chunk = chunk
                self.score = score

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.search = AsyncMock(
                return_value=[MockSearchResult(mock_chunk, 0.95)]
            )
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            results = await indexer.search("test query", limit=5)

            assert len(results) == 1
            assert results[0]["file_path"] == "test.py"
            assert results[0]["name"] == "test_function"
            assert results[0]["type"] == "function"
            assert results[0]["language"] == "python"
            assert results[0]["score"] == 0.95

    async def test_search_with_language_filter(self, tmp_path):
        """Test that search passes language filter correctly."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.search = AsyncMock(return_value=[])
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            await indexer.search("test query", limit=10, language="python")

            mock_store.search.assert_called_once_with(
                "test query", limit=10, language="python"
            )

    async def test_search_truncates_long_content(self, tmp_path):
        """Test that search truncates content longer than 500 chars."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        long_content = "x" * 600

        mock_chunk = CodeChunk(
            id="test-id",
            file_path="test.py",
            name="test_function",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            content=long_content,
            start_line=1,
            end_line=1,
        )

        class MockSearchResult:
            def __init__(self, chunk, score):
                self.chunk = chunk
                self.score = score

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.search = AsyncMock(
                return_value=[MockSearchResult(mock_chunk, 0.9)]
            )
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            results = await indexer.search("test query")

            assert len(results[0]["content"]) == 503  # 500 + "..."
            assert results[0]["content"].endswith("...")


class TestIndexWithProgressCallback:
    """Tests for index method with progress callback."""

    async def test_index_calls_progress_callback_complete(self, tmp_path):
        """Test that index calls progress callback with 'Indexing complete'."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        progress_messages = []

        def progress_callback(msg, current, total):
            progress_messages.append(msg)

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            await indexer.index(full_rebuild=True, progress_callback=progress_callback)

            assert any("Indexing complete" in msg for msg in progress_messages)


class TestParallelParsingPerformance:
    """Tests for parallel parsing performance logging.

    Note: The local_deepwiki logger has propagate=False for clean MCP output,
    so we mock the logger to capture log calls.
    """

    async def test_parallel_parsing_logs_performance_metrics(self, tmp_path):
        """Test that parallel parsing logs performance metrics."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        for i in range(3):
            (repo_path / f"module{i}.py").write_text(f"def func{i}(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        chunking = ChunkingConfig().model_copy(update={"parallel_workers": 2})
        config = Config().model_copy(update={"parsing": parsing, "chunking": chunking})

        log_messages = []

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                await indexer.index(full_rebuild=True)

        parsing_log = [m for m in log_messages if "Parallel parsing complete" in m]
        assert len(parsing_log) == 1

        log_msg = parsing_log[0]
        assert "files" in log_msg
        assert "chunks" in log_msg
        assert "files/s" in log_msg
        assert "chunks/s" in log_msg
        assert "workers" in log_msg

    async def test_parallel_parsing_uses_configured_workers(self, tmp_path):
        """Test that parallel parsing uses the configured number of workers."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        chunking = ChunkingConfig().model_copy(update={"parallel_workers": 4})
        config = Config().model_copy(update={"parsing": parsing, "chunking": chunking})

        log_messages = []

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                await indexer.index(full_rebuild=True)

        worker_log = [m for m in log_messages if "4 workers" in m]
        assert len(worker_log) >= 1

    async def test_parallel_parsing_handles_empty_file_list(self, tmp_path):
        """Test that parallel parsing handles empty file list gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        log_messages = []

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=0)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                status = await indexer.index(full_rebuild=True)

        assert status.total_files == 0
        assert status.total_chunks == 0
        assert any("No files to parse" in m for m in log_messages)

    async def test_parallel_parsing_counts_errors(self, tmp_path):
        """Test that parallel parsing counts and logs errors."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "good.py").write_text("def good(): pass")
        (repo_path / "bad.py").write_text("def bad(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        chunking = ChunkingConfig().model_copy(update={"parallel_workers": 2})
        config = Config().model_copy(update={"parsing": parsing, "chunking": chunking})

        log_messages = []

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            from local_deepwiki.core.indexer import ParseResult

            def mock_parse_single_file(file_path):
                file_info = indexer.parser.get_file_info(file_path, repo_path)
                if file_path.name == "bad.py":
                    return ParseResult(
                        file_path=file_path,
                        file_info=file_info,
                        chunks=[],
                        error="Simulated parsing error",
                    )
                chunks = list(indexer.chunker.chunk_file(file_path, repo_path))
                file_info.chunk_count = len(chunks)
                return ParseResult(
                    file_path=file_path, file_info=file_info, chunks=chunks
                )

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                with patch.object(
                    indexer, "_parse_single_file", mock_parse_single_file
                ):
                    await indexer.index(full_rebuild=True)

        parsing_log = [m for m in log_messages if "Parallel parsing complete" in m]
        assert len(parsing_log) == 1
        assert "1 errors" in parsing_log[0]
