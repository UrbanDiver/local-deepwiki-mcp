"""Tests for the recommendations generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest


def _make_health_data(
    *,
    hotspots: list[dict[str, Any]] | None = None,
    smells: list[dict[str, Any]] | None = None,
    god_classes: list[dict[str, Any]] | None = None,
    layer_violations: list[dict[str, Any]] | None = None,
    coupling_metrics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal health_data dict for testing."""
    data: dict[str, Any] = {
        "status": "success",
        "overall": {"grade": "B", "score": 75},
        "top_findings": {
            "hotspots": hotspots or [],
            "high_severity_smells": smells or [],
            "god_classes": god_classes or [],
            "layer_violations": layer_violations or [],
        },
        "stats": {
            "total_lines": 1000,
            "total_functions": 50,
            "files_scanned": 10,
            "total_modules": 5,
            "total_smells": len(smells or []) + len(god_classes or []),
        },
    }
    if coupling_metrics is not None:
        data["_coupling_metrics"] = coupling_metrics
    return data


def test_recommendations_from_god_class() -> None:
    """God class findings produce 'Split class' recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        god_classes=[
            {
                "type": "god_class",
                "severity": "high",
                "file": "src/big.py",
                "line": 1,
                "entity": "BigClass",
                "description": "Class has too many methods.",
            }
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    assert result["status"] == "success"
    recs = result["recommendations"]
    assert len(recs) >= 1

    god_rec = recs[0]
    assert "Split BigClass" in god_rec["title"]
    assert god_rec["category"] == "smells"
    assert god_rec["effort"] == "medium"
    assert god_rec["impact"] == "high"
    assert god_rec["file"] == "src/big.py"
    assert god_rec["line"] == 1


def test_recommendations_from_long_method() -> None:
    """Long method findings produce 'Extract helpers' recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        smells=[
            {
                "type": "long_method",
                "severity": "high",
                "file": "src/handler.py",
                "line": 42,
                "entity": "process_request",
                "description": "Method is 200 lines long.",
            }
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    recs = result["recommendations"]
    assert len(recs) >= 1

    lm_rec = recs[0]
    assert "Extract helpers from process_request" in lm_rec["title"]
    assert lm_rec["category"] == "complexity"
    assert lm_rec["effort"] == "low"
    assert lm_rec["impact"] == "high"


def test_recommendations_sorted_by_priority() -> None:
    """Recommendations are sorted by priority descending."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        smells=[
            {
                "type": "long_method",
                "severity": "high",
                "file": "src/a.py",
                "line": 1,
                "entity": "func_a",
                "description": "",
            },
            {
                "type": "long_parameter_list",
                "severity": "high",
                "file": "src/b.py",
                "line": 10,
                "entity": "func_b",
                "description": "",
            },
        ],
        god_classes=[
            {
                "type": "god_class",
                "severity": "high",
                "file": "src/c.py",
                "line": 1,
                "entity": "GodClass",
                "description": "",
            },
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    recs = result["recommendations"]
    assert len(recs) >= 3

    priorities = [r["priority"] for r in recs]
    assert priorities == sorted(priorities, reverse=True)


def test_recommendations_max_items() -> None:
    """max_items limits the number of returned recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    # Create many smells to exceed limit.
    smells = [
        {
            "type": "long_method",
            "severity": "high",
            "file": f"src/mod_{i}.py",
            "line": i,
            "entity": f"func_{i}",
            "description": "",
        }
        for i in range(20)
    ]

    health = _make_health_data(smells=smells)

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
        max_items=5,
    )

    assert len(result["recommendations"]) == 5
    assert result["stats"]["total_findings"] == 20
    assert result["stats"]["returned"] == 5


def test_recommendations_category_filter() -> None:
    """category_filter restricts results to a single category."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        smells=[
            {
                "type": "long_method",
                "severity": "high",
                "file": "src/a.py",
                "line": 1,
                "entity": "func_a",
                "description": "",
            },
        ],
        god_classes=[
            {
                "type": "god_class",
                "severity": "high",
                "file": "src/b.py",
                "line": 1,
                "entity": "BigClass",
                "description": "",
            },
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
        category_filter="smells",
    )

    recs = result["recommendations"]
    assert len(recs) >= 1
    assert all(r["category"] == "smells" for r in recs)
    assert result["stats"]["category"] == "smells"


def test_recommendations_empty_health() -> None:
    """Empty findings produce an empty recommendations list."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data()

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    assert result["status"] == "success"
    assert result["recommendations"] == []
    assert result["stats"]["total_findings"] == 0
    assert result["stats"]["returned"] == 0


def test_recommendations_reuses_health_data() -> None:
    """Passing health_data avoids calling analyze_architecture_health."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        smells=[
            {
                "type": "long_method",
                "severity": "high",
                "file": "src/x.py",
                "line": 5,
                "entity": "do_stuff",
                "description": "",
            },
        ],
    )

    # Path("/fake") does not exist.  If health_data were None, the function
    # would call analyze_architecture_health and fail on the missing path.
    # The fact that this succeeds proves health_data is reused.
    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    assert result["status"] == "success"
    assert len(result["recommendations"]) == 1


async def test_enrich_adds_enriched_description() -> None:
    """enrich_recommendations adds an enriched_description via the LLM."""
    from local_deepwiki.generators.analysis.recommendations import (
        enrich_recommendations,
    )

    recs = [
        {
            "title": "Split BigClass into focused components",
            "category": "smells",
            "description": "Class has too many methods.",
            "file": "src/big.py",
            "line": 1,
            "effort": "medium",
            "impact": "high",
            "priority": 1.5,
        },
    ]

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "This class handles too many concerns."

    enriched = await enrich_recommendations(recs, mock_llm)

    assert len(enriched) == 1
    assert (
        enriched[0]["enriched_description"] == "This class handles too many concerns."
    )
    # Original dict must not have been mutated.
    assert "enriched_description" not in recs[0]
    # All original fields are preserved.
    assert enriched[0]["title"] == recs[0]["title"]
    assert enriched[0]["category"] == recs[0]["category"]


async def test_enrich_handles_llm_failure_gracefully() -> None:
    """When the LLM fails for an item, the original rec is kept without enrichment."""
    from local_deepwiki.generators.analysis.recommendations import (
        enrich_recommendations,
    )

    recs = [
        {
            "title": "Fix something",
            "category": "layers",
            "description": "A layer violation.",
            "file": "src/x.py",
            "line": 0,
            "effort": "low",
            "impact": "high",
            "priority": 3.0,
        },
    ]

    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = RuntimeError("LLM unavailable")

    enriched = await enrich_recommendations(recs, mock_llm)

    assert len(enriched) == 1
    assert "enriched_description" not in enriched[0]
    assert enriched[0]["title"] == "Fix something"
    # Original must not be mutated.
    assert "enriched_description" not in recs[0]


def test_recommendations_from_coupling_high_distance() -> None:
    """Coupling metrics with distance > 0.7 produce recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        coupling_metrics=[
            {
                "module": "core.parser",
                "distance": 0.9,
                "instability": 0.8,
                "abstractness": 0.1,
            },
            {
                "module": "core.indexer",
                "distance": 0.3,
                "instability": 0.5,
                "abstractness": 0.2,
            },
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    recs = result["recommendations"]
    assert len(recs) == 1
    assert "core.parser" in recs[0]["title"]
    assert recs[0]["category"] == "coupling"


def test_recommendations_from_layer_violations() -> None:
    """Layer violations produce 'Fix upward dependency' recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        layer_violations=[
            {
                "from_layer": "handlers",
                "to_layer": "server",
                "file": "src/handlers/foo.py",
                "import_module": "server",
            },
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    recs = result["recommendations"]
    assert len(recs) == 1
    assert "Fix upward dependency" in recs[0]["title"]
    assert "handlers" in recs[0]["title"]
    assert "server" in recs[0]["title"]
    assert recs[0]["category"] == "layers"
    assert recs[0]["effort"] == "low"
    assert recs[0]["impact"] == "high"


def test_recommendations_from_hotspots_high_cc() -> None:
    """Hotspots with CC > 15 produce 'Reduce complexity' recommendations."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    health = _make_health_data(
        hotspots=[
            {
                "function": "complex_func",
                "file": "src/core.py",
                "line": 10,
                "details": {"cyclomatic": 25, "length": 100},
            },
            {
                "function": "simple_func",
                "file": "src/utils.py",
                "line": 5,
                "details": {"cyclomatic": 5, "length": 20},
            },
        ],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    recs = result["recommendations"]
    assert len(recs) == 1
    assert "complex_func" in recs[0]["title"]
    assert recs[0]["category"] == "complexity"


def test_recommendations_deduplicates() -> None:
    """Duplicate findings by (file, line, category) are removed."""
    from local_deepwiki.generators.analysis.recommendations import (
        generate_recommendations,
    )

    # Same file/line/category from both god_classes and high_severity_smells.
    smell = {
        "type": "god_class",
        "severity": "high",
        "file": "src/big.py",
        "line": 1,
        "entity": "BigClass",
        "description": "Too many methods.",
    }

    health = _make_health_data(
        god_classes=[smell],
        smells=[smell],
    )

    result = generate_recommendations(
        Path("/fake"),
        health_data=health,
    )

    recs = result["recommendations"]
    # Should be deduplicated to 1, not 2.
    assert len(recs) == 1
