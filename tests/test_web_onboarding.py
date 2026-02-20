"""Tests for web onboarding page functionality."""

import pytest


@pytest.fixture
def app():
    """Create a test Flask app with isolated WIKI_PATH.

    Clears app.config["WIKI_PATH"] so that get_wiki_path() (used by
    blueprint routes) falls through to the module-level WIKI_PATH that
    tests control via monkeypatch.
    """
    from local_deepwiki.web.app import app as flask_app

    flask_app.config["TESTING"] = True
    saved = flask_app.config.pop("WIKI_PATH", None)
    yield flask_app
    if saved is not None:
        flask_app.config["WIKI_PATH"] = saved
    else:
        flask_app.config.pop("WIKI_PATH", None)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_wiki_path(tmp_path):
    """Create a temporary wiki path."""
    wiki_dir = tmp_path / ".deepwiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    return wiki_dir


def test_onboarding_page_shown_when_wiki_missing(client, mock_wiki_path, monkeypatch):
    """Test that onboarding page is shown when index.md doesn't exist."""
    # Mock WIKI_PATH to point to our test directory
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Access root route - should show onboarding
    response = client.get("/")
    assert response.status_code == 200
    assert b"Welcome to Local DeepWiki" in response.data
    assert b"Repository Not Indexed" in response.data
    assert b"index_repository" in response.data


def test_onboarding_page_shown_on_view_page_when_wiki_missing(
    client, mock_wiki_path, monkeypatch
):
    """Test that onboarding page is shown when accessing /wiki/path without index."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Access a wiki page - should show onboarding
    response = client.get("/wiki/some-page.md")
    assert response.status_code == 200
    assert b"Welcome to Local DeepWiki" in response.data
    assert b"Repository Not Indexed" in response.data


def test_onboarding_page_shown_on_chat_when_wiki_missing(
    client, mock_wiki_path, monkeypatch
):
    """Test that onboarding page is shown when accessing chat without index."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Access chat page - should show onboarding
    response = client.get("/chat")
    assert response.status_code == 200
    assert b"Welcome to Local DeepWiki" in response.data
    assert b"Repository Not Indexed" in response.data


def test_onboarding_page_shown_on_codemap_when_wiki_missing(
    client, mock_wiki_path, monkeypatch
):
    """Test that onboarding page is shown when accessing codemap without index."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Access codemap page - should show onboarding
    response = client.get("/codemap")
    assert response.status_code == 200
    assert b"Welcome to Local DeepWiki" in response.data
    assert b"Repository Not Indexed" in response.data


def test_onboarding_page_shown_on_codemap_compare_when_wiki_missing(
    client, mock_wiki_path, monkeypatch
):
    """Test that onboarding page is shown when accessing codemap compare without index."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Access codemap compare page - should show onboarding
    response = client.get("/codemap/compare")
    assert response.status_code == 200
    assert b"Welcome to Local DeepWiki" in response.data
    assert b"Repository Not Indexed" in response.data


def test_normal_page_shown_when_wiki_exists(client, mock_wiki_path, monkeypatch):
    """Test that normal wiki page is shown when index.md exists."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Create index.md
    index_md = mock_wiki_path / "index.md"
    index_md.write_text("# Test Wiki\n\nWelcome to the test wiki.")

    # Access root route - should redirect to index.md
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/wiki/index.md" in response.location


def test_view_page_works_when_wiki_exists(client, mock_wiki_path, monkeypatch):
    """Test that view_page route works normally when wiki exists."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Create index.md and another page
    index_md = mock_wiki_path / "index.md"
    index_md.write_text("# Test Wiki")

    test_page = mock_wiki_path / "test.md"
    test_page.write_text("# Test Page\n\nThis is a test.")

    # Access the test page - should render normally
    response = client.get("/wiki/test.md")
    assert response.status_code == 200
    assert b"Test Page" in response.data
    assert b"This is a test" in response.data


def test_chat_page_works_when_wiki_exists(client, mock_wiki_path, monkeypatch):
    """Test that chat page works normally when wiki exists."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Create index.md
    index_md = mock_wiki_path / "index.md"
    index_md.write_text("# Test Wiki")

    # Access chat page - should render chat template
    response = client.get("/chat")
    assert response.status_code == 200
    # Chat template has different content than onboarding
    assert (
        b"Welcome to Local DeepWiki" not in response.data
        or b"Ask questions" in response.data
    )


def test_codemap_page_works_when_wiki_exists(client, mock_wiki_path, monkeypatch):
    """Test that codemap page works normally when wiki exists."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    # Create index.md
    index_md = mock_wiki_path / "index.md"
    index_md.write_text("# Test Wiki")

    # Access codemap page - should render codemap template
    response = client.get("/codemap")
    assert response.status_code == 200
    # Codemap template has different content than onboarding
    assert (
        b"Welcome to Local DeepWiki" not in response.data or b"Codemap" in response.data
    )


def test_onboarding_template_renders_wiki_path(client, mock_wiki_path, monkeypatch):
    """Test that onboarding template receives the correct wiki path."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    response = client.get("/")
    assert response.status_code == 200

    # Check that the parent path (repo path) is in the response
    expected_path = str(mock_wiki_path.parent)
    assert expected_path.encode() in response.data


def test_onboarding_has_correct_structure(client, mock_wiki_path, monkeypatch):
    """Test that onboarding page has all required elements."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    response = client.get("/")
    assert response.status_code == 200

    # Check for key sections
    assert b"What is Local DeepWiki?" in response.data
    assert b"Get Started" in response.data
    assert b"Alternative: CLI Commands" in response.data

    # Check for features
    assert b"Multi-language AST parsing" in response.data
    assert b"Semantic code search" in response.data
    assert b"RAG-based Q&amp;A" in response.data

    # Check for instructions
    assert b"Index Your Repository" in response.data
    assert b"Refresh This Page" in response.data

    # Check for CLI commands
    assert b"uv run local-deepwiki" in response.data
    assert b"uv run deepwiki-watch" in response.data


def test_wiki_path_none_returns_500(client):
    """Test that routes return 500 when WIKI_PATH is None."""
    from local_deepwiki.web import app as web_app

    # Temporarily set WIKI_PATH to None
    original_path = web_app.WIKI_PATH
    try:
        web_app.WIKI_PATH = None

        # Test various routes
        response = client.get("/")
        assert response.status_code == 500

        response = client.get("/wiki/test.md")
        assert response.status_code == 500

        response = client.get("/chat")
        assert response.status_code == 500

        response = client.get("/codemap")
        assert response.status_code == 500
    finally:
        web_app.WIKI_PATH = original_path


def test_onboarding_theme_toggle_exists(client, mock_wiki_path, monkeypatch):
    """Test that onboarding page includes theme toggle functionality."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    response = client.get("/")
    assert response.status_code == 200

    # Check for theme toggle button and script
    assert b"theme-toggle" in response.data
    assert b"setBaseTheme" in response.data
    assert b"localStorage.getItem('deepwiki-theme')" in response.data


def test_onboarding_status_indicator(client, mock_wiki_path, monkeypatch):
    """Test that onboarding page shows status indicator correctly."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    response = client.get("/")
    assert response.status_code == 200

    # Check for status indicator
    assert b"status-indicator" in response.data
    assert b"Repository Not Indexed" in response.data
    assert b"status-icon" in response.data


def test_create_app_with_missing_wiki_path():
    """Test that create_app raises error when wiki path doesn't exist."""
    from local_deepwiki.web.app import create_app

    with pytest.raises(ValueError, match="Wiki path does not exist"):
        create_app("/nonexistent/path/to/wiki")


def test_create_app_with_valid_wiki_path(tmp_path):
    """Test that create_app works with valid wiki path."""
    from local_deepwiki.web.app import create_app

    wiki_dir = tmp_path / ".deepwiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(wiki_dir)
    assert app is not None


def test_onboarding_responsive_design(client, mock_wiki_path, monkeypatch):
    """Test that onboarding page includes responsive design elements."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    response = client.get("/")
    assert response.status_code == 200

    # Check for viewport meta tag and responsive CSS
    assert b"viewport" in response.data
    assert b"@media" in response.data


def test_onboarding_accessibility(client, mock_wiki_path, monkeypatch):
    """Test that onboarding page has basic accessibility features."""
    from local_deepwiki.web import app as web_app

    monkeypatch.setattr(web_app, "WIKI_PATH", mock_wiki_path)

    response = client.get("/")
    assert response.status_code == 200

    # Check for semantic HTML and lang attribute
    assert b'lang="en"' in response.data
    assert b"<h1>" in response.data
    assert b"<h2>" in response.data
