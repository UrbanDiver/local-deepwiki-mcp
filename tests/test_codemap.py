"""Tests for the codemap MCP tools: generate_codemap and suggest_codemap_topics.

Tests cover:
- Pydantic args model validation (GenerateCodemapArgs, SuggestCodemapTopicsArgs)
- Data structure behavior (CodemapNode, CodemapEdge, CodemapGraph, CodemapResult)
- Generator unit tests (discover_entry_points, build_cross_file_graph, generate_codemap_diagram)
- Handler integration tests (handle_generate_codemap, handle_suggest_codemap_topics)
- Narrative generation and topic suggestion
"""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.handlers import (
    handle_generate_codemap,
    handle_suggest_codemap_topics,
)
from local_deepwiki.models import (
    CodemapFocusType,
    GenerateCodemapArgs,
    SuggestCodemapTopicsArgs,
)


# ── Args model validation tests ──────────────────────────────────────


class TestGenerateCodemapArgs:
    def test_valid_args(self):
        args = GenerateCodemapArgs(
            repo_path="/tmp/repo",
            query="How does authentication work?",
        )
        assert args.repo_path == "/tmp/repo"
        assert args.query == "How does authentication work?"
        assert args.focus == CodemapFocusType.EXECUTION_FLOW

    def test_empty_query_rejected(self):
        with pytest.raises(Exception):
            GenerateCodemapArgs(repo_path="/tmp/repo", query="")

    def test_query_too_long(self):
        long_query = "x" * 2001
        with pytest.raises(Exception):
            GenerateCodemapArgs(repo_path="/tmp/repo", query=long_query)

    def test_query_at_max_length(self):
        max_query = "x" * 2000
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query=max_query)
        assert len(args.query) == 2000

    def test_max_depth_bounds(self):
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_depth=1)
        assert args.max_depth == 1
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_depth=10)
        assert args.max_depth == 10
        with pytest.raises(Exception):
            GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_depth=0)
        with pytest.raises(Exception):
            GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_depth=11)

    def test_max_nodes_bounds(self):
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_nodes=5)
        assert args.max_nodes == 5
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_nodes=60)
        assert args.max_nodes == 60
        with pytest.raises(Exception):
            GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_nodes=4)
        with pytest.raises(Exception):
            GenerateCodemapArgs(repo_path="/tmp/repo", query="test", max_nodes=61)

    def test_focus_enum_validation(self):
        for focus in CodemapFocusType:
            args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test", focus=focus)
            assert args.focus == focus
        with pytest.raises(Exception):
            GenerateCodemapArgs(
                repo_path="/tmp/repo", query="test", focus="invalid_focus"
            )

    def test_entry_point_optional(self):
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test")
        assert args.entry_point is None
        args = GenerateCodemapArgs(
            repo_path="/tmp/repo",
            query="test",
            entry_point="handle_request",
        )
        assert args.entry_point == "handle_request"

    def test_defaults(self):
        args = GenerateCodemapArgs(repo_path="/tmp/repo", query="test")
        assert args.focus == CodemapFocusType.EXECUTION_FLOW
        assert args.max_depth == 5
        assert args.max_nodes == 30
        assert args.entry_point is None


class TestSuggestCodemapTopicsArgs:
    def test_valid_args(self):
        args = SuggestCodemapTopicsArgs(repo_path="/tmp/repo")
        assert args.repo_path == "/tmp/repo"
        assert args.max_suggestions == 10

    def test_max_suggestions_bounds(self):
        args = SuggestCodemapTopicsArgs(repo_path="/tmp/repo", max_suggestions=1)
        assert args.max_suggestions == 1
        args = SuggestCodemapTopicsArgs(repo_path="/tmp/repo", max_suggestions=30)
        assert args.max_suggestions == 30
        with pytest.raises(Exception):
            SuggestCodemapTopicsArgs(repo_path="/tmp/repo", max_suggestions=0)
        with pytest.raises(Exception):
            SuggestCodemapTopicsArgs(repo_path="/tmp/repo", max_suggestions=31)


# ── Data structure tests ─────────────────────────────────────────────


class TestCodemapDataStructures:
    def test_codemap_node_frozen(self):
        from local_deepwiki.generators.codemap import CodemapNode

        node = CodemapNode(
            name="my_func",
            qualified_name="module.my_func",
            file_path="src/module.py",
            start_line=10,
            end_line=20,
            chunk_type="function",
            docstring="Does something.",
            content_preview="def my_func(): ...",
        )
        assert node.name == "my_func"
        assert node.qualified_name == "module.my_func"
        with pytest.raises(FrozenInstanceError):
            node.name = "other"

    def test_codemap_edge_frozen(self):
        from local_deepwiki.generators.codemap import CodemapEdge

        edge = CodemapEdge(
            source="module.func_a",
            target="module.func_b",
            edge_type="calls",
            source_file="src/a.py",
            target_file="src/b.py",
        )
        assert edge.source == "module.func_a"
        assert edge.target == "module.func_b"
        with pytest.raises(FrozenInstanceError):
            edge.source = "other"

    def test_codemap_graph_cross_file_edges(self):
        from local_deepwiki.generators.codemap import (
            CodemapEdge,
            CodemapGraph,
            CodemapNode,
        )

        nodes = {
            "a.func": CodemapNode(
                name="func",
                qualified_name="a.func",
                file_path="src/a.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
            "b.func": CodemapNode(
                name="func",
                qualified_name="b.func",
                file_path="src/b.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
        }
        edges = [
            CodemapEdge(
                source="a.func",
                target="b.func",
                edge_type="calls",
                source_file="src/a.py",
                target_file="src/b.py",
            ),
            CodemapEdge(
                source="a.func",
                target="a.func",
                edge_type="calls",
                source_file="src/a.py",
                target_file="src/a.py",
            ),
        ]
        graph = CodemapGraph(nodes=nodes, edges=edges, entry_point="a.func")
        cross = graph.cross_file_edges
        assert len(cross) == 1
        assert cross[0].source == "a.func"
        assert cross[0].target == "b.func"

    def test_codemap_graph_files_involved(self):
        from local_deepwiki.generators.codemap import CodemapGraph, CodemapNode

        nodes = {
            "a.func": CodemapNode(
                name="func",
                qualified_name="a.func",
                file_path="src/a.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
            "b.func": CodemapNode(
                name="func",
                qualified_name="b.func",
                file_path="src/b.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
            "b.helper": CodemapNode(
                name="helper",
                qualified_name="b.helper",
                file_path="src/b.py",
                start_line=10,
                end_line=15,
                chunk_type="function",
            ),
        }
        graph = CodemapGraph(nodes=nodes, edges=[], entry_point=None)
        files = graph.files_involved
        assert sorted(files) == ["src/a.py", "src/b.py"]

    def test_codemap_graph_empty(self):
        from local_deepwiki.generators.codemap import CodemapGraph

        graph = CodemapGraph(nodes={}, edges=[], entry_point=None)
        assert graph.cross_file_edges == []
        assert graph.files_involved == set()

    def test_codemap_result_serialization(self):
        from local_deepwiki.generators.codemap import CodemapResult

        result = CodemapResult(
            query="How does auth work?",
            focus="execution_flow",
            entry_point="handle_login",
            mermaid_diagram="graph TD\n    A-->B",
            narrative="The auth flow starts at handle_login.",
            nodes=[{"name": "handle_login", "file": "auth.py"}],
            edges=[{"source": "A", "target": "B"}],
            files_involved=["auth.py", "session.py"],
            total_nodes=2,
            total_edges=1,
            cross_file_edges=1,
        )
        assert result.query == "How does auth work?"
        assert result.total_nodes == 2
        assert result.total_edges == 1
        assert result.cross_file_edges == 1
        assert len(result.files_involved) == 2


# ── Generator unit tests ─────────────────────────────────────────────


def _make_mock_search_result(
    name="my_func",
    file_path="src/module.py",
    start_line=10,
    end_line=25,
    chunk_type="function",
    content="def my_func(): pass",
    docstring="A function.",
    parent_name=None,
    score=0.9,
):
    """Create a mock search result matching the VectorStore.search return type."""
    chunk = MagicMock()
    chunk.name = name
    chunk.file_path = file_path
    chunk.start_line = start_line
    chunk.end_line = end_line
    chunk.chunk_type = MagicMock(value=chunk_type)
    chunk.content = content
    chunk.docstring = docstring
    chunk.parent_name = parent_name

    result = MagicMock()
    result.chunk = chunk
    result.score = score
    return result


def _make_mock_code_chunk(
    name="my_func",
    file_path="src/module.py",
    start_line=10,
    end_line=25,
    chunk_type="function",
    content="def my_func(): pass",
    docstring="A function.",
    parent_name=None,
):
    """Create a mock CodeChunk for vector store get_all_chunks.

    Uses a real ChunkType enum value so that identity comparisons like
    ``chunk.chunk_type == ChunkType.IMPORT`` work correctly.
    """
    from local_deepwiki.models import ChunkType

    chunk = MagicMock()
    chunk.name = name
    chunk.file_path = file_path
    chunk.start_line = start_line
    chunk.end_line = end_line
    # Use the actual ChunkType enum so both .value and identity checks work
    chunk.chunk_type = ChunkType(chunk_type)
    chunk.content = content
    chunk.docstring = docstring
    chunk.parent_name = parent_name
    return chunk


class TestDiscoverEntryPoints:
    async def test_with_hint(self, tmp_path):
        from local_deepwiki.generators.codemap import discover_entry_points

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="handle_request",
                    file_path="src/server.py",
                    start_line=5,
                    end_line=20,
                ),
            ]
        )

        nodes = await discover_entry_points(
            query="request handling",
            vector_store=mock_vs,
            repo_path=tmp_path,
            entry_point_hint="handle_request",
        )
        assert len(nodes) >= 1
        assert any(n.name == "handle_request" for n in nodes)
        mock_vs.search.assert_called()

    async def test_auto_discovery(self, tmp_path):
        from local_deepwiki.generators.codemap import discover_entry_points

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="process_data",
                    file_path="src/pipeline.py",
                    start_line=1,
                    end_line=30,
                ),
                _make_mock_search_result(
                    name="load_config",
                    file_path="src/config.py",
                    start_line=1,
                    end_line=10,
                    score=0.7,
                ),
            ]
        )

        nodes = await discover_entry_points(
            query="data processing pipeline",
            vector_store=mock_vs,
            repo_path=tmp_path,
        )
        assert len(nodes) >= 1
        names = [n.name for n in nodes]
        assert "process_data" in names

    async def test_no_results(self, tmp_path):
        from local_deepwiki.generators.codemap import discover_entry_points

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=[])

        nodes = await discover_entry_points(
            query="nonexistent feature",
            vector_store=mock_vs,
            repo_path=tmp_path,
        )
        assert nodes == []


class TestBuildCrossFileGraph:
    async def test_single_file(self, tmp_path):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapNode,
            build_cross_file_graph,
        )

        # Create a minimal source file for call graph extraction
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "module.py").write_text(
            "def func_a():\n    func_b()\n\ndef func_b():\n    pass\n"
        )

        entry = [
            CodemapNode(
                name="func_a",
                qualified_name="module.func_a",
                file_path="src/module.py",
                start_line=1,
                end_line=2,
                chunk_type="function",
            ),
        ]
        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="func_b",
                    file_path="src/module.py",
                    start_line=4,
                    end_line=5,
                    content="def func_b():\n    pass",
                ),
            ]
        )

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {
                "func_a": ["func_b"],
                "func_b": [],
            }
            MockCGE.return_value = extractor

            graph = await build_cross_file_graph(
                entry_nodes=entry,
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_depth=3,
                max_nodes=10,
                focus=CodemapFocus.EXECUTION_FLOW,
            )

        assert len(graph.nodes) >= 1
        assert graph.entry_point == "module.func_a"

    async def test_multi_file(self, tmp_path):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapNode,
            build_cross_file_graph,
        )

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "server.py").write_text("def handle():\n    db.query()\n")
        (src_dir / "db.py").write_text("def query():\n    pass\n")

        entry = [
            CodemapNode(
                name="handle",
                qualified_name="server.handle",
                file_path="src/server.py",
                start_line=1,
                end_line=2,
                chunk_type="function",
            ),
        ]
        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="query",
                    file_path="src/db.py",
                    start_line=1,
                    end_line=2,
                    content="def query():\n    pass",
                ),
            ]
        )

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {"handle": ["query"]}
            MockCGE.return_value = extractor

            graph = await build_cross_file_graph(
                entry_nodes=entry,
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_depth=3,
                max_nodes=10,
                focus=CodemapFocus.EXECUTION_FLOW,
            )

        files = graph.files_involved
        assert len(files) >= 1

    async def test_depth_limit(self, tmp_path):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapNode,
            build_cross_file_graph,
        )

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("def a(): b()\n")

        entry = [
            CodemapNode(
                name="a",
                qualified_name="a.a",
                file_path="src/a.py",
                start_line=1,
                end_line=1,
                chunk_type="function",
            ),
        ]
        mock_vs = AsyncMock()
        # Return many levels of nested calls
        mock_vs.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {"a": ["b", "c", "d"]}
            MockCGE.return_value = extractor

            graph = await build_cross_file_graph(
                entry_nodes=entry,
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_depth=1,
                max_nodes=30,
                focus=CodemapFocus.EXECUTION_FLOW,
            )

        # With depth=1, the graph should be limited
        assert len(graph.nodes) <= 30

    async def test_node_limit(self, tmp_path):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapNode,
            build_cross_file_graph,
        )

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "big.py").write_text("def start(): pass\n")

        entry = [
            CodemapNode(
                name="start",
                qualified_name="big.start",
                file_path="src/big.py",
                start_line=1,
                end_line=1,
                chunk_type="function",
            ),
        ]
        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=[])

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            # Simulate a huge call graph
            callees = [f"func_{i}" for i in range(100)]
            extractor.extract_from_file.return_value = {"start": callees}
            MockCGE.return_value = extractor

            graph = await build_cross_file_graph(
                entry_nodes=entry,
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_depth=5,
                max_nodes=5,
                focus=CodemapFocus.EXECUTION_FLOW,
            )

        assert len(graph.nodes) <= 5

    async def test_empty_entry(self, tmp_path):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            build_cross_file_graph,
        )

        mock_vs = AsyncMock()

        graph = await build_cross_file_graph(
            entry_nodes=[],
            vector_store=mock_vs,
            repo_path=tmp_path,
            max_depth=5,
            max_nodes=30,
            focus=CodemapFocus.EXECUTION_FLOW,
        )

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert graph.entry_point is None


class TestGenerateCodemapDiagram:
    def test_basic_diagram(self):
        from local_deepwiki.generators.codemap import (
            CodemapEdge,
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_diagram,
        )

        nodes = {
            "a.func_a": CodemapNode(
                name="func_a",
                qualified_name="a.func_a",
                file_path="src/a.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
            "a.func_b": CodemapNode(
                name="func_b",
                qualified_name="a.func_b",
                file_path="src/a.py",
                start_line=10,
                end_line=15,
                chunk_type="function",
            ),
        }
        edges = [
            CodemapEdge(
                source="a.func_a",
                target="a.func_b",
                edge_type="calls",
                source_file="src/a.py",
                target_file="src/a.py",
            ),
        ]
        graph = CodemapGraph(nodes=nodes, edges=edges, entry_point="a.func_a")

        diagram = generate_codemap_diagram(graph, CodemapFocus.EXECUTION_FLOW)
        assert "flowchart" in diagram.lower() or "graph" in diagram.lower()
        assert "func_a" in diagram
        assert "func_b" in diagram

    def test_cross_file_styling(self):
        from local_deepwiki.generators.codemap import (
            CodemapEdge,
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_diagram,
        )

        nodes = {
            "a.func": CodemapNode(
                name="func",
                qualified_name="a.func",
                file_path="src/a.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
            "b.func": CodemapNode(
                name="func",
                qualified_name="b.func",
                file_path="src/b.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
            ),
        }
        edges = [
            CodemapEdge(
                source="a.func",
                target="b.func",
                edge_type="calls",
                source_file="src/a.py",
                target_file="src/b.py",
            ),
        ]
        graph = CodemapGraph(nodes=nodes, edges=edges, entry_point="a.func")

        diagram = generate_codemap_diagram(graph, focus=CodemapFocus.EXECUTION_FLOW)
        # Cross-file edges should use dotted style (-.->) or similar distinction
        assert "-->" in diagram or "-.->" in diagram or "-.->|" in diagram

    def test_empty_graph(self):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapGraph,
            generate_codemap_diagram,
        )

        graph = CodemapGraph(nodes={}, edges=[], entry_point=None)
        diagram = generate_codemap_diagram(graph, CodemapFocus.EXECUTION_FLOW)
        # Should return a valid (fallback) diagram, not crash
        assert isinstance(diagram, str)
        assert len(diagram) > 0
        assert "No code paths found" in diagram

    def test_entry_point_styling(self):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_diagram,
        )

        nodes = {
            "main.entry": CodemapNode(
                name="entry",
                qualified_name="main.entry",
                file_path="src/main.py",
                start_line=1,
                end_line=10,
                chunk_type="function",
            ),
        }
        graph = CodemapGraph(nodes=nodes, edges=[], entry_point="main.entry")

        diagram = generate_codemap_diagram(graph, CodemapFocus.EXECUTION_FLOW)
        # Entry point should be mentioned/styled distinctly
        assert "entry" in diagram
        assert "classDef entry" in diagram


# ── Narrative and topic tests ────────────────────────────────────────


class TestGenerateCodemapNarrative:
    async def test_includes_file_refs(self):
        from local_deepwiki.generators.codemap import (
            CodemapEdge,
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_narrative,
        )

        nodes = {
            "server.handle": CodemapNode(
                name="handle",
                qualified_name="server.handle",
                file_path="src/server.py",
                start_line=10,
                end_line=30,
                chunk_type="function",
            ),
            "db.query": CodemapNode(
                name="query",
                qualified_name="db.query",
                file_path="src/db.py",
                start_line=5,
                end_line=15,
                chunk_type="function",
            ),
        }
        edges = [
            CodemapEdge(
                source="server.handle",
                target="db.query",
                edge_type="calls",
                source_file="src/server.py",
                target_file="src/db.py",
            ),
        ]
        graph = CodemapGraph(nodes=nodes, edges=edges, entry_point="server.handle")

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value="The flow starts at server.py:10 (handle) and calls db.py:5 (query)."
        )

        narrative = await generate_codemap_narrative(
            graph=graph,
            query="How does the server handle requests?",
            focus=CodemapFocus.EXECUTION_FLOW,
            llm=mock_llm,
        )

        assert isinstance(narrative, str)
        assert len(narrative) > 0
        # LLM should be called with context about the graph
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        # The prompt should contain file references
        assert "server.py" in prompt or "src/server.py" in prompt

    async def test_llm_failure_fallback(self):
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_narrative,
        )

        nodes = {
            "main.run": CodemapNode(
                name="run",
                qualified_name="main.run",
                file_path="src/main.py",
                start_line=1,
                end_line=10,
                chunk_type="function",
            ),
        }
        graph = CodemapGraph(nodes=nodes, edges=[], entry_point="main.run")

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        narrative = await generate_codemap_narrative(
            graph=graph,
            query="How does main work?",
            focus=CodemapFocus.EXECUTION_FLOW,
            llm=mock_llm,
        )

        # Should return a fallback message instead of raising
        assert isinstance(narrative, str)
        assert len(narrative) > 0


class TestSuggestTopics:
    async def test_finds_hubs(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="main",
                file_path=str(tmp_path / "src" / "main.py"),
                chunk_type="function",
                content="def main(): handle_request(); process_data(); send_response()",
            ),
            _make_mock_code_chunk(
                name="handle_request",
                file_path=str(tmp_path / "src" / "server.py"),
                chunk_type="function",
                content="def handle_request(): pass",
            ),
            _make_mock_code_chunk(
                name="process_data",
                file_path=str(tmp_path / "src" / "pipeline.py"),
                chunk_type="function",
                content="def process_data(): pass",
            ),
        ]

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {
                "main": ["handle_request", "process_data", "send_response"],
            }
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=5,
            )

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        # Should return suggestions with required keys
        for s in suggestions:
            assert isinstance(s, dict)
            assert "topic" in s
            assert "entry_point" in s
            assert "reason" in s

    async def test_empty_repo(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = []

        suggestions = await suggest_topics(
            vector_store=mock_vs,
            repo_path=tmp_path,
            max_suggestions=10,
        )

        assert isinstance(suggestions, list)
        assert len(suggestions) == 0


# ── Handler helpers ──────────────────────────────────────────────────


def _make_index_status(repo_path="/tmp/repo"):
    """Create a mock IndexStatus."""
    status = MagicMock()
    status.repo_path = repo_path
    status.indexed_at = 1700000000.0
    status.total_files = 10
    status.total_chunks = 100
    status.languages = ["python"]
    status.schema_version = 3
    status.files = []
    return status


def _make_config(repo_path="/tmp/repo"):
    """Create a mock config."""
    config = MagicMock()
    config.get_vector_db_path.return_value = Path(repo_path) / ".vector_db"
    config.get_wiki_path.return_value = Path(repo_path) / ".deepwiki"
    config.embedding = MagicMock()
    config.llm_cache = MagicMock()
    config.llm = MagicMock()
    return config


def _make_codemap_result(query="test query"):
    """Create a mock CodemapResult for handler tests."""
    from local_deepwiki.generators.codemap import CodemapResult

    return CodemapResult(
        query=query,
        focus="execution_flow",
        entry_point="handle_request",
        mermaid_diagram="flowchart TD\n    A[handle_request] --> B[process]",
        narrative="The flow starts at handle_request and calls process.",
        nodes=[
            {
                "name": "handle_request",
                "file": "src/server.py",
                "line": 10,
                "type": "function",
            },
            {
                "name": "process",
                "file": "src/pipeline.py",
                "line": 5,
                "type": "function",
            },
        ],
        edges=[
            {
                "source": "handle_request",
                "target": "process",
                "type": "calls",
            }
        ],
        files_involved=["src/server.py", "src/pipeline.py"],
        total_nodes=2,
        total_edges=1,
        cross_file_edges=1,
    )


@pytest.fixture
def mock_access_control():
    with patch("local_deepwiki.handlers.codemap.get_access_controller") as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


# ── Handler integration tests ────────────────────────────────────────


class TestHandleGenerateCodemap:
    async def test_success(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))
        codemap_result = _make_codemap_result("How does auth work?")

        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
        mock_rate_limiter.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "local_deepwiki.handlers.codemap._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.codemap._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.handlers.codemap.get_embedding_provider",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.handlers.codemap.validate_query_parameters",
            ),
            patch(
                "local_deepwiki.generators.codemap.generate_codemap",
                new_callable=AsyncMock,
                return_value=codemap_result,
            ),
            patch(
                "local_deepwiki.providers.llm.get_cached_llm_provider",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.handlers.codemap.get_rate_limiter",
                return_value=mock_rate_limiter,
            ),
        ):
            result = await handle_generate_codemap(
                {"repo_path": str(tmp_path), "query": "How does auth work?"}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["query"] == "How does auth work?"
        assert "mermaid_diagram" in data
        assert "narrative" in data
        assert data["summary"]["total_nodes"] == 2
        assert data["summary"]["total_edges"] == 1
        assert data["summary"]["cross_file_edges"] == 1
        assert "src/server.py" in data["summary"]["files_involved"]

    async def test_not_indexed(self, tmp_path, mock_access_control):
        from local_deepwiki.errors import ValidationError as DWValidationError

        with (
            patch(
                "local_deepwiki.handlers.codemap._load_index_status",
                side_effect=DWValidationError(
                    message=f"Repository {tmp_path} is not indexed",
                    hint="Run index_repository first.",
                ),
            ),
            patch(
                "local_deepwiki.handlers.codemap.validate_query_parameters",
            ),
        ):
            result = await handle_generate_codemap(
                {"repo_path": str(tmp_path), "query": "test"}
            )

        assert "error" in result[0].text.lower()
        assert "not indexed" in result[0].text

    async def test_nonexistent_repo(self, mock_access_control):
        result = await handle_generate_codemap(
            {"repo_path": "/nonexistent/path/xyz", "query": "test"}
        )
        assert "error" in result[0].text.lower()
        assert "does not exist" in result[0].text

    async def test_with_entry_point(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))
        codemap_result = _make_codemap_result("trace login")

        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
        mock_rate_limiter.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "local_deepwiki.handlers.codemap._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.codemap._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.handlers.codemap.get_embedding_provider",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.handlers.codemap.validate_query_parameters",
            ),
            patch(
                "local_deepwiki.generators.codemap.generate_codemap",
                new_callable=AsyncMock,
                return_value=codemap_result,
            ) as mock_gen,
            patch(
                "local_deepwiki.providers.llm.get_cached_llm_provider",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.handlers.codemap.get_rate_limiter",
                return_value=mock_rate_limiter,
            ),
        ):
            result = await handle_generate_codemap(
                {
                    "repo_path": str(tmp_path),
                    "query": "trace login",
                    "entry_point": "handle_login",
                }
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        # Verify entry_point was passed through to the generator
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["entry_point"] == "handle_login"

    async def test_invalid_args(self, mock_access_control):
        # Missing required 'query' field
        result = await handle_generate_codemap({"repo_path": "/tmp/repo"})
        assert "error" in result[0].text.lower()

    async def test_all_focus_modes(self, tmp_path, mock_access_control):
        """Verify all three focus modes are accepted."""
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
        mock_rate_limiter.__aexit__ = AsyncMock(return_value=False)

        for focus_value in ["execution_flow", "data_flow", "dependency_chain"]:
            codemap_result = _make_codemap_result("test")

            with (
                patch(
                    "local_deepwiki.handlers.codemap._load_index_status",
                    return_value=(index_status, tmp_path / ".deepwiki", config),
                ),
                patch(
                    "local_deepwiki.handlers.codemap._create_vector_store",
                    return_value=MagicMock(),
                ),
                patch(
                    "local_deepwiki.handlers.codemap.get_embedding_provider",
                    return_value=MagicMock(),
                ),
                patch(
                    "local_deepwiki.handlers.codemap.validate_query_parameters",
                ),
                patch(
                    "local_deepwiki.generators.codemap.generate_codemap",
                    new_callable=AsyncMock,
                    return_value=codemap_result,
                ) as mock_gen,
                patch(
                    "local_deepwiki.providers.llm.get_cached_llm_provider",
                    return_value=MagicMock(),
                ),
                patch(
                    "local_deepwiki.handlers.codemap.get_rate_limiter",
                    return_value=mock_rate_limiter,
                ),
            ):
                result = await handle_generate_codemap(
                    {
                        "repo_path": str(tmp_path),
                        "query": "test",
                        "focus": focus_value,
                    }
                )

            data = json.loads(result[0].text)
            assert data["status"] == "success"


class TestHandleSuggestCodemapTopics:
    async def test_success(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))
        suggestions = [
            {
                "topic": "Request handling pipeline",
                "entry_point": "handle_request",
                "reason": "Hub with 5 outgoing calls",
            },
            {
                "topic": "Data indexing flow",
                "entry_point": "index_repository",
                "reason": "Core entry point",
            },
        ]

        with (
            patch(
                "local_deepwiki.handlers.codemap._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.codemap._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.generators.codemap.suggest_topics",
                new_callable=AsyncMock,
                return_value=suggestions,
            ),
        ):
            result = await handle_suggest_codemap_topics({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total"] == 2
        assert len(data["suggestions"]) == 2
        assert data["suggestions"][0]["topic"] == "Request handling pipeline"

    async def test_not_indexed(self, tmp_path, mock_access_control):
        from local_deepwiki.errors import ValidationError as DWValidationError

        with patch(
            "local_deepwiki.handlers.codemap._load_index_status",
            side_effect=DWValidationError(
                message=f"Repository {tmp_path} is not indexed",
                hint="Run index_repository first.",
            ),
        ):
            result = await handle_suggest_codemap_topics({"repo_path": str(tmp_path)})

        assert "error" in result[0].text.lower()
        assert "not indexed" in result[0].text

    async def test_nonexistent_repo(self, mock_access_control):
        result = await handle_suggest_codemap_topics(
            {"repo_path": "/nonexistent/path/xyz"}
        )
        assert "error" in result[0].text.lower()
        assert "does not exist" in result[0].text

    async def test_empty_repo(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with (
            patch(
                "local_deepwiki.handlers.codemap._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.codemap._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.generators.codemap.suggest_topics",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await handle_suggest_codemap_topics({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["total"] == 0
        assert data["suggestions"] == []

    async def test_custom_max_suggestions(self, tmp_path, mock_access_control):
        index_status = _make_index_status(str(tmp_path))
        config = _make_config(str(tmp_path))

        with (
            patch(
                "local_deepwiki.handlers.codemap._load_index_status",
                return_value=(index_status, tmp_path / ".deepwiki", config),
            ),
            patch(
                "local_deepwiki.handlers.codemap._create_vector_store",
                return_value=MagicMock(),
            ),
            patch(
                "local_deepwiki.generators.codemap.suggest_topics",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_suggest,
        ):
            await handle_suggest_codemap_topics(
                {"repo_path": str(tmp_path), "max_suggestions": 25}
            )

        mock_suggest.assert_called_once()
        call_kwargs = mock_suggest.call_args[1]
        assert call_kwargs["max_suggestions"] == 25


# ── Tool registration tests ──────────────────────────────────────────


class TestCodemapToolRegistration:
    def test_codemap_tools_in_handlers(self):
        from local_deepwiki.server import TOOL_HANDLERS

        assert "generate_codemap" in TOOL_HANDLERS
        assert "suggest_codemap_topics" in TOOL_HANDLERS

    async def test_list_tools_includes_codemap(self):
        from local_deepwiki.server import list_tools

        tools = await list_tools()
        tool_names = {t.name for t in tools}

        assert "generate_codemap" in tool_names
        assert "suggest_codemap_topics" in tool_names

    def test_generate_codemap_schema(self):
        import asyncio

        from local_deepwiki.server import list_tools

        tools = asyncio.run(list_tools())
        codemap_tool = next(t for t in tools if t.name == "generate_codemap")
        schema = codemap_tool.inputSchema

        assert schema["type"] == "object"
        assert "repo_path" in schema["properties"]
        assert "query" in schema["properties"]
        assert "repo_path" in schema["required"]
        assert "query" in schema["required"]
        # Optional fields present
        assert "entry_point" in schema["properties"]
        assert "focus" in schema["properties"]
        assert "max_depth" in schema["properties"]
        assert "max_nodes" in schema["properties"]

    def test_suggest_codemap_topics_schema(self):
        import asyncio

        from local_deepwiki.server import list_tools

        tools = asyncio.run(list_tools())
        topics_tool = next(t for t in tools if t.name == "suggest_codemap_topics")
        schema = topics_tool.inputSchema

        assert schema["type"] == "object"
        assert "repo_path" in schema["properties"]
        assert "repo_path" in schema["required"]
        assert "max_suggestions" in schema["properties"]


# ── Fix verification tests ───────────────────────────────────────────


class TestDataFlowEdgeAnnotation:
    """Verify data_flow focus mode produces annotated edges."""

    def test_extract_param_names_python(self):
        from local_deepwiki.generators.codemap import _extract_param_names

        params = _extract_param_names(
            "def process(config, repo_path, limit=10):\n    pass"
        )
        assert params == ["config", "repo_path", "limit"]

    def test_extract_param_names_strips_self(self):
        from local_deepwiki.generators.codemap import _extract_param_names

        params = _extract_param_names("def run(self, data: str) -> None:\n    pass")
        assert params == ["data"]

    def test_extract_param_names_empty(self):
        from local_deepwiki.generators.codemap import _extract_param_names

        params = _extract_param_names("x = 42\ny = 10")
        assert params == []

    def test_data_flow_diagram_has_edge_labels(self):
        from local_deepwiki.generators.codemap import (
            CodemapEdge,
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_diagram,
        )

        nodes = {
            "a.caller": CodemapNode(
                name="caller",
                qualified_name="a.caller",
                file_path="src/a.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
                content_preview="def caller(): pass",
            ),
            "b.process": CodemapNode(
                name="process",
                qualified_name="b.process",
                file_path="src/b.py",
                start_line=1,
                end_line=10,
                chunk_type="function",
                content_preview="def process(config, path): pass",
            ),
        }
        edges = [
            CodemapEdge(
                source="a.caller",
                target="b.process",
                edge_type="passes(config, path)",
                source_file="src/a.py",
                target_file="src/b.py",
            ),
        ]
        graph = CodemapGraph(nodes=nodes, edges=edges, entry_point="a.caller")

        diagram = generate_codemap_diagram(graph, CodemapFocus.DATA_FLOW)
        assert "passes(config, path)" in diagram

    def test_execution_flow_no_edge_labels(self):
        from local_deepwiki.generators.codemap import (
            CodemapEdge,
            CodemapFocus,
            CodemapGraph,
            CodemapNode,
            generate_codemap_diagram,
        )

        nodes = {
            "a.caller": CodemapNode(
                name="caller",
                qualified_name="a.caller",
                file_path="src/a.py",
                start_line=1,
                end_line=5,
                chunk_type="function",
                content_preview="def caller(): pass",
            ),
            "b.process": CodemapNode(
                name="process",
                qualified_name="b.process",
                file_path="src/b.py",
                start_line=1,
                end_line=10,
                chunk_type="function",
                content_preview="def process(config, path): pass",
            ),
        }
        edges = [
            CodemapEdge(
                source="a.caller",
                target="b.process",
                edge_type="calls",
                source_file="src/a.py",
                target_file="src/b.py",
            ),
        ]
        graph = CodemapGraph(nodes=nodes, edges=edges, entry_point="a.caller")

        diagram = generate_codemap_diagram(graph, CodemapFocus.EXECUTION_FLOW)
        # Should NOT have edge label syntax
        assert '|"' not in diagram


class TestSuggestTopicsStdlibFiltering:
    """Verify suggest_topics filters out stdlib/external entities."""

    async def test_filters_stdlib_entities(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="main",
                file_path=str(tmp_path / "src" / "main.py"),
                chunk_type="function",
                content="def main(): Path(); MagicMock(); process()",
            ),
            _make_mock_code_chunk(
                name="process",
                file_path=str(tmp_path / "src" / "pipeline.py"),
                chunk_type="function",
                content="def process(data): pass",
            ),
        ]

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            # Call graph includes stdlib names as callees
            extractor.extract_from_file.return_value = {
                "main": ["Path", "MagicMock", "process", "mkdir", "exists"],
            }
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=10,
            )

        # Should NOT include stdlib entities that have no indexed chunk
        entry_points = {s["entry_point"] for s in suggestions}
        assert "Path" not in entry_points
        assert "MagicMock" not in entry_points
        assert "mkdir" not in entry_points
        assert "exists" not in entry_points

        # file_path should never be "unknown"
        for s in suggestions:
            assert s.get("file_path", "") != "unknown"

    async def test_keeps_project_entities(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="handle_request",
                file_path=str(tmp_path / "src" / "server.py"),
                chunk_type="function",
                content="def handle_request(req): validate(req); process(req)",
            ),
            _make_mock_code_chunk(
                name="validate",
                file_path=str(tmp_path / "src" / "validation.py"),
                chunk_type="function",
                content="def validate(req): pass",
            ),
            _make_mock_code_chunk(
                name="process",
                file_path=str(tmp_path / "src" / "pipeline.py"),
                chunk_type="function",
                content="def process(req): pass",
            ),
        ]

        with patch("local_deepwiki.generators.callgraph.CallGraphExtractor") as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {
                "handle_request": ["validate", "process"],
            }
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=10,
            )

        entry_points = {s["entry_point"] for s in suggestions}
        assert "handle_request" in entry_points
