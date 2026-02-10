"""Tests for partial failure warning propagation in context_builder."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.context_builder import (
    FileContext,
    build_file_context,
    find_related_files,
    format_context_for_llm,
    get_callers_from_other_files,
    get_type_definitions_used,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language


def _make_chunk(
    chunk_type: ChunkType = ChunkType.FUNCTION,
    name: str = "test_func",
    content: str = "def test_func(): pass",
    file_path: str = "src/test.py",
) -> CodeChunk:
    """Create a test code chunk."""
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


class TestGetCallersFromOtherFilesWarnings:
    """Tests that get_callers_from_other_files propagates warnings."""

    async def test_appends_warning_on_search_failure(self, tmp_path: Path) -> None:
        """Search failure appends a warning when warnings list is provided."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("connection lost")
        )
        warnings: list[str] = []

        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
            warnings=warnings,
        )

        assert result == {}
        assert len(warnings) == 1
        assert "my_function" in warnings[0]
        assert "connection lost" in warnings[0]

    async def test_no_warning_without_list(self, tmp_path: Path) -> None:
        """When warnings parameter is omitted, no error is raised."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("connection lost")
        )

        # Should not raise - backward compatible
        result = await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        assert result == {}

    async def test_multiple_failures_accumulate_warnings(self, tmp_path: Path) -> None:
        """Multiple entity failures accumulate separate warnings."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("timeout"))
        warnings: list[str] = []

        await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["func_one", "func_two"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
            warnings=warnings,
        )

        assert len(warnings) == 2
        assert "func_one" in warnings[0]
        assert "func_two" in warnings[1]

    async def test_no_warning_on_success(self, tmp_path: Path) -> None:
        """Successful search does not append any warnings."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])
        warnings: list[str] = []

        await get_callers_from_other_files(
            file_path="src/test.py",
            entity_names=["my_function"],
            repo_path=tmp_path,
            vector_store=mock_vector_store,
            warnings=warnings,
        )

        assert warnings == []


class TestFindRelatedFilesWarnings:
    """Tests that find_related_files propagates warnings."""

    async def test_appends_warning_on_search_failure(self) -> None:
        """Search failure appends a warning when warnings list is provided."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("index corrupted")
        )
        warnings: list[str] = []

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper"],
            vector_store=mock_vector_store,
            warnings=warnings,
        )

        assert result == []
        assert len(warnings) == 1
        assert "helper" in warnings[0]
        assert "index corrupted" in warnings[0]

    async def test_no_warning_without_list(self) -> None:
        """When warnings parameter is omitted, no error is raised."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("index corrupted")
        )

        result = await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper"],
            vector_store=mock_vector_store,
        )

        assert result == []

    async def test_multiple_module_failures_accumulate(self) -> None:
        """Failures across multiple modules accumulate warnings."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(side_effect=RuntimeError("timeout"))
        warnings: list[str] = []

        await find_related_files(
            file_path="src/test.py",
            imported_modules=["alpha", "Beta"],
            vector_store=mock_vector_store,
            warnings=warnings,
        )

        assert len(warnings) == 2
        assert "alpha" in warnings[0]
        assert "Beta" in warnings[1]

    async def test_no_warning_on_success(self) -> None:
        """Successful search does not append any warnings."""
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])
        warnings: list[str] = []

        await find_related_files(
            file_path="src/test.py",
            imported_modules=["helper"],
            vector_store=mock_vector_store,
            warnings=warnings,
        )

        assert warnings == []


class TestGetTypeDefinitionsUsedWarnings:
    """Tests that get_type_definitions_used propagates warnings."""

    async def test_appends_warning_on_search_failure(self) -> None:
        """Search failure appends a warning when warnings list is provided."""
        chunk = _make_chunk(
            content="def process(data: LongTypeName) -> int: pass",
        )
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("embedding failed")
        )
        warnings: list[str] = []

        result = await get_type_definitions_used(
            [chunk], mock_vector_store, warnings=warnings
        )

        assert result == []
        assert len(warnings) >= 1
        assert any("LongTypeName" in w for w in warnings)
        assert all("embedding failed" in w for w in warnings)

    async def test_no_warning_without_list(self) -> None:
        """When warnings parameter is omitted, no error is raised."""
        chunk = _make_chunk(
            content="def process(data: LongTypeName) -> None: pass",
        )
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("embedding failed")
        )

        result = await get_type_definitions_used([chunk], mock_vector_store)

        assert result == []

    async def test_no_warning_on_success(self) -> None:
        """Successful search does not append any warnings."""
        chunk = _make_chunk(
            content="def process(data: LongTypeName) -> None: pass",
        )
        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[])
        warnings: list[str] = []

        await get_type_definitions_used([chunk], mock_vector_store, warnings=warnings)

        assert warnings == []


class TestBuildFileContextWarnings:
    """Tests that build_file_context collects warnings into FileContext."""

    async def test_collects_all_warnings(self, tmp_path: Path) -> None:
        """Warnings from callers, related files, and types are all collected."""
        chunks = [
            _make_chunk(
                chunk_type=ChunkType.IMPORT,
                content="from pathlib import Path",
                file_path="src/test.py",
            ),
            _make_chunk(
                chunk_type=ChunkType.FUNCTION,
                name="long_function",
                content="def long_function(config: ConfigModel) -> ResultType: pass",
                file_path="src/test.py",
            ),
        ]

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(
            side_effect=RuntimeError("search unavailable")
        )

        result = await build_file_context(
            file_path="src/test.py",
            chunks=chunks,
            repo_path=tmp_path,
            vector_store=mock_vector_store,
        )

        # Should have warnings from callers, related files, and type defs
        assert len(result.warnings) >= 1
        assert any("search unavailable" in w for w in result.warnings)

    async def test_no_warnings_on_success(self, tmp_path: Path) -> None:
        """No warnings when all searches succeed."""
        chunks = [
            _make_chunk(
                chunk_type=ChunkType.FUNCTION,
                name="long_function",
                content="def long_function(): pass",
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

        assert result.warnings == []

    async def test_warnings_field_is_list(self, tmp_path: Path) -> None:
        """FileContext.warnings defaults to an empty list."""
        context = FileContext(file_path="src/test.py")
        assert context.warnings == []
        assert isinstance(context.warnings, list)


class TestFormatContextForLlmWarnings:
    """Tests that format_context_for_llm includes generation notes."""

    def test_includes_generation_notes_with_warnings(self) -> None:
        """Warnings produce a 'Generation Notes' section in output."""
        context = FileContext(
            file_path="src/test.py",
            warnings=[
                "Caller search failed for 'my_func': timeout",
                "Related file search failed for module 'utils': connection error",
            ],
        )

        result = format_context_for_llm(context)

        assert "## Generation Notes" in result
        assert "Some context could not be fully resolved" in result
        assert "Caller search failed" in result
        assert "Related file search failed" in result

    def test_omits_generation_notes_without_warnings(self) -> None:
        """No 'Generation Notes' section when there are no warnings."""
        context = FileContext(
            file_path="src/test.py",
            imports=["import os"],
        )

        result = format_context_for_llm(context)

        assert "Generation Notes" not in result

    def test_omits_generation_notes_for_empty_context(self) -> None:
        """Empty context produces empty string, no notes section."""
        context = FileContext(file_path="src/test.py")

        result = format_context_for_llm(context)

        assert result == ""
        assert "Generation Notes" not in result

    def test_generation_notes_appear_after_other_sections(self) -> None:
        """Generation notes appear at the end, after other sections."""
        context = FileContext(
            file_path="src/test.py",
            imports=["import os"],
            warnings=["Something failed"],
        )

        result = format_context_for_llm(context)

        deps_pos = result.index("Dependencies")
        notes_pos = result.index("Generation Notes")
        assert notes_pos > deps_pos
