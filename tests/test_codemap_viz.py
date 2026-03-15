"""Tests for codemap visualization: Mermaid diagrams and LLM narrative.

Tests cover:
- generate_codemap_diagram: basic output, cross-file styling, empty graph, entry point styling
- generate_codemap_narrative: file references in prompt, LLM failure fallback
- Data flow edge annotations: param extraction, edge labels, execution_flow no labels
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Diagram generation tests ─────────────────────────────────────────


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


# ── Narrative generation tests ───────────────────────────────────────


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


# ── Data flow edge annotation tests ──────────────────────────────────


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
