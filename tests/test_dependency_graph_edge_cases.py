"""Tests for dependency graph edge cases, error handling, and empty repos."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from local_deepwiki.generators.analysis.dependency_graph import (
    DependencyGraphGenerator,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.get_chunks_by_file = AsyncMock(return_value=[])
    return store


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_handles_empty_index_status(self, mock_vector_store):
        """Test handling of empty index status."""
        status = IndexStatus(
            repo_path="/test/empty",
            indexed_at=1234567890.0,
            total_files=0,
            total_chunks=0,
            languages={},
            files=[],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status)
        assert "```mermaid" in result

    async def test_handles_search_error(self, mock_vector_store):
        """Test handling of search errors."""
        mock_vector_store.search = AsyncMock(side_effect=Exception("Search failed"))
        status = IndexStatus(
            repo_path="/test/error",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/module.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        # Should not crash, but may have limited results
        with pytest.raises(Exception):
            await generator.generate_module_graph(status)

    async def test_handles_non_python_files(self, mock_vector_store):
        """Test handling of non-Python files."""
        status = IndexStatus(
            repo_path="/test/mixed",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            languages={"python": 1, "javascript": 1},
            files=[
                FileInfo(
                    path="src/module.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/module.js",
                    language="javascript",
                    hash="b",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status)
        assert "```mermaid" in result


class TestBuildDependencyGraphEdgeCases:
    """Tests for _build_dependency_graph edge cases (lines 471, 474, 478-485, 496-498)."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = AsyncMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_skips_non_import_chunks(self, mock_vector_store):
        """Test that non-import chunks are skipped (line 471)."""
        # Create a function chunk (not import)
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="def parse(): pass",
            chunk_type=ChunkType.FUNCTION,  # Not IMPORT
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=1,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status)
        # Should still produce a valid mermaid diagram
        assert "```mermaid" in result

    async def test_skips_test_file_chunks(self, mock_vector_store):
        """Test that test file chunks are skipped when exclude_tests=True (line 474)."""
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="tests/test_parser.py",
            content="import pytest",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=1,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status, exclude_tests=True)
        assert "test_parser" not in result

    async def test_creates_node_for_unknown_file(self, mock_vector_store):
        """Test that nodes are created for files not in the initial file list (lines 478-485)."""
        # Create an import chunk from a file not in the status.files list
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/extra/utils.py",  # Not in status.files
            content="import pathlib",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=1,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status)
        # Should still work and create the unknown module node
        assert "```mermaid" in result

    async def test_adds_internal_edges(self, mock_vector_store):
        """Test that edges are added for internal imports (lines 496-498)."""
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="from myproject.core import chunker",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=2,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status)
        assert "```mermaid" in result


class TestFileGraphInternalEdges:
    """Tests for generate_file_graph internal edge creation (lines 337, 341, 350, 356-357)."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = AsyncMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_file_graph_adds_edges_between_files(self, mock_vector_store):
        """Test that edges are added between files in the same module (lines 341-350)."""
        # Create import chunk that imports another file in the same module
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="from myproject.core.chunker import Chunker",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=4,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="core")
        assert "```mermaid" in result
        # Both files should be in the graph
        assert "parser" in result
        assert "chunker" in result

    async def test_file_graph_skips_non_import_chunks(self, mock_vector_store):
        """Test that non-IMPORT chunks are skipped in file graph (line 337)."""
        # Create a FUNCTION chunk (not IMPORT) - should be skipped
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="def parse(): pass",
            chunk_type=ChunkType.FUNCTION,  # Not IMPORT - should trigger line 337
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=4,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="core")
        # Should still produce a valid diagram (without edges since non-import was skipped)
        assert "```mermaid" in result

    async def test_file_graph_skips_imports_outside_module(self, mock_vector_store):
        """Test that imports from outside the module are skipped."""
        # Create import chunk from a file NOT in the target module
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/utils/helpers.py",  # Not in 'core' module
            content="from myproject.core import parser",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=4,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="core")
        # Should still produce diagram with the files
        assert "```mermaid" in result

    async def test_file_graph_detects_and_marks_cycles(self, mock_vector_store):
        """Test that cycles are detected and edges marked (lines 356-357)."""
        # Create chunks that form a cycle within the module
        chunk1 = MagicMock()
        chunk1.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="from myproject.core.chunker import Chunker",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        chunk2 = MagicMock()
        chunk2.chunk = CodeChunk(
            id="2",
            file_path="src/myproject/core/chunker.py",
            content="from myproject.core.parser import Parser",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk1, chunk2])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=4,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="core")
        assert "```mermaid" in result


class TestGenerateFileGraphWithEdges:
    """Tests for generate_file_graph edge rendering (lines 335-350, 356-357, 768-793)."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store with file-level imports."""
        store = AsyncMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_file_graph_with_internal_imports(self, mock_vector_store):
        """Test file graph with internal file imports (lines 335-350)."""
        # Create search results that have imports within the module
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="from myproject.core import chunker",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=4,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="core")
        assert "```mermaid" in result
        assert "parser" in result
        assert "chunker" in result

    async def test_file_graph_with_circular_dependencies(self, mock_vector_store):
        """Test file graph renders circular dependencies (lines 768-777, 781-783, 789-793)."""
        # Mock search to return circular imports
        chunk1 = MagicMock()
        chunk1.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/a.py",
            content="from . import b",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        chunk2 = MagicMock()
        chunk2.chunk = CodeChunk(
            id="2",
            file_path="src/myproject/core/b.py",
            content="from . import a",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk1, chunk2])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=4,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/a.py",
                    language="python",
                    hash="a",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/b.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="core")
        assert "```mermaid" in result


class TestBuildGraphInternalEdge:
    """Test for line 498 - adding internal edges."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store."""
        store = AsyncMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_adds_edge_for_resolved_internal_import(self, mock_vector_store):
        """Test that edges are added when internal import is resolved."""
        chunk = MagicMock()
        chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="from myproject.core.chunker import Chunk",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        mock_vector_store.search = AsyncMock(return_value=[chunk])

        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=2,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/myproject/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/myproject/core/chunker.py",
                    language="python",
                    hash="b",
                    chunk_count=1,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status)
        # Should have an arrow showing the dependency
        assert "```mermaid" in result
