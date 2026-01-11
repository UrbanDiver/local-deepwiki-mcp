"""Tests for search index generation."""

import json
import tempfile
from pathlib import Path

import pytest

from local_deepwiki.generators.search import (
    extract_code_terms,
    extract_headings,
    extract_snippet,
    generate_search_entry,
    generate_search_index,
    write_search_index,
)
from local_deepwiki.models import WikiPage


class TestExtractHeadings:
    """Tests for extract_headings function."""

    def test_extracts_h1_headings(self):
        """Test extraction of h1 headings."""
        content = "# Main Title\n\nSome content"
        headings = extract_headings(content)
        assert "Main Title" in headings

    def test_extracts_multiple_heading_levels(self):
        """Test extraction of h1, h2, h3 headings."""
        content = """# Title
## Section One
### Subsection
## Section Two
"""
        headings = extract_headings(content)
        assert len(headings) == 4
        assert "Title" in headings
        assert "Section One" in headings
        assert "Subsection" in headings
        assert "Section Two" in headings

    def test_removes_markdown_formatting(self):
        """Test that markdown formatting is stripped from headings."""
        content = "# **Bold Title**\n## `Code Title`"
        headings = extract_headings(content)
        assert "Bold Title" in headings
        assert "Code Title" in headings

    def test_empty_content(self):
        """Test with empty content."""
        assert extract_headings("") == []
        assert extract_headings("No headings here") == []


class TestExtractCodeTerms:
    """Tests for extract_code_terms function."""

    def test_extracts_simple_terms(self):
        """Test extraction of simple backticked terms."""
        content = "Use `VectorStore` and `WikiGenerator` for docs."
        terms = extract_code_terms(content)
        assert "VectorStore" in terms
        assert "WikiGenerator" in terms

    def test_extracts_qualified_names(self):
        """Test extraction of qualified names."""
        content = "Import `local_deepwiki.core.VectorStore` from module."
        terms = extract_code_terms(content)
        # Should include both full qualified name and last part
        assert "VectorStore" in terms
        assert "local_deepwiki.core.VectorStore" in terms

    def test_skips_long_code_blocks(self):
        """Test that long inline code is skipped."""
        content = "Example: `def foo(): return bar + baz + qux + more`"
        terms = extract_code_terms(content)
        # Should not include very long code snippets
        assert not any(len(t) > 50 for t in terms)

    def test_empty_content(self):
        """Test with empty content."""
        assert extract_code_terms("") == []


class TestExtractSnippet:
    """Tests for extract_snippet function."""

    def test_extracts_plain_text(self):
        """Test basic snippet extraction."""
        content = "This is a simple paragraph of text."
        snippet = extract_snippet(content)
        assert "simple paragraph" in snippet

    def test_removes_code_blocks(self):
        """Test that code blocks are removed."""
        content = """Some text.
```python
def foo():
    pass
```
More text."""
        snippet = extract_snippet(content)
        assert "def foo" not in snippet
        assert "Some text" in snippet

    def test_removes_headings(self):
        """Test that headings are removed."""
        content = "# Title\n\nActual content here."
        snippet = extract_snippet(content)
        assert "Title" not in snippet
        assert "content" in snippet

    def test_removes_links_keeps_text(self):
        """Test that link syntax is removed but text is kept."""
        content = "See [VectorStore](path.md) for details."
        snippet = extract_snippet(content)
        assert "VectorStore" in snippet
        assert "path.md" not in snippet

    def test_truncates_long_content(self):
        """Test that long content is truncated."""
        content = "Word " * 100
        snippet = extract_snippet(content, max_length=50)
        assert len(snippet) <= 53  # 50 + "..."
        assert snippet.endswith("...")

    def test_empty_content(self):
        """Test with empty content."""
        assert extract_snippet("") == ""


class TestGenerateSearchEntry:
    """Tests for generate_search_entry function."""

    def test_generates_complete_entry(self):
        """Test that all fields are populated."""
        page = WikiPage(
            path="files/wiki.md",
            title="Wiki Generator",
            content="# Wiki Generator\n\nUse `WikiGenerator` class.",
            generated_at=0,
        )
        entry = generate_search_entry(page)

        assert entry["path"] == "files/wiki.md"
        assert entry["title"] == "Wiki Generator"
        assert "Wiki Generator" in entry["headings"]
        assert "WikiGenerator" in entry["terms"]
        assert len(entry["snippet"]) > 0


class TestGenerateSearchIndex:
    """Tests for generate_search_index function."""

    def test_generates_index_for_multiple_pages(self):
        """Test index generation with multiple pages."""
        pages = [
            WikiPage(
                path="index.md",
                title="Overview",
                content="# Project Overview",
                generated_at=0,
            ),
            WikiPage(
                path="architecture.md",
                title="Architecture",
                content="# System Architecture",
                generated_at=0,
            ),
        ]
        index = generate_search_index(pages)

        assert len(index) == 2
        assert index[0]["path"] == "index.md"
        assert index[1]["path"] == "architecture.md"


class TestWriteSearchIndex:
    """Tests for write_search_index function."""

    def test_writes_json_file(self):
        """Test that search index is written to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            pages = [
                WikiPage(
                    path="index.md",
                    title="Test",
                    content="# Test\n\n`TestClass` content.",
                    generated_at=0,
                ),
            ]

            result_path = write_search_index(wiki_path, pages)

            assert result_path.exists()
            assert result_path.name == "search.json"

            data = json.loads(result_path.read_text())
            assert len(data) == 1
            assert data[0]["title"] == "Test"


class TestSearchJsonEndpoint:
    """Tests for the Flask /search.json endpoint."""

    def test_returns_search_index(self):
        """Test that /search.json returns the index."""
        from local_deepwiki.web.app import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            # Create a minimal wiki
            (wiki_path / "index.md").write_text("# Home\n")
            # Create search index
            search_data = [{"path": "index.md", "title": "Home", "headings": [], "terms": [], "snippet": ""}]
            (wiki_path / "search.json").write_text(json.dumps(search_data))

            app = create_app(wiki_path)
            client = app.test_client()

            response = client.get("/search.json")
            assert response.status_code == 200
            data = response.get_json()
            assert len(data) == 1
            assert data[0]["title"] == "Home"

    def test_returns_empty_when_no_index(self):
        """Test that missing search.json returns empty array."""
        from local_deepwiki.web.app import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = Path(tmpdir)
            (wiki_path / "index.md").write_text("# Home\n")

            app = create_app(wiki_path)
            client = app.test_client()

            response = client.get("/search.json")
            assert response.status_code == 200
            assert response.get_json() == []
