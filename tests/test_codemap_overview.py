"""Tests for the codemap overview module clustering backend."""

from __future__ import annotations

import pytest

from local_deepwiki.generators.codemap.overview import (
    OverviewEdge,
    OverviewModule,
    OverviewResult,
)


class TestOverviewModels:
    def test_overview_module_is_frozen(self):
        m = OverviewModule(
            id="core",
            label="Core Engine",
            description="Core processing",
            files=("a.py", "b.py"),
            function_count=10,
            hub_functions=("parse", "index"),
        )
        assert m.id == "core"
        assert m.function_count == 10
        with pytest.raises(AttributeError):
            m.id = "other"

    def test_overview_module_fields(self):
        m = OverviewModule(
            id="web",
            label="Web UI",
            description="Flask web server",
            files=("app.py",),
            function_count=5,
            hub_functions=("create_app",),
        )
        assert m.label == "Web UI"
        assert m.files == ("app.py",)
        assert m.hub_functions == ("create_app",)

    def test_overview_edge_is_frozen(self):
        e = OverviewEdge(
            source="core", target="web", weight=5, description="Core serves web"
        )
        assert e.weight == 5
        with pytest.raises(AttributeError):
            e.weight = 10

    def test_overview_result_is_frozen(self):
        m = OverviewModule(
            id="a",
            label="A",
            description="",
            files=(),
            function_count=0,
            hub_functions=(),
        )
        r = OverviewResult(modules=(m,), edges=(), summary="Test")
        assert r.summary == "Test"
        assert len(r.modules) == 1
        with pytest.raises(AttributeError):
            r.summary = "Other"

    def test_overview_result_with_edges(self):
        m1 = OverviewModule(
            id="a",
            label="A",
            description="",
            files=(),
            function_count=0,
            hub_functions=(),
        )
        m2 = OverviewModule(
            id="b",
            label="B",
            description="",
            files=(),
            function_count=0,
            hub_functions=(),
        )
        e = OverviewEdge(source="a", target="b", weight=3, description="A calls B")
        r = OverviewResult(modules=(m1, m2), edges=(e,), summary="Two modules")
        assert len(r.edges) == 1
        assert r.edges[0].source == "a"
