"""Tests for RepositoryIndexer configuration and initialization."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ASTCacheConfig, ChunkingConfig, Config, ParsingConfig
from local_deepwiki.core.index_manager import _migrate_status, _needs_migration
from local_deepwiki.core.indexer import CURRENT_SCHEMA_VERSION, RepositoryIndexer
from local_deepwiki.core.parser import ASTCache
from local_deepwiki.models import IndexStatus


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

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

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

            status, requires_rebuild = indexer._load_status()

            if CURRENT_SCHEMA_VERSION > 1:
                with open(status_path) as f:
                    saved_data = json.load(f)
                assert saved_data["schema_version"] == CURRENT_SCHEMA_VERSION


class TestEmbeddingProviderOverride:
    """Tests for embedding provider override in constructor."""

    def test_embedding_provider_override(self, tmp_path):
        """Test that embedding_provider_name overrides the config provider."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        assert config.embedding.provider == "local"

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            with patch(
                "local_deepwiki.core.indexer.get_embedding_provider"
            ) as MockGetProvider:
                mock_provider = MagicMock()
                MockGetProvider.return_value = mock_provider

                indexer = RepositoryIndexer(
                    repo_path, config, embedding_provider_name="openai"
                )

                assert indexer.config.embedding.provider == "openai"
                MockGetProvider.assert_called_once()
                call_config = MockGetProvider.call_args[0][0]
                assert call_config.provider == "openai"


class TestASTCacheIntegration:
    """Tests for AST cache integration with RepositoryIndexer."""

    def test_indexer_creates_ast_cache_when_enabled(self, tmp_path):
        """Test that indexer creates AST cache when enabled in config."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

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

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )
                mock_logger.warning = MagicMock()
                mock_logger.debug = MagicMock()

                await indexer.index(full_rebuild=True)

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

            result1 = indexer.parser.parse_file(repo_path / "test.py")
            assert result1 is not None

            stats1 = indexer.ast_cache.get_stats()
            assert stats1["misses"] == 1
            assert stats1["hits"] == 0

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

            result1 = indexer.parser.parse_file(repo_path / "test.py")
            assert result1 is not None

            stats1 = indexer.ast_cache.get_stats()
            assert stats1["misses"] == 1

            (repo_path / "test.py").write_text("def modified(): pass")

            result2 = indexer.parser.parse_file(repo_path / "test.py")
            assert result2 is not None

            stats2 = indexer.ast_cache.get_stats()
            assert stats2["misses"] == 2
