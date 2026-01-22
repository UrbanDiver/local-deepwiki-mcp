"""Tests for wiki.py to improve coverage."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.models import (
    FileInfo,
    IndexStatus,
    Language,
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


class TestWikiGeneratorInit:
    """Tests for WikiGenerator initialization."""

    def test_init_with_defaults(self, tmp_path):
        """Test WikiGenerator initialization with default config."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            # Make model_copy return a new mock to simulate defensive copying
            config_copy = MagicMock()
            config_copy.llm = config.llm
            config_copy.get_prompts.return_value = config.get_prompts.return_value
            config.model_copy.return_value = config_copy
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                assert generator.wiki_path == tmp_path
                assert generator.vector_store == mock_vector_store
                # Config should be a copy (via model_copy), not the original
                assert generator.config == config_copy
                assert generator.entity_registry is not None
                assert generator.relationship_analyzer is not None
                assert generator.status_manager is not None

    def test_init_with_custom_config(self, tmp_path):
        """Test WikiGenerator initialization with custom config."""
        with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
            mock_llm.return_value = MagicMock()

            from local_deepwiki.generators.wiki import WikiGenerator

            custom_config = MagicMock()
            custom_config.llm = MagicMock()
            custom_config.get_prompts.return_value = MagicMock(wiki_system="Custom prompt")
            # Make model_copy return a new mock to simulate defensive copying
            config_copy = MagicMock()
            config_copy.llm = custom_config.llm
            config_copy.get_prompts.return_value = custom_config.get_prompts.return_value
            custom_config.model_copy.return_value = config_copy

            mock_vector_store = MagicMock()
            generator = WikiGenerator(
                wiki_path=tmp_path,
                vector_store=mock_vector_store,
                config=custom_config,
            )

            # Config should be a copy (via model_copy), not the original
            assert generator.config == config_copy

    def test_init_with_llm_provider_override(self, tmp_path):
        """Test WikiGenerator initialization with LLM provider override."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.llm.provider = "ollama"  # Original provider
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")

            # Mock with_llm_provider to return a new config with updated provider
            config_with_provider = MagicMock()
            config_with_provider.llm = MagicMock()
            config_with_provider.llm.provider = "anthropic"
            config_with_provider.get_prompts.return_value = config.get_prompts.return_value
            config.with_llm_provider.return_value = config_with_provider

            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                    llm_provider_name="anthropic",
                )

                # with_llm_provider should have been called with "anthropic"
                config.with_llm_provider.assert_called_once_with("anthropic")
                # Generator's config should be the modified copy
                assert generator.config == config_with_provider
                assert generator.config.llm.provider == "anthropic"


class TestGetMainDefinitionLines:
    """Tests for _get_main_definition_lines method."""

    def test_returns_empty_when_no_table(self, tmp_path):
        """Test returns empty dict when vector store has no table."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                result = generator._get_main_definition_lines()
                assert result == {}

    def test_returns_class_lines(self, tmp_path):
        """Test returns lines for class definitions."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                # Create mock query chain for LanceDB
                def mock_search_results(chunk_type):
                    if chunk_type == "class":
                        return [
                            {"file_path": "src/test.py", "start_line": 10, "end_line": 40}
                        ]
                    elif chunk_type == "function":
                        return [
                            {"file_path": "src/test.py", "start_line": 50, "end_line": 60}
                        ]
                    return []

                mock_table = MagicMock()
                # Chain: table.search().where().select().limit().to_list()
                mock_search = MagicMock()
                mock_table.search.return_value = mock_search
                mock_where = MagicMock()
                mock_search.where.side_effect = lambda filter_str: mock_where
                mock_select = MagicMock()
                mock_where.select.return_value = mock_select
                mock_limit = MagicMock()
                mock_select.limit.return_value = mock_limit
                # Return different results based on the filter
                mock_search.where.side_effect = lambda f: (
                    MagicMock(
                        select=MagicMock(
                            return_value=MagicMock(
                                limit=MagicMock(
                                    return_value=MagicMock(
                                        to_list=MagicMock(
                                            return_value=mock_search_results("class" if "class" in f else "function")
                                        )
                                    )
                                )
                            )
                        )
                    )
                )

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = mock_table

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                result = generator._get_main_definition_lines()
                # Should return class lines (first definition)
                assert "src/test.py" in result
                assert result["src/test.py"] == (10, 40)

    def test_returns_function_lines_when_no_class(self, tmp_path):
        """Test returns function lines when no class exists."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                # Create mock query chain for LanceDB - only functions, no classes
                def mock_search_results(chunk_type):
                    if chunk_type == "class":
                        return []  # No classes
                    elif chunk_type == "function":
                        return [
                            {"file_path": "src/utils.py", "start_line": 5, "end_line": 15},
                            {"file_path": "src/utils.py", "start_line": 20, "end_line": 30},
                        ]
                    return []

                mock_table = MagicMock()
                mock_search = MagicMock()
                mock_table.search.return_value = mock_search
                # Return different results based on the filter
                mock_search.where.side_effect = lambda f: (
                    MagicMock(
                        select=MagicMock(
                            return_value=MagicMock(
                                limit=MagicMock(
                                    return_value=MagicMock(
                                        to_list=MagicMock(
                                            return_value=mock_search_results("class" if "class" in f else "function")
                                        )
                                    )
                                )
                            )
                        )
                    )
                )

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = mock_table

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                result = generator._get_main_definition_lines()
                # Should return first function lines
                assert "src/utils.py" in result
                assert result["src/utils.py"] == (5, 15)


class TestWritePage:
    """Tests for _write_page method."""

    async def test_writes_page_to_disk(self, tmp_path):
        """Test _write_page writes content to correct path."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                page = WikiPage(
                    path="test.md",
                    title="Test Page",
                    content="# Test\n\nContent here",
                    generated_at=time.time(),
                )

                await generator._write_page(page)

                written_file = tmp_path / "test.md"
                assert written_file.exists()
                assert written_file.read_text() == "# Test\n\nContent here"

    async def test_creates_parent_directories(self, tmp_path):
        """Test _write_page creates parent directories."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                page = WikiPage(
                    path="modules/deep/nested.md",
                    title="Nested Page",
                    content="# Nested\n\nDeep content",
                    generated_at=time.time(),
                )

                await generator._write_page(page)

                written_file = tmp_path / "modules" / "deep" / "nested.md"
                assert written_file.exists()
                assert written_file.read_text() == "# Nested\n\nDeep content"


class TestGenerateWikiFunction:
    """Tests for the generate_wiki convenience function."""

    async def test_generate_wiki_uses_default_provider(self, tmp_path):
        """Test generate_wiki uses default LLM provider."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.use_cloud_for_github = False
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.WikiGenerator") as mock_gen_class:
                mock_generator = MagicMock()
                mock_generator.generate = AsyncMock(return_value=MagicMock(pages=[]))
                mock_gen_class.return_value = mock_generator

                from local_deepwiki.generators.wiki import generate_wiki

                mock_vector_store = MagicMock()
                index_status = make_index_status(repo_path=str(tmp_path))

                await generate_wiki(
                    repo_path=tmp_path,
                    wiki_path=tmp_path / ".wiki",
                    vector_store=mock_vector_store,
                    index_status=index_status,
                )

                # Should have created generator with no provider override
                mock_gen_class.assert_called_once()
                call_kwargs = mock_gen_class.call_args.kwargs
                assert call_kwargs.get("llm_provider_name") is None

    async def test_generate_wiki_uses_cloud_for_github(self, tmp_path):
        """Test generate_wiki switches to cloud provider for GitHub repos."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.use_cloud_for_github = True
            config.wiki.github_llm_provider = "anthropic"
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.core.git_utils.is_github_repo") as mock_is_github:
                mock_is_github.return_value = True

                with patch("local_deepwiki.generators.wiki.WikiGenerator") as mock_gen_class:
                    mock_generator = MagicMock()
                    mock_generator.generate = AsyncMock(return_value=MagicMock(pages=[]))
                    mock_gen_class.return_value = mock_generator

                    from local_deepwiki.generators.wiki import generate_wiki

                    mock_vector_store = MagicMock()
                    index_status = make_index_status(repo_path=str(tmp_path))

                    await generate_wiki(
                        repo_path=tmp_path,
                        wiki_path=tmp_path / ".wiki",
                        vector_store=mock_vector_store,
                        index_status=index_status,
                    )

                    # Should have used cloud provider
                    call_kwargs = mock_gen_class.call_args.kwargs
                    assert call_kwargs.get("llm_provider_name") == "anthropic"

    async def test_generate_wiki_respects_explicit_provider(self, tmp_path):
        """Test generate_wiki uses explicit provider over auto-switching."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.use_cloud_for_github = True
            config.wiki.github_llm_provider = "anthropic"
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.WikiGenerator") as mock_gen_class:
                mock_generator = MagicMock()
                mock_generator.generate = AsyncMock(return_value=MagicMock(pages=[]))
                mock_gen_class.return_value = mock_generator

                from local_deepwiki.generators.wiki import generate_wiki

                mock_vector_store = MagicMock()
                index_status = make_index_status(repo_path=str(tmp_path))

                await generate_wiki(
                    repo_path=tmp_path,
                    wiki_path=tmp_path / ".wiki",
                    vector_store=mock_vector_store,
                    index_status=index_status,
                    llm_provider="openai",  # Explicit provider
                )

                # Should have used explicit provider
                call_kwargs = mock_gen_class.call_args.kwargs
                assert call_kwargs.get("llm_provider_name") == "openai"

    async def test_generate_wiki_passes_full_rebuild(self, tmp_path):
        """Test generate_wiki passes full_rebuild flag."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.use_cloud_for_github = False
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.WikiGenerator") as mock_gen_class:
                mock_generator = MagicMock()
                mock_generator.generate = AsyncMock(return_value=MagicMock(pages=[]))
                mock_gen_class.return_value = mock_generator

                from local_deepwiki.generators.wiki import generate_wiki

                mock_vector_store = MagicMock()
                index_status = make_index_status(repo_path=str(tmp_path))

                await generate_wiki(
                    repo_path=tmp_path,
                    wiki_path=tmp_path / ".wiki",
                    vector_store=mock_vector_store,
                    index_status=index_status,
                    full_rebuild=True,
                )

                # Should have called generate with full_rebuild=True
                mock_generator.generate.assert_called_once()
                call_args = mock_generator.generate.call_args
                assert call_args.args[0] == index_status
                assert call_args.kwargs.get("full_rebuild") is True or call_args.args[2] is True


class TestWikiGeneratorGenerate:
    """Tests for WikiGenerator.generate method."""

    @pytest.fixture
    def mock_generator(self, tmp_path):
        """Create a mocked WikiGenerator."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch("local_deepwiki.generators.wiki.get_llm_provider") as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None
                mock_vector_store.search = AsyncMock(return_value=[])

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                yield generator

    async def test_generate_creates_overview_page(self, mock_generator, tmp_path):
        """Test generate creates overview page."""
        index_status = make_index_status(
            repo_path=str(tmp_path),
            total_files=1,
            total_chunks=5,
            languages={"python": 1},
            files=[make_file_info(path="src/test.py")],
        )

        # Mock all the page generation functions
        with patch("local_deepwiki.generators.wiki.generate_overview_page") as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch("local_deepwiki.generators.wiki.generate_architecture_page") as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch("local_deepwiki.generators.wiki.generate_module_docs") as mock_modules:
                    mock_modules.return_value = ([], 0, 0)

                    with patch("local_deepwiki.generators.wiki.generate_file_docs") as mock_files:
                        mock_files.return_value = ([], 0, 0)

                        with patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page"
                        ) as mock_deps:
                            mock_deps.return_value = (
                                WikiPage(
                                    path="dependencies.md",
                                    title="Dependencies",
                                    content="# Dependencies",
                                    generated_at=time.time(),
                                ),
                                ["src/test.py"],
                            )

                            with patch(
                                "local_deepwiki.generators.wiki.generate_changelog_page"
                            ) as mock_changelog:
                                mock_changelog.return_value = None

                                with patch(
                                    "local_deepwiki.generators.wiki.generate_inheritance_page"
                                ) as mock_inheritance:
                                    mock_inheritance.return_value = None

                                    with patch(
                                        "local_deepwiki.generators.wiki.generate_glossary_page"
                                    ) as mock_glossary:
                                        mock_glossary.return_value = None

                                        with patch(
                                            "local_deepwiki.generators.wiki.generate_coverage_page"
                                        ) as mock_coverage:
                                            mock_coverage.return_value = None

                                            with patch(
                                                "local_deepwiki.generators.wiki.add_cross_links"
                                            ) as mock_crosslinks:
                                                mock_crosslinks.side_effect = lambda pages, _: pages

                                                with patch(
                                                    "local_deepwiki.generators.wiki.add_source_refs_sections"
                                                ) as mock_refs:
                                                    mock_refs.side_effect = lambda pages, _, __: pages

                                                    with patch(
                                                        "local_deepwiki.generators.wiki.add_see_also_sections"
                                                    ) as mock_see_also:
                                                        mock_see_also.side_effect = lambda pages, _: pages

                                                        with patch(
                                                            "local_deepwiki.generators.wiki.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki.generate_toc"
                                                            ) as mock_toc:
                                                                mock_toc.return_value = []

                                                                with patch(
                                                                    "local_deepwiki.generators.wiki.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await mock_generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Should have created pages
                                                                        assert result is not None
                                                                        assert (
                                                                            len(result.pages) >= 3
                                                                        )  # overview, architecture, dependencies

                                                                        # Check overview was generated
                                                                        mock_overview.assert_called_once()

    async def test_generate_calls_progress_callback(self, mock_generator, tmp_path):
        """Test generate calls progress callback at each step."""
        index_status = make_index_status(repo_path=str(tmp_path))

        progress_calls = []

        def progress_callback(msg, current, total):
            progress_calls.append((msg, current, total))

        # Mock all generation functions
        with patch("local_deepwiki.generators.wiki.generate_overview_page") as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md", title="Overview", content="# Overview", generated_at=time.time()
            )

            with patch("local_deepwiki.generators.wiki.generate_architecture_page") as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Arch",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs", return_value=([], 0, 0)
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs", return_value=([], 0, 0)
                    ):
                        with patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page"
                        ) as mock_deps:
                            mock_deps.return_value = (
                                WikiPage(
                                    path="dependencies.md",
                                    title="Deps",
                                    content="# Deps",
                                    generated_at=time.time(),
                                ),
                                [],
                            )

                            with patch(
                                "local_deepwiki.generators.wiki.generate_changelog_page",
                                return_value=None,
                            ):
                                with patch(
                                    "local_deepwiki.generators.wiki.generate_inheritance_page",
                                    return_value=None,
                                ):
                                    with patch(
                                        "local_deepwiki.generators.wiki.generate_glossary_page",
                                        return_value=None,
                                    ):
                                        with patch(
                                            "local_deepwiki.generators.wiki.generate_coverage_page",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "local_deepwiki.generators.wiki.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        await mock_generator.generate(
                                                                            index_status=index_status,
                                                                            progress_callback=progress_callback,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Should have multiple progress calls
                                                                        assert len(progress_calls) > 0
                                                                        # Check first call
                                                                        assert (
                                                                            "overview"
                                                                            in progress_calls[0][0].lower()
                                                                        )
