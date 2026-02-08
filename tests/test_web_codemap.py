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
                    "docstring": "Main entry point for the module.",
                    "content_preview": "def main():\n    helper()",
                },
                {
                    "name": "helper",
                    "qualified_name": "module.helper",
                    "file_path": "src/module.py",
                    "start_line": 12,
                    "end_line": 20,
                    "chunk_type": "function",
                    "docstring": "",
                    "content_preview": "def helper():\n    pass",
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


class TestCodemapPhase2Features:
    """Tests for Phase 2 codemap features."""

    def test_template_has_export_png_button(self):
        """Test that the template has an Export PNG button."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="export-png-btn"' in content
        assert "Export PNG" in content

    def test_template_has_node_tooltip(self):
        """Test that the template has a node tooltip element."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="node-tooltip"' in content
        assert "node-tooltip" in content
        assert "tooltip-name" in content
        assert "tooltip-meta" in content
        assert "tooltip-docstring" in content

    def test_template_has_zoom_controls(self):
        """Test that the template has floating zoom controls."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="zoom-controls"' in content
        assert 'id="zoom-in-btn"' in content
        assert 'id="zoom-out-btn"' in content
        assert 'id="fit-btn"' in content

    def test_template_has_shortcuts_hint(self):
        """Test that the template has keyboard shortcuts hint."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="shortcuts-hint"' in content
        assert "<kbd>" in content
        assert "Esc" in content

    def test_template_has_path_highlighting_styles(self):
        """Test that the template has dimmed/highlighted CSS classes."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "node.dimmed" in content
        assert "edge.dimmed" in content
        assert "node.highlighted" in content
        assert "edge.highlighted" in content

    def test_template_has_edge_label_style(self):
        """Test that the template has edge label Cytoscape style."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "edge[label]" in content
        assert "autorotate" in content

    def test_template_has_bfs_path_finding(self):
        """Test that the template has BFS path finding function."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "findPathFromEntry" in content
        assert "highlightPath" in content
        assert "clearHighlighting" in content

    def test_template_has_url_state_functions(self):
        """Test that the template has URL state preservation functions."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "readUrlState" in content
        assert "updateUrlState" in content
        assert "history.replaceState" in content

    def test_template_has_legend_collapsibility(self):
        """Test that the template has collapsible legend."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "legend.collapsed" in content
        assert "legend-items" in content

    def test_template_has_highlighted_path_legend_item(self):
        """Test that the legend includes a highlighted path entry."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "Highlighted path" in content
        assert "#f0883e" in content

    def test_template_has_export_function(self):
        """Test that the template has PNG export function."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "exportPng" in content
        assert "cy.png" in content

    def test_template_has_double_click_navigation(self):
        """Test that double-click navigates to wiki page."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "dbltap" in content

    def test_template_has_data_flow_edge_labels(self):
        """Test that edge labels are shown in data_flow mode."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "showEdgeLabels" in content or "data_flow" in content
        assert "edgeData.label" in content

    def test_template_has_tooltip_show_hide(self):
        """Test that template has tooltip show/hide functions."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "showTooltip" in content
        assert "hideTooltip" in content
        assert "mouseover" in content
        assert "mouseout" in content

    def test_template_has_keyboard_shortcut_handler(self):
        """Test that template handles keyboard shortcuts."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        # Check for keyboard event handling
        assert "keydown" in content
        # Check for the specific shortcuts
        assert "e.key === 'f'" in content or "e.key === 'F'" in content
        assert "e.key === 'Escape'" in content
        assert "e.key === 'l'" in content or "e.key === 'L'" in content

    def test_codemap_page_has_export_button(self, wiki_dir):
        """Test that the rendered codemap page has the export button."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"export-png-btn" in response.data
        assert b"Export PNG" in response.data

    def test_codemap_page_has_zoom_controls(self, wiki_dir):
        """Test that the rendered codemap page has zoom controls."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"zoom-controls" in response.data
        assert b"zoom-in-btn" in response.data
        assert b"fit-btn" in response.data

    def test_codemap_page_has_tooltip_element(self, wiki_dir):
        """Test that the rendered codemap page has the tooltip div."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"node-tooltip" in response.data

    def test_codemap_page_has_shortcuts_hint(self, wiki_dir):
        """Test that the rendered codemap page has shortcuts hint."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"shortcuts-hint" in response.data


class TestCodemapNodeSerialization:
    """Tests for codemap node serialization with docstring/content_preview."""

    def test_codemap_node_has_docstring_field(self):
        """Test that CodemapNode model has docstring field."""
        from local_deepwiki.generators.codemap import CodemapNode

        node = CodemapNode(
            name="test",
            qualified_name="mod.test",
            file_path="test.py",
            start_line=1,
            end_line=10,
            chunk_type="function",
            docstring="A test function.",
        )
        assert node.docstring == "A test function."

    def test_codemap_node_has_content_preview_field(self):
        """Test that CodemapNode model has content_preview field."""
        from local_deepwiki.generators.codemap import CodemapNode

        node = CodemapNode(
            name="test",
            qualified_name="mod.test",
            file_path="test.py",
            start_line=1,
            end_line=10,
            chunk_type="function",
            content_preview="def test():\n    pass",
        )
        assert node.content_preview == "def test():\n    pass"

    def test_codemap_node_defaults(self):
        """Test that CodemapNode defaults docstring to None and content_preview to empty."""
        from local_deepwiki.generators.codemap import CodemapNode

        node = CodemapNode(
            name="test",
            qualified_name="mod.test",
            file_path="test.py",
            start_line=1,
            end_line=10,
            chunk_type="function",
        )
        assert node.docstring is None
        assert node.content_preview == ""


class TestCodemapPhase3AnimatedTrace:
    """Tests for Phase 3 animated execution trace feature."""

    def test_template_has_play_controls(self):
        """Test that the template has play/pause/step controls."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="play-controls"' in content
        assert 'id="play-btn"' in content
        assert 'id="pause-btn"' in content
        assert 'id="step-btn"' in content
        assert 'id="stop-trace-btn"' in content

    def test_template_has_trace_functions(self):
        """Test that the template has trace animation functions."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "startTrace" in content
        assert "pauseTrace" in content
        assert "stopTrace" in content
        assert "stepTrace" in content
        assert "buildTraceSequence" in content

    def test_template_has_trace_styles(self):
        """Test that the template has Cytoscape styles for trace."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "node.trace-active" in content
        assert "node.trace-visited" in content

    def test_template_has_play_keyboard_shortcut(self):
        """Test that P key triggers play/pause."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "e.key === 'p'" in content or "e.key === 'P'" in content

    def test_codemap_page_has_play_controls(self, wiki_dir):
        """Test that rendered page has play controls."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"play-controls" in response.data
        assert b"play-btn" in response.data


class TestCodemapPhase3DiffOverlay:
    """Tests for Phase 3 git diff overlay feature."""

    def test_template_has_diff_toggle(self):
        """Test that the template has diff toggle checkbox."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="diff-toggle-cb"' in content
        assert "Show Changes" in content

    def test_template_has_diff_overlay_styles(self):
        """Test that the template has diff-changed Cytoscape styles."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "node.diff-changed" in content
        assert "#f85149" in content

    def test_template_has_diff_overlay_functions(self):
        """Test that the template has diff overlay functions."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "loadDiffFiles" in content
        assert "applyDiffOverlay" in content
        assert "removeDiffOverlay" in content

    def test_api_diff_returns_json(self, wiki_dir):
        """Test that /api/codemap/diff returns JSON."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/api/codemap/diff")
        assert response.status_code == 200
        assert response.content_type.startswith("application/json")
        data = response.get_json()
        assert "changed_files" in data

    def test_api_diff_validates_refs(self, wiki_dir):
        """Test that /api/codemap/diff validates git refs."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/api/codemap/diff?base_ref=;rm+-rf")
        assert response.status_code == 400

    def test_api_diff_accepts_valid_refs(self, wiki_dir):
        """Test that /api/codemap/diff accepts valid git refs."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/api/codemap/diff?base_ref=HEAD~3&head_ref=HEAD")
        assert response.status_code == 200


class TestCodemapPhase3Minimap:
    """Tests for Phase 3 minimap feature."""

    def test_template_has_minimap_container(self):
        """Test that the template has a minimap container."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="cy-minimap"' in content

    def test_template_has_minimap_function(self):
        """Test that the template has minimap initialization function."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "initMinimap" in content
        assert "navigator" in content

    def test_template_loads_navigator_extension(self):
        """Test that the template loads cytoscape-navigator CDN."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "cytoscape-navigator" in content

    def test_codemap_page_has_minimap_element(self, wiki_dir):
        """Test that rendered page has minimap div."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"cy-minimap" in response.data


class TestCodemapPhase3Cache:
    """Tests for Phase 3 persistent codemap cache feature."""

    def test_api_cache_returns_json(self, wiki_dir):
        """Test that /api/codemap/cache returns JSON array."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/api/codemap/cache")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_api_cache_validates_key(self, wiki_dir):
        """Test that /api/codemap/cache validates cache key format."""
        app = create_app(wiki_dir)
        client = app.test_client()
        # Invalid key (injection attempt)
        response = client.get("/api/codemap/cache?key=../../../etc/passwd")
        assert response.status_code == 400

    def test_api_cache_returns_404_for_missing(self, wiki_dir):
        """Test that /api/codemap/cache returns 404 for nonexistent key."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/api/codemap/cache?key=deadbeef12345678")
        assert response.status_code == 404

    def test_template_has_recent_codemaps(self):
        """Test that the template has recent codemaps section."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert 'id="recent-codemaps"' in content
        assert "loadRecentCodemaps" in content

    def test_template_has_cache_load_function(self):
        """Test that the template has cache loading function."""
        template_path = _MODULE_DIR / "templates" / "codemap.html"
        content = template_path.read_text()
        assert "loadCachedCodemap" in content

    def test_cache_write_and_read(self, wiki_dir):
        """Test cache write and read round-trip."""
        from local_deepwiki.generators.codemap_cache import (
            cache_key,
            read_cache,
            write_cache,
        )

        key = cache_key("test query", "execution_flow", 5, 30)
        result = {
            "query": "test query",
            "focus": "execution_flow",
            "total_nodes": 3,
            "total_edges": 2,
        }
        write_cache(wiki_dir, key, result)
        cached = read_cache(wiki_dir, key)
        assert cached is not None
        assert cached["query"] == "test query"
        assert cached["total_nodes"] == 3

    def test_cache_key_deterministic(self):
        """Test that cache key is deterministic."""
        from local_deepwiki.generators.codemap_cache import cache_key

        k1 = cache_key("test", "execution_flow", 5, 30)
        k2 = cache_key("test", "execution_flow", 5, 30)
        assert k1 == k2

    def test_cache_key_varies_with_params(self):
        """Test that cache key changes with different params."""
        from local_deepwiki.generators.codemap_cache import cache_key

        k1 = cache_key("test", "execution_flow", 5, 30)
        k2 = cache_key("test", "data_flow", 5, 30)
        k3 = cache_key("different", "execution_flow", 5, 30)
        assert k1 != k2
        assert k1 != k3


class TestCodemapPhase3Compare:
    """Tests for Phase 3 multi-codemap comparison feature."""

    def test_compare_page_renders(self, wiki_dir):
        """Test that /codemap/compare renders successfully."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap/compare")
        assert response.status_code == 200
        assert b"Codemap Compare" in response.data

    def test_compare_page_has_two_panes(self, wiki_dir):
        """Test that comparison page has two pane containers."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap/compare")
        assert response.status_code == 200
        assert b'id="pane-left"' in response.data
        assert b'id="pane-right"' in response.data

    def test_compare_page_has_query_inputs(self, wiki_dir):
        """Test that comparison page has query inputs for both panes."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap/compare")
        assert response.status_code == 200
        assert b'id="query-left"' in response.data
        assert b'id="query-right"' in response.data

    def test_compare_page_has_generate_buttons(self, wiki_dir):
        """Test that comparison page has generate buttons for both panes."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap/compare")
        assert response.status_code == 200
        assert b'id="gen-left"' in response.data
        assert b'id="gen-right"' in response.data

    def test_compare_page_has_cytoscape(self, wiki_dir):
        """Test that comparison page loads Cytoscape.js."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap/compare")
        assert response.status_code == 200
        assert b"cytoscape" in response.data
        assert b"dagre" in response.data

    def test_compare_template_exists(self):
        """Test that codemap_compare.html template exists."""
        template_path = _MODULE_DIR / "templates" / "codemap_compare.html"
        assert template_path.exists()

    def test_codemap_page_has_compare_link(self, wiki_dir):
        """Test that codemap page links to comparison view."""
        app = create_app(wiki_dir)
        client = app.test_client()
        response = client.get("/codemap")
        assert response.status_code == 200
        assert b"/codemap/compare" in response.data
