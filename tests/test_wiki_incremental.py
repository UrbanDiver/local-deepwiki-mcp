"""Tests for incremental wiki generation, generate_wiki function, and dependencies logic."""

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

        # Compute the structural fingerprint so summary pages are skipped
        structural_fp = generator.status_manager.compute_structural_fingerprint(
            index_status
        )

        prev_status = WikiGenerationStatus(
            repo_path=str(tmp_path),
            generated_at=time.time(),
            total_pages=3,
            pages={
                "index.md": WikiPageStatus(
                    path="index.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    structural_fingerprint=structural_fp,
                    content_hash="abc",
                    generated_at=time.time(),
                ),
                "architecture.md": WikiPageStatus(
                    path="architecture.md",
                    source_files=["src/main.py"],
                    source_hashes={"src/main.py": "same_hash"},
                    structural_fingerprint=structural_fp,
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
