"""Tests for Mermaid rendering, visualization, and file path conversion."""

from __future__ import annotations

import dataclasses

import pytest
from unittest.mock import AsyncMock

from local_deepwiki.generators.analysis.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphGenerator,
    DependencyNode,
)


@pytest.fixture
def generator():
    """Create a generator with mock store."""
    store = AsyncMock()
    return DependencyGraphGenerator(store)


class TestMermaidRendering:
    """Tests for Mermaid diagram rendering."""

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
        graph.edges[("a", "b")] = dataclasses.replace(
            graph.edges[("a", "b")], is_circular=True
        )
        graph.edges[("b", "a")] = dataclasses.replace(
            graph.edges[("b", "a")], is_circular=True
        )
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

    def test_converts_python_file(self, generator):
        """Test conversion of Python file path."""
        result = generator._file_path_to_wiki_path("src/core/parser.py")
        assert result.endswith(".md")
        assert "parser" in result

    def test_preserves_directory_structure(self, generator):
        """Test that directory structure is preserved."""
        result = generator._file_path_to_wiki_path("src/deep/nested/module.py")
        assert "deep" in result or "nested" in result


class TestRenderModuleGraphEdgeCases:
    """Tests for _render_module_graph edge cases (lines 699, 737)."""

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


class TestRenderFileGraphEdges:
    """Tests for _render_file_graph edge rendering (lines 768-777, 781-783, 789-793)."""

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
        graph.edges[("a", "b")] = dataclasses.replace(
            graph.edges[("a", "b")], is_circular=True
        )
        graph.edges[("b", "a")] = dataclasses.replace(
            graph.edges[("b", "a")], is_circular=True
        )

        result = generator._render_file_graph(graph, "core")
        assert "circular" in result
        assert "-.->|circular|" in result

    def test_renders_circular_styling(self, generator):
        """Test rendering circular link styling (lines 781-783)."""
        graph = DependencyGraph()
        graph.add_node(DependencyNode(name="a", file_path="a.py"))
        graph.add_node(DependencyNode(name="b", file_path="b.py"))
        graph.add_edge("a", "b")
        graph.edges[("a", "b")] = dataclasses.replace(
            graph.edges[("a", "b")], is_circular=True
        )

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
