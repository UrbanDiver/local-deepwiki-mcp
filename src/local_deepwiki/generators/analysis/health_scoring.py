"""Health scoring — converts raw architecture metrics into scores and grades.

Provides dimension-level scores (0-100) and an overall letter grade (A-F).
No I/O — pure computation on metric summaries.
"""

from __future__ import annotations

from typing import Any

# Letter grade thresholds
_GRADE_THRESHOLDS: tuple[tuple[str, int], ...] = (
    ("A", 90),
    ("B", 75),
    ("C", 60),
    ("D", 40),
    ("F", 0),
)

# Weights for overall score
_DIMENSION_WEIGHTS: dict[str, float] = {
    "complexity": 0.15,
    "coupling": 0.12,
    "smells": 0.12,
    "layers": 0.09,
    "churn": 0.12,
    "cohesion": 0.12,
    "duplication": 0.10,
    "testability": 0.10,
    "maintainability": 0.08,
}


def letter_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    for grade, threshold in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def score_complexity(
    hotspots: list[dict[str, Any]],
    total_functions: int,
) -> dict[str, Any]:
    """Score complexity dimension (0-100).

    Factors:
    - Max cyclomatic complexity (lower is better)
    - % of functions above CC=15 (lower is better)
    """
    if total_functions == 0:
        return {"score": 100, "grade": "A", "factors": {}}

    cc_values = [h["metric_value"] for h in hotspots if "metric_value" in h]
    max_cc = max(cc_values) if cc_values else 0
    high_cc_count = sum(1 for h in hotspots if h.get("metric_value", 0) > 15)
    high_cc_pct = (high_cc_count / total_functions) * 100 if total_functions > 0 else 0

    # Score: start at 100, deduct for high CC
    score = 100.0
    if max_cc > 50:
        score -= 30
    elif max_cc > 30:
        score -= 20
    elif max_cc > 15:
        score -= 10

    # Deduct for % of functions over CC=15
    score -= min(high_cc_pct * 5, 40)  # cap at 40 point deduction

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "max_cyclomatic": max_cc,
            "functions_over_cc15": high_cc_count,
            "pct_over_cc15": round(high_cc_pct, 1),
        },
    }


def score_coupling(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Score coupling dimension (0-100).

    Factors:
    - Average distance from main sequence (lower is better)
    - Percentage of problematic unstable modules

    Highly unstable modules are only flagged when they have Ca=0 (nothing
    depends on them) AND high Ce — these are disconnected modules that
    import a lot but provide no value to the rest of the system. Edge
    modules with Ca>0 (handlers that are imported by __init__.py, services
    used by handlers) are expected to be unstable and are not penalized.
    """
    if not metrics:
        return {"score": 100, "grade": "A", "factors": {}}

    distances = [m.get("distance", 0) for m in metrics]
    avg_distance = sum(distances) / len(distances) if distances else 0
    # Only flag modules that are fully disconnected (Ca=0) with high outgoing deps
    highly_unstable = sum(
        1
        for m in metrics
        if m.get("instability", 0) > 0.8
        and m.get("efferent_coupling", 0) > 5
        and m.get("afferent_coupling", 0) == 0
    )
    unstable_pct = (highly_unstable / len(metrics)) * 100 if metrics else 0

    score = 100.0
    score -= min(avg_distance * 30, 25)  # avg distance penalty, cap 25
    score -= min(unstable_pct * 2, 25)  # disconnected unstable % penalty, cap 25

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "avg_distance": round(avg_distance, 3),
            "highly_unstable_modules": highly_unstable,
            "unstable_pct": round(unstable_pct, 1),
            "total_modules": len(metrics),
        },
    }


def score_smells(
    smells: list[dict[str, Any]],
    total_lines: int,
) -> dict[str, Any]:
    """Score design smells dimension (0-100).

    Factors:
    - Smell density: smells per 1000 lines, weighted by severity
    - God class count (high-impact)
    """
    if total_lines == 0:
        return {"score": 100, "grade": "A", "factors": {}}

    severity_weights = {"high": 3, "medium": 1, "low": 0.5}
    weighted_count = sum(severity_weights.get(s.get("severity", "medium"), 1) for s in smells)
    density = (weighted_count / total_lines) * 1000
    god_classes = sum(1 for s in smells if s.get("type") == "god_class")

    score = 100.0
    score -= min(density * 8, 80)  # density penalty, cap 80
    score -= min(god_classes * 10, 35)  # god class penalty, cap 35

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "total_smells": len(smells),
            "weighted_density_per_1k": round(density, 2),
            "god_classes": god_classes,
        },
    }


def score_layers(violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Score layer discipline dimension (0-100).

    Simple: 100 minus 10 per violation, floor 0.
    """
    count = len(violations)
    score = max(0.0, 100.0 - count * 10)
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "total_violations": count,
        },
    }


def score_churn(
    composite: list[dict[str, Any]],
    *,
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Score churn dimension (0-100).

    Factors:
    - Count of files with composite > 0.5 (high churn AND high complexity)
    - Gini coefficient of churn distribution (concentration)
    """
    if not composite and not stats:
        return {"score": 100, "grade": "A", "factors": {}}

    high_risk = sum(1 for c in composite if c.get("composite", 0) > 0.5)
    total_files = stats.get("total_files", 0) or 1
    high_risk_pct = (high_risk / total_files) * 100
    gini = stats.get("gini_coefficient", 0.0)

    score = 100.0
    # High-churn+complex files: up to 40 point deduction
    score -= min(high_risk_pct * 4, 40)
    # Churn concentration (Gini): up to 15 point deduction
    if gini > 0.6:
        score -= min((gini - 0.6) * 37.5, 15)

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "high_churn_complex_files": high_risk,
            "churn_concentration": round(gini, 4),
            "total_files": stats.get("total_files", 0),
        },
    }


def score_cohesion(
    class_cohesion: list[dict[str, Any]],
    module_cohesion: list[dict[str, Any]],
    *,
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Score cohesion dimension (0-100).

    Factors:
    - Count of classes with LCOM4 > 2 (splittable)
    - Average LCOM4 across all classes
    - Count of modules with cohesion ratio < 0.3
    """
    if not stats:
        return {"score": 100, "grade": "A", "factors": {}}

    classes_gt2 = stats.get("classes_with_lcom_gt_2", 0)
    total_classes = stats.get("total_classes", 0) or 1
    gt2_pct = (classes_gt2 / total_classes) * 100
    avg_lcom = stats.get("avg_lcom", 1.0)
    low_modules = stats.get("low_cohesion_modules", 0)

    score = 100.0
    # Classes with high LCOM4: up to 40 point deduction
    score -= min(gt2_pct * 2, 40)
    # Low-cohesion modules: up to 30 point deduction
    score -= min(low_modules * 5, 30)
    # High average LCOM: up to 15 point deduction
    if avg_lcom > 2.0:
        score -= min((avg_lcom - 2.0) * 5, 15)

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "classes_with_lcom_gt_2": classes_gt2,
            "avg_lcom": round(avg_lcom, 2),
            "low_cohesion_modules": low_modules,
            "total_classes": stats.get("total_classes", 0),
        },
    }


def score_duplication(
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Score duplication dimension (0-100).

    Factors:
    - Duplication ratio (duplicated lines / total lines)
    - Number of clone groups
    - Largest clone block size
    """
    if not stats:
        return {"score": 100, "grade": "A", "factors": {}}

    ratio = stats.get("duplication_ratio", 0.0)
    clone_groups = stats.get("type1_clone_groups", 0) + stats.get("type2_clone_groups", 0)
    largest = stats.get("largest_clone_lines", 0)

    score = 100.0
    # Duplication ratio: up to 50 point deduction
    if ratio >= 0.30:
        score -= 50
    elif ratio >= 0.20:
        score -= 40
    elif ratio >= 0.10:
        score -= 20
    elif ratio > 0.0:
        score -= ratio * 200  # linear up to 20 at 10%

    # Clone group count: up to 25 point deduction
    score -= min(clone_groups * 0.5, 25)

    # Largest clone: up to 15 point deduction for clones over 50 lines
    if largest > 50:
        score -= min((largest - 50) * 0.3, 15)

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "duplication_ratio": round(ratio, 4),
            "clone_groups": clone_groups,
            "largest_clone_lines": largest,
        },
    }


def score_testability(
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Score testability dimension (0-100).

    Factors:
    - Test-to-code ratio (higher is better)
    - Percentage of untested source files (lower is better)
    - Average assertions per test file (higher is better)
    """
    if not stats:
        return {"score": 100, "grade": "A", "factors": {}}

    # No source files means nothing to test — perfect score
    total_source = stats.get("total_source_files", 0)
    if total_source == 0:
        return {"score": 100, "grade": "A", "factors": {}}

    ratio = stats.get("test_to_code_ratio", 0.0)
    untested_pct = stats.get("untested_file_pct", 0.0)
    avg_assertions = stats.get("avg_assertions_per_test", 0.0)

    score = 100.0

    # Test-to-code ratio penalty: ideal is >= 0.8
    if ratio < 0.1:
        score -= 40
    elif ratio < 0.3:
        score -= 25
    elif ratio < 0.5:
        score -= 15
    elif ratio < 0.8:
        score -= 5

    # Untested file percentage: up to 35 point deduction
    score -= min(untested_pct * 0.35, 35)

    # Low assertion density: up to 15 point deduction
    if avg_assertions < 1.0:
        score -= 15
    elif avg_assertions < 3.0:
        score -= 10
    elif avg_assertions < 5.0:
        score -= 5

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "test_to_code_ratio": round(ratio, 4),
            "untested_file_pct": round(untested_pct, 1),
            "avg_assertions_per_test": round(avg_assertions, 2),
        },
    }


def score_maintainability(
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Score maintainability dimension (0-100).

    Factors:
    - Average Maintainability Index across all functions
    - Percentage of functions with MI < 20 (hard to maintain)
    - Minimum MI (worst-case function)
    """
    if not stats:
        return {"score": 100, "grade": "A", "factors": {}}

    avg_mi = stats.get("avg_mi", 100.0)
    low_mi_pct = stats.get("low_mi_pct", 0.0)
    min_mi = stats.get("min_mi", 100.0)

    score = 100.0
    if avg_mi < 40:
        score -= min((40 - avg_mi) * 1.0, 40)
    low_mi_deduction = min(low_mi_pct * 0.7, 35)
    score -= low_mi_deduction
    if min_mi < 10:
        score -= min((10 - min_mi) * 1.5, 15)

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "grade": letter_grade(score),
        "factors": {
            "avg_mi": round(avg_mi, 1),
            "low_mi_functions": stats.get("low_mi_functions", 0),
            "low_mi_pct": round(low_mi_pct, 1),
            "min_mi": round(min_mi, 1),
        },
    }


def compute_overall(dimension_scores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compute weighted overall score from dimension scores."""
    total = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        dim_score = dimension_scores.get(dim, {}).get("score", 100)
        total += dim_score * weight

    overall = round(total, 1)
    return {
        "score": overall,
        "grade": letter_grade(overall),
        "dimensions": dimension_scores,
        "weights": _DIMENSION_WEIGHTS,
    }
