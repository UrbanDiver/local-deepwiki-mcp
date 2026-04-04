"""Tests for the detect_bugs MCP handler."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from local_deepwiki.handlers.analysis_bugs import handle_detect_bugs


async def test_handle_detect_bugs_success(tmp_path: Path):
    with patch("local_deepwiki.handlers.analysis_bugs.get_access_controller") as mock:
        mock.return_value.require_permission.return_value = None
        result = await handle_detect_bugs({"repo_path": str(tmp_path)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"


async def test_handle_detect_bugs_finds_bugs(tmp_path: Path):
    (tmp_path / "example.py").write_text("def f(x=[]):\n    pass\n")
    with patch("local_deepwiki.handlers.analysis_bugs.get_access_controller") as mock:
        mock.return_value.require_permission.return_value = None
        result = await handle_detect_bugs({"repo_path": str(tmp_path)})
    data = json.loads(result[0].text)
    assert data["total_findings"] >= 1


async def test_handle_detect_bugs_missing_repo():
    with patch("local_deepwiki.handlers.analysis_bugs.get_access_controller") as mock:
        mock.return_value.require_permission.return_value = None
        result = await handle_detect_bugs({"repo_path": "/nonexistent/path/repo"})
    assert len(result) == 1
    # handle_tool_errors wraps errors — check response text contains error info
    text = result[0].text
    assert "error" in text.lower() or "not found" in text.lower()


async def test_handle_detect_bugs_confidence_filter(tmp_path: Path):
    (tmp_path / "example.py").write_text("def f(x=[]):\n    pass\n")
    with patch("local_deepwiki.handlers.analysis_bugs.get_access_controller") as mock:
        mock.return_value.require_permission.return_value = None
        result = await handle_detect_bugs(
            {
                "repo_path": str(tmp_path),
                "min_confidence": "high",
            }
        )
    data = json.loads(result[0].text)
    for finding in data.get("findings", []):
        assert finding["confidence"] == "high"
