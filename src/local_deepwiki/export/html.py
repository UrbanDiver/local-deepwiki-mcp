"""HTML export functionality for DeepWiki documentation."""

import argparse
import json
import shutil
from pathlib import Path

import markdown


# Static HTML template - adapted from web/app.py for offline use
# Uses relative paths instead of Flask url_for()
STATIC_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - DeepWiki</title>
    <style>
        :root {{
            --bg-color: #0d1117;
            --text-color: #c9d1d9;
            --link-color: #58a6ff;
            --border-color: #30363d;
            --sidebar-bg: #161b22;
            --code-bg: #1f2428;
            --heading-color: #f0f6fc;
        }}
        [data-theme="light"] {{
            --bg-color: #ffffff;
            --text-color: #24292f;
            --link-color: #0969da;
            --border-color: #d0d7de;
            --sidebar-bg: #f6f8fa;
            --code-bg: #f6f8fa;
            --heading-color: #1f2328;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            display: flex;
            min-height: 100vh;
        }}
        .sidebar {{
            width: 280px;
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border-color);
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }}
        .sidebar-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }}
        .sidebar-header h2 {{
            color: var(--heading-color);
            font-size: 1.2em;
            margin: 0;
            padding: 0;
            border: none;
        }}
        .theme-toggle {{
            background: transparent;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 4px 8px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.2s;
        }}
        .theme-toggle:hover {{
            background: var(--border-color);
        }}
        .sidebar-toggle {{
            display: none;
            position: fixed;
            top: 15px;
            left: 15px;
            z-index: 1001;
            background: var(--sidebar-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 18px;
            cursor: pointer;
            color: var(--text-color);
            transition: background 0.2s;
        }}
        .sidebar-toggle:hover {{
            background: var(--border-color);
        }}
        .sidebar h2 {{
            color: var(--heading-color);
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }}
        .sidebar ul {{
            list-style: none;
        }}
        .sidebar li {{
            margin: 5px 0;
        }}
        .sidebar a {{
            color: var(--link-color);
            text-decoration: none;
            display: block;
            padding: 5px 10px;
            border-radius: 6px;
            transition: background 0.2s;
        }}
        .sidebar a:hover {{
            background: var(--border-color);
        }}
        .sidebar a.active {{
            background: var(--border-color);
            font-weight: 600;
        }}
        .sidebar .section {{
            margin-top: 20px;
        }}
        .sidebar .section-title {{
            font-size: 0.85em;
            text-transform: uppercase;
            color: #8b949e;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        .sidebar .toc-number {{
            color: #6e7681;
            font-size: 0.85em;
            margin-right: 6px;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
        }}
        .sidebar .toc-nested {{
            margin-left: 12px;
            border-left: 1px solid var(--border-color);
            padding-left: 8px;
        }}
        .sidebar .toc-item {{
            margin: 4px 0;
        }}
        .sidebar .toc-item > a {{
            display: flex;
            align-items: baseline;
        }}
        .sidebar .toc-parent {{
            font-weight: 500;
            color: var(--heading-color);
            margin-top: 12px;
            margin-bottom: 4px;
        }}
        .sidebar .toc-parent:first-child {{
            margin-top: 0;
        }}
        .content {{
            margin-left: 280px;
            padding: 40px 60px;
            max-width: 900px;
            flex: 1;
        }}
        .content h1 {{
            color: var(--heading-color);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .content h2, .content h3, .content h4 {{
            color: var(--heading-color);
            margin-top: 24px;
            margin-bottom: 16px;
        }}
        .content a {{
            color: var(--link-color);
            text-decoration: none;
        }}
        .content a:hover {{
            text-decoration: underline;
        }}
        .content code {{
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .content pre {{
            background: var(--code-bg);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 16px 0;
        }}
        .content pre code {{
            background: none;
            padding: 0;
        }}
        .content ul, .content ol {{
            margin: 16px 0;
            padding-left: 24px;
        }}
        .content li {{
            margin: 8px 0;
        }}
        .content blockquote {{
            border-left: 4px solid var(--border-color);
            padding-left: 16px;
            margin: 16px 0;
            color: #8b949e;
        }}
        .content table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        .content th, .content td {{
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            text-align: left;
        }}
        .content th {{
            background: var(--sidebar-bg);
        }}
        .breadcrumb {{
            color: #8b949e;
            margin-bottom: 20px;
            font-size: 0.9em;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0;
        }}
        .breadcrumb a {{
            color: var(--link-color);
            text-decoration: none;
        }}
        .breadcrumb a:hover {{
            text-decoration: underline;
        }}
        .breadcrumb .separator {{
            margin: 0 8px;
            color: #6e7681;
        }}
        .breadcrumb .current {{
            color: var(--text-color);
            font-weight: 500;
        }}
        .search-container {{
            margin-bottom: 20px;
            position: relative;
        }}
        .search-input {{
            width: 100%;
            padding: 10px 12px;
            background: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-input:focus {{
            border-color: var(--link-color);
        }}
        .search-input::placeholder {{
            color: #6e7681;
        }}
        .search-results {{
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
        }}
        .search-results.active {{
            display: block;
        }}
        .search-result {{
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            transition: background 0.15s;
        }}
        .search-result:last-child {{
            border-bottom: none;
        }}
        .search-result:hover {{
            background: var(--border-color);
        }}
        .search-result-title {{
            color: var(--link-color);
            font-weight: 500;
            margin-bottom: 2px;
        }}
        .search-result-path {{
            font-size: 12px;
            color: #6e7681;
            margin-bottom: 4px;
        }}
        .search-result-snippet {{
            font-size: 13px;
            color: #8b949e;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .search-result-match {{
            background: rgba(88, 166, 255, 0.2);
            color: var(--link-color);
            border-radius: 2px;
            padding: 0 2px;
        }}
        .search-no-results {{
            padding: 12px;
            color: #8b949e;
            text-align: center;
        }}
        .mermaid {{
            background: var(--sidebar-bg);
            padding: 20px;
            border-radius: 8px;
            margin: 16px 0;
            text-align: center;
        }}
        .mermaid svg {{
            max-width: 100%;
        }}
        @media (max-width: 768px) {{
            .sidebar-toggle {{
                display: block;
            }}
            .sidebar {{
                position: fixed;
                width: 280px;
                height: 100vh;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                z-index: 1000;
            }}
            .sidebar.open {{
                transform: translateX(0);
            }}
            .content {{
                margin-left: 0;
                padding: 20px;
                padding-top: 60px;
            }}
            body {{
                flex-direction: column;
            }}
        }}
    </style>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css" id="hljs-theme">
    <script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
</head>
<body>
    <button id="sidebar-toggle" class="sidebar-toggle" title="Toggle sidebar">&#9776;</button>
    <nav class="sidebar">
        <div class="sidebar-header">
            <h2>DeepWiki</h2>
            <button id="theme-toggle" class="theme-toggle" title="Toggle theme">&#127769;</button>
        </div>
        <div class="search-container">
            <input type="text" class="search-input" id="search-input" placeholder="Search docs..." autocomplete="off">
            <div class="search-results" id="search-results"></div>
        </div>
        <div class="toc">
            {toc_html}
        </div>
    </nav>
    <main class="content">
        {breadcrumb_html}
        {content_html}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        // Initialize mermaid with base theme
        mermaid.initialize({{
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'base',
            themeVariables: {{
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
            }},
            themeCSS: '.node rect, .node polygon {{ fill: #161b22; stroke: #30363d; }} .edgeLabel {{ background-color: #161b22; }}'
        }});

        // Find mermaid code blocks and render them
        document.addEventListener('DOMContentLoaded', function() {{
            const codeBlocks = document.querySelectorAll('pre code.language-mermaid');
            codeBlocks.forEach(function(codeBlock) {{
                const pre = codeBlock.parentElement;
                const mermaidDiv = document.createElement('div');
                mermaidDiv.className = 'mermaid';
                mermaidDiv.textContent = codeBlock.textContent;
                pre.parentNode.replaceChild(mermaidDiv, pre);
            }});
            mermaid.run();
        }});
    </script>
    <script>
        // Search functionality for static export
        (function() {{
            let searchIndex = null;
            const searchInput = document.getElementById('search-input');
            const searchResults = document.getElementById('search-results');

            // Load search index - use relative path for static export
            fetch('{search_json_path}')
                .then(response => response.json())
                .then(data => {{ searchIndex = data; }})
                .catch(err => console.log('Search index not available'));

            function fuzzyMatch(query, text) {{
                query = query.toLowerCase();
                text = text.toLowerCase();
                let qi = 0;
                for (let ti = 0; ti < text.length && qi < query.length; ti++) {{
                    if (text[ti] === query[qi]) qi++;
                }}
                return qi === query.length;
            }}

            function scoreResult(query, entry) {{
                query = query.toLowerCase();
                let score = 0;
                if (entry.title.toLowerCase().includes(query)) {{
                    score += 100;
                    if (entry.title.toLowerCase().startsWith(query)) score += 50;
                }} else if (fuzzyMatch(query, entry.title)) {{
                    score += 30;
                }}
                for (const heading of entry.headings || []) {{
                    if (heading.toLowerCase().includes(query)) {{
                        score += 40;
                        break;
                    }}
                }}
                for (const term of entry.terms || []) {{
                    if (term.toLowerCase().includes(query)) {{
                        score += 60;
                        break;
                    }} else if (fuzzyMatch(query, term)) {{
                        score += 20;
                        break;
                    }}
                }}
                if (entry.snippet && entry.snippet.toLowerCase().includes(query)) {{
                    score += 10;
                }}
                return score;
            }}

            function search(query) {{
                if (!searchIndex || query.length < 2) {{
                    searchResults.classList.remove('active');
                    return;
                }}
                const results = searchIndex
                    .map(entry => ({{ entry, score: scoreResult(query, entry) }}))
                    .filter(r => r.score > 0)
                    .sort((a, b) => b.score - a.score)
                    .slice(0, 8);

                if (results.length === 0) {{
                    searchResults.innerHTML = '<div class="search-no-results">No results found</div>';
                    searchResults.classList.add('active');
                    return;
                }}

                const html = results.map(r => {{
                    const entry = r.entry;
                    // Convert .md path to .html for static export
                    const htmlPath = entry.path.replace(/\\.md$/, '.html');
                    return `
                        <div class="search-result" data-path="${{htmlPath}}">
                            <div class="search-result-title">${{escapeHtml(entry.title)}}</div>
                            <div class="search-result-path">${{escapeHtml(entry.path)}}</div>
                            <div class="search-result-snippet">${{escapeHtml(entry.snippet || '')}}</div>
                        </div>
                    `;
                }}).join('');

                searchResults.innerHTML = html;
                searchResults.classList.add('active');

                searchResults.querySelectorAll('.search-result').forEach(el => {{
                    el.addEventListener('click', () => {{
                        window.location.href = '{root_path}' + el.dataset.path;
                    }});
                }});
            }}

            function escapeHtml(text) {{
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }}

            let debounceTimer;
            searchInput.addEventListener('input', (e) => {{
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => search(e.target.value.trim()), 150);
            }});

            searchInput.addEventListener('focus', () => {{
                if (searchInput.value.trim().length >= 2) {{
                    search(searchInput.value.trim());
                }}
            }});

            document.addEventListener('click', (e) => {{
                if (!e.target.closest('.search-container')) {{
                    searchResults.classList.remove('active');
                }}
            }});

            searchInput.addEventListener('keydown', (e) => {{
                const results = searchResults.querySelectorAll('.search-result');
                const active = searchResults.querySelector('.search-result:hover, .search-result.active');
                let index = Array.from(results).indexOf(active);

                if (e.key === 'ArrowDown') {{
                    e.preventDefault();
                    index = Math.min(index + 1, results.length - 1);
                    results.forEach((r, i) => r.classList.toggle('active', i === index));
                    if (results[index]) results[index].scrollIntoView({{ block: 'nearest' }});
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    index = Math.max(index - 1, 0);
                    results.forEach((r, i) => r.classList.toggle('active', i === index));
                    if (results[index]) results[index].scrollIntoView({{ block: 'nearest' }});
                }} else if (e.key === 'Enter' && index >= 0) {{
                    e.preventDefault();
                    results[index].click();
                }} else if (e.key === 'Escape') {{
                    searchResults.classList.remove('active');
                    searchInput.blur();
                }}
            }});
        }})();
    </script>
    <script>
        // Theme toggle
        (function() {{
            const themeToggle = document.getElementById('theme-toggle');
            const hljsTheme = document.getElementById('hljs-theme');

            function setTheme(theme) {{
                document.documentElement.setAttribute('data-theme', theme);
                localStorage.setItem('deepwiki-theme', theme);
                themeToggle.innerHTML = theme === 'dark' ? '&#127769;' : '&#9728;';
                if (hljsTheme) {{
                    hljsTheme.href = theme === 'dark'
                        ? 'https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css'
                        : 'https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css';
                }}
            }}

            const savedTheme = localStorage.getItem('deepwiki-theme') || 'dark';
            setTheme(savedTheme);

            themeToggle.addEventListener('click', () => {{
                const current = document.documentElement.getAttribute('data-theme') || 'dark';
                setTheme(current === 'dark' ? 'light' : 'dark');
            }});
        }})();

        // Sidebar toggle for mobile
        (function() {{
            const sidebarToggle = document.getElementById('sidebar-toggle');
            const sidebar = document.querySelector('.sidebar');

            sidebarToggle.addEventListener('click', (e) => {{
                e.stopPropagation();
                sidebar.classList.toggle('open');
            }});

            document.addEventListener('click', (e) => {{
                if (window.innerWidth <= 768 &&
                    !e.target.closest('.sidebar') &&
                    !e.target.closest('.sidebar-toggle')) {{
                    sidebar.classList.remove('open');
                }}
            }});
        }})();

        // Syntax highlighting
        if (typeof hljs !== 'undefined') {{
            hljs.highlightAll();
        }}
    </script>
</body>
</html>"""


def render_markdown(content: str) -> str:
    """Render markdown to HTML."""
    md = markdown.Markdown(extensions=[
        'fenced_code',
        'tables',
        'toc',
        'nl2br',
    ])
    return md.convert(content)


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


class HtmlExporter:
    """Export wiki markdown to static HTML files."""

    def __init__(self, wiki_path: Path, output_path: Path):
        """Initialize the exporter.

        Args:
            wiki_path: Path to the .deepwiki directory
            output_path: Output directory for HTML files
        """
        self.wiki_path = Path(wiki_path)
        self.output_path = Path(output_path)
        self.toc_entries: list[dict] = []

    def export(self) -> int:
        """Export all wiki pages to HTML.

        Returns:
            Number of pages exported
        """
        # Load TOC
        toc_path = self.wiki_path / "toc.json"
        if toc_path.exists():
            toc_data = json.loads(toc_path.read_text())
            self.toc_entries = toc_data.get("entries", [])

        # Create output directory
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Copy search.json
        search_src = self.wiki_path / "search.json"
        if search_src.exists():
            shutil.copy(search_src, self.output_path / "search.json")

        # Find and export all markdown files
        exported = 0
        for md_file in self.wiki_path.rglob("*.md"):
            rel_path = md_file.relative_to(self.wiki_path)
            self._export_page(md_file, rel_path)
            exported += 1

        return exported

    def _export_page(self, md_file: Path, rel_path: Path) -> None:
        """Export a single markdown page to HTML.

        Args:
            md_file: Path to the markdown file
            rel_path: Relative path from wiki root
        """
        # Read and convert markdown
        content = md_file.read_text()
        html_content = render_markdown(content)
        title = extract_title(md_file)

        # Calculate depth for relative paths
        depth = len(rel_path.parts) - 1
        root_path = "../" * depth if depth > 0 else "./"

        # Build TOC HTML with correct relative paths
        toc_html = self._render_toc(self.toc_entries, str(rel_path), root_path)

        # Build breadcrumb HTML
        breadcrumb_html = self._build_breadcrumb(rel_path, root_path)

        # Calculate search.json path relative to this page
        search_json_path = root_path + "search.json"

        # Render full HTML
        html = STATIC_HTML_TEMPLATE.format(
            title=title,
            toc_html=toc_html,
            breadcrumb_html=breadcrumb_html,
            content_html=html_content,
            search_json_path=search_json_path,
            root_path=root_path,
        )

        # Write output file
        output_file = self.output_path / rel_path.with_suffix(".html")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html)

    def _render_toc(self, entries: list[dict], current_path: str, root_path: str) -> str:
        """Render TOC entries as HTML.

        Args:
            entries: List of TOC entry dicts
            current_path: Current page path for highlighting active link
            root_path: Relative path to root (e.g., "../")

        Returns:
            HTML string for TOC
        """
        html_parts = []
        for entry in entries:
            html_parts.append(self._render_toc_entry(entry, current_path, root_path))
        return "\n".join(html_parts)

    def _render_toc_entry(self, entry: dict, current_path: str, root_path: str) -> str:
        """Render a single TOC entry recursively.

        Args:
            entry: TOC entry dict with number, title, path, children
            current_path: Current page path
            root_path: Relative path to root

        Returns:
            HTML string for this entry
        """
        has_children = bool(entry.get("children"))
        parent_class = "toc-parent" if has_children else ""

        html = f'<div class="toc-item {parent_class}">'

        if entry.get("path"):
            # Convert .md to .html for static export
            html_path = entry["path"].replace(".md", ".html")
            active = "active" if entry["path"] == current_path else ""
            html += f'''<a href="{root_path}{html_path}" class="{active}">
                <span class="toc-number">{entry.get("number", "")}</span>
                <span>{entry.get("title", "")}</span>
            </a>'''
        else:
            # No link, just a grouping label
            html += f'''<span class="toc-parent">
                <span class="toc-number">{entry.get("number", "")}</span>
                <span>{entry.get("title", "")}</span>
            </span>'''

        if has_children:
            html += '<div class="toc-nested">'
            for child in entry["children"]:
                html += self._render_toc_entry(child, current_path, root_path)
            html += '</div>'

        html += '</div>'
        return html

    def _build_breadcrumb(self, rel_path: Path, root_path: str) -> str:
        """Build breadcrumb navigation HTML.

        Args:
            rel_path: Relative path of current page
            root_path: Relative path to root

        Returns:
            HTML string for breadcrumb, or empty string if root page
        """
        parts = list(rel_path.parts)

        # Root pages don't need breadcrumbs
        if len(parts) == 1:
            return ""

        breadcrumb_items = []

        # Always start with Home
        breadcrumb_items.append(f'<a href="{root_path}index.html">Home</a>')

        # Build path progressively
        cumulative_path = ""
        for part in parts[:-1]:  # Exclude current page
            if cumulative_path:
                cumulative_path = f"{cumulative_path}/{part}"
            else:
                cumulative_path = part

            # Check if there's an index.md in this folder
            index_path = self.wiki_path / cumulative_path / "index.md"
            display_name = part.replace("_", " ").replace("-", " ").title()

            if index_path.exists():
                link_path = f"{cumulative_path}/index.html"
                breadcrumb_items.append(f'<a href="{root_path}{link_path}">{display_name}</a>')
            else:
                breadcrumb_items.append(f'<span>{display_name}</span>')

        # Add current page name
        current_page = parts[-1]
        if current_page.endswith('.md'):
            current_page = current_page[:-3]
        current_page = current_page.replace("_", " ").replace("-", " ").title()
        breadcrumb_items.append(f'<span class="current">{current_page}</span>')

        return '<div class="breadcrumb">' + \
            ' <span class="separator">&rsaquo;</span> '.join(breadcrumb_items) + \
            '</div>'


def export_to_html(wiki_path: str | Path, output_path: str | Path | None = None) -> str:
    """Export wiki to static HTML files.

    Args:
        wiki_path: Path to the .deepwiki directory
        output_path: Output directory (default: {wiki_path}_html)

    Returns:
        Path to the output directory
    """
    wiki_path = Path(wiki_path)
    if output_path is None:
        output_path = wiki_path.parent / f"{wiki_path.name}_html"
    else:
        output_path = Path(output_path)

    exporter = HtmlExporter(wiki_path, output_path)
    count = exporter.export()

    return f"Exported {count} pages to {output_path}"


def main():
    """CLI entry point for HTML export."""
    parser = argparse.ArgumentParser(
        description="Export DeepWiki documentation to static HTML"
    )
    parser.add_argument(
        "wiki_path",
        nargs="?",
        default=".deepwiki",
        help="Path to the .deepwiki directory (default: .deepwiki)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output directory (default: {wiki_path}_html)"
    )

    args = parser.parse_args()

    wiki_path = Path(args.wiki_path).resolve()
    if not wiki_path.exists():
        print(f"Error: Wiki path does not exist: {wiki_path}")
        return 1

    output_path = Path(args.output).resolve() if args.output else None

    result = export_to_html(wiki_path, output_path)
    print(result)

    # Print location hint
    actual_output = output_path or (wiki_path.parent / f"{wiki_path.name}_html")
    print(f"\nOpen {actual_output}/index.html in a browser to view the documentation.")

    return 0


if __name__ == "__main__":
    exit(main())
