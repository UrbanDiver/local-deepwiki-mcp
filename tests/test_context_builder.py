"""Tests for the context builder module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.context_builder import (
    FileContext,
    _parse_import_module,
    build_file_context,
    extract_imports_from_chunks,
    find_related_files,
    format_context_for_llm,
    get_callers_from_other_files,
    get_type_definitions_used,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language


def make_chunk(
    chunk_type: ChunkType = ChunkType.FUNCTION,
    name: str = "test_func",
    content: str = "def test_func(): pass",
    file_path: str = "src/test.py",
) -> CodeChunk:
    """Create a test code chunk."""
    import uuid
    return CodeChunk(
        id=str(uuid.uuid4()),
        content=content,
        chunk_type=chunk_type,
        file_path=file_path,
        start_line=1,
        end_line=1,
        language=Language.PYTHON,
        name=name,
    )


class TestExtractImportsFromChunks:
    """Tests for extract_imports_from_chunks function."""

    def test_extracts_from_import_statement(self) -> None:
        """Test extracting from 'from X import Y' statement."""
        chunk = make_chunk(
            chunk_type=ChunkType.IMPORT,
            content="from pathlib import Path\nfrom typing import List",
        )

        imports, modules = extract_imports_from_chunks([chunk])

        assert len(imports) == 2
        assert "from pathlib import Path" in imports
        assert "from typing import List" in imports
        assert "pathlib" in modules
        assert "typing" in modules

    def test_extracts_import_statement(self) -> None:
        """Test extracting from 'import X' statement."""
        chunk = make_chunk(
            chunk_type=ChunkType.IMPORT,
            content="import os\nimport sys",
        )

        imports, modules = extract_imports_from_chunks([chunk])

        assert len(imports) == 2
        assert "import os" in imports
        assert "os" in modules
        assert "sys" in modules

    def test_skips_non_import_chunks(self) -> None:
        """Test that non-import chunks are ignored."""
        chunks = [
            make_chunk(chunk_type=ChunkType.FUNCTION, content="def foo(): pass"),
            make_chunk(chunk_type=ChunkType.IMPORT, content="import os"),
        ]

        imports, modules = extract_imports_from_chunks(chunks)

        assert len(imports) == 1
        assert "import os" in imports

    def test_skips_comments(self) -> None:
        """Test that comments in import blocks are skipped."""
        chunk = make_chunk(
            chunk_type=ChunkType.IMPORT,
            content="# This is a comment\nimport os",
        )

        imports, _ = extract_imports_from_chunks([chunk])

        assert len(imports) == 1
        assert "import os" in imports

    def test_handles_empty_chunks(self) -> None:
        """Test handling empty chunk list."""
        imports, modules = extract_imports_from_chunks([])

        assert imports == []
        assert modules == []


class TestFormatContextForLlm:
    """Tests for format_context_for_llm function."""

    def test_formats_imports_section(self) -> None:
        """Test formatting imports section."""
        context = FileContext(
            file_path="src/test.py",
            imports=["from pathlib import Path", "import os"],
            imported_modules=["pathlib", "os"],
        )

        result = format_context_for_llm(context)

        assert "Dependencies" in result
        assert "from pathlib import Path" in result
        assert "import os" in result

    def test_formats_callers_section(self) -> None:
        """Test formatting callers section."""
        context = FileContext(
            file_path="src/test.py",
            callers={
                "my_function": ["src/caller1.py", "src/caller2.py"],
            },
        )

        result = format_context_for_llm(context)

        assert "External Usage" in result
        assert "my_function" in result
        assert "caller1" in result

    def test_formats_related_files_section(self) -> None:
        """Test formatting related files section."""
        context = FileContext(
            file_path="src/test.py",
            related_files=["src/utils.py", "src/models.py"],
        )

        result = format_context_for_llm(context)

        assert "Related Files" in result
        assert "src/utils.py" in result

    def test_formats_type_definitions_section(self) -> None:
        """Test formatting type definitions section."""
        context = FileContext(
            file_path="src/test.py",
            type_definitions=["Config: class Config(BaseModel):"],
        )

        result = format_context_for_llm(context)

        assert "Type Definitions" in result
        assert "Config" in result

    def test_returns_empty_for_empty_context(self) -> None:
        """Test returns empty string for empty context."""
        context = FileContext(file_path="src/test.py")

        result = format_context_for_llm(context)

        assert result == ""

    def test_limits_imports(self) -> None:
        """Test that imports are limited to max_imports."""
        context = FileContext(
            file_path="src/test.py",
            imports=[f"import mod{i}" for i in range(20)],
            imported_modules=[f"mod{i}" for i in range(20)],
        )

        result = format_context_for_llm(context, max_imports=5)

        assert "mod0" in result
        assert "mod4" in result
        # mod5 should not be shown directly (it's in the "and X more")
        assert "15 more" in result


class TestBuildFileContext:
    """Tests for build_file_context function."""

    async def test_builds_context_with_imports(self, tmp_path: Path) -> None:
        """Test building context extracts imports."""
        chunks = [
            make_chunk(
                chunk_type=ChunkType.IMPORT,
                content="from pathlib import Path",
                file_path="src/test.py",
            ),
            make_chunk(
                chunk_type=ChunkType.FUNCTION,
                name="my_func",
                content="def my_func(): pass",
                file_path="src/test.py",
            ),
        ]

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await build_file_context(
            file_path="src/test.py",
            chunks=chunks,
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert result.file_path == "src/test.py"
        assert "from pathlib import Path" in result.imports
        assert "pathlib" in result.imported_modules

    async def test_builds_context_with_empty_chunks(self, tmp_path: Path) -> None:
        """Test building context with no chunks."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await build_file_context(
            file_path="src/test.py",
            chunks=[],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert result.file_path == "src/test.py"
        assert result.imports == []
        assert result.callers == {}


class TestFileContextDataclass:
    """Tests for the FileContext dataclass."""

    def test_default_values(self) -> None:
        """Test that FileContext has correct defaults."""
        context = FileContext(file_path="test.py")

        assert context.file_path == "test.py"
        assert context.imports == []
        assert context.imported_modules == []
        assert context.callers == {}
        assert context.related_files == []
        assert context.type_definitions == []

    def test_with_values(self) -> None:
        """Test creating FileContext with values."""
        context = FileContext(
            file_path="test.py",
            imports=["import os"],
            callers={"func": ["other.py"]},
        )

        assert context.imports == ["import os"]
        assert context.callers == {"func": ["other.py"]}


class TestParseImportModule:
    """Tests for _parse_import_module function."""

    def test_parses_from_import(self) -> None:
        """Test parsing 'from X import Y' statement."""
        result = _parse_import_module("from pathlib import Path")
        assert result == "pathlib"

    def test_parses_from_import_nested(self) -> None:
        """Test parsing nested 'from X.Y import Z' statement."""
        result = _parse_import_module("from local_deepwiki.models import CodeChunk")
        assert result == "local_deepwiki"

    def test_parses_simple_import(self) -> None:
        """Test parsing 'import X' statement."""
        result = _parse_import_module("import os")
        assert result == "os"

    def test_parses_simple_import_nested(self) -> None:
        """Test parsing 'import X.Y' statement."""
        result = _parse_import_module("import os.path")
        assert result == "os"

    def test_returns_none_for_invalid(self) -> None:
        """Test returns None for invalid import line."""
        result = _parse_import_module("not an import statement")
        assert result is None

    def test_returns_none_for_empty(self) -> None:
        """Test returns None for empty string."""
        result = _parse_import_module("")
        assert result is None

    def test_returns_none_for_comment(self) -> None:
        """Test returns None for comment line."""
        result = _parse_import_module("# import os")
        assert result is None


class TestGetCallersFromOtherFiles:
    """Tests for get_callers_from_other_files function."""

    async def test_skips_short_entity_names(self, tmp_path: Path) -> None:
        """Test that short entity names (< 4 chars) are skipped."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["fn", "abc"],  # Both < 4 chars
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert result == {}
        # Search should not be called for short names
        mock_vector_store.search.assert_not_called()

    async def test_skips_same_file(self, tmp_path: Path) -> None:
        """Test that results from the same file are skipped."""
        mock_chunk = make_chunk(
            file_path="src/test.py",  # Same as the file we're analyzing
            content="my_function()",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert result == {}

    async def test_skips_if_entity_not_in_content(self, tmp_path: Path) -> None:
        """Test that results without the entity name in content are skipped."""
        mock_chunk = make_chunk(
            file_path="src/other.py",
            content="some_other_function()",  # Entity name not in content
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert result == {}

    async def test_finds_callers(self, tmp_path: Path) -> None:
        """Test finding callers from other files."""
        mock_chunk = make_chunk(
            file_path="src/caller.py",
            content="result = my_function(arg)",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert "my_function" in result
        assert "src/caller.py" in result["my_function"]

    async def test_limits_max_files(self, tmp_path: Path) -> None:
        """Test that max_files limit is respected."""
        # Create multiple caller results
        mock_results = []
        for i in range(15):
            mock_chunk = make_chunk(
                file_path=f"src/caller{i}.py",
                content="my_function()",
            )
            mock_result = MagicMock()
            mock_result.chunk = mock_chunk
            mock_results.append(mock_result)

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=mock_results)

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
            max_files=5,
        )

        assert "my_function" in result
        assert len(result["my_function"]) == 5

    async def test_handles_search_exception(self, tmp_path: Path) -> None:
        """Test that search exceptions are handled gracefully."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("Search failed"))

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        # Should return empty dict, not raise
        assert result == {}


class TestFindRelatedFiles:
    """Tests for find_related_files function."""

    async def test_finds_related_files_for_function(self) -> None:
        """Test finding related files for function module."""
        mock_chunk = make_chunk(
            file_path="src/utils.py",
            content="def helper_func(): pass",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper_func"],
            vector_store=mock_vector_store,
        )

        assert "src/utils.py" in result

    async def test_finds_related_files_for_class(self) -> None:
        """Test finding related files for class module."""
        mock_chunk = make_chunk(
            file_path="src/models.py",
            content="class MyClass: pass",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["MyClass"],  # Starts with uppercase
            vector_store=mock_vector_store,
        )

        assert "src/models.py" in result

    async def test_excludes_same_file(self) -> None:
        """Test that the same file is excluded from related files."""
        mock_chunk = make_chunk(
            file_path="src/test.py",  # Same file
            content="def helper(): pass",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper"],
            vector_store=mock_vector_store,
        )

        assert result == []

    async def test_limits_max_files(self) -> None:
        """Test that max_files limit is respected."""
        # Create multiple results
        mock_results = []
        for i in range(10):
            mock_chunk = make_chunk(
                file_path=f"src/file{i}.py",
                content="def helper(): pass",
            )
            mock_result = MagicMock()
            mock_result.chunk = mock_chunk
            mock_results.append(mock_result)

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=mock_results)

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper"],
            vector_store=mock_vector_store,
            max_files=3,
        )

        assert len(result) == 3

    async def test_handles_search_exception(self) -> None:
        """Test that search exceptions are handled gracefully."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("Search failed"))

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper"],
            vector_store=mock_vector_store,
        )

        # Should return empty list, not raise
        assert result == []


class TestGetTypeDefinitionsUsed:
    """Tests for get_type_definitions_used function."""

    async def test_extracts_type_annotations(self) -> None:
        """Test extracting type annotations from chunks."""
        chunk = make_chunk(
            content="def process(config: Config, data: DataModel) -> Result: pass",
        )

        mock_class_chunk = make_chunk(
            chunk_type=ChunkType.CLASS,
            content="class Config(BaseModel):",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_class_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await get_type_definitions_used([chunk], mock_vector_store)

        assert len(result) >= 1
        assert any("Config" in td for td in result)

    async def test_extracts_return_type_annotations(self) -> None:
        """Test extracting return type annotations."""
        chunk = make_chunk(
            content="def get_value() -> ResponseData: return data",
        )

        mock_class_chunk = make_chunk(
            chunk_type=ChunkType.CLASS,
            content="class ResponseData:",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_class_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await get_type_definitions_used([chunk], mock_vector_store)

        assert len(result) >= 1
        assert any("ResponseData" in td for td in result)

    async def test_skips_short_type_names(self) -> None:
        """Test that short type names (3 chars or less) are skipped."""
        chunk = make_chunk(
            content="def process(x: Int) -> Str: pass",  # Int, Str are <= 3 chars
        )

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await get_type_definitions_used([chunk], mock_vector_store)

        assert result == []
        # Search should not be called for short type names
        mock_vector_store.search.assert_not_called()

    async def test_handles_search_exception(self) -> None:
        """Test that search exceptions are handled gracefully."""
        chunk = make_chunk(
            content="def process(data: LongTypeName) -> None: pass",
        )

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("Search failed"))

        result = await get_type_definitions_used([chunk], mock_vector_store)

        # Should return empty list, not raise
        assert result == []

    async def test_limits_max_types(self) -> None:
        """Test that max_types limit is respected."""
        # Create content with many type annotations
        type_names = [f"TypeName{i}" for i in range(20)]
        content = "def process(" + ", ".join(f"arg{i}: {t}" for i, t in enumerate(type_names)) + "): pass"
        chunk = make_chunk(content=content)

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])

        result = await get_type_definitions_used([chunk], mock_vector_store, max_types=5)

        # Search should be called at most 5 times
        assert mock_vector_store.search.call_count <= 5

    async def test_skips_non_class_results(self) -> None:
        """Test that non-class results are skipped."""
        chunk = make_chunk(
            content="def process(data: ConfigType) -> None: pass",
        )

        # Return a function instead of a class
        mock_func_chunk = make_chunk(
            chunk_type=ChunkType.FUNCTION,
            content="def ConfigType(): pass",
        )
        mock_result = MagicMock()
        mock_result.chunk = mock_func_chunk

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        result = await get_type_definitions_used([chunk], mock_vector_store)

        # Should not include the function
        assert result == []


class TestFormatContextForLlmAdvanced:
    """Additional tests for format_context_for_llm edge cases."""

    def test_formats_callers_with_more_than_3_files(self) -> None:
        """Test formatting callers with more than 3 caller files."""
        context = FileContext(
            file_path="src/test.py",
            callers={
                "my_function": [
                    "src/caller1.py",
                    "src/caller2.py",
                    "src/caller3.py",
                    "src/caller4.py",
                    "src/caller5.py",
                ],
            },
        )

        result = format_context_for_llm(context)

        assert "External Usage" in result
        assert "my_function" in result
        assert "+2 more" in result  # 5 files - 3 shown = 2 more

    def test_limits_callers_to_10_entities(self) -> None:
        """Test that callers section limits to 10 entities."""
        callers = {f"func{i}": ["caller.py"] for i in range(15)}
        context = FileContext(
            file_path="src/test.py",
            callers=callers,
        )

        result = format_context_for_llm(context)

        # Should show at most 10 entities
        func_count = result.count("func")
        assert func_count <= 10

    def test_limits_related_files_to_5(self) -> None:
        """Test that related files section limits to 5 files."""
        context = FileContext(
            file_path="src/test.py",
            related_files=[f"src/file{i}.py" for i in range(10)],
        )

        result = format_context_for_llm(context)

        # Count file mentions (excluding the header line)
        file_mentions = sum(1 for i in range(10) if f"file{i}.py" in result)
        assert file_mentions == 5

    def test_limits_type_definitions_to_8(self) -> None:
        """Test that type definitions section limits to 8 types."""
        context = FileContext(
            file_path="src/test.py",
            type_definitions=[f"Type{i}: class Type{i}:" for i in range(15)],
        )

        result = format_context_for_llm(context)

        # Count type mentions
        type_mentions = sum(1 for i in range(15) if f"Type{i}" in result)
        assert type_mentions == 8
