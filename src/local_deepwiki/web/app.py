"""Simple Flask web UI for browsing DeepWiki documentation."""

from pathlib import Path
from flask import Flask, render_template_string, abort, redirect, url_for
import markdown

app = Flask(__name__)

# Default wiki path - can be overridden
WIKI_PATH: Path | None = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - DeepWiki</title>
    <style>
        :root {
            --bg-color: #0d1117;
            --text-color: #c9d1d9;
            --link-color: #58a6ff;
            --border-color: #30363d;
            --sidebar-bg: #161b22;
            --code-bg: #1f2428;
            --heading-color: #f0f6fc;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            display: flex;
            min-height: 100vh;
        }
        .sidebar {
            width: 280px;
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border-color);
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }
        .sidebar h2 {
            color: var(--heading-color);
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        .sidebar ul {
            list-style: none;
        }
        .sidebar li {
            margin: 5px 0;
        }
        .sidebar a {
            color: var(--link-color);
            text-decoration: none;
            display: block;
            padding: 5px 10px;
            border-radius: 6px;
            transition: background 0.2s;
        }
        .sidebar a:hover {
            background: var(--border-color);
        }
        .sidebar a.active {
            background: var(--border-color);
            font-weight: 600;
        }
        .sidebar .section {
            margin-top: 20px;
        }
        .sidebar .section-title {
            font-size: 0.85em;
            text-transform: uppercase;
            color: #8b949e;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }
        .content {
            margin-left: 280px;
            padding: 40px 60px;
            max-width: 900px;
            flex: 1;
        }
        .content h1 {
            color: var(--heading-color);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .content h2, .content h3, .content h4 {
            color: var(--heading-color);
            margin-top: 24px;
            margin-bottom: 16px;
        }
        .content a {
            color: var(--link-color);
            text-decoration: none;
        }
        .content a:hover {
            text-decoration: underline;
        }
        .content code {
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .content pre {
            background: var(--code-bg);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 16px 0;
        }
        .content pre code {
            background: none;
            padding: 0;
        }
        .content ul, .content ol {
            margin: 16px 0;
            padding-left: 24px;
        }
        .content li {
            margin: 8px 0;
        }
        .content blockquote {
            border-left: 4px solid var(--border-color);
            padding-left: 16px;
            margin: 16px 0;
            color: #8b949e;
        }
        .content table {
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }
        .content th, .content td {
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            text-align: left;
        }
        .content th {
            background: var(--sidebar-bg);
        }
        .breadcrumb {
            color: #8b949e;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        .breadcrumb a {
            color: var(--link-color);
        }
        .mermaid {
            background: var(--sidebar-bg);
            padding: 20px;
            border-radius: 8px;
            margin: 16px 0;
            text-align: center;
        }
        .mermaid svg {
            max-width: 100%;
        }
        @media (max-width: 768px) {
            .sidebar {
                position: relative;
                width: 100%;
                height: auto;
            }
            .content {
                margin-left: 0;
                padding: 20px;
            }
            body {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <nav class="sidebar">
        <h2>DeepWiki</h2>
        <ul>
            {% for page in pages %}
            <li><a href="{{ url_for('view_page', path=page.path) }}"
                   class="{{ 'active' if page.path == current_path else '' }}">{{ page.title }}</a></li>
            {% endfor %}
        </ul>
        {% for section_name, section_pages in sections.items() %}
        <div class="section">
            <div class="section-title">{{ section_name }}</div>
            <ul>
                {% for page in section_pages %}
                <li><a href="{{ url_for('view_page', path=page.path) }}"
                       class="{{ 'active' if page.path == current_path else '' }}">{{ page.title }}</a></li>
                {% endfor %}
            </ul>
        </div>
        {% endfor %}
    </nav>
    <main class="content">
        {% if breadcrumb %}
        <div class="breadcrumb">{{ breadcrumb | safe }}</div>
        {% endif %}
        {{ content | safe }}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        // Initialize mermaid with dark theme
        mermaid.initialize({
            startOnLoad: false,
            theme: 'dark',
            themeVariables: {
                primaryColor: '#238636',
                primaryTextColor: '#c9d1d9',
                primaryBorderColor: '#30363d',
                lineColor: '#8b949e',
                secondaryColor: '#161b22',
                tertiaryColor: '#0d1117',
                background: '#0d1117',
                mainBkg: '#161b22',
                nodeBorder: '#30363d',
                clusterBkg: '#161b22',
                clusterBorder: '#30363d',
                titleColor: '#c9d1d9',
                edgeLabelBackground: '#161b22'
            }
        });

        // Find mermaid code blocks and render them
        document.addEventListener('DOMContentLoaded', function() {
            // Find all code blocks with language-mermaid class
            const codeBlocks = document.querySelectorAll('pre code.language-mermaid');
            codeBlocks.forEach(function(codeBlock, index) {
                const pre = codeBlock.parentElement;
                const mermaidDiv = document.createElement('div');
                mermaidDiv.className = 'mermaid';
                mermaidDiv.textContent = codeBlock.textContent;
                pre.parentNode.replaceChild(mermaidDiv, pre);
            });

            // Render all mermaid diagrams
            mermaid.run();
        });
    </script>
</body>
</html>
"""


def get_wiki_structure(wiki_path: Path) -> tuple[list, dict]:
    """Get wiki pages and sections."""
    pages = []
    sections = {}

    # Get root pages
    for md_file in sorted(wiki_path.glob("*.md")):
        title = extract_title(md_file)
        pages.append({
            "path": md_file.name,
            "title": title
        })

    # Get section pages
    for section_dir in sorted(wiki_path.iterdir()):
        if section_dir.is_dir() and not section_dir.name.startswith('.'):
            section_pages = []
            for md_file in sorted(section_dir.glob("*.md")):
                title = extract_title(md_file)
                section_pages.append({
                    "path": f"{section_dir.name}/{md_file.name}",
                    "title": title
                })
            if section_pages:
                sections[section_dir.name.replace("_", " ").title()] = section_pages

    return pages, sections


def extract_title(md_file: Path) -> str:
    """Extract title from markdown file."""
    try:
        content = md_file.read_text()
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
            if line.startswith('**') and line.endswith('**'):
                return line[2:-2].strip()
    except Exception:
        pass
    return md_file.stem.replace("_", " ").replace("-", " ").title()


def render_markdown(content: str) -> str:
    """Render markdown to HTML."""
    md = markdown.Markdown(extensions=[
        'fenced_code',
        'tables',
        'toc',
        'nl2br',
    ])
    return md.convert(content)


@app.route('/')
def index():
    """Redirect to index.md."""
    return redirect(url_for('view_page', path='index.md'))


@app.route('/wiki/<path:path>')
def view_page(path: str):
    """View a wiki page."""
    if WIKI_PATH is None:
        abort(500, "Wiki path not configured")

    file_path = WIKI_PATH / path
    if not file_path.exists() or not file_path.is_file():
        abort(404, f"Page not found: {path}")

    try:
        content = file_path.read_text()
        html_content = render_markdown(content)
    except Exception as e:
        abort(500, f"Error reading page: {e}")

    pages, sections = get_wiki_structure(WIKI_PATH)
    title = extract_title(file_path)

    # Build breadcrumb
    parts = path.split('/')
    if len(parts) > 1:
        breadcrumb = f'<a href="{url_for("index")}">Home</a> / {" / ".join(parts[:-1])} / {parts[-1]}'
    else:
        breadcrumb = ""

    return render_template_string(
        HTML_TEMPLATE,
        content=html_content,
        title=title,
        pages=pages,
        sections=sections,
        current_path=path,
        breadcrumb=breadcrumb
    )


def create_app(wiki_path: str | Path) -> Flask:
    """Create Flask app with wiki path configured."""
    global WIKI_PATH
    WIKI_PATH = Path(wiki_path)
    if not WIKI_PATH.exists():
        raise ValueError(f"Wiki path does not exist: {wiki_path}")
    return app


def run_server(wiki_path: str | Path, host: str = "127.0.0.1", port: int = 8080, debug: bool = False):
    """Run the wiki web server."""
    app = create_app(wiki_path)
    print(f"Starting DeepWiki server at http://{host}:{port}")
    print(f"Serving wiki from: {wiki_path}")
    app.run(host=host, port=port, debug=debug)


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Serve DeepWiki documentation")
    parser.add_argument("wiki_path", nargs="?", default=".deepwiki",
                        help="Path to the .deepwiki directory")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    wiki_path = Path(args.wiki_path).resolve()
    run_server(wiki_path, args.host, args.port, args.debug)


if __name__ == "__main__":
    main()
