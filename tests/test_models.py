"""Tests for data models."""

import json

import pytest

from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    FileInfo,
    IndexStatus,
    Language,
    SearchResult,
    WikiGenerationStatus,
    WikiPage,
    WikiPageStatus,
    WikiStructure,
)


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
                WikiPage(path="index.md", title="Home", content="# Home", generated_at=1.0),
                WikiPage(path="arch.md", title="Architecture", content="# Arch", generated_at=1.0),
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
