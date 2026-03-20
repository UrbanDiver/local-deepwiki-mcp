"""Tests for the Design Smells wiki page renderer."""

from __future__ import annotations

from local_deepwiki.generators.analysis.smells_page import generate_smells_page


def _make_smell(
    smell_type: str = "god_class",
    severity: str = "high",
    file: str = "a.py",
    line: int = 49,
    entity: str = "BigClass",
    description: str = "25 methods",
    suggestion: str = "Split it",
) -> dict:
    return {
        "type": smell_type,
        "severity": severity,
        "file": file,
        "line": line,
        "entity": entity,
        "description": description,
        "suggestion": suggestion,
    }


def _make_data(
    smells: list[dict] | None = None,
    summary: dict | None = None,
) -> dict:
    if smells is None:
        smells = [_make_smell()]
    if summary is None:
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for s in smells:
            by_severity[s["severity"]] = by_severity.get(s["severity"], 0) + 1
            by_type[s["type"]] = by_type.get(s["type"], 0) + 1
        summary = {
            "total": len(smells),
            "by_severity": by_severity,
            "by_type": by_type,
        }
    return {"smells": smells, "summary": summary}


def test_returns_markdown_with_title():
    result = generate_smells_page(_make_data())
    assert result is not None
    assert "# Design Smells" in result


def test_groups_smells_by_type_into_sections():
    smells = [
        _make_smell(smell_type="god_class", entity="BigClass"),
        _make_smell(smell_type="long_method", entity="do_everything"),
        _make_smell(smell_type="long_method", entity="process_all"),
        _make_smell(smell_type="deep_nesting", entity="nested_func"),
    ]
    result = generate_smells_page(_make_data(smells=smells))
    assert result is not None
    assert "## God Class" in result
    assert "## Long Method" in result
    assert "## Deep Nesting" in result


def test_includes_severity_summary():
    smells = [
        _make_smell(severity="high"),
        _make_smell(severity="medium", smell_type="long_method", entity="func1"),
        _make_smell(severity="medium", smell_type="large_file", entity="big.py"),
        _make_smell(severity="low", smell_type="data_clump", entity="a, b, c"),
    ]
    result = generate_smells_page(_make_data(smells=smells))
    assert result is not None
    # Total count
    assert "4" in result
    # Severity breakdown
    assert "high" in result.lower()
    assert "medium" in result.lower()
    assert "low" in result.lower()


def test_includes_entity_name_and_file_in_output():
    smells = [
        _make_smell(
            entity="MyGodClass",
            file="core/engine.py",
            line=42,
            description="30 methods and 900 lines",
            suggestion="Apply SRP",
        ),
    ]
    result = generate_smells_page(_make_data(smells=smells))
    assert result is not None
    assert "MyGodClass" in result
    assert "core/engine.py" in result
    assert "30 methods and 900 lines" in result
    assert "Apply SRP" in result


def test_returns_none_for_empty_smells():
    result = generate_smells_page(_make_data(smells=[]))
    assert result is None


def test_returns_none_when_smells_key_missing():
    result = generate_smells_page({})
    assert result is None


def test_handles_single_smell_type_correctly():
    smells = [
        _make_smell(smell_type="feature_envy", entity="func_a", file="x.py"),
        _make_smell(smell_type="feature_envy", entity="func_b", file="y.py"),
    ]
    result = generate_smells_page(_make_data(smells=smells))
    assert result is not None
    assert "## Feature Envy" in result
    # Should not contain sections for other types
    assert "## God Class" not in result
    assert "## Long Method" not in result
    # Both entities present in the table
    assert "func_a" in result
    assert "func_b" in result


def test_summary_table_has_type_counts():
    smells = [
        _make_smell(smell_type="god_class", entity="A"),
        _make_smell(smell_type="god_class", entity="B"),
        _make_smell(smell_type="long_method", entity="C"),
    ]
    result = generate_smells_page(_make_data(smells=smells))
    assert result is not None
    # The summary table should show type names and counts
    assert "God Class" in result
    assert "Long Method" in result


def test_type_names_are_formatted_nicely():
    smells = [
        _make_smell(smell_type="long_parameter_list", entity="func1"),
        _make_smell(smell_type="data_clump", entity="a, b"),
    ]
    result = generate_smells_page(_make_data(smells=smells))
    assert result is not None
    assert "Long Parameter List" in result
    assert "Data Clump" in result


def test_smell_table_has_correct_columns():
    result = generate_smells_page(_make_data())
    assert result is not None
    assert "| Entity |" in result
    assert "| File |" in result
    assert "| Severity |" in result
    assert "| Description |" in result
    assert "| Suggestion |" in result
