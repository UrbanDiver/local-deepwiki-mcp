"""Tests for agentic tool handlers (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from local_deepwiki.handlers.agentic import (
    TOOL_GRAPH,
    handle_batch_explain_entities,
    handle_query_codebase,
    handle_run_workflow,
    handle_suggest_next_actions,
)


def _parse_response(result: list[TextContent]) -> dict[str, Any]:
    """Parse the JSON response from a handler."""
    return json.loads(result[0].text)


# ---- Fixtures ----


@pytest.fixture()
def indexed_repo(tmp_path: Path) -> Path:
    """Create a fake indexed repository with .deepwiki directory."""
    repo = tmp_path / "myrepo"
    repo.mkdir()

    wiki_dir = repo / ".deepwiki"
    wiki_dir.mkdir()

    # Create a search.json
    search_data = {
        "pages": [
            {
                "title": "Index",
                "path": "index.md",
                "headings": [],
                "terms": [],
                "snippet": "overview",
            },
        ],
        "entities": [
            {
                "name": "my_function",
                "display_name": "my_function",
                "entity_type": "function",
                "file": "src/main.py",
                "signature": "def my_function(x: int) -> str",
                "description": "Does something",
                "keywords": ["function"],
            },
            {
                "name": "MyClass",
                "display_name": "MyClass",
                "entity_type": "class",
                "file": "src/models.py",
                "signature": "class MyClass",
                "description": "A class",
                "keywords": ["class"],
            },
        ],
    }
    (wiki_dir / "search.json").write_text(json.dumps(search_data))

    # Create index_status.json
    index_status = {
        "repo_path": str(repo),
        "indexed_at": 1700000000.0,
        "total_files": 10,
        "total_chunks": 50,
        "languages": {"python": 10},
        "files": [],
        "schema_version": 1,
    }
    (wiki_dir / "index_status.json").write_text(json.dumps(index_status))

    return repo


@pytest.fixture()
def mock_rbac():
    """Mock RBAC to allow all operations."""
    with patch("local_deepwiki.handlers.agentic.get_access_controller") as mock:
        controller = MagicMock()
        controller.require_permission.return_value = None
        mock.return_value = controller
        yield mock


# ---- TestSuggestNextActions ----


class TestSuggestNextActions:
    """Tests for suggest_next_actions tool."""

    async def test_no_tools_used_no_repo(self) -> None:
        result = await handle_suggest_next_actions({})
        data = _parse_response(result)
        assert data["tool"] == "suggest_next_actions"
        assert data["status"] == "success"
        suggestions = data["data"]["suggestions"]
        assert len(suggestions) > 0
        # Without repo, should suggest index_repository
        tool_names = [s["tool"] for s in suggestions]
        assert "index_repository" in tool_names

    async def test_no_tools_used_with_wiki(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        wiki = repo / ".deepwiki"
        wiki.mkdir()

        # get_config is lazily imported inside the handler function
        with patch("local_deepwiki.config.get_config") as mock_config:
            config = MagicMock()
            config.get_wiki_path.return_value = wiki
            mock_config.return_value = config
            result = await handle_suggest_next_actions(
                {
                    "repo_path": str(repo),
                }
            )

        data = _parse_response(result)
        suggestions = data["data"]["suggestions"]
        tool_names = [s["tool"] for s in suggestions]
        assert "read_wiki_structure" in tool_names

    async def test_after_index_repository(self) -> None:
        result = await handle_suggest_next_actions(
            {
                "tools_used": ["index_repository"],
            }
        )
        data = _parse_response(result)
        suggestions = data["data"]["suggestions"]
        tool_names = [s["tool"] for s in suggestions]
        assert "read_wiki_structure" in tool_names
        assert "get_wiki_stats" in tool_names

    async def test_after_ask_question(self) -> None:
        result = await handle_suggest_next_actions(
            {
                "tools_used": ["ask_question"],
            }
        )
        data = _parse_response(result)
        suggestions = data["data"]["suggestions"]
        tool_names = [s["tool"] for s in suggestions]
        assert "explain_entity" in tool_names

    async def test_unknown_tools_returns_fallback(self) -> None:
        result = await handle_suggest_next_actions(
            {
                "tools_used": ["unknown_tool_xyz"],
            }
        )
        data = _parse_response(result)
        suggestions = data["data"]["suggestions"]
        assert len(suggestions) > 0

    async def test_deduplicates_already_used(self) -> None:
        result = await handle_suggest_next_actions(
            {
                "tools_used": ["index_repository", "read_wiki_structure"],
            }
        )
        data = _parse_response(result)
        suggestions = data["data"]["suggestions"]
        tool_names = [s["tool"] for s in suggestions]
        # read_wiki_structure already used, should not be suggested
        assert "read_wiki_structure" not in tool_names

    async def test_priority_sorting(self) -> None:
        result = await handle_suggest_next_actions(
            {
                "tools_used": ["index_repository"],
            }
        )
        data = _parse_response(result)
        suggestions = data["data"]["suggestions"]
        # High priority should come before medium
        priorities = [s["priority"] for s in suggestions]
        for i in range(len(priorities) - 1):
            if priorities[i] == "low":
                assert priorities[i + 1] in ("low",)


# ---- TestRunWorkflow ----


class TestRunWorkflow:
    """Tests for run_workflow tool."""

    async def test_invalid_preset(self, indexed_repo: Path, mock_rbac) -> None:
        result = await handle_run_workflow(
            {
                "repo_path": str(indexed_repo),
                "workflow": "nonexistent",
            }
        )
        # Errors are returned as plain text via format_error_response
        assert "Error" in result[0].text
        assert "nonexistent" in result[0].text

    async def test_repo_not_found(self, tmp_path: Path, mock_rbac) -> None:
        result = await handle_run_workflow(
            {
                "repo_path": str(tmp_path / "nonexistent"),
                "workflow": "onboarding",
            }
        )
        assert "Error" in result[0].text

    @patch("local_deepwiki.handlers.agentic._run_onboarding")
    async def test_onboarding_calls_steps(
        self, mock_onboarding: AsyncMock, indexed_repo: Path, mock_rbac
    ) -> None:
        mock_onboarding.return_value = [
            {"step": "get_project_manifest", "status": "success", "data": {}},
            {"step": "read_wiki_structure", "status": "success", "data": {}},
        ]
        result = await handle_run_workflow(
            {
                "repo_path": str(indexed_repo),
                "workflow": "onboarding",
            }
        )
        data = _parse_response(result)
        assert data["data"]["workflow"] == "onboarding"
        assert data["data"]["completed"] == 2
        assert data["data"]["failed"] == 0

    @patch("local_deepwiki.handlers.agentic._run_security_audit")
    async def test_step_failure_doesnt_cascade(
        self, mock_audit: AsyncMock, indexed_repo: Path, mock_rbac
    ) -> None:
        mock_audit.return_value = [
            {"step": "detect_secrets", "status": "success", "data": {}},
            {
                "step": "complexity:main.py",
                "status": "error",
                "error": "File not found",
            },
        ]
        result = await handle_run_workflow(
            {
                "repo_path": str(indexed_repo),
                "workflow": "security_audit",
            }
        )
        data = _parse_response(result)
        assert data["data"]["completed"] == 1
        assert data["data"]["failed"] == 1


# ---- TestBatchExplainEntities ----


class TestBatchExplainEntities:
    """Tests for batch_explain_entities tool."""

    async def test_single_entity_found(self, indexed_repo: Path, mock_rbac) -> None:
        with patch("local_deepwiki.handlers.agentic._load_index_status") as mock_load:
            mock_load.return_value = (
                MagicMock(),
                indexed_repo / ".deepwiki",
                MagicMock(),
            )

            result = await handle_batch_explain_entities(
                {
                    "repo_path": str(indexed_repo),
                    "entity_names": ["my_function"],
                }
            )

        data = _parse_response(result)
        results = data["data"]["results"]
        assert len(results) == 1
        assert results[0]["found"] is True
        assert results[0]["matches"][0]["name"] == "my_function"

    async def test_multiple_entities(self, indexed_repo: Path, mock_rbac) -> None:
        with patch("local_deepwiki.handlers.agentic._load_index_status") as mock_load:
            mock_load.return_value = (
                MagicMock(),
                indexed_repo / ".deepwiki",
                MagicMock(),
            )

            result = await handle_batch_explain_entities(
                {
                    "repo_path": str(indexed_repo),
                    "entity_names": ["my_function", "MyClass", "nonexistent"],
                }
            )

        data = _parse_response(result)
        assert data["data"]["total_requested"] == 3
        assert data["data"]["total_found"] == 2
        results = data["data"]["results"]
        assert results[0]["found"] is True
        assert results[1]["found"] is True
        assert results[2]["found"] is False

    async def test_entity_not_found(self, indexed_repo: Path, mock_rbac) -> None:
        with patch("local_deepwiki.handlers.agentic._load_index_status") as mock_load:
            mock_load.return_value = (
                MagicMock(),
                indexed_repo / ".deepwiki",
                MagicMock(),
            )

            result = await handle_batch_explain_entities(
                {
                    "repo_path": str(indexed_repo),
                    "entity_names": ["completely_unknown"],
                }
            )

        data = _parse_response(result)
        assert data["data"]["total_found"] == 0
        assert data["data"]["results"][0]["found"] is False

    async def test_no_search_index(self, tmp_path: Path, mock_rbac) -> None:
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        wiki = repo / ".deepwiki"
        wiki.mkdir()

        with patch("local_deepwiki.handlers.agentic._load_index_status") as mock_load:
            mock_load.return_value = (MagicMock(), wiki, MagicMock())

            result = await handle_batch_explain_entities(
                {
                    "repo_path": str(repo),
                    "entity_names": ["something"],
                }
            )

        data = _parse_response(result)
        assert "error" in data["data"]


# ---- TestQueryCodebase ----


class TestQueryCodebase:
    """Tests for query_codebase tool."""

    @patch("local_deepwiki.handlers.core.handle_ask_question")
    async def test_normal_answer_no_escalation(
        self, mock_ask: AsyncMock, indexed_repo: Path, mock_rbac
    ) -> None:
        # Return a long answer (>200 chars)
        long_answer = "This is a detailed answer. " * 20
        mock_ask.return_value = [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "question": "How does X work?",
                        "answer": long_answer,
                        "sources": [],
                    }
                ),
            )
        ]

        result = await handle_query_codebase(
            {
                "repo_path": str(indexed_repo),
                "query": "How does X work?",
            }
        )

        data = _parse_response(result)
        assert data["data"]["escalated"] is False
        assert "hints" in data

    @patch("local_deepwiki.handlers.research.handle_deep_research")
    @patch("local_deepwiki.handlers.core.handle_ask_question")
    async def test_short_answer_triggers_escalation(
        self,
        mock_ask: AsyncMock,
        mock_research: AsyncMock,
        indexed_repo: Path,
        mock_rbac,
    ) -> None:
        # Return a short answer (<200 chars)
        mock_ask.return_value = [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "question": "What is X?",
                        "answer": "X is a thing.",
                        "sources": [],
                    }
                ),
            )
        ]
        mock_research.return_value = [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "question": "What is X?",
                        "answer": "X is a comprehensive system that handles..."
                        + "x" * 300,
                        "sources": [],
                    }
                ),
            )
        ]

        result = await handle_query_codebase(
            {
                "repo_path": str(indexed_repo),
                "query": "What is X?",
            }
        )

        data = _parse_response(result)
        assert data["data"]["escalated"] is True

    @patch("local_deepwiki.handlers.core.handle_ask_question")
    async def test_escalation_disabled(
        self, mock_ask: AsyncMock, indexed_repo: Path, mock_rbac
    ) -> None:
        mock_ask.return_value = [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "question": "X?",
                        "answer": "short",
                        "sources": [],
                    }
                ),
            )
        ]

        result = await handle_query_codebase(
            {
                "repo_path": str(indexed_repo),
                "query": "X?",
                "auto_escalate": False,
            }
        )

        data = _parse_response(result)
        assert data["data"]["escalated"] is False
