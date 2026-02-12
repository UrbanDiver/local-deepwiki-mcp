"""Simple Flask web UI for browsing DeepWiki documentation.

Uses Jinja2 template files with automatic caching for production performance.
Templates are loaded from the 'templates' subdirectory relative to this module.

Route modules:
- routes_chat: /chat and /api/chat (RAG Q&A)
- routes_research: /api/research (deep multi-step research)
- routes_codemap: /codemap, /api/codemap/* (interactive code flow maps)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import html

import markdown

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

try:
    from flask import (
        Flask,
        Response,
        abort,
        jsonify,
        redirect,
        render_template,
        request,
        url_for,
    )

    # Re-export symbols that tests and other code import from this module.
    # The canonical definitions now live in routes_chat but we keep these
    # importable from app.py for backward compatibility.
    from local_deepwiki.web.routes_chat import (  # noqa: F401 - backward compat re-exports
        build_prompt_with_history,
        format_sources,
        stream_async_generator,
    )

    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False

# Get the directory containing this module for template path resolution
_MODULE_DIR = Path(__file__).parent

# Create Flask app with explicit template folder (only if Flask is available)
if _HAS_FLASK:
    app = Flask(__name__, template_folder=str(_MODULE_DIR / "templates"))
else:
    app = None  # type: ignore[assignment]

# Default wiki path - can be overridden via create_app()
WIKI_PATH: Path | None = None


# ---------------------------------------------------------------------------
# Register Blueprints (only when Flask is available)
# ---------------------------------------------------------------------------
if _HAS_FLASK:
    from local_deepwiki.web.routes_chat import chat_bp  # noqa: E402
    from local_deepwiki.web.routes_codemap import codemap_bp  # noqa: E402
    from local_deepwiki.web.routes_research import research_bp  # noqa: E402

    app.register_blueprint(chat_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(codemap_bp)


# ---------------------------------------------------------------------------
# Security headers (applied to all responses including blueprint routes)
# ---------------------------------------------------------------------------
@app.after_request
def add_security_headers(response: Response) -> Response:
    """Add security headers to all responses.

    These headers protect against common web vulnerabilities:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking attacks
    - X-XSS-Protection: Enables browser XSS filtering (legacy but still useful)
    - Content-Security-Policy: Controls allowed content sources
    - Referrer-Policy: Controls referrer information leakage
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# Wiki structure helpers
# ---------------------------------------------------------------------------
def get_wiki_structure(wiki_path: Path) -> tuple[list, dict, list | None]:
    """Get wiki pages and sections, with optional hierarchical TOC.

    Returns:
        Tuple of (pages, sections, toc_entries) where toc_entries is the
        hierarchical numbered TOC if toc.json exists, None otherwise.
    """
    pages = []
    sections = {}
    toc_entries = None

    # Try to load toc.json for hierarchical numbered structure
    toc_path = wiki_path / "toc.json"
    if toc_path.exists():
        try:
            toc_data = json.loads(toc_path.read_text())
            toc_entries = toc_data.get("entries", [])
        except (json.JSONDecodeError, OSError):
            pass  # Fall back to flat structure

    # Get root pages
    for md_file in sorted(wiki_path.glob("*.md")):
        title = extract_title(md_file)
        pages.append({"path": md_file.name, "title": title})

    # Get section pages (used as fallback if no toc.json)
    for section_dir in sorted(wiki_path.iterdir()):
        if section_dir.is_dir() and not section_dir.name.startswith("."):
            section_pages = []
            for md_file in sorted(section_dir.glob("*.md")):
                title = extract_title(md_file)
                section_pages.append(
                    {"path": f"{section_dir.name}/{md_file.name}", "title": title}
                )
            if section_pages:
                sections[section_dir.name.replace("_", " ").title()] = section_pages

    return pages, sections, toc_entries


def extract_title(md_file: Path) -> str:
    """Extract title from markdown file."""
    try:
        content = md_file.read_text()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("**") and line.endswith("**"):
                return line[2:-2].strip()
    except (OSError, UnicodeDecodeError) as e:
        logger.debug("Could not extract title from %s: %s", md_file, e)
    return md_file.stem.replace("_", " ").replace("-", " ").title()


def render_markdown(content: str) -> str:
    """Render markdown to HTML with sanitization.

    Uses nh3 (if available) to strip dangerous tags like <script> while
    preserving safe HTML produced by the markdown renderer.
    """
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "nl2br",
        ]
    )
    raw_html = md.convert(content)
    try:
        import nh3

        return nh3.clean(raw_html)
    except ImportError:
        return raw_html


def build_breadcrumb(wiki_path: Path, current_path: str) -> str:
    """Build breadcrumb navigation HTML with clickable links.

    For a path like 'files/src/local_deepwiki/core/chunker.md', generates:
    Home > Files > src > local_deepwiki > core > chunker

    Each segment links to its index.md if one exists in that folder.
    """
    parts = current_path.split("/")

    # Root pages don't need breadcrumbs (or just show Home)
    if len(parts) == 1:
        return ""

    breadcrumb_items = []

    # Always start with Home
    breadcrumb_items.append('<a href="/">Home</a>')

    # Build path progressively and check for index.md at each level
    cumulative_path = ""
    for part in parts[:-1]:  # Exclude the current page
        if cumulative_path:
            cumulative_path = f"{cumulative_path}/{part}"
        else:
            cumulative_path = part

        # Check if there's an index.md in this folder
        index_path = wiki_path / cumulative_path / "index.md"
        display_name = html.escape(part.replace("_", " ").replace("-", " ").title())

        if index_path.exists():
            link_path = f"{cumulative_path}/index.md"
            breadcrumb_items.append(f'<a href="/wiki/{link_path}">{display_name}</a>')
        else:
            # No index.md, just show as text
            breadcrumb_items.append(f"<span>{display_name}</span>")

    # Add current page name (no link, it's the current page)
    current_page = parts[-1]
    if current_page.endswith(".md"):
        current_page = current_page[:-3]
    current_page = html.escape(current_page.replace("_", " ").replace("-", " ").title())
    breadcrumb_items.append(f'<span class="current">{current_page}</span>')

    return ' <span class="separator">›</span> '.join(breadcrumb_items)


# ---------------------------------------------------------------------------
# Core routes (kept in app.py: index, search, view_page)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Redirect to index.md or show onboarding if wiki doesn't exist."""
    logger.debug("Accessing root route")

    if WIKI_PATH is None:
        logger.error("Wiki path not configured")
        abort(500, "Wiki path not configured")

    # Check if wiki directory has content
    index_md = WIKI_PATH / "index.md"
    if not index_md.exists():
        logger.info("Wiki not indexed yet, showing onboarding page")
        return render_template("onboarding.html", wiki_path=str(WIKI_PATH.parent))

    logger.debug("Redirecting / to index.md")
    return redirect(url_for("view_page", path="index.md"))


@app.route("/search.json")
def search_json():
    """Serve the search index JSON file."""
    if WIKI_PATH is None:
        abort(500, "Wiki path not configured")

    search_path = WIKI_PATH / "search.json"
    if not search_path.exists():
        # Return empty index if not generated yet
        return jsonify([])

    try:
        data = json.loads(search_path.read_text())
        return jsonify(data)
    except (json.JSONDecodeError, OSError) as e:
        from local_deepwiki.errors import sanitize_error_message

        abort(500, sanitize_error_message(str(e)))


@app.route("/wiki/<path:path>")
def view_page(path: str):
    """View a wiki page."""
    logger.debug("Viewing page: %s", path)

    if WIKI_PATH is None:
        logger.error("Wiki path not configured")
        abort(500, "Wiki path not configured")

    # Check if wiki directory exists and is indexed
    index_md = WIKI_PATH / "index.md"
    if not index_md.exists():
        logger.info("Wiki not indexed yet, showing onboarding page")
        return render_template("onboarding.html", wiki_path=str(WIKI_PATH.parent))

    file_path = (WIKI_PATH / path).resolve()
    if not file_path.is_relative_to(WIKI_PATH):
        logger.warning("Path traversal attempt blocked: %s", path)
        abort(403, "Invalid path")
    if not file_path.exists() or not file_path.is_file():
        logger.warning("Page not found: %s", path)
        abort(404, f"Page not found: {path}")

    try:
        # ETag based on file mtime + size for conditional requests
        stat = file_path.stat()
        etag = hashlib.md5(f"{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()

        if request.if_none_match and etag in request.if_none_match:
            return Response(status=304)

        content = file_path.read_text()
        html_content = render_markdown(content)
    except (OSError, UnicodeDecodeError) as e:
        from local_deepwiki.errors import sanitize_error_message

        abort(500, sanitize_error_message(str(e)))

    pages, sections, toc_entries = get_wiki_structure(WIKI_PATH)
    title = extract_title(file_path)

    # Build breadcrumb navigation
    breadcrumb = build_breadcrumb(WIKI_PATH, path)

    response = Response(
        render_template(
            "page.html",
            content=html_content,
            title=title,
            pages=pages,
            sections=sections,
            toc_entries=toc_entries,
            current_path=path,
            breadcrumb=breadcrumb,
        )
    )
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return response


# ---------------------------------------------------------------------------
# App factory and CLI entry point
# ---------------------------------------------------------------------------
def create_app(wiki_path: str | Path) -> Flask:
    """Create Flask app with wiki path configured."""
    global WIKI_PATH
    WIKI_PATH = Path(wiki_path).resolve()
    if not WIKI_PATH.exists():
        logger.error("Wiki path does not exist: %s", wiki_path)
        raise ValueError(f"Wiki path does not exist: {wiki_path}")
    logger.info("Configured wiki path: %s", WIKI_PATH)
    return app


def run_server(
    wiki_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8080,
    debug: bool = False,
):
    """Run the wiki web server."""
    flask_app = create_app(wiki_path)
    logger.info("Starting DeepWiki server at http://%s:%s", host, port)
    logger.info("Serving wiki from: %s", wiki_path)
    flask_app.run(host=host, port=port, debug=debug)


def main():
    """CLI entry point."""
    if not _HAS_FLASK:
        print(
            "Error: Flask is required for the web UI but is not installed.\n"
            "Install with: uv pip install flask",
            file=sys.stderr,
        )
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(description="Serve DeepWiki documentation")
    parser.add_argument(
        "wiki_path",
        nargs="?",
        default=".deepwiki",
        help="Path to the .deepwiki directory",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    wiki_path = Path(args.wiki_path).resolve()
    run_server(wiki_path, args.host, args.port, args.debug)


if __name__ == "__main__":
    main()
