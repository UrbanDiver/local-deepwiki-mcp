"""Simple Flask web UI for browsing DeepWiki documentation.

Uses Jinja2 template files with automatic caching for production performance.
Templates are loaded from the 'templates' subdirectory relative to this module.

Route modules:
- routes_chat: /chat and /api/chat (RAG Q&A)
- routes_research: /api/research (deep multi-step research)
- routes_codemap: /codemap, /api/codemap/* (interactive code flow maps)
- routes_architecture: /architecture, /architecture/api/* (architecture dashboard)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re as _re
import sys
from pathlib import Path

import markdown
from markupsafe import Markup

from local_deepwiki.logging import get_logger

try:
    import nh3 as _nh3

    _HAS_NH3 = True
except ImportError:
    _nh3 = None  # type: ignore[assignment]
    _HAS_NH3 = False

logger = get_logger(__name__)

try:
    from flask import (
        Flask,
        Response,
        abort,
        jsonify,
        make_response,
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

    from local_deepwiki.web.routes_architecture import architecture_bp  # noqa: E402

    app.register_blueprint(chat_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(codemap_bp)
    app.register_blueprint(architecture_bp)


# ---------------------------------------------------------------------------
# CSRF protection (Origin header check on mutating requests)
# ---------------------------------------------------------------------------
@app.before_request
def csrf_check() -> Response | None:
    """Block cross-origin mutating requests without a matching Origin header."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("Origin")
        if origin:
            host = request.host_url.rstrip("/")
            if not origin.startswith(host):
                logger.warning("CSRF blocked: Origin=%s Host=%s", origin, host)
                abort(403, "Cross-origin request blocked")
    return None


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
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
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


def _fix_markdown_fences(content: str) -> str:
    """Fix malformed markdown where headings and code fences are on the same line.

    LLM-generated wiki pages sometimes produce patterns like:
    - ``## Class Diagram```mermaid`` (heading glued to opening fence)
    - ``````## Call Graph```mermaid`` (closing fence + heading + opening fence)
    - ``````## Used By`` (closing fence glued to heading)
    """
    # Split closing fence glued to a heading: ```## Heading → ```\n\n## Heading
    content = _re.sub(
        r"^(```)(\s*)(#{1,6} )", r"\1\n\n\3", content, flags=_re.MULTILINE
    )
    # Split heading glued to opening fence: ## Heading```lang → ## Heading\n\n```lang
    content = _re.sub(
        r"^(#{1,6} [^\n`]*?)(```\w*)$", r"\1\n\n\2", content, flags=_re.MULTILINE
    )
    return content


def render_markdown(content: str) -> str:
    """Render markdown to HTML with sanitization.

    Uses nh3 (if available) to strip dangerous tags like <script> while
    preserving safe HTML produced by the markdown renderer.
    """
    content = _fix_markdown_fences(content)
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "nl2br",
            "md_in_html",
        ]
    )
    raw_html = md.convert(content)
    if _HAS_NH3:
        return _nh3.clean(
            raw_html,
            attributes={
                "code": {"class"},
                "a": {"href"},
                "img": {"src", "alt"},
                "details": {"id"},
                "summary": set(),
            },
        )
    # nh3 unavailable: strip HTML tags as a safety fallback
    return _re.sub(r"<[^>]+>", "", raw_html)


def build_breadcrumb(wiki_path: Path, current_path: str) -> Markup:
    """Build breadcrumb navigation HTML with clickable links.

    For a path like 'files/src/local_deepwiki/core/chunker.md', generates:
    Home > Files > src > local_deepwiki > core > chunker

    Each segment links to its index.md if one exists in that folder.

    Returns a ``Markup`` object so Jinja2 auto-escaping tracks safety.
    User-derived strings are passed through ``markupsafe.escape()``
    automatically via ``Markup.format()``, making XSS impossible by
    construction.
    """
    parts = current_path.split("/")

    # Root pages don't need breadcrumbs (or just show Home)
    if len(parts) == 1:
        return Markup("")

    breadcrumb_items: list[Markup] = []

    # Always start with Home
    breadcrumb_items.append(Markup('<a href="/">Home</a>'))

    # Build path progressively and check for index.md at each level
    cumulative_path = ""
    for part in parts[:-1]:  # Exclude the current page
        if cumulative_path:
            cumulative_path = f"{cumulative_path}/{part}"
        else:
            cumulative_path = part

        # Check if there's an index.md in this folder
        index_path = wiki_path / cumulative_path / "index.md"
        display_name = part.replace("_", " ").replace("-", " ").title()

        if index_path.exists():
            link_path = f"{cumulative_path}/index.md"
            # Markup.format() auto-escapes non-Markup arguments
            breadcrumb_items.append(
                Markup('<a href="/wiki/{}">{}</a>').format(link_path, display_name)
            )
        else:
            # No index.md, just show as text
            breadcrumb_items.append(Markup("<span>{}</span>").format(display_name))

    # Add current page name (no link, it's the current page)
    current_page = parts[-1]
    if current_page.endswith(".md"):
        current_page = current_page[:-3]
    current_page = current_page.replace("_", " ").replace("-", " ").title()
    breadcrumb_items.append(
        Markup('<span class="current">{}</span>').format(current_page)
    )

    separator = Markup(' <span class="separator">\u203a</span> ')
    return separator.join(breadcrumb_items)


# ---------------------------------------------------------------------------
# Inject shared template variables
# ---------------------------------------------------------------------------
@app.context_processor
def inject_active_page() -> dict[str, str]:
    """Make active_page available to all templates for nav highlighting."""
    from flask import request as _req

    path = _req.path
    if path.startswith("/architecture"):
        page = "architecture"
    elif path.startswith("/codemap"):
        page = "codemap"
    elif path.startswith("/chat"):
        page = "chat"
    else:
        page = "wiki"
    return {"active_page": page}


# ---------------------------------------------------------------------------
# Core routes (kept in app.py: index, search, view_page)
# ---------------------------------------------------------------------------
@app.route("/")
def index() -> Response | str:
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
    return make_response(redirect(url_for("view_page", path="index.md")))


@app.route("/search.json")
def search_json() -> Response:
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


import threading

# Persistent event loop for lazy generation so that in-flight futures
# created by LazyPageGenerator stay on the same loop across requests.
_lazy_loop: asyncio.AbstractEventLoop | None = None
_lazy_loop_lock = threading.Lock()


def _get_lazy_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent background event loop for lazy page generation."""
    global _lazy_loop
    if _lazy_loop is None or _lazy_loop.is_closed():
        with _lazy_loop_lock:
            if _lazy_loop is None or _lazy_loop.is_closed():
                _lazy_loop = asyncio.new_event_loop()
                t = threading.Thread(target=_lazy_loop.run_forever, daemon=True)
                t.start()
    return _lazy_loop


def _try_lazy_generate(page_path: str, wiki_path: Path) -> str | None:
    """Attempt to generate a missing wiki page on demand.

    Uses the lazy page generator to create pages for files, modules,
    and other known page types when they haven't been eagerly generated.

    Args:
        page_path: Relative wiki page path (e.g. 'files/utils.md').
        wiki_path: Resolved path to the .deepwiki directory.

    Returns:
        Markdown content string if generation succeeded, None otherwise.
    """
    try:
        from local_deepwiki.generators.lazy_generator import get_lazy_generator

        generator = get_lazy_generator(wiki_path)
        loop = _get_lazy_loop()
        future = asyncio.run_coroutine_threadsafe(generator.get_page(page_path), loop)
        content = future.result(timeout=120)

        logger.info("Lazy-generated page: %s", page_path)
        return content
    except FileNotFoundError:
        logger.debug("Lazy generation has no source for: %s", page_path)
        return None
    except Exception:  # noqa: BLE001 — web handler boundary: lazy generation failure returns None gracefully
        logger.exception("Lazy generation failed for: %s", page_path)
        return None


def _compute_etag(file_path: Path) -> str | None:
    """Compute an ETag from file mtime and size, or None on error."""
    try:
        stat = file_path.stat()
        return hashlib.md5(f"{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()
    except OSError:
        return None


def _resolve_page_content(wiki_path: Path, path: str) -> tuple[str, Path, str | None]:
    """Resolve wiki page path, read or lazily generate content.

    Handles path validation, traversal prevention, lazy generation for
    missing pages, and file reading.

    Args:
        wiki_path: Resolved .deepwiki directory path.
        path: Relative wiki page path (e.g. 'modules/src.md').

    Returns:
        Tuple of (markdown_content, resolved_file_path, etag_or_none).
        etag is None when content was freshly generated rather than read
        from disk.

    Raises:
        Werkzeug abort(403) on path traversal attempts.
        Werkzeug abort(404) when the page cannot be found or generated.
        Werkzeug abort(500) on file read errors.
    """
    file_path = (wiki_path / path).resolve()
    if not file_path.is_relative_to(wiki_path):
        logger.warning("Path traversal attempt blocked: %s", path)
        abort(403, "Invalid path")

    # If the page doesn't exist on disk, attempt lazy generation
    if not file_path.exists() or not file_path.is_file():
        content = _try_lazy_generate(path, wiki_path)
        if content is None:
            logger.warning("Page not found: %s", path)
            abort(404, f"Page not found: {path}")
        return content, file_path, None

    # Read existing file
    try:
        etag = _compute_etag(file_path)
        content = file_path.read_text()
        return content, file_path, etag
    except (OSError, UnicodeDecodeError) as e:
        from local_deepwiki.errors import sanitize_error_message

        abort(500, sanitize_error_message(str(e)))


def _build_page_response(
    wiki_path: Path, path: str, html_content: str, file_path: Path
) -> Response:
    """Build the full page response with sidebar, breadcrumb, and cache headers.

    Args:
        wiki_path: Resolved .deepwiki directory path.
        path: Relative wiki page path.
        html_content: Already-rendered HTML content.
        file_path: Resolved file path (may not exist for freshly generated pages).

    Returns:
        Flask Response with rendered template and cache headers.
    """
    pages, sections, toc_entries = get_wiki_structure(wiki_path)

    # After lazy generation the file now exists on disk
    title = (
        extract_title(file_path)
        if file_path.exists()
        else path.split("/")[-1].replace(".md", "").replace("_", " ").title()
    )

    breadcrumb = build_breadcrumb(wiki_path, path)

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

    # Set caching headers — use ETag if file exists on disk
    etag = _compute_etag(file_path) if file_path.exists() else None
    if etag is not None:
        response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return response


@app.route("/wiki/<path:path>")
def view_page(path: str) -> Response | str:
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

    content, file_path, etag = _resolve_page_content(WIKI_PATH, path)

    # Conditional request: return 304 if client has current version
    if etag is not None and request.if_none_match and etag in request.if_none_match:
        return Response(status=304)

    html_content = render_markdown(content)
    return _build_page_response(WIKI_PATH, path, html_content, file_path)


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
    # Store on app.config so blueprints can access via current_app.config
    # even when the server is launched via `python -m` (where __main__ and
    # local_deepwiki.web.app are separate module objects).
    app.config["WIKI_PATH"] = WIKI_PATH
    logger.info("Configured wiki path: %s", WIKI_PATH)
    return app


def run_server(
    wiki_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8080,
    debug: bool = False,
) -> None:
    """Run the wiki web server."""
    if debug and host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning(
            "Debug mode is not recommended on non-localhost host %s. "
            "Forcing debug=False for safety.",
            host,
        )
        debug = False
    flask_app = create_app(wiki_path)
    logger.info("Starting DeepWiki server at http://%s:%s", host, port)
    logger.info("Serving wiki from: %s", wiki_path)
    flask_app.run(host=host, port=port, debug=debug)


def main() -> None:
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
