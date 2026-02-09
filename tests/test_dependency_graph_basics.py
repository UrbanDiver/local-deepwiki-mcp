"""Tests for dependency graph basics - utility functions and data structures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from local_deepwiki.generators.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphGenerator,
    DependencyNode,
    _extract_module_name,
    _get_directory_module,
    _is_test_path,
    _sanitize_mermaid_name,
)


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
        result = _extract_module_name(
            "src/myproject/core/parser.py", "/path/to/myproject"
        )
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


class TestGetDirectoryModuleEdgeCases:
    """Additional tests for _get_directory_module edge cases."""

    def test_returns_root_for_file_in_src(self):
        """Test returns 'root' when file is directly in src."""
        # After skipping 'src', parts is empty, should return 'root'
        result = _get_directory_module("src/module.py")
        assert result == "root"

    def test_returns_root_for_lib_file(self):
        """Test returns 'root' for file in lib directory."""
        result = _get_directory_module("lib/utils.py")
        assert result == "root"

    def test_returns_single_directory_part(self):
        """Test returns single directory when exactly one part exists (line 211)."""
        # For path 'foo/module.py', parts = ['foo'], len(parts) == 1
        # Should return 'foo'
        result = _get_directory_module("mymodule/utils.py")
        assert result == "mymodule"

    def test_returns_custom_directory(self):
        """Test returns directory name for non-standard structure."""
        # Path that doesn't start with skip_dirs
        result = _get_directory_module("custom/module.py")
        assert result == "custom"
