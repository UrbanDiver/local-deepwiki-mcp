"""Tests for MCP prompt handlers (handlers/prompts.py).

Covers the public helper functions (_make_tool_message, _get_*_messages)
and the register_prompt_handlers callback wiring (list_prompts, get_prompt).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from mcp.types import GetPromptResult, PromptMessage, TextContent

from local_deepwiki.handlers.prompts import (
    _get_investigate_area_messages,
    _get_onboarding_messages,
    _get_security_audit_messages,
    _make_tool_message,
    register_prompt_handlers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_handlers() -> dict[str, object]:
    """Wire up a mock server and return the captured handler callables."""
    mock_server = MagicMock()
    handlers: dict[str, object] = {}
    mock_server.list_prompts.return_value = (
        lambda fn: handlers.__setitem__("list", fn) or fn
    )
    mock_server.get_prompt.return_value = (
        lambda fn: handlers.__setitem__("get", fn) or fn
    )
    register_prompt_handlers(mock_server)
    return handlers


# ---------------------------------------------------------------------------
# _make_tool_message
# ---------------------------------------------------------------------------


class TestMakeToolMessage:
    """Tests for _make_tool_message."""

    def test_returns_prompt_message_with_user_role(self):
        msg = _make_tool_message("index_repository", {"repo_path": "/tmp/repo"})
        assert isinstance(msg, PromptMessage)
        assert msg.role == "user"

    def test_content_contains_tool_name(self):
        msg = _make_tool_message("search_code", {"query": "auth"})
        assert isinstance(msg.content, TextContent)
        assert "`search_code`" in msg.content.text

    def test_content_contains_json_args(self):
        args = {"repo_path": "/tmp/repo", "query": "auth"}
        msg = _make_tool_message("search_code", args)
        text = msg.content.text
        # The JSON block should be parseable and match the original args
        json_start = text.index("```json\n") + len("```json\n")
        json_end = text.index("\n```", json_start)
        parsed = json.loads(text[json_start:json_end])
        assert parsed == args

    def test_empty_args(self):
        msg = _make_tool_message("some_tool", {})
        assert isinstance(msg.content, TextContent)
        assert "{}" in msg.content.text


# ---------------------------------------------------------------------------
# _get_onboarding_messages
# ---------------------------------------------------------------------------


class TestGetOnboardingMessages:
    """Tests for _get_onboarding_messages."""

    def test_returns_list_of_prompt_messages(self):
        msgs = _get_onboarding_messages("/tmp/repo")
        assert isinstance(msgs, list)
        assert all(isinstance(m, PromptMessage) for m in msgs)

    def test_first_message_is_intro(self):
        msgs = _get_onboarding_messages("/tmp/repo")
        assert "/tmp/repo" in msgs[0].content.text

    def test_includes_index_repository_call(self):
        msgs = _get_onboarding_messages("/tmp/repo")
        texts = [m.content.text for m in msgs]
        assert any("index_repository" in t for t in texts)

    def test_includes_read_wiki_structure_call(self):
        msgs = _get_onboarding_messages("/tmp/repo")
        texts = [m.content.text for m in msgs]
        assert any("read_wiki_structure" in t for t in texts)

    def test_includes_get_wiki_stats_call(self):
        msgs = _get_onboarding_messages("/tmp/repo")
        texts = [m.content.text for m in msgs]
        assert any("get_wiki_stats" in t for t in texts)

    def test_message_count(self):
        msgs = _get_onboarding_messages("/tmp/repo")
        assert len(msgs) == 4  # intro + 3 tool calls


# ---------------------------------------------------------------------------
# _get_security_audit_messages
# ---------------------------------------------------------------------------


class TestGetSecurityAuditMessages:
    """Tests for _get_security_audit_messages."""

    def test_returns_list_of_prompt_messages(self):
        msgs = _get_security_audit_messages("/tmp/repo")
        assert isinstance(msgs, list)
        assert all(isinstance(m, PromptMessage) for m in msgs)

    def test_includes_detect_secrets_call(self):
        msgs = _get_security_audit_messages("/tmp/repo")
        texts = [m.content.text for m in msgs]
        assert any("detect_secrets" in t for t in texts)

    def test_includes_get_project_manifest_call(self):
        msgs = _get_security_audit_messages("/tmp/repo")
        texts = [m.content.text for m in msgs]
        assert any("get_project_manifest" in t for t in texts)

    def test_includes_run_workflow_call(self):
        msgs = _get_security_audit_messages("/tmp/repo")
        texts = [m.content.text for m in msgs]
        assert any("run_workflow" in t for t in texts)

    def test_message_count(self):
        msgs = _get_security_audit_messages("/tmp/repo")
        assert len(msgs) == 4  # intro + 3 tool calls


# ---------------------------------------------------------------------------
# _get_investigate_area_messages
# ---------------------------------------------------------------------------


class TestGetInvestigateAreaMessages:
    """Tests for _get_investigate_area_messages."""

    def test_returns_list_of_prompt_messages(self):
        msgs = _get_investigate_area_messages("/tmp/repo", "auth flow")
        assert isinstance(msgs, list)
        assert all(isinstance(m, PromptMessage) for m in msgs)

    def test_includes_search_code_call(self):
        msgs = _get_investigate_area_messages("/tmp/repo", "auth flow")
        texts = [m.content.text for m in msgs]
        assert any("search_code" in t for t in texts)

    def test_includes_generate_codemap_call(self):
        msgs = _get_investigate_area_messages("/tmp/repo", "auth flow")
        texts = [m.content.text for m in msgs]
        assert any("generate_codemap" in t for t in texts)

    def test_intro_contains_query(self):
        msgs = _get_investigate_area_messages("/tmp/repo", "database layer")
        assert "database layer" in msgs[0].content.text

    def test_message_count(self):
        msgs = _get_investigate_area_messages("/tmp/repo", "auth flow")
        assert len(msgs) == 3  # intro + 2 tool calls


# ---------------------------------------------------------------------------
# register_prompt_handlers — list_prompts
# ---------------------------------------------------------------------------


class TestListPrompts:
    """Tests for the list_prompts handler registered by register_prompt_handlers."""

    async def test_returns_three_prompts(self):
        handlers = _register_handlers()
        prompts = await handlers["list"]()
        assert len(prompts) == 3

    async def test_prompt_names(self):
        handlers = _register_handlers()
        prompts = await handlers["list"]()
        names = {p.name for p in prompts}
        assert names == {"onboarding", "security_audit", "investigate_area"}

    async def test_all_prompts_have_descriptions(self):
        handlers = _register_handlers()
        prompts = await handlers["list"]()
        for prompt in prompts:
            assert prompt.description, f"Prompt {prompt.name} has no description"


# ---------------------------------------------------------------------------
# register_prompt_handlers — get_prompt
# ---------------------------------------------------------------------------


class TestGetPrompt:
    """Tests for the get_prompt handler registered by register_prompt_handlers."""

    async def test_onboarding_returns_get_prompt_result(self):
        handlers = _register_handlers()
        result = await handlers["get"]("onboarding", {"repo_path": "/tmp/repo"})
        assert isinstance(result, GetPromptResult)
        assert result.description is not None
        assert len(result.messages) > 0

    async def test_security_audit_returns_get_prompt_result(self):
        handlers = _register_handlers()
        result = await handlers["get"]("security_audit", {"repo_path": "/tmp/repo"})
        assert isinstance(result, GetPromptResult)
        assert len(result.messages) > 0

    async def test_investigate_area_returns_get_prompt_result(self):
        handlers = _register_handlers()
        result = await handlers["get"](
            "investigate_area", {"repo_path": "/tmp/repo", "query": "auth flow"}
        )
        assert isinstance(result, GetPromptResult)
        assert "auth flow" in result.description

    async def test_onboarding_missing_repo_path_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="repo_path"):
            await handlers["get"]("onboarding", {})

    async def test_onboarding_empty_repo_path_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="repo_path"):
            await handlers["get"]("onboarding", {"repo_path": ""})

    async def test_onboarding_none_arguments_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="repo_path"):
            await handlers["get"]("onboarding", None)

    async def test_security_audit_missing_repo_path_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="repo_path"):
            await handlers["get"]("security_audit", {})

    async def test_investigate_area_missing_repo_path_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="repo_path"):
            await handlers["get"]("investigate_area", {"query": "auth"})

    async def test_investigate_area_missing_query_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="query"):
            await handlers["get"]("investigate_area", {"repo_path": "/tmp/repo"})

    async def test_unknown_prompt_raises(self):
        handlers = _register_handlers()
        with pytest.raises(ValueError, match="Unknown prompt"):
            await handlers["get"]("unknown", {})
