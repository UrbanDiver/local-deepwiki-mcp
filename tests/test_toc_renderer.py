"""Tests for extracted TOC renderer."""

from __future__ import annotations


def test_render_toc_html_empty():
    from local_deepwiki.export.toc_renderer import render_toc_html

    result = render_toc_html([])
    assert '<div class="toc">' in result
    assert "</div>" in result


def test_render_toc_html_flat_entries():
    from local_deepwiki.export.toc_renderer import render_toc_html

    entries = [
        {"title": "Introduction"},
        {"title": "Setup"},
    ]
    result = render_toc_html(entries)
    assert "Introduction" in result
    assert "Setup" in result


def test_render_toc_html_nested_entries():
    from local_deepwiki.export.toc_renderer import render_toc_html

    entries = [
        {
            "title": "Chapter 1",
            "children": [
                {"title": "Section 1.1"},
                {"title": "Section 1.2"},
            ],
        },
    ]
    result = render_toc_html(entries)
    assert "Chapter 1" in result
    assert "Section 1.1" in result
    assert "Section 1.2" in result


def test_render_toc_html_deep_nesting():
    from local_deepwiki.export.toc_renderer import render_toc_html

    entries = [
        {
            "title": "L0",
            "children": [
                {
                    "title": "L1",
                    "children": [{"title": "L2"}],
                },
            ],
        },
    ]
    result = render_toc_html(entries)
    assert "L0" in result
    assert "L1" in result
    assert "L2" in result
