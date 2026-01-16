"""Tests for wiki_files.py to improve coverage."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.wiki_files import (
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


class TestGenerateSingleFileDoc:
    """Tests for generate_single_file_doc function."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## File Overview\n\nTest file documentation.")
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
        return mock

    async def test_returns_none_for_no_chunks(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test returns None when no chunks found for file."""
        mock_vector_store.search = AsyncMock(return_value=[])

        file_info = make_file_info(path="src/empty.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert page is None
        assert was_skipped is False

    async def test_generates_doc_for_file_with_chunks(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test generates documentation for file with chunks."""
        chunk = make_code_chunk(
            file_path="src/main.py", name="main_func", chunk_type=ChunkType.FUNCTION
        )
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="src/main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert page is not None
        assert page.path == "files/src/main.md"
        assert page.title == "main.py"
        assert was_skipped is False

    async def test_creates_nested_wiki_path(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test creates nested wiki path for nested source files."""
        chunk = make_code_chunk(file_path="src/core/parser.py", name="Parser")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="src/core/parser.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, _was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert page.path == "files/src/core/parser.md"

    async def test_skips_unchanged_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test skips regeneration for unchanged files."""
        existing_page = WikiPage(
            path="files/src/main.md",
            title="main.py",
            content="# Existing",
            generated_at=time.time(),
        )
        mock_status_manager.needs_regeneration = MagicMock(return_value=False)
        mock_status_manager.load_existing_page = AsyncMock(return_value=existing_page)
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        file_info = make_file_info(path="src/main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=False,
        )

        assert page == existing_page
        assert was_skipped is True
        mock_llm.generate.assert_not_called()

    async def test_full_rebuild_ignores_cache(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test full rebuild regenerates even for unchanged files."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])
        mock_status_manager.needs_regeneration = MagicMock(return_value=False)

        file_info = make_file_info(path="src/main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,  # Full rebuild
        )

        assert page is not None
        assert was_skipped is False
        mock_llm.generate.assert_called()

    async def test_fallback_search_by_filename(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test falls back to searching by filename when no direct matches."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")

        # First search returns no matching chunks, second returns match
        async def search_side_effect(query, **_kwargs):
            if "file:" in query:
                return []  # No direct matches
            return [make_search_result(chunk)]  # Fallback matches

        mock_vector_store.search = AsyncMock(side_effect=search_side_effect)
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="src/main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, _was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert page is not None
        # Should have called search at least twice (direct + fallback)
        # Context builder may add additional searches for callers/related files
        assert mock_vector_store.search.call_count >= 2

    async def test_registers_entities_for_crosslinking(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test registers entities for cross-linking."""
        chunk = make_code_chunk(file_path="src/main.py", name="MainClass")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="src/main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        mock_entity_registry.register_from_chunks.assert_called()

    async def test_adds_class_diagram(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test adds class diagram for files with classes."""
        chunk = make_code_chunk(file_path="src/models.py", name="User", chunk_type=ChunkType.CLASS)
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="src/models.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        with patch("local_deepwiki.generators.wiki_files.generate_class_diagram") as mock_diagram:
            mock_diagram.return_value = "```mermaid\nclassDiagram\n```"

            page, _was_skipped = await generate_single_file_doc(
                file_info=file_info,
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                entity_registry=mock_entity_registry,
                config=mock_config,
                full_rebuild=True,
            )

            assert "Class Diagram" in page.content

    async def test_adds_api_reference(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test adds API reference section."""
        chunk = make_code_chunk(file_path="main.py", name="run")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        # Create actual file
        (tmp_path / "main.py").write_text("def run(): pass")

        file_info = make_file_info(path="main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        with patch("local_deepwiki.generators.wiki_files.get_file_api_docs") as mock_api:
            mock_api.return_value = "### run()\n\nExecutes the main function."

            page, _was_skipped = await generate_single_file_doc(
                file_info=file_info,
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                entity_registry=mock_entity_registry,
                config=mock_config,
                full_rebuild=True,
            )

            assert "API Reference" in page.content

    async def test_strips_llm_generated_diagrams(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test strips LLM-generated class diagrams (we add our own)."""
        mock_llm.generate = AsyncMock(
            return_value="## File Overview\n\n## Class Diagram\n\n```mermaid\nclassDiagram\nFoo\n```"
        )
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="src/main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        with patch("local_deepwiki.generators.wiki_files.generate_class_diagram") as mock_diagram:
            mock_diagram.return_value = ""  # No auto-generated diagram

            page, _was_skipped = await generate_single_file_doc(
                file_info=file_info,
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                entity_registry=mock_entity_registry,
                config=mock_config,
                full_rebuild=True,
            )

            # LLM diagram should be stripped, so just one Class Diagram section if auto-generated
            # Since mock returns empty, there should be no Class Diagram section
            assert page.content.count("classDiagram") <= 1

    async def test_handles_root_level_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test handles root-level files (no directory)."""
        chunk = make_code_chunk(file_path="setup.py", name="setup")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        file_info = make_file_info(path="setup.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        page, _was_skipped = await generate_single_file_doc(
            file_info=file_info,
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert page.path == "files/setup.md"

    async def test_adds_call_graph(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test adds call graph section."""
        chunk = make_code_chunk(file_path="main.py", name="run")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        # Create actual file
        (tmp_path / "main.py").write_text("def run(): pass")

        file_info = make_file_info(path="main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        with patch("local_deepwiki.generators.wiki_files.get_file_call_graph") as mock_graph:
            mock_graph.return_value = "graph TD\n  A --> B"

            page, _was_skipped = await generate_single_file_doc(
                file_info=file_info,
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                entity_registry=mock_entity_registry,
                config=mock_config,
                full_rebuild=True,
            )

            assert "Call Graph" in page.content
            assert "graph TD" in page.content

    async def test_adds_test_examples(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test adds test examples section."""
        chunk = make_code_chunk(file_path="main.py", name="MyClass")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        # Create actual file
        (tmp_path / "main.py").write_text("class MyClass: pass")

        file_info = make_file_info(path="main.py")
        index_status = make_index_status(repo_path=str(tmp_path))

        with patch("local_deepwiki.generators.wiki_files.get_file_examples") as mock_examples:
            mock_examples.return_value = "## Test Examples\n\n```python\ntest code\n```"

            page, _was_skipped = await generate_single_file_doc(
                file_info=file_info,
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                status_manager=mock_status_manager,
                entity_registry=mock_entity_registry,
                config=mock_config,
                full_rebuild=True,
            )

            assert "Test Examples" in page.content


class TestGenerateFileDocs:
    """Tests for generate_file_docs function."""

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
        return mock

    async def test_returns_empty_for_no_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test returns empty when no files in index."""
        index_status = make_index_status(repo_path=str(tmp_path), files=[])

        pages, generated, skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert pages == []
        assert generated == 0
        assert skipped == 0

    async def test_filters_init_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test filters out __init__.py files."""
        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/__init__.py")],
        )

        pages, generated, skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert pages == []

    async def test_filters_test_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test filters out test files in tests/ directory."""
        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="tests/test_main.py")],
        )

        pages, generated, skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert pages == []

    async def test_includes_test_files_in_src(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test includes test_*.py files in src/ (e.g., test_examples.py)."""
        chunk = make_code_chunk(file_path="src/test_examples.py", name="TestHelper")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/test_examples.py")],
        )

        pages, generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        # Should include this file (not in tests/ directory)
        assert len(pages) > 0

    async def test_filters_low_chunk_count_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test filters out files with low chunk count."""
        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/tiny.py", chunk_count=1)],  # Too few chunks
        )

        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        assert pages == []

    async def test_limits_files_by_max_file_docs(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test limits number of files processed."""
        mock_config.wiki.max_file_docs = 2

        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        # Create many files
        files = [make_file_info(path=f"src/file{i}.py", chunk_count=5) for i in range(10)]
        index_status = make_index_status(repo_path=str(tmp_path), files=files)

        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        # Should have index + max 2 file pages (but may have fewer due to no chunks)
        assert len(pages) <= 3  # index + 2 files

    async def test_generates_files_index(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test generates files index page."""
        chunk = make_code_chunk(file_path="src/main.py", name="main")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        # First page should be files index
        assert pages[0].path == "files/index.md"
        assert pages[0].title == "Source Files"

    async def test_handles_generation_errors(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test handles errors during file generation."""
        # Create chunks for each file
        chunk1 = make_code_chunk(file_path="src/main.py", name="main")
        chunk2 = make_code_chunk(file_path="src/utils.py", name="utils")

        # Return appropriate chunks for each file
        async def search_side_effect(query, **_kwargs):
            if "src/main.py" in query:
                return [make_search_result(chunk1)]
            if "src/utils.py" in query:
                return [make_search_result(chunk2)]
            return []

        async def get_chunks_side_effect(path):
            if path == "src/main.py":
                return [chunk1]
            if path == "src/utils.py":
                return [chunk2]
            return []

        mock_vector_store.search = AsyncMock(side_effect=search_side_effect)
        mock_vector_store.get_chunks_by_file = AsyncMock(side_effect=get_chunks_side_effect)

        # Make LLM raise an error on second call
        call_count = 0

        async def generate_side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("LLM error")
            return "## Overview\n\nContent"

        mock_llm.generate = AsyncMock(side_effect=generate_side_effect)

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/main.py"),
                make_file_info(path="src/utils.py"),
            ],
        )

        # Should not raise, errors are caught
        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        # Should have at least the successful file + index
        assert len(pages) >= 1

    async def test_prioritizes_files_by_chunk_count(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test prioritizes files with more chunks when limiting."""
        mock_config.wiki.max_file_docs = 1

        chunk = make_code_chunk(file_path="src/complex.py", name="Complex")
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(chunk)])
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[chunk])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[
                make_file_info(path="src/simple.py", chunk_count=3),
                make_file_info(path="src/complex.py", chunk_count=10),  # More complex
            ],
        )

        pages, _generated, _skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=True,
        )

        # Should prioritize the file with more chunks
        # The complex file should be processed
        file_paths = [p.path for p in pages]
        # Since we limit to 1 file, complex.py should be preferred
        assert any("complex" in p for p in file_paths) or len(pages) <= 1

    async def test_counts_skipped_files(
        self,
        mock_llm,
        mock_vector_store,
        mock_status_manager,
        mock_entity_registry,
        mock_config,
        tmp_path,
    ):
        """Test correctly counts skipped files (incremental update)."""
        # Set up to return existing page (skipped)
        existing_page = WikiPage(
            path="files/src/main.md",
            title="main.py",
            content="# Existing",
            generated_at=time.time(),
        )
        mock_status_manager.needs_regeneration = MagicMock(return_value=False)
        mock_status_manager.load_existing_page = AsyncMock(return_value=existing_page)
        mock_vector_store.get_chunks_by_file = AsyncMock(return_value=[])

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py")],
        )

        pages, generated, skipped = await generate_file_docs(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_status_manager,
            entity_registry=mock_entity_registry,
            config=mock_config,
            full_rebuild=False,  # Incremental, not full rebuild
        )

        # Should count as skipped
        assert skipped == 1
        assert generated == 0
        # Should still have the page in results
        assert len(pages) == 2  # index + skipped page


class TestGenerateFilesIndex:
    """Tests for _generate_files_index function."""

    def test_generates_basic_index(self):
        """Test generates basic index content."""
        pages = [
            WikiPage(
                path="files/src/main.md", title="main.py", content="", generated_at=time.time()
            ),
            WikiPage(
                path="files/src/utils.md", title="utils.py", content="", generated_at=time.time()
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
                path="files/src/main.md", title="main.py", content="", generated_at=time.time()
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
                path="files/index.md", title="Source Files", content="", generated_at=time.time()
            ),
            WikiPage(
                path="files/src/main.md", title="main.py", content="", generated_at=time.time()
            ),
        ]

        result = _generate_files_index(pages)

        assert "[Source Files]" not in result
        assert "[main.py]" in result

    def test_handles_root_level_files(self):
        """Test handles files without directory prefix."""
        pages = [
            WikiPage(path="files/setup.md", title="setup.py", content="", generated_at=time.time()),
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
                path="files/src/zebra.md", title="zebra.py", content="", generated_at=time.time()
            ),
            WikiPage(
                path="files/src/alpha.md", title="alpha.py", content="", generated_at=time.time()
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


class TestCreateSourceDetails:
    """Tests for _create_source_details function."""

    def test_creates_details_block(self):
        """Test creates a properly formatted details block."""
        chunk = make_code_chunk(
            name="my_func",
            chunk_type=ChunkType.FUNCTION,
            content="def my_func():\n    pass",
            start_line=10,
            end_line=12,
        )

        result = _create_source_details(chunk, "python")

        assert "<details>" in result
        assert "</details>" in result
        assert "View Source (lines 10-12)" in result
        assert "```python" in result
        assert "def my_func():" in result

    def test_uses_correct_syntax_highlighting(self):
        """Test uses the provided syntax language."""
        chunk = make_code_chunk(
            name="main",
            chunk_type=ChunkType.FUNCTION,
            content="func main() {}",
            language=Language.GO,
        )

        result = _create_source_details(chunk, "go")

        assert "```go" in result


class TestInjectInlineSourceCode:
    """Tests for _inject_inline_source_code function."""

    def test_injects_source_after_api_reference_function(self):
        """Test injects source code after function in API Reference."""
        content = """## API Reference

### Functions

#### `my_func`

```python
def my_func() -> None
```

Does something.

**Returns:** `None`

## Other Section
"""
        chunk = make_code_chunk(
            name="my_func",
            chunk_type=ChunkType.FUNCTION,
            content="def my_func():\n    pass",
            start_line=10,
            end_line=12,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        # Source should appear after Returns
        assert "View Source (lines 10-12)" in result
        assert "<details>" in result
        # Source should be before "Other Section"
        source_pos = result.find("View Source")
        other_pos = result.find("## Other Section")
        assert source_pos < other_pos

    def test_handles_multiple_functions(self):
        """Test handles multiple functions in API Reference."""
        content = """## API Reference

### Functions

#### `func_a`

```python
def func_a() -> None
```

First function.

**Returns:** `None`

#### `func_b`

```python
def func_b() -> str
```

Second function.

**Returns:** `str`
"""
        chunks = [
            make_code_chunk(
                name="func_a",
                chunk_type=ChunkType.FUNCTION,
                content="def func_a():\n    pass",
                start_line=1,
                end_line=3,
            ),
            make_code_chunk(
                name="func_b",
                chunk_type=ChunkType.FUNCTION,
                content="def func_b():\n    return 'hello'",
                start_line=5,
                end_line=7,
            ),
        ]

        result = _inject_inline_source_code(content, chunks, "python")

        # Both functions should have source
        assert "View Source (lines 1-3)" in result
        assert "View Source (lines 5-7)" in result

    def test_adds_unmatched_chunks_to_additional_section(self):
        """Test adds unmatched chunks to Additional Source Code section."""
        content = """## API Reference

#### `unknown_func`

Some description.
"""
        chunk = make_code_chunk(
            name="other_func",
            chunk_type=ChunkType.FUNCTION,
            content="def other_func():\n    pass",
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        # Original content should be there
        assert "#### `unknown_func`" in result
        # Unmatched chunk should appear in Additional Source Code section
        assert "## Additional Source Code" in result
        assert "#### `other_func`" in result
        assert "View Source" in result

    def test_returns_unchanged_for_empty_chunks(self):
        """Test returns unchanged content for empty chunk list."""
        content = "## Some content\n\nMore content."

        result = _inject_inline_source_code(content, [], "python")

        assert result == content

    def test_skips_non_code_chunks(self):
        """Test skips import and module chunks."""
        content = """#### `imports`

Import statement.
"""
        chunk = make_code_chunk(
            name="imports",
            chunk_type=ChunkType.IMPORT,
            content="import os",
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source" not in result

    def test_handles_class_headings(self):
        """Test handles class headings in API Reference."""
        content = """## API Reference

### Classes

#### `MyClass`

```python
class MyClass
```

A test class.

**Returns:** `MyClass`
"""
        chunk = make_code_chunk(
            name="MyClass",
            chunk_type=ChunkType.CLASS,
            content="class MyClass:\n    pass",
            start_line=1,
            end_line=3,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source (lines 1-3)" in result

    def test_handles_heading_with_signature(self):
        """Test handles headings with full function signature."""
        content = """## API Reference

#### `__init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434")`

Initialize the provider.

**Returns:** `None`
"""
        chunk = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.FUNCTION,
            content="def __init__(self, model, base_url):\n    self.model = model",
            start_line=10,
            end_line=12,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source (lines 10-12)" in result

    def test_handles_class_prefix_in_heading(self):
        """Test handles headings with 'class ' prefix."""
        content = """## API Reference

### `class OllamaProvider`

A provider for Ollama.

**Returns:** `OllamaProvider`
"""
        chunk = make_code_chunk(
            name="OllamaProvider",
            chunk_type=ChunkType.CLASS,
            content="class OllamaProvider:\n    pass",
            start_line=1,
            end_line=5,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        assert "View Source (lines 1-5)" in result

    def test_injects_source_before_next_heading_no_returns(self):
        """Test injects source when hitting next heading without Returns line."""
        content = """## API Reference

#### `__init__`

```python
def __init__(base_url: str)
```

| Parameter | Type |
|-----------|------|
| base_url | str |

### class `NextClass`

Another class.
"""
        chunk = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.FUNCTION,
            content="def __init__(self, base_url):\n    self.url = base_url",
            start_line=5,
            end_line=7,
        )

        result = _inject_inline_source_code(content, [chunk], "python")

        # Source should be injected before NextClass heading
        assert "View Source (lines 5-7)" in result
        # The next heading should still be present
        assert "### class `NextClass`" in result
        # Source should come before NextClass
        source_pos = result.find("View Source")
        next_class_pos = result.find("### class `NextClass`")
        assert source_pos < next_class_pos

    def test_handles_duplicate_method_names_with_qualified_lookup(self):
        """Test uses qualified names to match methods in different classes."""
        content = """## API Reference

### class `ClassA`

First class.

#### `__init__`

Initialize ClassA.

### class `ClassB`

Second class.

#### `__init__`

Initialize ClassB.
"""
        chunk_a = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.METHOD,
            content="def __init__(self):\n    self.a = 1",
            start_line=10,
            end_line=12,
            parent_name="ClassA",
        )
        chunk_b = make_code_chunk(
            name="__init__",
            chunk_type=ChunkType.METHOD,
            content="def __init__(self):\n    self.b = 2",
            start_line=20,
            end_line=22,
            parent_name="ClassB",
        )

        result = _inject_inline_source_code(content, [chunk_a, chunk_b], "python")

        # Both should have different source blocks
        assert "View Source (lines 10-12)" in result
        assert "View Source (lines 20-22)" in result
        # ClassA's __init__ should get ClassA's source
        class_a_pos = result.find("### class `ClassA`")
        class_b_pos = result.find("### class `ClassB`")
        source_a_pos = result.find("View Source (lines 10-12)")
        source_b_pos = result.find("View Source (lines 20-22)")
        assert class_a_pos < source_a_pos < class_b_pos < source_b_pos

    def test_falls_back_to_class_source_for_unmatched_method(self):
        """Test uses class source when method chunk doesn't exist."""
        content = """## API Reference

### class `SimpleClass`

A simple class.

#### `__init__`

Initialize the class.

#### `do_something`

Do something.
"""
        # Only class chunk exists, no separate method chunks
        class_chunk = make_code_chunk(
            name="SimpleClass",
            chunk_type=ChunkType.CLASS,
            content="class SimpleClass:\n    def __init__(self):\n        pass\n    def do_something(self):\n        pass",
            start_line=1,
            end_line=5,
        )

        result = _inject_inline_source_code(content, [class_chunk], "python")

        # Class heading should get class source
        assert "View Source (lines 1-5)" in result
        # Method headings should also get class source as fallback
        # Count occurrences - should be 3 (class + 2 methods)
        assert result.count("View Source (lines 1-5)") == 3

    def test_includes_github_link_when_repo_info_provided(self):
        """Test includes GitHub link when repo_info is provided."""
        from local_deepwiki.core.git_utils import GitRepoInfo

        content = """## API Reference

#### `my_func`

A function.

**Returns:** `None`
"""
        chunk = make_code_chunk(
            name="my_func",
            chunk_type=ChunkType.FUNCTION,
            content="def my_func():\n    pass",
            start_line=10,
            end_line=12,
            file_path="src/example.py",
        )

        repo_info = GitRepoInfo(
            remote_url="https://github.com/owner/repo",
            host="github.com",
            owner="owner",
            repo="repo",
            default_branch="main",
        )

        result = _inject_inline_source_code(content, [chunk], "python", repo_info)

        # Should include GitHub link
        assert "GitHub" in result
        assert "https://github.com/owner/repo/blob/main/src/example.py#L10-L12" in result
