"""Simple Flask web UI for browsing DeepWiki documentation."""

import json
from pathlib import Path
from flask import Flask, render_template_string, abort, redirect, url_for, jsonify
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
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0;
        }
        .breadcrumb a {
            color: var(--link-color);
            text-decoration: none;
        }
        .breadcrumb a:hover {
            text-decoration: underline;
        }
        .breadcrumb .separator {
            margin: 0 8px;
            color: #6e7681;
        }
        .breadcrumb .current {
            color: var(--text-color);
            font-weight: 500;
        }
        /* Search box styles */
        .search-container {
            margin-bottom: 20px;
            position: relative;
        }
        .search-input {
            width: 100%;
            padding: 10px 12px;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        .search-input:focus {
            border-color: var(--link-color);
        }
        .search-input::placeholder {
            color: #6e7681;
        }
        .search-results {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--sidebar-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-top: 4px;
            max-height: 400px;
            overflow-y: auto;
            z-index: 100;
            display: none;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .search-results.active {
            display: block;
        }
        .search-result {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            transition: background 0.15s;
        }
        .search-result:last-child {
            border-bottom: none;
        }
        .search-result:hover {
            background: var(--border-color);
        }
        .search-result-title {
            color: var(--link-color);
            font-weight: 500;
            margin-bottom: 2px;
        }
        .search-result-path {
            font-size: 12px;
            color: #6e7681;
            margin-bottom: 4px;
        }
        .search-result-snippet {
            font-size: 13px;
            color: #8b949e;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .search-result-match {
            background: rgba(88, 166, 255, 0.2);
            color: var(--link-color);
            border-radius: 2px;
            padding: 0 2px;
        }
        .search-no-results {
            padding: 12px;
            color: #8b949e;
            text-align: center;
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
        <div class="search-container">
            <input type="text" class="search-input" id="search-input" placeholder="Search docs..." autocomplete="off">
            <div class="search-results" id="search-results"></div>
        </div>
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
        // Initialize mermaid with base theme (allows custom styles)
        mermaid.initialize({
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'base',
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
                edgeLabelBackground: '#161b22',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
            },
            themeCSS: '.node rect, .node polygon { fill: #161b22; stroke: #30363d; } .edgeLabel { background-color: #161b22; }'
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
    <script>
        // Search functionality
        (function() {
            let searchIndex = null;
            const searchInput = document.getElementById('search-input');
            const searchResults = document.getElementById('search-results');

            // Load search index
            fetch('/search.json')
                .then(response => response.json())
                .then(data => { searchIndex = data; })
                .catch(err => console.log('Search index not available'));

            // Simple fuzzy match - checks if all query chars appear in order
            function fuzzyMatch(query, text) {
                query = query.toLowerCase();
                text = text.toLowerCase();
                let qi = 0;
                for (let ti = 0; ti < text.length && qi < query.length; ti++) {
                    if (text[ti] === query[qi]) qi++;
                }
                return qi === query.length;
            }

            // Score a result based on match quality
            function scoreResult(query, entry) {
                query = query.toLowerCase();
                let score = 0;

                // Title match (highest priority)
                if (entry.title.toLowerCase().includes(query)) {
                    score += 100;
                    if (entry.title.toLowerCase().startsWith(query)) score += 50;
                } else if (fuzzyMatch(query, entry.title)) {
                    score += 30;
                }

                // Heading match
                for (const heading of entry.headings || []) {
                    if (heading.toLowerCase().includes(query)) {
                        score += 40;
                        break;
                    }
                }

                // Code terms match (class names, functions)
                for (const term of entry.terms || []) {
                    if (term.toLowerCase().includes(query)) {
                        score += 60;
                        break;
                    } else if (fuzzyMatch(query, term)) {
                        score += 20;
                        break;
                    }
                }

                // Snippet match
                if (entry.snippet && entry.snippet.toLowerCase().includes(query)) {
                    score += 10;
                }

                return score;
            }

            // Perform search
            function search(query) {
                if (!searchIndex || query.length < 2) {
                    searchResults.classList.remove('active');
                    return;
                }

                const results = searchIndex
                    .map(entry => ({ entry, score: scoreResult(query, entry) }))
                    .filter(r => r.score > 0)
                    .sort((a, b) => b.score - a.score)
                    .slice(0, 8);

                if (results.length === 0) {
                    searchResults.innerHTML = '<div class="search-no-results">No results found</div>';
                    searchResults.classList.add('active');
                    return;
                }

                const html = results.map(r => {
                    const entry = r.entry;
                    return `
                        <div class="search-result" data-path="${entry.path}">
                            <div class="search-result-title">${escapeHtml(entry.title)}</div>
                            <div class="search-result-path">${escapeHtml(entry.path)}</div>
                            <div class="search-result-snippet">${escapeHtml(entry.snippet || '')}</div>
                        </div>
                    `;
                }).join('');

                searchResults.innerHTML = html;
                searchResults.classList.add('active');

                // Add click handlers
                searchResults.querySelectorAll('.search-result').forEach(el => {
                    el.addEventListener('click', () => {
                        window.location.href = '/wiki/' + el.dataset.path;
                    });
                });
            }

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }

            // Event listeners
            let debounceTimer;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => search(e.target.value.trim()), 150);
            });

            searchInput.addEventListener('focus', () => {
                if (searchInput.value.trim().length >= 2) {
                    search(searchInput.value.trim());
                }
            });

            // Close results when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.search-container')) {
                    searchResults.classList.remove('active');
                }
            });

            // Keyboard navigation
            searchInput.addEventListener('keydown', (e) => {
                const results = searchResults.querySelectorAll('.search-result');
                const active = searchResults.querySelector('.search-result:hover, .search-result.active');
                let index = Array.from(results).indexOf(active);

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    index = Math.min(index + 1, results.length - 1);
                    results.forEach((r, i) => r.classList.toggle('active', i === index));
                    if (results[index]) results[index].scrollIntoView({ block: 'nearest' });
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    index = Math.max(index - 1, 0);
                    results.forEach((r, i) => r.classList.toggle('active', i === index));
                    if (results[index]) results[index].scrollIntoView({ block: 'nearest' });
                } else if (e.key === 'Enter' && index >= 0) {
                    e.preventDefault();
                    results[index].click();
                } else if (e.key === 'Escape') {
                    searchResults.classList.remove('active');
                    searchInput.blur();
                }
            });
        })();
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


def build_breadcrumb(wiki_path: Path, current_path: str) -> str:
    """Build breadcrumb navigation HTML with clickable links.

    For a path like 'files/src/local_deepwiki/core/chunker.md', generates:
    Home > Files > src > local_deepwiki > core > chunker

    Each segment links to its index.md if one exists in that folder.
    """
    parts = current_path.split('/')

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
            breadcrumb_items.append(f'<span>{display_name}</span>')

    # Add current page name (no link, it's the current page)
    current_page = parts[-1]
    if current_page.endswith('.md'):
        current_page = current_page[:-3]
    current_page = current_page.replace("_", " ").replace("-", " ").title()
    breadcrumb_items.append(f'<span class="current">{current_page}</span>')

    return ' <span class="separator">›</span> '.join(breadcrumb_items)


@app.route('/')
def index():
    """Redirect to index.md."""
    return redirect(url_for('view_page', path='index.md'))


@app.route('/search.json')
def search_json():
    """Serve the search index JSON file."""
    if WIKI_PATH is None:
        abort(500, "Wiki path not configured")

    search_path = WIKI_PATH / 'search.json'
    if not search_path.exists():
        # Return empty index if not generated yet
        return jsonify([])

    try:
        data = json.loads(search_path.read_text())
        return jsonify(data)
    except Exception as e:
        abort(500, f"Error reading search index: {e}")


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

    # Build breadcrumb navigation
    breadcrumb = build_breadcrumb(WIKI_PATH, path)

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
