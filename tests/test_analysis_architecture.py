"""Tests for the architecture analysis MCP tool handlers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import (
    handle_get_architecture_summary,
    handle_get_coupling_metrics,
    handle_get_cross_module_dependencies,
    handle_get_design_smells,
    handle_get_layer_dependencies,
)
from local_deepwiki.server import TOOL_HANDLERS
from local_deepwiki.tool_defs import TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def mock_manifest():
    manifest = MagicMock()
    manifest.name = "test-project"
    return manifest


@pytest.fixture
def mini_project(tmp_path: Path) -> Path:
    """Create a minimal multi-layer Python project."""
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    (core_dir / "parser.py").write_text("def parse(): pass\n")
    (core_dir / "indexer.py").write_text("from core.parser import parse\n")

    handlers_dir = tmp_path / "handlers"
    handlers_dir.mkdir()
    (handlers_dir / "api.py").write_text("from core.indexer import index\n")

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "data.py").write_text("class Data:\n    pass\n")

    return tmp_path


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Verify tools are registered in both TOOL_DEFINITIONS and TOOL_HANDLERS."""

    def test_get_layer_dependencies_in_tool_definitions(self) -> None:
        tool_names = [t.name for t in TOOL_DEFINITIONS]
        assert "get_layer_dependencies" in tool_names

    def test_get_layer_dependencies_in_tool_handlers(self) -> None:
        assert "get_layer_dependencies" in TOOL_HANDLERS

    def test_get_architecture_summary_in_tool_definitions(self) -> None:
        tool_names = [t.name for t in TOOL_DEFINITIONS]
        assert "get_architecture_summary" in tool_names

    def test_get_architecture_summary_in_tool_handlers(self) -> None:
        assert "get_architecture_summary" in TOOL_HANDLERS

    def test_get_layer_dependencies_handler_matches(self) -> None:
        assert TOOL_HANDLERS["get_layer_dependencies"] is handle_get_layer_dependencies

    def test_get_architecture_summary_handler_matches(self) -> None:
        assert (
            TOOL_HANDLERS["get_architecture_summary"] is handle_get_architecture_summary
        )


# ---------------------------------------------------------------------------
# handle_get_layer_dependencies tests
# ---------------------------------------------------------------------------


class TestHandleGetLayerDependencies:
    """Tests for the get_layer_dependencies handler."""

    async def test_returns_layer_analysis(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_layer_dependencies(
                {"repo_path": str(mini_project)}
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert data["project_name"] == "test-project"
        assert "layer_file_counts" in data
        assert "layer_edges" in data
        assert "violations" in data
        assert "total_violations" in data

    async def test_includes_layer_file_counts(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_layer_dependencies(
                {"repo_path": str(mini_project)}
            )

        data = json.loads(result[0].text)
        counts = data["layer_file_counts"]
        assert counts.get("core", 0) == 2
        assert counts.get("handlers", 0) == 1
        assert counts.get("models", 0) == 1

    async def test_nonexistent_repo_path(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        bogus = tmp_path / "does_not_exist"
        result = await handle_get_layer_dependencies({"repo_path": str(bogus)})
        data = json.loads(result[0].text)
        # Error response from handle_tool_errors decorator
        assert "error" in data or data.get("status") == "error"

    async def test_uses_repo_name_when_manifest_empty(
        self, mini_project: Path, mock_access_control
    ) -> None:
        empty_manifest = MagicMock()
        empty_manifest.name = None
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=empty_manifest,
        ):
            result = await handle_get_layer_dependencies(
                {"repo_path": str(mini_project)}
            )

        data = json.loads(result[0].text)
        # Falls back to directory name
        assert data["project_name"] == mini_project.name

    async def test_summary_only(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_layer_dependencies(
                {"repo_path": str(mini_project), "summary_only": True}
            )

        data = json.loads(result[0].text)
        assert data["status"] == "success"
        assert "total_violations" in data
        assert "layer_file_counts" not in data
        assert "layer_edges" not in data
        assert "violations" not in data


# ---------------------------------------------------------------------------
# handle_get_architecture_summary tests
# ---------------------------------------------------------------------------


class TestHandleGetArchitectureSummary:
    """Tests for the get_architecture_summary handler (deprecated, delegates to health)."""

    async def test_returns_health_check_data(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
        """Deprecated handler delegates to get_architecture_health with full detail."""
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_architecture_summary(
                {"repo_path": str(mini_project)}
            )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "success"
        # Should include health grade data (from delegation to health check)
        assert "overall" in data
        # Full detail includes file_metrics
        assert "file_metrics" in data

    async def test_nonexistent_repo_path(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        bogus = tmp_path / "does_not_exist"
        result = await handle_get_architecture_summary({"repo_path": str(bogus)})
        data = json.loads(result[0].text)
        assert "error" in data or data.get("status") == "error"


# ---------------------------------------------------------------------------
# handle_get_design_smells overflow tests
# ---------------------------------------------------------------------------


class TestHandleGetDesignSmellsOverflow:
    """Tests for top_n and summary_only parameters on get_design_smells."""

    async def test_top_n_limits_smells(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        """get_design_smells with top_n=5 returns at most 5 smells."""
        fake_smells = [
            {"type": f"smell_{i}", "severity": "high", "file": "f.py", "line": i}
            for i in range(20)
        ]
        fake_result = {
            "status": "success",
            "smells": fake_smells,
            "summary": {"total": 20, "by_severity": {}, "by_type": {}},
        }
        with patch(
            "local_deepwiki.generators.analysis.design_smells.analyze_design_smells",
            return_value=fake_result,
        ):
            result = await handle_get_design_smells(
                {"repo_path": str(tmp_path), "top_n": 5}
            )

        data = json.loads(result[0].text)
        assert len(data["smells"]) == 5

    async def test_summary_only_returns_type_counts(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        """get_design_smells with summary_only=True returns smells_by_type without individual smells."""
        fake_smells = [
            {"type": "god_class", "severity": "high", "file": "a.py", "line": 1},
            {"type": "god_class", "severity": "high", "file": "b.py", "line": 1},
            {"type": "long_method", "severity": "high", "file": "c.py", "line": 1},
        ]
        fake_result = {
            "status": "success",
            "smells": fake_smells,
            "summary": {"total": 3, "by_severity": {}, "by_type": {}},
        }
        with patch(
            "local_deepwiki.generators.analysis.design_smells.analyze_design_smells",
            return_value=fake_result,
        ):
            result = await handle_get_design_smells(
                {"repo_path": str(tmp_path), "summary_only": True}
            )

        data = json.loads(result[0].text)
        assert "smells" not in data
        assert data["smells_by_type"] == {"god_class": 2, "long_method": 1}
        assert data["total_smells"] == 3


# ---------------------------------------------------------------------------
# handle_get_coupling_metrics overflow tests
# ---------------------------------------------------------------------------


class TestHandleGetCouplingMetricsOverflow:
    """Tests for top_n parameter on get_coupling_metrics."""

    async def test_top_n_limits_modules(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        """get_coupling_metrics with top_n=10 returns at most 10 modules."""
        fake_metrics = [
            {
                "module": f"mod_{i}",
                "afferent_coupling": 1,
                "efferent_coupling": 1,
                "instability": 0.5,
                "abstractness": 0.0,
                "distance": round(0.5 - i * 0.01, 4),
            }
            for i in range(30)
        ]
        fake_result = {
            "status": "success",
            "metrics": fake_metrics,
            "stats": {
                "total_modules": 30,
                "avg_instability": 0.5,
                "avg_abstractness": 0.0,
            },
        }
        with patch(
            "local_deepwiki.generators.analysis.coupling.analyze_coupling_metrics",
            return_value=fake_result,
        ):
            result = await handle_get_coupling_metrics(
                {"repo_path": str(tmp_path), "top_n": 10}
            )

        data = json.loads(result[0].text)
        assert len(data["metrics"]) == 10


# ---------------------------------------------------------------------------
# handle_get_cross_module_dependencies overflow tests
# ---------------------------------------------------------------------------


class TestHandleGetCrossModuleDependenciesOverflow:
    """Tests for top_n parameter on get_cross_module_dependencies."""

    async def test_top_n_limits_nodes(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        """get_cross_module_dependencies with top_n=20 limits modules to 20."""
        fake_modules = [
            {"name": f"mod_{i}", "file_count": 2, "total_lines": 100} for i in range(50)
        ]
        fake_edges = [
            {
                "source": f"mod_{i}",
                "target": f"mod_{i + 1}",
                "weight": 1,
                "imports": [],
            }
            for i in range(49)
        ]
        fake_result = {
            "status": "success",
            "modules": fake_modules,
            "edges": fake_edges,
            "mermaid": "graph LR",
            "stats": {"total_modules": 50, "total_edges": 49},
        }
        with patch(
            "local_deepwiki.generators.analysis.module_dependencies.analyze_cross_module_dependencies",
            return_value=fake_result,
        ):
            result = await handle_get_cross_module_dependencies(
                {"repo_path": str(tmp_path), "top_n": 20}
            )

        data = json.loads(result[0].text)
        assert len(data["modules"]) == 20
