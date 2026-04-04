"""Tests for health scoring utilities."""

from __future__ import annotations

import pytest

from local_deepwiki.generators.analysis.health_scoring import (
    compute_overall,
    letter_grade,
    score_churn,
    score_cohesion,
    score_complexity,
    score_coupling,
    score_duplication,
    score_layers,
    score_maintainability,
    score_smells,
    score_testability,
)


# ---------------------------------------------------------------------------
# letter_grade
# ---------------------------------------------------------------------------


def test_letter_grade_a_at_90():
    assert letter_grade(90) == "A"


def test_letter_grade_a_at_100():
    assert letter_grade(100) == "A"


def test_letter_grade_b_at_75():
    assert letter_grade(75) == "B"


def test_letter_grade_b_at_89():
    assert letter_grade(89) == "B"


def test_letter_grade_c_at_60():
    assert letter_grade(60) == "C"


def test_letter_grade_c_at_74():
    assert letter_grade(74) == "C"


def test_letter_grade_d_at_40():
    assert letter_grade(40) == "D"


def test_letter_grade_d_at_59():
    assert letter_grade(59) == "D"


def test_letter_grade_f_at_0():
    assert letter_grade(0) == "F"


def test_letter_grade_f_at_39():
    assert letter_grade(39) == "F"


def test_letter_grade_float_score():
    assert letter_grade(90.0) == "A"
    assert letter_grade(89.9) == "B"


def test_letter_grade_boundary_exactly_90():
    assert letter_grade(90) == "A"


def test_letter_grade_boundary_just_below_90():
    assert letter_grade(89.99) == "B"


# ---------------------------------------------------------------------------
# score_complexity
# ---------------------------------------------------------------------------


def test_score_complexity_empty_hotspots_zero_functions():
    result = score_complexity([], 0)
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert result["factors"] == {}


def test_score_complexity_perfect_no_high_cc():
    # All functions have low CC (below 15)
    hotspots = [{"metric_value": 3}, {"metric_value": 5}, {"metric_value": 2}]
    result = score_complexity(hotspots, total_functions=10)
    assert result["score"] == 100.0
    assert result["grade"] == "A"
    assert result["factors"]["max_cyclomatic"] == 5
    assert result["factors"]["functions_over_cc15"] == 0
    assert result["factors"]["pct_over_cc15"] == 0.0


def test_score_complexity_some_high_cc():
    # 2 out of 10 functions over CC=15
    hotspots = [{"metric_value": 20}, {"metric_value": 18}, {"metric_value": 5}]
    result = score_complexity(hotspots, total_functions=10)
    assert result["score"] < 100
    assert result["factors"]["functions_over_cc15"] == 2
    assert result["factors"]["max_cyclomatic"] == 20


def test_score_complexity_max_cc_over_30():
    hotspots = [{"metric_value": 35}]
    result = score_complexity(hotspots, total_functions=100)
    # -20 for max_cc > 30, small pct penalty
    assert result["score"] <= 80


def test_score_complexity_max_cc_over_50():
    hotspots = [{"metric_value": 55}]
    result = score_complexity(hotspots, total_functions=100)
    # -30 for max_cc > 50
    assert result["score"] <= 70


def test_score_complexity_all_over_cc15():
    # All 10 functions over CC=15: 100% → penalty = min(100*5, 40) = 40
    hotspots = [{"metric_value": 20}] * 10
    result = score_complexity(hotspots, total_functions=10)
    assert result["score"] <= 60  # at least 40 deducted


def test_score_complexity_score_clamped_to_zero():
    # Many high-CC functions should clamp at 0
    hotspots = [{"metric_value": 60}] * 50
    result = score_complexity(hotspots, total_functions=50)
    assert result["score"] >= 0.0
    assert result["score"] <= 100.0


def test_score_complexity_missing_metric_value_ignored():
    hotspots = [{"other_key": 5}, {"metric_value": 10}]
    result = score_complexity(hotspots, total_functions=5)
    # Should not raise; metric_value=10 is not over 15
    assert result["factors"]["functions_over_cc15"] == 0


def test_score_complexity_returns_grade():
    result = score_complexity([], 0)
    assert "grade" in result
    assert result["grade"] in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# score_coupling
# ---------------------------------------------------------------------------


def test_score_coupling_empty_metrics():
    result = score_coupling([])
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert result["factors"] == {}


def test_score_coupling_perfect_zero_distance():
    metrics = [
        {"distance": 0.0, "instability": 0.0, "efferent_coupling": 0},
        {"distance": 0.0, "instability": 0.1, "efferent_coupling": 1},
    ]
    result = score_coupling(metrics)
    assert result["score"] == 100.0
    assert result["grade"] == "A"


def test_score_coupling_high_avg_distance():
    # avg_distance = 0.8 → penalty = min(0.8*30, 25) = 24
    metrics = [{"distance": 0.8, "instability": 0.5, "efferent_coupling": 2}] * 3
    result = score_coupling(metrics)
    assert result["score"] <= 80  # 100 - 24 = 76 approx


def test_score_coupling_many_unstable_modules():
    # instability > 0.8 AND efferent_coupling > 5 AND afferent_coupling == 0
    metrics = [
        {
            "distance": 0.0,
            "instability": 0.9,
            "efferent_coupling": 6,
            "afferent_coupling": 0,
        }
    ] * 20
    result = score_coupling(metrics)
    assert result["factors"]["highly_unstable_modules"] == 20
    # unstable_pct = 100%, penalty = min(100*2, 25) = 25
    assert result["score"] <= 75


def test_score_coupling_unstable_but_low_efferent():
    # instability > 0.8 but efferent_coupling <= 5: not counted as highly unstable
    metrics = [{"distance": 0.0, "instability": 0.9, "efferent_coupling": 4}]
    result = score_coupling(metrics)
    assert result["factors"]["highly_unstable_modules"] == 0


def test_score_coupling_score_clamped():
    # Worst case should clamp at 0
    metrics = [{"distance": 2.0, "instability": 0.9, "efferent_coupling": 10}] * 50
    result = score_coupling(metrics)
    assert result["score"] >= 0.0
    assert result["score"] <= 100.0


def test_score_coupling_total_modules_factor():
    metrics = [
        {"distance": 0.1, "instability": 0.5, "efferent_coupling": 1},
        {"distance": 0.2, "instability": 0.5, "efferent_coupling": 1},
    ]
    result = score_coupling(metrics)
    assert result["factors"]["total_modules"] == 2


# ---------------------------------------------------------------------------
# score_smells
# ---------------------------------------------------------------------------


def test_score_smells_zero_lines():
    result = score_smells([], 0)
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert result["factors"] == {}


def test_score_smells_no_smells():
    result = score_smells([], total_lines=1000)
    assert result["score"] == 100.0
    assert result["grade"] == "A"
    assert result["factors"]["total_smells"] == 0
    assert result["factors"]["god_classes"] == 0


def test_score_smells_high_severity_weighted_more():
    high_smell = {"severity": "high", "type": "long_method"}
    medium_smell = {"severity": "medium", "type": "long_parameter_list"}
    result_high = score_smells([high_smell], total_lines=1000)
    result_medium = score_smells([medium_smell], total_lines=1000)
    # High severity smell should penalize more
    assert result_high["score"] < result_medium["score"]


def test_score_smells_god_class_extra_penalty():
    god = {"severity": "high", "type": "god_class"}
    long_method = {"severity": "high", "type": "long_method"}
    result_god = score_smells([god], total_lines=1000)
    result_long = score_smells([long_method], total_lines=1000)
    # God class has extra -5 penalty
    assert result_god["score"] < result_long["score"]


def test_score_smells_density_calculation():
    # 1 medium smell in 1000 lines → density = 1/1000 * 1000 = 1.0
    # penalty = min(1.0 * 8, 60) = 8
    smells = [{"severity": "medium", "type": "large_file"}]
    result = score_smells(smells, total_lines=1000)
    assert result["factors"]["weighted_density_per_1k"] == pytest.approx(1.0, rel=0.01)
    assert result["score"] == pytest.approx(92.0, rel=0.01)


def test_score_smells_score_clamped():
    smells = [{"severity": "high", "type": "god_class"}] * 100
    result = score_smells(smells, total_lines=100)
    assert result["score"] >= 0.0
    assert result["score"] <= 100.0


def test_score_smells_unknown_severity_defaults_to_medium_weight():
    smells = [{"severity": "unknown", "type": "something"}]
    result = score_smells(smells, total_lines=1000)
    # weight=1 (default), density = 1.0, penalty = 8
    assert result["score"] == pytest.approx(92.0, rel=0.01)


def test_smells_score_with_one_god_class():
    """With only 1 god class (down from 6), score should differentiate from many."""
    smells = [
        {"type": "god_class", "severity": "high"},
        *[{"type": "long_method", "severity": "high"} for _ in range(20)],
    ]
    result = score_smells(smells, total_lines=70000)
    assert result["score"] > 40


def test_smells_score_with_zero_god_classes():
    """Zero god classes should contribute 0 penalty."""
    smells = [{"type": "long_method", "severity": "medium"} for _ in range(20)]
    result = score_smells(smells, total_lines=70000)
    assert result["score"] > 60
    assert result["factors"]["god_classes"] == 0


def test_smells_score_differentiates_god_class_counts():
    """Score should meaningfully differ between 0, 1, and 6 god classes."""
    base_smells = [{"type": "long_method", "severity": "medium"} for _ in range(30)]
    score_0 = score_smells(base_smells, total_lines=70000)["score"]
    score_1 = score_smells(
        [*base_smells, {"type": "god_class", "severity": "high"}],
        total_lines=70000,
    )["score"]
    score_6 = score_smells(
        [*base_smells, *[{"type": "god_class", "severity": "high"} for _ in range(6)]],
        total_lines=70000,
    )["score"]
    assert score_0 > score_1 > score_6
    assert (score_0 - score_1) >= 3
    assert (score_1 - score_6) >= 5


def test_smells_score_density_5_differs_from_7_5():
    """Density ~5 should score meaningfully different from density ~7.5."""
    # Create smells to produce density ~5.0 (all high severity, weight=3)
    # density = (count * 3 / total_lines) * 1000
    # For density=5: count * 3 / 70000 * 1000 = 5 → count = 116.67 → 117
    smells_5 = [{"type": "long_method", "severity": "high"} for _ in range(117)]
    # For density=7.5: count * 3 / 70000 * 1000 = 7.5 → count = 175
    smells_7_5 = [{"type": "long_method", "severity": "high"} for _ in range(175)]

    score_5 = score_smells(smells_5, total_lines=70000)["score"]
    score_7_5 = score_smells(smells_7_5, total_lines=70000)["score"]

    # Must have meaningful differentiation (at least 5 points)
    assert score_5 > score_7_5
    assert (score_5 - score_7_5) >= 5


# ---------------------------------------------------------------------------
# score_layers
# ---------------------------------------------------------------------------


def test_score_layers_no_violations():
    result = score_layers([])
    assert result["score"] == 100.0
    assert result["grade"] == "A"
    assert result["factors"]["total_violations"] == 0


def test_score_layers_one_violation():
    result = score_layers([{"from": "a", "to": "b"}])
    assert result["score"] == 90.0
    assert result["grade"] == "A"


def test_score_layers_two_violations():
    result = score_layers([{}] * 2)
    assert result["score"] == 80.0


def test_score_layers_ten_violations():
    result = score_layers([{}] * 10)
    assert result["score"] == 0.0
    assert result["grade"] == "F"


def test_score_layers_many_violations_clamped():
    result = score_layers([{}] * 50)
    assert result["score"] == 0.0


def test_score_layers_grade_b_at_two_violations():
    # 100 - 2*10 = 80 → B
    result = score_layers([{}] * 2)
    assert result["grade"] == "B"


def test_score_layers_grade_c_at_four_violations():
    # 100 - 4*10 = 60 → C
    result = score_layers([{}] * 4)
    assert result["grade"] == "C"


def test_score_layers_grade_d_at_seven_violations():
    # 100 - 7*10 = 30 → F (below 40)
    result = score_layers([{}] * 7)
    assert result["grade"] == "F"


# ---------------------------------------------------------------------------
# score_churn
# ---------------------------------------------------------------------------


def test_score_churn_empty_stats():
    result = score_churn([], stats={})
    assert result["score"] == 100
    assert result["grade"] == "A"


def test_score_churn_no_high_churn_complex_files():
    composite = [{"file": "a.py", "churn": 5, "complexity": 3, "composite": 0.1}]
    stats = {"gini_coefficient": 0.3, "total_files": 10}
    result = score_churn(composite, stats=stats)
    assert result["score"] >= 80


def test_score_churn_many_high_churn_complex_files():
    composite = [
        {"file": f"f{i}.py", "churn": 20, "complexity": 30, "composite": 0.8}
        for i in range(10)
    ]
    stats = {"gini_coefficient": 0.5, "total_files": 20}
    result = score_churn(composite, stats=stats)
    assert result["score"] < 70
    assert result["factors"]["high_churn_complex_files"] == 10


def test_score_churn_extreme_gini():
    composite = []
    stats = {"gini_coefficient": 0.9, "total_files": 50}
    result = score_churn(composite, stats=stats)
    assert result["score"] < 90
    assert result["factors"]["churn_concentration"] == 0.9


def test_score_churn_score_clamped():
    composite = [{"file": f"f{i}.py", "composite": 0.9} for i in range(100)]
    stats = {"gini_coefficient": 1.0, "total_files": 100}
    result = score_churn(composite, stats=stats)
    assert 0.0 <= result["score"] <= 100.0


def test_score_churn_returns_factors():
    composite = [{"file": "a.py", "composite": 0.6}]
    stats = {"gini_coefficient": 0.4, "total_files": 5}
    result = score_churn(composite, stats=stats)
    assert "high_churn_complex_files" in result["factors"]
    assert "churn_concentration" in result["factors"]
    assert "total_files" in result["factors"]


# ---------------------------------------------------------------------------
# score_cohesion
# ---------------------------------------------------------------------------


def test_score_cohesion_empty_stats():
    result = score_cohesion([], [], stats={})
    assert result["score"] == 100
    assert result["grade"] == "A"


def test_score_cohesion_no_issues():
    stats = {
        "classes_with_lcom_gt_2": 0,
        "total_classes": 10,
        "avg_lcom": 1.2,
        "low_cohesion_modules": 0,
    }
    result = score_cohesion([], [], stats=stats)
    assert result["score"] >= 90


def test_score_cohesion_many_splittable_classes():
    stats = {
        "classes_with_lcom_gt_2": 8,
        "total_classes": 10,
        "avg_lcom": 3.5,
        "low_cohesion_modules": 2,
    }
    result = score_cohesion([], [], stats=stats)
    assert result["score"] < 50


def test_score_cohesion_high_avg_lcom():
    stats = {
        "classes_with_lcom_gt_2": 0,
        "total_classes": 10,
        "avg_lcom": 5.0,
        "low_cohesion_modules": 0,
    }
    result = score_cohesion([], [], stats=stats)
    assert result["score"] < 90


def test_score_cohesion_score_clamped():
    stats = {
        "classes_with_lcom_gt_2": 100,
        "total_classes": 100,
        "avg_lcom": 10.0,
        "low_cohesion_modules": 20,
    }
    result = score_cohesion([], [], stats=stats)
    assert 0.0 <= result["score"] <= 100.0


def test_score_cohesion_returns_factors():
    stats = {
        "classes_with_lcom_gt_2": 3,
        "total_classes": 20,
        "avg_lcom": 2.5,
        "low_cohesion_modules": 1,
    }
    result = score_cohesion([], [], stats=stats)
    assert "classes_with_lcom_gt_2" in result["factors"]
    assert "avg_lcom" in result["factors"]
    assert "low_cohesion_modules" in result["factors"]


# ---------------------------------------------------------------------------
# score_duplication
# ---------------------------------------------------------------------------


def test_score_duplication_empty_stats():
    result = score_duplication(stats={})
    assert result["score"] == 100
    assert result["grade"] == "A"


def test_score_duplication_no_duplicates():
    stats = {
        "duplication_ratio": 0.0,
        "type1_clone_groups": 0,
        "type2_clone_groups": 0,
        "largest_clone_lines": 0,
    }
    result = score_duplication(stats=stats)
    assert result["score"] == 100.0


def test_score_duplication_moderate():
    stats = {
        "duplication_ratio": 0.10,
        "type1_clone_groups": 5,
        "type2_clone_groups": 3,
        "largest_clone_lines": 30,
    }
    result = score_duplication(stats=stats)
    assert result["score"] < 80


def test_score_duplication_high():
    stats = {
        "duplication_ratio": 0.30,
        "type1_clone_groups": 20,
        "type2_clone_groups": 10,
        "largest_clone_lines": 100,
    }
    result = score_duplication(stats=stats)
    assert result["score"] < 30


def test_score_duplication_score_clamped():
    stats = {
        "duplication_ratio": 0.50,
        "type1_clone_groups": 100,
        "type2_clone_groups": 50,
        "largest_clone_lines": 500,
    }
    result = score_duplication(stats=stats)
    assert 0.0 <= result["score"] <= 100.0


def test_score_duplication_returns_factors():
    stats = {
        "duplication_ratio": 0.05,
        "type1_clone_groups": 2,
        "type2_clone_groups": 1,
        "largest_clone_lines": 20,
    }
    result = score_duplication(stats=stats)
    assert "duplication_ratio" in result["factors"]
    assert "clone_groups" in result["factors"]
    assert "largest_clone_lines" in result["factors"]


# ---------------------------------------------------------------------------
# score_testability
# ---------------------------------------------------------------------------


def test_score_testability_empty_stats():
    result = score_testability(stats={})
    assert result["score"] == 100
    assert result["grade"] == "A"


def test_score_testability_excellent():
    stats = {
        "total_source_files": 10,
        "test_to_code_ratio": 1.0,
        "untested_file_pct": 0.0,
        "avg_assertions_per_test": 8.0,
    }
    result = score_testability(stats=stats)
    assert result["score"] == 100.0
    assert result["grade"] == "A"


def test_score_testability_no_tests():
    stats = {
        "total_source_files": 10,
        "test_to_code_ratio": 0.0,
        "untested_file_pct": 100.0,
        "avg_assertions_per_test": 0.0,
    }
    result = score_testability(stats=stats)
    assert result["score"] < 30


def test_score_testability_low_ratio():
    stats = {
        "total_source_files": 10,
        "test_to_code_ratio": 0.2,
        "untested_file_pct": 30.0,
        "avg_assertions_per_test": 4.0,
    }
    result = score_testability(stats=stats)
    assert result["score"] < 75


def test_score_testability_score_clamped():
    stats = {
        "total_source_files": 10,
        "test_to_code_ratio": 0.0,
        "untested_file_pct": 100.0,
        "avg_assertions_per_test": 0.0,
    }
    result = score_testability(stats=stats)
    assert 0.0 <= result["score"] <= 100.0


def test_score_testability_returns_factors():
    stats = {
        "total_source_files": 10,
        "test_to_code_ratio": 0.5,
        "untested_file_pct": 20.0,
        "avg_assertions_per_test": 5.0,
    }
    result = score_testability(stats=stats)
    assert "test_to_code_ratio" in result["factors"]
    assert "untested_file_pct" in result["factors"]
    assert "avg_assertions_per_test" in result["factors"]


def test_score_testability_zero_source_files():
    stats = {
        "total_source_files": 0,
        "test_to_code_ratio": 0.0,
        "untested_file_pct": 0.0,
        "avg_assertions_per_test": 0.0,
    }
    result = score_testability(stats=stats)
    assert result["score"] == 100
    assert result["grade"] == "A"


# ---------------------------------------------------------------------------
# score_maintainability
# ---------------------------------------------------------------------------


def test_score_maintainability_empty_stats():
    result = score_maintainability(stats={})
    assert result["score"] == 100
    assert result["grade"] == "A"


def test_score_maintainability_excellent():
    stats = {
        "avg_mi": 80.0,
        "low_mi_pct": 0.0,
        "low_mi_functions": 0,
        "min_mi": 60.0,
    }
    result = score_maintainability(stats=stats)
    assert result["score"] == 100.0
    assert result["grade"] == "A"


def test_score_maintainability_low_avg_mi():
    stats = {
        "avg_mi": 25.0,
        "low_mi_pct": 5.0,
        "low_mi_functions": 2,
        "min_mi": 15.0,
    }
    result = score_maintainability(stats=stats)
    # avg_mi < 40 → deduction = min((40-25)*1.0, 40) = 15
    # low_mi_pct = 5 → deduction = min(5*0.7, 35) = 3.5
    # min_mi >= 10 → no extra deduction
    # score = 100 - 15 - 3.5 = 81.5
    assert result["score"] == pytest.approx(81.5, rel=0.01)


def test_score_maintainability_very_low_min_mi():
    stats = {
        "avg_mi": 50.0,
        "low_mi_pct": 10.0,
        "low_mi_functions": 5,
        "min_mi": 3.0,
    }
    result = score_maintainability(stats=stats)
    # avg_mi >= 40 → no avg deduction
    # low_mi_pct = 10 → deduction = min(10*0.7, 35) = 7.0
    # min_mi < 10 → deduction = min((10-3)*1.5, 15) = 10.5
    # score = 100 - 0 - 7.0 - 10.5 = 82.5
    assert result["score"] == pytest.approx(82.5, rel=0.01)


def test_score_maintainability_score_clamped():
    stats = {
        "avg_mi": 5.0,
        "low_mi_pct": 80.0,
        "low_mi_functions": 100,
        "min_mi": 0.0,
    }
    result = score_maintainability(stats=stats)
    assert 0.0 <= result["score"] <= 100.0


def test_score_maintainability_returns_factors():
    stats = {
        "avg_mi": 60.0,
        "low_mi_pct": 5.0,
        "low_mi_functions": 3,
        "min_mi": 12.0,
    }
    result = score_maintainability(stats=stats)
    assert "avg_mi" in result["factors"]
    assert "low_mi_functions" in result["factors"]
    assert "low_mi_pct" in result["factors"]
    assert "min_mi" in result["factors"]


# ---------------------------------------------------------------------------
# compute_overall
# ---------------------------------------------------------------------------


def test_compute_overall_all_perfect():
    dimensions = {
        "complexity": {"score": 100},
        "coupling": {"score": 100},
        "smells": {"score": 100},
        "layers": {"score": 100},
        "churn": {"score": 100},
        "cohesion": {"score": 100},
        "duplication": {"score": 100},
        "testability": {"score": 100},
        "maintainability": {"score": 100},
    }
    result = compute_overall(dimensions)
    assert result["score"] == 100.0
    assert result["grade"] == "A"


def test_compute_overall_all_zero():
    dimensions = {
        "complexity": {"score": 0},
        "coupling": {"score": 0},
        "smells": {"score": 0},
        "layers": {"score": 0},
        "churn": {"score": 0},
        "cohesion": {"score": 0},
        "duplication": {"score": 0},
        "testability": {"score": 0},
        "maintainability": {"score": 0},
    }
    result = compute_overall(dimensions)
    assert result["score"] == 0.0
    assert result["grade"] == "F"


def test_compute_overall_weighted_average():
    # All 100 except smells=0. New weights:
    # complexity=0.15, coupling=0.12, smells=0.12, layers=0.09,
    # churn=0.12, cohesion=0.12, duplication=0.10, testability=0.10,
    # maintainability=0.08
    # expected = 100*(1 - 0.12) = 88.0
    dimensions = {
        "complexity": {"score": 100},
        "coupling": {"score": 100},
        "smells": {"score": 0},
        "layers": {"score": 100},
        "churn": {"score": 100},
        "cohesion": {"score": 100},
        "duplication": {"score": 100},
        "testability": {"score": 100},
        "maintainability": {"score": 100},
    }
    result = compute_overall(dimensions)
    assert result["score"] == pytest.approx(88.0, rel=0.01)
    assert result["grade"] == "B"


def test_compute_overall_missing_dimension_defaults_100():
    # If a dimension is missing, it defaults to 100
    dimensions = {
        "complexity": {"score": 0},
        # all others missing -> default 100
    }
    result = compute_overall(dimensions)
    # 0*0.15 + 100*(0.12+0.12+0.09+0.12+0.12+0.10+0.10+0.08) = 85.0
    assert result["score"] == pytest.approx(85.0, rel=0.01)


def test_compute_overall_dimensions_included_in_result():
    dimensions = {
        "complexity": {"score": 80},
        "coupling": {"score": 70},
        "smells": {"score": 90},
        "layers": {"score": 100},
        "churn": {"score": 85},
        "cohesion": {"score": 75},
        "duplication": {"score": 80},
        "testability": {"score": 90},
        "maintainability": {"score": 85},
    }
    result = compute_overall(dimensions)
    assert result["dimensions"] is dimensions


def test_compute_overall_weights_included_in_result():
    result = compute_overall({})
    assert "weights" in result
    weights = result["weights"]
    assert "complexity" in weights
    assert "coupling" in weights
    assert "smells" in weights
    assert "layers" in weights
    assert "churn" in weights
    assert "cohesion" in weights
    assert "duplication" in weights
    assert "testability" in weights
    assert "maintainability" in weights
    # Weights should sum to approximately 1.0
    assert sum(weights.values()) == pytest.approx(1.0, rel=0.001)


def test_compute_overall_grade_b_boundary():
    # Score of exactly 75.0 -> B
    dimensions = {
        "complexity": {"score": 75},
        "coupling": {"score": 75},
        "smells": {"score": 75},
        "layers": {"score": 75},
        "churn": {"score": 75},
        "cohesion": {"score": 75},
        "duplication": {"score": 75},
        "testability": {"score": 75},
        "maintainability": {"score": 75},
    }
    result = compute_overall(dimensions)
    assert result["score"] == 75.0
    assert result["grade"] == "B"
