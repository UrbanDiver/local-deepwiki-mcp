"""Tests for the get_guided_tour MCP tool handler."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "server.py").write_text("def main():\n    pass\n")
    (src / "handler.py").write_text("def handle():\n    pass\n")
    return tmp_path


async def test_handler_returns_tour(mock_access_control, sample_repo):
    from local_deepwiki.handlers.analysis_architecture import handle_get_guided_tour

    result = await handle_get_guided_tour({"repo_path": str(sample_repo)})
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "stops" in data
    assert "summary" in data


async def test_handler_missing_repo(mock_access_control, tmp_path):
    from local_deepwiki.handlers.analysis_architecture import handle_get_guided_tour

    result = await handle_get_guided_tour({"repo_path": str(tmp_path / "nonexistent")})
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_handler_with_topic(mock_access_control, sample_repo):
    from local_deepwiki.handlers.analysis_architecture import handle_get_guided_tour

    result = await handle_get_guided_tour(
        {"repo_path": str(sample_repo), "topic": "testing"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["topic"] == "testing"
