"""Tests for the web UI functionality."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.web.app import (
    _MODULE_DIR,
    WIKI_PATH,
    app,
    build_breadcrumb,
    build_prompt_with_history,
    create_app,
    extract_title,
    format_sources,
    get_wiki_structure,
    render_markdown,
)


@pytest.fixture
def wiki_dir():
    """Create a temporary wiki directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)

        # Create root pages
        (wiki_path / "index.md").write_text("# Home\n")
        (wiki_path / "architecture.md").write_text("# Architecture\n")

        # Create modules section with index
        modules_dir = wiki_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "index.md").write_text("# Modules\n")
        (modules_dir / "src.md").write_text("# Source Code\n")

        # Create files section with nested structure
        files_dir = wiki_path / "files"
        files_dir.mkdir()
        (files_dir / "index.md").write_text("# Files\n")

        # Create deeply nested structure (no index.md at intermediate levels)
        nested_dir = files_dir / "src" / "core"
        nested_dir.mkdir(parents=True)
        (nested_dir / "parser.md").write_text("# Parser\n")

        yield wiki_path


class TestBuildBreadcrumb:
    """Tests for build_breadcrumb function."""

    def test_root_page_no_breadcrumb(self, wiki_dir):
        """Root pages should have no breadcrumb."""
        result = build_breadcrumb(wiki_dir, "index.md")
        assert result == ""

        result = build_breadcrumb(wiki_dir, "architecture.md")
        assert result == ""

    def test_simple_nested_page(self, wiki_dir):
        """Pages one level deep should show Home > Section > Page."""
        result = build_breadcrumb(wiki_dir, "modules/src.md")

        # Should contain Home link
        assert '<a href="/">Home</a>' in result

        # Should contain link to modules/index.md since it exists
        assert '<a href="/wiki/modules/index.md">Modules</a>' in result

        # Should contain current page without link
        assert '<span class="current">Src</span>' in result

        # Should use › as separator
        assert '<span class="separator">›</span>' in result

    def test_deeply_nested_page(self, wiki_dir):
        """Deeply nested pages should show full path."""
        result = build_breadcrumb(wiki_dir, "files/src/core/parser.md")

        # Home link
        assert '<a href="/">Home</a>' in result

        # Files has index.md, should be linked
        assert '<a href="/wiki/files/index.md">Files</a>' in result

        # src and core don't have index.md, should be plain text
        assert "<span>Src</span>" in result
        assert "<span>Core</span>" in result

        # Current page
        assert '<span class="current">Parser</span>' in result

    def test_index_page_in_section(self, wiki_dir):
        """Index pages in sections should show proper breadcrumb."""
        result = build_breadcrumb(wiki_dir, "modules/index.md")

        assert '<a href="/">Home</a>' in result
        # Current page is index
        assert '<span class="current">Index</span>' in result

    def test_formatting_underscores_and_dashes(self, wiki_dir):
        """Underscores and dashes should be replaced with spaces."""
        # Create a page with underscores
        test_dir = wiki_dir / "test_section"
        test_dir.mkdir()
        (test_dir / "my-test-file.md").write_text("# Test\n")

        result = build_breadcrumb(wiki_dir, "test_section/my-test-file.md")

        # Section name should be formatted
        assert "Test Section" in result
        # File name should be formatted
        assert "My Test File" in result


class TestFlaskApp:
    """Tests for Flask app functionality."""

    def test_create_app(self, wiki_dir):
        """Test that create_app initializes correctly."""
        app = create_app(wiki_dir)
        assert app is not None

    def test_create_app_invalid_path(self):
        """Test that create_app raises error for invalid path."""
        with pytest.raises(ValueError, match="does not exist"):
            create_app("/nonexistent/path")

    def test_index_redirect(self, wiki_dir):
        """Test that / redirects to /wiki/index.md."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/")
        assert response.status_code == 302
        assert "/wiki/index.md" in response.location

    def test_view_page(self, wiki_dir):
        """Test viewing a wiki page."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/wiki/index.md")
        assert response.status_code == 200
        assert b"Home" in response.data

    def test_view_nested_page_has_breadcrumb(self, wiki_dir):
        """Test that nested pages display breadcrumbs."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/wiki/modules/src.md")
        assert response.status_code == 200
        # Check for breadcrumb elements
        assert b'class="breadcrumb"' in response.data
        assert b"Modules" in response.data

    def test_404_for_missing_page(self, wiki_dir):
        """Test that missing pages return 404."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/wiki/nonexistent.md")
        assert response.status_code == 404


class TestTemplateConfiguration:
    """Tests for Jinja2 template configuration."""

    def test_template_folder_exists(self):
        """Test that the templates folder exists."""
        template_folder = _MODULE_DIR / "templates"
        assert template_folder.exists()
        assert template_folder.is_dir()

    def test_page_template_exists(self):
        """Test that the page.html template exists."""
        template_path = _MODULE_DIR / "templates" / "page.html"
        assert template_path.exists()
        assert template_path.is_file()

    def test_app_configured_with_template_folder(self):
        """Test that Flask app has correct template folder configured."""
        expected_path = str(_MODULE_DIR / "templates")
        assert app.template_folder == expected_path

    def test_template_contains_required_blocks(self):
        """Test that the template contains essential Jinja2 variables."""
        template_path = _MODULE_DIR / "templates" / "page.html"
        content = template_path.read_text()

        # Check for required template variables
        assert "{{ title }}" in content
        assert "{{ content | safe }}" in content
        assert "{{ breadcrumb | safe }}" in content
        assert "{% if toc_entries %}" in content
        assert "{% for page in pages %}" in content

    def test_template_caching_enabled_in_production(self, wiki_dir):
        """Test that template caching is enabled when debug=False."""
        flask_app = create_app(wiki_dir)

        # When debug is False (default), auto_reload should be False
        # and templates should be cached
        assert flask_app.debug is False
        # jinja_env.auto_reload follows debug setting
        assert flask_app.jinja_env.auto_reload is False

    def test_chat_template_exists(self):
        """Test that the chat.html template exists."""
        template_path = _MODULE_DIR / "templates" / "chat.html"
        assert template_path.exists()
        assert template_path.is_file()


class TestChatEndpoints:
    """Tests for chat functionality."""

    def test_chat_page_renders(self, wiki_dir):
        """Test that the chat page renders successfully."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/chat")
        assert response.status_code == 200
        assert b"DeepWiki Chat" in response.data
        assert b"Ask questions" in response.data

    def test_chat_page_has_input_elements(self, wiki_dir):
        """Test that the chat page has required input elements."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/chat")
        assert response.status_code == 200
        # Check for input elements
        assert b'id="question-input"' in response.data
        assert b'id="send-btn"' in response.data
        assert b'id="research-mode"' in response.data

    def test_api_chat_requires_question(self, wiki_dir):
        """Test that /api/chat returns error for missing question."""
        app = create_app(wiki_dir)
        client = app.test_client()

        # Empty body
        response = client.post("/api/chat", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "required" in data["error"].lower()

        # Empty question
        response = client.post("/api/chat", json={"question": ""})
        assert response.status_code == 400

        # Whitespace only
        response = client.post("/api/chat", json={"question": "   "})
        assert response.status_code == 400

    def test_api_research_requires_question(self, wiki_dir):
        """Test that /api/research returns error for missing question."""
        app = create_app(wiki_dir)
        client = app.test_client()

        # Empty body
        response = client.post("/api/research", json={})
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

        # Empty question
        response = client.post("/api/research", json={"question": ""})
        assert response.status_code == 400

    def test_api_chat_returns_sse(self, wiki_dir):
        """Test that /api/chat returns Server-Sent Events content type."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/chat",
            json={"question": "test question"},
        )
        # Should return SSE or error (no indexed data)
        # We check content type for valid responses
        assert response.content_type.startswith("text/event-stream") or response.status_code == 500

    def test_api_research_returns_sse(self, wiki_dir):
        """Test that /api/research returns Server-Sent Events content type."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/research",
            json={"question": "test question"},
        )
        # Should return SSE or error (no indexed data)
        assert response.content_type.startswith("text/event-stream") or response.status_code == 500

    def test_page_template_has_chat_link(self, wiki_dir):
        """Test that wiki pages have a link to the chat interface."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/wiki/index.md")
        assert response.status_code == 200
        assert b'href="/chat"' in response.data
        assert b"Chat" in response.data


class TestGetWikiStructure:
    """Tests for get_wiki_structure function."""

    def test_returns_pages_and_sections(self, wiki_dir):
        """Test that function returns pages and sections."""
        pages, sections, toc_entries = get_wiki_structure(wiki_dir)

        assert isinstance(pages, list)
        assert isinstance(sections, dict)
        # toc_entries is None when no toc.json
        assert toc_entries is None

        # Should have root pages
        assert len(pages) >= 2
        page_paths = [p["path"] for p in pages]
        assert "index.md" in page_paths
        assert "architecture.md" in page_paths

    def test_loads_toc_json(self, wiki_dir):
        """Test that function loads toc.json when present."""
        # Create toc.json
        toc_data = {
            "entries": [
                {"number": "1", "title": "Overview", "path": "index.md"},
                {"number": "2", "title": "Architecture", "path": "architecture.md"},
            ]
        }
        (wiki_dir / "toc.json").write_text(json.dumps(toc_data))

        pages, sections, toc_entries = get_wiki_structure(wiki_dir)

        assert toc_entries is not None
        assert len(toc_entries) == 2
        assert toc_entries[0]["title"] == "Overview"

    def test_handles_invalid_toc_json(self, wiki_dir):
        """Test that function handles invalid toc.json gracefully."""
        # Create invalid toc.json
        (wiki_dir / "toc.json").write_text("not valid json {{{")

        pages, sections, toc_entries = get_wiki_structure(wiki_dir)

        # Should fall back gracefully
        assert toc_entries is None
        assert len(pages) >= 2

    def test_handles_toc_json_oserror(self, wiki_dir):
        """Test that function handles OSError reading toc.json."""
        # Create a directory with the same name as toc.json
        toc_path = wiki_dir / "toc.json"
        toc_path.mkdir()

        pages, sections, toc_entries = get_wiki_structure(wiki_dir)

        # Should fall back gracefully
        assert toc_entries is None


class TestExtractTitle:
    """Tests for extract_title function."""

    def test_extracts_h1_title(self, wiki_dir):
        """Test extraction of H1 title."""
        md_file = wiki_dir / "test.md"
        md_file.write_text("# My Title\n\nContent here")

        title = extract_title(md_file)
        assert title == "My Title"

    def test_extracts_bold_title(self, wiki_dir):
        """Test extraction of bold-style title."""
        md_file = wiki_dir / "test.md"
        md_file.write_text("**Bold Title**\n\nContent here")

        title = extract_title(md_file)
        assert title == "Bold Title"

    def test_falls_back_to_filename(self, wiki_dir):
        """Test fallback to filename when no title found."""
        md_file = wiki_dir / "my_test_file.md"
        md_file.write_text("No title here, just content")

        title = extract_title(md_file)
        assert title == "My Test File"

    def test_handles_nonexistent_file(self, wiki_dir):
        """Test handling of nonexistent file."""
        md_file = wiki_dir / "nonexistent.md"

        title = extract_title(md_file)
        assert title == "Nonexistent"

    def test_handles_unicode_error(self, wiki_dir):
        """Test handling of unicode decode error."""
        md_file = wiki_dir / "binary.md"
        # Write binary content that can't be decoded as UTF-8
        md_file.write_bytes(b"\xff\xfe")

        title = extract_title(md_file)
        assert title == "Binary"


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_renders_basic_markdown(self):
        """Test rendering basic markdown."""
        content = "# Hello\n\nThis is **bold**."
        html = render_markdown(content)

        assert "<h1" in html  # h1 may have id attribute
        assert "<strong>bold</strong>" in html

    def test_renders_fenced_code(self):
        """Test rendering fenced code blocks."""
        content = "```python\nprint('hello')\n```"
        html = render_markdown(content)

        assert "<code" in html  # code may have class attribute

    def test_renders_tables(self):
        """Test rendering tables."""
        content = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = render_markdown(content)

        assert "<table>" in html
        assert "<td>" in html


class TestSearchEndpoint:
    """Tests for /search.json endpoint."""

    def test_search_json_returns_empty_when_no_file(self, wiki_dir):
        """Test that search.json returns empty list when file doesn't exist."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/search.json")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_search_json_returns_data(self, wiki_dir):
        """Test that search.json returns data when file exists."""
        # Create search.json
        search_data = [
            {"path": "index.md", "title": "Home", "content": "Welcome"},
            {"path": "architecture.md", "title": "Architecture", "content": "Design"},
        ]
        (wiki_dir / "search.json").write_text(json.dumps(search_data))

        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/search.json")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
        assert data[0]["title"] == "Home"

    def test_search_json_handles_invalid_json(self, wiki_dir):
        """Test that search.json handles invalid JSON file."""
        (wiki_dir / "search.json").write_text("invalid json {{{")

        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/search.json")
        assert response.status_code == 500


class TestViewPageErrorHandling:
    """Tests for view_page error handling."""

    def test_view_page_handles_read_error(self, wiki_dir):
        """Test that view_page handles file read errors."""
        # Create a directory with the same name as a md file
        problem_path = wiki_dir / "problem.md"
        problem_path.mkdir()

        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/wiki/problem.md")
        # Should return 404 since it's a directory, not a file
        assert response.status_code == 404


class TestFormatSources:
    """Tests for format_sources function."""

    def test_formats_search_results(self):
        """Test formatting of search results."""
        # Create mock search results using SimpleNamespace for JSON serialization
        mock_chunk = SimpleNamespace(
            file_path="src/test.py",
            start_line=10,
            end_line=20,
            chunk_type=SimpleNamespace(value="function"),
            name="test_func",
        )
        mock_result = SimpleNamespace(chunk=mock_chunk, score=0.95)

        sources = format_sources([mock_result])

        assert len(sources) == 1
        assert sources[0]["file"] == "src/test.py"
        assert sources[0]["lines"] == "10-20"
        assert sources[0]["type"] == "function"
        assert sources[0]["name"] == "test_func"
        assert sources[0]["score"] == 0.95

    def test_formats_multiple_results(self):
        """Test formatting of multiple search results."""
        results = []
        for i in range(3):
            chunk = SimpleNamespace(
                file_path=f"file{i}.py",
                start_line=i * 10,
                end_line=i * 10 + 5,
                chunk_type=SimpleNamespace(value="class"),
                name=f"Class{i}",
            )
            results.append(SimpleNamespace(chunk=chunk, score=0.9 - i * 0.1))

        sources = format_sources(results)

        assert len(sources) == 3
        assert sources[0]["file"] == "file0.py"
        assert sources[2]["file"] == "file2.py"


class TestBuildPromptWithHistory:
    """Tests for build_prompt_with_history function."""

    def test_builds_prompt_without_history(self):
        """Test prompt building without conversation history."""
        prompt = build_prompt_with_history(
            question="What is this?",
            history=[],
            context="def foo(): pass",
        )

        assert "Question: What is this?" in prompt
        assert "def foo(): pass" in prompt
        assert "Previous conversation" not in prompt

    def test_builds_prompt_with_history(self):
        """Test prompt building with conversation history."""
        history = [
            {"question": "What is foo?", "answer": "Foo is a function."},
            {"question": "Where is it used?", "answer": "In module bar."},
        ]

        prompt = build_prompt_with_history(
            question="Can you explain more?",
            history=history,
            context="def foo(): pass",
        )

        assert "Previous conversation" in prompt
        assert "What is foo?" in prompt
        assert "Foo is a function." in prompt
        assert "Current question: Can you explain more?" in prompt

    def test_limits_history_to_last_3(self):
        """Test that only last 3 history items are included."""
        history = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)]

        prompt = build_prompt_with_history(
            question="New question?",
            history=history,
            context="context",
        )

        # Should only include Q7, Q8, Q9 (last 3)
        assert "Q7" in prompt
        assert "Q8" in prompt
        assert "Q9" in prompt
        # Should not include earlier ones
        assert "Q0" not in prompt
        assert "Q5" not in prompt


class TestStreamAsyncGenerator:
    """Tests for stream_async_generator function."""

    def test_streams_items(self):
        """Test that items are streamed correctly."""
        from local_deepwiki.web.app import stream_async_generator

        async def async_gen():
            yield "item1"
            yield "item2"
            yield "item3"

        results = list(stream_async_generator(async_gen))

        assert results == ["item1", "item2", "item3"]

    def test_handles_exception(self):
        """Test that exceptions are handled and reported."""
        from local_deepwiki.web.app import stream_async_generator

        async def failing_gen():
            yield "item1"
            raise ValueError("Test error")

        results = list(stream_async_generator(failing_gen))

        assert len(results) == 2
        assert results[0] == "item1"
        assert "error" in results[1]
        assert "Test error" in results[1]


class TestMainAndRunServer:
    """Tests for main() and run_server() functions."""

    def test_run_server_calls_flask_run(self, wiki_dir):
        """Test that run_server calls Flask's run method."""
        from local_deepwiki.web.app import run_server

        with patch("local_deepwiki.web.app.app") as mock_app:
            mock_app.run = MagicMock()

            # Mock create_app to return our mock
            with patch("local_deepwiki.web.app.create_app", return_value=mock_app):
                run_server(wiki_dir, host="127.0.0.1", port=8080, debug=False)

            mock_app.run.assert_called_once_with(host="127.0.0.1", port=8080, debug=False)

    def test_main_parses_arguments(self):
        """Test that main() parses command line arguments."""
        from local_deepwiki.web.app import main

        with patch("sys.argv", ["deepwiki-serve", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse exits with 0 for --help
            assert exc_info.value.code == 0

    def test_main_calls_run_server(self, wiki_dir):
        """Test that main() calls run_server with parsed arguments."""
        from local_deepwiki.web.app import main

        with patch("sys.argv", ["deepwiki-serve", str(wiki_dir), "--port", "9000"]):
            with patch("local_deepwiki.web.app.run_server") as mock_run:
                main()

                mock_run.assert_called_once()
                call_args = mock_run.call_args
                assert call_args[0][0] == wiki_dir.resolve()
                assert call_args[0][2] == 9000  # port


class TestWikiPathNotConfigured:
    """Tests for endpoints when WIKI_PATH is not configured."""

    def test_search_json_without_wiki_path(self):
        """Test search.json returns error when wiki path not set."""
        import local_deepwiki.web.app as web_app

        # Temporarily set WIKI_PATH to None
        original = web_app.WIKI_PATH
        web_app.WIKI_PATH = None

        try:
            client = app.test_client()
            response = client.get("/search.json")
            assert response.status_code == 500
        finally:
            web_app.WIKI_PATH = original

    def test_view_page_without_wiki_path(self):
        """Test view_page returns error when wiki path not set."""
        import local_deepwiki.web.app as web_app

        original = web_app.WIKI_PATH
        web_app.WIKI_PATH = None

        try:
            client = app.test_client()
            response = client.get("/wiki/index.md")
            assert response.status_code == 500
        finally:
            web_app.WIKI_PATH = original

    def test_chat_page_without_wiki_path(self):
        """Test chat page returns error when wiki path not set."""
        import local_deepwiki.web.app as web_app

        original = web_app.WIKI_PATH
        web_app.WIKI_PATH = None

        try:
            client = app.test_client()
            response = client.get("/chat")
            assert response.status_code == 500
        finally:
            web_app.WIKI_PATH = original

    def test_api_chat_without_wiki_path(self):
        """Test api_chat returns error when wiki path not set."""
        import local_deepwiki.web.app as web_app

        original = web_app.WIKI_PATH
        web_app.WIKI_PATH = None

        try:
            client = app.test_client()
            response = client.post("/api/chat", json={"question": "test"})
            assert response.status_code == 500
        finally:
            web_app.WIKI_PATH = original

    def test_api_research_without_wiki_path(self):
        """Test api_research returns error when wiki path not set."""
        import local_deepwiki.web.app as web_app

        original = web_app.WIKI_PATH
        web_app.WIKI_PATH = None

        try:
            client = app.test_client()
            response = client.post("/api/research", json={"question": "test"})
            assert response.status_code == 500
        finally:
            web_app.WIKI_PATH = original


class TestViewPageReadError:
    """Tests for view_page handling of read errors."""

    def test_view_page_binary_file_error(self, wiki_dir):
        """Test that view_page handles binary file read errors."""
        # Create a file with binary content that can't be decoded
        binary_file = wiki_dir / "binary_content.md"
        binary_file.write_bytes(b"\xff\xfe\x00\x01" * 100)

        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.get("/wiki/binary_content.md")
        # Should return 500 due to decode error
        assert response.status_code == 500


class TestDeepwikiPathHandling:
    """Tests for .deepwiki parent path handling in api endpoints."""

    def test_api_chat_with_deepwiki_path(self):
        """Test api_chat handles .deepwiki directory path."""
        import local_deepwiki.web.app as web_app

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .deepwiki directory structure
            repo_path = Path(tmpdir)
            deepwiki_path = repo_path / ".deepwiki"
            deepwiki_path.mkdir()
            (deepwiki_path / "index.md").write_text("# Test")

            original = web_app.WIKI_PATH
            web_app.WIKI_PATH = deepwiki_path

            try:
                client = app.test_client()
                response = client.post("/api/chat", json={"question": "test"})
                # Will return SSE stream (error about not indexed, but endpoint works)
                assert response.content_type.startswith("text/event-stream")

                # Read the response to verify it contains the expected error
                data = response.get_data(as_text=True)
                assert "not indexed" in data.lower() or "error" in data.lower()
            finally:
                web_app.WIKI_PATH = original

    def test_api_research_with_deepwiki_path(self):
        """Test api_research handles .deepwiki directory path."""
        import local_deepwiki.web.app as web_app

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .deepwiki directory structure
            repo_path = Path(tmpdir)
            deepwiki_path = repo_path / ".deepwiki"
            deepwiki_path.mkdir()
            (deepwiki_path / "index.md").write_text("# Test")

            original = web_app.WIKI_PATH
            web_app.WIKI_PATH = deepwiki_path

            try:
                client = app.test_client()
                response = client.post("/api/research", json={"question": "test"})
                # Will return SSE stream
                assert response.content_type.startswith("text/event-stream")

                # Read the response
                data = response.get_data(as_text=True)
                assert "not indexed" in data.lower() or "error" in data.lower()
            finally:
                web_app.WIKI_PATH = original


class TestApiChatStreaming:
    """Tests for api_chat streaming functionality."""

    def test_api_chat_returns_sse_headers(self, wiki_dir):
        """Test that api_chat returns proper SSE headers."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/chat",
            json={"question": "What is this?"},
        )

        # Should have SSE content type
        assert "text/event-stream" in response.content_type
        # Should have no-cache headers
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("X-Accel-Buffering") == "no"

    def test_api_chat_with_history(self, wiki_dir):
        """Test api_chat accepts conversation history."""
        app = create_app(wiki_dir)
        client = app.test_client()

        history = [
            {"question": "What is foo?", "answer": "Foo is a function."},
        ]

        response = client.post(
            "/api/chat",
            json={"question": "Tell me more", "history": history},
        )

        # Should accept and process (even if not indexed)
        assert response.content_type.startswith("text/event-stream")


class TestApiResearchStreaming:
    """Tests for api_research streaming functionality."""

    def test_api_research_returns_sse_headers(self, wiki_dir):
        """Test that api_research returns proper SSE headers."""
        app = create_app(wiki_dir)
        client = app.test_client()

        response = client.post(
            "/api/research",
            json={"question": "How does this work?"},
        )

        # Should have SSE content type
        assert "text/event-stream" in response.content_type
        # Should have no-cache headers
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("X-Accel-Buffering") == "no"
