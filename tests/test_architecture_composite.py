"""Tests for the analyze_architecture composite tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers.analysis_architecture import handle_analyze_architecture


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def simple_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        "from .utils import helper\n\ndef main():\n    return helper()\n"
    )
    (src / "utils.py").write_text("def helper():\n    return 42\n")
    (src / "__init__.py").write_text("")
    return tmp_path


async def test_analyze_architecture_returns_markdown(mock_access_control, simple_repo):
    """Composite tool should return a markdown narrative report."""
    result = await handle_analyze_architecture({"repo_path": str(simple_repo)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "report" in data
    assert "## Executive Summary" in data["report"]


async def test_analyze_architecture_summary_detail(mock_access_control, simple_repo):
    """Summary detail level should produce compact output."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "detail_level": "summary"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "## Executive Summary" in data["report"]
    assert "## Concerns" not in data["report"]


async def test_analyze_architecture_standard_detail(mock_access_control, simple_repo):
    """Standard detail level should include all sections."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "detail_level": "standard"}
    )
    data = json.loads(result[0].text)
    assert "## Executive Summary" in data["report"]
    assert "## Dependency Structure" in data["report"]


async def test_analyze_architecture_focus_complexity(mock_access_control, simple_repo):
    """Focus=complexity should only include complexity-related findings."""
    result = await handle_analyze_architecture(
        {"repo_path": str(simple_repo), "focus": "complexity"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "## Dependency Structure" not in data["report"]


async def test_analyze_architecture_missing_repo(mock_access_control, tmp_path):
    """Should return error for missing repo."""
    result = await handle_analyze_architecture(
        {"repo_path": str(tmp_path / "nonexistent")}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_analyze_architecture_output_size(mock_access_control, simple_repo):
    """Standard output should stay under 8K characters."""
    result = await handle_analyze_architecture({"repo_path": str(simple_repo)})
    assert len(result[0].text) < 8000
