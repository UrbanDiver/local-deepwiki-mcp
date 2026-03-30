"""Tests for codemap and diagram parameter objects.

Validates the frozen dataclasses ``CodemapRequest``, ``GraphBuildContext``,
and ``DiagramScanContext`` used to bundle long parameter lists.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from local_deepwiki.generators.codemap.models import CodemapFocus
from local_deepwiki.generators.codemap.params import CodemapRequest, GraphBuildContext
from local_deepwiki.generators.diagrams.dependency_diagram import DiagramScanContext


# ---------------------------------------------------------------------------
# CodemapRequest
# ---------------------------------------------------------------------------


class TestCodemapRequest:
    """Tests for the CodemapRequest frozen dataclass."""

    def _make_request(self, **overrides):
        defaults = {
            "query": "How does indexing work?",
            "vector_store": MagicMock(),
            "repo_path": Path("/tmp/repo"),
            "llm": MagicMock(),
        }
        return CodemapRequest(**{**defaults, **overrides})

    def test_required_fields(self):
        req = self._make_request()
        assert req.query == "How does indexing work?"
        assert req.repo_path == Path("/tmp/repo")

    def test_defaults(self):
        req = self._make_request()
        assert req.entry_point is None
        assert req.focus == CodemapFocus.EXECUTION_FLOW
        assert req.max_depth == 4
        assert req.max_nodes == 40

    def test_custom_values(self):
        req = self._make_request(
            entry_point="main",
            focus=CodemapFocus.DATA_FLOW,
            max_depth=6,
            max_nodes=20,
        )
        assert req.entry_point == "main"
        assert req.focus == CodemapFocus.DATA_FLOW
        assert req.max_depth == 6
        assert req.max_nodes == 20

    def test_frozen(self):
        req = self._make_request()
        with pytest.raises(FrozenInstanceError):
            req.query = "changed"  # type: ignore[misc]

    def test_slots(self):
        req = self._make_request()
        with pytest.raises((AttributeError, FrozenInstanceError, TypeError)):
            req.extra_field = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# GraphBuildContext
# ---------------------------------------------------------------------------


class TestGraphBuildContext:
    """Tests for the GraphBuildContext frozen dataclass."""

    def _make_ctx(self, **overrides):
        defaults = {
            "vector_store": MagicMock(),
            "repo_path": Path("/tmp/repo"),
        }
        return GraphBuildContext(**{**defaults, **overrides})

    def test_required_fields(self):
        ctx = self._make_ctx()
        assert ctx.repo_path == Path("/tmp/repo")

    def test_defaults(self):
        ctx = self._make_ctx()
        assert ctx.focus == CodemapFocus.EXECUTION_FLOW
        assert ctx.max_nodes == 40
        assert ctx.max_depth == 4

    def test_custom_values(self):
        ctx = self._make_ctx(
            focus=CodemapFocus.DEPENDENCY_CHAIN,
            max_nodes=10,
            max_depth=2,
        )
        assert ctx.focus == CodemapFocus.DEPENDENCY_CHAIN
        assert ctx.max_nodes == 10
        assert ctx.max_depth == 2

    def test_frozen(self):
        ctx = self._make_ctx()
        with pytest.raises(FrozenInstanceError):
            ctx.max_nodes = 99  # type: ignore[misc]

    def test_slots(self):
        ctx = self._make_ctx()
        with pytest.raises((AttributeError, FrozenInstanceError, TypeError)):
            ctx.extra = "nope"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# DiagramScanContext
# ---------------------------------------------------------------------------


class TestDiagramScanContext:
    """Tests for the DiagramScanContext frozen dataclass."""

    def test_required_fields(self):
        ctx = DiagramScanContext(project_name="my_project")
        assert ctx.project_name == "my_project"

    def test_defaults(self):
        ctx = DiagramScanContext(project_name="p")
        assert ctx.show_external is False
        assert ctx.exclude_tests is True

    def test_custom_values(self):
        ctx = DiagramScanContext(
            project_name="pkg",
            show_external=True,
            exclude_tests=False,
        )
        assert ctx.show_external is True
        assert ctx.exclude_tests is False

    def test_frozen(self):
        ctx = DiagramScanContext(project_name="p")
        with pytest.raises(FrozenInstanceError):
            ctx.project_name = "changed"  # type: ignore[misc]

    def test_slots(self):
        ctx = DiagramScanContext(project_name="p")
        with pytest.raises((AttributeError, FrozenInstanceError, TypeError)):
            ctx.bad = 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Integration: parameter objects used in function calls
# ---------------------------------------------------------------------------


class TestCodemapRequestIntegration:
    """Verify CodemapRequest can be constructed from typical caller patterns."""

    def test_from_handler_args(self):
        """Simulate the pattern used in handlers/codemap.py."""
        vs = MagicMock()
        llm = MagicMock()
        req = CodemapRequest(
            query="How does the search pipeline work?",
            vector_store=vs,
            repo_path=Path("/repo"),
            llm=llm,
            entry_point="handle_search",
            focus=CodemapFocus.EXECUTION_FLOW,
            max_depth=4,
            max_nodes=40,
        )
        assert req.vector_store is vs
        assert req.llm is llm
        assert req.entry_point == "handle_search"


class TestGraphBuildContextIntegration:
    """Verify GraphBuildContext bundles params consistently."""

    def test_context_carries_all_bfs_params(self):
        vs = MagicMock()
        ctx = GraphBuildContext(
            vector_store=vs,
            repo_path=Path("/repo"),
            focus=CodemapFocus.DATA_FLOW,
            max_nodes=30,
            max_depth=5,
        )
        assert ctx.vector_store is vs
        assert ctx.repo_path == Path("/repo")
        assert ctx.focus == CodemapFocus.DATA_FLOW
        assert ctx.max_nodes == 30
        assert ctx.max_depth == 5


class TestDiagramScanContextIntegration:
    """Verify DiagramScanContext bundles scan params consistently."""

    def test_context_from_collect_dependencies(self):
        """Simulate the pattern used in _collect_dependencies."""
        ctx = DiagramScanContext(
            project_name="local_deepwiki",
            show_external=True,
            exclude_tests=True,
        )
        assert ctx.project_name == "local_deepwiki"
        assert ctx.show_external is True
        assert ctx.exclude_tests is True
