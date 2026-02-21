"""Tests for repository indexer with batched processing."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ASTCacheConfig, ChunkingConfig, Config, ParsingConfig
from local_deepwiki.core.indexer import (
    CURRENT_SCHEMA_VERSION,
    RepositoryIndexer,
    _migrate_status,
    _needs_migration,
)
from local_deepwiki.core.parser import ASTCache
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


class TestChunkingConfigBatchSize:
    """Tests for batch_size configuration."""

    def test_default_batch_size(self):
        """Test that default batch size is 500."""
        config = ChunkingConfig()
        assert config.batch_size == 500

    def test_custom_batch_size(self):
        """Test that batch size can be customized."""
        config = ChunkingConfig(batch_size=100)
        assert config.batch_size == 100


class TestParallelWorkersConfig:
    """Tests for parallel_workers configuration."""

    def test_default_parallel_workers_based_on_cpu(self):
        """Test that default parallel_workers is based on CPU count."""
        import os

        config = ChunkingConfig()
        cpu_count = os.cpu_count() or 4
        expected = min(cpu_count, 8)
        assert config.parallel_workers == expected

    def test_custom_parallel_workers(self):
        """Test that parallel_workers can be customized."""
        config = ChunkingConfig(parallel_workers=2)
        assert config.parallel_workers == 2

    def test_parallel_workers_max_value(self):
        """Test that parallel_workers is capped at CPU count via field validator.

        The Field allows up to 32, but the validator caps at os.cpu_count().
        """
        import os

        cpu_count = os.cpu_count() or 4
        config = ChunkingConfig(parallel_workers=32)
        # Validator caps at CPU count
        assert config.parallel_workers <= cpu_count
        assert config.parallel_workers >= 1

    def test_parallel_workers_min_value(self):
        """Test that parallel_workers minimum is 1."""
        config = ChunkingConfig(parallel_workers=1)
        assert config.parallel_workers == 1

    def test_parallel_workers_in_full_config(self):
        """Test that parallel_workers is accessible in full config."""
        config = Config()
        assert hasattr(config.chunking, "parallel_workers")
        assert config.chunking.parallel_workers >= 1


class TestBatchedProcessing:
    """Tests for batched chunk processing in the indexer."""

    async def test_processes_chunks_in_batches(self, tmp_path):
        """Test that chunks are processed in batches to limit memory usage."""
        # Create a simple repo structure
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create multiple Python files to generate enough chunks
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

        # Create config with small batch size
        # Config classes are frozen, so we use model_copy to create modified versions
        chunking = ChunkingConfig().model_copy(update={"batch_size": 3})
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"chunking": chunking, "parsing": parsing})

        # Track calls to vector store methods
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

        # Create indexer with mocked vector store
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

            # Run indexing
            status = await indexer.index(full_rebuild=True)

        # Verify batching occurred
        # With 5 files × ~3 chunks each = ~15 chunks
        # With batch_size=3, we should have multiple batches
        total_batches = len(create_calls) + len(add_calls)
        assert total_batches > 1, "Should have processed chunks in multiple batches"

        # First call should be create_or_update_table
        assert len(create_calls) == 1, (
            "Should call create_or_update_table once for first batch"
        )

        # Subsequent calls should be add_chunks
        assert len(add_calls) >= 1, "Should call add_chunks for subsequent batches"

        # Total chunks should match what we created
        assert status.total_chunks > 0

    async def test_incremental_update_with_batching(self, tmp_path):
        """Test that incremental updates work with batched processing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create initial files
        (repo_path / "module1.py").write_text(
            """
def function_a():
    pass

def function_b():
    pass
"""
        )

        # Config classes are frozen, so we use model_copy to create modified versions
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

            # First index (full rebuild)
            await indexer.index(full_rebuild=True)

            # Clear tracking
            delete_calls.clear()
            add_calls.clear()

            # Add another file
            (repo_path / "module2.py").write_text(
                """
def function_c():
    pass
"""
            )

            # Run incremental update
            await indexer.index(full_rebuild=False)

        # For incremental updates, delete should be called per file
        # Note: with no previous status, all files are treated as new
        assert len(add_calls) >= 1, "Should add chunks in incremental update"

    async def test_empty_batch_handling(self, tmp_path):
        """Test that empty repositories are handled correctly."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Config classes are frozen, so we use model_copy to create modified versions
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


class TestBatchSizeConfiguration:
    """Tests for batch size in config."""

    def test_batch_size_in_full_config(self):
        """Test that batch size is accessible in full config."""
        config = Config()
        assert hasattr(config.chunking, "batch_size")
        assert config.chunking.batch_size == 500

    def test_batch_size_validation(self):
        """Test that batch size accepts positive integers."""
        config = ChunkingConfig(batch_size=1)
        assert config.batch_size == 1

        config = ChunkingConfig(batch_size=10000)
        assert config.batch_size == 10000


class TestSchemaMigration:
    """Tests for schema version migration."""

    def test_current_schema_version_exists(self):
        """Test that CURRENT_SCHEMA_VERSION is defined."""
        assert CURRENT_SCHEMA_VERSION >= 1

    def test_needs_migration_old_version(self):
        """Test that old schema versions need migration."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=10,
            total_chunks=100,
            schema_version=1,
        )
        # If current version is > 1, migration is needed
        if CURRENT_SCHEMA_VERSION > 1:
            assert _needs_migration(status) is True

    def test_needs_migration_current_version(self):
        """Test that current schema version doesn't need migration."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=10,
            total_chunks=100,
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        assert _needs_migration(status) is False

    def test_migrate_status_updates_version(self):
        """Test that migration updates the schema version."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=10,
            total_chunks=100,
            schema_version=1,
        )
        migrated, requires_rebuild = _migrate_status(status)
        assert migrated.schema_version == CURRENT_SCHEMA_VERSION

    def test_migrate_status_preserves_data(self):
        """Test that migration preserves existing data."""
        status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=10,
            total_chunks=100,
            languages={"python": 8, "javascript": 2},
            schema_version=1,
        )
        migrated, _ = _migrate_status(status)

        assert migrated.repo_path == "/test/repo"
        assert migrated.indexed_at == 1234567890.0
        assert migrated.total_files == 10
        assert migrated.total_chunks == 100
        assert migrated.languages == {"python": 8, "javascript": 2}

    async def test_load_status_handles_legacy_files(self, tmp_path):
        """Test that loading status handles legacy files without schema_version."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Config classes are frozen, so we use model_copy to create modified versions
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Create legacy status file without schema_version
            legacy_status = {
                "repo_path": str(repo_path),
                "indexed_at": 1234567890.0,
                "total_files": 5,
                "total_chunks": 50,
                "languages": {"python": 5},
                "files": [],
            }
            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(legacy_status))

            # Load should handle missing schema_version
            status, requires_rebuild = indexer._load_status()

            assert status is not None
            assert status.schema_version == CURRENT_SCHEMA_VERSION
            assert status.total_files == 5
            assert status.total_chunks == 50

    async def test_save_status_includes_schema_version(self, tmp_path):
        """Test that saved status includes the current schema version."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "test.py").write_text("def test(): pass")

        # Config classes are frozen, so we use model_copy to create modified versions
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            await indexer.index(full_rebuild=True)

            # Read the saved status file
            status_path = indexer.wiki_path / "index_status.json"
            with open(status_path) as f:
                data = json.load(f)

            assert "schema_version" in data
            assert data["schema_version"] == CURRENT_SCHEMA_VERSION

    async def test_index_status_model_default_schema_version(self):
        """Test that IndexStatus defaults to schema_version=1."""
        status = IndexStatus(
            repo_path="/test",
            indexed_at=1.0,
            total_files=0,
            total_chunks=0,
        )
        assert status.schema_version == 1

    async def test_migration_triggered_on_load(self, tmp_path):
        """Test that migration is triggered when loading old schema version."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Config classes are frozen, so we use model_copy to create modified versions
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Create status file with old schema version
            old_status = {
                "repo_path": str(repo_path),
                "indexed_at": 1234567890.0,
                "total_files": 5,
                "total_chunks": 50,
                "languages": {"python": 5},
                "files": [],
                "schema_version": 1,
            }
            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(old_status))

            # Load status - should migrate
            status, requires_rebuild = indexer._load_status()

            if CURRENT_SCHEMA_VERSION > 1:
                # Status should be migrated and saved
                with open(status_path) as f:
                    saved_data = json.load(f)
                assert saved_data["schema_version"] == CURRENT_SCHEMA_VERSION


class TestEmbeddingProviderOverride:
    """Tests for embedding provider override in constructor."""

    def test_embedding_provider_override(self, tmp_path):
        """Test that embedding_provider_name overrides the config provider."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Config classes are frozen, so we use model_copy to create modified versions
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        # Default should be "local"
        assert config.embedding.provider == "local"

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            with patch(
                "local_deepwiki.core.indexer.get_embedding_provider"
            ) as MockGetProvider:
                mock_provider = MagicMock()
                MockGetProvider.return_value = mock_provider

                # Create indexer with overridden embedding provider
                indexer = RepositoryIndexer(
                    repo_path, config, embedding_provider_name="openai"
                )

                # The internal config should have "openai" as provider
                assert indexer.config.embedding.provider == "openai"
                # Verify get_embedding_provider was called with the updated config
                MockGetProvider.assert_called_once()
                call_config = MockGetProvider.call_args[0][0]
                assert call_config.provider == "openai"


class TestParseFileErrors:
    """Tests for error handling in _parse_single_file."""

    def test_parse_single_file_oserror(self, tmp_path):
        """Test that OSError in _parse_single_file returns error result."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create a file
        file_path = repo_path / "test.py"
        file_path.write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Mock the chunker to raise OSError
            with patch.object(
                indexer.chunker, "chunk_file", side_effect=OSError("Test error")
            ):
                result = indexer._parse_single_file(file_path)

                assert result.error is not None
                assert "Test error" in result.error
                assert result.chunks == []

    def test_parse_single_file_value_error(self, tmp_path):
        """Test that ValueError in _parse_single_file returns error result."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        file_path = repo_path / "test.py"
        file_path.write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            with patch.object(
                indexer.chunker, "chunk_file", side_effect=ValueError("Invalid value")
            ):
                result = indexer._parse_single_file(file_path)

                assert result.error is not None
                assert "Invalid value" in result.error
                assert result.chunks == []

    def test_parse_single_file_unicode_decode_error(self, tmp_path):
        """Test that UnicodeDecodeError in _parse_single_file returns error result."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        file_path = repo_path / "test.py"
        file_path.write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            with patch.object(
                indexer.chunker,
                "chunk_file",
                side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"),
            ):
                result = indexer._parse_single_file(file_path)

                assert result.error is not None
                assert result.chunks == []

    def test_parse_single_file_runtime_error(self, tmp_path):
        """Test that RuntimeError in _parse_single_file returns error result."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        file_path = repo_path / "test.py"
        file_path.write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            with patch.object(
                indexer.chunker, "chunk_file", side_effect=RuntimeError("Runtime issue")
            ):
                result = indexer._parse_single_file(file_path)

                assert result.error is not None
                assert "Runtime issue" in result.error
                assert result.chunks == []


class TestLoadStatusErrors:
    """Tests for error handling in _load_status."""

    def test_load_status_file_not_exists(self, tmp_path):
        """Test that _load_status returns None when status file doesn't exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            status, requires_rebuild = indexer._load_status()

            assert status is None
            assert requires_rebuild is False

    def test_load_status_json_decode_error(self, tmp_path):
        """Test that _load_status handles JSONDecodeError gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Create invalid JSON file
            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text("not valid json {{{")

            status, requires_rebuild = indexer._load_status()

            assert status is None
            assert requires_rebuild is False

    def test_load_status_validation_error(self, tmp_path):
        """Test that _load_status handles Pydantic validation error gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Create JSON with missing required fields
            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps({"not_a_valid_field": "value"}))

            status, requires_rebuild = indexer._load_status()

            assert status is None
            assert requires_rebuild is False


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_returns_status(self, tmp_path):
        """Test that get_status returns the loaded status."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Create a valid status file
            status_data = {
                "repo_path": str(repo_path),
                "indexed_at": 1234567890.0,
                "total_files": 10,
                "total_chunks": 100,
                "languages": {"python": 10},
                "files": [],
                "schema_version": CURRENT_SCHEMA_VERSION,
            }
            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status_data))

            status = indexer.get_status()

            assert status is not None
            assert status.total_files == 10
            assert status.total_chunks == 100

    def test_get_status_returns_none_when_no_index(self, tmp_path):
        """Test that get_status returns None when no index exists."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            status = indexer.get_status()

            assert status is None


class TestSearch:
    """Tests for search method."""

    async def test_search_returns_results(self, tmp_path):
        """Test that search returns properly formatted results."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        # Create mock search results
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


class TestFindSourceFiles:
    """Tests for _find_source_files filtering logic."""

    def test_find_source_files_excludes_pattern_match(self, tmp_path):
        """Test that files matching exclude patterns are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create a file that matches an exclude pattern
        (repo_path / "test.pyc").write_text("compiled")
        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(
            update={"languages": ["python"], "exclude_patterns": ["*.pyc"]}
        )
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            files = indexer._find_source_files()

            # .pyc should be excluded, .py should be included
            file_names = [f.name for f in files]
            assert "test.pyc" not in file_names
            assert "test.py" in file_names

    def test_find_source_files_excludes_large_files(self, tmp_path):
        """Test that files exceeding max_file_size are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create a small file and a large file
        (repo_path / "small.py").write_text("def small(): pass")
        (repo_path / "large.py").write_text("x" * 2000)

        parsing = ParsingConfig().model_copy(
            update={"languages": ["python"], "max_file_size": 1000}
        )
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            files = indexer._find_source_files()

            file_names = [f.name for f in files]
            assert "small.py" in file_names
            assert "large.py" not in file_names

    def test_find_source_files_excludes_unsupported_language(self, tmp_path):
        """Test that files with unsupported languages are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "test.py").write_text("def test(): pass")
        (repo_path / "test.rb").write_text("def test; end")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            files = indexer._find_source_files()

            file_names = [f.name for f in files]
            assert "test.py" in file_names
            assert "test.rb" not in file_names

    def test_find_source_files_handles_stat_error(self, tmp_path):
        """Test that files that fail stat() are skipped gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Mock Path.stat to raise OSError for the test file
            original_stat = Path.stat

            def mock_stat(self):
                if self.name == "test.py":
                    raise OSError("Permission denied")
                return original_stat(self)

            with patch.object(Path, "stat", mock_stat):
                files = indexer._find_source_files()

                # File should be skipped due to stat error
                assert len(files) == 0

    def test_find_source_files_skips_unknown_language(self, tmp_path):
        """Test that files with undetectable language are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create a file with unknown extension
        (repo_path / "test.xyz").write_text("unknown content")
        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            files = indexer._find_source_files()

            file_names = [f.name for f in files]
            assert "test.xyz" not in file_names
            assert "test.py" in file_names


class TestDeleteOldChunks:
    """Tests for _delete_old_chunks_for_modified_files."""

    async def test_delete_old_chunks_with_progress_callback(self, tmp_path):
        """Test that progress callback is called during chunk deletion."""
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
            mock_store.delete_chunks_by_files = AsyncMock(return_value=1)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            # Simulate files_to_process with a file that exists in prev_files_by_path
            files_to_process = [repo_path / "test.py"]
            prev_files_by_path: dict[str, FileInfo] = {
                "test.py": FileInfo(
                    path="test.py",
                    language=Language.PYTHON,
                    size_bytes=50,
                    last_modified=1.0,
                    hash="old_hash",
                ),
            }

            await indexer._delete_old_chunks_for_modified_files(
                files_to_process, prev_files_by_path, progress_callback
            )

            # Check that progress callback was called
            assert any("Removing old chunks" in msg for msg in progress_messages)
            mock_store.delete_chunks_by_files.assert_called_once()


class TestParseFilesParallelErrors:
    """Tests for error handling in _parse_files_parallel."""

    async def test_parse_files_parallel_handles_errors(self, tmp_path):
        """Test that _parse_files_parallel handles file parsing errors gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "good.py").write_text("def good(): pass")
        (repo_path / "bad.py").write_text("def bad(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        chunking = ChunkingConfig().model_copy(update={"batch_size": 10})
        config = Config().model_copy(update={"parsing": parsing, "chunking": chunking})

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

            # Create a ParseResult with error to simulate failure
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
                # Return a valid result for good.py
                chunks = list(indexer.chunker.chunk_file(file_path, repo_path))
                file_info.chunk_count = len(chunks)
                return ParseResult(
                    file_path=file_path, file_info=file_info, chunks=chunks
                )

            with patch.object(indexer, "_parse_single_file", mock_parse_single_file):
                files_to_process = [repo_path / "good.py", repo_path / "bad.py"]
                processed_files, total_chunks = await indexer._parse_files_parallel(
                    files_to_process,
                    full_rebuild=True,
                    progress_callback=progress_callback,
                )

            # Should have processed good.py but not bad.py
            assert len(processed_files) == 1
            assert processed_files[0].path == "good.py"

            # Progress callback should have been called with error message
            assert any("Error processing" in msg for msg in progress_messages)


class TestLoadPreviousStatus:
    """Tests for _load_previous_status method."""

    def test_load_previous_status_full_rebuild(self, tmp_path):
        """Test that full_rebuild=True returns empty previous status."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            status, prev_files, rebuild = indexer._load_previous_status(
                full_rebuild=True
            )

            assert status is None
            assert prev_files == {}
            assert rebuild is True

    def test_load_previous_status_no_previous_index(self, tmp_path):
        """Test that missing previous index returns None status."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            status, prev_files, rebuild = indexer._load_previous_status(
                full_rebuild=False
            )

            assert status is None
            assert prev_files == {}
            assert rebuild is False

    async def test_load_previous_status_migration_requires_rebuild(self, tmp_path):
        """Test that schema migration requiring rebuild triggers full rebuild."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Mock the status manager's load_with_migration_info to return requires_rebuild=True
            with patch.object(
                indexer._status_manager,
                "load_with_migration_info",
                return_value=(None, True),
            ):
                status, prev_files, rebuild = indexer._load_previous_status(
                    full_rebuild=False
                )

                assert status is None
                assert prev_files == {}
                assert rebuild is True


class TestCollectFilesToProcess:
    """Tests for _collect_files_to_process with progress callback."""

    def test_collect_files_calls_progress_callback(self, tmp_path):
        """Test that _collect_files_to_process calls progress callback."""
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
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            files_to_process, files_unchanged, deleted_file_paths = (
                indexer._collect_files_to_process({}, progress_callback)
            )

            # Should have called progress callback for found files and processing status
            assert any("Found source files" in msg for msg in progress_messages)
            assert any("Processing" in msg for msg in progress_messages)
            # No deleted files when prev_files_by_path is empty
            assert deleted_file_paths == []


class TestDeletedFileCleanup:
    """Tests for deleted file cleanup during incremental indexing."""

    def test_collect_files_detects_deleted_files(self, tmp_path):
        """Test that _collect_files_to_process detects files removed from disk."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Only module_a.py exists on disk
        (repo_path / "module_a.py").write_text("def a(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            # Simulate a previous index that knew about module_a.py and module_b.py
            prev_files_by_path: dict[str, FileInfo] = {
                "module_a.py": FileInfo(
                    path="module_a.py",
                    language=Language.PYTHON,
                    size_bytes=50,
                    last_modified=1.0,
                    hash="same_hash",
                ),
                "module_b.py": FileInfo(
                    path="module_b.py",
                    language=Language.PYTHON,
                    size_bytes=50,
                    last_modified=1.0,
                    hash="old_hash",
                ),
            }

            # Patch get_file_info to return a matching hash for module_a.py
            original_get_file_info = indexer.parser.get_file_info

            def patched_get_file_info(file_path, repo_path):
                info = original_get_file_info(file_path, repo_path)
                if info.path == "module_a.py":
                    info.hash = "same_hash"
                return info

            with patch.object(
                indexer.parser, "get_file_info", side_effect=patched_get_file_info
            ):
                _, files_unchanged, deleted_file_paths = (
                    indexer._collect_files_to_process(prev_files_by_path, None)
                )

            assert "module_b.py" in deleted_file_paths
            assert len(deleted_file_paths) == 1
            # module_a.py should be unchanged (same hash)
            assert len(files_unchanged) == 1

    def test_collect_files_no_deletions_when_no_previous(self, tmp_path):
        """Test that no deletions are detected on first run (empty prev_files_by_path)."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "module_a.py").write_text("def a(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            _, _, deleted_file_paths = indexer._collect_files_to_process({}, None)

            assert deleted_file_paths == []

    async def test_deleted_files_chunks_removed_from_vector_store(self, tmp_path):
        """Test that chunks for deleted files are removed from the vector store during indexing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Only module_a.py exists on disk now
        (repo_path / "module_a.py").write_text("def a(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        delete_calls: list[list[str]] = []

        async def mock_delete_chunks_by_files(file_paths):
            delete_calls.append(list(file_paths))
            return len(file_paths)

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            mock_store.delete_chunks_by_files = AsyncMock(
                side_effect=mock_delete_chunks_by_files
            )
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            # Simulate a previous index with module_a.py and module_b.py
            prev_status = IndexStatus(
                repo_path=str(repo_path),
                indexed_at=1.0,
                total_files=2,
                total_chunks=10,
                languages={"python": 2},
                files=[
                    FileInfo(
                        path="module_a.py",
                        language=Language.PYTHON,
                        size_bytes=50,
                        last_modified=1.0,
                        hash="placeholder",
                    ),
                    FileInfo(
                        path="module_b.py",
                        language=Language.PYTHON,
                        size_bytes=50,
                        last_modified=1.0,
                        hash="old_hash",
                    ),
                ],
                schema_version=CURRENT_SCHEMA_VERSION,
            )

            # Write previous status so the indexer loads it
            import json

            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(prev_status.model_dump_json())

            # Run incremental indexing (module_b.py is gone from disk)
            await indexer.index(full_rebuild=False)

            # Verify delete_chunks_by_files was called with module_b.py
            all_deleted_paths = [path for call in delete_calls for path in call]
            assert "module_b.py" in all_deleted_paths

    async def test_no_deletion_when_no_files_deleted(self, tmp_path):
        """Test that no deletion occurs when all previously indexed files still exist."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "module_a.py").write_text("def a(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            mock_store.delete_chunks_by_files = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            # First index
            await indexer.index(full_rebuild=True)

            # Reset mock tracking
            mock_store.delete_chunks_by_files.reset_mock()

            # Incremental index with same files
            await indexer.index(full_rebuild=False)

            # delete_chunks_by_files should NOT have been called for deleted files
            # (it may be called for modified files, but not for deleted)
            # Since the file is unchanged, no deletion calls at all
            mock_store.delete_chunks_by_files.assert_not_called()

    async def test_deleted_files_are_logged(self, tmp_path):
        """Test that deleted files are properly logged."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "remaining.py").write_text("def remaining(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        log_messages: list[str] = []

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            mock_store.delete_chunks_by_files = AsyncMock(return_value=1)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            # Simulate previous index with a file that no longer exists
            prev_files_by_path: dict[str, FileInfo] = {
                "remaining.py": FileInfo(
                    path="remaining.py",
                    language=Language.PYTHON,
                    size_bytes=50,
                    last_modified=1.0,
                    hash="different_hash",
                ),
                "deleted_module.py": FileInfo(
                    path="deleted_module.py",
                    language=Language.PYTHON,
                    size_bytes=50,
                    last_modified=1.0,
                    hash="old_hash",
                ),
            }

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                _, _, deleted_file_paths = indexer._collect_files_to_process(
                    prev_files_by_path, None
                )

            assert "deleted_module.py" in deleted_file_paths
            # Check that the detection was logged
            detection_logs = [
                m for m in log_messages if "Detected" in m and "deleted" in m
            ]
            assert len(detection_logs) == 1
            assert "deleted_module.py" in detection_logs[0]


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

            # Should have called progress callback with "Indexing complete"
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

        # Create multiple files to ensure parallel parsing is used
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

            # Mock logger.info to capture messages
            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                await indexer.index(full_rebuild=True)

        # Check that performance logging occurred
        parsing_log = [m for m in log_messages if "Parallel parsing complete" in m]
        assert len(parsing_log) == 1

        # Verify the log contains key metrics
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
        # Use explicit worker count
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

            # Mock logger.info to capture messages
            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                await indexer.index(full_rebuild=True)

        # Check log mentions the correct worker count
        worker_log = [m for m in log_messages if "4 workers" in m]
        assert len(worker_log) >= 1

    async def test_parallel_parsing_handles_empty_file_list(self, tmp_path):
        """Test that parallel parsing handles empty file list gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # No files to process
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

            # Mock logger.info to capture messages
            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                status = await indexer.index(full_rebuild=True)

        # Should complete without errors
        assert status.total_files == 0
        assert status.total_chunks == 0

        # Should log "No files to parse"
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

            # Mock _parse_single_file to simulate one error
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

            # Mock logger.info to capture messages
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

        # Check that error count is logged
        parsing_log = [m for m in log_messages if "Parallel parsing complete" in m]
        assert len(parsing_log) == 1
        assert "1 errors" in parsing_log[0]


class TestASTCacheIntegration:
    """Tests for AST cache integration with RepositoryIndexer."""

    def test_indexer_creates_ast_cache_when_enabled(self, tmp_path):
        """Test that indexer creates AST cache when enabled in config."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # AST cache enabled by default
        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            assert indexer.ast_cache is not None
            assert isinstance(indexer.ast_cache, ASTCache)
            assert indexer.parser.cache is indexer.ast_cache

    def test_indexer_no_ast_cache_when_disabled(self, tmp_path):
        """Test that indexer does not create AST cache when disabled."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        ast_cache = ASTCacheConfig(enabled=False)
        config = Config().model_copy(
            update={"parsing": parsing, "ast_cache": ast_cache}
        )

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            assert indexer.ast_cache is None
            assert indexer.parser.cache is None

    def test_indexer_ast_cache_uses_config_values(self, tmp_path):
        """Test that AST cache uses configuration values."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        ast_cache = ASTCacheConfig(enabled=True, max_entries=500, ttl_seconds=1800)
        config = Config().model_copy(
            update={"parsing": parsing, "ast_cache": ast_cache}
        )

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

            assert indexer.ast_cache is not None
            # Check internal config by accessing private attributes
            assert indexer.ast_cache._max_entries == 500
            assert indexer.ast_cache._ttl_seconds == 1800

    async def test_indexer_logs_ast_cache_stats_after_indexing(self, tmp_path):
        """Test that indexer logs AST cache statistics after indexing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        log_messages = []

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(return_value=1)
            mock_store.add_chunks = AsyncMock(return_value=0)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            # Mock logger.info to capture messages
            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                await indexer.index(full_rebuild=True)

        # Check that AST cache stats were logged
        cache_log = [m for m in log_messages if "AST cache stats" in m]
        assert len(cache_log) == 1
        assert "hits=" in cache_log[0]
        assert "misses=" in cache_log[0]
        assert "hit_rate=" in cache_log[0]

    async def test_indexer_ast_cache_hit_on_unchanged_file(self, tmp_path):
        """Test that AST cache provides hits when parsing the same file."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            assert indexer.ast_cache is not None

            # First parse - should be a cache miss
            result1 = indexer.parser.parse_file(repo_path / "test.py")
            assert result1 is not None

            stats1 = indexer.ast_cache.get_stats()
            assert stats1["misses"] == 1
            assert stats1["hits"] == 0

            # Second parse of same file - should be a cache hit
            result2 = indexer.parser.parse_file(repo_path / "test.py")
            assert result2 is not None

            stats2 = indexer.ast_cache.get_stats()
            assert stats2["hits"] == 1
            assert stats2["misses"] == 1

    async def test_indexer_ast_cache_miss_on_modified_file(self, tmp_path):
        """Test that AST cache misses when file content changes."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "test.py").write_text("def test(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            assert indexer.ast_cache is not None

            # First parse
            result1 = indexer.parser.parse_file(repo_path / "test.py")
            assert result1 is not None

            stats1 = indexer.ast_cache.get_stats()
            assert stats1["misses"] == 1

            # Modify the file
            (repo_path / "test.py").write_text("def modified(): pass")

            # Second parse - should miss because content changed
            result2 = indexer.parser.parse_file(repo_path / "test.py")
            assert result2 is not None

            stats2 = indexer.ast_cache.get_stats()
            # Both should be misses since content is different
            assert stats2["misses"] == 2
            assert stats2["hits"] == 0
