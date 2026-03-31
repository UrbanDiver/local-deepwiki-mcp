"""Tests for codemap topic suggestion quality.

Validates that _format_topic_suggestions filters out functions with
insufficient outbound calls, preventing leaf nodes and trivial wrappers
from being suggested as codemap topics.
"""

from pathlib import Path
from unittest.mock import MagicMock

from local_deepwiki.generators.codemap.generator import _format_topic_suggestions
from local_deepwiki.models import ChunkType


def _make_chunk(
    name,
    file_path="src/app.py",
    chunk_type="function",
    parent_name=None,
):
    """Create a mock CodeChunk for topic suggestion tests."""
    chunk = MagicMock()
    chunk.name = name
    chunk.file_path = file_path
    chunk.start_line = 1
    chunk.end_line = 10
    chunk.chunk_type = ChunkType(chunk_type)
    chunk.content = f"def {name}(): pass"
    chunk.docstring = None
    chunk.parent_name = parent_name
    return chunk


class TestSuggestionFiltering:
    """Tests that leaf nodes and trivial functions are excluded."""

    def test_leaf_nodes_excluded(self):
        """Functions with 0 outbound calls should not be suggested."""
        chunk_by_name = {
            "create_app": _make_chunk("create_app", "src/web/app.py"),
            "run_pipeline": _make_chunk("run_pipeline", "src/core/pipeline.py"),
        }
        ranked = [("create_app", 50), ("run_pipeline", 30)]
        call_graph = {
            "create_app": [],
            "run_pipeline": ["step_one", "step_two", "step_three"],
        }

        suggestions = _format_topic_suggestions(
            ranked,
            chunk_by_name,
            Path("/repo"),
            5,
            call_graph=call_graph,
        )

        names = [s["entry_point"] for s in suggestions]
        assert "create_app" not in names
        assert "run_pipeline" in names

    def test_trivial_single_call_excluded(self):
        """Functions with only 1 outbound call (trivial wrappers) excluded."""
        chunk_by_name = {
            "main": _make_chunk("main", "src/cli/main.py"),
            "index": _make_chunk("index", "src/core/indexer.py"),
        }
        ranked = [("main", 40), ("index", 25)]
        call_graph = {
            "main": ["typer.run"],
            "index": ["parse", "embed", "store", "generate"],
        }

        suggestions = _format_topic_suggestions(
            ranked,
            chunk_by_name,
            Path("/repo"),
            5,
            call_graph=call_graph,
        )

        names = [s["entry_point"] for s in suggestions]
        assert "main" not in names
        assert "index" in names

    def test_no_call_graph_keeps_all(self):
        """When call_graph is None, no filtering occurs (backward compat)."""
        chunk_by_name = {
            "create_app": _make_chunk("create_app"),
            "run_pipeline": _make_chunk("run_pipeline"),
        }
        ranked = [("create_app", 50), ("run_pipeline", 30)]

        suggestions = _format_topic_suggestions(
            ranked,
            chunk_by_name,
            Path("/repo"),
            5,
            call_graph=None,
        )

        assert len(suggestions) == 2

    def test_qualified_name_fallback(self):
        """Should check bare name when qualified name not in call_graph."""
        chunk_by_name = {
            "MyClass.process": _make_chunk(
                "process", chunk_type="method", parent_name="MyClass"
            ),
        }
        ranked = [("MyClass.process", 20)]
        # Call graph uses bare name
        call_graph = {"process": ["validate", "transform", "save"]}

        suggestions = _format_topic_suggestions(
            ranked,
            chunk_by_name,
            Path("/repo"),
            5,
            call_graph=call_graph,
        )

        assert len(suggestions) == 1
        assert suggestions[0]["entry_point"] == "MyClass.process"

    def test_qualified_name_not_found_in_either_form(self):
        """Functions missing from call_graph entirely should be filtered."""
        chunk_by_name = {
            "MyClass.unknown": _make_chunk(
                "unknown", chunk_type="method", parent_name="MyClass"
            ),
        }
        ranked = [("MyClass.unknown", 15)]
        call_graph = {"other_func": ["a", "b", "c"]}

        suggestions = _format_topic_suggestions(
            ranked,
            chunk_by_name,
            Path("/repo"),
            5,
            call_graph=call_graph,
        )

        assert len(suggestions) == 0

    def test_exactly_two_outbound_calls_included(self):
        """Functions with exactly MIN_OUTBOUND_FOR_SUGGESTION calls pass."""
        chunk_by_name = {
            "handler": _make_chunk("handler", "src/api/handler.py"),
        }
        ranked = [("handler", 10)]
        call_graph = {"handler": ["validate", "process"]}

        suggestions = _format_topic_suggestions(
            ranked,
            chunk_by_name,
            Path("/repo"),
            5,
            call_graph=call_graph,
        )

        assert len(suggestions) == 1
        assert suggestions[0]["entry_point"] == "handler"
