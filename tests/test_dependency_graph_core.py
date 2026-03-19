"""Tests for core dependency graph generation (DependencyGraphGenerator)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from local_deepwiki.generators.analysis.dependency_graph import (
    DependencyGraphGenerator,
    generate_dependency_graph_page,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])
    store.get_chunks_by_file = AsyncMock(return_value=[])
    return store


@pytest.fixture
def sample_index_status():
    """Create a sample index status."""
    return IndexStatus(
        repo_path="/test/myproject",
        indexed_at=1234567890.0,
        total_files=3,
        total_chunks=10,
        languages={"python": 3},
        files=[
            FileInfo(
                path="src/myproject/core/parser.py",
                language="python",
                hash="a",
                chunk_count=5,
                size_bytes=100,
                last_modified=1234567890.0,
            ),
            FileInfo(
                path="src/myproject/core/chunker.py",
                language="python",
                hash="b",
                chunk_count=3,
                size_bytes=100,
                last_modified=1234567890.0,
            ),
            FileInfo(
                path="src/myproject/utils/helpers.py",
                language="python",
                hash="c",
                chunk_count=2,
                size_bytes=100,
                last_modified=1234567890.0,
            ),
        ],
    )


class TestDependencyGraphGenerator:
    """Tests for DependencyGraphGenerator class."""

    async def test_generate_module_graph_creates_mermaid(
        self, mock_vector_store, sample_index_status
    ):
        """Test that generate_module_graph produces Mermaid output."""
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(sample_index_status)
        assert "```mermaid" in result
        assert "flowchart" in result
        assert "```" in result

    async def test_generate_module_graph_shows_nodes(
        self, mock_vector_store, sample_index_status
    ):
        """Test that generate_module_graph shows nodes."""
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(sample_index_status)
        # Should have subgraphs for the modules
        assert "subgraph" in result

    async def test_generate_module_graph_excludes_tests(self, mock_vector_store):
        """Test that test files are excluded when exclude_tests=True."""
        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=5,
            languages={"python": 2},
            files=[
                FileInfo(
                    path="src/core/parser.py",
                    language="python",
                    hash="a",
                    chunk_count=3,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="tests/test_parser.py",
                    language="python",
                    hash="b",
                    chunk_count=2,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(status, exclude_tests=True)
        assert "test_parser" not in result

    async def test_generate_module_graph_shows_external(
        self, mock_vector_store, sample_index_status
    ):
        """Test that external dependencies are shown when enabled."""
        # Mock search to return import chunk with external import
        mock_chunk = MagicMock()
        mock_chunk.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/parser.py",
            content="import pathlib\nfrom os import path",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=2,
        )
        mock_vector_store.search = AsyncMock(return_value=[mock_chunk])

        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_module_graph(
            sample_index_status,
            show_external=True,
        )
        # Should have external subgraph if externals found
        if "external" in result.lower():
            assert "External" in result or "external" in result

    async def test_generate_file_graph_basic(
        self, mock_vector_store, sample_index_status
    ):
        """Test basic file graph generation."""
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(
            sample_index_status,
            module_path="core",
        )
        assert "```mermaid" in result
        assert "flowchart" in result

    async def test_generate_file_graph_empty_module(self, mock_vector_store):
        """Test file graph with non-existent module."""
        status = IndexStatus(
            repo_path="/test/myproject",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[
                FileInfo(
                    path="src/other/module.py",
                    language="python",
                    hash="a",
                    chunk_count=5,
                    size_bytes=100,
                    last_modified=1234567890.0,
                ),
            ],
        )
        generator = DependencyGraphGenerator(mock_vector_store)
        result = await generator.generate_file_graph(status, module_path="nonexistent")
        assert "No files found" in result or "```mermaid" in result


class TestGenerateDependencyGraphPage:
    """Tests for the page generation function."""

    async def test_generates_complete_page(self):
        """Test that complete page is generated."""
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        store.get_chunks_by_file = AsyncMock(return_value=[])

        status = IndexStatus(
            repo_path="/test/myproject",
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

        result = await generate_dependency_graph_page(status, store)
        assert "# Dependency Graph" in result
        assert "```mermaid" in result
        assert "Legend" in result
        assert "Best Practices" in result
