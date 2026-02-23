"""Tests for wiki status management functionality."""

import json

from local_deepwiki.generators.wiki.status import WikiStatusManager
from local_deepwiki.models import (
    IndexStatus,
    WikiGenerationStatus,
    WikiPage,
    WikiPageStatus,
)
from local_deepwiki.models.chunks import FileInfo


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
            "pages": {},
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

        result = manager.needs_regeneration(
            "files/main.md", ["src/main.py", "src/utils.py"]
        )
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
        assert status.source_line_info["src/main.py"] == {
            "start_line": 1,
            "end_line": 100,
        }

    def test_record_page_status_missing_hash(self, tmp_path):
        """Test recording page status omits files with no hash (prevents poisoning)."""
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
        # Missing hashes are omitted instead of storing empty strings
        assert status.source_hashes == {}

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


class TestWikiStatusManagerGetChangedFiles:
    """Tests for get_changed_files method."""

    def test_no_previous_status_all_files_changed(self, tmp_path):
        """Test all files reported as changed when no previous status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "hash1", "src/b.py": "hash2"}

        changed = manager.get_changed_files()

        assert changed == {"src/a.py", "src/b.py"}

    def test_detects_changed_file(self, tmp_path):
        """Test detecting a changed file."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "new_hash", "src/b.py": "same_hash"}

        page_status = WikiPageStatus(
            path="files/a.md",
            source_files=["src/a.py"],
            source_hashes={"src/a.py": "old_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        page_status_b = WikiPageStatus(
            path="files/b.md",
            source_files=["src/b.py"],
            source_hashes={"src/b.py": "same_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=2,
            pages={"files/a.md": page_status, "files/b.md": page_status_b},
        )

        changed = manager.get_changed_files()

        assert "src/a.py" in changed
        assert "src/b.py" not in changed

    def test_detects_new_file(self, tmp_path):
        """Test detecting a new file not in previous status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "hash1", "src/new.py": "hash2"}

        page_status = WikiPageStatus(
            path="files/a.md",
            source_files=["src/a.py"],
            source_hashes={"src/a.py": "hash1"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"files/a.md": page_status},
        )

        changed = manager.get_changed_files()

        assert "src/new.py" in changed
        assert "src/a.py" not in changed


class TestWikiStatusManagerBuildReverseIndex:
    """Tests for build_reverse_index method."""

    def test_no_previous_status_empty_index(self, tmp_path):
        """Test empty reverse index when no previous status."""
        manager = WikiStatusManager(wiki_path=tmp_path)

        reverse_index = manager.build_reverse_index()

        assert reverse_index == {}

    def test_builds_reverse_index(self, tmp_path):
        """Test building reverse index from previous status."""
        manager = WikiStatusManager(wiki_path=tmp_path)

        page_status_a = WikiPageStatus(
            path="files/a.md",
            source_files=["src/a.py", "src/shared.py"],
            source_hashes={"src/a.py": "h1", "src/shared.py": "h2"},
            content_hash="xyz",
            generated_at=1.0,
        )
        page_status_b = WikiPageStatus(
            path="files/b.md",
            source_files=["src/b.py", "src/shared.py"],
            source_hashes={"src/b.py": "h3", "src/shared.py": "h2"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=2,
            pages={"files/a.md": page_status_a, "files/b.md": page_status_b},
        )

        reverse_index = manager.build_reverse_index()

        assert reverse_index["src/a.py"] == {"files/a.md"}
        assert reverse_index["src/b.py"] == {"files/b.md"}
        assert reverse_index["src/shared.py"] == {"files/a.md", "files/b.md"}


class TestWikiStatusManagerGetAffectedPages:
    """Tests for get_affected_pages method."""

    def test_no_changes_no_affected_pages(self, tmp_path):
        """Test no affected pages when nothing changed."""
        manager = WikiStatusManager(wiki_path=tmp_path)

        affected = manager.get_affected_pages(changed_files=set())

        assert affected == set()

    def test_finds_affected_pages(self, tmp_path):
        """Test finding pages affected by file changes."""
        manager = WikiStatusManager(wiki_path=tmp_path)

        page_status_a = WikiPageStatus(
            path="files/a.md",
            source_files=["src/a.py"],
            source_hashes={"src/a.py": "h1"},
            content_hash="xyz",
            generated_at=1.0,
        )
        page_status_b = WikiPageStatus(
            path="files/b.md",
            source_files=["src/b.py"],
            source_hashes={"src/b.py": "h2"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=2,
            pages={"files/a.md": page_status_a, "files/b.md": page_status_b},
        )

        affected = manager.get_affected_pages(changed_files={"src/a.py"})

        assert affected == {"files/a.md"}

    def test_shared_file_affects_multiple_pages(self, tmp_path):
        """Test that changing a shared file affects multiple pages."""
        manager = WikiStatusManager(wiki_path=tmp_path)

        page_status_a = WikiPageStatus(
            path="files/a.md",
            source_files=["src/shared.py"],
            source_hashes={"src/shared.py": "h1"},
            content_hash="xyz",
            generated_at=1.0,
        )
        page_status_b = WikiPageStatus(
            path="files/b.md",
            source_files=["src/shared.py"],
            source_hashes={"src/shared.py": "h1"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=2,
            pages={"files/a.md": page_status_a, "files/b.md": page_status_b},
        )

        affected = manager.get_affected_pages(changed_files={"src/shared.py"})

        assert affected == {"files/a.md", "files/b.md"}


class TestWikiStatusManagerGetRegenerationSummary:
    """Tests for get_regeneration_summary method."""

    def test_summary_full_rebuild(self, tmp_path):
        """Test summary when doing full rebuild (no previous status)."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "h1", "src/b.py": "h2"}

        summary = manager.get_regeneration_summary()

        assert summary["is_full_rebuild"] is True
        assert summary["changed_file_count"] == 2
        assert set(summary["changed_files"]) == {"src/a.py", "src/b.py"}

    def test_summary_incremental(self, tmp_path):
        """Test summary for incremental update."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "new_hash", "src/b.py": "same_hash"}

        page_status_a = WikiPageStatus(
            path="files/a.md",
            source_files=["src/a.py"],
            source_hashes={"src/a.py": "old_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        page_status_b = WikiPageStatus(
            path="files/b.md",
            source_files=["src/b.py"],
            source_hashes={"src/b.py": "same_hash"},
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=2,
            pages={"files/a.md": page_status_a, "files/b.md": page_status_b},
        )

        summary = manager.get_regeneration_summary()

        assert summary["is_full_rebuild"] is False
        assert summary["changed_file_count"] == 1
        assert summary["affected_page_count"] == 1
        assert summary["unchanged_page_count"] == 1
        assert "src/a.py" in summary["changed_files"]
        assert "files/a.md" in summary["affected_pages"]


def _make_index_status(files, languages=None):
    """Helper to build an IndexStatus for testing structural fingerprints."""
    file_infos = [
        FileInfo(path=f, size_bytes=100, last_modified=1.0, hash=f"hash_{f}")
        for f in files
    ]
    return IndexStatus(
        repo_path="/test/repo",
        indexed_at=1.0,
        total_files=len(file_infos),
        total_chunks=len(file_infos) * 5,
        languages=languages or {"python": len(file_infos)},
        files=file_infos,
    )


class TestComputeStructuralFingerprint:
    """Tests for compute_structural_fingerprint method."""

    def test_same_files_same_hash(self, tmp_path):
        """Same set of files produces the same fingerprint."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx = _make_index_status(["src/a.py", "src/b.py"])

        fp1 = manager.compute_structural_fingerprint(idx)
        fp2 = manager.compute_structural_fingerprint(idx)

        assert fp1 == fp2
        assert len(fp1) == 16

    def test_file_added_changes_hash(self, tmp_path):
        """Adding a file changes the fingerprint."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx1 = _make_index_status(["src/a.py", "src/b.py"])
        idx2 = _make_index_status(["src/a.py", "src/b.py", "src/c.py"])

        fp1 = manager.compute_structural_fingerprint(idx1)
        fp2 = manager.compute_structural_fingerprint(idx2)

        assert fp1 != fp2

    def test_file_removed_changes_hash(self, tmp_path):
        """Removing a file changes the fingerprint."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx1 = _make_index_status(["src/a.py", "src/b.py"])
        idx2 = _make_index_status(["src/a.py"])

        fp1 = manager.compute_structural_fingerprint(idx1)
        fp2 = manager.compute_structural_fingerprint(idx2)

        assert fp1 != fp2

    def test_content_change_same_hash(self, tmp_path):
        """Changing file content (but not the file list) keeps the same fingerprint."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        files = ["src/a.py", "src/b.py"]

        # Same files, different content hashes — fingerprint only uses paths
        idx1 = _make_index_status(files)
        idx2 = _make_index_status(files)
        # Manually change hashes to simulate content edit
        idx2.files[0] = FileInfo(
            path="src/a.py", size_bytes=200, last_modified=2.0, hash="different_hash"
        )

        fp1 = manager.compute_structural_fingerprint(idx1)
        fp2 = manager.compute_structural_fingerprint(idx2)

        assert fp1 == fp2

    def test_language_change_changes_hash(self, tmp_path):
        """Changing language distribution changes the fingerprint."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx1 = _make_index_status(["src/a.py"], languages={"python": 1})
        idx2 = _make_index_status(["src/a.py"], languages={"python": 1, "go": 1})

        fp1 = manager.compute_structural_fingerprint(idx1)
        fp2 = manager.compute_structural_fingerprint(idx2)

        assert fp1 != fp2

    def test_order_independent(self, tmp_path):
        """File order does not affect the fingerprint (sorted internally)."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx1 = _make_index_status(["src/b.py", "src/a.py"])
        idx2 = _make_index_status(["src/a.py", "src/b.py"])

        fp1 = manager.compute_structural_fingerprint(idx1)
        fp2 = manager.compute_structural_fingerprint(idx2)

        assert fp1 == fp2


class TestNeedsRegenerationStructural:
    """Tests for needs_regeneration_structural method."""

    def test_no_previous_status_returns_true(self, tmp_path):
        """Returns True when there is no previous wiki status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx = _make_index_status(["src/a.py"])

        assert manager.needs_regeneration_structural("index.md", idx) is True

    def test_page_not_in_previous_returns_true(self, tmp_path):
        """Returns True when the page was not previously generated."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=0,
            pages={},
        )
        idx = _make_index_status(["src/a.py"])

        assert manager.needs_regeneration_structural("index.md", idx) is True

    def test_empty_fingerprint_returns_true(self, tmp_path):
        """Returns True when previous fingerprint is empty (pre-migration)."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        page_status = WikiPageStatus(
            path="index.md",
            source_files=["src/a.py"],
            source_hashes={"src/a.py": "h1"},
            structural_fingerprint="",
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"index.md": page_status},
        )
        idx = _make_index_status(["src/a.py"])

        assert manager.needs_regeneration_structural("index.md", idx) is True

    def test_same_structure_returns_false(self, tmp_path):
        """Returns False when the structural fingerprint matches."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx = _make_index_status(["src/a.py", "src/b.py"])
        fp = manager.compute_structural_fingerprint(idx)

        page_status = WikiPageStatus(
            path="index.md",
            source_files=["src/a.py", "src/b.py"],
            source_hashes={"src/a.py": "h1", "src/b.py": "h2"},
            structural_fingerprint=fp,
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"index.md": page_status},
        )

        assert manager.needs_regeneration_structural("index.md", idx) is False

    def test_structure_changed_returns_true(self, tmp_path):
        """Returns True when a file is added (structure changed)."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        idx_old = _make_index_status(["src/a.py"])
        fp_old = manager.compute_structural_fingerprint(idx_old)

        page_status = WikiPageStatus(
            path="index.md",
            source_files=["src/a.py"],
            source_hashes={"src/a.py": "h1"},
            structural_fingerprint=fp_old,
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"index.md": page_status},
        )

        idx_new = _make_index_status(["src/a.py", "src/b.py"])

        assert manager.needs_regeneration_structural("index.md", idx_new) is True

    def test_content_only_change_returns_false(self, tmp_path):
        """Returns False when only file content changed, not structure."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        files = ["src/a.py", "src/b.py"]
        idx = _make_index_status(files)
        fp = manager.compute_structural_fingerprint(idx)

        page_status = WikiPageStatus(
            path="index.md",
            source_files=files,
            source_hashes={"src/a.py": "old_hash", "src/b.py": "old_hash2"},
            structural_fingerprint=fp,
            content_hash="xyz",
            generated_at=1.0,
        )
        manager._previous_status = WikiGenerationStatus(
            repo_path="/test",
            generated_at=1.0,
            total_pages=1,
            pages={"index.md": page_status},
        )

        # Same structure, different content hashes — fingerprint unchanged
        assert manager.needs_regeneration_structural("index.md", idx) is False


class TestRecordSummaryPageStatus:
    """Tests for record_summary_page_status method."""

    def test_stores_fingerprint(self, tmp_path):
        """Stores structural fingerprint in the page status."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "abc"}
        idx = _make_index_status(["src/a.py"])

        page = WikiPage(
            path="index.md",
            title="Overview",
            content="# Docs",
            generated_at=1.0,
        )
        manager.record_summary_page_status(page, ["src/a.py"], idx)

        status = manager.page_statuses["index.md"]
        assert status.structural_fingerprint != ""
        assert status.structural_fingerprint == manager.compute_structural_fingerprint(
            idx
        )

    def test_stores_source_files_and_hashes(self, tmp_path):
        """Still stores source_files and source_hashes for compatibility."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {"src/a.py": "abc", "src/b.py": "def"}
        idx = _make_index_status(["src/a.py", "src/b.py"])

        page = WikiPage(
            path="index.md",
            title="Overview",
            content="# Docs",
            generated_at=1.0,
        )
        manager.record_summary_page_status(page, ["src/a.py", "src/b.py"], idx)

        status = manager.page_statuses["index.md"]
        assert set(status.source_files) == {"src/a.py", "src/b.py"}
        assert status.source_hashes == {"src/a.py": "abc", "src/b.py": "def"}

    def test_stores_content_hash(self, tmp_path):
        """Content hash is computed and stored."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        manager.file_hashes = {}
        idx = _make_index_status([])

        page = WikiPage(
            path="index.md",
            title="Overview",
            content="# Unique Content",
            generated_at=1.0,
        )
        manager.record_summary_page_status(page, [], idx)

        status = manager.page_statuses["index.md"]
        assert len(status.content_hash) == 16


class TestStructuralFingerprintBackwardsCompat:
    """Tests for backwards compatibility with old wiki_status.json."""

    async def test_old_status_without_fingerprint_deserializes(self, tmp_path):
        """Old wiki_status.json without structural_fingerprint loads with empty default."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        status_data = {
            "repo_path": "/test/repo",
            "generated_at": 1.0,
            "total_pages": 1,
            "pages": {
                "index.md": {
                    "path": "index.md",
                    "source_files": ["src/a.py"],
                    "source_hashes": {"src/a.py": "abc"},
                    "content_hash": "xyz",
                    "generated_at": 1.0,
                }
            },
        }
        status_file = tmp_path / "wiki_status.json"
        with open(status_file, "w") as f:
            json.dump(status_data, f)

        result = await manager.load_status()

        assert result is not None
        page_status = result.pages["index.md"]
        assert page_status.structural_fingerprint == ""

    async def test_old_status_triggers_regeneration(self, tmp_path):
        """Pages from old status (empty fingerprint) trigger one-time regeneration."""
        manager = WikiStatusManager(wiki_path=tmp_path)
        status_data = {
            "repo_path": "/test/repo",
            "generated_at": 1.0,
            "total_pages": 1,
            "pages": {
                "index.md": {
                    "path": "index.md",
                    "source_files": ["src/a.py"],
                    "source_hashes": {"src/a.py": "abc"},
                    "content_hash": "xyz",
                    "generated_at": 1.0,
                }
            },
        }
        status_file = tmp_path / "wiki_status.json"
        with open(status_file, "w") as f:
            json.dump(status_data, f)

        await manager.load_status()
        idx = _make_index_status(["src/a.py"])

        assert manager.needs_regeneration_structural("index.md", idx) is True
