"""PDF style constants for DeepWiki documentation export.

Contains the print-optimized CSS and HTML template used by the PDF
exporter to render wiki pages.
"""

from __future__ import annotations

# Print-optimized CSS for PDF output
PRINT_CSS = """
@page {
    size: letter;
    margin: 1in 0.75in;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 10pt;
        color: #666;
    }
    @top-center {
        content: string(doctitle);
        font-size: 10pt;
        color: #666;
    }
}

@page :first {
    @top-center {
        content: none;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1f2328;
    background: white;
    max-width: 100%;
}

h1 {
    string-set: doctitle content();
    font-size: 24pt;
    font-weight: 600;
    color: #1f2328;
    margin: 0 0 0.5em 0;
    padding-bottom: 0.3em;
    border-bottom: 1px solid #d0d7de;
    page-break-after: avoid;
}

h2 {
    font-size: 18pt;
    font-weight: 600;
    color: #1f2328;
    margin: 1.5em 0 0.5em 0;
    padding-bottom: 0.2em;
    border-bottom: 1px solid #d0d7de;
    page-break-after: avoid;
}

h3 {
    font-size: 14pt;
    font-weight: 600;
    color: #1f2328;
    margin: 1.2em 0 0.4em 0;
    page-break-after: avoid;
}

h4, h5, h6 {
    font-size: 12pt;
    font-weight: 600;
    color: #1f2328;
    margin: 1em 0 0.3em 0;
    page-break-after: avoid;
}

p {
    margin: 0.8em 0;
    orphans: 3;
    widows: 3;
}

a {
    color: #0969da;
    text-decoration: none;
}

code {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 9pt;
    background: #f6f8fa;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}

pre {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 9pt;
    background: #f6f8fa;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    line-height: 1.45;
    page-break-inside: avoid;
    margin: 1em 0;
}

pre code {
    background: none;
    padding: 0;
    border-radius: 0;
}

blockquote {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 4px solid #d0d7de;
    color: #656d76;
    background: #f6f8fa;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    page-break-inside: avoid;
}

th, td {
    border: 1px solid #d0d7de;
    padding: 8px 12px;
    text-align: left;
}

th {
    background: #f6f8fa;
    font-weight: 600;
}

tr:nth-child(even) {
    background: #f6f8fa;
}

ul, ol {
    margin: 0.8em 0;
    padding-left: 2em;
}

li {
    margin: 0.3em 0;
}

hr {
    border: none;
    border-top: 1px solid #d0d7de;
    margin: 2em 0;
}

img {
    max-width: 100%;
    height: auto;
}

.page-break {
    page-break-before: always;
}

.toc-title {
    font-size: 18pt;
    font-weight: 600;
    margin-bottom: 1em;
}

.toc-item {
    margin: 0.3em 0;
}

.toc-item a {
    color: #1f2328;
}

.toc-section {
    margin-left: 1.5em;
}

.mermaid-note {
    background: #fff8c5;
    border: 1px solid #d4a72c;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 10pt;
    color: #6e5a00;
    margin: 1em 0;
}

.mermaid-diagram {
    margin: 1em 0;
    text-align: center;
    page-break-inside: avoid;
}

.mermaid-diagram svg {
    max-width: 100%;
    height: auto;
}
"""

# HTML template for PDF generation
PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
{content}
</body>
</html>
"""
