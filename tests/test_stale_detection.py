"""Tests for stale documentation detection."""

import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from local_deepwiki.core.git_utils import (
    StaleInfo,
    check_page_staleness,
    get_file_last_modified,
    get_files_last_modified,
)
from local_deepwiki.generators.analysis.stale_detection import (
    StaleReport,
    add_stale_banners,
    analyze_staleness,
    generate_stale_banner,
    generate_stale_report_page,
)
from local_deepwiki.models import WikiGenerationStatus, WikiPage, WikiPageStatus


class TestGetFileLastModified:
    """Tests for get_file_last_modified function."""

    def test_returns_datetime_for_tracked_file(self, tmp_path: Path) -> None:
        """Test getting modification date for a git-tracked file."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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

        # Create and commit a file
        test_file = tmp_path / "test.py"
        test_file.write_text("# test")
        subprocess.run(["git", "add", "test.py"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_file_last_modified(tmp_path, "test.py")

        assert result is not None
        assert isinstance(result, datetime)
        # Should be within the last minute
        assert (datetime.now(tz=timezone.utc) - result).total_seconds() < 60

    def test_returns_none_for_untracked_file(self, tmp_path: Path) -> None:
        """Test returns None for files not in git."""
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        # Create file but don't commit
        test_file = tmp_path / "untracked.py"
        test_file.write_text("# untracked")

        result = get_file_last_modified(tmp_path, "untracked.py")
        assert result is None

    def test_returns_none_for_non_git_directory(self, tmp_path: Path) -> None:
        """Test returns None for non-git directories."""
        test_file = tmp_path / "file.py"
        test_file.write_text("# test")

        result = get_file_last_modified(tmp_path, "file.py")
        assert result is None


class TestGetFilesLastModified:
    """Tests for get_files_last_modified function."""

    def test_returns_dates_for_multiple_files(self, tmp_path: Path) -> None:
        """Test getting modification dates for multiple files."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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

        # Create and commit files
        (tmp_path / "file1.py").write_text("# file1")
        (tmp_path / "file2.py").write_text("# file2")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add files"],
            cwd=tmp_path,
            capture_output=True,
        )

        result = get_files_last_modified(tmp_path, ["file1.py", "file2.py"])

        assert len(result) == 2
        assert "file1.py" in result
        assert "file2.py" in result

    def test_returns_empty_dict_for_empty_list(self, tmp_path: Path) -> None:
        """Test returns empty dict for empty file list."""
        result = get_files_last_modified(tmp_path, [])
        assert result == {}


class TestCheckPageStaleness:
    """Tests for check_page_staleness function."""

    def test_returns_none_when_doc_is_newer(self, tmp_path: Path) -> None:
        """Test returns None when documentation is up to date."""
        # Initialize git repo with a file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "source.py").write_text("# source")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Documentation generated after the commit
        result = check_page_staleness(
            repo_path=tmp_path,
            page_path="files/source.md",
            generated_at=time.time() + 10,  # 10 seconds in the future
            source_files=["source.py"],
        )

        assert result is None

    def test_returns_stale_info_when_source_is_newer(self, tmp_path: Path) -> None:
        """Test returns StaleInfo when source is newer than doc."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "source.py").write_text("# source")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Documentation generated before the commit (1 day ago)
        old_time = time.time() - 86400  # 1 day ago
        result = check_page_staleness(
            repo_path=tmp_path,
            page_path="files/source.md",
            generated_at=old_time,
            source_files=["source.py"],
        )

        assert result is not None
        assert isinstance(result, StaleInfo)
        assert result.page_path == "files/source.md"
        assert result.days_stale >= 0

    def test_returns_none_for_empty_source_files(self, tmp_path: Path) -> None:
        """Test returns None when no source files provided."""
        result = check_page_staleness(
            repo_path=tmp_path,
            page_path="files/test.md",
            generated_at=time.time(),
            source_files=[],
        )
        assert result is None


class TestAnalyzeStaleness:
    """Tests for analyze_staleness function."""

    def test_returns_report_with_counts(self, tmp_path: Path) -> None:
        """Test returns a StaleReport with correct counts."""
        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=2,
            pages={
                "files/test.md": WikiPageStatus(
                    path="files/test.md",
                    source_files=["test.py"],
                    source_hashes={"test.py": "abc123"},
                    content_hash="xyz789",
                    generated_at=time.time(),
                ),
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=[],
                    source_hashes={},
                    content_hash="def456",
                    generated_at=time.time(),
                ),
            },
        )

        result = analyze_staleness(tmp_path, wiki_status)

        assert isinstance(result, StaleReport)
        assert result.total_pages == 1  # Only files/ pages are counted


class TestGenerateStaleReportPage:
    """Tests for generate_stale_report_page function."""

    def test_generates_wiki_page(self, tmp_path: Path) -> None:
        """Test generates a valid WikiPage."""
        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=1,
            pages={
                "files/test.md": WikiPageStatus(
                    path="files/test.md",
                    source_files=["test.py"],
                    source_hashes={"test.py": "abc123"},
                    content_hash="xyz789",
                    generated_at=time.time(),
                ),
            },
        )

        result = generate_stale_report_page(tmp_path, wiki_status)

        assert isinstance(result, WikiPage)
        assert result.path == "freshness.md"
        assert result.title == "Documentation Freshness"
        assert "Documentation Freshness Report" in result.content

    def test_shows_all_up_to_date_when_no_stale(self, tmp_path: Path) -> None:
        """Test shows success message when all docs are current."""
        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=0,
            pages={},
        )

        result = generate_stale_report_page(tmp_path, wiki_status)

        assert "All Documentation Up to Date" in result.content


class TestGenerateStaleBanner:
    """Tests for generate_stale_banner function."""

    def test_generates_warning_banner(self) -> None:
        """Test generates a markdown warning banner."""
        stale_info = StaleInfo(
            page_path="files/test.md",
            generated_at=datetime.now() - timedelta(days=5),
            source_files=["test.py"],
            newest_source_date=datetime.now(),
            days_stale=5,
        )

        result = generate_stale_banner(stale_info)

        assert "⚠️" in result
        assert "outdated" in result.lower()
        assert "5 days" in result


class TestAddStaleBanners:
    """Tests for add_stale_banners function."""

    def test_adds_banner_to_stale_pages(self, tmp_path: Path) -> None:
        """Test adds banners to pages with stale documentation."""
        # Initialize git repo with a recent commit
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "test.py").write_text("# test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create a page with old generation time
        old_time = time.time() - 86400 * 10  # 10 days ago
        pages = [
            WikiPage(
                path="files/test.md",
                title="Test",
                content="# Test\n\nContent here.",
                generated_at=old_time,
            )
        ]

        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=1,
            pages={
                "files/test.md": WikiPageStatus(
                    path="files/test.md",
                    source_files=["test.py"],
                    source_hashes={"test.py": "abc123"},
                    content_hash="xyz789",
                    generated_at=old_time,
                ),
            },
        )

        result = add_stale_banners(pages, tmp_path, wiki_status, stale_threshold_days=1)

        assert len(result) == 1
        # Should have banner prepended
        assert "⚠️" in result[0].content
        assert "# Test" in result[0].content  # Original content still there

    def test_does_not_add_banner_to_fresh_pages(self, tmp_path: Path) -> None:
        """Test does not add banners to up-to-date pages."""
        pages = [
            WikiPage(
                path="files/test.md",
                title="Test",
                content="# Test\n\nContent here.",
                generated_at=time.time(),
            )
        ]

        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=1,
            pages={
                "files/test.md": WikiPageStatus(
                    path="files/test.md",
                    source_files=[],  # No source files = not stale
                    source_hashes={},
                    content_hash="xyz789",
                    generated_at=time.time(),
                ),
            },
        )

        result = add_stale_banners(pages, tmp_path, wiki_status)

        assert len(result) == 1
        assert "⚠️" not in result[0].content

    def test_does_not_add_banner_to_non_file_pages(self, tmp_path: Path) -> None:
        """Test does not add banners to non-file pages (index, overview, etc.)."""
        pages = [
            WikiPage(
                path="index.md",
                title="Index",
                content="# Index\n\nOverview content.",
                generated_at=time.time(),
            )
        ]

        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=1,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["test.py"],
                    source_hashes={"test.py": "abc123"},
                    content_hash="xyz789",
                    generated_at=time.time() - 86400,  # Old
                ),
            },
        )

        result = add_stale_banners(pages, tmp_path, wiki_status)

        assert len(result) == 1
        # Should not have banner since path doesn't start with "files/"
        assert "⚠️" not in result[0].content

    def test_preserves_pages_without_status(self, tmp_path: Path) -> None:
        """Test preserves pages that don't have status info."""
        pages = [
            WikiPage(
                path="files/unknown.md",
                title="Unknown",
                content="# Unknown\n\nContent.",
                generated_at=time.time(),
            )
        ]

        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=0,
            pages={},  # No status for this page
        )

        result = add_stale_banners(pages, tmp_path, wiki_status)

        assert len(result) == 1
        assert result[0].content == "# Unknown\n\nContent."


class TestAnalyzeStalenessWithStalePages:
    """Tests for analyze_staleness when stale pages exist."""

    def test_detects_stale_pages(self, tmp_path: Path) -> None:
        """Test detects and returns stale pages."""
        # Initialize git repo with a recent commit
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "source.py").write_text("# source code")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create wiki status with OLD generation time (before commit)
        old_time = time.time() - 86400 * 5  # 5 days ago
        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=old_time,
            total_pages=1,
            pages={
                "files/source.md": WikiPageStatus(
                    path="files/source.md",
                    source_files=["source.py"],
                    source_hashes={"source.py": "abc123"},
                    content_hash="xyz789",
                    generated_at=old_time,
                ),
            },
        )

        result = analyze_staleness(tmp_path, wiki_status)

        assert isinstance(result, StaleReport)
        assert result.total_pages == 1
        assert result.stale_pages == 1
        assert len(result.stale_info) == 1
        assert result.stale_info[0].page_path == "files/source.md"

    def test_sorts_stale_pages_by_staleness(self, tmp_path: Path) -> None:
        """Test that stale pages are sorted by days stale (most stale first)."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "old.py").write_text("# old")
        (tmp_path / "new.py").write_text("# new")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create wiki status with different generation times
        very_old_time = time.time() - 86400 * 10  # 10 days ago
        slightly_old_time = time.time() - 86400 * 2  # 2 days ago

        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=2,
            pages={
                "files/new.md": WikiPageStatus(
                    path="files/new.md",
                    source_files=["new.py"],
                    source_hashes={"new.py": "abc"},
                    content_hash="xyz",
                    generated_at=slightly_old_time,
                ),
                "files/old.md": WikiPageStatus(
                    path="files/old.md",
                    source_files=["old.py"],
                    source_hashes={"old.py": "def"},
                    content_hash="uvw",
                    generated_at=very_old_time,
                ),
            },
        )

        result = analyze_staleness(tmp_path, wiki_status)

        assert result.stale_pages == 2
        # Should be sorted by days_stale descending (most stale first)
        assert result.stale_info[0].days_stale >= result.stale_info[1].days_stale


class TestGenerateStaleReportPageWithStalePages:
    """Tests for generate_stale_report_page when stale pages exist."""

    def test_generates_report_with_stale_pages_table(self, tmp_path: Path) -> None:
        """Test generates report with summary and stale pages table."""
        # Initialize git repo with a recent commit
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "stale.py").write_text("# stale code")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create wiki status with OLD generation time
        old_time = time.time() - 86400 * 5  # 5 days ago
        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=old_time,
            total_pages=2,
            pages={
                "files/stale.md": WikiPageStatus(
                    path="files/stale.md",
                    source_files=["stale.py"],
                    source_hashes={"stale.py": "abc123"},
                    content_hash="xyz789",
                    generated_at=old_time,
                ),
                "files/fresh.md": WikiPageStatus(
                    path="files/fresh.md",
                    source_files=[],  # No source files = not stale
                    source_hashes={},
                    content_hash="def456",
                    generated_at=time.time(),
                ),
            },
        )

        result = generate_stale_report_page(tmp_path, wiki_status)

        assert isinstance(result, WikiPage)
        assert result.path == "freshness.md"
        # Should contain summary section
        assert "## Summary" in result.content
        assert "Total file pages" in result.content
        assert "Potentially stale" in result.content
        assert "Freshness" in result.content
        # Should contain stale pages section
        assert "Potentially Stale Documentation" in result.content
        assert "Page | Days Stale" in result.content
        # Should contain link to stale page
        assert "stale" in result.content
        # Should contain recommendations
        assert "Recommendations" in result.content

    def test_calculates_freshness_percentage(self, tmp_path: Path) -> None:
        """Test calculates correct freshness percentage."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
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
        (tmp_path / "file1.py").write_text("# file1")
        (tmp_path / "file2.py").write_text("# file2")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
        )

        old_time = time.time() - 86400 * 5
        wiki_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=4,
            pages={
                "files/file1.md": WikiPageStatus(
                    path="files/file1.md",
                    source_files=["file1.py"],
                    source_hashes={"file1.py": "abc"},
                    content_hash="xyz",
                    generated_at=old_time,  # Stale
                ),
                "files/file2.md": WikiPageStatus(
                    path="files/file2.md",
                    source_files=["file2.py"],
                    source_hashes={"file2.py": "def"},
                    content_hash="uvw",
                    generated_at=old_time,  # Stale
                ),
                "files/fresh1.md": WikiPageStatus(
                    path="files/fresh1.md",
                    source_files=[],
                    source_hashes={},
                    content_hash="aaa",
                    generated_at=time.time(),  # Fresh
                ),
                "files/fresh2.md": WikiPageStatus(
                    path="files/fresh2.md",
                    source_files=[],
                    source_hashes={},
                    content_hash="bbb",
                    generated_at=time.time(),  # Fresh
                ),
            },
        )

        result = generate_stale_report_page(tmp_path, wiki_status)

        # 2 fresh out of 4 = 50% freshness
        assert "50%" in result.content
