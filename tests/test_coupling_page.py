"""Tests for the Coupling Metrics wiki page renderer."""

from __future__ import annotations

from local_deepwiki.generators.analysis.coupling_page import generate_coupling_page


def _make_module(
    module: str = "core.indexer",
    afferent_coupling: int = 5,
    efferent_coupling: int = 3,
    instability: float = 0.375,
    abstractness: float = 0.0,
    distance: float = 0.625,
) -> dict:
    return {
        "module": module,
        "afferent_coupling": afferent_coupling,
        "efferent_coupling": efferent_coupling,
        "instability": instability,
        "abstractness": abstractness,
        "distance": distance,
    }


def _make_data(
    metrics: list[dict] | None = None,
    stats: dict | None = None,
) -> dict:
    if metrics is None:
        metrics = [_make_module()]
    if stats is None:
        total = len(metrics)
        avg_dist = (
            round(sum(m["distance"] for m in metrics) / total, 4) if total else 0.0
        )
        stats = {
            "total_modules": total,
            "avg_instability": 0.5,
            "avg_abstractness": 0.1,
        }
    return {"status": "success", "metrics": metrics, "stats": stats}


def test_returns_markdown_with_title_and_table():
    result = generate_coupling_page(_make_data())
    assert result is not None
    assert "# Coupling Metrics" in result
    # Should have a markdown table
    assert "| Module |" in result


def test_includes_module_name_in_output():
    metrics = [_make_module(module="generators.wiki")]
    result = generate_coupling_page(_make_data(metrics=metrics))
    assert result is not None
    assert "generators.wiki" in result


def test_table_has_coupling_columns():
    result = generate_coupling_page(_make_data())
    assert result is not None
    assert "| Ca |" in result or "Ca" in result
    assert "| Ce |" in result or "Ce" in result
    assert "| I |" in result
    assert "| A |" in result
    assert "| D |" in result


def test_returns_none_for_empty_metrics():
    result = generate_coupling_page(_make_data(metrics=[]))
    assert result is None


def test_returns_none_when_metrics_key_missing():
    result = generate_coupling_page({"status": "success"})
    assert result is None


def test_highlights_distant_modules():
    metrics = [
        _make_module(
            module="core.parser", distance=0.85, instability=0.1, abstractness=0.05
        ),
        _make_module(
            module="core.indexer", distance=0.45, instability=0.5, abstractness=0.05
        ),
        _make_module(
            module="web.app", distance=0.75, instability=0.9, abstractness=0.15
        ),
    ]
    result = generate_coupling_page(_make_data(metrics=metrics))
    assert result is not None
    # Should have a section highlighting modules far from main sequence
    assert "core.parser" in result
    assert "web.app" in result
    # Check for highlight section header
    assert "Far from Main Sequence" in result or "Distant" in result


def test_includes_summary_stats():
    metrics = [
        _make_module(module="a", distance=0.5),
        _make_module(module="b", distance=0.3),
        _make_module(module="c", distance=0.8),
    ]
    stats = {
        "total_modules": 3,
        "avg_instability": 0.4,
        "avg_abstractness": 0.1,
    }
    result = generate_coupling_page(_make_data(metrics=metrics, stats=stats))
    assert result is not None
    # Should include total modules count
    assert "3" in result


def test_includes_explanation_paragraph():
    result = generate_coupling_page(_make_data())
    assert result is not None
    # Should mention key concepts
    assert "afferent" in result.lower() or "Ca" in result
    assert "efferent" in result.lower() or "Ce" in result
    assert "instability" in result.lower()
    assert "main sequence" in result.lower()


def test_table_sorted_by_distance_descending():
    metrics = [
        _make_module(module="low_dist", distance=0.1),
        _make_module(module="high_dist", distance=0.9),
        _make_module(module="mid_dist", distance=0.5),
    ]
    result = generate_coupling_page(_make_data(metrics=metrics))
    assert result is not None
    # high_dist should appear before mid_dist which should appear before low_dist
    high_pos = result.index("high_dist")
    mid_pos = result.index("mid_dist")
    low_pos = result.index("low_dist")
    assert high_pos < mid_pos < low_pos


def test_no_highlight_section_when_no_distant_modules():
    metrics = [
        _make_module(module="stable_a", distance=0.2),
        _make_module(module="stable_b", distance=0.3),
    ]
    result = generate_coupling_page(_make_data(metrics=metrics))
    assert result is not None
    assert "Far from Main Sequence" not in result
