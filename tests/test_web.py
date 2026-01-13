"""Tests for the web UI functionality."""

import tempfile
from pathlib import Path

import pytest

from local_deepwiki.web.app import _MODULE_DIR, app, build_breadcrumb, create_app


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
