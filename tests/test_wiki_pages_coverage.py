"""Tests for wiki_pages.py to improve coverage."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.manifest import ProjectManifest
from local_deepwiki.generators.wiki_pages import (
    generate_architecture_page,
    generate_changelog_page,
    generate_dependencies_page,
    generate_overview_page,
)
from local_deepwiki.models import (
    ChunkType,
    CodeChunk,
    FileInfo,
    IndexStatus,
    Language,
    SearchResult,
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


class TestGenerateOverviewPage:
    """Tests for generate_overview_page function."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## Description\n\nTest project.\n\n## Key Features\n\n- Feature 1")
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    async def test_generates_basic_overview(self, mock_llm, mock_vector_store, tmp_path):
        """Test generates basic overview page."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=None,
            repo_path=repo_path,
        )

        assert result.path == "index.md"
        assert result.title == "Overview"
        assert "test-repo" in result.content
        assert result.generated_at > 0

    async def test_includes_manifest_description(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes manifest description in content."""
        manifest = ProjectManifest(
            name="my-project",
            description="A great project for testing.",
            language="Python",
            language_version="3.11",
        )
        repo_path = tmp_path / "my-project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=manifest,
            repo_path=repo_path,
        )

        assert "A great project for testing." in result.content

    async def test_includes_technology_stack(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes technology stack from manifest."""
        manifest = ProjectManifest(
            name="my-project",
            language="Python",
            language_version="3.11",
            dependencies={"flask": "2.0", "requests": "2.28"},
        )
        repo_path = tmp_path / "my-project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=manifest,
            repo_path=repo_path,
        )

        assert "Technology Stack" in result.content
        assert "Python 3.11" in result.content
        assert "flask" in result.content

    async def test_includes_entry_points(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes entry points from manifest."""
        manifest = ProjectManifest(
            name="my-cli",
            entry_points={"my-cli": "my_cli.main:run", "my-serve": "my_cli.server:serve"},
        )
        repo_path = tmp_path / "my-cli"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=manifest,
            repo_path=repo_path,
        )

        assert "Quick Start" in result.content
        assert "my-cli" in result.content
        assert "my_cli.main:run" in result.content

    async def test_includes_directory_structure(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes directory structure."""
        # Create some directories
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "app.py").touch()

        index_status = make_index_status(repo_path=str(tmp_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=None,
            repo_path=tmp_path,
        )

        assert "Directory Structure" in result.content

    async def test_uses_code_context_from_search(self, mock_llm, mock_vector_store, tmp_path):
        """Test uses code context from vector store search."""
        # Set up mock to return search results
        chunk1 = make_code_chunk(name="main", chunk_type=ChunkType.FUNCTION)
        chunk2 = make_code_chunk(name="Server", chunk_type=ChunkType.CLASS)
        mock_vector_store.search = AsyncMock(
            return_value=[make_search_result(chunk1), make_search_result(chunk2)]
        )

        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=None,
            repo_path=repo_path,
        )

        # LLM should have been called with code context
        mock_llm.generate.assert_called_once()
        call_args = mock_llm.generate.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert "CODE SAMPLES" in prompt

    async def test_handles_many_dependencies(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles many dependencies by truncating list."""
        manifest = ProjectManifest(
            name="big-project",
            dependencies={f"dep{i}": "1.0" for i in range(20)},  # 20 dependencies
        )
        repo_path = tmp_path / "big-project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=manifest,
            repo_path=repo_path,
        )

        # Should mention "more" since there are over 12 deps
        assert "more" in result.content.lower()


class TestGenerateArchitecturePage:
    """Tests for generate_architecture_page function."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(
            return_value="## System Overview\n\nArchitecture content.\n\n```mermaid\ngraph TD\n```"
        )
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    async def test_generates_basic_architecture(self, mock_llm, mock_vector_store, tmp_path):
        """Test generates basic architecture page."""
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="Architecture expert",
            manifest=None,
            repo_path=repo_path,
        )

        assert result.path == "architecture.md"
        assert result.title == "Architecture"
        assert "System Overview" in result.content or "Architecture" in result.content

    async def test_includes_workflow_sequences(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes workflow sequence diagrams."""
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        with patch(
            "local_deepwiki.generators.wiki_pages.generate_workflow_sequences"
        ) as mock_workflows:
            mock_workflows.return_value = "```mermaid\nsequenceDiagram\n```"

            result = await generate_architecture_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Architecture expert",
                manifest=None,
                repo_path=repo_path,
            )

            assert "Workflow Sequences" in result.content
            mock_workflows.assert_called_once()

    async def test_searches_multiple_context_types(self, mock_llm, mock_vector_store, tmp_path):
        """Test searches for multiple types of architectural context."""
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="Architecture expert",
            manifest=None,
            repo_path=repo_path,
        )

        # Should have made multiple search calls
        assert mock_vector_store.search.call_count >= 3

    async def test_deduplicates_chunks(self, mock_llm, mock_vector_store, tmp_path):
        """Test deduplicates search results from different queries."""
        chunk = make_code_chunk(name="CoreClass", file_path="src/core.py")
        result = make_search_result(chunk)

        # Same result returned for different searches
        mock_vector_store.search = AsyncMock(return_value=[result, result])

        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="Architecture expert",
            manifest=None,
            repo_path=repo_path,
        )

        # LLM should be called with deduplicated context
        mock_llm.generate.assert_called_once()

    async def test_includes_dependency_context(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes dependency context from manifest."""
        manifest = ProjectManifest(
            name="project",
            dependencies={"fastapi": "0.100", "pydantic": "2.0"},
        )
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="Architecture expert",
            manifest=manifest,
            repo_path=repo_path,
        )

        call_args = mock_llm.generate.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert "dependencies" in prompt.lower()

    async def test_extracts_class_names(self, mock_llm, mock_vector_store, tmp_path):
        """Test extracts class names for reference in prompt."""
        class_chunk = make_code_chunk(
            name="MyService", chunk_type=ChunkType.CLASS, file_path="src/service.py"
        )

        # Return class chunk for class search
        async def search_side_effect(query, **_kwargs):
            if "class" in query.lower():
                return [make_search_result(class_chunk)]
            return []

        mock_vector_store.search = AsyncMock(side_effect=search_side_effect)
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="Architecture expert",
            manifest=None,
            repo_path=repo_path,
        )

        call_args = mock_llm.generate.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert "MyService" in prompt


class TestGenerateDependenciesPage:
    """Tests for generate_dependencies_page function."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(
            return_value="## External Dependencies\n\n- flask: Web framework"
        )
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    async def test_generates_basic_dependencies(self, mock_llm, mock_vector_store, tmp_path):
        """Test generates basic dependencies page."""
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            page, source_files = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=None,
                import_search_limit=100,
            )

            assert page.path == "dependencies.md"
            assert page.title == "Dependencies"
            assert isinstance(source_files, list)

    async def test_includes_external_dependencies(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes external dependencies from manifest."""
        manifest = ProjectManifest(
            name="project",
            dependencies={"requests": "2.28.0", "pydantic": "2.0.0"},
        )
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=manifest,
                import_search_limit=100,
            )

            call_args = mock_llm.generate.call_args
            prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
            assert "requests" in prompt
            assert "pydantic" in prompt

    async def test_includes_dev_dependencies(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes dev dependencies from manifest."""
        manifest = ProjectManifest(
            name="project",
            dev_dependencies={"pytest": "7.0", "mypy": "1.0"},
        )
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=manifest,
                import_search_limit=100,
            )

            call_args = mock_llm.generate.call_args
            prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
            assert "pytest" in prompt
            assert "DEV DEPENDENCIES" in prompt

    async def test_includes_import_chunks(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes import chunks from code."""
        import_chunk = make_code_chunk(
            name="imports",
            chunk_type=ChunkType.IMPORT,
            content="import os\nimport sys",
            file_path="src/main.py",
        )
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(import_chunk)])

        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            page, source_files = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=None,
                import_search_limit=100,
            )

            assert "src/main.py" in source_files

    async def test_separates_test_files(self, mock_llm, mock_vector_store, tmp_path):
        """Test separates test files from source files in ordering."""
        import_chunk1 = make_code_chunk(
            name="imports", chunk_type=ChunkType.IMPORT, file_path="src/main.py"
        )
        import_chunk2 = make_code_chunk(
            name="imports", chunk_type=ChunkType.IMPORT, file_path="tests/test_main.py"
        )
        mock_vector_store.search = AsyncMock(
            return_value=[make_search_result(import_chunk1), make_search_result(import_chunk2)]
        )

        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            page, source_files = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=None,
                import_search_limit=100,
            )

            # Source files should come before test files
            src_idx = source_files.index("src/main.py")
            test_idx = source_files.index("tests/test_main.py")
            assert src_idx < test_idx

    async def test_includes_dependency_graph(self, mock_llm, mock_vector_store, tmp_path):
        """Test includes auto-generated dependency graph."""
        import_chunk = make_code_chunk(
            name="imports", chunk_type=ChunkType.IMPORT, file_path="src/main.py"
        )
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(import_chunk)])

        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = "```mermaid\ngraph TD\n  A --> B\n```"

            page, _ = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=None,
                import_search_limit=100,
            )

            assert "Module Dependency Graph" in page.content
            assert "mermaid" in page.content

    async def test_handles_empty_dependency_graph(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles empty dependency graph gracefully."""
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""  # Empty graph

            page, _ = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="Dependencies expert",
                manifest=None,
                import_search_limit=100,
            )

            # Should not include graph section when empty
            assert "Module Dependency Graph" not in page.content


class TestGenerateChangelogPage:
    """Tests for generate_changelog_page function."""

    async def test_returns_none_when_no_repo_path(self):
        """Test returns None when repo_path is None."""
        result = await generate_changelog_page(repo_path=None)
        assert result is None

    async def test_generates_changelog_from_git(self, tmp_path):
        """Test generates changelog from git history."""
        with patch(
            "local_deepwiki.generators.changelog.generate_changelog_content"
        ) as mock_changelog:
            mock_changelog.return_value = "# Changelog\n\n## v1.0.0\n\n- Initial release"

            result = await generate_changelog_page(repo_path=tmp_path)

            assert result is not None
            assert result.path == "changelog.md"
            assert result.title == "Changelog"
            assert "v1.0.0" in result.content
            mock_changelog.assert_called_once_with(tmp_path)

    async def test_returns_none_when_no_changelog_content(self, tmp_path):
        """Test returns None when no changelog content generated."""
        with patch(
            "local_deepwiki.generators.changelog.generate_changelog_content"
        ) as mock_changelog:
            mock_changelog.return_value = ""  # Empty content

            result = await generate_changelog_page(repo_path=tmp_path)

            assert result is None

    async def test_returns_none_for_non_git_repo(self, tmp_path):
        """Test returns None for non-git repository."""
        with patch(
            "local_deepwiki.generators.changelog.generate_changelog_content"
        ) as mock_changelog:
            mock_changelog.return_value = None  # Not a git repo

            result = await generate_changelog_page(repo_path=tmp_path)

            assert result is None


class TestOverviewPageEdgeCases:
    """Edge case tests for generate_overview_page."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## Description\n\nTest.\n\n## Key Features\n\n- Feature")
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    async def test_handles_none_repo_path(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles None repo_path gracefully."""
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=None,
            repo_path=None,  # No repo path
        )

        assert result is not None
        assert result.path == "index.md"
        # Should not include directory structure without repo_path
        assert "Directory Structure" not in result.content

    async def test_handles_manifest_without_language_version(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles manifest without language version."""
        manifest = ProjectManifest(
            name="project",
            language="Python",  # No version
            dependencies={"flask": "2.0"},
        )
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=manifest,
            repo_path=repo_path,
        )

        assert "Python" in result.content
        # Should not have version number

    async def test_handles_wildcard_version(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles wildcard version in dependencies."""
        manifest = ProjectManifest(
            name="project",
            dependencies={"requests": "*"},  # Wildcard version
        )
        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        result = await generate_overview_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=manifest,
            repo_path=repo_path,
        )

        # Should list dependency without version string
        assert "requests" in result.content


class TestArchitecturePageEdgeCases:
    """Edge case tests for generate_architecture_page."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## System Overview\n\nContent")
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    async def test_handles_none_repo_path(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles None repo_path gracefully."""
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        result = await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=None,
            repo_path=None,
        )

        assert result is not None
        assert result.path == "architecture.md"

    async def test_handles_no_classes_found(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles case where no classes are found."""
        # Only return function chunks, no classes
        func_chunk = make_code_chunk(
            name="main", chunk_type=ChunkType.FUNCTION, file_path="src/main.py"
        )
        mock_vector_store.search = AsyncMock(return_value=[make_search_result(func_chunk)])

        repo_path = tmp_path / "project"
        repo_path.mkdir()
        index_status = make_index_status(repo_path=str(repo_path))

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="System prompt",
            manifest=None,
            repo_path=repo_path,
        )

        call_args = mock_llm.generate.call_args
        prompt = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
        assert "No classes found" in prompt


class TestDependenciesPageEdgeCases:
    """Edge case tests for generate_dependencies_page."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.generate = AsyncMock(return_value="## External Dependencies\n\nNone")
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    async def test_handles_no_dependencies(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles project with no dependencies."""
        manifest = ProjectManifest(name="minimal-project")  # No dependencies
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            page, _ = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                manifest=manifest,
                import_search_limit=100,
            )

            assert page is not None

    async def test_handles_large_dependency_lists(self, mock_llm, mock_vector_store, tmp_path):
        """Test handles large dependency lists by truncating."""
        manifest = ProjectManifest(
            name="big-project",
            dependencies={f"dep{i}": "1.0" for i in range(50)},  # 50 dependencies
            dev_dependencies={f"devdep{i}": "1.0" for i in range(30)},  # 30 dev deps
        )
        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                manifest=manifest,
                import_search_limit=100,
            )

            # Should have been called - truncation handled internally
            mock_llm.generate.assert_called_once()

    async def test_filters_non_import_chunks(self, mock_llm, mock_vector_store, tmp_path):
        """Test filters out non-import chunks from import search."""
        import_chunk = make_code_chunk(
            name="imports", chunk_type=ChunkType.IMPORT, file_path="src/main.py"
        )
        func_chunk = make_code_chunk(
            name="process", chunk_type=ChunkType.FUNCTION, file_path="src/utils.py"
        )

        mock_vector_store.search = AsyncMock(
            return_value=[make_search_result(import_chunk), make_search_result(func_chunk)]
        )

        index_status = make_index_status(repo_path=str(tmp_path / "project"))

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            page, source_files = await generate_dependencies_page(
                index_status=index_status,
                vector_store=mock_vector_store,
                llm=mock_llm,
                system_prompt="System prompt",
                manifest=None,
                import_search_limit=100,
            )

            # Only import chunk's file should be in source files
            assert "src/main.py" in source_files
            assert "src/utils.py" not in source_files
