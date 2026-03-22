"""Tests for graph extraction helpers and deleted-file cleanup in RepositoryIndexer."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import Config, ParsingConfig
from local_deepwiki.core.indexer import CURRENT_SCHEMA_VERSION, RepositoryIndexer
from local_deepwiki.models import FileInfo, IndexStatus, Language


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_indexer(repo_path, config):
    """Return a RepositoryIndexer with a mock VectorStore."""
    with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
        mock_store = MagicMock()
        MockVectorStore.return_value = mock_store
        indexer = RepositoryIndexer(repo_path, config)
    return indexer


# ---------------------------------------------------------------------------
# Deleted-file cleanup tests
# ---------------------------------------------------------------------------


class TestDeletedFileCleanup:
    """Tests for deleted file cleanup during incremental indexing."""

    def test_collect_files_detects_deleted_files(self, tmp_path):
        """Test that _collect_files_to_process detects files removed from disk."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        (repo_path / "module_a.py").write_text("def a(): pass")

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        with patch("local_deepwiki.core.indexer.VectorStore") as MockVectorStore:
            mock_store = MagicMock()
            MockVectorStore.return_value = mock_store

            indexer = RepositoryIndexer(repo_path, config)

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
                    indexer._status_tracker.collect_files_to_process(
                        prev_files_by_path, None
                    )
                )

            assert "module_b.py" in deleted_file_paths
            assert len(deleted_file_paths) == 1
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

            _, _, deleted_file_paths = indexer._status_tracker.collect_files_to_process(
                {}, None
            )

            assert deleted_file_paths == []

    async def test_deleted_files_chunks_removed_from_vector_store(self, tmp_path):
        """Test that chunks for deleted files are removed from the vector store."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

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

            status_path = indexer.wiki_path / "index_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(prev_status.model_dump_json())

            await indexer.index(full_rebuild=False)

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

            await indexer.index(full_rebuild=True)

            mock_store.delete_chunks_by_files.reset_mock()

            await indexer.index(full_rebuild=False)

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

                _, _, deleted_file_paths = (
                    indexer._status_tracker.collect_files_to_process(
                        prev_files_by_path, None
                    )
                )

            assert "deleted_module.py" in deleted_file_paths
            detection_logs = [
                m for m in log_messages if "Detected" in m and "deleted" in m
            ]
            assert len(detection_logs) == 1
            assert "deleted_module.py" in detection_logs[0]


# ---------------------------------------------------------------------------
# Graph helper method tests (Task 1)
# ---------------------------------------------------------------------------


class TestEmitGraphStart:
    """Tests for GraphExtractor.emit_graph_start helper."""

    async def test_emit_graph_start_fires_event(self, tmp_path):
        """Test that emit_graph_start emits the GRAPH_EXTRACT_START event."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        files = [repo_path / "a.py", repo_path / "b.py"]
        emitted_events = []

        with patch("local_deepwiki.core.indexer.get_event_emitter") as mock_get_emitter:
            mock_emitter = AsyncMock()
            mock_emitter.emit = AsyncMock(
                side_effect=lambda t, d: emitted_events.append((t, d))
            )
            mock_get_emitter.return_value = mock_emitter

            await indexer._graph_helper.emit_graph_start(files)

        assert len(emitted_events) == 1
        event_type, event_data = emitted_events[0]
        assert event_data["file_count"] == 2
        assert event_data["repo_path"] == str(repo_path)


class TestDeleteStaleGraphData:
    """Tests for GraphExtractor.delete_stale_graph_data helper."""

    async def test_skips_deletion_on_full_rebuild(self, tmp_path):
        """Test that incremental deletion is skipped during a full rebuild."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        indexer._graph_helper.graph_store = mock_graph_store
        indexer._graph_helper._graph_enabled = True

        file_a = repo_path / "a.py"
        file_a.write_text("def a(): pass")
        prev_files_by_path = {
            "a.py": FileInfo(
                path="a.py",
                language=Language.PYTHON,
                size_bytes=50,
                last_modified=1.0,
                hash="old",
            )
        }

        await indexer._graph_helper.delete_stale_graph_data(
            [file_a], prev_files_by_path, [], full_rebuild=True
        )

        mock_graph_store.delete_by_file.assert_not_called()

    async def test_deletes_modified_files_on_incremental(self, tmp_path):
        """Test that graph data for modified files is deleted in incremental mode."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        indexer._graph_helper.graph_store = mock_graph_store
        indexer._graph_helper._graph_enabled = True

        file_a = repo_path / "a.py"
        file_a.write_text("def a(): pass")
        prev_files_by_path = {
            "a.py": FileInfo(
                path="a.py",
                language=Language.PYTHON,
                size_bytes=50,
                last_modified=1.0,
                hash="old",
            )
        }

        await indexer._graph_helper.delete_stale_graph_data(
            [file_a], prev_files_by_path, [], full_rebuild=False
        )

        mock_graph_store.delete_by_file.assert_awaited_once_with("a.py")

    async def test_deletes_graph_data_for_deleted_files(self, tmp_path):
        """Test that graph data for deleted files is always removed."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        indexer._graph_helper.graph_store = mock_graph_store
        indexer._graph_helper._graph_enabled = True

        await indexer._graph_helper.delete_stale_graph_data(
            [], {}, ["gone.py", "also_gone.py"], full_rebuild=False
        )

        assert mock_graph_store.delete_by_file.await_count == 2

    async def test_logs_warning_on_delete_failure(self, tmp_path):
        """Test that a failed graph deletion logs a warning and does not raise."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        mock_graph_store.delete_by_file = AsyncMock(
            side_effect=RuntimeError("DB error")
        )
        indexer._graph_helper.graph_store = mock_graph_store
        indexer._graph_helper._graph_enabled = True

        # Should not raise
        with patch("local_deepwiki.core.indexer.logger") as mock_logger:
            await indexer._graph_helper.delete_stale_graph_data(
                [], {}, ["gone.py"], full_rebuild=False
            )
            mock_logger.warning.assert_called()


class TestExtractAndStoreGraphData:
    """Tests for GraphExtractor.extract_and_store_graph_data helper."""

    async def test_returns_zero_counts_when_no_graph_data(self, tmp_path):
        """Test that (0, 0) is returned when no graph data is extracted."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        indexer._graph_helper.graph_store = mock_graph_store

        with patch.object(
            indexer._graph_helper, "extract_graph_for_file", return_value=None
        ):
            file_a = repo_path / "a.py"
            file_a.write_text("def a(): pass")
            total_e, total_r = await indexer._graph_helper.extract_and_store_graph_data(
                [file_a], {}, None
            )

        assert total_e == 0
        assert total_r == 0

    async def test_accumulates_entity_and_relationship_counts(self, tmp_path):
        """Test that entity and relationship counts are summed across files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        mock_graph_store.add_entities = AsyncMock(return_value=3)
        mock_graph_store.add_relationships = AsyncMock(return_value=2)
        indexer._graph_helper.graph_store = mock_graph_store

        fake_graph_data = MagicMock()
        fake_graph_data.entities = [MagicMock(), MagicMock(), MagicMock()]
        fake_graph_data.relationships = [MagicMock(), MagicMock()]

        file_a = repo_path / "a.py"
        file_a.write_text("def a(): pass")
        file_b = repo_path / "b.py"
        file_b.write_text("def b(): pass")

        with patch.object(
            indexer._graph_helper,
            "extract_graph_for_file",
            return_value=fake_graph_data,
        ):
            total_e, total_r = await indexer._graph_helper.extract_and_store_graph_data(
                [file_a, file_b], {}, None
            )

        assert total_e == 6  # 3 per file x 2 files
        assert total_r == 4  # 2 per file x 2 files

    async def test_calls_progress_callback_per_file(self, tmp_path):
        """Test that progress callback is called once per file."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        mock_graph_store = AsyncMock()
        mock_graph_store.add_entities = AsyncMock(return_value=0)
        mock_graph_store.add_relationships = AsyncMock(return_value=0)
        indexer._graph_helper.graph_store = mock_graph_store

        fake_graph_data = MagicMock()
        fake_graph_data.entities = []
        fake_graph_data.relationships = []

        progress_calls = []

        def progress_callback(msg, current, total):
            progress_calls.append((msg, current, total))

        files = []
        for name in ["a.py", "b.py", "c.py"]:
            f = repo_path / name
            f.write_text(f"def {name[0]}(): pass")
            files.append(f)

        with patch.object(
            indexer._graph_helper,
            "extract_graph_for_file",
            return_value=fake_graph_data,
        ):
            await indexer._graph_helper.extract_and_store_graph_data(
                files, {}, progress_callback
            )

        assert len(progress_calls) == 3
        assert progress_calls[-1][1] == 3  # current = total on last call


class TestEmitGraphComplete:
    """Tests for GraphExtractor.emit_graph_complete helper."""

    async def test_emits_complete_event_and_logs(self, tmp_path):
        """Test that emit_graph_complete emits event and logs the summary."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        emitted_events = []
        log_messages = []

        with patch("local_deepwiki.core.indexer.get_event_emitter") as mock_get_emitter:
            mock_emitter = AsyncMock()
            mock_emitter.emit = AsyncMock(
                side_effect=lambda t, d: emitted_events.append((t, d))
            )
            mock_get_emitter.return_value = mock_emitter

            with patch("local_deepwiki.core.indexer.logger") as mock_logger:
                mock_logger.info = MagicMock(
                    side_effect=lambda msg, *args: log_messages.append(
                        msg % args if args else msg
                    )
                )

                await indexer._graph_helper.emit_graph_complete(
                    total_entities=5, total_relationships=10
                )

        assert len(emitted_events) == 1
        _, event_data = emitted_events[0]
        assert event_data["total_entities"] == 5
        assert event_data["total_relationships"] == 10

        complete_logs = [m for m in log_messages if "Graph extraction complete" in m]
        assert len(complete_logs) == 1
        assert "5" in complete_logs[0]
        assert "10" in complete_logs[0]


class TestRunGraphExtraction:
    """Integration tests for _run_graph_extraction orchestrator."""

    async def test_returns_early_when_graph_disabled(self, tmp_path):
        """Test that _run_graph_extraction exits immediately when graph is disabled."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        indexer._graph_enabled = False
        indexer.graph_store = None

        # Should complete silently
        await indexer._run_graph_extraction([], {}, {}, [], False, None)

    async def test_calls_all_helpers_in_order(self, tmp_path):
        """Test that _run_graph_extraction calls helper methods in the correct order."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
        config = Config().model_copy(update={"parsing": parsing})

        indexer = _make_indexer(repo_path, config)

        indexer._graph_enabled = True
        indexer.graph_store = AsyncMock()

        call_order = []

        async def mock_emit_start(files):
            call_order.append("emit_start")

        async def mock_delete_stale(files, prev, deleted, rebuild):
            call_order.append("delete_stale")

        async def mock_extract_store(files, chunks, cb, extract_fn=None):
            call_order.append("extract_store")
            return (7, 3)

        async def mock_emit_complete(entities, relationships):
            call_order.append("emit_complete")

        helper = indexer._graph_helper
        with (
            patch.object(helper, "emit_graph_start", side_effect=mock_emit_start),
            patch.object(
                helper, "delete_stale_graph_data", side_effect=mock_delete_stale
            ),
            patch.object(
                helper,
                "extract_and_store_graph_data",
                side_effect=mock_extract_store,
            ),
            patch.object(helper, "emit_graph_complete", side_effect=mock_emit_complete),
        ):
            await indexer._run_graph_extraction([], {}, {}, [], False, None)

        assert call_order == [
            "emit_start",
            "delete_stale",
            "extract_store",
            "emit_complete",
        ]
