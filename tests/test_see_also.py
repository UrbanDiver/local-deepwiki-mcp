"""Tests for See Also section generation."""

import pytest

from local_deepwiki.generators.see_also import (
    FileRelationships,
    RelationshipAnalyzer,
    _relative_path,
    add_see_also_sections,
    build_file_to_wiki_map,
    generate_see_also_section,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language, WikiPage


class TestRelationshipAnalyzer:
    """Tests for RelationshipAnalyzer class."""

    def test_analyze_python_imports(self):
        """Test analyzing Python import statements."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/indexer.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core.chunker import CodeChunker\nfrom local_deepwiki.models import CodeChunk",
                start_line=1,
                end_line=2,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)

        # Check that files are tracked
        known_files = analyzer.get_all_known_files()
        assert "src/local_deepwiki/core/indexer.py" in known_files
        assert "src/local_deepwiki/core/chunker.py" in known_files

    def test_get_relationships_imports(self):
        """Test getting import relationships for a file."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/indexer.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core.chunker import CodeChunker",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)
        relationships = analyzer.get_relationships("src/local_deepwiki/core/indexer.py")

        assert isinstance(relationships, FileRelationships)
        assert relationships.file_path == "src/local_deepwiki/core/indexer.py"

    def test_get_relationships_imported_by(self):
        """Test finding files that import a given file."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/indexer.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core.chunker import CodeChunker",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/generators/wiki.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core.chunker import CodeChunker",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="3",
                file_path="src/local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)
        relationships = analyzer.get_relationships("src/local_deepwiki/core/chunker.py")

        # Both indexer.py and wiki.py import chunker.py
        assert "src/local_deepwiki/core/indexer.py" in relationships.imported_by
        assert "src/local_deepwiki/generators/wiki.py" in relationships.imported_by

    def test_ignores_non_import_chunks(self):
        """Test that non-import chunks are ignored."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/indexer.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="Indexer",
                content="class Indexer: pass",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)
        assert len(analyzer.get_all_known_files()) == 0

    def test_shared_dependencies(self):
        """Test finding files with shared dependencies."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/indexer.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk\nfrom local_deepwiki.config import Config",
                start_line=1,
                end_line=2,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk\nfrom local_deepwiki.config import Config",
                start_line=1,
                end_line=2,
            ),
        ]

        analyzer.analyze_chunks(chunks)
        relationships = analyzer.get_relationships("src/local_deepwiki/core/indexer.py")

        # Both files share 2 dependencies (models and config)
        assert "src/local_deepwiki/core/chunker.py" in relationships.shared_deps_with
        assert relationships.shared_deps_with["src/local_deepwiki/core/chunker.py"] >= 2


class TestBuildFileToWikiMap:
    """Tests for build_file_to_wiki_map function."""

    def test_builds_correct_mapping(self):
        """Test that file paths are correctly mapped to wiki paths."""
        pages = [
            WikiPage(
                path="files/src/local_deepwiki/core/chunker.md",
                title="Chunker",
                content="# Chunker",
                generated_at=0,
            ),
            WikiPage(
                path="files/src/local_deepwiki/models.md",
                title="Models",
                content="# Models",
                generated_at=0,
            ),
            WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=0,
            ),
        ]

        mapping = build_file_to_wiki_map(pages)

        assert (
            mapping["src/local_deepwiki/core/chunker.py"]
            == "files/src/local_deepwiki/core/chunker.md"
        )
        assert mapping["src/local_deepwiki/models.py"] == "files/src/local_deepwiki/models.md"
        # index.md shouldn't be mapped (not a file doc)
        assert "index.py" not in mapping


class TestGenerateSeeAlsoSection:
    """Tests for generate_see_also_section function."""

    def test_generates_section_with_importers(self):
        """Test generating See Also with files that import this file."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/core/chunker.py",
            imported_by={"src/local_deepwiki/core/indexer.py"},
        )
        file_to_wiki = {
            "src/local_deepwiki/core/chunker.py": "files/src/local_deepwiki/core/chunker.md",
            "src/local_deepwiki/core/indexer.py": "files/src/local_deepwiki/core/indexer.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/core/chunker.md",
        )

        assert section is not None
        assert "## See Also" in section
        assert "indexer" in section
        assert "uses this" in section

    def test_generates_section_with_dependencies(self):
        """Test generating See Also with dependency files."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/core/indexer.py",
            imports={"src/local_deepwiki/core/chunker.py"},
        )
        file_to_wiki = {
            "src/local_deepwiki/core/indexer.py": "files/src/local_deepwiki/core/indexer.md",
            "src/local_deepwiki/core/chunker.py": "files/src/local_deepwiki/core/chunker.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/core/indexer.md",
        )

        assert section is not None
        assert "## See Also" in section
        assert "chunker" in section
        assert "dependency" in section

    def test_returns_none_for_no_relationships(self):
        """Test that None is returned when no related pages exist."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/isolated.py",
        )
        file_to_wiki = {
            "src/local_deepwiki/isolated.py": "files/src/local_deepwiki/isolated.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/isolated.md",
        )

        assert section is None

    def test_avoids_self_reference(self):
        """Test that See Also doesn't include the current page."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/core/chunker.py",
            imports={
                "src/local_deepwiki/core/chunker.py"
            },  # Self-import (shouldn't happen but test)
        )
        file_to_wiki = {
            "src/local_deepwiki/core/chunker.py": "files/src/local_deepwiki/core/chunker.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/core/chunker.md",
        )

        assert section is None  # No valid relationships


class TestRelativePath:
    """Tests for _relative_path function."""

    def test_same_directory(self):
        """Test relative path in same directory."""
        result = _relative_path(
            "files/src/core/chunker.md",
            "files/src/core/indexer.md",
        )
        assert result == "indexer.md"

    def test_parent_directory(self):
        """Test relative path to parent directory."""
        result = _relative_path(
            "files/src/core/chunker.md",
            "files/src/models.md",
        )
        assert result == "../models.md"

    def test_sibling_directory(self):
        """Test relative path to sibling directory."""
        result = _relative_path(
            "files/src/core/chunker.md",
            "files/src/generators/wiki.md",
        )
        assert result == "../generators/wiki.md"


class TestAddSeeAlsoSections:
    """Tests for add_see_also_sections function."""

    def test_adds_sections_to_file_pages(self):
        """Test that See Also sections are added to file documentation pages."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/core/indexer.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core.chunker import CodeChunker",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk",
                start_line=1,
                end_line=1,
            ),
        ]
        analyzer.analyze_chunks(chunks)

        pages = [
            WikiPage(
                path="files/src/local_deepwiki/core/indexer.md",
                title="Indexer",
                content="# Indexer\n\nIndexer documentation.",
                generated_at=0,
            ),
            WikiPage(
                path="files/src/local_deepwiki/core/chunker.md",
                title="Chunker",
                content="# Chunker\n\nChunker documentation.",
                generated_at=0,
            ),
            WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=0,
            ),
        ]

        updated_pages = add_see_also_sections(pages, analyzer)

        # Find the chunker page
        chunker_page = next(p for p in updated_pages if "chunker" in p.path)
        assert "## See Also" in chunker_page.content
        assert "indexer" in chunker_page.content

    def test_skips_non_file_pages(self):
        """Test that non-file pages are not modified."""
        analyzer = RelationshipAnalyzer()

        pages = [
            WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=0,
            ),
            WikiPage(
                path="architecture.md",
                title="Architecture",
                content="# Architecture",
                generated_at=0,
            ),
        ]

        updated_pages = add_see_also_sections(pages, analyzer)

        for page in updated_pages:
            assert "## See Also" not in page.content

    def test_skips_files_index(self):
        """Test that files/index.md is not modified."""
        analyzer = RelationshipAnalyzer()

        pages = [
            WikiPage(
                path="files/index.md",
                title="Source Files",
                content="# Source Files",
                generated_at=0,
            ),
        ]

        updated_pages = add_see_also_sections(pages, analyzer)

        assert "## See Also" not in updated_pages[0].content
