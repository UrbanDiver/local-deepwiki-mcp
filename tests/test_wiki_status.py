"""Tests for wiki status management functionality."""

import json
import time
from pathlib import Path

import pytest

from local_deepwiki.generators.wiki_status import WikiStatusManager
from local_deepwiki.models import WikiGenerationStatus, WikiPage, WikiPageStatus


class TestWikiStatusManager:
    """Tests for WikiStatusManager class."""

    def test_creation(self, tmp_path):
        """Test creating a WikiStatusManager instance."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        assert manager.wiki_path == tmp_path
        assert manager.file_hashes == {}
        assert manager.file_line_info == {}
        assert manager.page_statuses == {}
        assert manager.previous_status is None

    def test_file_hashes_property(self, tmp_path):
        """Test file_hashes getter and setter."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        test_hashes = {"src/main.py": "abc123", "src/utils.py": "def456"}
        manager.file_hashes = test_hashes
        assert manager.file_hashes == test_hashes

    def test_file_line_info_property(self, tmp_path):
        """Test file_line_info getter and setter."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        test_info = {"src/main.py": (1, 100), "src/utils.py": (1, 50)}
        manager.file_line_info = test_info
        assert manager.file_line_info == test_info


class TestWikiStatusManagerLoadStatus:
    """Tests for load_status method."""

    async def test_load_status_no_file(self, tmp_path):
        """Test loading status when file does not exist."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        result = await manager.load_status()
        assert result is None
        assert manager.previous_status is None

    async def test_load_status_valid_file(self, tmp_path):
        """Test loading status from valid file."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        status_data = {
            "repo_path": "/test/repo",
            "generated_at": 1234567890.0,
            "total_pages": 5,
            "pages": {}
        }
        status_file = tmp_path / "wiki_status.json"
        with open(status_file, "w") as f:
            json.dump(status_data, f)

        result = await manager.load_status()
        assert result is not None
        assert result.repo_path == "/test/repo"
        assert result.total_pages == 5
        assert manager.previous_status == result

    async def test_load_status_invalid_json(self, tmp_path):
        """Test loading status from invalid JSON file."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        status_file = tmp_path / "wiki_status.json"
        status_file.write_text("not valid json")

        result = await manager.load_status()
        assert result is None

    async def test_load_status_invalid_schema(self, tmp_path):
        """Test loading status from file with invalid schema."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        status_file = tmp_path / "wiki_status.json"
        with open(status_file, "w") as f:
            json.dump({"invalid": "data"}, f)

        result = await manager.load_status()
        assert result is None


class TestWikiStatusManagerSaveStatus:
    """Tests for save_status method."""

    async def test_save_status(self, tmp_path):
        """Test saving wiki generation status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        status = WikiGenerationStatus(
            repo_path="/test/repo",
            generated_at=1234567890.0,
            total_pages=10,
        )
        
        await manager.save_status(status)
        
        status_file = tmp_path / "wiki_status.json"
        assert status_file.exists()
        
        with open(status_file) as f:
            data = json.load(f)
        
        assert data["repo_path"] == "/test/repo"
        assert data["total_pages"] == 10

    async def test_save_status_with_pages(self, tmp_path):
        """Test saving status with page information."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        page_status = WikiPageStatus(
            path="files/main.md",
            source_files=["src/main.py"],
            source_hashes={"src/main.py": "abc123"},
            content_hash="xyz789",
            generated_at=1234567890.0,
        )
        
        status = WikiGenerationStatus(
            repo_path="/test/repo",
            generated_at=1234567890.0,
            total_pages=1,
            pages={"files/main.md": page_status},
        )
        
        await manager.save_status(status)
        
        status_file = tmp_path / "wiki_status.json"
        with open(status_file) as f:
            data = json.load(f)
        
        assert "files/main.md" in data["pages"]
        assert data["pages"]["files/main.md"]["source_files"] == ["src/main.py"]


class TestWikiStatusManagerComputeContentHash:
    """Tests for compute_content_hash method."""

    def test_compute_content_hash(self, tmp_path):
        """Test computing content hash."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        content = "# Test Page with content"
        hash1 = manager.compute_content_hash(content)
        
        hash2 = manager.compute_content_hash(content)
        assert hash1 == hash2
        
        assert len(hash1) == 16
        
    def test_compute_content_hash_different_content(self, tmp_path):
        """Test that different content produces different hashes."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        hash1 = manager.compute_content_hash("content1")
        hash2 = manager.compute_content_hash("content2")
        
        assert hash1 != hash2


class TestWikiStatusManagerNeedsRegeneration:
    """Tests for needs_regeneration method."""

    def test_needs_regeneration_no_previous_status(self, tmp_path):
        """Test needs_regeneration returns True when no previous status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        result = manager.needs_regeneration("files/main.md", ["src/main.py"])
        assert result is True

    def test_needs_regeneration_page_not_in_previous(self, tmp_path):
        """Test needs_regeneration returns True for new page."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=0,
            pages={},
        )
        
        result = manager.needs_regeneration("files/new.md", ["src/new.py"])
        assert result is True

    def test_needs_regeneration_source_file_changed(self, tmp_path):
        """Test needs_regeneration returns True when source file changed."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/main.py": "new_hash"}
        
        page_status = WikiPageStatus(
            path="files/main.md",
            source_files=["src/main.py"],
            source_hashes={"src/main.py": "old_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"files/main.md": page_status},
        )
        
        result = manager.needs_regeneration("files/main.md", ["src/main.py"])
        assert result is True

    def test_needs_regeneration_no_change(self, tmp_path):
        """Test needs_regeneration returns False when nothing changed."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/main.py": "same_hash"}
        
        page_status = WikiPageStatus(
            path="files/main.md",
            source_files=["src/main.py"],
            source_hashes={"src/main.py": "same_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"files/main.md": page_status},
        )
        
        result = manager.needs_regeneration("files/main.md", ["src/main.py"])
        assert result is False

    def test_needs_regeneration_source_files_changed(self, tmp_path):
        """Test needs_regeneration returns True when source files list changed."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/main.py": "hash1", "src/utils.py": "hash2"}
        
        page_status = WikiPageStatus(
            path="files/main.md",
            source_files=["src/main.py"],
            source_hashes={"src/main.py": "hash1"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"files/main.md": page_status},
        )
        
        result = manager.needs_regeneration("files/main.md", ["src/main.py", "src/utils.py"])
        assert result is True

    def test_needs_regeneration_missing_current_hash(self, tmp_path):
        """Test needs_regeneration returns True when current hash is missing."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {}
        
        page_status = WikiPageStatus(
            path="files/main.md",
            source_files=["src/main.py"],
            source_hashes={"src/main.py": "old_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"files/main.md": page_status},
        )
        
        result = manager.needs_regeneration("files/main.md", ["src/main.py"])
        assert result is True


class TestWikiStatusManagerLoadExistingPage:
    """Tests for load_existing_page method."""

    async def test_load_existing_page_not_found(self, tmp_path):
        """Test loading page that does not exist."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        result = await manager.load_existing_page("files/nonexistent.md")
        assert result is None

    async def test_load_existing_page(self, tmp_path):
        """Test loading existing page."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        page_dir = tmp_path / "files"
        page_dir.mkdir(parents=True)
        page_file = page_dir / "test.md"
        page_file.write_text("# Test Page")
        
        result = await manager.load_existing_page("files/test.md")
        assert result is not None
        assert result.path == "files/test.md"
        assert "# Test Page" in result.content

    async def test_load_existing_page_with_previous_status(self, tmp_path):
        """Test loading existing page uses previous status timestamp."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        
        page_status = WikiPageStatus(
            path="files/test.md",
            source_files=["src/test.py"],
            source_hashes={},
            content_hash="xyz",
            generated_at=1234567890.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"files/test.md": page_status},
        )
        
        page_dir = tmp_path / "files"
        page_dir.mkdir(parents=True)
        page_file = page_dir / "test.md"
        page_file.write_text("# Test")
        
        result = await manager.load_existing_page("files/test.md")
        assert result is not None
        assert result.generated_at == 1234567890.0


class TestWikiStatusManagerRecordPageStatus:
    """Tests for record_page_status method."""

    def test_record_page_status(self, tmp_path):
        """Test recording page status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/main.py": "abc123"}
        
        page = WikiPage(
            path="files/main.md",
            title="Main Module",
            content="# Main Content",
            generated_at=1234567890.0,
        )
        
        manager.record_page_status(page, ["src/main.py"])
        
        assert "files/main.md" in manager.page_statuses
        status = manager.page_statuses["files/main.md"]
        assert status.path == "files/main.md"
        assert status.source_files == ["src/main.py"]
        assert status.source_hashes == {"src/main.py": "abc123"}
        assert status.generated_at == 1234567890.0

    def test_record_page_status_with_line_info(self, tmp_path):
        """Test recording page status with line info."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/main.py": "abc123"}
        manager.file_line_info = {"src/main.py": (1, 100)}
        
        page = WikiPage(
            path="files/main.md",
            title="Main",
            content="# Main",
            generated_at=1.0,
        )
        
        manager.record_page_status(page, ["src/main.py"])
        
        status = manager.page_statuses["files/main.md"]
        assert "src/main.py" in status.source_line_info
        assert status.source_line_info["src/main.py"] == {"start_line": 1, "end_line": 100}

    def test_record_page_status_missing_hash(self, tmp_path):
        """Test recording page status when file hash is missing."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {}
        
        page = WikiPage(
            path="files/main.md",
            title="Main",
            content="# Main",
            generated_at=1.0,
        )
        
        manager.record_page_status(page, ["src/main.py"])
        
        status = manager.page_statuses["files/main.md"]
        assert status.source_hashes == {"src/main.py": ""}

    def test_record_page_status_content_hash(self, tmp_path):
        """Test that content hash is computed for recorded status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {}
        
        page = WikiPage(
            path="files/main.md",
            title="Main",
            content="# Unique Content",
            generated_at=1.0,
        )
        
        manager.record_page_status(page, [])
        
        status = manager.page_statuses["files/main.md"]
        assert len(status.content_hash) == 16
