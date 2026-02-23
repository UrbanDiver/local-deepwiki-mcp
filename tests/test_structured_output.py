"""Tests for structured output helpers (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_deepwiki.handlers._response import (
    build_wiki_resource_uri,
    wrap_tool_response,
)


class TestWrapToolResponse:
    """Tests for the JSON envelope helper."""

    def test_basic_envelope(self) -> None:
        result = wrap_tool_response("my_tool", {"key": "value"})
        parsed = json.loads(result)
        assert parsed["tool"] == "my_tool"
        assert parsed["status"] == "success"
        assert parsed["key"] == "value"
        assert "hints" not in parsed

    def test_with_hints(self) -> None:
        hints = {"next_tools": [{"tool": "ask_question"}]}
        result = wrap_tool_response("my_tool", {"answer": "hello"}, hints=hints)
        parsed = json.loads(result)
        assert parsed["hints"] == hints
        assert parsed["answer"] == "hello"

    def test_empty_data(self) -> None:
        result = wrap_tool_response("empty_tool", {})
        parsed = json.loads(result)
        assert parsed["tool"] == "empty_tool"
        assert parsed["status"] == "success"

    def test_nested_data(self) -> None:
        data = {"results": [{"name": "foo", "score": 0.9}], "count": 1}
        result = wrap_tool_response("search", data)
        parsed = json.loads(result)
        assert parsed["results"][0]["name"] == "foo"

    def test_none_hints_excluded(self) -> None:
        result = wrap_tool_response("tool", {"x": 1}, hints=None)
        parsed = json.loads(result)
        assert "hints" not in parsed


class TestBuildWikiResourceUri:
    """Tests for URI builder."""

    def test_basic_uri(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        uri = build_wiki_resource_uri(wiki_path, "index.md")
        assert uri.startswith("deepwiki://")
        assert str(wiki_path) in uri
        assert uri.endswith("index.md")

    def test_nested_page(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        uri = build_wiki_resource_uri(wiki_path, "modules/core.md")
        assert "modules/core.md" in uri

    def test_uri_format(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        uri = build_wiki_resource_uri(wiki_path, "page.md")
        expected = f"deepwiki://{wiki_path}/page.md"
        assert uri == expected
