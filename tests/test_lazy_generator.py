"""Tests for lazy wiki page generator."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import make_file_info, make_index_status
from local_deepwiki.generators.crosslinks import EntityRegistry
from local_deepwiki.generators.lazy_generator import (
    LazyPageGenerator,
    _extract_cross_link_targets,
    _lazy_generators,
    get_active_generators,
    get_lazy_generator,
)
from local_deepwiki.generators.lazy_resources import LazyResourceManager
from local_deepwiki.models import WikiPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wiki_dir(tmp_path: Path, repo_path: str = "/repo") -> Path:
    """Create a minimal wiki directory with index_status.json."""
    wiki = tmp_path / ".deepwiki"
    wiki.mkdir(parents=True)
    files = [
        make_file_info("src/main.py", chunk_count=5),
        make_file_info("src/utils.py", chunk_count=3),
    ]
    idx = make_index_status(repo_path, total_files=2, files=files)
    (wiki / "index_status.json").write_text(idx.model_dump_json())
    return wiki


def _make_generator(wiki_path: Path) -> LazyPageGenerator:
    """Create a LazyPageGenerator with eager mode (no prefetch)."""
    config = MagicMock()
    config.wiki.generation_mode = "eager"
    config.wiki.prefetch_workers = 0
    config.wiki.max_file_docs = 0
    gen = LazyPageGenerator.__new__(LazyPageGenerator)
    gen._wiki_path = wiki_path
    gen._config = config
    gen._resources = LazyResourceManager(wiki_path, config)
    gen._auxiliary_cache = None
    gen._in_flight = {}
    gen._prefetch = None
    return gen


# ---------------------------------------------------------------------------
# TestLazyPageGenerator
# ---------------------------------------------------------------------------


class TestLazyPageGenerator:
    """Tests for LazyPageGenerator core behaviour."""

    def test_read_cached_returns_existing_page(self, tmp_path: Path) -> None:
        from local_deepwiki.generators.lazy_cache import read_cached_page

        wiki = _make_wiki_dir(tmp_path)
        _make_generator(wiki)

        (wiki / "index.md").write_text("# Overview")

        result = read_cached_page(wiki, "index.md")
        assert result == "# Overview"

    def test_read_cached_returns_none_for_missing(self, tmp_path: Path) -> None:
        from local_deepwiki.generators.lazy_cache import read_cached_page

        wiki = _make_wiki_dir(tmp_path)
        _make_generator(wiki)

        result = read_cached_page(wiki, "nonexistent.md")
        assert result is None

    async def test_get_page_returns_cached(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)
        (wiki / "index.md").write_text("# Cached content")

        content = await gen.get_page("index.md")
        assert content == "# Cached content"

    async def test_get_page_generates_and_caches(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        test_page = WikiPage(
            path="index.md",
            title="Overview",
            content="# Generated overview",
            generated_at=time.time(),
        )
        gen._generate_page = AsyncMock(return_value=test_page)
        gen._resources.get_cross_linker = AsyncMock(
            return_value=MagicMock(add_links=lambda p: p)
        )

        content = await gen.get_page("index.md")

        assert content == "# Generated overview"
        assert (wiki / "index.md").read_text() == "# Generated overview"
        gen._generate_page.assert_awaited_once_with("index.md")

    async def test_get_page_deduplicates_concurrent_requests(
        self, tmp_path: Path
    ) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        call_count = 0

        async def slow_generate(path: str) -> WikiPage:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return WikiPage(
                path=path,
                title="Test",
                content="# Content",
                generated_at=time.time(),
            )

        gen._generate_page = slow_generate
        gen._resources.get_cross_linker = AsyncMock(
            return_value=MagicMock(add_links=lambda p: p)
        )

        results = await asyncio.gather(
            gen.get_page("index.md"),
            gen.get_page("index.md"),
        )

        assert results[0] == "# Content"
        assert results[1] == "# Content"
        assert call_count == 1

    async def test_get_page_propagates_errors(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        gen._generate_page = AsyncMock(side_effect=RuntimeError("generation failed"))

        with pytest.raises(RuntimeError, match="generation failed"):
            await gen.get_page("index.md")

        assert "index.md" not in gen._in_flight

    def test_get_virtual_structure_with_index(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        structure = gen.get_virtual_structure()

        assert "pages" in structure
        assert "sections" in structure
        page_paths = {p["path"] for p in structure["pages"]}
        assert "index.md" in page_paths
        assert "architecture.md" in page_paths

    def test_get_virtual_structure_without_index(self, tmp_path: Path) -> None:
        wiki = tmp_path / ".deepwiki"
        wiki.mkdir()
        gen = _make_generator(wiki)

        with pytest.raises(Exception):
            gen.get_virtual_structure()

    async def test_warm_page_populates_cache(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        test_page = WikiPage(
            path="architecture.md",
            title="Arch",
            content="# Architecture",
            generated_at=time.time(),
        )
        gen._generate_page = AsyncMock(return_value=test_page)
        gen._resources.get_cross_linker = AsyncMock(
            return_value=MagicMock(add_links=lambda p: p)
        )

        await gen.warm_page("architecture.md")

        assert (wiki / "architecture.md").read_text() == "# Architecture"

    async def test_warm_page_swallows_errors(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)
        gen._generate_page = AsyncMock(side_effect=RuntimeError("fail"))

        await gen.warm_page("bad.md")


# ---------------------------------------------------------------------------
# TestGenerateModule
# ---------------------------------------------------------------------------


class TestGenerateModule:
    async def test_generate_modules_index(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        vs = MagicMock()
        page = await gen._generate_module("modules/index.md", vs)
        assert page.path == "modules/index.md"

    async def test_generate_module_no_files_raises(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        vs = MagicMock()
        with pytest.raises(FileNotFoundError, match="No files for module"):
            await gen._generate_module("modules/nonexistent.md", vs)

    @patch(
        "local_deepwiki.generators.lazy_generator.generate_single_module_doc",
        new_callable=AsyncMock,
    )
    async def test_generate_module_calls_single_module_doc(
        self, mock_gen: AsyncMock, tmp_path: Path
    ) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        mock_page = WikiPage(
            path="modules/src.md",
            title="Module: src",
            content="# src module",
            generated_at=time.time(),
        )
        mock_gen.return_value = mock_page

        gen._resources.get_llm = MagicMock(return_value=MagicMock())
        gen._resources.get_system_prompt = MagicMock(return_value="system prompt")

        vs = MagicMock()
        page = await gen._generate_module("modules/src.md", vs)

        assert page.title == "Module: src"
        mock_gen.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestGenerateFile
# ---------------------------------------------------------------------------


class TestGenerateFile:
    async def test_generate_files_index(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        gen = _make_generator(wiki)

        vs = MagicMock()
        page = gen._generate_files_index_page()
        assert page.path == "files/index.md"
        assert page.title == "Source Files"


# ---------------------------------------------------------------------------
# TestGetLazyGenerator
# ---------------------------------------------------------------------------


class TestGetLazyGenerator:
    def setup_method(self) -> None:
        _lazy_generators.clear()

    def teardown_method(self) -> None:
        _lazy_generators.clear()

    def test_singleton_per_wiki_path(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        config = MagicMock()
        config.wiki.generation_mode = "eager"
        config.wiki.prefetch_workers = 0

        gen1 = get_lazy_generator(wiki, config)
        gen2 = get_lazy_generator(wiki, config)

        assert gen1 is gen2

    def test_different_paths_different_instances(self, tmp_path: Path) -> None:
        wiki1 = _make_wiki_dir(tmp_path / "a")
        wiki2 = _make_wiki_dir(tmp_path / "b")
        config = MagicMock()
        config.wiki.generation_mode = "eager"
        config.wiki.prefetch_workers = 0

        gen1 = get_lazy_generator(wiki1, config)
        gen2 = get_lazy_generator(wiki2, config)

        assert gen1 is not gen2


# ---------------------------------------------------------------------------
# TestGetActiveGenerators
# ---------------------------------------------------------------------------


class TestGetActiveGenerators:
    def setup_method(self) -> None:
        _lazy_generators.clear()

    def teardown_method(self) -> None:
        _lazy_generators.clear()

    def test_returns_module_level_dict(self) -> None:
        result = get_active_generators()
        assert result is _lazy_generators

    def test_reflects_registered_generators(self, tmp_path: Path) -> None:
        wiki = _make_wiki_dir(tmp_path)
        config = MagicMock()
        config.wiki.generation_mode = "eager"
        config.wiki.prefetch_workers = 0

        gen = get_lazy_generator(wiki, config)

        active = get_active_generators()
        assert str(wiki.resolve()) in active
        assert active[str(wiki.resolve())] is gen


# ---------------------------------------------------------------------------
# TestExtractCrossLinkTargets
# ---------------------------------------------------------------------------


class TestExtractCrossLinkTargets:
    def test_extracts_simple_links(self) -> None:
        content = "See [overview](index.md) and [arch](architecture.md)."
        targets = _extract_cross_link_targets(content)
        assert set(targets) == {"index.md", "architecture.md"}

    def test_normalizes_relative_paths(self) -> None:
        content = "See [file](../files/main.md) and [mod](../../modules/src.md)."
        targets = _extract_cross_link_targets(content)
        assert "files/main.md" in targets
        assert "modules/src.md" in targets

    def test_returns_empty_for_no_links(self) -> None:
        content = "No links here."
        targets = _extract_cross_link_targets(content)
        assert targets == []


# ---------------------------------------------------------------------------
# TestAppendToSearchIndex
# ---------------------------------------------------------------------------


class TestAppendToSearchIndex:
    def test_creates_new_index(self, tmp_path: Path) -> None:
        from local_deepwiki.generators.lazy_cache import append_to_search_index

        wiki = _make_wiki_dir(tmp_path)
        _make_generator(wiki)
        page = WikiPage(
            path="test.md", title="Test", content="# Test", generated_at=time.time()
        )

        append_to_search_index(wiki, page)

        idx_path = wiki / "search_index.json"
        assert idx_path.exists()
        entries = json.loads(idx_path.read_text())
        assert len(entries) == 1
        assert entries[0]["path"] == "test.md"

    def test_appends_to_existing_index(self, tmp_path: Path) -> None:
        from local_deepwiki.generators.lazy_cache import append_to_search_index

        wiki = _make_wiki_dir(tmp_path)
        _make_generator(wiki)
        (wiki / "search_index.json").write_text(
            json.dumps([{"path": "old.md", "title": "Old", "summary": ""}])
        )
        page = WikiPage(
            path="new.md", title="New", content="# New", generated_at=time.time()
        )

        append_to_search_index(wiki, page)

        entries = json.loads((wiki / "search_index.json").read_text())
        assert len(entries) == 2
