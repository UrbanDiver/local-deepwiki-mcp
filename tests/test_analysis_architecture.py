"""Tests for the architecture analysis MCP tool handlers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import (
    handle_get_architecture_summary,
    handle_get_layer_dependencies,
)
from local_deepwiki.server import TOOL_HANDLERS
from local_deepwiki.server_tool_defs import TOOL_DEFINITIONS


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


# ---------------------------------------------------------------------------
# handle_get_architecture_summary tests
# ---------------------------------------------------------------------------


class TestHandleGetArchitectureSummary:
    """Tests for the get_architecture_summary handler."""

    async def test_returns_structured_summary(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
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
        assert "layer_analysis" in data
        assert "file_metrics" in data

    async def test_includes_layer_file_counts(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_architecture_summary(
                {"repo_path": str(mini_project)}
            )

        data = json.loads(result[0].text)
        layer_counts = data["layer_analysis"]["layer_file_counts"]
        assert "core" in layer_counts
        assert "handlers" in layer_counts

    async def test_file_metrics_shape(
        self, mini_project: Path, mock_access_control, mock_manifest
    ) -> None:
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_architecture_summary(
                {"repo_path": str(mini_project)}
            )

        data = json.loads(result[0].text)
        metrics = data["file_metrics"]
        assert "total_files" in metrics
        assert "total_lines" in metrics
        assert "largest_files" in metrics
        assert "files_over_threshold" in metrics
        assert "threshold_lines" in metrics
        assert metrics["total_files"] >= 4  # 2 core + 1 handlers + 1 models

    async def test_large_file_detection(
        self, tmp_path: Path, mock_access_control, mock_manifest
    ) -> None:
        """A file with >800 lines should appear in files_over_threshold."""
        src_dir = tmp_path / "core"
        src_dir.mkdir()
        # Create a file with 850 lines
        large_content = "\n".join(f"line_{i} = {i}" for i in range(850))
        (src_dir / "big.py").write_text(large_content)
        # Create a small file
        (src_dir / "small.py").write_text("x = 1\n")

        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_architecture_summary({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        metrics = data["file_metrics"]
        assert metrics["files_over_threshold"] >= 1
        # The big file should be first in largest_files
        assert metrics["largest_files"][0]["file"] == "core/big.py"
        assert metrics["largest_files"][0]["lines"] >= 850

    async def test_nonexistent_repo_path(
        self, tmp_path: Path, mock_access_control
    ) -> None:
        bogus = tmp_path / "does_not_exist"
        result = await handle_get_architecture_summary({"repo_path": str(bogus)})
        data = json.loads(result[0].text)
        assert "error" in data or data.get("status") == "error"

    async def test_empty_project(
        self, tmp_path: Path, mock_access_control, mock_manifest
    ) -> None:
        """An empty directory should return zero counts gracefully."""
        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_architecture_summary({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        assert data["layer_analysis"]["total_violations"] == 0
        assert data["file_metrics"]["total_files"] == 0
        assert data["file_metrics"]["total_lines"] == 0

    async def test_skips_pycache_and_hidden_dirs(
        self, tmp_path: Path, mock_access_control, mock_manifest
    ) -> None:
        """Files in __pycache__ and .hidden dirs should be excluded."""
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "cached.py").write_text("x = 1\n")

        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.py").write_text("y = 2\n")

        core_dir = tmp_path / "core"
        core_dir.mkdir()
        (core_dir / "real.py").write_text("z = 3\n")

        with patch(
            "local_deepwiki.generators.manifest.get_cached_manifest",
            return_value=mock_manifest,
        ):
            result = await handle_get_architecture_summary({"repo_path": str(tmp_path)})

        data = json.loads(result[0].text)
        # Only core/real.py should be counted
        assert data["file_metrics"]["total_files"] == 1
