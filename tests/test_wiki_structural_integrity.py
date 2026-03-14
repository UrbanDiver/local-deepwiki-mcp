"""Wiki structural integrity tests.

Validates the structural correctness of generated wiki output: internal
links, cross-references, required pages, and JSON data files.

Run selectively with: pytest -m wiki_output
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wiki_output_helpers import extract_markdown_links, find_broken_links


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def wiki_path() -> Path:
    """Path to the project's generated wiki."""
    path = Path(__file__).parent.parent / ".deepwiki"
    if not path.exists():
        pytest.skip("No .deepwiki directory found — run 'deepwiki update' first")
    return path


@pytest.fixture(scope="session")
def toc_data(wiki_path: Path) -> dict:
    """Parsed toc.json content."""
    toc_file = wiki_path / "toc.json"
    if not toc_file.exists():
        pytest.skip("toc.json not found")
    return json.loads(toc_file.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def search_data(wiki_path: Path) -> dict:
    """Parsed search.json content."""
    search_file = wiki_path / "search.json"
    if not search_file.exists():
        pytest.skip("search.json not found")
    return json.loads(search_file.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def all_md_files(wiki_path: Path) -> list[Path]:
    """All markdown files in the wiki."""
    return sorted(wiki_path.rglob("*.md"))


# ---------------------------------------------------------------------------
# Link integrity
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestLinkIntegrity:
    """Tests for internal link validity."""

    def test_no_broken_internal_links(self, wiki_path: Path) -> None:
        """All internal markdown links should resolve to existing files."""
        broken = find_broken_links(wiki_path)
        assert not broken, (
            f"Found {len(broken)} broken internal links:\n"
            + "\n".join(
                f"  - {src} -> [{text}]({target})" for src, text, target in broken[:20]
            )
            + (f"\n  ... and {len(broken) - 20} more" if len(broken) > 20 else "")
        )

    def test_no_self_links(self, all_md_files: list[Path], wiki_path: Path) -> None:
        """No page should contain a link to itself."""
        self_links: list[tuple[str, str]] = []

        for md_file in all_md_files:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            page_rel = str(md_file.relative_to(wiki_path))
            page_dir = md_file.parent

            for link_text, link_target in extract_markdown_links(content):
                # Skip external links and anchors
                if link_target.startswith(("http://", "https://", "#", "mailto:")):
                    continue

                target_path = link_target.split("#")[0]
                if not target_path:
                    continue

                # Resolve relative to page directory
                resolved = (page_dir / target_path).resolve()
                if resolved == md_file.resolve():
                    self_links.append((page_rel, link_target))

        assert not self_links, f"Found {len(self_links)} self-links:\n" + "\n".join(
            f"  - {page}: [{target}]" for page, target in self_links[:20]
        )


# ---------------------------------------------------------------------------
# Required pages
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestRequiredPages:
    """Tests for the existence of required wiki pages."""

    REQUIRED_PAGES = [
        "index.md",
        "architecture.md",
        "glossary.md",
        "inheritance.md",
        "coverage.md",
        "modules/index.md",
        "files/index.md",
    ]

    @pytest.mark.parametrize("page_path", REQUIRED_PAGES)
    def test_required_page_exists(self, wiki_path: Path, page_path: str) -> None:
        """Each required wiki page must exist."""
        full_path = wiki_path / page_path
        assert full_path.exists(), f"Required page missing: {page_path}"


# ---------------------------------------------------------------------------
# JSON data files
# ---------------------------------------------------------------------------


@pytest.mark.wiki_output
class TestJsonDataFiles:
    """Tests for JSON data file validity."""

    def test_toc_json_valid(self, toc_data: dict) -> None:
        """toc.json must be valid JSON with entries that have paths."""
        assert "entries" in toc_data, "toc.json should have an 'entries' key"
        entries = toc_data["entries"]
        assert isinstance(entries, list), "toc.json 'entries' should be a list"
        assert len(entries) > 0, "toc.json should have at least one entry"

        # Each top-level entry should have path and title
        for entry in entries:
            assert "title" in entry, f"TOC entry missing 'title': {entry}"
            assert "path" in entry, f"TOC entry missing 'path': {entry}"

    def test_toc_entries_point_to_existing_files(
        self, wiki_path: Path, toc_data: dict
    ) -> None:
        """Every path in toc.json must point to an existing file on disk."""

        def _collect_paths(entries: list[dict]) -> list[str]:
            """Recursively collect all non-empty paths from TOC entries."""
            paths: list[str] = []
            for entry in entries:
                path = entry.get("path", "")
                if path:
                    paths.append(path)
                children = entry.get("children", [])
                if children:
                    paths.extend(_collect_paths(children))
            return paths

        all_paths = _collect_paths(toc_data.get("entries", []))
        missing = [p for p in all_paths if not (wiki_path / p).exists()]

        assert not missing, (
            f"TOC references {len(missing)} non-existent files:\n"
            + "\n".join(f"  - {p}" for p in missing[:20])
        )

    def test_search_json_valid(self, search_data: dict) -> None:
        """search.json must be valid JSON with expected structure."""
        assert isinstance(search_data, dict), "search.json should be a dict"
        # Should have at least a 'pages' key
        assert "pages" in search_data, "search.json should have a 'pages' key"
        pages = search_data["pages"]
        assert isinstance(pages, list), "search.json 'pages' should be a list"
        assert len(pages) > 0, "search.json should have at least one page entry"

    def test_search_json_no_test_files(self, search_data: dict) -> None:
        """search.json page entries should not reference test file paths.

        The search index should cover wiki pages, not test files directly.
        """
        pages = search_data.get("pages", [])
        test_pages = [
            p.get("path", "")
            for p in pages
            if "test_" in p.get("path", "") or "/tests/" in p.get("path", "")
        ]
        # Note: entity entries may reference test files (that's a separate concern).
        # This test only checks the top-level 'pages' list.
        # TODO: Fix search index to exclude test file wiki pages
        assert not test_pages, (
            f"search.json 'pages' contains {len(test_pages)} test-related entries. "
            f"First 5: {test_pages[:5]}"
        )
