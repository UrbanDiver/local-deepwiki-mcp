# File Overview

**File**: `src/local_deepwiki/generators/analysis/health_scoring.py`

**Description**: This module provides functions to compute health scores for various architectural dimensions of a codebase. It converts raw metrics into dimension-specific scores (0–100) and an overall letter grade (A–F), enabling a standardized way to assess code quality and architecture health.

**Responsibility**: The module encapsulates scoring logic for multiple architectural health dimensions, such as complexity, coupling, smells, layers, churn, cohesion, duplication, testability, and maintainability. It is designed to be used with summary data from analysis tools and does not perform I/O operations.

**Design Rationale**: The design follows a modular approach where each architectural dimension is scored independently, using weighted penalties based on metric thresholds. This allows for clear separation of concerns and makes it easy to adjust scoring logic for individual dimensions. The `compute_overall` function aggregates these scores using predefined weights, providing a unified health score.

---

# Key Concepts

## Dimension-Based Scoring

Each function in this module computes a score for a specific architectural dimension. The scoring algorithm typically:
1. Takes raw metrics or summaries as input.
2. Applies penalties based on thresholds or ratios.
3. Caps penalties to prevent a single issue from completely derailing the score.
4. Returns a normalized score (0–100) and a letter grade.

This approach allows for fine-grained assessment of code health, highlighting different aspects like complexity, maintainability, and testability.

## Weighted Aggregation

The `compute_overall` function aggregates dimension scores using predefined weights (`_DIMENSION_WEIGHTS`) to produce a single health score. This reflects the relative importance of each dimension in overall architecture health.

## Letter Grade Conversion

The `letter_grade` function maps a numerical score to a letter grade (A–F) using a fixed threshold list (`_GRADE_THRESHOLDS`). This provides a human-readable representation of health scores.

## Penalty Algorithms

Penalties are applied using linear or capped deductions, depending on the metric's severity. For example:
- Duplication ratio uses a stepwise penalty.
- Cohesion uses a combination of percentage and average metrics.

These algorithms were chosen to reflect real-world impact: small deviations should not heavily penalize, while large issues should be heavily weighted.

---

# Integration

This module is part of the architecture analysis pipeline and is used by other components in the codebase, particularly in:
- `src/local_deepwiki/generators/analysis/architecture_report.py` — for generating detailed architecture health reports.
- `src/local_deepwiki/handlers/session_state.py` — to manage the state of health scoring during analysis.
- `src/local_deepwiki/handlers/types.py` — to define the types used in health scoring.

Functions are called from:
- `test_health_scoring` — for unit testing of individual scoring functions.
- `architecture_health` — for computing the overall health score in the architecture health report.

The module is designed to work with summary data from analysis tools (e.g., cyclomatic complexity, churn metrics, duplication counts) and does not perform I/O or depend on external data sources.

---

# Design Notes

## Edge Case Handling

- **Zero Division Protection**: Functions like `score_complexity`, `score_smells`, and `score_cohesion` check for zero values (e.g., `total_functions`, `total_lines`) to prevent division-by-zero errors.
- **Empty Input Handling**: Functions such as `score_coupling`, `score_churn`, and `score_maintainability` return a perfect score (100) when no data is provided, assuming no issues in a null case.
- **Capping Penalties**: All penalties are capped to ensure no single issue completely ruins the score, reflecting real-world resilience.

## Scoring Logic Choices

- **Capped Deductions**: Deductions are capped to prevent extreme score drops. For example, `score_duplication` caps its deduction at 50 points for duplication ratio ≥ 0.30.
- **Weighted Metrics**: Some functions use weighted metrics (e.g., severity in `score_smells`) to reflect the impact of different issues.
- **Threshold-Based Scoring**: Functions like `score_testability` use thresholds to penalize low test-to-code ratios or high untested file percentages.

## No I/O

This module is purely computational and does not read or write files. It operates on dictionaries of metric data, making it fast and suitable for integration into larger analysis workflows.

## API Reference

### Functions

#### `letter_grade`

```python
def letter_grade(score: float) -> str
```

Convert a 0-100 score to a letter grade.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `score` | `float` | - | - |

**Returns:** `str`



<details>
<summary>View Source (lines 34-39) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L34-L39">GitHub</a></summary>

```python
def letter_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    for grade, threshold in _GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"
```

</details>

#### `score_complexity`

```python
def score_complexity(hotspots: list[dict[str, Any]], total_functions: int) -> dict[str, Any]
```

Score complexity dimension (0-100).  Factors: - Max cyclomatic complexity (lower is better) - % of functions above CC=15 (lower is better)


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hotspots` | `list[dict[str, Any]]` | - | - |
| `total_functions` | `int` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 42-81) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L42-L81">GitHub</a></summary>

```python
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
```

</details>

#### `score_coupling`

```python
def score_coupling(metrics: list[dict[str, Any]]) -> dict[str, Any]
```

Score coupling dimension (0-100).  Factors: - Average distance from main sequence (lower is better) - Percentage of problematic unstable modules  Highly unstable modules are only flagged when they have Ca=0 (nothing depends on them) AND high Ce — these are disconnected modules that import a lot but provide no value to the rest of the system. Edge modules with Ca>0 (handlers that are imported by __init__.py, services used by handlers) are expected to be unstable and are not penalized.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metrics` | `list[dict[str, Any]]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 84-126) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L84-L126">GitHub</a></summary>

```python
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
```

</details>

#### `score_smells`

```python
def score_smells(smells: list[dict[str, Any]], total_lines: int) -> dict[str, Any]
```

Score design smells dimension (0-100).  Factors: - Smell density: smells per 1000 lines, weighted by severity - God class count (high-impact)


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `smells` | `list[dict[str, Any]]` | - | - |
| `total_lines` | `int` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 129-160) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L129-L160">GitHub</a></summary>

```python
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
```

</details>

#### `score_layers`

```python
def score_layers(violations: list[dict[str, Any]]) -> dict[str, Any]
```

Score layer discipline dimension (0-100).  Simple: 100 minus 10 per violation, floor 0.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `violations` | `list[dict[str, Any]]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 163-176) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L163-L176">GitHub</a></summary>

```python
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
```

</details>

#### `score_churn`

```python
def score_churn(composite: list[dict[str, Any]], stats: dict[str, Any]) -> dict[str, Any]
```

Score churn dimension (0-100).  Factors: - Count of files with composite > 0.5 (high churn AND high complexity) - Gini coefficient of churn distribution (concentration)


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `composite` | `list[dict[str, Any]]` | - | - |
| `stats` | `dict[str, Any]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 179-214) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L179-L214">GitHub</a></summary>

```python
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
```

</details>

#### `score_cohesion`

```python
def score_cohesion(class_cohesion: list[dict[str, Any]], module_cohesion: list[dict[str, Any]], stats: dict[str, Any]) -> dict[str, Any]
```

Score cohesion dimension (0-100).  Factors: - Count of classes with LCOM4 > 2 (splittable) - Average LCOM4 across all classes - Count of modules with cohesion ratio < 0.3


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `class_cohesion` | `list[dict[str, Any]]` | - | - |
| `module_cohesion` | `list[dict[str, Any]]` | - | - |
| `stats` | `dict[str, Any]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 217-258) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L217-L258">GitHub</a></summary>

```python
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
```

</details>

#### `score_duplication`

```python
def score_duplication(stats: dict[str, Any]) -> dict[str, Any]
```

Score duplication dimension (0-100).  Factors: - Duplication ratio (duplicated lines / total lines) - Number of clone groups - Largest clone block size


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stats` | `dict[str, Any]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 261-305) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L261-L305">GitHub</a></summary>

```python
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
```

</details>

#### `score_testability`

```python
def score_testability(stats: dict[str, Any]) -> dict[str, Any]
```

Score testability dimension (0-100).  Factors: - Test-to-code ratio (higher is better) - Percentage of untested source files (lower is better) - Average assertions per test file (higher is better)


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stats` | `dict[str, Any]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 308-362) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L308-L362">GitHub</a></summary>

```python
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
```

</details>

#### `score_maintainability`

```python
def score_maintainability(stats: dict[str, Any]) -> dict[str, Any]
```

Score maintainability dimension (0-100).  Factors: - Average Maintainability Index across all functions - Percentage of functions with MI < 20 (hard to maintain) - Minimum MI (worst-case function)


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stats` | `dict[str, Any]` | - | - |

**Returns:** `dict[str, Any]`



<details>
<summary>View Source (lines 365-400) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L365-L400">GitHub</a></summary>

```python
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
```

</details>

#### `compute_overall`

```python
def compute_overall(dimension_scores: dict[str, dict[str, Any]]) -> dict[str, Any]
```

Compute weighted overall score from dimension scores.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dimension_scores` | `dict[str, dict[str, Any]]` | - | - |

**Returns:** `dict[str, Any]`




<details>
<summary>View Source (lines 403-416) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/generators/analysis/health_scoring.py#L403-L416">GitHub</a></summary>

```python
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
```

</details>

## Call Graph

```mermaid
flowchart TD
    N0[compute_overall]
    N1[letter_grade]
    N2[score_churn]
    N3[score_cohesion]
    N4[score_complexity]
    N5[score_coupling]
    N6[score_duplication]
    N7[score_layers]
    N8[score_maintainability]
    N9[score_smells]
    N10[score_testability]
    N4 --> N1
    N5 --> N1
    N9 --> N1
    N7 --> N1
    N2 --> N1
    N3 --> N1
    N6 --> N1
    N10 --> N1
    N8 --> N1
    N0 --> N1
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10 func
```

## Used By

Functions and methods in this file and their callers:

- **`letter_grade`**: called by `compute_overall`, `score_churn`, `score_cohesion`, `score_complexity`, `score_coupling`, `score_duplication`, `score_layers`, `score_maintainability`, `score_smells`, `score_testability`

## Usage Examples

*Examples extracted from test files*

### Example: `letter_grade`

From `test_health_scoring.py::test_letter_grade_a_at_90`:

```python
assert letter_grade(90) == "A"
```

### Example: `letter_grade`

From `test_health_scoring.py::test_letter_grade_a_at_100`:

```python
assert letter_grade(100) == "A"
```

### Example: `score_complexity`

From `test_health_scoring.py::test_score_complexity_empty_hotspots_zero_functions`:

```python
result = score_complexity([], 0)
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert result["factors"] == {}
```

### Example: `score_complexity`

From `test_health_scoring.py::test_score_complexity_perfect_no_high_cc`:

```python
hotspots = [{"metric_value": 3}, {"metric_value": 5}, {"metric_value": 2}]
    result = score_complexity(hotspots, total_functions=10)
    assert result["score"] == 100.0
    assert result["grade"] == "A"
    assert result["factors"]["max_cyclomatic"] == 5
    assert result["factors"]["functions_over_cc15"] == 0
    assert result["factors"]["pct_over_cc15"] == 0.0
```

### Example: `score_coupling`

From `test_health_scoring.py::test_score_coupling_empty_metrics`:

```python
result = score_coupling([])
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert result["factors"] == {}
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `score_smells` | function | Brian Breidenbach | today | `d50a656` feat: add maintainability i... |
| `score_duplication` | function | Brian Breidenbach | today | `d50a656` feat: add maintainability i... |
| `score_maintainability` | function | Brian Breidenbach | today | `64e4b55` feat: add maintainability i... |
| `score_testability` | function | Brian Breidenbach | today | `6d8243f` feat: add testability-based... |
| `score_cohesion` | function | Brian Breidenbach | today | `0cd069b` feat(cohesion): add score_c... |
| `score_churn` | function | Brian Breidenbach | today | `3336b41` feat(churn): add score_chur... |
| `score_coupling` | function | Brian Breidenbach | yesterday | `c0fe1bd` fix: unify module labels in... |
| `letter_grade` | function | Brian Breidenbach | 2 weeks ago | `c9f0d4d` refactor: extract source_fi... |
| `score_complexity` | function | Brian Breidenbach | 2 weeks ago | `c9f0d4d` refactor: extract source_fi... |
| `score_layers` | function | Brian Breidenbach | 2 weeks ago | `c9f0d4d` refactor: extract source_fi... |
| `compute_overall` | function | Brian Breidenbach | 2 weeks ago | `c9f0d4d` refactor: extract source_fi... |

## Relevant Source Files

- `src/local_deepwiki/generators/analysis/health_scoring.py:34-39`
