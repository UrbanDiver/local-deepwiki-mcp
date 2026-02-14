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
    with patch("local_deepwiki.handlers.analysis_diff.get_access_controller") as mock:
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
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_embedding_provider"
        ) as mock_embed,
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
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
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
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
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config", return_value=mock_config
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch(
            "local_deepwiki.handlers.analysis_diff.VectorStore",
            return_value=mock_vector_store,
        ),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
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
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
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
    assert "error" in text.lower()
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
    assert "error" in text.lower()
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
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
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


async def test_ask_about_diff_custom_refs(mock_access_control, git_repo):
    """Custom base_ref and head_ref should be passed through correctly."""
    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed?",
                "base_ref": "HEAD~1",
                "head_ref": "HEAD",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["base_ref"] == "HEAD~1"
    assert data["head_ref"] == "HEAD"


async def test_ask_about_diff_invalid_head_ref(mock_access_control, git_repo):
    """Shell injection attempt in head_ref should also be rejected."""
    result = await handle_ask_about_diff(
        {
            "repo_path": str(git_repo),
            "question": "What changed?",
            "head_ref": "HEAD && echo pwned",
        }
    )

    text = result[0].text
    assert "Invalid git ref" in text


async def test_ask_about_diff_non_git_repo(mock_access_control, tmp_path):
    """A directory that is not a git repo should produce an error from git diff."""
    mocks = _build_mock_context(tmp_path)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(tmp_path),
                "question": "What changed?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "git diff failed" in data["error"]


async def test_ask_about_diff_git_timeout(mock_access_control, git_repo):
    """When git diff times out, a timeout error should be returned."""
    import subprocess as sp

    with patch(
        "subprocess.run",
        side_effect=sp.TimeoutExpired(cmd="git diff", timeout=30),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "timed out" in data["error"]


async def test_ask_about_diff_llm_failure(mock_access_control, git_repo):
    """When the LLM provider raises, the error should propagate."""
    mocks = _build_mock_context(git_repo)
    mocks["llm"].generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed?",
            }
        )

    text = result[0].text
    assert "error" in text.lower()


async def test_ask_about_diff_vector_search_empty(mock_access_control, git_repo):
    """Vector store exists but returns no results -- should still answer."""
    vector_db_dir = git_repo / "vectordb_empty"
    vector_db_dir.mkdir()

    mock_config = MagicMock()
    mock_config.get_vector_db_path.return_value = vector_db_dir
    mock_config.get_wiki_path.return_value = git_repo / ".deepwiki"
    mock_config.llm_cache = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.embedding = MagicMock()

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="Answer without context.")

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
    mock_rate_limiter.__aexit__ = AsyncMock(return_value=None)

    mock_vector_store = AsyncMock()
    mock_vector_store.search = AsyncMock(return_value=[])

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config", return_value=mock_config
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch(
            "local_deepwiki.handlers.analysis_diff.VectorStore",
            return_value=mock_vector_store,
        ),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mock_rate_limiter,
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What is the purpose of this change?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["sources"] == []
    assert data["answer"] == "Answer without context."


async def test_ask_about_diff_multiple_files(mock_access_control, git_repo):
    """Diff spanning multiple files should still work."""
    # Add a second file
    (git_repo / "utils.py").write_text("def helper(): pass\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "add utils"],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )
    # Modify both files
    (git_repo / "main.py").write_text("x = 99\n")
    (git_repo / "utils.py").write_text("def helper(): return 42\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "modify both"],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )

    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What files were changed?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    # LLM was called with the diff containing both files
    call_args = mocks["llm"].generate.call_args
    prompt_sent = call_args[0][0]
    assert "main.py" in prompt_sent
    assert "utils.py" in prompt_sent


async def test_ask_about_diff_binary_file(mock_access_control, git_repo):
    """Binary files in the diff should not break the handler."""
    # Write a binary file
    (git_repo / "image.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "add binary"],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )

    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What binary files were added?",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["answer"] is not None


async def test_ask_about_diff_git_diff_returncode_nonzero(
    mock_access_control, git_repo
):
    """When git diff exits with nonzero code, an error status is returned."""
    mock_completed = MagicMock()
    mock_completed.returncode = 128
    mock_completed.stderr = "fatal: bad revision 'nonexistent'"
    mock_completed.stdout = ""

    with patch(
        "subprocess.run",
        return_value=mock_completed,
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What changed?",
                "base_ref": "nonexistent",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "git diff failed" in data["error"]


async def test_ask_about_diff_diff_stats_not_truncated(mock_access_control, git_repo):
    """Small diff should have truncated=False in diff_stats."""
    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
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
    assert data["diff_stats"]["truncated"] is False
    assert data["diff_stats"]["diff_length"] < 10000


async def test_ask_about_diff_prompt_contains_question(mock_access_control, git_repo):
    """The question should appear verbatim in the prompt sent to the LLM."""
    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "Are there any security vulnerabilities?",
            }
        )

    call_args = mocks["llm"].generate.call_args
    prompt_sent = call_args[0][0]
    assert "Are there any security vulnerabilities?" in prompt_sent


async def test_ask_about_diff_multiple_vector_results(mock_access_control, git_repo):
    """Multiple vector search results should all appear as sources."""
    vector_db_dir = git_repo / "vectordb_multi"
    vector_db_dir.mkdir()

    mock_config = MagicMock()
    mock_config.get_vector_db_path.return_value = vector_db_dir
    mock_config.get_wiki_path.return_value = git_repo / ".deepwiki"
    mock_config.llm_cache = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.embedding = MagicMock()

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="Answer with multiple contexts.")

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
    mock_rate_limiter.__aexit__ = AsyncMock(return_value=None)

    def _make_search_result(file_path, score):
        chunk = MagicMock()
        chunk.file_path = file_path
        chunk.start_line = 1
        chunk.end_line = 10
        chunk.chunk_type.value = "function"
        chunk.content = "def foo(): pass"
        sr = MagicMock()
        sr.chunk = chunk
        sr.score = score
        return sr

    mock_vector_store = AsyncMock()
    mock_vector_store.search = AsyncMock(
        return_value=[
            _make_search_result("main.py", 0.95),
            _make_search_result("utils.py", 0.88),
            _make_search_result("config.py", 0.72),
        ]
    )

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config", return_value=mock_config
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch(
            "local_deepwiki.handlers.analysis_diff.VectorStore",
            return_value=mock_vector_store,
        ),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mock_rate_limiter,
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "Explain the changes.",
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data["sources"]) == 3
    assert data["sources"][0]["file"] == "main.py"
    assert data["sources"][1]["file"] == "utils.py"
    assert data["sources"][2]["file"] == "config.py"


async def test_ask_about_diff_max_context_respected(mock_access_control, git_repo):
    """max_context should be passed to vector_store.search as the limit."""
    vector_db_dir = git_repo / "vectordb_ctx"
    vector_db_dir.mkdir()

    mock_config = MagicMock()
    mock_config.get_vector_db_path.return_value = vector_db_dir
    mock_config.get_wiki_path.return_value = git_repo / ".deepwiki"
    mock_config.llm_cache = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.embedding = MagicMock()

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="OK")

    mock_rate_limiter = AsyncMock()
    mock_rate_limiter.__aenter__ = AsyncMock(return_value=None)
    mock_rate_limiter.__aexit__ = AsyncMock(return_value=None)

    mock_vector_store = AsyncMock()
    mock_vector_store.search = AsyncMock(return_value=[])

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config", return_value=mock_config
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch(
            "local_deepwiki.handlers.analysis_diff.VectorStore",
            return_value=mock_vector_store,
        ),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mock_llm,
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mock_rate_limiter,
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "Test",
                "max_context": 5,
            }
        )

    mock_vector_store.search.assert_called_once()
    call_kwargs = mock_vector_store.search.call_args
    assert call_kwargs[1]["limit"] == 5 or call_kwargs[0][1] == 5


def test_ask_about_diff_args_max_context_default():
    """max_context should default to 10."""
    args = AskAboutDiffArgs(
        repo_path="/tmp/repo",
        question="Test",
    )
    assert args.max_context == 10


def test_ask_about_diff_args_ref_defaults():
    """base_ref defaults to HEAD~1, head_ref defaults to HEAD."""
    args = AskAboutDiffArgs(
        repo_path="/tmp/repo",
        question="Test",
    )
    assert args.base_ref == "HEAD~1"
    assert args.head_ref == "HEAD"


def test_ask_about_diff_args_long_question_rejected():
    """Question exceeding max_length=2000 should fail validation."""
    with pytest.raises(Exception):
        AskAboutDiffArgs(
            repo_path="/tmp/repo",
            question="x" * 2001,
        )


def test_ask_about_diff_args_valid_long_question():
    """Question at exactly max_length=2000 should be accepted."""
    args = AskAboutDiffArgs(
        repo_path="/tmp/repo",
        question="x" * 2000,
    )
    assert len(args.question) == 2000


async def test_ask_about_diff_only_whitespace_diff(mock_access_control, git_repo):
    """If the diff is only whitespace changes, it should still be processed."""
    # Add trailing whitespace
    (git_repo / "main.py").write_text("x = 2\ny = 3  \n")
    subprocess.run(
        ["git", "add", "."],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "whitespace"],
        cwd=str(git_repo),
        capture_output=True,
        check=True,
    )

    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": "What whitespace changes were made?",
            }
        )

    data = json.loads(result[0].text)
    # Could be "success" with an answer or "No changes found" depending on git diff
    assert data["status"] == "success"


async def test_ask_about_diff_special_chars_in_question(mock_access_control, git_repo):
    """Special characters in the question should not break processing."""
    mocks = _build_mock_context(git_repo)

    with (
        patch(
            "local_deepwiki.handlers.analysis_diff.get_config",
            return_value=mocks["config"],
        ),
        patch("local_deepwiki.handlers.analysis_diff.get_embedding_provider"),
        patch("local_deepwiki.handlers.analysis_diff.VectorStore"),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mocks["llm"],
        ),
        patch(
            "local_deepwiki.handlers.analysis_diff.get_rate_limiter",
            return_value=mocks["rate_limiter"],
        ),
    ):
        result = await handle_ask_about_diff(
            {
                "repo_path": str(git_repo),
                "question": 'Does this diff contain "SQL injection" or <script> tags?',
            }
        )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["answer"] is not None
