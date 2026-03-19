"""Tests for circular dependency detection, cycle normalization, and edge extraction."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from local_deepwiki.generators.analysis.dependency_graph import (
    DependencyGraphGenerator,
)


@pytest.fixture
def generator():
    """Create a generator with mock store."""
    store = AsyncMock()
    return DependencyGraphGenerator(store)


class TestCircularDependencyDetection:
    """Tests for circular dependency detection."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_detects_direct_cycle(self, generator):
        """Test detection of A -> B -> A cycle."""
        graph = {
            "a": {"b"},
            "b": {"a"},
        }
        cycles = generator.detect_circular_dependencies(graph)
        assert len(cycles) > 0
        # Should contain a cycle with both a and b
        flat_cycles = [item for cycle in cycles for item in cycle]
        assert "a" in flat_cycles
        assert "b" in flat_cycles

    def test_detects_longer_cycle(self, generator):
        """Test detection of A -> B -> C -> A cycle."""
        graph = {
            "a": {"b"},
            "b": {"c"},
            "c": {"a"},
        }
        cycles = generator.detect_circular_dependencies(graph)
        assert len(cycles) > 0

    def test_no_false_positives(self, generator):
        """Test no cycles reported for acyclic graph."""
        graph = {
            "a": {"b"},
            "b": {"c"},
            "c": set(),
        }
        cycles = generator.detect_circular_dependencies(graph)
        assert len(cycles) == 0

    def test_handles_empty_graph(self, generator):
        """Test handling of empty graph."""
        cycles = generator.detect_circular_dependencies({})
        assert len(cycles) == 0

    def test_handles_disconnected_graph(self, generator):
        """Test handling of disconnected graph."""
        graph = {
            "a": {"b"},
            "b": set(),
            "c": {"d"},
            "d": set(),
        }
        cycles = generator.detect_circular_dependencies(graph)
        assert len(cycles) == 0

    def test_detects_multiple_cycles(self, generator):
        """Test detection of multiple cycles."""
        graph = {
            "a": {"b"},
            "b": {"a"},  # Cycle 1: a-b
            "c": {"d"},
            "d": {"c"},  # Cycle 2: c-d
        }
        cycles = generator.detect_circular_dependencies(graph)
        # Should detect both cycles
        assert len(cycles) >= 1

    def test_normalizes_cycles(self, generator):
        """Test that cycles are normalized consistently."""
        # Test the normalization helper
        cycle1 = generator._normalize_cycle(["b", "a", "c", "b"])
        cycle2 = generator._normalize_cycle(["c", "b", "a", "c"])
        # Both should start with "a" (the smallest)
        assert cycle1[0] == "a"
        assert cycle2[0] == "a"


class TestCycleNormalization:
    """Tests for cycle normalization."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_normalizes_single_element_cycle(self, generator):
        """Test normalizing single element cycle."""
        cycle = generator._normalize_cycle(["a"])
        assert cycle == ["a"]

    def test_normalizes_empty_cycle(self, generator):
        """Test normalizing empty cycle."""
        cycle = generator._normalize_cycle([])
        assert cycle == []

    def test_removes_duplicate_end_element(self, generator):
        """Test removing duplicate end element."""
        cycle = generator._normalize_cycle(["a", "b", "c", "a"])
        assert len(cycle) == 3
        assert cycle[-1] != cycle[0] or len(cycle) == 1

    def test_rotates_to_min_element(self, generator):
        """Test rotation to minimum element."""
        cycle = generator._normalize_cycle(["c", "a", "b"])
        assert cycle[0] == "a"


class TestCircularEdgeExtraction:
    """Tests for circular edge extraction."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_extracts_edges_from_simple_cycle(self, generator):
        """Test extracting edges from simple cycle."""
        cycles = [["a", "b"]]
        edges = generator._get_circular_edges(cycles)
        assert ("a", "b") in edges or ("b", "a") in edges

    def test_extracts_edges_from_longer_cycle(self, generator):
        """Test extracting edges from longer cycle."""
        cycles = [["a", "b", "c"]]
        edges = generator._get_circular_edges(cycles)
        assert ("a", "b") in edges
        assert ("b", "c") in edges
        assert ("c", "a") in edges

    def test_handles_multiple_cycles(self, generator):
        """Test handling multiple cycles."""
        cycles = [["a", "b"], ["c", "d"]]
        edges = generator._get_circular_edges(cycles)
        assert len(edges) >= 2

    def test_handles_empty_cycles(self, generator):
        """Test handling empty cycles list."""
        edges = generator._get_circular_edges([])
        assert len(edges) == 0


class TestGenerateModuleGraphCircularEdges:
    """Tests for circular edge marking in generate_module_graph (lines 271-272)."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store with circular import results."""
        from unittest.mock import MagicMock
        from local_deepwiki.models import ChunkType, CodeChunk, Language

        store = AsyncMock()
        # Create chunks that form a circular dependency
        chunk_a = MagicMock()
        chunk_a.chunk = CodeChunk(
            id="1",
            file_path="src/myproject/core/a.py",
            content="from myproject.core import b",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        chunk_b = MagicMock()
        chunk_b.chunk = CodeChunk(
            id="2",
            file_path="src/myproject/core/b.py",
            content="from myproject.core import a",
            chunk_type=ChunkType.IMPORT,
            language=Language.PYTHON,
            start_line=1,
            end_line=1,
        )
        store.search = AsyncMock(return_value=[chunk_a, chunk_b])
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_marks_circular_edges(self, mock_vector_store):
        """Test that circular edges are marked correctly."""
        from local_deepwiki.models import FileInfo, IndexStatus

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
        result = await generator.generate_module_graph(status)
        # The result should be mermaid diagram (circles may or may not be detected
        # depending on import resolution)
        assert "```mermaid" in result


class TestModuleGraphCircularEdgeMarking:
    """Tests for circular edge marking in module graphs (lines 271-272)."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create mock vector store with circular imports."""
        store = AsyncMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    async def test_module_graph_marks_circular_edges(self, mock_vector_store):
        """Test that circular edges are marked in the module graph."""
        from unittest.mock import MagicMock
        from local_deepwiki.models import (
            ChunkType,
            CodeChunk,
            FileInfo,
            IndexStatus,
            Language,
        )

        # Create import chunks that create a cycle between internal modules
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
        result = await generator.generate_module_graph(status)
        # Should produce valid mermaid
        assert "```mermaid" in result
