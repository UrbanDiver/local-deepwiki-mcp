"""Tests for WikiPipelineContext frozen dataclass."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import make_index_status, make_wiki_ctx
from local_deepwiki.generators.wiki.context import WikiPipelineContext


class TestWikiPipelineContext:
    """Tests for WikiPipelineContext construction and immutability."""

    def test_construction_with_defaults(self):
        """Test context can be constructed with default values."""
        ctx = make_wiki_ctx()
        assert ctx.full_rebuild is False
        assert ctx.max_chunk_content_chars == 15000
        assert ctx.manifest is None

    def test_construction_with_overrides(self):
        """Test context respects overridden values."""
        manifest = MagicMock()
        ctx = make_wiki_ctx(
            full_rebuild=True,
            max_chunk_content_chars=5000,
            manifest=manifest,
        )
        assert ctx.full_rebuild is True
        assert ctx.max_chunk_content_chars == 5000
        assert ctx.manifest is manifest

    def test_frozen_raises_on_mutation(self):
        """Test that assigning to a frozen field raises FrozenInstanceError."""
        ctx = make_wiki_ctx()
        with pytest.raises(FrozenInstanceError):
            ctx.full_rebuild = True  # type: ignore[misc]

    def test_frozen_raises_on_system_prompt_mutation(self):
        """Test mutating system_prompt raises FrozenInstanceError."""
        ctx = make_wiki_ctx()
        with pytest.raises(FrozenInstanceError):
            ctx.system_prompt = "new prompt"  # type: ignore[misc]

    def test_frozen_raises_on_repo_path_mutation(self):
        """Test mutating repo_path raises FrozenInstanceError."""
        ctx = make_wiki_ctx()
        with pytest.raises(FrozenInstanceError):
            ctx.repo_path = Path("/other")  # type: ignore[misc]

    def test_stores_all_fields(self):
        """Test all fields are accessible after construction."""
        mock_is = MagicMock()
        mock_vs = MagicMock()
        mock_llm = MagicMock()
        mock_config = MagicMock()
        mock_wc = MagicMock()
        mock_sm = MagicMock()
        mock_manifest = MagicMock()

        ctx = WikiPipelineContext(
            index_status=mock_is,
            vector_store=mock_vs,
            llm=mock_llm,
            system_prompt="prompt",
            repo_path=Path("/repo"),
            wiki_path=Path("/wiki"),
            config=mock_config,
            wiki_config=mock_wc,
            manifest=mock_manifest,
            status_manager=mock_sm,
            full_rebuild=True,
            max_chunk_content_chars=8000,
        )

        assert ctx.index_status is mock_is
        assert ctx.vector_store is mock_vs
        assert ctx.llm is mock_llm
        assert ctx.system_prompt == "prompt"
        assert ctx.repo_path == Path("/repo")
        assert ctx.wiki_path == Path("/wiki")
        assert ctx.config is mock_config
        assert ctx.wiki_config is mock_wc
        assert ctx.manifest is mock_manifest
        assert ctx.status_manager is mock_sm
        assert ctx.full_rebuild is True
        assert ctx.max_chunk_content_chars == 8000


class TestContextDrivenGeneration:
    """Tests that page generators work correctly when called via ctx."""

    async def test_overview_page_via_ctx(self, tmp_path):
        """Test generate_overview_page works when called with ctx only."""
        from local_deepwiki.generators.wiki.pages import generate_overview_page

        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value="## Description\n\nTest.\n\n## Key Features\n\n- F1"
        )
        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=[])

        ctx = make_wiki_ctx(
            index_status=make_index_status(repo_path=str(repo_path)),
            vector_store=mock_vs,
            llm=mock_llm,
            system_prompt="You are a docs expert.",
            repo_path=repo_path,
        )

        result = await generate_overview_page(ctx)

        assert result.path == "index.md"
        assert result.title == "Overview"
        assert "test-repo" in result.content

    async def test_architecture_page_via_ctx(self, tmp_path):
        """Test generate_architecture_page works when called with ctx only."""
        from local_deepwiki.generators.wiki.pages import generate_architecture_page

        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value="## System Overview\n\nArchitecture."
        )
        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=[])

        ctx = make_wiki_ctx(
            index_status=make_index_status(repo_path=str(repo_path)),
            vector_store=mock_vs,
            llm=mock_llm,
            system_prompt="You are an architect.",
            repo_path=repo_path,
        )

        result = await generate_architecture_page(ctx)

        assert result.path == "architecture.md"
        assert result.title == "Architecture"

    async def test_module_docs_via_ctx(self, tmp_path):
        """Test generate_module_docs works when called with ctx only."""
        from conftest import make_file_info
        from local_deepwiki.generators.wiki.modules import generate_module_docs

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="## Module docs")

        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=[])
        mock_vs.get_chunks_by_file = AsyncMock(return_value=[])

        mock_sm = MagicMock()
        mock_sm.needs_regeneration = MagicMock(return_value=True)
        mock_sm.needs_regeneration_structural = MagicMock(return_value=True)
        mock_sm.load_existing_page = AsyncMock(return_value=None)
        mock_sm.record_page_status = MagicMock()
        mock_sm.record_summary_page_status = MagicMock()

        ctx = make_wiki_ctx(
            index_status=make_index_status(
                repo_path=str(tmp_path),
                files=[
                    make_file_info(path="src/a.py"),
                    make_file_info(path="src/b.py"),
                ],
            ),
            vector_store=mock_vs,
            llm=mock_llm,
            system_prompt="System prompt",
            status_manager=mock_sm,
            full_rebuild=True,
        )

        pages, generated, skipped = await generate_module_docs(ctx)

        # No relevant chunks found -> no pages generated
        assert pages == []
        assert generated == 0

    async def test_dependencies_page_via_ctx(self, tmp_path):
        """Test generate_dependencies_page works when called with ctx only."""
        from unittest.mock import patch

        from local_deepwiki.generators.wiki.pages import generate_dependencies_page

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="## External Dependencies\n\nNone")
        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(return_value=[])

        ctx = make_wiki_ctx(
            index_status=make_index_status(repo_path=str(tmp_path / "project")),
            vector_store=mock_vs,
            llm=mock_llm,
            system_prompt="Deps expert",
        )

        with patch(
            "local_deepwiki.generators.diagrams.generate_dependency_graph"
        ) as mock_graph:
            mock_graph.return_value = ""

            page, source_files = await generate_dependencies_page(
                ctx, import_search_limit=100
            )

        assert page.path == "dependencies.md"
        assert isinstance(source_files, list)
