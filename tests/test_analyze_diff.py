"""Tests for the analyze_diff MCP tool."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.handlers import handle_analyze_diff
from local_deepwiki.models import AnalyzeDiffArgs


@pytest.fixture
def mock_access_control():
    """Mock RBAC access controller to allow all operations."""
    with patch("local_deepwiki.handlers.get_access_controller") as mock:
        controller = MagicMock()
        mock.return_value = controller
        yield controller


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo with two commits."""
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=str(tmp_path), capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    # Initial commit
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True
    )
    # Second commit with changes
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello(): pass\n")
    (tmp_path / "README.md").write_text("# Updated Test\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add code"], cwd=str(tmp_path), capture_output=True
    )
    return tmp_path


async def test_analyze_diff_basic(mock_access_control, git_repo):
    """Diff between HEAD~1 and HEAD shows changed files."""
    result = await handle_analyze_diff({"repo_path": str(git_repo)})

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["base_ref"] == "HEAD~1"
    assert data["head_ref"] == "HEAD"

    files = {f["file"] for f in data["changed_files"]}
    assert "src/main.py" in files
    assert "README.md" in files
    assert data["summary"]["total_changed_files"] >= 2


async def test_analyze_diff_no_changes(mock_access_control, git_repo):
    """Diff HEAD to HEAD shows no changes."""
    result = await handle_analyze_diff(
        {"repo_path": str(git_repo), "base_ref": "HEAD", "head_ref": "HEAD"}
    )

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["message"] == "No file changes found between the specified refs."
    assert data["changed_files"] == []


async def test_analyze_diff_with_wiki_mapping(mock_access_control, git_repo):
    """Changed files are mapped to wiki pages and entities when index exists."""
    wiki_dir = git_repo / ".deepwiki"
    wiki_dir.mkdir()
    toc_data = [
        {
            "title": "Main Module",
            "path": "files/src/main.md",
            "source_file": "src/main.py",
        }
    ]
    (wiki_dir / "toc.json").write_text(json.dumps(toc_data))
    search_data = {
        "entities": [
            {
                "name": "hello",
                "display_name": "hello",
                "entity_type": "function",
                "file": "src/main.py",
            }
        ],
        "pages": [],
    }
    (wiki_dir / "search.json").write_text(json.dumps(search_data))

    mock_config = MagicMock()
    mock_index = MagicMock()

    with patch("local_deepwiki.handlers._load_index_status") as mock_load:
        mock_load.return_value = (mock_index, wiki_dir, mock_config)
        result = await handle_analyze_diff({"repo_path": str(git_repo)})

    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert len(data["affected_wiki_pages"]) == 1
    assert data["affected_wiki_pages"][0]["source_file"] == "src/main.py"
    assert data["affected_wiki_pages"][0]["title"] == "Main Module"
    assert len(data["affected_entities"]) == 1
    assert data["affected_entities"][0]["name"] == "hello"
    assert data["affected_entities"][0]["type"] == "function"


async def test_analyze_diff_include_content(mock_access_control, git_repo):
    """include_content=True returns diff content for each file."""
    result = await handle_analyze_diff(
        {"repo_path": str(git_repo), "include_content": True}
    )

    data = json.loads(result[0].text)
    assert data["status"] == "success"

    for cf in data["changed_files"]:
        assert "diff_content" in cf


async def test_analyze_diff_invalid_ref(mock_access_control, git_repo):
    """Shell injection attempt in base_ref is rejected."""
    result = await handle_analyze_diff(
        {"repo_path": str(git_repo), "base_ref": "HEAD; rm -rf /"}
    )

    # The handle_tool_errors decorator formats ValidationError as plain text
    text = result[0].text
    assert "Invalid git ref" in text


async def test_analyze_diff_invalid_ref_backtick(mock_access_control, git_repo):
    """Backtick injection in head_ref is rejected."""
    result = await handle_analyze_diff(
        {"repo_path": str(git_repo), "head_ref": "`whoami`"}
    )

    text = result[0].text
    assert "Invalid git ref" in text


async def test_analyze_diff_repo_not_found(mock_access_control, tmp_path):
    """Nonexistent repo path raises an error."""
    fake_path = str(tmp_path / "nonexistent")
    result = await handle_analyze_diff({"repo_path": fake_path})

    text = result[0].text
    assert "Error" in text
    assert "does not exist" in text or "not found" in text.lower()


async def test_analyze_diff_not_git_repo(mock_access_control, tmp_path):
    """Directory exists but is not a git repo returns error from git."""
    result = await handle_analyze_diff({"repo_path": str(tmp_path)})

    data = json.loads(result[0].text)
    assert data["status"] == "error"
    assert "git diff failed" in data["error"]


async def test_analyze_diff_validation_error(mock_access_control, tmp_path):
    """Missing required repo_path field raises an error."""
    result = await handle_analyze_diff({})

    # Pydantic validation errors are formatted as plain text by the decorator
    text = result[0].text
    assert "Error" in text
    assert "repo_path" in text


async def test_analyze_diff_args_model():
    """Pydantic model validates defaults and constraints."""
    # Defaults
    args = AnalyzeDiffArgs(repo_path="/tmp/repo")
    assert args.base_ref == "HEAD~1"
    assert args.head_ref == "HEAD"
    assert args.include_content is False

    # Custom values
    args2 = AnalyzeDiffArgs(
        repo_path="/tmp/repo",
        base_ref="v1.0.0",
        head_ref="main",
        include_content=True,
    )
    assert args2.base_ref == "v1.0.0"
    assert args2.head_ref == "main"
    assert args2.include_content is True


async def test_analyze_diff_summary_counts(mock_access_control, git_repo):
    """Summary counts match the actual changed files."""
    result = await handle_analyze_diff({"repo_path": str(git_repo)})

    data = json.loads(result[0].text)
    summary = data["summary"]

    # Verify total matches the number of changed_files
    assert summary["total_changed_files"] == len(data["changed_files"])

    # Verify individual status counts add up
    added = sum(1 for f in data["changed_files"] if f["status"] == "added")
    modified = sum(1 for f in data["changed_files"] if f["status"] == "modified")
    deleted = sum(1 for f in data["changed_files"] if f["status"] == "deleted")

    assert summary["added"] == added
    assert summary["modified"] == modified
    assert summary["deleted"] == deleted

    # src/main.py should be "added", README.md should be "modified"
    file_statuses = {f["file"]: f["status"] for f in data["changed_files"]}
    assert file_statuses.get("src/main.py") == "added"
    assert file_statuses.get("README.md") == "modified"
