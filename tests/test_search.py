"""Tests for search index generation."""

import json
import tempfile
from pathlib import Path

import pytest

from local_deepwiki.generators.search import (
    _build_keywords,
    extract_code_terms,
    extract_headings,
    extract_snippet,
    generate_entity_entries,
    generate_full_search_index,
    generate_search_entry,
    generate_search_index,
    write_full_search_index,
    write_search_index,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language, WikiPage


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
            search_data = [
                {"path": "index.md", "title": "Home", "headings": [], "terms": [], "snippet": ""}
            ]
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


class TestBuildKeywords:
    """Tests for _build_keywords function."""

    def test_extracts_name_keywords(self):
        """Test that name parts are extracted as keywords."""
        keywords = _build_keywords("get_user_data", {}, None, [])
        assert "get" in keywords
        assert "user" in keywords
        assert "data" in keywords
        assert "get_user_data" in keywords

    def test_extracts_camelcase_parts(self):
        """Test that camelCase parts are extracted."""
        keywords = _build_keywords("getUserData", {}, None, [])
        assert "get" in keywords
        assert "user" in keywords
        assert "data" in keywords

    def test_extracts_type_keywords(self):
        """Test that parameter types are included."""
        keywords = _build_keywords("foo", {"x": "list[str]", "y": "int"}, None, [])
        assert "list" in keywords
        assert "int" in keywords

    def test_extracts_return_type(self):
        """Test that return type is included."""
        keywords = _build_keywords("foo", {}, "dict[str, int]", [])
        assert "dict" in keywords

    def test_extracts_exception_keywords(self):
        """Test that raised exceptions are included."""
        keywords = _build_keywords("foo", {}, None, ["ValueError", "TypeError"])
        assert "valueerror" in keywords
        assert "typeerror" in keywords
        assert "value" in keywords  # Without "Error" suffix
        assert "type" in keywords

    def test_handles_none_name(self):
        """Test that None name is handled gracefully."""
        keywords = _build_keywords(None, {}, None, [])
        assert keywords == []


class TestGenerateEntityEntries:
    """Tests for generate_entity_entries function."""

    @pytest.fixture
    def mock_index_status(self):
        """Create a mock index status."""
        return IndexStatus(
            repo_path="/test/repo",
            files=[
                FileInfo(
                    path="src/module.py",
                    hash="abc123",
                    size_bytes=100,
                    last_modified=0,
                )
            ],
            total_files=1,
            total_chunks=5,
            indexed_at=0,
        )

    @pytest.fixture
    def mock_vector_store(self, mock_index_status):
        """Create a mock vector store with chunks."""
        from unittest.mock import AsyncMock, MagicMock

        mock_store = MagicMock()

        # Create mock chunks
        chunks = [
            CodeChunk(
                id="1",
                content="def foo(): pass",
                file_path="src/module.py",
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
                chunk_type=ChunkType.FUNCTION,
                name="foo",
                docstring="A function that does foo.",
                metadata={
                    "parameter_types": {"x": "int"},
                    "return_type": "str",
                    "is_async": False,
                    "raises": ["ValueError"],
                },
            ),
            CodeChunk(
                id="2",
                content="class Bar: pass",
                file_path="src/module.py",
                language=Language.PYTHON,
                start_line=3,
                end_line=3,
                chunk_type=ChunkType.CLASS,
                name="Bar",
                docstring="A class called Bar.",
            ),
            CodeChunk(
                id="3",
                content="async def baz(): pass",
                file_path="src/module.py",
                language=Language.PYTHON,
                start_line=5,
                end_line=5,
                chunk_type=ChunkType.FUNCTION,
                name="baz",
                docstring="An async function.",
                metadata={"is_async": True},
            ),
            CodeChunk(
                id="4",
                content="def method(): pass",
                file_path="src/module.py",
                language=Language.PYTHON,
                start_line=7,
                end_line=7,
                chunk_type=ChunkType.METHOD,
                name="method",
                parent_name="Bar",
                docstring="A method in Bar.",
            ),
            CodeChunk(
                id="5",
                content="# Module content",
                file_path="src/module.py",
                language=Language.PYTHON,
                start_line=0,
                end_line=10,
                chunk_type=ChunkType.MODULE,
                name="module",
            ),
        ]

        mock_store.get_chunks_by_file = AsyncMock(return_value=chunks)
        return mock_store

    async def test_generates_entity_entries(self, mock_index_status, mock_vector_store):
        """Test that entity entries are generated for functions, classes, methods."""
        entries = await generate_entity_entries(mock_index_status, mock_vector_store)

        # Should have 4 entries (foo, Bar, baz, method) - not MODULE
        assert len(entries) == 4

        # Check function entry
        foo_entry = next(e for e in entries if e["name"] == "foo")
        assert foo_entry["type"] == "entity"
        assert foo_entry["entity_type"] == "function"
        assert foo_entry["signature"] == "(x) → str"
        assert foo_entry["is_async"] is False
        assert foo_entry["raises"] == ["ValueError"]
        assert "foo" in foo_entry["keywords"]

    async def test_generates_class_entry(self, mock_index_status, mock_vector_store):
        """Test that class entries have no signature."""
        entries = await generate_entity_entries(mock_index_status, mock_vector_store)

        bar_entry = next(e for e in entries if e["name"] == "Bar")
        assert bar_entry["entity_type"] == "class"
        assert bar_entry["signature"] == ""

    async def test_generates_async_entry(self, mock_index_status, mock_vector_store):
        """Test that async functions are marked."""
        entries = await generate_entity_entries(mock_index_status, mock_vector_store)

        baz_entry = next(e for e in entries if e["name"] == "baz")
        assert baz_entry["is_async"] is True

    async def test_generates_method_display_name(self, mock_index_status, mock_vector_store):
        """Test that method display name includes parent class."""
        entries = await generate_entity_entries(mock_index_status, mock_vector_store)

        method_entry = next(e for e in entries if e["name"] == "method")
        assert method_entry["display_name"] == "Bar.method"

    async def test_entries_sorted_by_name(self, mock_index_status, mock_vector_store):
        """Test that entries are sorted alphabetically."""
        entries = await generate_entity_entries(mock_index_status, mock_vector_store)

        names = [e["display_name"].lower() for e in entries]
        assert names == sorted(names)


class TestGenerateFullSearchIndex:
    """Tests for generate_full_search_index function."""

    async def test_combines_pages_and_entities(self):
        """Test that full search index combines pages and entities."""
        pages = [
            WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=0,
            ),
        ]

        # Without index_status/vector_store, should only have pages
        index = await generate_full_search_index(pages)

        assert "pages" in index
        assert "entities" in index
        assert "meta" in index
        assert len(index["pages"]) == 1
        assert len(index["entities"]) == 0
        assert index["meta"]["total_pages"] == 1
        assert index["meta"]["total_entities"] == 0


class TestWriteFullSearchIndex:
    """Tests for write_full_search_index function."""

    async def test_writes_full_index(self):
        """Test that full search index is written to disk."""
        from unittest.mock import AsyncMock, MagicMock

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

            index_status = IndexStatus(
                repo_path="/test/repo",
                files=[
                    FileInfo(
                        path="src/test.py",
                        hash="abc",
                        size_bytes=100,
                        last_modified=0,
                    )
                ],
                total_files=1,
                total_chunks=0,
                indexed_at=0,
            )

            mock_vector_store = MagicMock()
            mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

            result_path = await write_full_search_index(
                wiki_path, pages, index_status, mock_vector_store
            )

            assert result_path.exists()
            assert result_path.name == "search.json"

            data = json.loads(result_path.read_text())
            assert "pages" in data
            assert "entities" in data
            assert "meta" in data
            assert len(data["pages"]) == 1
            assert data["pages"][0]["title"] == "Test"
