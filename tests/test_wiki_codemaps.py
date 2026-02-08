"""Tests for wiki codemap page generation."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.codemap import CodemapResult
from local_deepwiki.generators.wiki_codemaps import (
    _format_codemap_index,
    _format_codemap_page,
    _topic_slug,
    generate_codemap_pages,
)


# ---------------------------------------------------------------------------
# _topic_slug
# ---------------------------------------------------------------------------


class TestTopicSlug:
    def test_simple_name(self):
        assert _topic_slug("generate") == "generate"

    def test_dotted_name(self):
        assert _topic_slug("WikiGenerator.generate") == "wikigenerator-generate"

    def test_underscored_name(self):
        assert _topic_slug("handle_request") == "handle-request"

    def test_dunder_name(self):
        assert _topic_slug("__main__") == "main"

    def test_special_chars(self):
        assert _topic_slug("foo@bar!baz") == "foo-bar-baz"

    def test_long_name_truncated(self):
        long_name = "a" * 200
        assert len(_topic_slug(long_name)) == 80

    def test_empty_string(self):
        assert _topic_slug("") == "unnamed"

    def test_all_special_chars(self):
        assert _topic_slug("@#$%") == "unnamed"


# ---------------------------------------------------------------------------
# _format_codemap_page
# ---------------------------------------------------------------------------


class TestFormatCodemapPage:
    def _make_result(self, **overrides):
        defaults = {
            "query": "How does handle_request work?",
            "focus": "execution_flow",
            "entry_point": "handle_request",
            "mermaid_diagram": "flowchart TD\n    A --> B",
            "narrative": "Step 1: A calls B.",
            "nodes": [{"name": "A"}, {"name": "B"}],
            "edges": [{"source": "A", "target": "B"}],
            "files_involved": ["src/handler.py", "src/utils.py"],
            "total_nodes": 5,
            "total_edges": 4,
            "cross_file_edges": 2,
        }
        defaults.update(overrides)
        return CodemapResult(**defaults)

    def test_contains_title(self):
        topic = {"entry_point": "handle_request", "file_path": "src/handler.py"}
        result = self._make_result()
        page = _format_codemap_page(topic, result)
        assert "# Codemap: How handle_request Works" in page

    def test_contains_mermaid_block(self):
        topic = {"entry_point": "handle_request", "file_path": "src/handler.py"}
        result = self._make_result()
        page = _format_codemap_page(topic, result)
        assert "```mermaid" in page
        assert "flowchart TD" in page

    def test_contains_stats_table(self):
        topic = {"entry_point": "handle_request", "file_path": "src/handler.py"}
        result = self._make_result()
        page = _format_codemap_page(topic, result)
        assert "| Nodes | 5 |" in page
        assert "| Edges | 4 |" in page
        assert "| Cross-file edges | 2 |" in page
        assert "| Files involved | 2 |" in page

    def test_contains_narrative(self):
        topic = {"entry_point": "handle_request", "file_path": "src/handler.py"}
        result = self._make_result()
        page = _format_codemap_page(topic, result)
        assert "Step 1: A calls B." in page

    def test_files_involved_links(self):
        topic = {"entry_point": "handle_request", "file_path": "src/handler.py"}
        result = self._make_result()
        page = _format_codemap_page(topic, result)
        assert "[`src/handler.py`](../files/handler.md)" in page
        assert "[`src/utils.py`](../files/utils.md)" in page

    def test_entry_point_in_blockquote(self):
        topic = {"entry_point": "handle_request", "file_path": "src/handler.py"}
        result = self._make_result()
        page = _format_codemap_page(topic, result)
        assert "> Entry point: `handle_request` in `src/handler.py`" in page


# ---------------------------------------------------------------------------
# _format_codemap_index
# ---------------------------------------------------------------------------


class TestFormatCodemapIndex:
    def test_empty_topics(self):
        content = _format_codemap_index([])
        assert "# Codemaps" in content
        assert "*No codemaps were generated" in content
        assert "| Entry Point" not in content

    def test_single_topic(self):
        topics = [
            {
                "entry_point": "main",
                "file_path": "src/main.py",
                "reason": "Hub function with 10 connections",
            }
        ]
        content = _format_codemap_index(topics)
        assert "| [main](main.md)" in content
        assert "`src/main.py`" in content
        assert "Hub function with 10 connections" in content

    def test_multiple_topics(self):
        topics = [
            {"entry_point": "foo", "file_path": "a.py", "reason": "r1"},
            {"entry_point": "bar", "file_path": "b.py", "reason": "r2"},
            {"entry_point": "baz", "file_path": "c.py", "reason": "r3"},
            {"entry_point": "qux", "file_path": "d.py", "reason": "r4"},
            {"entry_point": "quux", "file_path": "e.py", "reason": "r5"},
        ]
        content = _format_codemap_index(topics)
        assert content.count("| [") == 5


# ---------------------------------------------------------------------------
# generate_codemap_pages (async integration)
# ---------------------------------------------------------------------------


def _make_wiki_config(**overrides):
    """Create a mock WikiConfig with codemap settings."""
    defaults = {
        "codemap_enabled": True,
        "codemap_max_topics": 5,
        "codemap_max_depth": 4,
        "codemap_max_nodes": 30,
    }
    defaults.update(overrides)
    config = MagicMock()
    for k, v in defaults.items():
        setattr(config, k, v)
    return config


def _make_codemap_result(total_nodes=5, **overrides):
    defaults = {
        "query": "How does handle_request work?",
        "focus": "execution_flow",
        "entry_point": "handle_request",
        "mermaid_diagram": "flowchart TD\n    A --> B",
        "narrative": "Step 1: A calls B.",
        "nodes": [{"name": f"n{i}"} for i in range(total_nodes)],
        "edges": [{"source": "A", "target": "B"}],
        "files_involved": ["src/handler.py"],
        "total_nodes": total_nodes,
        "total_edges": 1,
        "cross_file_edges": 0,
    }
    defaults.update(overrides)
    return CodemapResult(**defaults)


def _make_topic(entry_point="handle_request", file_path="src/handler.py"):
    return {
        "topic": f"How {entry_point} works",
        "entry_point": entry_point,
        "file_path": file_path,
        "reason": "Hub function with 10 connections",
        "suggested_query": f"How does {entry_point} work?",
    }


class TestGenerateCodemapPages:
    @pytest.fixture
    def status_manager(self):
        mgr = MagicMock()
        mgr.needs_regeneration.return_value = True
        mgr.load_existing_page = AsyncMock(return_value=None)
        mgr.record_page_status = MagicMock()
        return mgr

    async def test_disabled_returns_empty(self, status_manager):
        config = _make_wiki_config(codemap_enabled=False)
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=Path("/wiki"),
            status_manager=status_manager,
            config=config,
            full_rebuild=False,
        )
        assert pages == []
        assert gen == 0
        assert skip == 0

    async def test_zero_max_topics_returns_empty(self, status_manager):
        config = _make_wiki_config(codemap_max_topics=0)
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=Path("/wiki"),
            status_manager=status_manager,
            config=config,
            full_rebuild=False,
        )
        assert pages == []
        assert gen == 0

    @patch("local_deepwiki.generators.wiki_codemaps.generate_codemap")
    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_generates_pages_and_index(
        self, mock_suggest, mock_codemap, status_manager, tmp_path
    ):
        mock_suggest.return_value = [_make_topic("foo", "a.py")]
        mock_codemap.return_value = _make_codemap_result()

        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        # 1 codemap page + 1 index page
        assert len(pages) == 2
        assert gen == 2
        assert skip == 0
        # Index page is last
        assert pages[-1].path == "codemaps/index.md"
        assert pages[0].path == "codemaps/foo.md"

    @patch("local_deepwiki.generators.wiki_codemaps.generate_codemap")
    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_skips_trivial_graphs(
        self, mock_suggest, mock_codemap, status_manager, tmp_path
    ):
        mock_suggest.return_value = [_make_topic("tiny", "x.py")]
        mock_codemap.return_value = _make_codemap_result(total_nodes=2)

        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        # Only index page (codemap skipped due to <3 nodes)
        assert len(pages) == 1
        assert pages[0].path == "codemaps/index.md"
        assert gen == 1

    @patch("local_deepwiki.generators.wiki_codemaps.generate_codemap")
    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_incremental_skip(
        self, mock_suggest, mock_codemap, status_manager, tmp_path
    ):
        mock_suggest.return_value = [_make_topic("cached", "c.py")]
        status_manager.needs_regeneration.return_value = False
        existing_page = MagicMock()
        existing_page.path = "codemaps/cached.md"
        existing_page.title = "Codemap: cached"
        existing_page.content = "cached content"
        status_manager.load_existing_page = AsyncMock(return_value=existing_page)

        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=False,
        )
        # Cached page + index
        assert len(pages) == 2
        assert skip == 1
        # generate_codemap should NOT have been called
        mock_codemap.assert_not_called()

    @patch("local_deepwiki.generators.wiki_codemaps.generate_codemap")
    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_error_resilience(
        self, mock_suggest, mock_codemap, status_manager, tmp_path
    ):
        mock_suggest.return_value = [
            _make_topic("good", "a.py"),
            _make_topic("bad", "b.py"),
        ]
        mock_codemap.side_effect = [
            _make_codemap_result(),
            Exception("LLM timeout"),
        ]

        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        # 1 successful codemap + index
        assert len(pages) == 2
        assert gen == 2

    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_no_topics_returns_empty(
        self, mock_suggest, status_manager, tmp_path
    ):
        mock_suggest.return_value = []
        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        assert pages == []
        assert gen == 0
        assert skip == 0

    @patch("local_deepwiki.generators.wiki_codemaps.generate_codemap")
    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_orphan_cleanup(
        self, mock_suggest, mock_codemap, status_manager, tmp_path
    ):
        # Pre-create an orphaned codemap file
        codemaps_dir = tmp_path / "codemaps"
        codemaps_dir.mkdir()
        orphan = codemaps_dir / "old_topic.md"
        orphan.write_text("stale content")

        mock_suggest.return_value = [_make_topic("new_topic", "a.py")]
        mock_codemap.return_value = _make_codemap_result()

        config = _make_wiki_config()
        await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        assert not orphan.exists()

    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_suggest_topics_exception(
        self, mock_suggest, status_manager, tmp_path
    ):
        mock_suggest.side_effect = RuntimeError("vector store error")
        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        assert pages == []
        assert gen == 0

    @patch("local_deepwiki.generators.wiki_codemaps.generate_codemap")
    @patch("local_deepwiki.generators.wiki_codemaps.suggest_topics")
    async def test_multiple_topics(
        self, mock_suggest, mock_codemap, status_manager, tmp_path
    ):
        topics = [_make_topic(f"func_{i}", f"f{i}.py") for i in range(3)]
        mock_suggest.return_value = topics
        mock_codemap.return_value = _make_codemap_result()

        config = _make_wiki_config()
        pages, gen, skip = await generate_codemap_pages(
            vector_store=MagicMock(),
            llm=MagicMock(),
            repo_path=Path("/repo"),
            wiki_path=tmp_path,
            status_manager=status_manager,
            config=config,
            full_rebuild=True,
        )
        # 3 codemap pages + 1 index
        assert len(pages) == 4
        assert gen == 4
