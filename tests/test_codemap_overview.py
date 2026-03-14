"""Tests for the codemap overview module clustering backend."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.codemap.overview import (
    OverviewEdge,
    OverviewModule,
    OverviewResult,
    build_overview,
    cluster_files_into_modules,
    compute_module_metadata,
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


class TestModuleClustering:
    """Tests for cluster_files_into_modules."""

    def test_groups_by_directory(self):
        files = {
            "src/core/parser.py": ["parse", "tokenize"],
            "src/core/indexer.py": ["index", "search"],
            "src/web/app.py": ["create_app"],
            "src/web/routes.py": ["register_routes"],
        }
        modules = cluster_files_into_modules(files)
        ids = {m["id"] for m in modules}
        assert "src/core" in ids
        assert "src/web" in ids

    def test_single_file_directory(self):
        files = {
            "src/core/parser.py": ["parse"],
            "src/server.py": ["main"],
        }
        modules = cluster_files_into_modules(files)
        ids = {m["id"] for m in modules}
        assert "src/core" in ids
        # Single root file gets its own module
        assert "src" in ids

    def test_module_contains_files(self):
        files = {
            "src/core/parser.py": ["parse", "tokenize"],
            "src/core/indexer.py": ["index"],
        }
        modules = cluster_files_into_modules(files)
        core = next(m for m in modules if m["id"] == "src/core")
        assert set(core["files"]) == {"src/core/parser.py", "src/core/indexer.py"}

    def test_empty_input(self):
        modules = cluster_files_into_modules({})
        assert modules == []


class TestComputeModuleMetadata:
    """Tests for compute_module_metadata."""

    def test_function_count(self):
        raw_modules = [
            {"id": "src/core", "files": ["a.py", "b.py"], "dir_label": "core"},
        ]
        file_functions = {
            "a.py": ["parse", "tokenize", "validate"],
            "b.py": ["index", "search"],
        }
        # edges: parse->index (cross-file), parse->tokenize (same-file)
        edges = [
            {
                "source": "parse",
                "target": "index",
                "source_file": "a.py",
                "target_file": "b.py",
            },
            {
                "source": "parse",
                "target": "tokenize",
                "source_file": "a.py",
                "target_file": "a.py",
            },
        ]
        result = compute_module_metadata(raw_modules, file_functions, edges)
        assert result[0].function_count == 5
        assert result[0].id == "src/core"

    def test_hub_functions_by_degree(self):
        raw_modules = [
            {"id": "mod", "files": ["a.py"], "dir_label": "mod"},
        ]
        file_functions = {"a.py": ["hub", "leaf1", "leaf2", "leaf3"]}
        edges = [
            {
                "source": "hub",
                "target": "leaf1",
                "source_file": "a.py",
                "target_file": "a.py",
            },
            {
                "source": "hub",
                "target": "leaf2",
                "source_file": "a.py",
                "target_file": "a.py",
            },
            {
                "source": "hub",
                "target": "leaf3",
                "source_file": "a.py",
                "target_file": "a.py",
            },
        ]
        result = compute_module_metadata(raw_modules, file_functions, edges)
        assert result[0].hub_functions[0] == "hub"
        assert len(result[0].hub_functions) <= 3


def _make_chunk(name, file_path, chunk_type="function", parent_name=None, calls=None):
    """Create a mock CodeChunk for testing."""
    chunk = MagicMock()
    chunk.name = name
    chunk.file_path = file_path
    chunk.chunk_type = MagicMock()
    chunk.chunk_type.value = chunk_type
    chunk.parent_name = parent_name
    chunk.content = f"def {name}(): pass"
    chunk.calls = calls or []
    return chunk


class TestBuildOverview:
    """Tests for the async build_overview function."""

    async def test_build_overview_returns_result(self):
        chunks = [
            _make_chunk("parse", "src/core/parser.py"),
            _make_chunk("index", "src/core/indexer.py"),
            _make_chunk("create_app", "src/web/app.py"),
        ]
        vs = MagicMock()
        vs.get_all_chunks.return_value = chunks

        llm_response = json.dumps(
            {
                "modules": {
                    "src/core": "Core parsing and indexing",
                    "src/web": "Web application",
                },
                "edges": {},
                "summary": "A two-module system",
            }
        )
        llm = AsyncMock()
        llm.generate.return_value = llm_response

        result = await build_overview(vs, "/repo", llm)
        assert isinstance(result, OverviewResult)
        assert len(result.modules) == 2
        assert result.summary == "A two-module system"

    async def test_build_overview_handles_llm_error(self):
        chunks = [
            _make_chunk("parse", "src/core/parser.py"),
        ]
        vs = MagicMock()
        vs.get_all_chunks.return_value = chunks

        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM unavailable")

        result = await build_overview(vs, "/repo", llm)
        assert isinstance(result, OverviewResult)
        # Should still return modules, just without LLM descriptions
        assert len(result.modules) >= 1
        assert result.summary != ""

    async def test_build_overview_empty_repo(self):
        vs = MagicMock()
        vs.get_all_chunks.return_value = []

        llm = AsyncMock()

        result = await build_overview(vs, "/repo", llm)
        assert isinstance(result, OverviewResult)
        assert len(result.modules) == 0
        llm.generate.assert_not_called()

    async def test_build_overview_llm_prompt_format(self):
        chunks = [
            _make_chunk("parse", "src/core/parser.py"),
            _make_chunk("create_app", "src/web/app.py"),
        ]
        vs = MagicMock()
        vs.get_all_chunks.return_value = chunks

        llm_response = json.dumps(
            {
                "modules": {},
                "edges": {},
                "summary": "Test",
            }
        )
        llm = AsyncMock()
        llm.generate.return_value = llm_response

        await build_overview(vs, "/repo", llm)

        # Verify LLM was called with a prompt containing module info
        llm.generate.assert_called_once()
        call_kwargs = llm.generate.call_args
        prompt = (
            call_kwargs.kwargs.get("prompt", "") or call_kwargs.args[0]
            if call_kwargs.args
            else ""
        )
        assert "src/core" in prompt or "core" in prompt
