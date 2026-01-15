"""Tests for wiki_modules.py to improve coverage."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from local_deepwiki.generators.wiki_modules import (
    _generate_modules_index,
    generate_module_docs,
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
) -> FileInfo:
    """Helper to create FileInfo with required fields."""
    return FileInfo(
        path=path,
        hash=hash,
        language=language,
        size_bytes=100,
        last_modified=time.time(),
    )


def make_code_chunk(
    file_path: str = "src/test.py",
    name: str = "TestClass",
    chunk_type: ChunkType = ChunkType.CLASS,
    content: str = "class TestClass:\n    pass",
    language: Language = Language.PYTHON,
) -> CodeChunk:
    """Helper to create CodeChunk with sensible defaults."""
    return CodeChunk(
        id=f"{file_path}:{name}",
        file_path=file_path,
        language=language,
        chunk_type=chunk_type,
        name=name,
        content=content,
        start_line=1,
        end_line=10,
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


class TestGenerateModuleDocs:
    """Tests for generate_module_docs function."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## Module Purpose\n\nTest module.")
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_status_manager(self):
        """Create a mock WikiStatusManager."""
        mock = MagicMock()
        mock.needs_regeneration = MagicMock(return_value=True)
        mock.load_existing_page = AsyncMock(return_value=None)
        mock.record_page_status = MagicMock()
        return mock

    async def test_returns_empty_for_no_files(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test returns empty when no files in index."""
        index_status = make_index_status(repo_path=str(tmp_path), files=[])

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        assert pages == []
        assert generated == 0
        assert skipped == 0

    async def test_skips_single_file_directories(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test skips directories with less than 2 files."""
        # Single file in directory - should be skipped
        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        assert pages == []
        assert generated == 0

    async def test_groups_files_by_directory(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test correctly groups files by top-level directory."""
        # Multiple files in src directory
        chunk1 = make_code_chunk(file_path="src/main.py", name="main")
        chunk2 = make_code_chunk(file_path="src/utils.py", name="utils")
        mock_vector_store.search = AsyncMock(
            return_value=[make_search_result(chunk1), make_search_result(chunk2)]
        )

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # Should generate module index + src module page
        assert len(pages) == 2
        assert generated == 1  # One module page generated
        assert any(p.path == "modules/src.md" for p in pages)

    async def test_handles_root_level_files(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test root-level files grouped under 'root' but no page generated without matching chunks.

        Root-level files are grouped under 'root' directory name, but since the chunk
        file_path filter checks startswith('root'), files with paths like 'main.py'
        won't match, so no module page is generated for root files.
        """
        chunk1 = make_code_chunk(file_path="main.py", name="main")
        chunk2 = make_code_chunk(file_path="config.py", name="config")
        mock_vector_store.search = AsyncMock(
            return_value=[make_search_result(chunk1), make_search_result(chunk2)]
        )

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="main.py"),
                make_file_info(path="config.py"),
            ],
        )

        pages, generated, _skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # Root files get grouped but no page generated since chunk filter doesn't match
        assert pages == []
        assert generated == 0

    async def test_generates_modules_index(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test generates modules index page."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, _, _ = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # First page should be modules index
        assert pages[0].path == "modules/index.md"
        assert pages[0].title == "Modules"

    async def test_skips_unchanged_pages(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test skips regeneration of unchanged pages."""
        # Configure status manager to indicate no regeneration needed
        mock_status_manager.needs_regeneration = MagicMock(return_value=False)
        existing_page = WikiPage(
            path="modules/src.md",
            title="Module: src",
            content="# Existing content",
            generated_at=time.time(),
        )
        mock_status_manager.load_existing_page = AsyncMock(return_value=existing_page)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=False,  # Not a full rebuild
        )

        assert generated == 0
        assert skipped == 1
        # LLM should not have been called
        mock_llm.generate.assert_not_called()

    async def test_full_rebuild_ignores_cache(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test full rebuild regenerates all pages."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        # Even if needs_regeneration returns False, full_rebuild should still generate
        mock_status_manager.needs_regeneration = MagicMock(return_value=False)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,  # Full rebuild
        )

        assert generated == 1
        assert skipped == 0
        mock_llm.generate.assert_called()

    async def test_filters_chunks_by_directory(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test filters search results to chunks from relevant directory."""
        # Return chunks from different directories
        src_chunk = make_code_chunk(file_path="src/main.py", name="main")
        other_chunk = make_code_chunk(file_path="other/util.py", name="util")
        mock_vector_store.search = AsyncMock(
            return_value=[make_search_result(src_chunk), make_search_result(other_chunk)]
        )

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # LLM should have been called with only src directory chunks
        call_args = mock_llm.generate.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert "src/main.py" in prompt

    async def test_skips_directories_without_relevant_chunks(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test skips directories with no matching chunks from search."""
        # Return no relevant chunks for the directory
        mock_vector_store.search = AsyncMock(return_value=[])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # No pages generated since no chunks match
        assert pages == []
        assert generated == 0

    async def test_generates_multiple_modules(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test generates pages for multiple modules."""
        src_chunk = make_code_chunk(file_path="src/main.py", name="main")
        tests_chunk = make_code_chunk(file_path="tests/test_main.py", name="test_main")

        async def search_side_effect(query, **_kwargs):
            if "src" in query:
                return [make_search_result(src_chunk)]
            if "tests" in query:
                return [make_search_result(tests_chunk)]
            return []

        mock_vector_store.search = AsyncMock(side_effect=search_side_effect)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
                make_file_info(path="tests/test_main.py"),
                make_file_info(path="tests/test_utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # Should have index + 2 module pages
        assert len(pages) == 3
        assert generated == 2
        module_paths = [p.path for p in pages]
        assert "modules/index.md" in module_paths
        assert "modules/src.md" in module_paths
        assert "modules/tests.md" in module_paths

    async def test_records_page_status(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test records status for generated pages."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # Should have called record_page_status for module page and index
        assert mock_status_manager.record_page_status.call_count >= 2

    async def test_handles_many_files_in_prompt(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test truncates file list for many files."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])

        # Create 15 files in src directory
        files = [make_file_info(path=f"src/file{i}.py") for i in range(15)]
        index_status = make_index_status(repo_path=str(tmp_path), files=files)

        await generate_module_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            full_rebuild=True,
        )

        # Prompt should have ellipsis for truncated file list
        call_args = mock_llm.generate.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert "..." in prompt


class TestGenerateModulesIndex:
    """Tests for _generate_modules_index function."""

    def test_generates_basic_index(self):
        """Test generates basic index content."""
        pages = [
            WikiPage(path="modules/src.md", title="Module: src", content="", generated_at=time.time()),
            WikiPage(path="modules/tests.md", title="Module: tests", content="", generated_at=time.time()),
        ]

        result = _generate_modules_index(pages)

        assert "# Modules" in result
        assert "[Module: src](src.md)" in result
        assert "[Module: tests](tests.md)" in result

    def test_excludes_index_page_from_listing(self):
        """Test excludes the index page itself from listings."""
        pages = [
            WikiPage(path="modules/index.md", title="Modules", content="", generated_at=time.time()),
            WikiPage(path="modules/src.md", title="Module: src", content="", generated_at=time.time()),
        ]

        result = _generate_modules_index(pages)

        # Should have link to src.md but not to index.md
        assert "[Module: src](src.md)" in result
        assert "index.md" not in result

    def test_handles_empty_pages(self):
        """Test handles empty pages list."""
        result = _generate_modules_index([])

        assert "# Modules" in result
        # Should have header but no links

    def test_generates_correct_links(self):
        """Test generates correct relative links."""
        pages = [
            WikiPage(
                path="modules/my_module.md", title="Module: my_module", content="", generated_at=time.time()
            ),
        ]

        result = _generate_modules_index(pages)

        # Link should use stem (filename without extension)
        assert "[Module: my_module](my_module.md)" in result
