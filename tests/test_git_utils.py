"""Tests for the git_utils module."""

import subprocess
from pathlib import Path

import pytest

from local_deepwiki.core.git_utils import (
    GitRepoInfo,
    build_source_url,
    get_default_branch,
    get_git_remote_url,
    get_repo_info,
    is_github_repo,
    parse_remote_url,
)


class TestParseRemoteUrl:
    """Tests for parse_remote_url function."""

    def test_github_https(self) -> None:
        """Test parsing GitHub HTTPS URL."""
        result = parse_remote_url("https://github.com/owner/repo")
        assert result == ("github.com", "owner", "repo")

    def test_github_https_with_git_suffix(self) -> None:
        """Test parsing GitHub HTTPS URL with .git suffix."""
        result = parse_remote_url("https://github.com/owner/repo.git")
        assert result == ("github.com", "owner", "repo")

    def test_github_ssh(self) -> None:
        """Test parsing GitHub SSH URL."""
        result = parse_remote_url("git@github.com:owner/repo.git")
        assert result == ("github.com", "owner", "repo")

    def test_github_ssh_without_suffix(self) -> None:
        """Test parsing GitHub SSH URL without .git suffix."""
        result = parse_remote_url("git@github.com:owner/repo")
        assert result == ("github.com", "owner", "repo")

    def test_gitlab_https(self) -> None:
        """Test parsing GitLab HTTPS URL."""
        result = parse_remote_url("https://gitlab.com/owner/repo.git")
        assert result == ("gitlab.com", "owner", "repo")

    def test_gitlab_ssh(self) -> None:
        """Test parsing GitLab SSH URL."""
        result = parse_remote_url("git@gitlab.com:owner/repo")
        assert result == ("gitlab.com", "owner", "repo")

    def test_self_hosted_gitlab(self) -> None:
        """Test parsing self-hosted GitLab URL."""
        result = parse_remote_url("https://git.company.com/team/project.git")
        assert result == ("git.company.com", "team", "project")

    def test_ssh_url_format(self) -> None:
        """Test parsing ssh:// URL format."""
        result = parse_remote_url("ssh://git@github.com/owner/repo.git")
        assert result == ("github.com", "owner", "repo")

    def test_nested_path(self) -> None:
        """Test parsing URL with nested group/project paths."""
        result = parse_remote_url("https://gitlab.com/group/subgroup/repo.git")
        assert result == ("gitlab.com", "group/subgroup", "repo")

    def test_invalid_url_returns_none(self) -> None:
        """Test that invalid URLs return None."""
        assert parse_remote_url("not-a-url") is None
        assert parse_remote_url("") is None
        assert parse_remote_url("https://github.com") is None


class TestBuildSourceUrl:
    """Tests for build_source_url function."""

    def test_github_url_without_lines(self) -> None:
        """Test building GitHub URL without line numbers."""
        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py")
        assert result == "https://github.com/owner/repo/blob/main/src/file.py"

    def test_github_url_with_single_line(self) -> None:
        """Test building GitHub URL with single line number."""
        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py", start_line=42)
        assert result == "https://github.com/owner/repo/blob/main/src/file.py#L42"

    def test_github_url_with_line_range(self) -> None:
        """Test building GitHub URL with line range."""
        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py", start_line=10, end_line=20)
        assert result == "https://github.com/owner/repo/blob/main/src/file.py#L10-L20"

    def test_gitlab_url_with_line_range(self) -> None:
        """Test building GitLab URL with line range (different format)."""
        repo_info = GitRepoInfo(
            remote_url="https://gitlab.com/owner/repo",
            host="gitlab.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py", start_line=10, end_line=20)
        # GitLab uses /-/blob/ and #L10-20 format
        assert result == "https://gitlab.com/owner/repo/-/blob/main/src/file.py#L10-20"

    def test_gitlab_url_without_lines(self) -> None:
        """Test building GitLab URL without line numbers."""
        repo_info = GitRepoInfo(
            remote_url="https://gitlab.com/owner/repo",
            host="gitlab.com",
            owner="owner",
            repo="repo",
            default_branch="develop",
        )
        result = build_source_url(repo_info, "lib/module.rb")
        assert result == "https://gitlab.com/owner/repo/-/blob/develop/lib/module.rb"

    def test_no_remote_returns_none(self) -> None:
        """Test that missing remote info returns None."""
        repo_info = GitRepoInfo(
            remote_url=None,
            host=None,
            owner=None,
            repo=None,
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py")
        assert result is None

    def test_same_start_end_line(self) -> None:
        """Test that same start and end line shows single line."""
        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py", start_line=42, end_line=42)
        assert result == "https://github.com/owner/repo/blob/main/src/file.py#L42"


class TestGetGitRemoteUrl:
    """Tests for get_git_remote_url function."""

    def test_returns_remote_url(self, tmp_path: Path) -> None:
        """Test getting remote URL from a git repo."""
        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_git_remote_url(tmp_path)
        assert result == "https://github.com/test/repo.git"

    def test_returns_none_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns None for non-git directory."""
        result = get_git_remote_url(tmp_path)
        assert result is None

    def test_returns_none_for_repo_without_remote(self, tmp_path: Path) -> None:
        """Test returns None for repo without remote."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        result = get_git_remote_url(tmp_path)
        assert result is None


class TestGetDefaultBranch:
    """Tests for get_default_branch function."""

    def test_returns_current_branch(self, tmp_path: Path) -> None:
        """Test returns current branch name."""
        # Initialize a git repo with a commit
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        # Create a file and commit
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_default_branch(tmp_path)
        assert result == "main"

    def test_returns_fallback_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns 'main' fallback for non-git directory."""
        result = get_default_branch(tmp_path)
        assert result == "main"


class TestGetRepoInfo:
    """Tests for get_repo_info function."""

    def test_returns_complete_info(self, tmp_path: Path) -> None:
        """Test returns complete GitRepoInfo for valid repo."""
        # Initialize repo with remote
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/myorg/myrepo.git"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_repo_info(tmp_path)

        assert result.remote_url == "https://github.com/myorg/myrepo.git"
        assert result.host == "github.com"
        assert result.owner == "myorg"
        assert result.repo == "myrepo"
        assert result.default_branch == "main"

    def test_returns_partial_info_without_remote(self, tmp_path: Path) -> None:
        """Test returns partial info for repo without remote."""
        # Initialize repo with a commit so branch exists
        subprocess.run(["git", "init", "-b", "develop"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_repo_info(tmp_path)

        assert result.remote_url is None
        assert result.host is None
        assert result.owner is None
        assert result.repo is None
        assert result.default_branch == "develop"

    def test_returns_empty_info_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns empty info for non-git directory."""
        result = get_repo_info(tmp_path)

        assert result.remote_url is None
        assert result.host is None
        assert result.owner is None
        assert result.repo is None
        assert result.default_branch == "main"  # Fallback


class TestIsGithubRepo:
    """Tests for is_github_repo function."""

    def test_github_https_returns_true(self, tmp_path: Path) -> None:
        """Test returns True for GitHub HTTPS remote."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/owner/repo.git"],
            cwd=tmp_path,
            capture_output=True,
        )

        assert is_github_repo(tmp_path) is True

    def test_github_ssh_returns_true(self, tmp_path: Path) -> None:
        """Test returns True for GitHub SSH remote."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:owner/repo.git"],
            cwd=tmp_path,
            capture_output=True,
        )

        assert is_github_repo(tmp_path) is True

    def test_gitlab_returns_false(self, tmp_path: Path) -> None:
        """Test returns False for GitLab remote."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://gitlab.com/owner/repo.git"],
            cwd=tmp_path,
            capture_output=True,
        )

        assert is_github_repo(tmp_path) is False

    def test_no_remote_returns_false(self, tmp_path: Path) -> None:
        """Test returns False for repo without remote."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        assert is_github_repo(tmp_path) is False

    def test_non_git_dir_returns_false(self, tmp_path: Path) -> None:
        """Test returns False for non-git directory."""
        assert is_github_repo(tmp_path) is False
