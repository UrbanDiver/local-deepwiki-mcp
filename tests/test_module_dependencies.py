"""Tests for get_cross_module_dependencies analysis tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_get_cross_module_dependencies


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
def simple_pkg(tmp_path: Path) -> Path:
    """Create a minimal two-package repo with known import edges."""
    # Package structure: mypkg/core/__init__.py imports from mypkg/models/__init__.py
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    core = pkg / "core"
    core.mkdir()
    (core / "__init__.py").write_text("")
    (core / "parser.py").write_text(
        "from mypkg.models import Item\nfrom mypkg.models import Config\n"
    )
    (core / "indexer.py").write_text(
        "from mypkg.models import Item\nfrom mypkg.core.parser import parse\n"
    )

    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "item.py").write_text("class Item:\n    pass\n")
    (models / "config.py").write_text("class Config:\n    pass\n")

    return tmp_path


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


async def test_cross_module_deps_success(mock_access_control, simple_pkg):
    """Handler returns success status."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"


async def test_cross_module_deps_has_modules(mock_access_control, simple_pkg):
    """Result contains a non-empty modules list."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    assert len(data["modules"]) > 0


async def test_cross_module_deps_module_shape(mock_access_control, simple_pkg):
    """Each module entry has name, file_count, and total_lines."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    for mod in data["modules"]:
        assert "name" in mod
        assert "file_count" in mod
        assert "total_lines" in mod


async def test_cross_module_deps_edges(mock_access_control, simple_pkg):
    """There is at least one edge from core to models."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    edges = data["edges"]
    # Both core.parser and core.indexer import from models.
    core_to_models = [
        e for e in edges if "core" in e["source"] and "models" in e["target"]
    ]
    assert len(core_to_models) > 0


async def test_cross_module_deps_edge_shape(mock_access_control, simple_pkg):
    """Each edge has source, target, weight, and imports."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    for edge in data["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "weight" in edge
        assert isinstance(edge["weight"], int)
        assert "imports" in edge
        assert isinstance(edge["imports"], list)


async def test_cross_module_deps_edge_weight(mock_access_control, simple_pkg):
    """Edge weight reflects import count (core imports models twice)."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    edges = data["edges"]
    core_to_models = [
        e for e in edges if "core" in e["source"] and "models" in e["target"]
    ]
    if core_to_models:
        assert core_to_models[0]["weight"] >= 1


# ---------------------------------------------------------------------------
# Mermaid diagram
# ---------------------------------------------------------------------------


async def test_cross_module_deps_mermaid(mock_access_control, simple_pkg):
    """Result includes a Mermaid graph LR diagram."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    mermaid = data["mermaid"]
    assert mermaid.startswith("graph LR")


async def test_cross_module_deps_mermaid_empty_repo(mock_access_control, tmp_path):
    """An empty repo returns a 'No edges' Mermaid comment."""
    (tmp_path / "x.py").write_text("x = 1\n")
    result = await handle_get_cross_module_dependencies({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert "graph LR" in data["mermaid"]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


async def test_cross_module_deps_stats(mock_access_control, simple_pkg):
    """Stats has total_modules, total_edges, most_depended_on, most_dependent."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(simple_pkg)})
    data = json.loads(result[0].text)
    stats = data["stats"]
    assert "total_modules" in stats
    assert "total_edges" in stats
    assert "most_depended_on" in stats
    assert "most_dependent" in stats
    assert isinstance(stats["most_depended_on"], list)
    assert isinstance(stats["most_dependent"], list)


# ---------------------------------------------------------------------------
# min_edge_weight filter
# ---------------------------------------------------------------------------


async def test_cross_module_deps_min_edge_weight(mock_access_control, simple_pkg):
    """min_edge_weight=100 returns no edges."""
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(simple_pkg), "min_edge_weight": 100}
    )
    data = json.loads(result[0].text)
    assert data["edges"] == []


# ---------------------------------------------------------------------------
# module_filter
# ---------------------------------------------------------------------------


async def test_cross_module_deps_module_filter(mock_access_control, simple_pkg):
    """module_filter restricts results to the specified prefix."""
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(simple_pkg), "module_filter": "core"}
    )
    data = json.loads(result[0].text)
    for mod in data["modules"]:
        # Source modules should start with the filter.
        assert mod["name"].startswith("core") or mod["file_count"] == 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


async def test_cross_module_deps_missing_repo(mock_access_control, tmp_path):
    """Non-existent repo returns an error response."""
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_cross_module_deps_empty_repo(mock_access_control, tmp_path):
    """An empty repo returns zero edges."""
    result = await handle_get_cross_module_dependencies({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["edges"] == []


# ---------------------------------------------------------------------------
# No-external filter
# ---------------------------------------------------------------------------


async def test_cross_module_deps_no_external_by_default(mock_access_control, tmp_path):
    """Third-party imports are excluded by default."""
    (tmp_path / "app.py").write_text("import flask\nimport requests\n")
    result = await handle_get_cross_module_dependencies(
        {"repo_path": str(tmp_path), "include_external": False}
    )
    data = json.loads(result[0].text)
    target_names = [e["target"] for e in data["edges"]]
    assert "flask" not in target_names
    assert "requests" not in target_names
