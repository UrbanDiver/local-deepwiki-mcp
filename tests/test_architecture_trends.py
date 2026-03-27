"""Tests for the get_architecture_trends MCP tool handler."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers.analysis_architecture import (
    handle_get_architecture_trends,
)


@pytest.fixture
def mock_access_control():
    with patch(
        "local_deepwiki.handlers.analysis_architecture.get_access_controller"
    ) as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def repo_with_history(tmp_path):
    wiki = tmp_path / ".deepwiki"
    wiki.mkdir()
    history = wiki / "health-history.jsonl"
    history.write_text(
        '{"timestamp":"2026-03-01T10:00:00Z","git_ref":"aaa","score":55,"grade":"D","dimensions":{}}\n'
        '{"timestamp":"2026-03-15T10:00:00Z","git_ref":"bbb","score":62,"grade":"C","dimensions":{}}\n'
        '{"timestamp":"2026-03-25T10:00:00Z","git_ref":"ccc","score":70,"grade":"B","dimensions":{}}\n'
    )
    return tmp_path


async def test_trends_returns_snapshots(mock_access_control, repo_with_history):
    result = await handle_get_architecture_trends(
        {"repo_path": str(repo_with_history), "since": "2026-01-01"}
    )
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data["snapshots"]) == 3
    assert data["summary"]["snapshot_count"] == 3


async def test_trends_since_filter(mock_access_control, repo_with_history):
    result = await handle_get_architecture_trends(
        {"repo_path": str(repo_with_history), "since": "2026-03-10"}
    )
    data = json.loads(result[0].text)
    assert len(data["snapshots"]) == 2
    assert data["snapshots"][0]["git_ref"] == "bbb"
    assert data["snapshots"][1]["git_ref"] == "ccc"


async def test_trends_no_history(mock_access_control, tmp_path):
    wiki = tmp_path / ".deepwiki"
    wiki.mkdir()
    result = await handle_get_architecture_trends(
        {"repo_path": str(tmp_path), "since": "2026-01-01"}
    )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["snapshots"] == []
    assert data["summary"] is None


async def test_trends_missing_repo(mock_access_control, tmp_path):
    missing = tmp_path / "nonexistent"
    result = await handle_get_architecture_trends({"repo_path": str(missing)})
    data = json.loads(result[0].text)
    assert data["status"] == "error"


async def test_trends_score_change(mock_access_control, repo_with_history):
    result = await handle_get_architecture_trends(
        {"repo_path": str(repo_with_history), "since": "2026-01-01"}
    )
    data = json.loads(result[0].text)
    assert data["summary"]["score_change"] == 15
    assert data["summary"]["current_grade"] == "B"
