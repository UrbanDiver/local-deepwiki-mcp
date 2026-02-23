"""Tests for WikiGenerator init, definition lines, generate method, and cache statistics."""

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
        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
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
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
            "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
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
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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


class TestWikiGeneratorGenerate:
    """Tests for WikiGenerator.generate method."""

    @pytest.fixture
    def mock_generator(self, tmp_path):
        """Create a mocked WikiGenerator."""
        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.import_search_limit = 100
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
            "local_deepwiki.generators.wiki.generator.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generator.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Architecture",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generator.generate_module_docs"
                ) as mock_modules:
                    mock_modules.return_value = ([], 0, 0)

                    with patch(
                        "local_deepwiki.generators.wiki.generator.generate_file_docs"
                    ) as mock_files:
                        mock_files.return_value = ([], 0, 0)

                        with patch(
                            "local_deepwiki.generators.wiki.generator.generate_dependencies_page"
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
                                "local_deepwiki.generators.wiki.generator.generate_changelog_page"
                            ) as mock_changelog:
                                mock_changelog.return_value = None

                                with patch(
                                    "local_deepwiki.generators.wiki.generator.generate_inheritance_page"
                                ) as mock_inheritance:
                                    mock_inheritance.return_value = None

                                    with patch(
                                        "local_deepwiki.generators.wiki.generator.generate_glossary_page"
                                    ) as mock_glossary:
                                        mock_glossary.return_value = None

                                        with patch(
                                            "local_deepwiki.generators.wiki.generator.generate_coverage_page"
                                        ) as mock_coverage:
                                            mock_coverage.return_value = None

                                            with patch(
                                                "local_deepwiki.generators.wiki.postprocessing.add_cross_links"
                                            ) as mock_crosslinks:
                                                mock_crosslinks.side_effect = (
                                                    lambda pages, _: pages
                                                )

                                                with patch(
                                                    "local_deepwiki.generators.wiki.postprocessing.add_source_refs_sections"
                                                ) as mock_refs:
                                                    mock_refs.side_effect = (
                                                        lambda pages, _, __: pages
                                                    )

                                                    with patch(
                                                        "local_deepwiki.generators.wiki.postprocessing.add_see_also_sections"
                                                    ) as mock_see_also:
                                                        mock_see_also.side_effect = (
                                                            lambda pages, _: pages
                                                        )

                                                        with patch(
                                                            "local_deepwiki.generators.wiki.postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki.postprocessing.generate_toc"
                                                            ) as mock_toc:
                                                                mock_toc.return_value = []

                                                                with patch(
                                                                    "local_deepwiki.generators.wiki.postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.generator.get_cached_manifest"
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
            "local_deepwiki.generators.wiki.generator.generate_overview_page"
        ) as mock_overview:
            mock_overview.return_value = WikiPage(
                path="index.md",
                title="Overview",
                content="# Overview",
                generated_at=time.time(),
            )

            with patch(
                "local_deepwiki.generators.wiki.generator.generate_architecture_page"
            ) as mock_arch:
                mock_arch.return_value = WikiPage(
                    path="architecture.md",
                    title="Architecture",
                    content="# Arch",
                    generated_at=time.time(),
                )

                with patch(
                    "local_deepwiki.generators.wiki.generator.generate_module_docs",
                    return_value=([], 0, 0),
                ):
                    with patch(
                        "local_deepwiki.generators.wiki.generator.generate_file_docs",
                        return_value=([], 0, 0),
                    ):
                        with patch(
                            "local_deepwiki.generators.wiki.generator.generate_dependencies_page"
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
                                "local_deepwiki.generators.wiki.generator.generate_changelog_page",
                                return_value=None,
                            ):
                                with patch(
                                    "local_deepwiki.generators.wiki.generator.generate_inheritance_page",
                                    return_value=None,
                                ):
                                    with patch(
                                        "local_deepwiki.generators.wiki.generator.generate_glossary_page",
                                        return_value=None,
                                    ):
                                        with patch(
                                            "local_deepwiki.generators.wiki.generator.generate_coverage_page",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "local_deepwiki.generators.wiki.postprocessing.add_cross_links",
                                                side_effect=lambda p, _: p,
                                            ):
                                                with patch(
                                                    "local_deepwiki.generators.wiki.postprocessing.add_source_refs_sections",
                                                    side_effect=lambda p, _, __: p,
                                                ):
                                                    with patch(
                                                        "local_deepwiki.generators.wiki.postprocessing.add_see_also_sections",
                                                        side_effect=lambda p, _: p,
                                                    ):
                                                        with patch(
                                                            "local_deepwiki.generators.wiki.postprocessing.write_full_search_index"
                                                        ):
                                                            with patch(
                                                                "local_deepwiki.generators.wiki.postprocessing.generate_toc",
                                                                return_value=[],
                                                            ):
                                                                with patch(
                                                                    "local_deepwiki.generators.wiki.postprocessing.write_toc"
                                                                ):
                                                                    with patch(
                                                                        "local_deepwiki.generators.wiki.generator.get_cached_manifest"
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


class TestCacheStatisticsLogging:
    """Tests for LLM cache statistics logging in wiki generation."""

    @pytest.mark.asyncio
    async def test_logs_cache_stats_when_available(self, tmp_path):
        """Test that cache statistics are logged when LLM provider has stats."""
        from contextlib import ExitStack

        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.max_file_docs = 0
            config.wiki.import_search_limit = 10
            config.wiki.max_concurrent_llm_calls = 1
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
                            "local_deepwiki.generators.wiki.generator.generate_overview_page",
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
                            "local_deepwiki.generators.wiki.generator.generate_architecture_page",
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
                            "local_deepwiki.generators.wiki.generator.generate_module_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_file_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )

                    mock_deps = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_dependencies_page",
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
                            "local_deepwiki.generators.wiki.generator.generate_changelog_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_inheritance_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_glossary_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_coverage_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.add_cross_links",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.add_source_refs_sections",
                            side_effect=lambda p, _, __: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.add_see_also_sections",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.write_full_search_index"
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.generate_toc",
                            return_value=[],
                        )
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki.postprocessing.write_toc")
                    )

                    mock_stale = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.generate_stale_report_page"
                        )
                    )
                    mock_stale.return_value = WikiPage(
                        path="freshness.md",
                        title="Freshness",
                        content="# Fresh",
                        generated_at=time.time(),
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki.generator.get_cached_manifest")
                    )

                    # Capture logger calls
                    mock_logger = stack.enter_context(
                        patch("local_deepwiki.generators.wiki.generator.logger")
                    )

                    await generator.generate(
                        index_status=index_status,
                        full_rebuild=True,
                    )

                    # Check that cache stats were logged (lazy % formatting)
                    cache_stats_call = None
                    for call in mock_logger.info.call_args_list:
                        args = call[0]
                        if args and "LLM cache stats" in str(args[0]):
                            cache_stats_call = args
                            break

                    assert cache_stats_call is not None, (
                        f"Cache stats not logged. Calls: {mock_logger.info.call_args_list}"
                    )

                    # Verify the specific stats were included as arguments
                    # Format: ("LLM cache stats: %d hits, %d misses, %d skipped (%.1f%% hit rate)", hits, misses, skipped, hit_rate)
                    formatted = cache_stats_call[0] % cache_stats_call[1:]
                    assert "5 hits" in formatted
                    assert "10 misses" in formatted
                    assert "33.3%" in formatted

    @pytest.mark.asyncio
    async def test_handles_mock_stats_gracefully(self, tmp_path):
        """Test that mock stats (non-integer) are handled gracefully."""
        from contextlib import ExitStack

        with patch("local_deepwiki.generators.wiki.generator.get_config") as mock_config:
            config = MagicMock()
            config.llm = MagicMock()
            config.wiki = MagicMock()
            config.wiki.max_file_docs = 0
            config.wiki.import_search_limit = 10
            config.wiki.max_concurrent_llm_calls = 1
            config.get_prompts.return_value = MagicMock(wiki_system="System prompt")
            mock_config.return_value = config

            with patch(
                "local_deepwiki.generators.wiki.generator.get_cached_llm_provider"
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
                            "local_deepwiki.generators.wiki.generator.generate_overview_page",
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
                            "local_deepwiki.generators.wiki.generator.generate_architecture_page",
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
                            "local_deepwiki.generators.wiki.generator.generate_module_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_file_docs",
                            new_callable=AsyncMock,
                            return_value=([], 0, 0),
                        )
                    )

                    mock_deps = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_dependencies_page",
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
                            "local_deepwiki.generators.wiki.generator.generate_changelog_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_inheritance_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_glossary_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.generator.generate_coverage_page",
                            new_callable=AsyncMock,
                            return_value=None,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.add_cross_links",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.add_source_refs_sections",
                            side_effect=lambda p, _, __: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.add_see_also_sections",
                            side_effect=lambda p, _: p,
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.write_full_search_index"
                        )
                    )
                    stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.generate_toc",
                            return_value=[],
                        )
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki.postprocessing.write_toc")
                    )

                    mock_stale = stack.enter_context(
                        patch(
                            "local_deepwiki.generators.wiki.postprocessing.generate_stale_report_page"
                        )
                    )
                    mock_stale.return_value = WikiPage(
                        path="freshness.md",
                        title="Freshness",
                        content="# Fresh",
                        generated_at=time.time(),
                    )
                    stack.enter_context(
                        patch("local_deepwiki.generators.wiki.generator.get_cached_manifest")
                    )

                    # Should not raise an exception (mock stats are handled gracefully)
                    result = await generator.generate(
                        index_status=index_status,
                        full_rebuild=True,
                    )

                    # Should complete successfully
                    assert result is not None
                    assert len(result.pages) > 0
