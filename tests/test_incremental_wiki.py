"""Tests for incremental wiki generation."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.models import (
    FileInfo,
    IndexStatus,
    Language,
    WikiGenerationStatus,
    WikiPage,
    WikiPageStatus,
)


class TestWikiPageStatus:
    """Test WikiPageStatus model."""

    def test_create_page_status(self):
        """Test creating a WikiPageStatus."""
        status = WikiPageStatus(
            path="files/test.md",
            source_files=["src/test.py"],
            source_hashes={"src/test.py": "abc123"},
            content_hash="def456",
            generated_at=time.time(),
        )
        assert status.path == "files/test.md"
        assert status.source_files == ["src/test.py"]
        assert status.source_hashes["src/test.py"] == "abc123"
        assert status.content_hash == "def456"

    def test_page_status_multiple_sources(self):
        """Test page status with multiple source files."""
        status = WikiPageStatus(
            path="modules/core.md",
            source_files=["src/core/a.py", "src/core/b.py"],
            source_hashes={"src/core/a.py": "hash1", "src/core/b.py": "hash2"},
            content_hash="contenthash",
            generated_at=time.time(),
        )
        assert len(status.source_files) == 2
        assert len(status.source_hashes) == 2


class TestWikiGenerationStatus:
    """Test WikiGenerationStatus model."""

    def test_create_generation_status(self):
        """Test creating a WikiGenerationStatus."""
        status = WikiGenerationStatus(
            repo_path="/path/to/repo",
            generated_at=time.time(),
            total_pages=5,
            index_status_hash="abc123",
            pages={},
        )
        assert status.repo_path == "/path/to/repo"
        assert status.total_pages == 5

    def test_generation_status_with_pages(self):
        """Test generation status with page statuses."""
        page_status = WikiPageStatus(
            path="index.md",
            source_files=["src/main.py"],
            source_hashes={"src/main.py": "hash1"},
            content_hash="contenthash",
            generated_at=time.time(),
        )
        status = WikiGenerationStatus(
            repo_path="/path/to/repo",
            generated_at=time.time(),
            total_pages=1,
            index_status_hash="abc123",
            pages={"index.md": page_status},
        )
        assert "index.md" in status.pages
        assert status.pages["index.md"].source_files == ["src/main.py"]


class TestWikiGeneratorHelpers:
    """Test WikiGenerator helper methods."""

    @pytest.fixture
    def mock_wiki_generator(self):
        """Create a mock WikiGenerator."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = Path("/tmp/test_wiki")
            generator._file_hashes = {
                "src/test.py": "current_hash",
                "src/other.py": "other_hash",
            }
            generator._previous_status = None
            generator._page_statuses = {}
            generator._file_line_info = {}  # For source refs with line numbers
            return generator

    def test_compute_content_hash(self, mock_wiki_generator):
        """Test content hash computation."""
        hash1 = mock_wiki_generator._compute_content_hash("Hello World")
        hash2 = mock_wiki_generator._compute_content_hash("Hello World")
        hash3 = mock_wiki_generator._compute_content_hash("Different content")

        assert hash1 == hash2  # Same content should produce same hash
        assert hash1 != hash3  # Different content should produce different hash
        assert len(hash1) == 16  # Should be 16 chars (truncated SHA256)

    def test_needs_regeneration_no_previous_status(self, mock_wiki_generator):
        """Test needs_regeneration when no previous status exists."""
        result = mock_wiki_generator._needs_regeneration("index.md", ["src/test.py"])
        assert result is True

    def test_needs_regeneration_page_not_in_status(self, mock_wiki_generator):
        """Test needs_regeneration when page not in previous status."""
        mock_wiki_generator._previous_status = WikiGenerationStatus(
            repo_path="/repo",
            generated_at=time.time(),
            total_pages=1,
            pages={},
        )
        result = mock_wiki_generator._needs_regeneration("new_page.md", ["src/test.py"])
        assert result is True

    def test_needs_regeneration_source_hash_changed(self, mock_wiki_generator):
        """Test needs_regeneration when source file hash changed."""
        mock_wiki_generator._previous_status = WikiGenerationStatus(
            repo_path="/repo",
            generated_at=time.time(),
            total_pages=1,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/test.py"],
                    source_hashes={"src/test.py": "old_hash"},  # Different from current
                    content_hash="contenthash",
                    generated_at=time.time(),
                )
            },
        )
        result = mock_wiki_generator._needs_regeneration("index.md", ["src/test.py"])
        assert result is True  # Hash changed, should regenerate

    def test_needs_regeneration_no_changes(self, mock_wiki_generator):
        """Test needs_regeneration when nothing changed."""
        mock_wiki_generator._previous_status = WikiGenerationStatus(
            repo_path="/repo",
            generated_at=time.time(),
            total_pages=1,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/test.py"],
                    source_hashes={"src/test.py": "current_hash"},  # Same as current
                    content_hash="contenthash",
                    generated_at=time.time(),
                )
            },
        )
        result = mock_wiki_generator._needs_regeneration("index.md", ["src/test.py"])
        assert result is False  # No changes, should skip

    def test_needs_regeneration_source_files_changed(self, mock_wiki_generator):
        """Test needs_regeneration when source files list changed."""
        mock_wiki_generator._previous_status = WikiGenerationStatus(
            repo_path="/repo",
            generated_at=time.time(),
            total_pages=1,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/test.py"],  # Only had one file
                    source_hashes={"src/test.py": "current_hash"},
                    content_hash="contenthash",
                    generated_at=time.time(),
                )
            },
        )
        # Now depends on two files
        result = mock_wiki_generator._needs_regeneration(
            "index.md", ["src/test.py", "src/other.py"]
        )
        assert result is True  # Source files list changed

    def test_record_page_status(self, mock_wiki_generator):
        """Test recording page status."""
        page = WikiPage(
            path="test.md",
            title="Test",
            content="# Test\nContent here",
            generated_at=time.time(),
        )
        mock_wiki_generator._record_page_status(page, ["src/test.py"])

        assert "test.md" in mock_wiki_generator._page_statuses
        status = mock_wiki_generator._page_statuses["test.md"]
        assert status.source_files == ["src/test.py"]
        assert status.source_hashes["src/test.py"] == "current_hash"
        assert len(status.content_hash) == 16


class TestWikiStatusPersistence:
    """Test wiki status file persistence."""

    async def test_save_and_load_wiki_status(self, tmp_path):
        """Test saving and loading wiki status."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = tmp_path

            # Create a status to save
            page_status = WikiPageStatus(
                path="index.md",
                source_files=["src/main.py"],
                source_hashes={"src/main.py": "hash123"},
                content_hash="contenthash",
                generated_at=time.time(),
            )
            status = WikiGenerationStatus(
                repo_path="/test/repo",
                generated_at=time.time(),
                total_pages=1,
                index_status_hash="indexhash",
                pages={"index.md": page_status},
            )

            # Save
            await generator._save_wiki_status(status)

            # Check file exists
            status_file = tmp_path / "wiki_status.json"
            assert status_file.exists()

            # Load
            loaded = await generator._load_wiki_status()
            assert loaded is not None
            assert loaded.repo_path == "/test/repo"
            assert loaded.total_pages == 1
            assert "index.md" in loaded.pages
            assert loaded.pages["index.md"].source_files == ["src/main.py"]

    async def test_load_missing_status(self, tmp_path):
        """Test loading when status file doesn't exist."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = tmp_path

            loaded = await generator._load_wiki_status()
            assert loaded is None

    async def test_load_corrupted_status(self, tmp_path):
        """Test loading when status file is corrupted."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = tmp_path

            # Write corrupted JSON
            status_file = tmp_path / "wiki_status.json"
            status_file.write_text("not valid json {{{")

            loaded = await generator._load_wiki_status()
            assert loaded is None


class TestLoadExistingPage:
    """Test loading existing wiki pages."""

    async def test_load_existing_page(self, tmp_path):
        """Test loading an existing page from disk."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = tmp_path
            generator._previous_status = None

            # Create a test page
            page_path = tmp_path / "test.md"
            page_path.write_text("# Test Page\n\nSome content")

            loaded = await generator._load_existing_page("test.md")
            assert loaded is not None
            assert loaded.path == "test.md"
            assert "# Test Page" in loaded.content

    async def test_load_missing_page(self, tmp_path):
        """Test loading a page that doesn't exist."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = tmp_path
            generator._previous_status = None

            loaded = await generator._load_existing_page("nonexistent.md")
            assert loaded is None

    async def test_load_page_uses_previous_timestamp(self, tmp_path):
        """Test that loaded page uses timestamp from previous status."""
        from local_deepwiki.generators.wiki import WikiGenerator

        with patch.object(WikiGenerator, "__init__", lambda x, *args, **kwargs: None):
            generator = WikiGenerator.__new__(WikiGenerator)
            generator.wiki_path = tmp_path

            # Set up previous status with known timestamp
            prev_time = 12345.0
            generator._previous_status = WikiGenerationStatus(
                repo_path="/repo",
                generated_at=time.time(),
                total_pages=1,
                pages={
                    "test.md": WikiPageStatus(
                        path="test.md",
                        source_files=["src/test.py"],
                        source_hashes={},
                        content_hash="hash",
                        generated_at=prev_time,
                    )
                },
            )

            # Create the page
            page_path = tmp_path / "test.md"
            page_path.write_text("# Test\nContent")

            loaded = await generator._load_existing_page("test.md")
            assert loaded is not None
            assert loaded.generated_at == prev_time
