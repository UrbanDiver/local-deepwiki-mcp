"""Tests for RepositoryIndexer file handling, status loading, and error handling."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ChunkingConfig, Config, ParsingConfig
from local_deepwiki.core.indexer import (
    CURRENT_SCHEMA_VERSION,
    RepositoryIndexer,
    _delete_old_chunks_for_modified_files,
)
from local_deepwiki.models import FileInfo, IndexStatus, Language


class TestParseFileErrors:
    """Tests for error handling in _parse_single_file."""

    def test_parse_single_file_oserror(self, tmp_path):
        """Test that OSError in _parse_single_file returns error result."""
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

            status, requires_rebuild = indexer._status_tracker.load_status()

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

            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text("not valid json {{{")

            status, requires_rebuild = indexer._status_tracker.load_status()

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

            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps({"not_a_valid_field": "value"}))

            status, requires_rebuild = indexer._status_tracker.load_status()

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


class TestFindSourceFiles:
    """Tests for _find_source_files filtering logic."""

    def test_find_source_files_excludes_pattern_match(self, tmp_path):
        """Test that files matching exclude patterns are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

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

            file_names = [f.name for f in files]
            assert "test.pyc" not in file_names
            assert "test.py" in file_names

    def test_find_source_files_excludes_large_files(self, tmp_path):
        """Test that files exceeding max_file_size are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

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

            original_stat = Path.stat

            def mock_stat(self):
                if self.name == "test.py":
                    raise OSError("Permission denied")
                return original_stat(self)

            with patch.object(Path, "stat", mock_stat):
                files = indexer._find_source_files()

                assert len(files) == 0

    def test_find_source_files_skips_unknown_language(self, tmp_path):
        """Test that files with undetectable language are skipped."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

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

            await _delete_old_chunks_for_modified_files(
                mock_store,
                indexer.parser,
                indexer.repo_path,
                files_to_process,
                prev_files_by_path,
                progress_callback,
            )

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

            with patch.object(indexer, "_parse_single_file", mock_parse_single_file):
                files_to_process = [repo_path / "good.py", repo_path / "bad.py"]
                (
                    processed_files,
                    total_chunks,
                    _file_chunks,
                ) = await indexer._parse_files_parallel(
                    files_to_process,
                    full_rebuild=True,
                    progress_callback=progress_callback,
                )

            assert len(processed_files) == 1
            assert processed_files[0].path == "good.py"
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

            status, prev_files, rebuild = indexer._status_tracker.load_previous_status(
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

            status, prev_files, rebuild = indexer._status_tracker.load_previous_status(
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

            with patch.object(
                indexer._status_manager,
                "load_with_migration_info",
                return_value=(None, True),
            ):
                status, prev_files, rebuild = (
                    indexer._status_tracker.load_previous_status(full_rebuild=False)
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
                indexer._status_tracker.collect_files_to_process({}, progress_callback)
            )

            assert any("Found source files" in msg for msg in progress_messages)
            assert any("Processing" in msg for msg in progress_messages)
            assert deleted_file_paths == []
