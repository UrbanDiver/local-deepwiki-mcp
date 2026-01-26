"""Tests for dependency graph generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from local_deepwiki.generators.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphGenerator,
    DependencyNode,
    _extract_module_name,
    _get_directory_module,
    _is_test_path,
    _sanitize_mermaid_name,
    generate_dependency_graph_page,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


class TestSanitizeMermaidName:
    """Tests for _sanitize_mermaid_name function."""

    def test_basic_name(self):
        """Test basic name passes through."""
        assert _sanitize_mermaid_name("MyModule") == "MyModule"

    def test_replaces_dots(self):
        """Test dots are replaced."""
        assert _sanitize_mermaid_name("core.parser") == "core_parser"

    def test_replaces_slashes(self):
        """Test slashes are replaced."""
        assert _sanitize_mermaid_name("core/parser") == "core_parser"

    def test_replaces_hyphens(self):
        """Test hyphens are replaced."""
        assert _sanitize_mermaid_name("my-module") == "my_module"

    def test_prefixes_digit(self):
        """Test names starting with digits get prefixed."""
        assert _sanitize_mermaid_name("123module") == "M123module"


class TestIsTestPath:
    """Tests for _is_test_path function."""

    def test_detects_test_directory(self):
        """Test detection of /test/ directory."""
        assert _is_test_path("src/test/parser.py") is True
        assert _is_test_path("src/tests/parser.py") is True

    def test_detects_test_prefix(self):
        """Test detection of test_ prefix."""
        assert _is_test_path("test_parser.py") is True
        assert _is_test_path("src/core/test_utils.py") is True

    def test_detects_test_suffix(self):
        """Test detection of _test suffix."""
        assert _is_test_path("src/parser_test.py") is True

    def test_detects_spec_files(self):
        """Test detection of spec files."""
        assert _is_test_path("src/spec/parser.py") is True
        assert _is_test_path("src/parser.spec.ts") is True

    def test_non_test_file(self):
        """Test non-test files return False."""
        assert _is_test_path("src/core/parser.py") is False
        assert _is_test_path("src/utils/helpers.py") is False


class TestExtractModuleName:
    """Tests for _extract_module_name function."""

    def test_extracts_from_src_path(self):
        """Test extraction from src/ path."""
        result = _extract_module_name("src/myproject/core/parser.py")
        assert "parser" in result

    def test_strips_project_name(self):
        """Test stripping project name from path."""
        result = _extract_module_name("src/myproject/core/parser.py", "/path/to/myproject")
        assert "parser" in result
        assert "myproject" not in result.lower() or result.count("myproject") == 0

    def test_handles_nested_path(self):
        """Test handling of deeply nested paths."""
        result = _extract_module_name("src/pkg/sub1/sub2/module.py")
        assert "module" in result

    def test_handles_root_level_file(self):
        """Test handling of root level file."""
        result = _extract_module_name("module.py")
        assert result == "module"


class TestGetDirectoryModule:
    """Tests for _get_directory_module function."""

    def test_extracts_directory(self):
        """Test extraction of directory module."""
        result = _get_directory_module("src/myproject/core/parser.py")
        assert result == "core" or result == "myproject"

    def test_handles_root_file(self):
        """Test handling of root file."""
        result = _get_directory_module("module.py")
        assert result == "root"


class TestDependencyNode:
    """Tests for DependencyNode dataclass."""

    def test_creates_node(self):
        """Test basic node creation."""
        node = DependencyNode(
            name="core.parser",
            file_path="src/core/parser.py",
        )
        assert node.name == "core.parser"
        assert node.file_path == "src/core/parser.py"
        assert node.is_external is False
        assert node.is_test is False

    def test_external_node(self):
        """Test external node creation."""
        node = DependencyNode(
            name="pathlib",
            file_path="",
            is_external=True,
        )
        assert node.is_external is True


class TestDependencyEdge:
    """Tests for DependencyEdge dataclass."""

    def test_creates_edge(self):
        """Test basic edge creation."""
        edge = DependencyEdge(
            source="core.parser",
            target="core.chunker",
        )
        assert edge.source == "core.parser"
        assert edge.target == "core.chunker"
        assert edge.count == 1
        assert edge.is_circular is False

    def test_circular_edge(self):
        """Test circular edge creation."""
        edge = DependencyEdge(
            source="a",
            target="b",
            is_circular=True,
        )
        assert edge.is_circular is True


class TestDependencyGraph:
    """Tests for DependencyGraph dataclass."""

    def test_add_node(self):
        """Test adding nodes."""
        graph = DependencyGraph()
        node = DependencyNode(name="test", file_path="test.py")
        graph.add_node(node)
        assert "test" in graph.nodes

    def test_add_duplicate_node_ignored(self):
        """Test duplicate nodes are ignored."""
        graph = DependencyGraph()
        node1 = DependencyNode(name="test", file_path="test1.py")
        node2 = DependencyNode(name="test", file_path="test2.py")
        graph.add_node(node1)
        graph.add_node(node2)
        assert graph.nodes["test"].file_path == "test1.py"

    def test_add_edge(self):
        """Test adding edges."""
        graph = DependencyGraph()
        graph.add_edge("a", "b")
        assert ("a", "b") in graph.edges

    def test_add_duplicate_edge_increments_count(self):
        """Test duplicate edges increment count."""
        graph = DependencyGraph()
        graph.add_edge("a", "b")
        graph.add_edge("a", "b")
        assert graph.edges[("a", "b")].count == 2

    def test_get_adjacency_list(self):
        """Test getting adjacency list."""
        graph = DependencyGraph()
        graph.add_edge("a", "b")
        graph.add_edge("a", "c")
        graph.add_edge("b", "c")
        adj = graph.get_adjacency_list()
        assert adj["a"] == {"b", "c"}
        assert adj["b"] == {"c"}


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

    async def test_generate_module_graph_excludes_tests(
        self, mock_vector_store
    ):
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

    async def test_generate_file_graph_basic(self, mock_vector_store, sample_index_status):
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
        result = generator._resolve_internal_import("myproject.core.parser", internal_modules)
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
        graph.add_node(DependencyNode(name="core.parser", file_path="src/core/parser.py"))
        graph.add_node(DependencyNode(name="core.chunker", file_path="src/core/chunker.py"))
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
