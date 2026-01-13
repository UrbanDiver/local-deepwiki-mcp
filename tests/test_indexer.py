"""Tests for repository indexer with batched processing."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ChunkingConfig, Config
from local_deepwiki.core.indexer import (
    CURRENT_SCHEMA_VERSION,
    RepositoryIndexer,
    _migrate_status,
    _needs_migration,
)
from local_deepwiki.models import CodeChunk, IndexStatus, Language, ChunkType


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


class TestBatchedProcessing:
    """Tests for batched chunk processing in the indexer."""

    async def test_processes_chunks_in_batches(self, tmp_path):
        """Test that chunks are processed in batches to limit memory usage."""
        # Create a simple repo structure
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create multiple Python files to generate enough chunks
        for i in range(5):
            (repo_path / f"module{i}.py").write_text(f'''
def function_{i}_a():
    """Function A in module {i}."""
    pass

def function_{i}_b():
    """Function B in module {i}."""
    pass

def function_{i}_c():
    """Function C in module {i}."""
    pass
''')

        # Create config with small batch size
        config = Config()
        config.chunking.batch_size = 3  # Small batch size for testing
        config.parsing.languages = ["python"]

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

        # Create indexer with mocked vector store
        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(side_effect=mock_create_or_update_table)
            mock_store.add_chunks = AsyncMock(side_effect=mock_add_chunks)
            mock_store.delete_chunks_by_file = AsyncMock(side_effect=mock_delete_chunks_by_file)
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
        assert len(create_calls) == 1, "Should call create_or_update_table once for first batch"

        # Subsequent calls should be add_chunks
        assert len(add_calls) >= 1, "Should call add_chunks for subsequent batches"

        # Total chunks should match what we created
        assert status.total_chunks > 0

    async def test_incremental_update_with_batching(self, tmp_path):
        """Test that incremental updates work with batched processing."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Create initial files
        (repo_path / "module1.py").write_text('''
def function_a():
    pass

def function_b():
    pass
''')

        config = Config()
        config.chunking.batch_size = 2
        config.parsing.languages = ["python"]

        delete_calls = []
        add_calls = []

        async def mock_add_chunks(chunks):
            add_calls.append(len(chunks))
            return len(chunks)

        async def mock_delete_chunks_by_file(file_path):
            delete_calls.append(file_path)
            return 1

        async def mock_create_or_update_table(chunks):
            return len(chunks)

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            mock_store.create_or_update_table = AsyncMock(side_effect=mock_create_or_update_table)
            mock_store.add_chunks = AsyncMock(side_effect=mock_add_chunks)
            mock_store.delete_chunks_by_file = AsyncMock(side_effect=mock_delete_chunks_by_file)
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)
            indexer.vector_store = mock_store

            # First index (full rebuild)
            await indexer.index(full_rebuild=True)

            # Clear tracking
            delete_calls.clear()
            add_calls.clear()

            # Add another file
            (repo_path / "module2.py").write_text('''
def function_c():
    pass
''')

            # Run incremental update
            await indexer.index(full_rebuild=False)

        # For incremental updates, delete should be called per file
        # Note: with no previous status, all files are treated as new
        assert len(add_calls) >= 1, "Should add chunks in incremental update"

    async def test_empty_batch_handling(self, tmp_path):
        """Test that empty repositories are handled correctly."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        config = Config()
        config.chunking.batch_size = 10
        config.parsing.languages = ["python"]

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

        config = Config()
        config.parsing.languages = ["python"]

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

        config = Config()
        config.parsing.languages = ["python"]

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

        config = Config()
        config.parsing.languages = ["python"]

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
