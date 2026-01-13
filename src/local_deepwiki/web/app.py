"""Simple Flask web UI for browsing DeepWiki documentation.

Uses Jinja2 template files with automatic caching for production performance.
Templates are loaded from the 'templates' subdirectory relative to this module.
"""

import json
from pathlib import Path

import markdown
from flask import Flask, abort, jsonify, redirect, render_template, url_for

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Get the directory containing this module for template path resolution
_MODULE_DIR = Path(__file__).parent

# Create Flask app with explicit template folder
# Flask caches compiled templates when debug=False (the default)
app = Flask(__name__, template_folder=str(_MODULE_DIR / "templates"))

# Default wiki path - can be overridden
WIKI_PATH: Path | None = None


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
                section_pages.append({"path": f"{section_dir.name}/{md_file.name}", "title": title})
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
    except Exception as e:
        logger.debug(f"Could not extract title from {md_file}: {e}")
    return md_file.stem.replace("_", " ").replace("-", " ").title()


def render_markdown(content: str) -> str:
    """Render markdown to HTML."""
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "nl2br",
        ]
    )
    return md.convert(content)


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
    breadcrumb_items.append(f'<a href="/">Home</a>')

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
            breadcrumb_items.append(f'<a href="/wiki/{link_path}">{display_name}</a>')
        else:
            # No index.md, just show as text
            breadcrumb_items.append(f"<span>{display_name}</span>")

    # Add current page name (no link, it's the current page)
    current_page = parts[-1]
    if current_page.endswith(".md"):
        current_page = current_page[:-3]
    current_page = current_page.replace("_", " ").replace("-", " ").title()
    breadcrumb_items.append(f'<span class="current">{current_page}</span>')

    return ' <span class="separator">›</span> '.join(breadcrumb_items)


@app.route("/")
def index():
    """Redirect to index.md."""
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
    except Exception as e:
        abort(500, f"Error reading search index: {e}")


@app.route("/wiki/<path:path>")
def view_page(path: str):
    """View a wiki page."""
    logger.debug(f"Viewing page: {path}")

    if WIKI_PATH is None:
        logger.error("Wiki path not configured")
        abort(500, "Wiki path not configured")

    file_path = WIKI_PATH / path
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"Page not found: {path}")
        abort(404, f"Page not found: {path}")

    try:
        content = file_path.read_text()
        html_content = render_markdown(content)
    except Exception as e:
        abort(500, f"Error reading page: {e}")

    pages, sections, toc_entries = get_wiki_structure(WIKI_PATH)
    title = extract_title(file_path)

    # Build breadcrumb navigation
    breadcrumb = build_breadcrumb(WIKI_PATH, path)

    return render_template(
        "page.html",
        content=html_content,
        title=title,
        pages=pages,
        sections=sections,
        toc_entries=toc_entries,
        current_path=path,
        breadcrumb=breadcrumb,
    )


def create_app(wiki_path: str | Path) -> Flask:
    """Create Flask app with wiki path configured."""
    global WIKI_PATH
    WIKI_PATH = Path(wiki_path)
    if not WIKI_PATH.exists():
        logger.error(f"Wiki path does not exist: {wiki_path}")
        raise ValueError(f"Wiki path does not exist: {wiki_path}")
    logger.info(f"Configured wiki path: {WIKI_PATH}")
    return app


def run_server(
    wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False
):
    """Run the wiki web server."""
    app = create_app(wiki_path)
    logger.info(f"Starting DeepWiki server at http://{host}:{port}")
    logger.info(f"Serving wiki from: {wiki_path}")
    print(f"Starting DeepWiki server at http://{host}:{port}")
    print(f"Serving wiki from: {wiki_path}")
    app.run(host=host, port=port, debug=debug)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Serve DeepWiki documentation")
    parser.add_argument(
        "wiki_path", nargs="?", default=".deepwiki", help="Path to the .deepwiki directory"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    wiki_path = Path(args.wiki_path).resolve()
    run_server(wiki_path, args.host, args.port, args.debug)


if __name__ == "__main__":
    main()
