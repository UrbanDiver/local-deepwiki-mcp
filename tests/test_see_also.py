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

    def test_preserves_page_without_relationships(self):
        """Test that pages without relationships are preserved unchanged."""
        analyzer = RelationshipAnalyzer()
        # Don't add any chunks, so no relationships exist

        pages = [
            WikiPage(
                path="files/src/isolated.md",
                title="Isolated",
                content="# Isolated\n\nNo imports.",
                generated_at=123,
            ),
        ]

        updated_pages = add_see_also_sections(pages, analyzer)

        # Page should be returned unchanged
        assert len(updated_pages) == 1
        assert updated_pages[0].path == "files/src/isolated.md"
        assert updated_pages[0].content == "# Isolated\n\nNo imports."
        assert "## See Also" not in updated_pages[0].content


class TestImportParsing:
    """Tests for import statement parsing edge cases."""

    def test_import_statement_parsing(self):
        """Test parsing 'import X' style statements (not 'from X import Y')."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/main.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="import local_deepwiki.core.chunker",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="import os",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)

        # Verify import was tracked
        relationships = analyzer.get_relationships("src/local_deepwiki/main.py")
        # Should have tracked the import of local_deepwiki.core.chunker
        assert "src/local_deepwiki/main.py" in analyzer.get_all_known_files()

    def test_import_with_comma_separated_modules(self):
        """Test parsing 'import X, Y' style with comma separation."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/test.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="import os, sys",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)

        # Should handle comma-separated imports (takes first one)
        known = analyzer.get_all_known_files()
        assert "src/test.py" in known

    def test_empty_lines_in_import_chunk(self):
        """Test that empty lines in import content are skipped."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/local_deepwiki/main.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core import chunker\n\n\nfrom local_deepwiki import models",
                start_line=1,
                end_line=4,
            ),
        ]

        analyzer.analyze_chunks(chunks)

        # Should have processed both imports despite empty lines
        known = analyzer.get_all_known_files()
        assert "src/local_deepwiki/main.py" in known

    def test_malformed_import_returns_none(self):
        """Test that malformed import lines return None."""
        analyzer = RelationshipAnalyzer()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/test.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from\nimport\n# comment\nrandom text",
                start_line=1,
                end_line=4,
            ),
        ]

        analyzer.analyze_chunks(chunks)

        # Should not crash, file should still be tracked
        assert "src/test.py" in analyzer.get_all_known_files()


class TestModuleToFilePath:
    """Tests for module to file path resolution."""

    def test_exact_match_in_known_files(self):
        """Test exact match when module path directly matches a known file."""
        analyzer = RelationshipAnalyzer()

        # Add files directly to known files via chunks
        chunks = [
            CodeChunk(
                id="1",
                file_path="local_deepwiki/core/chunker.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.models import CodeChunk",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/local_deepwiki/main.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.IMPORT,
                name="imports",
                content="from local_deepwiki.core.chunker import Chunker",
                start_line=1,
                end_line=1,
            ),
        ]

        analyzer.analyze_chunks(chunks)

        # Now get relationships - this should trigger module resolution
        relationships = analyzer.get_relationships("src/local_deepwiki/main.py")

        # The chunker file should be found as an import
        assert "local_deepwiki/core/chunker.py" in relationships.imports


class TestSharedDependencies:
    """Tests for shared dependencies in See Also generation."""

    def test_shared_dependencies_in_see_also(self):
        """Test that shared dependencies appear in See Also section."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/core/indexer.py",
            imports=set(),
            imported_by=set(),
            shared_deps_with={
                "src/local_deepwiki/core/processor.py": 3,
                "src/local_deepwiki/core/validator.py": 2,
            },
        )
        file_to_wiki = {
            "src/local_deepwiki/core/indexer.py": "files/src/local_deepwiki/core/indexer.md",
            "src/local_deepwiki/core/processor.py": "files/src/local_deepwiki/core/processor.md",
            "src/local_deepwiki/core/validator.py": "files/src/local_deepwiki/core/validator.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/core/indexer.md",
        )

        assert section is not None
        assert "## See Also" in section
        assert "processor" in section
        assert "shares 3 dependencies" in section

    def test_shared_dependencies_skips_already_added(self):
        """Test that shared deps don't duplicate already added pages."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/core/indexer.py",
            imports={"src/local_deepwiki/core/processor.py"},  # Already an import
            imported_by=set(),
            shared_deps_with={
                "src/local_deepwiki/core/processor.py": 3,  # Also has shared deps
            },
        )
        file_to_wiki = {
            "src/local_deepwiki/core/indexer.py": "files/src/local_deepwiki/core/indexer.md",
            "src/local_deepwiki/core/processor.py": "files/src/local_deepwiki/core/processor.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/core/indexer.md",
        )

        assert section is not None
        # processor should appear only once in a bullet point (as dependency, not as shared dep)
        # Count bullet points with "processor"
        bullet_lines = [line for line in section.split("\n") if line.startswith("- [")]
        processor_bullets = [line for line in bullet_lines if "processor" in line]
        assert len(processor_bullets) == 1
        assert "dependency" in section
        assert "shares 3 dependencies" not in section

    def test_shared_dependencies_skips_unmapped_files(self):
        """Test that shared deps without wiki mappings are skipped."""
        relationships = FileRelationships(
            file_path="src/local_deepwiki/core/indexer.py",
            imports=set(),
            imported_by=set(),
            shared_deps_with={
                "src/unmapped/file.py": 5,  # Not in file_to_wiki
            },
        )
        file_to_wiki = {
            "src/local_deepwiki/core/indexer.py": "files/src/local_deepwiki/core/indexer.md",
            # Note: src/unmapped/file.py is NOT mapped
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/local_deepwiki/core/indexer.md",
        )

        # Should return None since the only shared dep has no wiki mapping
        assert section is None


class TestMaxItemsLimit:
    """Tests for max_items limit in See Also generation."""

    def test_max_items_limits_output(self):
        """Test that max_items parameter limits the number of See Also entries."""
        relationships = FileRelationships(
            file_path="src/main.py",
            imports=set(),
            imported_by={
                "src/a.py",
                "src/b.py",
                "src/c.py",
                "src/d.py",
                "src/e.py",
                "src/f.py",
                "src/g.py",
            },
            shared_deps_with={},
        )
        file_to_wiki = {
            "src/main.py": "files/src/main.md",
            "src/a.py": "files/src/a.md",
            "src/b.py": "files/src/b.md",
            "src/c.py": "files/src/c.md",
            "src/d.py": "files/src/d.md",
            "src/e.py": "files/src/e.md",
            "src/f.py": "files/src/f.md",
            "src/g.py": "files/src/g.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/main.md",
            max_items=3,  # Limit to 3 items
        )

        assert section is not None
        # Count the bullet points
        bullet_count = section.count("- [")
        assert bullet_count == 3

    def test_default_max_items_is_five(self):
        """Test that default max_items is 5."""
        relationships = FileRelationships(
            file_path="src/main.py",
            imports=set(),
            imported_by={
                "src/a.py",
                "src/b.py",
                "src/c.py",
                "src/d.py",
                "src/e.py",
                "src/f.py",
                "src/g.py",
                "src/h.py",
            },
            shared_deps_with={},
        )
        file_to_wiki = {
            "src/main.py": "files/src/main.md",
            "src/a.py": "files/src/a.md",
            "src/b.py": "files/src/b.md",
            "src/c.py": "files/src/c.md",
            "src/d.py": "files/src/d.md",
            "src/e.py": "files/src/e.md",
            "src/f.py": "files/src/f.md",
            "src/g.py": "files/src/g.md",
            "src/h.py": "files/src/h.md",
        }

        section = generate_see_also_section(
            relationships,
            file_to_wiki,
            "files/src/main.md",
            # Using default max_items=5
        )

        assert section is not None
        bullet_count = section.count("- [")
        assert bullet_count == 5
