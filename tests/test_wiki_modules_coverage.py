"""Tests for wiki_modules.py to improve coverage."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import (
    make_code_chunk,
    make_file_info,
    make_index_status,
    make_search_result,
    make_wiki_ctx,
)
from local_deepwiki.generators.wiki.modules import (
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
        mock.get_chunks_by_file = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_status_manager(self):
        """Create a mock WikiStatusManager."""
        mock = MagicMock()
        mock.needs_regeneration = MagicMock(return_value=True)
        mock.needs_regeneration_structural = MagicMock(return_value=True)
        mock.load_existing_page = AsyncMock(return_value=None)
        mock.record_page_status = MagicMock()
        mock.record_summary_page_status = MagicMock()
        return mock

    async def test_returns_empty_for_no_files(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test returns empty when no files in index."""
        index_status = make_index_status(repo_path=str(tmp_path), files=[])

        pages, generated, skipped = await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
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
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
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

        async def _get_chunks(fp):
            if fp == "src/main.py":
                return [chunk1]
            if fp == "src/utils.py":
                return [chunk2]
            return []

        mock_vector_store.get_chunks_by_file = AsyncMock(side_effect=_get_chunks)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # Should generate module index + src module page
        assert len(pages) == 2
        assert generated == 2  # One module page + modules index generated
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
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # Root files get grouped but no page generated since chunk filter doesn't match
        assert pages == []
        assert generated == 0

    async def test_generates_modules_index(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test generates modules index page."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, _, _ = await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
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
        mock_status_manager.needs_regeneration_structural = MagicMock(
            return_value=False
        )
        existing_page = WikiPage(
            path="modules/src.md",
            title="Module: src",
            content="# Existing content",
            generated_at=time.time(),
        )
        existing_index = WikiPage(
            path="modules/index.md",
            title="Modules",
            content="# Modules",
            generated_at=time.time(),
        )

        async def _load_existing(page_path):
            if page_path == "modules/src.md":
                return existing_page
            if page_path == "modules/index.md":
                return existing_index
            return None

        mock_status_manager.load_existing_page = AsyncMock(side_effect=_load_existing)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=False,
            )
        )

        assert generated == 0
        assert skipped == 2  # module page + modules index both skipped
        # LLM should not have been called
        mock_llm.generate.assert_not_called()

    async def test_full_rebuild_ignores_cache(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test full rebuild regenerates all pages."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])
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
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        assert generated == 2  # module page + modules index
        assert skipped == 0
        mock_llm.generate.assert_called()

    async def test_filters_chunks_by_directory(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test only includes chunks from the target directory's files."""
        src_chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[src_chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # LLM should have been called with only src directory chunks
        call_args = mock_llm.generate.call_args
        prompt = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        )
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
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # No pages generated since no chunks match
        assert pages == []
        assert generated == 0

    async def test_generates_multiple_modules(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test generates pages for multiple source modules, excludes test dirs."""
        src_chunk = make_code_chunk(file_path="src/main.py", name="main")
        lib_chunk = make_code_chunk(file_path="lib/helpers.py", name="helpers")

        async def _get_chunks(fp):
            if fp.startswith("src/"):
                return [src_chunk]
            if fp.startswith("lib/"):
                return [lib_chunk]
            return []

        mock_vector_store.get_chunks_by_file = AsyncMock(side_effect=_get_chunks)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
                make_file_info(path="lib/helpers.py"),
                make_file_info(path="lib/external.py"),
                make_file_info(path="tests/test_main.py"),
                make_file_info(path="tests/test_utils.py"),
            ],
        )

        pages, generated, skipped = await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # Should have index + 2 source module pages (tests dir excluded)
        assert len(pages) == 3
        assert generated == 3  # 2 module pages + modules index
        module_paths = [p.path for p in pages]
        assert "modules/index.md" in module_paths
        assert "modules/src.md" in module_paths
        assert "modules/lib.md" in module_paths
        assert "modules/tests.md" not in module_paths

    async def test_records_page_status(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test records status for generated pages."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # record_page_status called for module page, record_summary_page_status for index
        assert mock_status_manager.record_page_status.call_count >= 1
        assert mock_status_manager.record_summary_page_status.call_count >= 1

    async def test_handles_many_files_in_prompt(
        self, mock_llm, mock_vector_store, mock_status_manager, tmp_path
    ):
        """Test truncates file list for many files."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        # Create 25 files in src directory (truncation threshold is 20)
        files = [make_file_info(path=f"src/file{i}.py") for i in range(25)]
        index_status = make_index_status(repo_path=str(tmp_path), files=files)

        await generate_module_docs(
            make_wiki_ctx(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                full_rebuild=True,
            )
        )

        # Prompt should have ellipsis for truncated file list
        call_args = mock_llm.generate.call_args
        prompt = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        )
        assert "..." in prompt


class TestGenerateModulesIndex:
    """Tests for _generate_modules_index function."""

    def test_generates_basic_index(self):
        """Test generates basic index content."""
        pages = [
            WikiPage(
                path="modules/src.md",
                title="Module: src",
                content="",
                generated_at=time.time(),
            ),
            WikiPage(
                path="modules/tests.md",
                title="Module: tests",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_modules_index(pages)

        assert "# Modules" in result
        assert "[Module: src](src.md)" in result
        assert "[Module: tests](tests.md)" in result

    def test_excludes_index_page_from_listing(self):
        """Test excludes the index page itself from listings."""
        pages = [
            WikiPage(
                path="modules/index.md",
                title="Modules",
                content="",
                generated_at=time.time(),
            ),
            WikiPage(
                path="modules/src.md",
                title="Module: src",
                content="",
                generated_at=time.time(),
            ),
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
                path="modules/my_module.md",
                title="Module: my_module",
                content="",
                generated_at=time.time(),
            ),
        ]

        result = _generate_modules_index(pages)

        # Link should use stem (filename without extension)
        assert "[Module: my_module](my_module.md)" in result


class TestModuleDocEnrichment:
    """Tests for enriched module documentation (file list, imports, authoritative docs)."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider that captures prompts."""
        mock = MagicMock()
        mock.captured_prompt = None

        async def capture_generate(prompt, **kwargs):
            mock.captured_prompt = prompt
            return "## Module Purpose\n\nEnriched module doc."

        mock.generate = AsyncMock(side_effect=capture_generate)
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store with relevant chunks."""
        mock = MagicMock()

        chunk1 = make_code_chunk(
            file_path="src/parser.py", name="CodeParser", chunk_type="class"
        )
        chunk2 = make_code_chunk(
            file_path="src/indexer.py", name="index_repo", chunk_type="function"
        )
        mock.search = AsyncMock(
            return_value=[make_search_result(chunk1), make_search_result(chunk2)]
        )

        async def _get_chunks_by_file(fp):
            if fp == "src/parser.py":
                return [chunk1]
            if fp == "src/indexer.py":
                return [chunk2]
            return []

        mock.get_chunks_by_file = AsyncMock(side_effect=_get_chunks_by_file)
        return mock

    async def test_file_list_appears_in_prompt(
        self, mock_llm, mock_vector_store, tmp_path
    ):
        """Test that the enriched file list appears in the LLM prompt."""
        from local_deepwiki.generators.wiki.modules import generate_single_module_doc

        ctx = make_wiki_ctx(
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            repo_path=tmp_path,
        )
        page = await generate_single_module_doc(
            dir_name="src",
            files=["src/parser.py", "src/indexer.py", "src/utils.py"],
            ctx=ctx,
        )

        assert page is not None
        prompt = mock_llm.captured_prompt
        assert "FILES IN MODULE:" in prompt
        assert "src/parser.py" in prompt
        assert "src/indexer.py" in prompt

    async def test_authoritative_docs_appear_in_prompt(
        self, mock_llm, mock_vector_store, tmp_path
    ):
        """Test that authoritative docs appear when CLAUDE.md exists."""
        from local_deepwiki.generators.wiki.modules import generate_single_module_doc

        # Create CLAUDE.md
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\n\nThis is a code indexing tool.")

        ctx = make_wiki_ctx(
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            repo_path=tmp_path,
        )
        page = await generate_single_module_doc(
            dir_name="src",
            files=["src/parser.py", "src/indexer.py"],
            ctx=ctx,
        )

        assert page is not None
        prompt = mock_llm.captured_prompt
        assert "AUTHORITATIVE PROJECT DOCUMENTATION" in prompt
        assert "code indexing tool" in prompt

    async def test_no_authoritative_section_without_docs(
        self, mock_llm, mock_vector_store, tmp_path
    ):
        """Test no authoritative section when no docs exist."""
        from local_deepwiki.generators.wiki.modules import generate_single_module_doc

        ctx = make_wiki_ctx(
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            repo_path=tmp_path,
        )
        page = await generate_single_module_doc(
            dir_name="src",
            files=["src/parser.py", "src/indexer.py"],
            ctx=ctx,
        )

        assert page is not None
        prompt = mock_llm.captured_prompt
        assert "AUTHORITATIVE PROJECT DOCUMENTATION" not in prompt

    async def test_file_entity_descriptions_from_chunks(
        self, mock_llm, mock_vector_store, tmp_path
    ):
        """Test that file list includes entity names from search results."""
        from local_deepwiki.generators.wiki.modules import generate_single_module_doc

        ctx = make_wiki_ctx(
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            repo_path=tmp_path,
        )
        page = await generate_single_module_doc(
            dir_name="src",
            files=["src/parser.py", "src/indexer.py"],
            ctx=ctx,
        )

        assert page is not None
        prompt = mock_llm.captured_prompt
        # Should have entity descriptions from chunk results
        assert "defines CodeParser" in prompt or "defines index_repo" in prompt

    async def test_repo_path_none_still_works(self, mock_llm, mock_vector_store):
        """Test that generate_single_module_doc works when repo_path is None."""
        from local_deepwiki.generators.wiki.modules import generate_single_module_doc

        ctx = make_wiki_ctx(
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            repo_path=None,
        )
        page = await generate_single_module_doc(
            dir_name="src",
            files=["src/parser.py", "src/indexer.py"],
            ctx=ctx,
        )

        assert page is not None
        prompt = mock_llm.captured_prompt
        assert "AUTHORITATIVE PROJECT DOCUMENTATION" not in prompt
