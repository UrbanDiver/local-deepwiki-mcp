"""Automated output size tests for architecture tools.

Verifies that default parameters produce output under the specified limits.
Uses a synthetic repo for realistic but fast CI tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers.analysis_architecture import (
    handle_analyze_architecture,
    handle_get_architecture_health,
    handle_get_coupling_metrics,
    handle_get_cross_module_dependencies,
    handle_get_design_smells,
    handle_get_hotspots,
    handle_get_layer_dependencies,
)


@pytest.fixture
def sized_repo(tmp_path: Path) -> Path:
    """Create a repo with enough structure to produce realistic output."""
    src = tmp_path / "src"
    for i in range(20):
        pkg = src / f"pkg{i}"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(f"from .mod import func{i}\n")
        body = "\n".join(f"    x{j} = {j}" for j in range(10))
        (pkg / "mod.py").write_text(f"def func{i}(a, b, c):\n{body}\n    return a\n")
    return tmp_path


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


_8K = 8000
_6K = 6000
_1K = 1000


async def test_hotspots_default_under_6k(mock_access_control, sized_repo):
    result = await handle_get_hotspots({"repo_path": str(sized_repo)})
    assert len(result[0].text) < _6K


async def test_hotspots_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_hotspots(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


async def test_coupling_default_under_6k(mock_access_control, sized_repo):
    result = await handle_get_coupling_metrics({"repo_path": str(sized_repo)})
    assert len(result[0].text) < _6K


async def test_coupling_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_coupling_metrics(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


async def test_layer_deps_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_layer_dependencies(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


async def test_smells_summary_under_1k(mock_access_control, sized_repo):
    result = await handle_get_design_smells(
        {"repo_path": str(sized_repo), "summary_only": True}
    )
    assert len(result[0].text) < _1K


async def test_health_summary_under_3k(mock_access_control, sized_repo):
    result = await handle_get_architecture_health(
        {"repo_path": str(sized_repo), "detail_level": "summary"}
    )
    assert len(result[0].text) < 3500


async def test_analyze_architecture_standard_under_8k(mock_access_control, sized_repo):
    result = await handle_analyze_architecture({"repo_path": str(sized_repo)})
    assert len(result[0].text) < _8K
