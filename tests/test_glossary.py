"""Tests for glossary generation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.glossary import (
    EntityEntry,
    _format_signature,
    _get_brief_description,
    _get_wiki_link,
    collect_all_entities,
    generate_glossary_page,
    group_entities_by_letter,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


class TestEntityEntry:
    """Tests for EntityEntry dataclass."""

    def test_creates_function_entry(self):
        """Test creating a function entry."""
        entry = EntityEntry(
            name="my_function",
            entity_type="function",
            file_path="src/module.py",
        )
        assert entry.name == "my_function"
        assert entry.entity_type == "function"
        assert entry.parent_name is None

    def test_creates_method_entry_with_parent(self):
        """Test creating a method entry with parent class."""
        entry = EntityEntry(
            name="my_method",
            entity_type="method",
            file_path="src/module.py",
            parent_name="MyClass",
            docstring="A method docstring.",
        )
        assert entry.parent_name == "MyClass"
        assert entry.docstring == "A method docstring."


class TestGroupEntitiesByLetter:
    """Tests for group_entities_by_letter function."""

    def test_groups_alphabetically(self):
        """Test that entities are grouped by first letter."""
        entities = [
            EntityEntry("apple", "function", "a.py"),
            EntityEntry("apricot", "function", "a.py"),
            EntityEntry("banana", "class", "b.py"),
        ]
        grouped = group_entities_by_letter(entities)
        assert "A" in grouped
        assert "B" in grouped
        assert len(grouped["A"]) == 2
        assert len(grouped["B"]) == 1

    def test_case_insensitive_grouping(self):
        """Test that grouping is case-insensitive."""
        entities = [
            EntityEntry("Apple", "function", "a.py"),
            EntityEntry("apple", "function", "a.py"),
        ]
        grouped = group_entities_by_letter(entities)
        assert "A" in grouped
        assert len(grouped["A"]) == 2

    def test_non_alpha_grouped_under_hash(self):
        """Test that non-alphabetic names are grouped under #."""
        entities = [
            EntityEntry("_private", "function", "a.py"),
            EntityEntry("123func", "function", "a.py"),
            EntityEntry("__init__", "method", "a.py"),
        ]
        grouped = group_entities_by_letter(entities)
        assert "#" in grouped
        assert len(grouped["#"]) == 3

    def test_empty_list(self):
        """Test with empty entity list."""
        grouped = group_entities_by_letter([])
        assert grouped == {}


class TestGetWikiLink:
    """Tests for _get_wiki_link function."""

    def test_simple_path(self):
        """Test simple file path conversion."""
        result = _get_wiki_link("src/module.py")
        assert result == "files/src/module.md"

    def test_nested_path(self):
        """Test nested file path conversion."""
        result = _get_wiki_link("src/package/subpackage/module.py")
        assert result == "files/src/package/subpackage/module.md"


class TestGetBriefDescription:
    """Tests for _get_brief_description function."""

    def test_returns_empty_for_none(self):
        """Test returns empty string for None docstring."""
        assert _get_brief_description(None) == ""

    def test_returns_first_line(self):
        """Test returns first line of docstring."""
        docstring = "This is the first line.\n\nMore details here."
        result = _get_brief_description(docstring)
        assert result == "This is the first line."

    def test_truncates_long_description(self):
        """Test truncates descriptions longer than max_length."""
        docstring = "This is a very long description that should be truncated for display."
        result = _get_brief_description(docstring, max_length=30)
        assert len(result) == 30
        assert result.endswith("...")

    def test_filters_out_args_section(self):
        """Test filters out docstrings starting with Args:."""
        docstring = "Args: param1, param2"
        result = _get_brief_description(docstring)
        assert result == ""

    def test_filters_out_returns_section(self):
        """Test filters out docstrings starting with Returns:."""
        docstring = "Returns: Some value"
        result = _get_brief_description(docstring)
        assert result == ""

    def test_filters_out_raises_section(self):
        """Test filters out docstrings starting with Raises:."""
        docstring = "Raises: ValueError"
        result = _get_brief_description(docstring)
        assert result == ""

    def test_filters_out_example_section(self):
        """Test filters out docstrings starting with Example:."""
        docstring = "Example: some_function()"
        result = _get_brief_description(docstring)
        assert result == ""

    def test_filters_out_note_section(self):
        """Test filters out docstrings starting with Note:."""
        docstring = "Note: Important information"
        result = _get_brief_description(docstring)
        assert result == ""

    def test_empty_docstring(self):
        """Test returns empty string for empty docstring."""
        assert _get_brief_description("") == ""

    def test_strips_whitespace(self):
        """Test strips whitespace from first line."""
        docstring = "   Spaced description.   \n\nMore content."
        result = _get_brief_description(docstring)
        assert result == "Spaced description."


class TestFormatSignature:
    """Tests for _format_signature function."""

    def test_returns_empty_for_class(self):
        """Test returns empty string for class entities."""
        entry = EntityEntry(
            name="MyClass",
            entity_type="class",
            file_path="src/module.py",
        )
        result = _format_signature(entry)
        assert result == ""

    def test_function_with_no_types(self):
        """Test function with no type information."""
        entry = EntityEntry(
            name="my_func",
            entity_type="function",
            file_path="src/module.py",
        )
        result = _format_signature(entry)
        assert result == "(...)"

    def test_function_with_parameter_types(self):
        """Test function with parameter types."""
        entry = EntityEntry(
            name="my_func",
            entity_type="function",
            file_path="src/module.py",
            parameter_types={"x": "int", "y": "str"},
        )
        result = _format_signature(entry)
        assert "x: int" in result
        assert "y: str" in result

    def test_function_with_return_type(self):
        """Test function with return type."""
        entry = EntityEntry(
            name="my_func",
            entity_type="function",
            file_path="src/module.py",
            return_type="bool",
        )
        result = _format_signature(entry)
        assert "→ bool" in result

    def test_function_with_full_signature(self):
        """Test function with both parameters and return type."""
        entry = EntityEntry(
            name="my_func",
            entity_type="function",
            file_path="src/module.py",
            parameter_types={"x": "int"},
            return_type="str",
        )
        result = _format_signature(entry)
        assert "(x: int)" in result
        assert "→ str" in result

    def test_truncates_many_parameters(self):
        """Test that many parameters are truncated."""
        entry = EntityEntry(
            name="my_func",
            entity_type="function",
            file_path="src/module.py",
            parameter_types={"a": "int", "b": "str", "c": "bool", "d": "float", "e": "list"},
        )
        result = _format_signature(entry, max_params=3)
        assert "...+2" in result

    def test_parameter_without_type_hint(self):
        """Test parameter without type hint."""
        entry = EntityEntry(
            name="my_func",
            entity_type="function",
            file_path="src/module.py",
            parameter_types={"x": "", "y": "int"},
        )
        result = _format_signature(entry)
        # x should appear without type, y with type
        assert "x," in result or "x)" in result
        assert "y: int" in result

    def test_method_signature(self):
        """Test method signature formatting."""
        entry = EntityEntry(
            name="my_method",
            entity_type="method",
            file_path="src/module.py",
            parent_name="MyClass",
            parameter_types={"self": "", "value": "int"},
            return_type="None",
        )
        result = _format_signature(entry)
        assert "→ None" in result


class TestCollectAllEntities:
    """Tests for collect_all_entities function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_index_status(self):
        """Create a sample index status."""
        return IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/module.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/utils.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

    async def test_collects_classes(self, mock_vector_store, sample_index_status):
        """Test collecting class entities."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="MyClass",
                    docstring="A sample class.",
                )
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        assert len(entities) >= 1
        class_entity = next((e for e in entities if e.name == "MyClass"), None)
        assert class_entity is not None
        assert class_entity.entity_type == "class"
        assert class_entity.docstring == "A sample class."

    async def test_collects_functions(self, mock_vector_store, sample_index_status):
        """Test collecting function entities."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="my_func",
                    metadata={
                        "parameter_types": {"x": "int"},
                        "return_type": "str",
                        "is_async": True,
                        "raises": ["ValueError"],
                    },
                )
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        func_entity = next((e for e in entities if e.name == "my_func"), None)
        assert func_entity is not None
        assert func_entity.entity_type == "function"
        assert func_entity.parameter_types == {"x": "int"}
        assert func_entity.return_type == "str"
        assert func_entity.is_async is True
        assert func_entity.raises == ["ValueError"]

    async def test_collects_methods(self, mock_vector_store, sample_index_status):
        """Test collecting method entities."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_method(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="my_method",
                    parent_name="MyClass",
                )
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        method_entity = next((e for e in entities if e.name == "my_method"), None)
        assert method_entity is not None
        assert method_entity.entity_type == "method"
        assert method_entity.parent_name == "MyClass"

    async def test_sorts_alphabetically(self, mock_vector_store, sample_index_status):
        """Test that entities are sorted alphabetically."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def zebra(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="zebra",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def apple(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=2,
                    end_line=2,
                    name="apple",
                ),
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        names = [e.name for e in entities]
        # Should appear multiple times due to multiple files, but apple should come before zebra
        apple_idx = next(i for i, n in enumerate(names) if n == "apple")
        zebra_idx = next(i for i, n in enumerate(names) if n == "zebra")
        assert apple_idx < zebra_idx

    async def test_handles_chunk_without_name(self, mock_vector_store, sample_index_status):
        """Test handling chunks without a name."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name=None,
                )
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        # Should use "Unknown" as name
        unknown_entity = next((e for e in entities if e.name == "Unknown"), None)
        assert unknown_entity is not None

    async def test_handles_chunk_without_metadata(self, mock_vector_store, sample_index_status):
        """Test handling chunks without metadata (empty dict)."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="func",
                    # metadata defaults to empty dict, no type info present
                )
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        func_entity = next((e for e in entities if e.name == "func"), None)
        assert func_entity is not None
        assert func_entity.parameter_types is None
        assert func_entity.return_type is None
        assert func_entity.is_async is False

    async def test_skips_non_entity_chunks(self, mock_vector_store, sample_index_status):
        """Test that non-entity chunk types are skipped."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="import os",
                    chunk_type=ChunkType.IMPORT,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="os",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=2,
                    end_line=2,
                    name="func",
                ),
            ]
        )

        entities = await collect_all_entities(sample_index_status, mock_vector_store)

        # Should only have the function, not the import
        names = [e.name for e in entities]
        assert "func" in names or any("func" in n for n in names)
        assert "os" not in names


class TestGenerateGlossaryPage:
    """Tests for generate_glossary_page function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_chunks_by_file = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def sample_index_status(self):
        """Create a sample index status."""
        return IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            files=[
                FileInfo(
                    path="src/module.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
            ],
        )

    async def test_returns_none_for_no_entities(self, mock_vector_store, sample_index_status):
        """Test returns None when no entities are found."""
        result = await generate_glossary_page(sample_index_status, mock_vector_store)
        assert result is None

    async def test_generates_page_with_entities(self, mock_vector_store, sample_index_status):
        """Test generates a valid markdown page."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="MyClass",
                    docstring="A sample class for testing.",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def my_function(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=5,
                    end_line=5,
                    name="my_function",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert result is not None
        assert "# Glossary" in result
        assert "MyClass" in result
        assert "my_function" in result

    async def test_includes_navigation(self, mock_vector_store, sample_index_status):
        """Test includes letter navigation."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def apple(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="apple",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def banana(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=2,
                    end_line=2,
                    name="banana",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "Quick Navigation:" in result
        assert "[A](#a)" in result
        assert "[B](#b)" in result

    async def test_includes_summary_stats(self, mock_vector_store, sample_index_status):
        """Test includes summary statistics."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="MyClass",
                ),
                CodeChunk(
                    id="chunk2",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=2,
                    end_line=2,
                    name="func",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "Total:" in result
        assert "2 entities" in result
        assert "1 classes" in result
        assert "1 functions" in result

    async def test_includes_legend(self, mock_vector_store, sample_index_status):
        """Test includes legend at the end."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="func",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "Legend:" in result
        assert "🔷 Class" in result
        assert "🔹 Function" in result

    async def test_formats_method_with_parent(self, mock_vector_store, sample_index_status):
        """Test methods display with parent class name."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def my_method(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="my_method",
                    parent_name="MyClass",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "MyClass.my_method" in result

    async def test_shows_async_marker(self, mock_vector_store, sample_index_status):
        """Test async functions show async marker."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="async def async_func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="async_func",
                    metadata={"is_async": True},
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "⚡" in result

    async def test_shows_raises_indicator(self, mock_vector_store, sample_index_status):
        """Test functions that raise exceptions show indicator."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def risky_func(): raise ValueError",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="risky_func",
                    metadata={"raises": ["ValueError", "TypeError"]},
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "⚠️" in result
        assert "ValueError" in result

    async def test_truncates_many_raises(self, mock_vector_store, sample_index_status):
        """Test truncates when many exceptions are raised."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def risky(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="risky",
                    metadata={
                        "raises": ["ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError"]
                    },
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "+2" in result  # 5 exceptions, shows 3 + "+2"

    async def test_includes_type_signature(self, mock_vector_store, sample_index_status):
        """Test includes type signature for functions."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def typed_func(x: int) -> str: pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="typed_func",
                    metadata={
                        "parameter_types": {"x": "int"},
                        "return_type": "str",
                    },
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "x: int" in result
        assert "→ str" in result

    async def test_includes_brief_description(self, mock_vector_store, sample_index_status):
        """Test includes brief description from docstring."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def documented(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="documented",
                    docstring="This function does something useful.",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "This function does something useful." in result

    async def test_groups_non_alpha_under_hash(self, mock_vector_store, sample_index_status):
        """Test non-alphabetic names grouped under #."""
        mock_vector_store.get_chunks_by_file = AsyncMock(
            return_value=[
                CodeChunk(
                    id="chunk1",
                    content="def __init__(self): pass",
                    chunk_type=ChunkType.METHOD,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=1,
                    name="__init__",
                    parent_name="MyClass",
                ),
            ]
        )

        result = await generate_glossary_page(sample_index_status, mock_vector_store)

        assert "## #" in result
