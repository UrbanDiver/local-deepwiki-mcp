"""Tests for the interactive codemap web UI functionality."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.web.app import _MODULE_DIR, create_app


@pytest.fixture
def wiki_dir():
    """Create a temporary wiki directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        (wiki_path / "index.md").write_text("# Home\n")
        yield wiki_path


class TestCodemapPage:
    """Tests for the /codemap page."""

    def test_codemap_page_renders(self, wiki_dir):
        """Test that the codemap page renders successfully."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"DeepWiki Codemap" in response.data

    def test_codemap_page_has_query_input(self, wiki_dir):
        """Test that the codemap page has required input elements."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b'id="query-input"' in response.data
        assert b'id="generate-btn"' in response.data
        assert b'id="focus-select"' in response.data
        assert b'id="depth-input"' in response.data
        assert b'id="nodes-input"' in response.data

    def test_codemap_page_has_cytoscape_script(self, wiki_dir):
        """Test that the codemap page loads Cytoscape.js from CDN."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"cytoscape" in response.data
        assert b"dagre" in response.data

    def test_codemap_page_has_focus_options(self, wiki_dir):
        """Test that all three focus modes are available."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"execution_flow" in response.data
        assert b"data_flow" in response.data
        assert b"dependency_chain" in response.data

    def test_codemap_page_has_graph_container(self, wiki_dir):
        """Test that the page has a Cytoscape container."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b'id="cy"' in response.data

    def test_codemap_page_has_narrative_panel(self, wiki_dir):
        """Test that the page has the narrative panel."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"narrative-panel" in response.data
        assert b"Narrative Trace" in response.data


class TestCodemapTemplate:
    """Tests for the codemap template file."""

    def test_codemap_template_exists(self):
        """Test that the codemap.html template exists."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        assert template_path.exists()
        assert template_path.is_file()

    def test_codemap_template_has_theme_toggle(self):
        """Test that the template has theme support."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="theme-toggle"' in content
        assert "data-theme" in content


class TestApiCodemap:
    """Tests for the /api/codemap endpoint."""

    def test_api_codemap_requires_query(self, wiki_dir):
        """Test that /api/codemap returns error for missing query."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post("/api/codemap", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "required" in data["error"].lower()

    def test_api_codemap_rejects_empty_query(self, wiki_dir):
        """Test that /api/codemap rejects empty/whitespace query."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post("/api/codemap", json={"query": ""})
        assert response.status_code == 400

        response = client.post("/api/codemap", json={"query": "   "})
        assert response.status_code == 400

    def test_api_codemap_validates_focus(self, wiki_dir):
        """Test that /api/codemap validates focus mode."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/codemap",
            json={"query": "test", "focus": "invalid_mode"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid focus mode" in data["error"]

    def test_api_codemap_accepts_valid_focus(self, wiki_dir):
        """Test that /api/codemap accepts all valid focus modes."""
        app = create_app(wiki_dir)
        client = app.test_client()

        for focus in ["execution_flow", "data_flow", "dependency_chain"]:
            response = client.post(
                "/api/codemap",
                json={"query": "test", "focus": focus},
            )
            # Should not be a 400 for focus validation
            assert (
                response.status_code != 400
                or "focus" not in response.get_json().get("error", "").lower()
            )

    def test_api_codemap_validates_depth_range(self, wiki_dir):
        """Test that /api/codemap validates max_depth bounds."""
        app = create_app(wiki_dir)
        client = app.test_client()

        # Too low
        response = client.post(
            "/api/codemap",
            json={"query": "test", "max_depth": 0},
        )
        assert response.status_code == 400
        assert "max_depth" in response.get_json()["error"]

        # Too high
        response = client.post(
            "/api/codemap",
            json={"query": "test", "max_depth": 11},
        )
        assert response.status_code == 400

    def test_api_codemap_validates_nodes_range(self, wiki_dir):
        """Test that /api/codemap validates max_nodes bounds."""
        app = create_app(wiki_dir)
        client = app.test_client()

        # Too low
        response = client.post(
            "/api/codemap",
            json={"query": "test", "max_nodes": 4},
        )
        assert response.status_code == 400
        assert "max_nodes" in response.get_json()["error"]

        # Too high
        response = client.post(
            "/api/codemap",
            json={"query": "test", "max_nodes": 61},
        )
        assert response.status_code == 400

    def test_api_codemap_returns_sse(self, wiki_dir):
        """Test that /api/codemap returns SSE content type."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/codemap",
            json={"query": "test query"},
        )
        assert response.content_type.startswith("text/event-stream")

    def test_api_codemap_sse_has_error_for_unindexed(self, wiki_dir):
        """Test that /api/codemap returns error event for unindexed repo."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/codemap",
            json={"query": "test query"},
        )
        assert response.status_code == 200
        data = response.data.decode()
        # Should contain an error about not being indexed
        assert "not indexed" in data.lower() or "error" in data.lower()

    def test_api_codemap_default_values(self, wiki_dir):
        """Test that /api/codemap uses sensible defaults."""
        app = create_app(wiki_dir)
        client = app.test_client()

        # Just query, defaults for everything else
        response = client.post(
            "/api/codemap",
            json={"query": "test"},
        )
        # Should not fail on validation (defaults are within bounds)
        assert response.content_type.startswith("text/event-stream")


class TestApiCodemapTopics:
    """Tests for the /api/codemap/topics endpoint."""

    def test_api_topics_returns_json(self, wiki_dir):
        """Test that /api/codemap/topics returns JSON."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/api/codemap/topics")
        assert response.status_code == 200
        assert response.content_type.startswith("application/json")

    def test_api_topics_returns_array(self, wiki_dir):
        """Test that /api/codemap/topics returns a JSON array."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/api/codemap/topics")
        data = response.get_json()
        assert isinstance(data, list)

    def test_api_topics_graceful_for_unindexed(self, wiki_dir):
        """Test that topics returns empty array when repo not indexed."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/api/codemap/topics")
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestCodemapNavigation:
    """Tests for codemap navigation links."""

    def test_page_template_has_codemap_link(self, wiki_dir):
        """Test that page.html has a link to /codemap."""
        template_path = _MODULE_DIR / "templates" / "page.html"
        content = template_path.read_text()
        assert 'href="/codemap"' in content

    def test_chat_template_has_codemap_link(self):
        """Test that chat.html has a link to /codemap."""
        template_path = _MODULE_DIR / "templates" / "chat.html"
        content = template_path.read_text()
        assert 'href="/codemap"' in content

    def test_codemap_page_has_back_links(self, wiki_dir):
        """Test that codemap page has links back to wiki and chat."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b'href="/"' in response.data
        assert b'href="/chat"' in response.data


class TestApiCodemapWithMockedGenerator:
    """Tests for /api/codemap with mocked codemap generator."""

    def _make_mock_result(self):
        """Create a mock CodemapResult-like object."""
        return MagicMock(
            query="test query",
            focus="execution_flow",
            entry_point="module.main",
            mermaid_diagram="flowchart TD\n    A-->B",
            narrative="Step 1: Call main()\nStep 2: Call helper()",
            nodes=[
                {
                    "name": "main",
                    "qualified_name": "module.main",
                    "file_path": "src/module.py",
                    "start_line": 1,
                    "end_line": 10,
                    "chunk_type": "function",
                },
                {
                    "name": "helper",
                    "qualified_name": "module.helper",
                    "file_path": "src/module.py",
                    "start_line": 12,
                    "end_line": 20,
                    "chunk_type": "function",
                },
            ],
            edges=[
                {
                    "source": "module.main",
                    "target": "module.helper",
                    "edge_type": "calls",
                    "source_file": "src/module.py",
                    "target_file": "src/module.py",
                },
            ],
            files_involved=["src/module.py"],
            total_nodes=2,
            total_edges=1,
            cross_file_edges=0,
        )

    @patch("local_deepwiki.web.app.WIKI_PATH")
    def test_api_codemap_streams_result(self, mock_wiki_path, wiki_dir):
        """Test that codemap SSE stream contains a result event."""
        mock_wiki_path.__bool__ = lambda self: True
        mock_wiki_path.parent = wiki_dir
        mock_wiki_path.name = ".deepwiki"

        mock_result = self._make_mock_result()

        with (
            patch(
                "local_deepwiki.generators.codemap.generate_codemap",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch("local_deepwiki.config.get_config") as mock_config,
            patch("local_deepwiki.providers.embeddings.get_embedding_provider"),
            patch("local_deepwiki.core.vectorstore.VectorStore"),
            patch("local_deepwiki.providers.llm.get_cached_llm_provider"),
        ):
            config = MagicMock()
            config.get_vector_db_path.return_value = wiki_dir / "vectors"
            (wiki_dir / "vectors").mkdir()
            config.get_wiki_path.return_value = wiki_dir
            config.wiki.chat_llm_provider = "default"
            mock_config.return_value = config

            app = create_app(wiki_dir)
            client = app.test_client()

            response = client.post(
                "/api/codemap",
                json={"query": "test query"},
            )

            assert response.status_code == 200
            assert response.content_type.startswith("text/event-stream")

            data = response.data.decode()
            # Should contain progress and result events
            assert "progress" in data
            assert "result" in data or "error" in data
