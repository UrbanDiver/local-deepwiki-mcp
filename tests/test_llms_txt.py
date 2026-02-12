"""Tests for llms.txt generation (Phase 4)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from local_deepwiki.generators.llms_txt import (
    _page_summary,
    _sort_key,
    generate_llms_txt,
)
from local_deepwiki.models import IndexStatus, WikiPage


def _make_page(path: str, title: str, content: str = "") -> WikiPage:
    """Helper to create a WikiPage."""
    return WikiPage(
        path=path,
        title=title,
        content=content or f"# {title}\nSome content here.",
        generated_at=time.time(),
    )


def _make_index_status(repo_path: str = "/tmp/repo", **kwargs) -> IndexStatus:
    """Helper to create an IndexStatus."""
    defaults = {
        "repo_path": repo_path,
        "indexed_at": time.time(),
        "total_files": 10,
        "total_chunks": 50,
        "languages": {"python": 8, "javascript": 2},
        "files": [],
    }
    defaults.update(kwargs)
    return IndexStatus(**defaults)


class TestGenerateLlmsTxt:
    """Tests for generate_llms_txt."""

    def test_basic_output(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        pages = [
            _make_page("index.md", "My Project"),
            _make_page("modules/core.md", "Core Module"),
        ]
        index_status = _make_index_status()

        result = generate_llms_txt(pages, index_status, wiki_path)

        assert result == wiki_path / "llms.txt"
        assert result.exists()

        content = result.read_text()
        assert content.startswith("# ")
        assert "## Documentation Pages" in content
        assert "## Code Statistics" in content
        assert "Files indexed: 10" in content
        assert "Wiki pages: 2" in content

    def test_with_manifest(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        pages = [_make_page("index.md", "Index")]
        index_status = _make_index_status()
        manifest = {"name": "awesome-project", "description": "An awesome project"}

        result = generate_llms_txt(pages, index_status, wiki_path, manifest=manifest)
        content = result.read_text()

        assert "# awesome-project" in content
        assert "> An awesome project" in content

    def test_without_manifest_fallback(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        pages = [_make_page("index.md", "Index")]
        index_status = _make_index_status(repo_path="/home/user/my-repo")

        result = generate_llms_txt(pages, index_status, wiki_path)
        content = result.read_text()

        # Should fall back to repo directory name
        assert "my-repo" in content

    def test_empty_pages(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        index_status = _make_index_status()
        result = generate_llms_txt([], index_status, wiki_path)
        content = result.read_text()

        # Should still have stats section
        assert "## Code Statistics" in content
        assert "Wiki pages: 0" in content

    def test_languages_listed(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        index_status = _make_index_status(languages={"python": 5, "go": 3, "rust": 2})
        result = generate_llms_txt([], index_status, wiki_path)
        content = result.read_text()

        assert "Languages: go, python, rust" in content

    def test_page_ordering(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / ".deepwiki"
        wiki_path.mkdir()

        pages = [
            _make_page("files/main.md", "Main"),
            _make_page("modules/core.md", "Core Module"),
            _make_page("architecture.md", "Architecture"),
            _make_page("index.md", "Index"),
            _make_page("misc.md", "Misc"),
        ]
        index_status = _make_index_status()

        result = generate_llms_txt(pages, index_status, wiki_path)
        content = result.read_text()

        lines = content.split("\n")
        page_lines = [l for l in lines if l.startswith("- [")]

        # index.md should be first, architecture second
        assert "index.md" in page_lines[0]
        assert "architecture.md" in page_lines[1]
        assert "modules/" in page_lines[2]
        assert "files/" in page_lines[3]


class TestSortKey:
    """Tests for page sort ordering."""

    def test_index_first(self) -> None:
        page = _make_page("index.md", "Index")
        assert _sort_key(page) == (0, "index.md")

    def test_architecture_second(self) -> None:
        page = _make_page("architecture.md", "Arch")
        assert _sort_key(page) == (1, "architecture.md")

    def test_modules_third(self) -> None:
        page = _make_page("modules/core.md", "Core")
        assert _sort_key(page)[0] == 2

    def test_files_fourth(self) -> None:
        page = _make_page("files/main.md", "Main")
        assert _sort_key(page)[0] == 3

    def test_other_last(self) -> None:
        page = _make_page("random.md", "Random")
        assert _sort_key(page)[0] == 4


class TestPageSummary:
    """Tests for _page_summary helper."""

    def test_extracts_first_content_line(self) -> None:
        page = _make_page(
            "test.md", "Test", "# Title\n\nThis is the summary line.\nMore content."
        )
        assert _page_summary(page) == "This is the summary line."

    def test_skips_headings(self) -> None:
        page = _make_page("test.md", "Test", "# Title\n## Subtitle\nContent here.")
        assert _page_summary(page) == "Content here."

    def test_truncates_long_summary(self) -> None:
        long_line = "x" * 200
        page = _make_page("test.md", "Test", f"# Title\n{long_line}")
        summary = _page_summary(page)
        assert len(summary) <= 120
        assert summary.endswith("...")

    def test_fallback_to_title(self) -> None:
        page = _make_page("test.md", "Test", "# Only Heading")
        summary = _page_summary(page)
        assert summary == "Test"
