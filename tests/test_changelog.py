"""Tests for the changelog module."""

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from local_deepwiki.core.git_utils import GitRepoInfo
from local_deepwiki.generators.changelog import (
    CommitInfo,
    build_commit_url,
    generate_changelog_content,
    get_commit_history,
)


class TestGetCommitHistory:
    """Tests for get_commit_history function."""

    def test_returns_commits_from_real_repo(self, tmp_path: Path) -> None:
        """Test getting commit history from a real git repo."""
        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Author"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create a file and commit
        (tmp_path / "file1.py").write_text("# File 1")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create another file and commit
        (tmp_path / "file2.py").write_text("# File 2")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add second file"],
            cwd=tmp_path,
            capture_output=True,
        )

        commits = get_commit_history(tmp_path, limit=10)

        assert len(commits) == 2
        # Newest commit first
        assert commits[0].message == "Add second file"
        assert commits[1].message == "Initial commit"
        assert commits[0].author == "Test Author"
        assert "file2.py" in commits[0].files
        assert "file1.py" in commits[1].files

    def test_returns_empty_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns empty list for non-git directory."""
        commits = get_commit_history(tmp_path)
        assert commits == []

    def test_respects_limit(self, tmp_path: Path) -> None:
        """Test that limit parameter is respected."""
        # Initialize git repo
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

        # Create 5 commits
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"# File {i}")
            subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=tmp_path,
                capture_output=True,
            )

        commits = get_commit_history(tmp_path, limit=3)

        assert len(commits) == 3


class TestBuildCommitUrl:
    """Tests for build_commit_url function."""

    def test_github_url(self) -> None:
        """Test building GitHub commit URL."""
        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_commit_url(repo_info, "abc1234")
        assert result == "https://github.com/owner/repo/commit/abc1234"

    def test_gitlab_url(self) -> None:
        """Test building GitLab commit URL."""
        repo_info = GitRepoInfo(
            remote_url="https://gitlab.com/owner/repo",
            host="gitlab.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_commit_url(repo_info, "abc1234")
        assert result == "https://gitlab.com/owner/repo/-/commit/abc1234"

    def test_no_remote_returns_none(self) -> None:
        """Test returns None when no remote configured."""
        repo_info = GitRepoInfo(
            remote_url=None,
            host=None,
            owner=None,
            repo=None,
            default_branch="main",
        )
        result = build_commit_url(repo_info, "abc1234")
        assert result is None


class TestGenerateChangelogContent:
    """Tests for generate_changelog_content function."""

    def test_generates_markdown(self, tmp_path: Path) -> None:
        """Test generates valid markdown content."""
        # Initialize git repo with remote
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Author"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create commits
        (tmp_path / "file.py").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        content = generate_changelog_content(tmp_path)

        assert content is not None
        assert "# Changelog" in content
        assert "## Recent Commits" in content
        assert "Initial commit" in content
        assert "## Statistics" in content
        assert "https://github.com/test/repo/commit/" in content

    def test_returns_none_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns None for non-git directory."""
        content = generate_changelog_content(tmp_path)
        assert content is None

    def test_groups_by_date(self, tmp_path: Path) -> None:
        """Test commits are grouped by date."""
        # Initialize git repo
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

        # Create commit
        (tmp_path / "file.py").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Test commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        content = generate_changelog_content(tmp_path)

        assert content is not None
        # Should have a date header (format: ### Month Day, Year)
        assert "### " in content

    def test_includes_file_changes(self, tmp_path: Path) -> None:
        """Test includes changed files in output."""
        # Initialize git repo
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

        # Create commit with file
        (tmp_path / "myfile.py").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add myfile"],
            cwd=tmp_path,
            capture_output=True,
        )

        content = generate_changelog_content(tmp_path)

        assert content is not None
        assert "myfile.py" in content

    def test_respects_max_commits(self, tmp_path: Path) -> None:
        """Test max_commits parameter limits output."""
        # Initialize git repo
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

        # Create 5 commits
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"# File {i}")
            subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit number {i}"],
                cwd=tmp_path,
                capture_output=True,
            )

        content = generate_changelog_content(tmp_path, max_commits=2)

        assert content is not None
        # Should show 2 in statistics
        assert "**Commits shown**: 2" in content

    def test_shows_statistics(self, tmp_path: Path) -> None:
        """Test includes statistics section."""
        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Author"],
            cwd=tmp_path,
            capture_output=True,
        )

        (tmp_path / "file.py").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            capture_output=True,
        )

        content = generate_changelog_content(tmp_path)

        assert content is not None
        assert "## Statistics" in content
        assert "**Commits shown**:" in content
        assert "**Contributors**:" in content
        assert "**Latest commit**:" in content


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_create_commit_info(self) -> None:
        """Test creating CommitInfo object."""
        commit = CommitInfo(
            hash="abc1234",
            full_hash="abc1234567890",
            author="Test Author",
            date=datetime(2026, 1, 13, 10, 30, 0),
            message="Test commit",
            files=["file1.py", "file2.py"],
        )

        assert commit.hash == "abc1234"
        assert commit.author == "Test Author"
        assert commit.message == "Test commit"
        assert len(commit.files) == 2

    def test_default_files_list(self) -> None:
        """Test that files defaults to empty list."""
        commit = CommitInfo(
            hash="abc1234",
            full_hash="abc1234567890",
            author="Test",
            date=datetime.now(),
            message="Test",
        )

        assert commit.files == []
