"""Tests for data models."""

import json

import pytest

from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    DeepResearchResult,
    FileInfo,
    IndexStatus,
    Language,
    ResearchStep,
    ResearchStepType,
    SearchResult,
    SourceReference,
    SubQuestion,
    WikiGenerationStatus,
    WikiPage,
    WikiPageStatus,
    WikiStructure,
)


class TestChunkTypeValues:
    """Tests for ChunkType enum values."""

    def test_file_summary_exists(self):
        """FILE_SUMMARY chunk type should exist with correct value."""
        assert ChunkType.FILE_SUMMARY == "file_summary"

    def test_module_summary_exists(self):
        """MODULE_SUMMARY chunk type should exist with correct value."""
        assert ChunkType.MODULE_SUMMARY == "module_summary"

    def test_all_original_values_preserved(self):
        """All 7 original ChunkType values must still exist."""
        expected = {
            "function": ChunkType.FUNCTION,
            "class": ChunkType.CLASS,
            "method": ChunkType.METHOD,
            "module": ChunkType.MODULE,
            "import": ChunkType.IMPORT,
            "comment": ChunkType.COMMENT,
            "other": ChunkType.OTHER,
        }
        for value, member in expected.items():
            assert member.value == value


class TestCodeChunkToVectorRecord:
    """Tests for CodeChunk.to_vector_record method."""

    def test_basic_conversion(self):
        """Test basic chunk to vector record conversion."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="test_func",
            content="def test_func(): pass",
            start_line=1,
            end_line=1,
        )

        record = chunk.to_vector_record()

        assert record["id"] == "test_id"
        assert record["file_path"] == "src/main.py"
        assert record["language"] == "python"
        assert record["chunk_type"] == "function"
        assert record["name"] == "test_func"
        assert record["content"] == "def test_func(): pass"
        assert record["start_line"] == 1
        assert record["end_line"] == 1
        assert record["docstring"] == ""
        assert record["parent_name"] == ""
        assert record["metadata"] == "{}"
        assert "vector" not in record

    def test_with_vector(self):
        """Test conversion with vector embedding."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            content="def test(): pass",
            start_line=1,
            end_line=1,
        )
        vector = [0.1, 0.2, 0.3]

        record = chunk.to_vector_record(vector=vector)

        assert record["vector"] == [0.1, 0.2, 0.3]

    def test_with_optional_fields(self):
        """Test conversion with optional fields populated."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.METHOD,
            name="my_method",
            content="def my_method(self): pass",
            start_line=10,
            end_line=20,
            docstring="This is a docstring",
            parent_name="MyClass",
            metadata={"key": "value", "count": 42},
        )

        record = chunk.to_vector_record()

        assert record["name"] == "my_method"
        assert record["docstring"] == "This is a docstring"
        assert record["parent_name"] == "MyClass"
        # Metadata should be JSON-serialized
        assert json.loads(record["metadata"]) == {"key": "value", "count": 42}

    def test_none_fields_become_empty_strings(self):
        """Test that None fields are converted to empty strings."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.GO,
            chunk_type=ChunkType.FUNCTION,
            name=None,
            content="func test() {}",
            start_line=1,
            end_line=1,
            docstring=None,
            parent_name=None,
        )

        record = chunk.to_vector_record()

        assert record["name"] == ""
        assert record["docstring"] == ""
        assert record["parent_name"] == ""

    def test_all_languages(self):
        """Test conversion works for all supported languages."""
        for lang in Language:
            chunk = CodeChunk(
                id=f"test_{lang.value}",
                file_path=f"test.{lang.value}",
                language=lang,
                chunk_type=ChunkType.FUNCTION,
                content="code",
                start_line=1,
                end_line=1,
            )

            record = chunk.to_vector_record()
            assert record["language"] == lang.value

    def test_all_chunk_types(self):
        """Test conversion works for all chunk types."""
        for chunk_type in ChunkType:
            chunk = CodeChunk(
                id=f"test_{chunk_type.value}",
                file_path="test.py",
                language=Language.PYTHON,
                chunk_type=chunk_type,
                content="code",
                start_line=1,
                end_line=1,
            )

            record = chunk.to_vector_record()
            assert record["chunk_type"] == chunk_type.value


class TestModelRepr:
    """Tests for model __repr__ methods."""

    def test_code_chunk_repr_with_name(self):
        """Test CodeChunk repr with a named chunk."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="my_function",
            content="def my_function(): pass",
            start_line=10,
            end_line=15,
        )
        result = repr(chunk)
        assert "CodeChunk" in result
        assert "function" in result
        assert "my_function" in result
        assert "src/main.py:10-15" in result

    def test_code_chunk_repr_without_name(self):
        """Test CodeChunk repr without a name."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/module.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.MODULE,
            content="# module",
            start_line=1,
            end_line=5,
        )
        result = repr(chunk)
        assert "CodeChunk" in result
        assert "module" in result
        assert "src/module.py:1-5" in result

    def test_file_info_repr(self):
        """Test FileInfo repr."""
        info = FileInfo(
            path="src/utils.py",
            language=Language.PYTHON,
            size_bytes=1024,
            last_modified=1234567890.0,
            hash="abc123",
            chunk_count=5,
        )
        result = repr(info)
        assert "FileInfo" in result
        assert "src/utils.py" in result
        assert "python" in result
        assert "5 chunks" in result

    def test_file_info_repr_no_language(self):
        """Test FileInfo repr with no detected language."""
        info = FileInfo(
            path="README.txt",
            language=None,
            size_bytes=256,
            last_modified=1234567890.0,
            hash="def456",
            chunk_count=0,
        )
        result = repr(info)
        assert "unknown" in result

    def test_index_status_repr(self):
        """Test IndexStatus repr."""
        status = IndexStatus(
            repo_path="/home/user/project",
            indexed_at=1234567890.0,
            total_files=25,
            total_chunks=150,
        )
        result = repr(status)
        assert "IndexStatus" in result
        assert "/home/user/project" in result
        assert "25 files" in result
        assert "150 chunks" in result

    def test_wiki_page_repr(self):
        """Test WikiPage repr."""
        page = WikiPage(
            path="modules/core.md",
            title="Core Module",
            content="# Core Module\n\nContent here.",
            generated_at=1234567890.0,
        )
        result = repr(page)
        assert "WikiPage" in result
        assert "modules/core.md" in result
        assert "Core Module" in result

    def test_wiki_structure_repr(self):
        """Test WikiStructure repr."""
        structure = WikiStructure(
            root="/project/.deepwiki",
            pages=[
                WikiPage(
                    path="index.md", title="Home", content="# Home", generated_at=1.0
                ),
                WikiPage(
                    path="arch.md",
                    title="Architecture",
                    content="# Arch",
                    generated_at=1.0,
                ),
            ],
        )
        result = repr(structure)
        assert "WikiStructure" in result
        assert "/project/.deepwiki" in result
        assert "2 pages" in result

    def test_search_result_repr(self):
        """Test SearchResult repr."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="search_func",
            content="def search_func(): pass",
            start_line=1,
            end_line=1,
        )
        result_obj = SearchResult(chunk=chunk, score=0.95)
        result = repr(result_obj)
        assert "SearchResult" in result
        assert "search_func" in result
        assert "0.95" in result

    def test_search_result_repr_no_name(self):
        """Test SearchResult repr when chunk has no name."""
        chunk = CodeChunk(
            id="test_id",
            file_path="src/main.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.MODULE,
            content="# module",
            start_line=1,
            end_line=1,
        )
        result_obj = SearchResult(chunk=chunk, score=0.75)
        result = repr(result_obj)
        assert "module" in result

    def test_wiki_page_status_repr(self):
        """Test WikiPageStatus repr."""
        status = WikiPageStatus(
            path="files/src/main.md",
            source_files=["src/main.py", "src/utils.py"],
            source_hashes={"src/main.py": "abc", "src/utils.py": "def"},
            content_hash="xyz123",
            generated_at=1234567890.0,
        )
        result = repr(status)
        assert "WikiPageStatus" in result
        assert "files/src/main.md" in result
        assert "2 sources" in result

    def test_wiki_generation_status_repr(self):
        """Test WikiGenerationStatus repr."""
        status = WikiGenerationStatus(
            repo_path="/home/user/project",
            generated_at=1234567890.0,
            total_pages=15,
        )
        result = repr(status)
        assert "WikiGenerationStatus" in result
        assert "/home/user/project" in result
        assert "15 pages" in result

    def test_research_step_repr(self):
        """Test ResearchStep repr."""
        step = ResearchStep(
            step_type=ResearchStepType.RETRIEVAL,
            description="Retrieved code chunks",
            duration_ms=150,
        )
        result = repr(step)
        assert "ResearchStep" in result
        assert "retrieval" in result
        assert "150ms" in result

    def test_sub_question_repr(self):
        """Test SubQuestion repr."""
        sq = SubQuestion(
            question="How does the authentication flow work in this codebase?",
            category="flow",
        )
        result = repr(sq)
        assert "SubQuestion" in result
        assert "flow" in result
        assert "How does the authentication" in result

    def test_source_reference_repr_with_name(self):
        """Test SourceReference repr with a name."""
        ref = SourceReference(
            file_path="src/auth.py",
            start_line=10,
            end_line=25,
            chunk_type="function",
            name="authenticate_user",
            relevance_score=0.92,
        )
        result = repr(ref)
        assert "Source" in result
        assert "src/auth.py:10-25" in result
        assert "authenticate_user" in result

    def test_source_reference_repr_without_name(self):
        """Test SourceReference repr without a name (uses chunk_type)."""
        ref = SourceReference(
            file_path="src/module.py",
            start_line=1,
            end_line=50,
            chunk_type="module",
            name=None,
            relevance_score=0.75,
        )
        result = repr(ref)
        assert "Source" in result
        assert "src/module.py:1-50" in result
        assert "module" in result

    def test_deep_research_result_repr(self):
        """Test DeepResearchResult repr."""
        result_obj = DeepResearchResult(
            question="How does caching work?",
            answer="The caching system uses Redis...",
            sub_questions=[
                SubQuestion(question="What is cached?", category="structure"),
                SubQuestion(question="When is cache invalidated?", category="flow"),
            ],
            sources=[
                SourceReference(
                    file_path="src/cache.py",
                    start_line=1,
                    end_line=100,
                    chunk_type="module",
                    relevance_score=0.95,
                ),
            ],
            total_chunks_analyzed=25,
            total_llm_calls=5,
        )
        result = repr(result_obj)
        assert "DeepResearchResult" in result
        assert "2 sub-questions" in result
        assert "1 sources" in result
        assert "5 LLM calls" in result


class TestWikiStructureToToc:
    """Tests for WikiStructure.to_toc method."""

    def test_empty_structure(self):
        """Test to_toc with no pages."""
        structure = WikiStructure(root="/project/.deepwiki", pages=[])
        toc = structure.to_toc()
        assert toc == {"sections": []}

    def test_flat_pages(self):
        """Test to_toc with pages in root directory."""
        structure = WikiStructure(
            root="/project/.deepwiki",
            pages=[
                WikiPage(
                    path="index.md", title="Home", content="# Home", generated_at=1.0
                ),
                WikiPage(
                    path="overview.md",
                    title="Overview",
                    content="# Overview",
                    generated_at=1.0,
                ),
            ],
        )
        toc = structure.to_toc()
        assert "sections" in toc
        assert "pages" in toc
        assert len(toc["pages"]) == 2
        # Pages should be sorted by path
        assert toc["pages"][0]["path"] == "index.md"
        assert toc["pages"][0]["title"] == "Home"
        assert toc["pages"][1]["path"] == "overview.md"
        assert toc["pages"][1]["title"] == "Overview"

    def test_nested_structure(self):
        """Test to_toc with nested directory structure."""
        structure = WikiStructure(
            root="/project/.deepwiki",
            pages=[
                WikiPage(
                    path="index.md", title="Home", content="# Home", generated_at=1.0
                ),
                WikiPage(
                    path="files/main.md",
                    title="Main",
                    content="# Main",
                    generated_at=1.0,
                ),
                WikiPage(
                    path="files/src/utils.md",
                    title="Utils",
                    content="# Utils",
                    generated_at=1.0,
                ),
            ],
        )
        toc = structure.to_toc()

        # Root level should have sections and pages
        assert "sections" in toc
        assert "pages" in toc

        # Find the 'files' section
        files_section = next((s for s in toc["sections"] if s["name"] == "files"), None)
        assert files_section is not None
        assert "sections" in files_section
        assert "pages" in files_section

        # files/main.md should be in files section pages
        assert any(p["path"] == "files/main.md" for p in files_section["pages"])

        # Find the 'src' section inside 'files'
        src_section = next(
            (s for s in files_section["sections"] if s["name"] == "src"), None
        )
        assert src_section is not None
        assert any(p["path"] == "files/src/utils.md" for p in src_section["pages"])

    def test_deeply_nested_structure(self):
        """Test to_toc with deeply nested paths."""
        structure = WikiStructure(
            root="/project/.deepwiki",
            pages=[
                WikiPage(
                    path="a/b/c/d/file.md",
                    title="Deep File",
                    content="# Deep",
                    generated_at=1.0,
                ),
            ],
        )
        toc = structure.to_toc()

        # Navigate down the nested sections
        current = toc
        for level in ["a", "b", "c", "d"]:
            section = next(
                (s for s in current.get("sections", []) if s["name"] == level), None
            )
            assert section is not None, f"Section '{level}' not found"
            current = section

        # The final section should have the page
        assert any(p["path"] == "a/b/c/d/file.md" for p in current.get("pages", []))

    def test_multiple_pages_same_directory(self):
        """Test to_toc with multiple pages in the same directory."""
        structure = WikiStructure(
            root="/project/.deepwiki",
            pages=[
                WikiPage(
                    path="files/alpha.md",
                    title="Alpha",
                    content="# Alpha",
                    generated_at=1.0,
                ),
                WikiPage(
                    path="files/beta.md",
                    title="Beta",
                    content="# Beta",
                    generated_at=1.0,
                ),
                WikiPage(
                    path="files/gamma.md",
                    title="Gamma",
                    content="# Gamma",
                    generated_at=1.0,
                ),
            ],
        )
        toc = structure.to_toc()

        files_section = next((s for s in toc["sections"] if s["name"] == "files"), None)
        assert files_section is not None
        assert len(files_section["pages"]) == 3
        # Should be sorted alphabetically by path
        paths = [p["path"] for p in files_section["pages"]]
        assert paths == ["files/alpha.md", "files/beta.md", "files/gamma.md"]
