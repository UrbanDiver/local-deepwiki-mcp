"""Tests for the context builder module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.context_builder import (
    FileContext,
    build_file_context,
    extract_imports_from_chunks,
    format_context_for_llm,
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
