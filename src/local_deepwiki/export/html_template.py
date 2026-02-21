from __future__ import annotations

"""Static HTML template for DeepWiki HTML export."""

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
        // securityLevel: 'strict' prevents XSS from user-controlled diagram content
        mermaid.initialize({{
            startOnLoad: false,
            securityLevel: 'strict',
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
                .then(data => {{ searchIndex = data.pages || data; }})
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
