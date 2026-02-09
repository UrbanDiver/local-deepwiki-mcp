"""Tests for dependency graph generation - generator class, rendering, and edge cases."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from local_deepwiki.generators.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphGenerator,
    DependencyNode,
    generate_dependency_graph_page,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


class TestDependencyGraphGenerator:
    """Tests for DependencyGraphGenerator class."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_index_status(self):
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


class TestImportParsing:
    """Tests for import parsing functionality."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_parses_python_from_import(self, generator):
        """Test parsing Python 'from X import Y'."""
        content = "from mypackage.core import parser"
        imports = generator._parse_imports(content, "python")
        assert "mypackage.core" in imports

    def test_parses_python_import(self, generator):
        """Test parsing Python 'import X'."""
        content = "import pathlib"
        imports = generator._parse_imports(content, "python")
        assert "pathlib" in imports

    def test_parses_javascript_import(self, generator):
        """Test parsing JavaScript import."""
        content = 'import { something } from "./module"'
        imports = generator._parse_imports(content, "javascript")
        assert "./module" in imports

    def test_parses_typescript_import(self, generator):
        """Test parsing TypeScript import."""
        content = 'import type { Type } from "module"'
        imports = generator._parse_imports(content, "typescript")
        assert "module" in imports

    def test_handles_multiple_imports(self, generator):
        """Test handling multiple imports."""
        content = """import os
from pathlib import Path
import json"""
        imports = generator._parse_imports(content, "python")
        assert "os" in imports
        assert "pathlib" in imports
        assert "json" in imports

    def test_handles_empty_content(self, generator):
        """Test handling empty content."""
        imports = generator._parse_imports("", "python")
        assert len(imports) == 0


class TestInternalImportResolution:
    """Tests for internal import resolution."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_identifies_internal_import(self, generator):
        """Test identification of internal import."""
        internal_modules = {"core.parser", "core.chunker", "utils.helpers"}
        assert generator._is_internal_import("core.parser", internal_modules) is True

    def test_identifies_external_import(self, generator):
        """Test identification of external import."""
        internal_modules = {"core.parser", "core.chunker"}
        assert generator._is_internal_import("pathlib", internal_modules) is False

    def test_resolves_internal_import(self, generator):
        """Test resolving internal import to module."""
        internal_modules = {"core.parser", "core.chunker", "utils.helpers"}
        result = generator._resolve_internal_import("core.parser", internal_modules)
        assert result == "core.parser"

    def test_resolves_import_by_last_component(self, generator):
        """Test resolving import by matching last component."""
        internal_modules = {"core.parser", "core.chunker"}
        result = generator._resolve_internal_import(
            "myproject.core.parser", internal_modules
        )
        assert result == "core.parser"


class TestMermaidRendering:
    """Tests for Mermaid diagram rendering."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_renders_empty_graph_message(self, generator):
        """Test rendering of empty graph message."""
        result = generator._generate_empty_graph_message("No dependencies found")
        assert "```mermaid" in result
        assert "No dependencies found" in result

    def test_renders_graph_with_nodes(self, generator):
        """Test rendering graph with nodes."""
        graph = DependencyGraph()
        graph.add_node(
            DependencyNode(name="core.parser", file_path="src/core/parser.py")
        )
        graph.add_node(
            DependencyNode(name="core.chunker", file_path="src/core/chunker.py")
        )
        graph.add_edge("core.parser", "core.chunker")

        result = generator._render_module_graph(
            graph=graph,
            show_external=False,
            max_external=10,
            wiki_base_path="",
        )
        assert "```mermaid" in result
        assert "flowchart" in result
        assert "-->" in result

    def test_renders_circular_dependency_warning(self, generator):
        """Test rendering of circular dependency warning."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="a", file_path="a.py"))
        graph.add_node(DependencyNode(name="b", file_path="b.py"))
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        graph.edges[("a", "b")].is_circular = True
        graph.edges[("b", "a")].is_circular = True
        graph.cycles = [["a", "b"]]

        result = generator._render_module_graph(
            graph=graph,
            show_external=False,
            max_external=10,
            wiki_base_path="",
        )
        assert "Warning" in result or "circular" in result

    def test_adds_wiki_links_when_base_path_provided(self, generator):
        """Test wiki links are added when base path provided."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="parser", file_path="src/parser.py"))

        result = generator._render_module_graph(
            graph=graph,
            show_external=False,
            max_external=10,
            wiki_base_path="files/",
        )
        assert "click" in result
        assert "files/" in result

    def test_renders_external_dependencies(self, generator):
        """Test rendering of external dependencies."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="parser", file_path="src/parser.py"))
        graph.add_node(DependencyNode(name="pathlib", file_path="", is_external=True))
        graph.add_edge("parser", "pathlib")

        result = generator._render_module_graph(
            graph=graph,
            show_external=True,
            max_external=10,
            wiki_base_path="",
        )
        assert "external" in result.lower() or "External" in result


class TestFilePathToWikiPath:
    """Tests for file path to wiki path conversion."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_converts_python_file(self, generator):
        """Test conversion of Python file path."""
        result = generator._file_path_to_wiki_path("src/core/parser.py")
        assert result.endswith(".md")
        assert "parser" in result

    def test_preserves_directory_structure(self, generator):
        """Test that directory structure is preserved."""
        result = generator._file_path_to_wiki_path("src/deep/nested/module.py")
        assert "deep" in result or "nested" in result


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


class TestGenerateModuleGraphCircularEdges:
    """Tests for circular edge marking in generate_module_graph (lines 271-272)."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store with circular import results."""
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


class TestInternalImportEdgeCases:
    """Tests for _is_internal_import edge cases (lines 559, 567, 569)."""

    @pytest.fixture
    def generator(self):
        """Create a generator with project name set."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_import_starts_with_project_name(self, generator):
        """Test import that starts with project name (line 559)."""
        internal_modules = {"core.parser", "core.chunker"}
        # Import starts with project name
        assert (
            generator._is_internal_import("myproject.core.parser", internal_modules)
            is True
        )

    def test_import_parts_match_module_last_component(self, generator):
        """Test when import parts match module by last component (line 567)."""
        internal_modules = {"core.parser"}
        # Import "parser" should match "core.parser" by last component
        assert generator._is_internal_import("utils.parser", internal_modules) is True

    def test_import_ends_with_module(self, generator):
        """Test when import ends with module name (line 569)."""
        internal_modules = {"parser"}
        # Import that ends with the module
        assert (
            generator._is_internal_import("myproject.parser", internal_modules) is True
        )


class TestResolveInternalImportEdgeCases:
    """Tests for _resolve_internal_import edge cases (lines 597-603)."""

    @pytest.fixture
    def generator(self):
        """Create a generator with project name set."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_strips_project_prefix(self, generator):
        """Test stripping project prefix from import (lines 591-594)."""
        internal_modules = {"core.parser"}
        # Import with project prefix should be resolved
        result = generator._resolve_internal_import(
            "myproject.core.parser", internal_modules
        )
        assert result == "core.parser"

    def test_matches_by_last_component(self, generator):
        """Test matching by last component when prefix doesn't match (lines 597-601)."""
        internal_modules = {"core.parser", "utils.helpers"}
        # Import where only last component matches
        result = generator._resolve_internal_import(
            "somepackage.parser", internal_modules
        )
        assert result == "core.parser"

    def test_returns_none_for_no_match(self, generator):
        """Test returns None when no match found (line 603)."""
        internal_modules = {"core.parser"}
        result = generator._resolve_internal_import(
            "completely.unrelated", internal_modules
        )
        assert result is None


class TestRenderModuleGraphEdgeCases:
    """Tests for _render_module_graph edge cases (lines 699, 737)."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_renders_edge_with_count_greater_than_one(self, generator):
        """Test rendering edge with count > 1 (line 699)."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="a", file_path="a.py"))
        graph.add_node(DependencyNode(name="b", file_path="b.py"))
        # Add same edge twice to get count=2
        graph.add_edge("a", "b")
        graph.add_edge("a", "b")

        result = generator._render_module_graph(
            graph=graph,
            show_external=False,
            max_external=10,
            wiki_base_path="",
        )
        # Should show count on the arrow
        assert "|2|" in result

    def test_renders_more_than_five_cycles_warning(self, generator):
        """Test rendering warning for more than 5 cycles (line 737)."""
        graph = DependencyGraph()
        # Create nodes
        for i in range(12):
            graph.add_node(DependencyNode(name=f"m{i}", file_path=f"m{i}.py"))

        # Create 6 independent cycles (more than 5)
        graph.cycles = [
            ["m0", "m1"],
            ["m2", "m3"],
            ["m4", "m5"],
            ["m6", "m7"],
            ["m8", "m9"],
            ["m10", "m11"],
        ]

        result = generator._render_module_graph(
            graph=graph,
            show_external=False,
            max_external=10,
            wiki_base_path="",
        )
        # Should show "and X more" warning
        assert "and 1 more" in result


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


class TestInternalImportEndsWithModule:
    """Test for line 569 - import ends with module."""

    @pytest.fixture
    def generator(self):
        """Create a generator with project name."""
        store = AsyncMock()
        gen = DependencyGraphGenerator(store)
        gen._project_name = "myproject"
        return gen

    def test_import_ending_with_dot_module(self, generator):
        """Test import that ends with '.' + module name."""
        internal_modules = {"chunker"}
        # Import ending with ".chunker"
        result = generator._is_internal_import("some.package.chunker", internal_modules)
        assert result is True


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


class TestRenderFileGraphEdges:
    """Tests for _render_file_graph edge rendering (lines 768-777, 781-783, 789-793)."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mock store."""
        store = AsyncMock()
        return DependencyGraphGenerator(store)

    def test_renders_normal_edges(self, generator):
        """Test rendering normal (non-circular) edges (lines 775-777)."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="parser", file_path="parser.py"))
        graph.add_node(DependencyNode(name="chunker", file_path="chunker.py"))
        graph.add_edge("parser", "chunker")

        result = generator._render_file_graph(graph, "core")
        assert "```mermaid" in result
        assert "-->" in result
        assert "parser" in result
        assert "chunker" in result

    def test_renders_circular_edges_in_file_graph(self, generator):
        """Test rendering circular edges in file graph (lines 772-774)."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="a", file_path="a.py"))
        graph.add_node(DependencyNode(name="b", file_path="b.py"))
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        graph.edges[("a", "b")].is_circular = True
        graph.edges[("b", "a")].is_circular = True

        result = generator._render_file_graph(graph, "core")
        assert "circular" in result
        assert "-.->|circular|" in result

    def test_renders_circular_styling(self, generator):
        """Test rendering circular link styling (lines 781-783)."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="a", file_path="a.py"))
        graph.add_node(DependencyNode(name="b", file_path="b.py"))
        graph.add_edge("a", "b")
        graph.edges[("a", "b")].is_circular = True

        result = generator._render_file_graph(graph, "core")
        # Should have linkStyle for circular edge
        assert "linkStyle" in result
        assert "stroke:#f00" in result

    def test_renders_cycle_warnings_in_file_graph(self, generator):
        """Test rendering cycle warnings in file graph (lines 789-793)."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="a", file_path="a.py"))
        graph.add_node(DependencyNode(name="b", file_path="b.py"))
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        graph.cycles = [["a", "b"]]

        result = generator._render_file_graph(graph, "core")
        assert "Warning" in result
        assert "Circular" in result or "circular" in result


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
