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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
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
        with patch(
            "local_deepwiki.generators.wiki.get_cached_llm_provider"
        ) as mock_llm:
            mock_llm.return_value = MagicMock()

            from local_deepwiki.generators.wiki import WikiGenerator

            custom_config = MagicMock()
            custom_config.llm = MagicMock()
            custom_config.get_prompts.return_value = MagicMock(
                wiki_system="Custom prompt"
            )
            # Make model_copy return a new mock to simulate defensive copying
            config_copy = MagicMock()
            config_copy.llm = custom_config.llm
            config_copy.get_prompts.return_value = (
                custom_config.get_prompts.return_value
            )
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
            config_with_provider.get_prompts.return_value = (
                config.get_prompts.return_value
            )
            config.with_llm_provider.return_value = config_with_provider

            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                # Mock the public method that WikiGenerator delegates to
                mock_vector_store.get_main_definition_lines.return_value = {}

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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                # Mock the public method - returns class lines (first definition)
                mock_vector_store.get_main_definition_lines.return_value = {
                    "src/test.py": (10, 40)
                }

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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                # Mock the public method - returns function lines when no class exists
                mock_vector_store.get_main_definition_lines.return_value = {
                    "src/utils.py": (5, 15)
                }

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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
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

            with patch(
                "local_deepwiki.generators.wiki.WikiGenerator"
            ) as mock_gen_class:
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

            with patch(
                "local_deepwiki.core.git_utils.is_github_repo"
            ) as mock_is_github:
                mock_is_github.return_value = True

                with patch(
                    "local_deepwiki.generators.wiki.WikiGenerator"
                ) as mock_gen_class:
                    mock_generator = MagicMock()
                    mock_generator.generate = AsyncMock(
                        return_value=MagicMock(pages=[])
                    )
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

            with patch(
                "local_deepwiki.generators.wiki.WikiGenerator"
            ) as mock_gen_class:
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

            with patch(
                "local_deepwiki.generators.wiki.WikiGenerator"
            ) as mock_gen_class:
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
                assert (
                    call_args.kwargs.get("full_rebuild") is True
                    or call_args.args[2] is True
                )


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

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
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
        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs"
                ) as mock_modules:
                    mock_modules.return_value = ([], 0, 0)

                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs"
                    ) as mock_files:
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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links"
                                            ) as mock_crosslinks:
                                                mock_crosslinks.side_effect = (
                                                    lambda pages, _: pages
                                                )

                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections"
                                                ) as mock_refs:
                                                    mock_refs.side_effect = (
                                                        lambda pages, _, __: pages
                                                    )

                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections"
                                                    ) as mock_see_also:
                                                        mock_see_also.side_effect = (
                                                            lambda pages, _: pages
                                                        )

                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc"
                                                            ) as mock_toc:
                                                                mock_toc.return_value = []

                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await mock_generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Should have created pages
                                                                        assert (
                                                                            result
                                                                            is not None
                                                                        )
                                                                        assert (
                                                                            len(
                                                                                result.pages
                                                                            )
                                                                            >= 3
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
        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Arch",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
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
                                                                        assert (
                                                                            len(
                                                                                progress_calls
                                                                            )
                                                                            > 0
                                                                        )
                                                                        # Check first call
                                                                        assert (
                                                                            "overview"
                                                                            in progress_calls[
                                                                                0
                                                                            ][0].lower()
                                                                        )


class TestIncrementalGeneration:
    """Tests for incremental wiki generation (not full_rebuild).

    These tests cover lines 236, 278, 294, 318-324, 433-448.
    """

    @pytest.fixture
    def setup_generator(self, tmp_path):
        """Create a WikiGenerator for incremental tests."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                yield generator, tmp_path

    async def test_incremental_loads_previous_status(self, setup_generator):
        """Test incremental generation loads previous status (line 236)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py", hash="same_hash")],
        )

        # Create existing index.md and architecture.md for caching
        (tmp_path / "index.md").write_text("# Cached Overview")
        (tmp_path / "architecture.md").write_text("# Cached Architecture")
        (tmp_path / "dependencies.md").write_text("# Cached Dependencies")

        # Mock status_manager.load_status to track the call
        with patch.object(
            generator.status_manager, "load_status", new_callable=AsyncMock
        ) as mock_load:
            mock_load.return_value = None  # No previous status initially

            with patch(
                "local_deepwiki.generators.wiki.generate_overview_page"
            ) as mock_overview:
                mock_overview.return_value = WikiPage(
                    path="index.md",
                    title="Overview",
                    content="# Overview",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_architecture_page"
                ) as mock_arch:
                    mock_arch.return_value = WikiPage(
                        path="architecture.md",
                        title="Architecture",
                        content="# Architecture",
                        generated_at=time.time(),
                    )

                    with patch(
                        "local_deepwiki.generators.wiki.generate_module_docs",
                        return_value=([], 0, 0),
                    ):
                        with patch(
                            "local_deepwiki.generators.wiki.generate_file_docs",
                            return_value=([], 0, 0),
                        ):
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
                                                    "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                    side_effect=lambda p, _: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                        side_effect=lambda p, _, __: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                            side_effect=lambda p, _: p,
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                    return_value=[],
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                    ):
                                                                        with patch(
                                                                            "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                        ):
                                                                            await generator.generate(
                                                                                index_status=index_status,
                                                                                full_rebuild=False,  # Incremental mode
                                                                            )

                                                                            # load_status should have been called for incremental
                                                                            mock_load.assert_called_once()

    async def test_incremental_skips_unchanged_pages(self, setup_generator):
        """Test incremental generation skips unchanged pages (lines 278, 294, 318-324)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py", hash="same_hash")],
        )

        # Create existing pages that will be cached
        (tmp_path / "index.md").write_text("# Cached Overview\nContent here")
        (tmp_path / "architecture.md").write_text("# Cached Architecture\nContent here")
        (tmp_path / "dependencies.md").write_text("# Cached Dependencies")

        # Set up previous status so pages are NOT regenerated
        from local_deepwiki.models import WikiGenerationStatus, WikiPageStatus

        prev_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=3,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="abc",
                    generated_at=time.time(),
                ),
                "architecture.md": WikiPageStatus(
                    path="architecture.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="def",
                    generated_at=time.time(),
                ),
                "dependencies.md": WikiPageStatus(
                    path="dependencies.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="ghi",
                    generated_at=time.time(),
                ),
            },
        )
        generator.status_manager._previous_status = prev_status
        generator.status_manager.file_hashes = {"src/main.py": "same_hash"}

        # Mock generators - they should NOT be called for cached pages
        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="New Overview",
                content="# New",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="New Arch",
                    content="# New Arch",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
                    ):
                        with patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page"
                        ) as mock_deps:
                            mock_deps.return_value = (
                                WikiPage(
                                    path="dependencies.md",
                                    title="New Deps",
                                    content="# New Deps",
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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=False,
                                                                        )

                                                                        # Overview and architecture generators should NOT be called
                                                                        # because pages are cached
                                                                        assert (
                                                                            mock_overview.call_count
                                                                            == 0
                                                                        )
                                                                        assert (
                                                                            mock_arch.call_count
                                                                            == 0
                                                                        )
                                                                        # Dependencies also cached
                                                                        assert (
                                                                            mock_deps.call_count
                                                                            == 0
                                                                        )

    async def test_generate_or_load_page_loads_from_cache(self, setup_generator):
        """Test _generate_or_load_page loads from cache when available (lines 318-324)."""
        generator, tmp_path = setup_generator

        # Create existing page file
        (tmp_path / "test_page.md").write_text("# Cached Page Content")

        # Set up previous status
        from local_deepwiki.generators.wiki import _GenerationContext
        from local_deepwiki.models import WikiGenerationStatus, WikiPageStatus

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=["src/main.py"],
            full_rebuild=False,
        )

        prev_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=1,
            pages={
                "test_page.md": WikiPageStatus(
                    path="test_page.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="xyz",
                    generated_at=12345.0,
                ),
            },
        )
        generator.status_manager._previous_status = prev_status
        generator.status_manager.file_hashes = {"src/main.py": "same_hash"}

        # Generator function that should NOT be called
        async def mock_generator_fn():
            return WikiPage(
                path="test_page.md",
                title="New Page",
                content="# New",
                generated_at=time.time(),
            )

        page, was_generated = await generator._generate_or_load_page(
            ctx=ctx,
            page_path="test_page.md",
            generator=mock_generator_fn,
            source_files=["src/main.py"],
        )

        # Should load from cache
        assert was_generated is False
        assert "# Cached Page Content" in page.content
        assert page.generated_at == 12345.0

    async def test_generate_or_load_page_generates_when_cache_missing(
        self, setup_generator
    ):
        """Test _generate_or_load_page generates when cache file missing (lines 320-321)."""
        generator, tmp_path = setup_generator

        # Don't create the page file (simulating missing cache)
        from local_deepwiki.generators.wiki import _GenerationContext
        from local_deepwiki.models import WikiGenerationStatus, WikiPageStatus

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=["src/main.py"],
            full_rebuild=False,
        )

        prev_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=1,
            pages={
                "missing_page.md": WikiPageStatus(
                    path="missing_page.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="xyz",
                    generated_at=12345.0,
                ),
            },
        )
        generator.status_manager._previous_status = prev_status
        generator.status_manager.file_hashes = {"src/main.py": "same_hash"}

        # Generator that will be called since file is missing
        async def mock_generator_fn():
            return WikiPage(
                path="missing_page.md",
                title="Generated Page",
                content="# Generated Content",
                generated_at=99999.0,
            )

        page, was_generated = await generator._generate_or_load_page(
            ctx=ctx,
            page_path="missing_page.md",
            generator=mock_generator_fn,
            source_files=["src/main.py"],
        )

        # Should generate since cache file doesn't exist
        assert was_generated is True
        assert "# Generated Content" in page.content


class TestModulePageProcessing:
    """Tests for module page processing (lines 373-374)."""

    @pytest.fixture
    def setup_generator(self, tmp_path):
        """Create a WikiGenerator for module tests."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                yield generator, tmp_path

    async def test_module_pages_written(self, setup_generator):
        """Test module pages are appended and written (lines 373-374)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(repo_path=str(tmp_path))

        # Create module pages that will be returned
        module_page1 = WikiPage(
            path="modules/core.md",
            title="Core Module",
            content="# Core Module",
            generated_at=time.time(),
        )
        module_page2 = WikiPage(
            path="modules/utils.md",
            title="Utils Module",
            content="# Utils Module",
            generated_at=time.time(),
        )

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs"
                ) as mock_modules:
                    # Return module pages with gen_count
                    mock_modules.return_value = ([module_page1, module_page2], 2, 0)

                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Module pages should be in result
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "modules/core.md"
                                                                            in paths
                                                                        )
                                                                        assert (
                                                                            "modules/utils.md"
                                                                            in paths
                                                                        )

                                                                        # Module files should be written
                                                                        assert (
                                                                            tmp_path
                                                                            / "modules"
                                                                            / "core.md"
                                                                        ).exists()
                                                                        assert (
                                                                            tmp_path
                                                                            / "modules"
                                                                            / "utils.md"
                                                                        ).exists()


class TestChangelogPageGeneration:
    """Tests for changelog page generation (lines 470-473)."""

    @pytest.fixture
    def setup_generator(self, tmp_path):
        """Create a WikiGenerator for changelog tests."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                yield generator, tmp_path

    async def test_changelog_page_generated(self, setup_generator):
        """Test changelog page is added when generated (lines 470-473)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(repo_path=str(tmp_path))

        changelog_page = WikiPage(
            path="changelog.md",
            title="Changelog",
            content="# Changelog\n\n## v1.0.0\n- Initial release",
            generated_at=time.time(),
        )

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                "local_deepwiki.generators.wiki.generate_changelog_page"
                            ) as mock_changelog:
                                # Return a changelog page
                                mock_changelog.return_value = changelog_page

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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Changelog should be in result
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "changelog.md"
                                                                            in paths
                                                                        )

                                                                        # Changelog file should be written
                                                                        changelog_file = (
                                                                            tmp_path
                                                                            / "changelog.md"
                                                                        )
                                                                        assert changelog_file.exists()
                                                                        assert (
                                                                            "# Changelog"
                                                                            in changelog_file.read_text()
                                                                        )


class TestAuxiliaryPagesGeneration:
    """Tests for auxiliary pages (inheritance, glossary, coverage) - lines 494-537."""

    @pytest.fixture
    def setup_generator(self, tmp_path):
        """Create a WikiGenerator for auxiliary page tests."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                yield generator, tmp_path

    async def test_inheritance_page_generated(self, setup_generator):
        """Test inheritance page is added when content is generated (lines 494-503)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(repo_path=str(tmp_path))

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                    "local_deepwiki.generators.wiki.generate_inheritance_page"
                                ) as mock_inheritance:
                                    # Return content for inheritance page
                                    mock_inheritance.return_value = "# Class Inheritance\n\nBaseClass -> DerivedClass"

                                    with patch(
                                        "local_deepwiki.generators.wiki.generate_glossary_page",
                                        return_value=None,
                                    ):
                                        with patch(
                                            "local_deepwiki.generators.wiki.generate_coverage_page",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Inheritance should be in result
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "inheritance.md"
                                                                            in paths
                                                                        )

                                                                        # File should be written
                                                                        assert (
                                                                            tmp_path
                                                                            / "inheritance.md"
                                                                        ).exists()

    async def test_glossary_page_generated(self, setup_generator):
        """Test glossary page is added when content is generated (lines 511-520)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(repo_path=str(tmp_path))

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                        "local_deepwiki.generators.wiki.generate_glossary_page"
                                    ) as mock_glossary:
                                        # Return content for glossary page
                                        mock_glossary.return_value = "# Glossary\n\n**API** - Application Programming Interface"

                                        with patch(
                                            "local_deepwiki.generators.wiki.generate_coverage_page",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Glossary should be in result
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "glossary.md"
                                                                            in paths
                                                                        )

                                                                        # File should be written
                                                                        assert (
                                                                            tmp_path
                                                                            / "glossary.md"
                                                                        ).exists()

    async def test_coverage_page_generated(self, setup_generator):
        """Test coverage page is added when content is generated (lines 528-537)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(repo_path=str(tmp_path))

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                            "local_deepwiki.generators.wiki.generate_coverage_page"
                                        ) as mock_coverage:
                                            # Return content for coverage page
                                            mock_coverage.return_value = "# Documentation Coverage\n\n80% documented"

                                            with patch(
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # Coverage should be in result
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "coverage.md"
                                                                            in paths
                                                                        )

                                                                        # File should be written
                                                                        assert (
                                                                            tmp_path
                                                                            / "coverage.md"
                                                                        ).exists()

    async def test_all_auxiliary_pages_generated(self, setup_generator):
        """Test all auxiliary pages are generated when content is returned."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(repo_path=str(tmp_path))

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
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
                                "local_deepwiki.generators.wiki.generate_changelog_page"
                            ) as mock_changelog:
                                mock_changelog.return_value = WikiPage(
                                    path="changelog.md",
                                    title="Changelog",
                                    content="# Changelog",
                                    generated_at=time.time(),
                                )

                                with patch(
                                    "local_deepwiki.generators.wiki.generate_inheritance_page"
                                ) as mock_inheritance:
                                    mock_inheritance.return_value = (
                                        "# Class Inheritance"
                                    )

                                    with patch(
                                        "local_deepwiki.generators.wiki.generate_glossary_page"
                                    ) as mock_glossary:
                                        mock_glossary.return_value = "# Glossary"

                                        with patch(
                                            "local_deepwiki.generators.wiki.generate_coverage_page"
                                        ) as mock_coverage:
                                            mock_coverage.return_value = (
                                                "# Documentation Coverage"
                                            )

                                            with patch(
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=True,
                                                                        )

                                                                        # All auxiliary pages should be in result
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "changelog.md"
                                                                            in paths
                                                                        )
                                                                        assert (
                                                                            "inheritance.md"
                                                                            in paths
                                                                        )
                                                                        assert (
                                                                            "glossary.md"
                                                                            in paths
                                                                        )
                                                                        assert (
                                                                            "coverage.md"
                                                                            in paths
                                                                        )

                                                                        # All files should be written
                                                                        assert (
                                                                            tmp_path
                                                                            / "changelog.md"
                                                                        ).exists()
                                                                        assert (
                                                                            tmp_path
                                                                            / "inheritance.md"
                                                                        ).exists()
                                                                        assert (
                                                                            tmp_path
                                                                            / "glossary.md"
                                                                        ).exists()
                                                                        assert (
                                                                            tmp_path
                                                                            / "coverage.md"
                                                                        ).exists()


class TestDependenciesIncrementalLogic:
    """Tests for dependencies page incremental logic (lines 433-448)."""

    @pytest.fixture
    def setup_generator(self, tmp_path):
        """Create a WikiGenerator for dependencies tests."""
        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                mock_llm.return_value = MagicMock()

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store._get_table.return_value = None
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                yield generator, tmp_path

    async def test_dependencies_cached_incremental(self, setup_generator):
        """Test dependencies page is loaded from cache in incremental mode (lines 433-448)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py", hash="same_hash")],
        )

        # Create cached dependencies file
        (tmp_path / "dependencies.md").write_text("# Cached Dependencies\nOld content")
        (tmp_path / "index.md").write_text("# Cached Overview")
        (tmp_path / "architecture.md").write_text("# Cached Architecture")

        # Set up previous status so dependencies page is NOT regenerated
        from local_deepwiki.models import WikiGenerationStatus, WikiPageStatus

        prev_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=3,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="abc",
                    generated_at=1000.0,
                ),
                "architecture.md": WikiPageStatus(
                    path="architecture.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="def",
                    generated_at=1000.0,
                ),
                "dependencies.md": WikiPageStatus(
                    path="dependencies.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="ghi",
                    generated_at=2000.0,
                ),
            },
        )
        generator.status_manager._previous_status = prev_status
        generator.status_manager.file_hashes = {"src/main.py": "same_hash"}

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="New Overview",
                content="# New",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="New Arch",
                    content="# New Arch",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
                    ):
                        with patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page"
                        ) as mock_deps:
                            mock_deps.return_value = (
                                WikiPage(
                                    path="dependencies.md",
                                    title="New Dependencies",
                                    content="# New Dependencies",
                                    generated_at=time.time(),
                                ),
                                ["src/main.py"],
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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        result = await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=False,  # Incremental mode
                                                                        )

                                                                        # Dependencies page should NOT be regenerated
                                                                        assert (
                                                                            mock_deps.call_count
                                                                            == 0
                                                                        )

                                                                        # Dependencies page should be in result (loaded from cache)
                                                                        paths = [
                                                                            p.path
                                                                            for p in result.pages
                                                                        ]
                                                                        assert (
                                                                            "dependencies.md"
                                                                            in paths
                                                                        )

    async def test_dependencies_regenerated_when_file_missing(self, setup_generator):
        """Test dependencies page regenerated when cache file is missing (lines 434-436)."""
        generator, tmp_path = setup_generator

        index_status = make_index_status(
            repo_path=str(tmp_path),
            files=[make_file_info(path="src/main.py", hash="same_hash")],
        )

        # Create other cached files but NOT dependencies.md
        (tmp_path / "index.md").write_text("# Cached Overview")
        (tmp_path / "architecture.md").write_text("# Cached Architecture")
        # dependencies.md is intentionally NOT created

        from local_deepwiki.models import WikiGenerationStatus, WikiPageStatus

        prev_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=3,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="abc",
                    generated_at=1000.0,
                ),
                "architecture.md": WikiPageStatus(
                    path="architecture.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="def",
                    generated_at=1000.0,
                ),
                "dependencies.md": WikiPageStatus(
                    path="dependencies.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    content_hash="ghi",
                    generated_at=2000.0,
                ),
            },
        )
        generator.status_manager._previous_status = prev_status
        generator.status_manager.file_hashes = {"src/main.py": "same_hash"}

        with patch(
            "local_deepwiki.generators.wiki.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generate_file_docs",
                        return_value=([], 0, 0),
                    ):
                        with patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page"
                        ) as mock_deps:
                            mock_deps.return_value = (
                                WikiPage(
                                    path="dependencies.md",
                                    title="Generated Dependencies",
                                    content="# Generated Dependencies",
                                    generated_at=time.time(),
                                ),
                                ["src/main.py"],
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
                                                "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki_postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.get_cached_manifest"
                                                                    ):
                                                                        await generator.generate(
                                                                            index_status=index_status,
                                                                            full_rebuild=False,
                                                                        )

                                                                        # Dependencies SHOULD be regenerated because file doesn't exist
                                                                        assert (
                                                                            mock_deps.call_count
                                                                            == 1
                                                                        )


class TestCacheStatisticsLogging:
    """Tests for LLM cache statistics logging in wiki generation."""

    @pytest.mark.asyncio
    async def test_logs_cache_stats_when_available(self, tmp_path):
        """Test that cache statistics are logged when LLM provider has stats."""
        from contextlib import ExitStack

        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.max_file_docs = 0
            config.wiki.import_search_limit = 10
            config.wiki.max_concurrent_llm_calls = 1
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                # Create mock LLM with proper stats
                llm_mock = MagicMock()
                llm_mock.stats = {"hits": 5, "misses": 10, "skipped": 2}
                llm_mock.generate = AsyncMock(return_value="Generated content")
                mock_llm.return_value = llm_mock

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.embedding_provider = MagicMock()
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                index_status = make_index_status(
                    repo_path=str(tmp_path),
                    total_files=0,
                    total_chunks=0,
                    files=[],
                )

                # Use ExitStack to avoid too many nested with blocks
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "load_status",
                            new_callable=AsyncMock,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "save_status",
                            new_callable=AsyncMock,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "needs_regeneration",
                            return_value=True,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "load_existing_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )

                    mock_overview = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_overview_page",
                            new_callable=AsyncMock,
                        )
                    )
                    mock_overview.return_value = WikiPage(
                        path="index.md",
                        title="Overview",
                        content="# Overview",
                        generated_at=time.time(),
                    )

                    mock_arch = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_architecture_page",
                            new_callable=AsyncMock,
                        )
                    )
                    mock_arch.return_value = WikiPage(
                        path="architecture.md",
                        title="Architecture",
                        content="# Architecture",
                        generated_at=time.time(),
                    )

                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_module_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_file_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )

                    mock_deps = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page",
                            new_callable=AsyncMock,
                        )
                    )
                    deps_page = WikiPage(
                        path="dependencies.md",
                        title="Dependencies",
                        content="# Dependencies",
                        generated_at=time.time(),
                    )
                    mock_deps.return_value = (deps_page, [])

                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_changelog_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_inheritance_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_glossary_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_coverage_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                            side_effect=lambda p, _, __: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                            return_value=[],
                        )
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki_postprocessing.write_toc")
                    )

                    mock_stale = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.generate_stale_report_page"
                        )
                    )
                    mock_stale.return_value = WikiPage(
                        path="freshness.md",
                        title="Freshness",
                        content="# Fresh",
                        generated_at=time.time(),
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki.get_cached_manifest")
                    )

                    # Capture logger calls
                    mock_logger = stack.enter_context(
                        patch("local_deepwiki.generators.wiki.logger")
                    )

                    await generator.generate(
                        index_status=index_status,
                        full_rebuild=True,
                    )

                    # Check that cache stats were logged
                    info_calls = [str(call) for call in mock_logger.info.call_args_list]
                    cache_stats_logged = any(
                        "LLM cache stats" in call for call in info_calls
                    )
                    assert cache_stats_logged, (
                        f"Cache stats not logged. Calls: {info_calls}"
                    )

                    # Verify the specific stats were included
                    stats_call = [
                        call for call in info_calls if "LLM cache stats" in call
                    ][0]
                    assert "5 hits" in stats_call
                    assert "10 misses" in stats_call
                    assert "33.3%" in stats_call

    @pytest.mark.asyncio
    async def test_handles_mock_stats_gracefully(self, tmp_path):
        """Test that mock stats (non-integer) are handled gracefully."""
        from contextlib import ExitStack

        with patch("local_deepwiki.generators.wiki.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.max_file_docs = 0
            config.wiki.import_search_limit = 10
            config.wiki.max_concurrent_llm_calls = 1
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.get_cached_llm_provider"
            ) as mock_llm:
                # Create mock LLM with MagicMock stats (simulates test mocking)
                llm_mock = MagicMock()
                # stats returns MagicMock by default, which caused the original failure
                llm_mock.generate = AsyncMock(return_value="Generated content")
                mock_llm.return_value = llm_mock

                from local_deepwiki.generators.wiki import WikiGenerator

                mock_vector_store = MagicMock()
                mock_vector_store.search = AsyncMock(return_value=[])
                mock_vector_store.embedding_provider = MagicMock()
                mock_vector_store.get_main_definition_lines.return_value = {}

                generator = WikiGenerator(
                    wiki_path=tmp_path,
                    vector_store=mock_vector_store,
                )

                index_status = make_index_status(
                    repo_path=str(tmp_path),
                    total_files=0,
                    total_chunks=0,
                    files=[],
                )

                # Use ExitStack to avoid too many nested with blocks
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "load_status",
                            new_callable=AsyncMock,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "save_status",
                            new_callable=AsyncMock,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "needs_regeneration",
                            return_value=True,
                        )
                    )
                    stack.enter_context(
                        patch.object(
                            generator.status_manager,
                            "load_existing_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )

                    mock_overview = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_overview_page",
                            new_callable=AsyncMock,
                        )
                    )
                    mock_overview.return_value = WikiPage(
                        path="index.md",
                        title="Overview",
                        content="# Overview",
                        generated_at=time.time(),
                    )

                    mock_arch = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_architecture_page",
                            new_callable=AsyncMock,
                        )
                    )
                    mock_arch.return_value = WikiPage(
                        path="architecture.md",
                        title="Architecture",
                        content="# Architecture",
                        generated_at=time.time(),
                    )

                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_module_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_file_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )

                    mock_deps = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_dependencies_page",
                            new_callable=AsyncMock,
                        )
                    )
                    deps_page = WikiPage(
                        path="dependencies.md",
                        title="Dependencies",
                        content="# Dependencies",
                        generated_at=time.time(),
                    )
                    mock_deps.return_value = (deps_page, [])

                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_changelog_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_inheritance_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_glossary_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generate_coverage_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.add_cross_links",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.add_source_refs_sections",
                            side_effect=lambda p, _, __: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.add_see_also_sections",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.write_full_search_index"
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.generate_toc",
                            return_value=[],
                        )
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki_postprocessing.write_toc")
                    )

                    mock_stale = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki_postprocessing.generate_stale_report_page"
                        )
                    )
                    mock_stale.return_value = WikiPage(
                        path="freshness.md",
                        title="Freshness",
                        content="# Fresh",
                        generated_at=time.time(),
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki.get_cached_manifest")
                    )

                    # Should not raise an exception (mock stats are handled gracefully)
                    result = await generator.generate(
                        index_status=index_status,
                        full_rebuild=True,
                    )

                    # Should complete successfully
                    assert result is not None
                    assert len(result.pages) > 0
