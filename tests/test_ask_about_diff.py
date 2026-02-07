"""Tests for the ask_about_diff MCP tool."""

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_ask_about_diff
from local_deepwiki.models import AskAboutDiffArgs


@pytest.fixture
def mock_access_control():
    """Mock the RBAC access controller."""
    with patch("local_deepwiki.handlers.get_access_controller") as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo with two commits."""
    subprocess.run(
        ["git", "init"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    (tmp_path / "main.py").write_text("x = 1\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    (tmp_path / "main.py").write_text("x = 2\ny = 3\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "update"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )
    return tmp_path


def _build_mock_context(tmp_path, vector_db_exists=False):
    """Build a standard set of mocks for the handler dependencies.

    Returns a dict of mock objects for use in patch context managers.
    """
    mock_config = MagicMock()
    mock_config.get_vector_db_path.return_value = (
        tmp_path / "vectordb" if not vector_db_exists else tmp_path / "vectordb_exists"
    )
    mock_config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    mock_config.llm_cache = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.embedding = MagicMock()

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value="The diff modifies variable x from 1 to 2 and adds variable y."
    )

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
    mock_rate_limiter.__aexit__ = AsyncMock(return_value=None)

    return {
        "config": mock_config,
        "llm": mock_llm,
        "rate_limiter": mock_rate_limiter,
    }


async def test_ask_about_diff_basic(mock_access_control, git_repo):
    """Basic test: ask a question about the diff, get an LLM answer back."""
    mocks = _build_mock_context(git_repo)

    with (
        patch("local_deepwiki.handlers.get_config", return_value=mocks["config"]),
        patch("local_deepwiki.handlers.get_embedding_provider") as mock_embed,
        patch("local_deepwiki.handlers.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed in this commit?",
            }
        )

    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["question"] == "What changed in this commit?"
    assert "modifies variable x" in data["answer"]
    assert data["base_ref"] == "HEAD~1"
    assert data["head_ref"] == "HEAD"
    assert "diff_stats" in data
    assert isinstance(data["sources"], list)


async def test_ask_about_diff_no_changes(mock_access_control, git_repo):
    """When diffing HEAD to HEAD there are no changes; LLM should NOT be called."""
    mocks = _build_mock_context(git_repo)

    with (
        patch("local_deepwiki.handlers.get_config", return_value=mocks["config"]),
        patch("local_deepwiki.handlers.get_embedding_provider"),
        patch("local_deepwiki.handlers.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed?",
                "base_ref": "HEAD",
                "head_ref": "HEAD",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert "No changes found" in data["answer"]
    assert data["sources"] == []
    # LLM should NOT have been called
    mocks["llm"].generate.assert_not_called()


async def test_ask_about_diff_with_vector_context(mock_access_control, git_repo):
    """When vector store exists, sources should appear in the result."""
    # Create a fake vector DB directory so vector_db_path.exists() returns True
    vector_db_dir = git_repo / "vectordb_real"
    vector_db_dir.mkdir()

    mock_config = MagicMock()
    mock_config.get_vector_db_path.return_value = vector_db_dir
    mock_config.get_wiki_path.return_value = git_repo / ".deepwiki"
    mock_config.llm_cache = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.embedding = MagicMock()

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="Analysis with context.")

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
    mock_rate_limiter.__aexit__ = AsyncMock(return_value=None)

    # Build a mock search result
    mock_chunk = MagicMock()
    mock_chunk.file_path = "main.py"
    mock_chunk.start_line = 1
    mock_chunk.end_line = 5
    mock_chunk.chunk_type.value = "function"
    mock_chunk.content = "def foo(): pass"

    mock_search_result = MagicMock()
    mock_search_result.chunk = mock_chunk
    mock_search_result.score = 0.95

    mock_vector_store = AsyncMock()
    mock_vector_store.search = AsyncMock(return_value=[mock_search_result])

    with (
        patch("local_deepwiki.handlers.get_config", return_value=mock_config),
        patch("local_deepwiki.handlers.get_embedding_provider"),
        patch(
            "local_deepwiki.handlers.VectorStore",
            return_value=mock_vector_store,
        ),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "local_deepwiki.handlers.get_rate_limiter",
            return_value=mock_rate_limiter,
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What functions were affected?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["file"] == "main.py"
    assert data["sources"][0]["score"] == 0.95


async def test_ask_about_diff_no_vector_store(mock_access_control, git_repo):
    """Works even when no vector DB exists (diff-only, no RAG context)."""
    mocks = _build_mock_context(git_repo)

    with (
        patch("local_deepwiki.handlers.get_config", return_value=mocks["config"]),
        patch("local_deepwiki.handlers.get_embedding_provider"),
        patch("local_deepwiki.handlers.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "Summarize the changes",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["answer"] is not None
    assert data["sources"] == []


async def test_ask_about_diff_invalid_ref(mock_access_control, git_repo):
    """Shell injection attempt in git ref should be rejected."""
    result = await handle_ask_about_diff(
        {
            "repo_path": str(git_repo),
            "question": "What changed?",
            "base_ref": "HEAD; rm -rf /",
        }
    )

    text = result[0].text
    assert "Invalid git ref" in text


async def test_ask_about_diff_repo_not_found(mock_access_control, tmp_path):
    """Nonexistent repo path should raise an error."""
    result = await handle_ask_about_diff(
        {
            "repo_path": str(tmp_path / "nonexistent"),
            "question": "What changed?",
        }
    )

    text = result[0].text
    assert "Error" in text
    assert "does not exist" in text


async def test_ask_about_diff_validation_error(mock_access_control):
    """Missing required fields should produce validation error."""
    result = await handle_ask_about_diff(
        {
            "repo_path": "/some/path",
            # "question" is missing
        }
    )

    text = result[0].text
    assert "Error" in text
    assert "question" in text.lower()


def test_ask_about_diff_args_model():
    """Pydantic validation on the args model."""
    # Valid args
    valid = AskAboutDiffArgs(
        repo_path="/tmp/repo",
        question="What changed?",
    )
    assert valid.base_ref == "HEAD~1"
    assert valid.head_ref == "HEAD"
    assert valid.max_context == 10

    # Custom values
    custom = AskAboutDiffArgs(
        repo_path="/tmp/repo",
        question="Any bugs?",
        base_ref="main",
        head_ref="feature-branch",
        max_context=25,
    )
    assert custom.base_ref == "main"
    assert custom.head_ref == "feature-branch"
    assert custom.max_context == 25

    # Empty question should fail
    with pytest.raises(Exception):
        AskAboutDiffArgs(repo_path="/tmp/repo", question="")

    # max_context out of range should fail
    with pytest.raises(Exception):
        AskAboutDiffArgs(repo_path="/tmp/repo", question="test", max_context=0)

    with pytest.raises(Exception):
        AskAboutDiffArgs(repo_path="/tmp/repo", question="test", max_context=31)


async def test_ask_about_diff_truncates_large_diff(mock_access_control, git_repo):
    """A very large diff should be truncated and flagged in diff_stats."""
    mocks = _build_mock_context(git_repo)

    # Create a large diff by writing a big file
    large_content = "\n".join(f"line_{i} = {i}" for i in range(5000))
    (git_repo / "main.py").write_text(large_content)
    subprocess.run(
        ["git", "add", "."],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "big change"],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )

    with (
        patch("local_deepwiki.handlers.get_config", return_value=mocks["config"]),
        patch("local_deepwiki.handlers.get_embedding_provider"),
        patch("local_deepwiki.handlers.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["diff_stats"]["truncated"] is True
    assert data["diff_stats"]["diff_length"] > 10000

    # Verify the prompt sent to LLM contains truncation notice
    call_args = mocks["llm"].generate.call_args
    prompt_sent = call_args[0][0]
    assert "diff truncated" in prompt_sent
