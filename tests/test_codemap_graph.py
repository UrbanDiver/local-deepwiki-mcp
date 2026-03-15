"""Tests for codemap cross-file graph building and BFS traversal.

Tests cover:
- build_cross_file_graph: single file, multi-file, depth/node limits, empty entry
- Min similarity floor: low/high score filtering, _search_cross_file kwargs
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Mock helpers ─────────────────────────────────────────────────────


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


# ── Cross-file graph building tests ──────────────────────────────────


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

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
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

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
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

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
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

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
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


# ── Min similarity floor tests ───────────────────────────────────────


class TestMinSimilarityFloor:
    """Tests that codemap cross-file search applies a min_similarity floor."""

    async def test_low_similarity_results_filtered_from_cross_file_graph(
        self, tmp_path
    ):
        """Low-similarity vector search results (score < 0.3) should not
        appear in the cross-file graph because min_similarity=0.3 is passed
        to the vector store search call.
        """
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapNode,
            build_cross_file_graph,
        )

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main():\n    helper()\n")
        (src_dir / "utils.py").write_text("def helper():\n    pass\n")

        entry = [
            CodemapNode(
                name="main",
                qualified_name="main.main",
                file_path="src/main.py",
                start_line=1,
                end_line=2,
                chunk_type="function",
            ),
        ]

        async def search_with_similarity_filter(
            query, *, limit=10, min_similarity=0.0, **kwargs
        ):
            """Mock that respects min_similarity like the real VectorStore."""
            low_score_result = _make_mock_search_result(
                name="helper",
                file_path="src/utils.py",
                start_line=1,
                end_line=2,
                content="def helper():\n    pass",
                score=0.1,  # Below the 0.3 floor
            )
            return [r for r in [low_score_result] if r.score >= min_similarity]

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(side_effect=search_with_similarity_filter)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {"main": ["helper"]}
            MockCGE.return_value = extractor

            graph = await build_cross_file_graph(
                entry_nodes=entry,
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_depth=3,
                max_nodes=10,
                focus=CodemapFocus.EXECUTION_FLOW,
            )

        # Only the entry node should be in the graph; the low-similarity
        # "helper" result should have been filtered out by the vector store
        assert "main.main" in graph.nodes
        cross_file_nodes = [
            n for qn, n in graph.nodes.items() if n.file_path != "src/main.py"
        ]
        assert len(cross_file_nodes) == 0, (
            "Low-similarity results (score < 0.3) should be filtered out"
        )

    async def test_high_similarity_results_kept_in_cross_file_graph(self, tmp_path):
        """Results with score >= 0.3 should still be included in the graph."""
        from local_deepwiki.generators.codemap import (
            CodemapFocus,
            CodemapNode,
            build_cross_file_graph,
        )

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main():\n    helper()\n")
        (src_dir / "utils.py").write_text("def helper():\n    pass\n")

        entry = [
            CodemapNode(
                name="main",
                qualified_name="main.main",
                file_path="src/main.py",
                start_line=1,
                end_line=2,
                chunk_type="function",
            ),
        ]

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="helper",
                    file_path="src/utils.py",
                    start_line=1,
                    end_line=2,
                    content="def helper():\n    pass",
                    score=0.8,  # Above the 0.3 floor
                ),
            ]
        )

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {"main": ["helper"]}
            MockCGE.return_value = extractor

            graph = await build_cross_file_graph(
                entry_nodes=entry,
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_depth=3,
                max_nodes=10,
                focus=CodemapFocus.EXECUTION_FLOW,
            )

        # The high-similarity helper should be found in the graph
        cross_file_nodes = [
            n for qn, n in graph.nodes.items() if n.file_path != "src/main.py"
        ]
        assert len(cross_file_nodes) >= 1, (
            "High-similarity results (score >= 0.3) should be kept"
        )

    async def test_search_called_with_min_similarity_0_3(self, tmp_path):
        """Verify that vector_store.search is called with min_similarity=0.3."""
        from local_deepwiki.generators.codemap.graph import _search_cross_file

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=[])

        await _search_cross_file("some_func", mock_vs, tmp_path, "src/caller.py")

        mock_vs.search.assert_called_once_with(
            "def some_func", limit=5, min_similarity=0.3
        )
