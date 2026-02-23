"""Tests for files index generation and file docs callbacks."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.wiki.files import (
    _create_source_details,
    _generate_files_index,
    _inject_inline_source_code,
    generate_file_docs,
    generate_single_file_doc,
)
from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    FileInfo,
    IndexStatus,
    Language,
    SearchResult,
    WikiPage,
)


def make_index_status(
    repo_path: str,
    total_files: int = 0,
    total_chunks: int = 0,
    languages: dict | None = None,
    files: list | None = None,
) -> IndexStatus:
    """Helper to create IndexStatus with required fields."""
    return IndexStatus(
        repo_path=repo_path,
        indexed_at=time.time(),
        total_files=total_files,
        total_chunks=total_chunks,
        languages=languages or {},
        files=files or [],
    )


def make_file_info(
    path: str,
    hash: str = "abc123",
    language: Language | None = Language.PYTHON,
    chunk_count: int = 5,
) -> FileInfo:
    """Helper to create FileInfo with required fields."""
    return FileInfo(
        path=path,
        hash=hash,
        language=language,
        size_bytes=100,
        last_modified=time.time(),
        chunk_count=chunk_count,
    )


def make_code_chunk(
    file_path: str = "src/test.py",
    name: str = "TestClass",
    chunk_type: ChunkType = ChunkType.CLASS,
    content: str = "class TestClass:\n    pass",
    language: Language = Language.PYTHON,
    start_line: int = 1,
    end_line: int = 10,
    parent_name: str | None = None,
) -> CodeChunk:
    """Helper to create CodeChunk with sensible defaults."""
    return CodeChunk(
        id=f"{file_path}:{name}",
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=name,
        content=content,
        start_line=start_line,
        end_line=end_line,
        parent_name=parent_name,
    )


def make_search_result(
    chunk: CodeChunk | None = None,
    score: float = 0.9,
) -> SearchResult:
    """Helper to create SearchResult."""
    if chunk is None:
        chunk = make_code_chunk()
    return SearchResult(
        chunk=chunk,
        score=score,
        highlights=[],
    )


class TestGenerateFilesIndex:
    """Tests for _generate_files_index function."""

    def test_generates_basic_index(self):
        """Test generates basic index content."""
        pages = [
            WikiPage(
                path="files/src/main.md",
                title="main.py",
                content="",
                generated_at=time.time(),
            ),
            WikiPage(
                path="files/src/utils.md",
                title="utils.py",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_files_index(pages)

        assert "# Source Files" in result
        assert "[main.py]" in result
        assert "[utils.py]" in result

    def test_groups_by_directory(self):
        """Test groups files by directory."""
        pages = [
            WikiPage(
                path="files/src/main.md",
                title="main.py",
                content="",
                generated_at=time.time(),
            ),
            WikiPage(
                path="files/tests/test_main.md",
                title="test_main.py",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_files_index(pages)

        assert "## src" in result
        assert "## tests" in result

    def test_excludes_index_page(self):
        """Test excludes index page from listing."""
        pages = [
            WikiPage(
                path="files/index.md",
                title="Source Files",
                content="",
                generated_at=time.time(),
            ),
            WikiPage(
                path="files/src/main.md",
                title="main.py",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_files_index(pages)

        assert "[Source Files]" not in result
        assert "[main.py]" in result

    def test_handles_root_level_files(self):
        """Test handles files without directory prefix."""
        pages = [
            WikiPage(
                path="files/setup.md",
                title="setup.py",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_files_index(pages)

        assert "## root" in result
        assert "[setup.py]" in result

    def test_generates_relative_links(self):
        """Test generates correct relative links."""
        pages = [
            WikiPage(
                path="files/src/core/parser.md",
                title="parser.py",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_files_index(pages)

        # Link should be relative to files/index.md
        assert "(src/core/parser.md)" in result

    def test_sorts_files_alphabetically(self):
        """Test sorts files alphabetically within directories."""
        pages = [
            WikiPage(
                path="files/src/zebra.md",
                title="zebra.py",
                content="",
                generated_at=time.time(),
            ),
            WikiPage(
                path="files/src/alpha.md",
                title="alpha.py",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_files_index(pages)

        # alpha should appear before zebra
        alpha_pos = result.find("alpha.py")
        zebra_pos = result.find("zebra.py")
        assert alpha_pos < zebra_pos

    def test_handles_empty_pages(self):
        """Test handles empty pages list."""
        result = _generate_files_index([])

        assert "# Source Files" in result


class TestGenerateFileDocsCallbacks:
    """Tests for callback functionality in generate_file_docs."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## File Overview\n\nDoc content.")
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        mock.get_chunks_by_file = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_status_manager(self):
        """Create a mock WikiStatusManager."""
        mock = MagicMock()
        mock.needs_regeneration = MagicMock(return_value=True)
        mock.load_existing_page = AsyncMock(return_value=None)
        mock.record_page_status = MagicMock()
        return mock

    @pytest.fixture
    def mock_entity_registry(self):
        """Create a mock EntityRegistry."""
        mock = MagicMock()
        mock.register_from_chunks = MagicMock()
        return mock

    @pytest.fixture
    def mock_config(self):
        """Create a mock Config."""
        mock = MagicMock()
        mock.wiki = MagicMock()
        mock.wiki.context_search_limit = 20
        mock.wiki.fallback_search_limit = 10
        mock.wiki.max_file_docs = 50
        mock.wiki.max_concurrent_llm_calls = 3
        mock.wiki.max_chunk_content_chars = 15000
        mock.wiki.max_chunks_per_file = 60
        mock.effective_llm_concurrency = 3
        return mock

    async def test_calls_write_callback_for_each_page(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test calls write_callback for each generated page."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        written_pages = []

        async def write_callback(page: WikiPage):
            written_pages.append(page)

        pages, generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
            write_callback=write_callback,
        )

        # write_callback should be called for the generated page
        assert len(written_pages) >= 1
        assert any(p.path == "files/src/main.md" for p in written_pages)

    async def test_calls_progress_callback_for_each_file(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test calls progress_callback for each processed file."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        progress_calls = []

        def progress_callback(message: str, current: int, total: int):
            progress_calls.append((message, current, total))

        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
            progress_callback=progress_callback,
        )

        # progress_callback should be called at least once
        assert len(progress_calls) >= 1
        # Should include file path in message
        assert any("src/main.py" in call[0] for call in progress_calls)

    async def test_calls_generation_progress_complete_file_on_error(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test calls generation_progress.complete_file() on error."""
        # Make get_chunks_by_file raise an error
        mock_vector_store.get_chunks_by_file = AsyncMock(
            side_effect=ValueError("Test error")
        )

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        mock_progress = MagicMock()
        mock_progress.start_phase = MagicMock()
        mock_progress.complete_file = MagicMock()
        mock_progress.complete_phase = MagicMock()

        # Should not raise - errors are caught
        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
            generation_progress=mock_progress,
        )

        # complete_file should be called even on error (without filename arg)
        mock_progress.complete_file.assert_called()

    async def test_generation_progress_start_and_complete_phase(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test generation_progress start_phase and complete_phase are called."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        mock_progress = MagicMock()
        mock_progress.start_phase = MagicMock()
        mock_progress.complete_file = MagicMock()
        mock_progress.complete_phase = MagicMock()

        await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
            generation_progress=mock_progress,
        )

        mock_progress.start_phase.assert_called_once_with("file_docs", total=1)
        mock_progress.complete_file.assert_called()
        mock_progress.complete_phase.assert_called_once()
