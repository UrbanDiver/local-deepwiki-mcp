"""Tests for the Complexity Hotspots wiki page renderer."""

from __future__ import annotations

from local_deepwiki.generators.analysis.hotspots_page import generate_hotspots_page


def _make_hotspot(
    function: str = "foo",
    file: str = "a.py",
    line: int = 10,
    metric_value: int = 33,
    cyclomatic: int = 33,
    params: int = 4,
    length: int = 118,
    nesting: int = 0,
) -> dict:
    return {
        "function": function,
        "file": file,
        "line": line,
        "metric_value": metric_value,
        "details": {
            "cyclomatic": cyclomatic,
            "params": params,
            "length": length,
            "nesting": nesting,
        },
    }


def _make_data(hotspots: list[dict] | None = None, stats: dict | None = None) -> dict:
    return {
        "hotspots": hotspots if hotspots is not None else [_make_hotspot()],
        "stats": stats
        if stats is not None
        else {
            "total_functions": 1946,
            "files_scanned": 242,
            "metric_used": "complexity",
        },
    }


def test_returns_markdown_with_title_and_table_headers():
    result = generate_hotspots_page(_make_data())
    assert result is not None
    assert "# Complexity Hotspots" in result
    assert "| Rank |" in result
    assert "| Function |" in result
    assert "| File |" in result
    assert "| CC |" in result
    assert "| Lines |" in result
    assert "| Params |" in result
    assert "| Nesting |" in result


def test_includes_function_name_and_file_in_output():
    data = _make_data(
        hotspots=[
            _make_hotspot(function="process_data", file="core/engine.py", line=42)
        ]
    )
    result = generate_hotspots_page(data)
    assert result is not None
    assert "`process_data`" in result
    assert "`core/engine.py:42`" in result


def test_returns_none_for_empty_hotspots():
    data = _make_data(hotspots=[])
    result = generate_hotspots_page(data)
    assert result is None


def test_stats_section_present():
    data = _make_data(
        stats={
            "total_functions": 500,
            "files_scanned": 80,
            "metric_used": "length",
        }
    )
    result = generate_hotspots_page(data)
    assert result is not None
    assert "500" in result
    assert "length" in result


def test_ranks_are_numbered_correctly():
    hotspots = [
        _make_hotspot(function=f"func_{i}", metric_value=100 - i) for i in range(5)
    ]
    data = _make_data(hotspots=hotspots)
    result = generate_hotspots_page(data)
    assert result is not None
    lines = result.split("\n")
    table_rows = [ln for ln in lines if ln.startswith("| ") and "func_" in ln]
    assert len(table_rows) == 5
    for idx, row in enumerate(table_rows, start=1):
        assert row.startswith(f"| {idx} ")


def test_limits_to_top_20():
    hotspots = [
        _make_hotspot(function=f"func_{i}", metric_value=100 - i) for i in range(30)
    ]
    data = _make_data(hotspots=hotspots)
    result = generate_hotspots_page(data)
    assert result is not None
    lines = result.split("\n")
    table_rows = [ln for ln in lines if ln.startswith("| ") and "func_" in ln]
    assert len(table_rows) == 20


def test_returns_none_when_hotspots_key_missing():
    result = generate_hotspots_page({})
    assert result is None


def test_handles_missing_stats_gracefully():
    data = {"hotspots": [_make_hotspot()]}
    result = generate_hotspots_page(data)
    assert result is not None
    assert "# Complexity Hotspots" in result
