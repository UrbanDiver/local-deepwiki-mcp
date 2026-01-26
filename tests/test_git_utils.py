"""Tests for the git_utils module."""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.core.git_utils import (
    BlameInfo,
    EntityBlameInfo,
    GitPathValidationError,
    GitRepoInfo,
    StaleInfo,
    _parse_all_porcelain_blame,
    _parse_line_blame_map,
    _validate_git_path,
    _validate_repo_path,
    build_source_url,
    check_page_staleness,
    format_blame_date,
    get_default_branch,
    get_file_entity_blame,
    get_file_last_modified,
    get_files_last_modified,
    get_git_remote_url,
    get_line_blame,
    get_range_blame,
    get_repo_info,
    is_github_repo,
    parse_remote_url,
)


class TestValidateGitPath:
    """Tests for _validate_git_path function (security validation)."""

    def test_valid_path_returns_resolved_path(self, tmp_path: Path) -> None:
        """Test valid path returns absolute Path object."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = _validate_git_path(test_file)
        assert result.is_absolute()
        assert result.exists()

    def test_rejects_path_starting_with_dash(self, tmp_path: Path) -> None:
        """Test rejects paths starting with dash (option injection prevention)."""
        with pytest.raises(GitPathValidationError, match="starts with '-'"):
            _validate_git_path("-malicious")

    def test_rejects_path_with_null_byte(self, tmp_path: Path) -> None:
        """Test rejects paths containing null bytes."""
        with pytest.raises(GitPathValidationError, match="null byte"):
            _validate_git_path("path\x00with_null")

    def test_rejects_nonexistent_path(self, tmp_path: Path) -> None:
        """Test rejects paths that don't exist."""
        with pytest.raises(GitPathValidationError, match="does not exist"):
            _validate_git_path(tmp_path / "nonexistent")

    def test_accepts_directory(self, tmp_path: Path) -> None:
        """Test accepts directory paths."""
        result = _validate_git_path(tmp_path)
        assert result == tmp_path.resolve()

    def test_accepts_file(self, tmp_path: Path) -> None:
        """Test accepts file paths."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        result = _validate_git_path(test_file)
        assert result == test_file.resolve()


class TestValidateRepoPath:
    """Tests for _validate_repo_path function (repository validation)."""

    def test_valid_repo_returns_resolved_path(self, tmp_path: Path) -> None:
        """Test valid git repo returns absolute Path object."""
        (tmp_path / ".git").mkdir()
        result = _validate_repo_path(tmp_path)
        assert result.is_absolute()
        assert result.exists()

    def test_rejects_file_path(self, tmp_path: Path) -> None:
        """Test rejects file paths (must be directory)."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        with pytest.raises(GitPathValidationError, match="not a directory"):
            _validate_repo_path(test_file)

    def test_rejects_non_git_directory(self, tmp_path: Path) -> None:
        """Test rejects directory without .git."""
        with pytest.raises(GitPathValidationError, match="not inside a git repository"):
            _validate_repo_path(tmp_path)

    def test_accepts_subdirectory_in_git_repo(self, tmp_path: Path) -> None:
        """Test accepts subdirectory inside a git repository."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src"
        subdir.mkdir()
        result = _validate_repo_path(subdir)
        assert result == subdir.resolve()

    def test_rejects_path_starting_with_dash(self, tmp_path: Path) -> None:
        """Test inherits dash rejection from _validate_git_path."""
        with pytest.raises(GitPathValidationError, match="starts with '-'"):
            _validate_repo_path("-malicious")

    def test_rejects_path_with_null_byte(self, tmp_path: Path) -> None:
        """Test inherits null byte rejection from _validate_git_path."""
        with pytest.raises(GitPathValidationError, match="null byte"):
            _validate_repo_path("path\x00with_null")


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

    def test_gitlab_url_with_single_line(self) -> None:
        """Test building GitLab URL with single line number."""
        repo_info = GitRepoInfo(
            remote_url="https://gitlab.com/owner/repo",
            host="gitlab.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py", start_line=42)
        assert result == "https://gitlab.com/owner/repo/-/blob/main/src/file.py#L42"

    def test_gitlab_url_with_same_start_end_line(self) -> None:
        """Test GitLab URL with same start and end line shows single line."""
        repo_info = GitRepoInfo(
            remote_url="https://gitlab.com/owner/repo",
            host="gitlab.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )
        result = build_source_url(repo_info, "src/file.py", start_line=42, end_line=42)
        assert result == "https://gitlab.com/owner/repo/-/blob/main/src/file.py#L42"

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

    def test_handles_timeout_error(self, tmp_path: Path) -> None:
        """Test returns None when subprocess times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=5)
            result = get_git_remote_url(tmp_path)
            assert result is None

    def test_handles_file_not_found_error(self, tmp_path: Path) -> None:
        """Test returns None when git is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = get_git_remote_url(tmp_path)
            assert result is None

    def test_handles_os_error(self, tmp_path: Path) -> None:
        """Test returns None on OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
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

    def test_handles_timeout_in_first_try(self, tmp_path: Path) -> None:
        """Test handles timeout when getting current branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=5)
            result = get_default_branch(tmp_path)
            # Should fall through all try blocks and return "main"
            assert result == "main"

    def test_handles_file_not_found_in_first_try(self, tmp_path: Path) -> None:
        """Test handles FileNotFoundError when git not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = get_default_branch(tmp_path)
            assert result == "main"

    def test_gets_branch_from_remote_head(self, tmp_path: Path) -> None:
        """Test getting branch from remote HEAD when in detached state."""
        # Create .git directory so path validation passes
        (tmp_path / ".git").mkdir()
        with patch("subprocess.run") as mock_run:
            # First call returns detached HEAD
            mock_result1 = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="HEAD\n", stderr=""
            )
            # Second call returns remote HEAD ref
            mock_result2 = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="refs/remotes/origin/develop\n", stderr=""
            )
            mock_run.side_effect = [mock_result1, mock_result2]

            result = get_default_branch(tmp_path)
            assert result == "develop"

    def test_gets_branch_from_remote_head_when_first_call_fails(self, tmp_path: Path) -> None:
        """Test falling back to remote HEAD when rev-parse fails."""
        with patch("subprocess.run") as mock_run:
            # First call fails
            mock_result1 = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="error"
            )
            # Second call returns remote HEAD ref
            mock_result2 = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="refs/remotes/origin/main\n", stderr=""
            )
            mock_run.side_effect = [mock_result1, mock_result2]

            result = get_default_branch(tmp_path)
            assert result == "main"

    def test_returns_fallback_when_remote_head_empty(self, tmp_path: Path) -> None:
        """Test fallback when remote HEAD returns empty."""
        with patch("subprocess.run") as mock_run:
            # First call returns detached HEAD
            mock_result1 = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="HEAD\n", stderr=""
            )
            # Second call returns empty
            mock_result2 = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            mock_run.side_effect = [mock_result1, mock_result2]

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


class TestParsePorcelainBlame:
    """Tests for _parse_all_porcelain_blame function."""

    def test_parses_single_entry(self) -> None:
        """Test parsing a single blame entry."""
        output = """abc123def456abc123def456abc123def456abc1 1 1 1
author John Doe
author-mail <john@example.com>
author-time 1700000000
author-tz +0000
committer John Doe
committer-mail <john@example.com>
committer-time 1700000000
committer-tz +0000
summary Initial commit
filename test.py
\tdef hello(): pass
"""
        entries = _parse_all_porcelain_blame(output)

        assert len(entries) == 1
        assert entries[0].author == "John Doe"
        assert entries[0].author_email == "john@example.com"
        assert entries[0].commit_hash == "abc123def456abc123def456abc123def456abc1"
        assert entries[0].summary == "Initial commit"

    def test_parses_multiple_entries(self) -> None:
        """Test parsing multiple blame entries."""
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-mail <alice@example.com>
author-time 1700000000
summary First commit
filename test.py
\tline 1
def456abc123def456abc123def456abc123def45678 2 2 1
author Bob
author-mail <bob@example.com>
author-time 1700100000
summary Second commit
filename test.py
\tline 2
"""
        entries = _parse_all_porcelain_blame(output)

        assert len(entries) == 2
        assert entries[0].author == "Alice"
        assert entries[1].author == "Bob"
        # Second entry is more recent
        assert entries[1].date > entries[0].date

    def test_handles_empty_output(self) -> None:
        """Test handling empty output."""
        entries = _parse_all_porcelain_blame("")
        assert entries == []

    def test_handles_missing_fields(self) -> None:
        """Test handling entries with missing optional fields."""
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Jane
author-time 1700000000
filename test.py
\tsome code
"""
        entries = _parse_all_porcelain_blame(output)

        assert len(entries) == 1
        assert entries[0].author == "Jane"
        assert entries[0].author_email is None
        assert entries[0].summary is None


class TestParseLineBlameMap:
    """Tests for _parse_line_blame_map function."""

    def test_builds_line_number_mapping(self) -> None:
        """Test building line number to blame info mapping."""
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-time 1700000000
filename test.py
\tdef foo():
def456abc123def456abc123def456abc123def45678 2 2 1
author Bob
author-time 1700100000
filename test.py
\t    pass
"""
        line_map = _parse_line_blame_map(output)

        assert 1 in line_map
        assert 2 in line_map
        assert line_map[1].author == "Alice"
        assert line_map[2].author == "Bob"


class TestFormatBlameDate:
    """Tests for format_blame_date function."""

    def test_today(self) -> None:
        """Test formatting today's date."""
        now = datetime.now()
        result = format_blame_date(now)
        assert result == "today"

    def test_yesterday(self) -> None:
        """Test formatting yesterday's date."""
        yesterday = datetime.now() - timedelta(days=1)
        result = format_blame_date(yesterday)
        assert result == "yesterday"

    def test_few_days_ago(self) -> None:
        """Test formatting a few days ago."""
        three_days_ago = datetime.now() - timedelta(days=3)
        result = format_blame_date(three_days_ago)
        assert result == "3 days ago"

    def test_weeks_ago(self) -> None:
        """Test formatting weeks ago."""
        two_weeks_ago = datetime.now() - timedelta(days=14)
        result = format_blame_date(two_weeks_ago)
        assert result == "2 weeks ago"

    def test_month_format(self) -> None:
        """Test formatting dates older than a month."""
        old_date = datetime.now() - timedelta(days=60)
        result = format_blame_date(old_date)
        # Should contain month abbreviation and year
        assert len(result) > 5  # e.g., "Nov 15, 2024"

    def test_year_or_older_format(self) -> None:
        """Test formatting dates older than a year."""
        very_old_date = datetime.now() - timedelta(days=400)
        result = format_blame_date(very_old_date)
        # Should still use "Mon DD, YYYY" format
        assert len(result) > 5
        # Verify it contains a year and is properly formatted
        assert "," in result


class TestGetLineBlame:
    """Tests for get_line_blame function."""

    def test_returns_blame_for_line(self, tmp_path: Path) -> None:
        """Test getting blame for a specific line in a git repo."""
        # Set up git repo with a committed file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create and commit a file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add test file"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_line_blame(tmp_path, "test.py", 1)

        assert result is not None
        assert result.author == "Test User"
        assert "test@example.com" in (result.author_email or "")

    def test_returns_none_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns None for non-git directory."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")

        result = get_line_blame(tmp_path, "test.py", 1)
        assert result is None

    def test_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test returns None for nonexistent file."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        result = get_line_blame(tmp_path, "nonexistent.py", 1)
        assert result is None


class TestGetRangeBlame:
    """Tests for get_range_blame function."""

    def test_returns_blame_for_range(self, tmp_path: Path) -> None:
        """Test returns blame for a range of lines."""
        # Set up git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Author"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create and commit a file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('hello')\n    pass\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_range_blame(tmp_path, "test.py", 1, 3)

        assert result is not None
        assert result.author == "Test Author"


class TestGetFileEntityBlame:
    """Tests for get_file_entity_blame function."""

    def test_returns_blame_for_entities(self, tmp_path: Path) -> None:
        """Test getting blame info for multiple entities."""
        # Set up git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "dev@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Developer"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create file with multiple functions
        test_file = tmp_path / "module.py"
        test_file.write_text("""def foo():
    return 1

def bar():
    return 2

class MyClass:
    def method(self):
        pass
""")
        subprocess.run(["git", "add", "module.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add module"],
            cwd=tmp_path,
            capture_output=True,
        )

        entities = [
            ("foo", "function", 1, 2),
            ("bar", "function", 4, 5),
            ("MyClass", "class", 7, 9),
        ]

        result = get_file_entity_blame(tmp_path, "module.py", entities)

        assert len(result) == 3
        assert all(e.last_modified_by == "Developer" for e in result)
        assert result[0].entity_name == "foo"
        assert result[1].entity_name == "bar"
        assert result[2].entity_name == "MyClass"

    def test_returns_empty_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns empty list for non-git directory."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass\n")

        entities = [("foo", "function", 1, 1)]
        result = get_file_entity_blame(tmp_path, "test.py", entities)

        assert result == []

    def test_returns_empty_for_empty_entities(self, tmp_path: Path) -> None:
        """Test returns empty list for empty entities input."""
        result = get_file_entity_blame(tmp_path, "test.py", [])
        assert result == []

    def test_handles_timeout_error(self, tmp_path: Path) -> None:
        """Test returns empty list when subprocess times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=60)
            entities = [("foo", "function", 1, 2)]
            result = get_file_entity_blame(tmp_path, "test.py", entities)
            assert result == []

    def test_handles_file_not_found_error(self, tmp_path: Path) -> None:
        """Test returns empty list when git is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            entities = [("foo", "function", 1, 2)]
            result = get_file_entity_blame(tmp_path, "test.py", entities)
            assert result == []

    def test_handles_os_error(self, tmp_path: Path) -> None:
        """Test returns empty list on OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            entities = [("foo", "function", 1, 2)]
            result = get_file_entity_blame(tmp_path, "test.py", entities)
            assert result == []

    def test_returns_empty_when_line_blame_empty(self, tmp_path: Path) -> None:
        """Test returns empty list when line_blame map is empty."""
        with patch("subprocess.run") as mock_run:
            # Return success but with empty/invalid output
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            entities = [("foo", "function", 1, 2)]
            result = get_file_entity_blame(tmp_path, "test.py", entities)
            assert result == []


class TestGetLineBlameExceptionHandling:
    """Additional tests for get_line_blame exception handling."""

    def test_handles_timeout_error(self, tmp_path: Path) -> None:
        """Test returns None when subprocess times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
            result = get_line_blame(tmp_path, "test.py", 1)
            assert result is None

    def test_handles_file_not_found_error(self, tmp_path: Path) -> None:
        """Test returns None when git is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = get_line_blame(tmp_path, "test.py", 1)
            assert result is None

    def test_handles_os_error(self, tmp_path: Path) -> None:
        """Test returns None on OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            result = get_line_blame(tmp_path, "test.py", 1)
            assert result is None


class TestGetRangeBlameExceptionHandling:
    """Additional tests for get_range_blame exception handling."""

    def test_handles_timeout_error(self, tmp_path: Path) -> None:
        """Test returns None when subprocess times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
            result = get_range_blame(tmp_path, "test.py", 1, 10)
            assert result is None

    def test_handles_file_not_found_error(self, tmp_path: Path) -> None:
        """Test returns None when git is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = get_range_blame(tmp_path, "test.py", 1, 10)
            assert result is None

    def test_handles_os_error(self, tmp_path: Path) -> None:
        """Test returns None on OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            result = get_range_blame(tmp_path, "test.py", 1, 10)
            assert result is None

    def test_returns_none_when_returncode_nonzero(self, tmp_path: Path) -> None:
        """Test returns None when git blame returns non-zero exit code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=128, stdout="", stderr="fatal: no such path"
            )
            result = get_range_blame(tmp_path, "nonexistent.py", 1, 10)
            assert result is None

    def test_returns_none_when_entries_empty(self, tmp_path: Path) -> None:
        """Test returns None when parsed entries are empty."""
        with patch("subprocess.run") as mock_run:
            # Return success but with output that produces no valid entries
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = get_range_blame(tmp_path, "test.py", 1, 10)
            assert result is None


class TestParsePorcelainBlameValueError:
    """Tests for invalid author-time handling in blame parsing."""

    def test_handles_invalid_author_time(self) -> None:
        """Test skipping entries with non-integer author-time."""
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-mail <alice@example.com>
author-time not_a_number
summary Bad commit
filename test.py
\tline 1
"""
        entries = _parse_all_porcelain_blame(output)
        # Entry should be skipped because author_time is not a valid integer
        assert entries == []

    def test_handles_empty_author_time(self) -> None:
        """Test skipping entries with empty author-time."""
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-time
summary Bad commit
filename test.py
\tline 1
"""
        entries = _parse_all_porcelain_blame(output)
        assert entries == []


class TestParseLineBlameMapEdgeCases:
    """Tests for edge cases in _parse_line_blame_map."""

    def test_handles_invalid_author_time(self) -> None:
        """Test skipping entries with non-integer author-time in line map."""
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-time not_a_number
filename test.py
\tdef foo():
"""
        line_map = _parse_line_blame_map(output)
        # Line should not be added because author_time is invalid
        assert 1 not in line_map

    def test_handles_non_commit_lines(self) -> None:
        """Test handling of non-commit lines in output (garbage lines)."""
        output = """some random garbage line
abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-time 1700000000
filename test.py
\tdef foo():
another garbage line
"""
        line_map = _parse_line_blame_map(output)
        # Should still parse the valid entry
        assert 1 in line_map
        assert line_map[1].author == "Alice"

    def test_handles_abbreviated_entry_with_cache(self) -> None:
        """Test handling of abbreviated entries using commit cache."""
        # First entry has full info, second entry from same commit has abbreviated info
        output = """abc123def456abc123def456abc123def456abc12345 1 1 1
author Alice
author-mail <alice@example.com>
author-time 1700000000
summary First commit
filename test.py
\tline 1
abc123def456abc123def456abc123def456abc12345 2 2
filename test.py
\tline 2
"""
        line_map = _parse_line_blame_map(output)
        # Both lines should use the cached blame info
        assert 1 in line_map
        assert 2 in line_map
        assert line_map[1].author == "Alice"
        assert line_map[2].author == "Alice"
        # They should be the same object (cached)
        assert line_map[1] is line_map[2]


class TestGetFileLastModified:
    """Tests for get_file_last_modified function."""

    def test_returns_date_for_committed_file(self, tmp_path: Path) -> None:
        """Test getting last modified date for a committed file."""
        # Set up git repo with a committed file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add file"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_file_last_modified(tmp_path, "test.py")

        assert result is not None
        assert isinstance(result, datetime)
        # Should be within the last minute
        assert (datetime.now() - result).total_seconds() < 60

    def test_returns_none_for_non_git_dir(self, tmp_path: Path) -> None:
        """Test returns None for non-git directory."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")

        result = get_file_last_modified(tmp_path, "test.py")
        assert result is None

    def test_returns_none_for_uncommitted_file(self, tmp_path: Path) -> None:
        """Test returns None for file not in git history."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")

        result = get_file_last_modified(tmp_path, "test.py")
        assert result is None

    def test_handles_timeout_error(self, tmp_path: Path) -> None:
        """Test returns None when subprocess times out."""
        with patch("local_deepwiki.core.git_utils.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
            result = get_file_last_modified(tmp_path, "test.py")
            assert result is None

    def test_handles_file_not_found_error(self, tmp_path: Path) -> None:
        """Test returns None when git is not found."""
        with patch("local_deepwiki.core.git_utils.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = get_file_last_modified(tmp_path, "test.py")
            assert result is None

    def test_handles_os_error(self, tmp_path: Path) -> None:
        """Test returns None on OSError."""
        with patch("local_deepwiki.core.git_utils.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            result = get_file_last_modified(tmp_path, "test.py")
            assert result is None

    def test_handles_value_error_invalid_timestamp(self, tmp_path: Path) -> None:
        """Test returns None when timestamp cannot be parsed."""
        with patch("local_deepwiki.core.git_utils.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="not_a_timestamp\n", stderr=""
            )
            result = get_file_last_modified(tmp_path, "test.py")
            assert result is None


class TestGetFilesLastModified:
    """Tests for get_files_last_modified function."""

    def test_returns_empty_dict_for_empty_file_paths(self, tmp_path: Path) -> None:
        """Test returns empty dict when file_paths is empty."""
        result = get_files_last_modified(tmp_path, [])
        assert result == {}

    def test_returns_dates_for_multiple_files(self, tmp_path: Path) -> None:
        """Test getting modification dates for multiple committed files."""
        # Set up git repo with committed files
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        (tmp_path / "file1.py").write_text("def foo(): pass\n")
        (tmp_path / "file2.py").write_text("def bar(): pass\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add files"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_files_last_modified(tmp_path, ["file1.py", "file2.py"])

        assert len(result) == 2
        assert "file1.py" in result
        assert "file2.py" in result
        assert isinstance(result["file1.py"], datetime)
        assert isinstance(result["file2.py"], datetime)


class TestCheckPageStaleness:
    """Tests for check_page_staleness function."""

    def test_returns_none_for_empty_source_files(self, tmp_path: Path) -> None:
        """Test returns None when source_files is empty."""
        result = check_page_staleness(
            tmp_path, "page.md", datetime.now().timestamp(), []
        )
        assert result is None

    def test_returns_none_when_source_not_newer(self, tmp_path: Path) -> None:
        """Test returns None when source file is not newer than doc."""
        # Set up git repo with a committed file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add file"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Document generated "now" (after the commit)
        future_time = (datetime.now() + timedelta(seconds=10)).timestamp()
        result = check_page_staleness(
            tmp_path, "page.md", future_time, ["test.py"]
        )
        assert result is None

    def test_returns_stale_info_when_source_newer(self, tmp_path: Path) -> None:
        """Test returns StaleInfo when source file is newer than doc."""
        # Set up git repo with a committed file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add file"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Document generated in the past (before the commit)
        past_time = (datetime.now() - timedelta(days=30)).timestamp()
        result = check_page_staleness(
            tmp_path, "page.md", past_time, ["test.py"]
        )

        assert result is not None
        assert isinstance(result, StaleInfo)
        assert result.page_path == "page.md"
        assert result.source_files == ["test.py"]

    def test_returns_none_when_below_threshold(self, tmp_path: Path) -> None:
        """Test returns None when staleness is below threshold."""
        # Set up git repo with a committed file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            capture_output=True,
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add file"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Document generated 1 day ago
        past_time = (datetime.now() - timedelta(days=1)).timestamp()
        # But threshold is 7 days
        result = check_page_staleness(
            tmp_path,
            "page.md",
            past_time,
            ["test.py"],
            stale_threshold_days=7,
        )
        # Should return None because days_stale (around 1) < threshold (7)
        assert result is None

    def test_returns_none_when_no_mod_dates(self, tmp_path: Path) -> None:
        """Test returns None when no modification dates can be retrieved."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        # No committed files, so no modification dates
        past_time = (datetime.now() - timedelta(days=30)).timestamp()
        result = check_page_staleness(
            tmp_path, "page.md", past_time, ["nonexistent.py"]
        )
        assert result is None
