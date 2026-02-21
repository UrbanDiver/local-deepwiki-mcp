"""Tests for page writing, module pages, changelog, and auxiliary pages generation."""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


class TestArchitecturePageAuthoritativeDocs:
    """Tests for architecture page authoritative docs inclusion."""

    async def test_architecture_prompt_includes_authoritative_docs(self, tmp_path):
        """Verify LLM prompt contains authoritative doc content when CLAUDE.md exists."""
        from local_deepwiki.generators.wiki_pages import generate_architecture_page

        # Create a CLAUDE.md in the repo
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nThis project does amazing things.")

        index_status = make_index_status(repo_path=str(tmp_path))

        # Mock vector store with some search results
        mock_chunk = MagicMock()
        mock_chunk.file_path = "src/main.py"
        mock_chunk.chunk_type = MagicMock()
        mock_chunk.chunk_type.value = "class"
        mock_chunk.name = "MainClass"
        mock_chunk.content = "class MainClass:\n    pass"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk
        mock_result.score = 0.9

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        captured_prompt = {}

        async def capture_generate(prompt, **kwargs):
            captured_prompt["prompt"] = prompt
            return "# Architecture\n\nContent here"

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=capture_generate)

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=None,
            repo_path=tmp_path,
        )

        # The authoritative docs should appear in the prompt
        assert "AUTHORITATIVE PROJECT DOCUMENTATION" in captured_prompt["prompt"]
        assert "This project does amazing things" in captured_prompt["prompt"]

    async def test_architecture_prompt_no_authoritative_docs_when_missing(
        self, tmp_path
    ):
        """Verify prompt has no authoritative section when no docs exist."""
        from local_deepwiki.generators.wiki_pages import generate_architecture_page

        index_status = make_index_status(repo_path=str(tmp_path))

        mock_chunk = MagicMock()
        mock_chunk.file_path = "src/main.py"
        mock_chunk.chunk_type = MagicMock()
        mock_chunk.chunk_type.value = "function"
        mock_chunk.name = "main"
        mock_chunk.content = "def main(): pass"

        mock_result = MagicMock()
        mock_result.chunk = mock_chunk
        mock_result.score = 0.8

        mock_vector_store = MagicMock()
        mock_vector_store.search = AsyncMock(return_value=[mock_result])

        captured_prompt = {}

        async def capture_generate(prompt, **kwargs):
            captured_prompt["prompt"] = prompt
            return "# Architecture\n\nContent here"

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=capture_generate)

        await generate_architecture_page(
            index_status=index_status,
            vector_store=mock_vector_store,
            llm=mock_llm,
            system_prompt="You are a documentation expert.",
            manifest=None,
            repo_path=tmp_path,
        )

        assert "AUTHORITATIVE PROJECT DOCUMENTATION" not in captured_prompt["prompt"]
