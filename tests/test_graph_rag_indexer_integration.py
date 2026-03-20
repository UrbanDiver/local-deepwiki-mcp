"""Tests for GraphRAG integration into the indexing pipeline.

Verifies that the RepositoryIndexer correctly extracts graph entities and
relationships during indexing when GraphRAG is enabled, and properly skips
extraction when disabled.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.config import ChunkingConfig, Config, ParsingConfig
from local_deepwiki.config.models import GraphRAGConfig
from local_deepwiki.core.graph_rag.models import (
    EntityType,
    FileGraphData,
    GraphEntity,
    GraphRelationship,
    RelationshipType,
    entity_id,
    relationship_id,
)
from local_deepwiki.core.indexer import RepositoryIndexer
from local_deepwiki.events import EventType, get_event_emitter, reset_event_emitter
from local_deepwiki.models import ChunkType, CodeChunk, Language

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_python_file(repo_path: Path, name: str, content: str) -> Path:
    """Write a Python file to the repo and return its path."""
    file_path = repo_path / name
    file_path.write_text(content)
    return file_path


def _make_graph_rag_config(
    enabled: bool = True,
    extract_during_index: bool = True,
) -> GraphRAGConfig:
    """Create a GraphRAGConfig with the given settings."""
    return GraphRAGConfig(
        enabled=enabled,
        extract_during_index=extract_during_index,
    )


def _make_config(
    graph_rag: GraphRAGConfig | None = None,
) -> Config:
    """Create a test Config with graph_rag settings."""
    chunking = ChunkingConfig().model_copy(
        update={"batch_size": 50, "parallel_workers": 1}
    )
    parsing = ParsingConfig().model_copy(update={"languages": ["python"]})
    updates: dict = {"chunking": chunking, "parsing": parsing}
    if graph_rag is not None:
        updates["graph_rag"] = graph_rag
    return Config().model_copy(update=updates)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_events():
    """Reset the global event emitter between tests."""
    reset_event_emitter()
    yield
    reset_event_emitter()


@pytest.fixture()
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repository directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


@pytest.fixture()
def simple_python_source() -> str:
    """A small Python source file with a class and function."""
    return (
        "def greet(name):\n"
        "    return f'Hello {name}'\n"
        "\n"
        "class Greeter:\n"
        "    def say_hello(self):\n"
        "        return greet('world')\n"
    )


# ---------------------------------------------------------------------------
# Test: GraphRAG disabled (default)
# ---------------------------------------------------------------------------


class TestGraphDisabledByDefault:
    """Verify that graph extraction does not run when disabled."""

    async def test_graph_store_not_created_when_disabled(self, repo_path: Path):
        config = _make_config(graph_rag=_make_graph_rag_config(enabled=False))
        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        assert indexer.graph_store is None
        assert indexer._graph_extractor is None
        assert indexer._graph_enabled is False

    async def test_graph_store_not_created_when_extract_during_index_false(
        self, repo_path: Path
    ):
        config = _make_config(
            graph_rag=_make_graph_rag_config(
                enabled=True,
                extract_during_index=False,
            )
        )
        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        assert indexer.graph_store is None
        assert indexer._graph_extractor is None
        assert indexer._graph_enabled is False

    async def test_no_graph_events_when_disabled(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=False))

        emitter = get_event_emitter()
        events_captured: list[EventType] = []

        @emitter.on(EventType.GRAPH_EXTRACT_START)
        def on_start(event):
            events_captured.append(event.type)

        @emitter.on(EventType.GRAPH_EXTRACT_COMPLETE)
        def on_complete(event):
            events_captured.append(event.type)

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            await indexer.index(full_rebuild=True)

        assert events_captured == []


# ---------------------------------------------------------------------------
# Test: GraphRAG enabled — initialization
# ---------------------------------------------------------------------------


class TestGraphEnabledInit:
    """Verify indexer creates graph store and extractor when enabled."""

    async def test_graph_store_created_when_enabled(self, repo_path: Path):
        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))
        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        assert indexer.graph_store is not None
        assert indexer._graph_extractor is not None
        assert indexer._graph_enabled is True

    async def test_graph_store_uses_same_db_path(self, repo_path: Path):
        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))
        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        assert indexer.graph_store is not None
        assert indexer.graph_store.db_path == indexer.vector_db_path


# ---------------------------------------------------------------------------
# Test: Graph extraction during indexing
# ---------------------------------------------------------------------------


class TestGraphExtractionDuringIndex:
    """Verify graph extraction runs during indexing when enabled."""

    async def test_graph_events_emitted(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        emitter = get_event_emitter()
        events_captured: list[tuple[EventType, dict]] = []

        @emitter.on(EventType.GRAPH_EXTRACT_START)
        def on_start(event):
            events_captured.append((event.type, dict(event.data)))

        @emitter.on(EventType.GRAPH_EXTRACT_COMPLETE)
        def on_complete(event):
            events_captured.append((event.type, dict(event.data)))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            # Mock graph store to capture calls
            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(
                side_effect=lambda entities: len(entities)
            )
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            await indexer.index(full_rebuild=True)

        # Verify both events were emitted in order
        event_types = [e[0] for e in events_captured]
        assert EventType.GRAPH_EXTRACT_START in event_types
        assert EventType.GRAPH_EXTRACT_COMPLETE in event_types
        start_idx = event_types.index(EventType.GRAPH_EXTRACT_START)
        complete_idx = event_types.index(EventType.GRAPH_EXTRACT_COMPLETE)
        assert start_idx < complete_idx

    async def test_entities_and_relationships_stored(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            # Mock graph store to capture calls
            entities_added: list[list] = []
            relationships_added: list[list] = []

            async def capture_entities(entities):
                entities_added.append(list(entities))
                return len(entities)

            async def capture_relationships(rels):
                relationships_added.append(list(rels))
                return len(rels)

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(side_effect=capture_entities)
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=capture_relationships
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            await indexer.index(full_rebuild=True)

        # Should have added entities (greet function, Greeter class, say_hello method)
        assert len(entities_added) > 0
        all_entities = [e for batch in entities_added for e in batch]
        entity_names = {e.name for e in all_entities}
        assert "greet" in entity_names
        assert "Greeter" in entity_names
        assert "say_hello" in entity_names

        # Should have added relationships (calls, contains, etc.)
        assert len(relationships_added) > 0

    async def test_progress_callback_called_for_graph_extraction(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        progress_messages: list[str] = []

        def progress_callback(msg: str, current: int, total: int) -> None:
            progress_messages.append(msg)

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(
                side_effect=lambda entities: len(entities)
            )
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            await indexer.index(
                full_rebuild=True,
                progress_callback=progress_callback,
            )

        graph_messages = [m for m in progress_messages if "graph" in m.lower()]
        assert len(graph_messages) > 0

    async def test_graph_complete_event_contains_counts(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        emitter = get_event_emitter()
        complete_data: list[dict] = []

        @emitter.on(EventType.GRAPH_EXTRACT_COMPLETE)
        def on_complete(event):
            complete_data.append(dict(event.data))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(
                side_effect=lambda entities: len(entities)
            )
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            await indexer.index(full_rebuild=True)

        assert len(complete_data) == 1
        assert "total_entities" in complete_data[0]
        assert "total_relationships" in complete_data[0]
        assert complete_data[0]["total_entities"] > 0


# ---------------------------------------------------------------------------
# Test: Graph extraction non-blocking
# ---------------------------------------------------------------------------


class TestGraphExtractionNonBlocking:
    """Verify graph extraction failures don't crash indexing."""

    async def test_extraction_failure_does_not_fail_indexing(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            # Make graph store raise an exception
            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(
                side_effect=RuntimeError("DB connection lost")
            )
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=RuntimeError("DB connection lost")
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            # Should NOT raise — graph failures are non-blocking
            status = await indexer.index(full_rebuild=True)

        assert status.total_files > 0

    async def test_complete_graph_phase_failure_does_not_fail_indexing(
        self, repo_path: Path, simple_python_source: str
    ):
        """Test that even if _run_graph_extraction itself raises, indexing continues."""
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
            patch.object(
                RepositoryIndexer,
                "_run_graph_extraction",
                side_effect=RuntimeError("Graph phase crashed"),
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            # Should NOT raise
            status = await indexer.index(full_rebuild=True)

        assert status.total_files > 0


# ---------------------------------------------------------------------------
# Test: Incremental re-indexing with graph
# ---------------------------------------------------------------------------


class TestGraphIncrementalReindex:
    """Verify graph data is cleaned up for modified and deleted files."""

    async def test_deletes_graph_data_for_modified_files(self, repo_path: Path):
        _write_python_file(repo_path, "main.py", "def old_func():\n    pass\n")

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        deleted_files: list[str] = []

        async def capture_delete(file_path):
            deleted_files.append(file_path)

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(
                side_effect=lambda entities: len(entities)
            )
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            mock_graph_store.delete_by_file = AsyncMock(side_effect=capture_delete)
            indexer.graph_store = mock_graph_store

            # Simulate incremental re-index: provide prev_files_by_path
            # with "main.py" already indexed (different hash triggers re-process)
            from conftest import make_file_info

            prev_file = make_file_info(
                path="main.py",
                hash="old_hash_that_differs",
                language=Language.PYTHON,
            )

            # Call _run_graph_extraction directly for targeted testing
            files_to_process = [repo_path / "main.py"]
            file_chunks: dict = {"main.py": []}
            prev_files_by_path = {"main.py": prev_file}

            await indexer._run_graph_extraction(
                files_to_process=files_to_process,
                file_chunks=file_chunks,
                prev_files_by_path=prev_files_by_path,
                deleted_file_paths=[],
                full_rebuild=False,
                progress_callback=None,
            )

        # Should have deleted old graph data for the modified file
        assert "main.py" in deleted_files

    async def test_deletes_graph_data_for_deleted_files(self, repo_path: Path):
        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        deleted_files: list[str] = []

        async def capture_delete(file_path):
            deleted_files.append(file_path)

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(return_value=0)
            mock_graph_store.add_relationships = AsyncMock(return_value=0)
            mock_graph_store.delete_by_file = AsyncMock(side_effect=capture_delete)
            indexer.graph_store = mock_graph_store

            await indexer._run_graph_extraction(
                files_to_process=[],
                file_chunks={},
                prev_files_by_path={},
                deleted_file_paths=["removed.py", "old/module.py"],
                full_rebuild=False,
                progress_callback=None,
            )

        assert "removed.py" in deleted_files
        assert "old/module.py" in deleted_files

    async def test_no_delete_on_full_rebuild(self, repo_path: Path):
        _write_python_file(repo_path, "main.py", "def func():\n    pass\n")

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(
                side_effect=lambda entities: len(entities)
            )
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            from conftest import make_file_info

            prev_file = make_file_info(
                path="main.py",
                hash="old_hash",
                language=Language.PYTHON,
            )

            await indexer._run_graph_extraction(
                files_to_process=[repo_path / "main.py"],
                file_chunks={"main.py": []},
                prev_files_by_path={"main.py": prev_file},
                deleted_file_paths=[],
                full_rebuild=True,
                progress_callback=None,
            )

        # On full rebuild, delete_by_file should NOT be called
        # (because prev_files_by_path is only used when not full_rebuild)
        mock_graph_store.delete_by_file.assert_not_called()


# ---------------------------------------------------------------------------
# Test: _extract_graph_for_file
# ---------------------------------------------------------------------------


class TestExtractGraphForFile:
    """Test the per-file graph extraction helper."""

    async def test_returns_file_graph_data(
        self, repo_path: Path, simple_python_source: str
    ):
        file_path = _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        result = indexer._graph_helper.extract_graph_for_file(file_path, [])

        assert result is not None
        assert isinstance(result, FileGraphData)
        assert result.file_path == "main.py"
        assert len(result.entities) > 0

        entity_names = {e.name for e in result.entities}
        assert "greet" in entity_names
        assert "Greeter" in entity_names

    async def test_returns_none_for_unsupported_file(self, repo_path: Path):
        txt_file = repo_path / "readme.txt"
        txt_file.write_text("Just some text.")

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        result = indexer._graph_helper.extract_graph_for_file(txt_file, [])
        assert result is None

    async def test_links_entities_to_chunks(self, repo_path: Path):
        source = "def my_func():\n    return 42\n"
        file_path = _write_python_file(repo_path, "main.py", source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        # Create a matching chunk
        chunk = CodeChunk(
            id="chunk-123",
            file_path="main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="my_func",
            content=source,
            start_line=1,
            end_line=2,
        )

        result = indexer._graph_helper.extract_graph_for_file(file_path, [chunk])

        assert result is not None
        func_entities = [e for e in result.entities if e.name == "my_func"]
        assert len(func_entities) == 1
        assert func_entities[0].chunk_id == "chunk-123"

    async def test_returns_none_when_graph_disabled(self, repo_path: Path):
        source = "def func():\n    pass\n"
        file_path = _write_python_file(repo_path, "main.py", source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=False))

        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        result = indexer._graph_helper.extract_graph_for_file(file_path, [])
        assert result is None

    async def test_handles_extraction_error_gracefully(self, repo_path: Path):
        source = "def func():\n    pass\n"
        file_path = _write_python_file(repo_path, "main.py", source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed:
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)

        # Make the extractor raise an error
        mock_extractor = MagicMock()
        mock_extractor.extract_from_ast.side_effect = RuntimeError("Parse error")
        indexer._graph_helper._graph_extractor = mock_extractor

        result = indexer._graph_helper.extract_graph_for_file(file_path, [])
        assert result is None


# ---------------------------------------------------------------------------
# Test: _parse_files_parallel collects chunks when graph enabled
# ---------------------------------------------------------------------------


class TestParseFilesParallelChunkCollection:
    """Verify that _parse_files_parallel collects per-file chunks."""

    async def test_collects_chunks_when_graph_enabled(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()

            files = [repo_path / "main.py"]
            _, _, file_chunks = await indexer._parse_files_parallel(
                files, full_rebuild=True, progress_callback=None
            )

        assert "main.py" in file_chunks
        assert len(file_chunks["main.py"]) > 0

    async def test_empty_chunks_when_graph_disabled(
        self, repo_path: Path, simple_python_source: str
    ):
        _write_python_file(repo_path, "main.py", simple_python_source)

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=False))

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()

            files = [repo_path / "main.py"]
            _, _, file_chunks = await indexer._parse_files_parallel(
                files, full_rebuild=True, progress_callback=None
            )

        # When graph is disabled, file_chunks should be empty
        assert file_chunks == {}


# ---------------------------------------------------------------------------
# Test: Multiple files
# ---------------------------------------------------------------------------


class TestGraphExtractionMultipleFiles:
    """Verify graph extraction handles multiple files correctly."""

    async def test_extracts_from_multiple_files(self, repo_path: Path):
        _write_python_file(
            repo_path,
            "module_a.py",
            "def func_a():\n    return 1\n",
        )
        _write_python_file(
            repo_path,
            "module_b.py",
            "class MyClass:\n    def method_b(self):\n        pass\n",
        )

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        entities_by_call: list[list] = []

        async def capture_entities(entities):
            entities_by_call.append(list(entities))
            return len(entities)

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()
            indexer.vector_store.create_or_update_table = AsyncMock()
            indexer.vector_store.add_chunks = AsyncMock()
            indexer.vector_store.delete_chunks_by_files = AsyncMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(side_effect=capture_entities)
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            mock_graph_store.delete_by_file = AsyncMock()
            indexer.graph_store = mock_graph_store

            await indexer.index(full_rebuild=True)

        # Should have entities from both files
        all_entities = [e for batch in entities_by_call for e in batch]
        entity_names = {e.name for e in all_entities}
        assert "func_a" in entity_names
        assert "MyClass" in entity_names
        assert "method_b" in entity_names


# ---------------------------------------------------------------------------
# Test: delete_by_file failure is non-blocking
# ---------------------------------------------------------------------------


class TestDeleteByFileFailure:
    """Verify that delete_by_file failures during incremental reindex are non-blocking."""

    async def test_delete_failure_does_not_stop_extraction(self, repo_path: Path):
        _write_python_file(repo_path, "main.py", "def func():\n    pass\n")

        config = _make_config(graph_rag=_make_graph_rag_config(enabled=True))

        entities_added: list[list] = []

        async def capture_entities(entities):
            entities_added.append(list(entities))
            return len(entities)

        with (
            patch("local_deepwiki.core.indexer.get_embedding_provider") as mock_embed,
            patch(
                "local_deepwiki.core.indexer.scan_repository_for_secrets",
                return_value={},
            ),
        ):
            mock_embed.return_value = MagicMock()
            indexer = RepositoryIndexer(repo_path, config=config)
            indexer.vector_store = MagicMock()

            mock_graph_store = MagicMock()
            mock_graph_store.add_entities = AsyncMock(side_effect=capture_entities)
            mock_graph_store.add_relationships = AsyncMock(
                side_effect=lambda rels: len(rels)
            )
            # delete_by_file will raise but should not block extraction
            mock_graph_store.delete_by_file = AsyncMock(
                side_effect=RuntimeError("Delete failed")
            )
            indexer.graph_store = mock_graph_store

            from conftest import make_file_info

            prev_file = make_file_info(
                path="main.py",
                hash="old_hash",
                language=Language.PYTHON,
            )

            # Should NOT raise
            await indexer._run_graph_extraction(
                files_to_process=[repo_path / "main.py"],
                file_chunks={"main.py": []},
                prev_files_by_path={"main.py": prev_file},
                deleted_file_paths=[],
                full_rebuild=False,
                progress_callback=None,
            )

        # Should still have extracted entities despite delete failure
        assert len(entities_added) > 0
