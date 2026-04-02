# Module: health_scoring

## Module Purpose

The `health_scoring` module provides functions for computing architectural health scores for a codebase. It implements a scoring system that evaluates code quality based on multiple dimensions including complexity, coupling, code smells, and architectural layers. The module is designed to work with the output of other analysis modules like coupling metrics and complexity analysis to produce a comprehensive health assessment.

## Key Classes and Functions

### Function: `letter_grade`
```python
def letter_grade(score: float) -> str
```
Converts a numerical score (0.0-1.0) into a letter grade (A-F).

### Function: `score_complexity`
```python
def score_complexity(complexity: float) -> float
```
Computes a health score based on code complexity metrics. Takes a complexity value and returns a normalized score between 0.0 and 1.0.

### Function: `score_coupling`
```python
def score_coupling(coupling: dict[str, Any]) -> float
```
Computes a health score based on coupling metrics. Takes a dictionary containing coupling data and returns a normalized score between 0.0 and 1.0.

### Function: `score_smells`
```python
def score_smells(smells: list[dict[str, Any]]) -> float
```
Computes a health score based on code smell detection results. Takes a list of smell dictionaries and returns a normalized score between 0.0 and 1.0.

### Function: `score_layers`
```python
def score_layers(layers: dict[str, Any]) -> float
```
Computes a health score based on architectural layer analysis. Takes a dictionary containing layer data and returns a normalized score between 0.0 and 1.0.

### Function: `compute_overall`
```python
def compute_overall(
    complexity: float,
    coupling: dict[str, Any],
    smells: list[dict[str, Any]],
    layers: dict[str, Any],
) -> dict[str, Any]
```
Computes the overall health score by combining scores from all dimensions. Takes complexity, coupling, smells, and layers data and returns a dictionary containing the overall score and individual component scores.

## How Components Interact

The components in this module work together to provide a comprehensive architectural health assessment:

1. Individual scoring functions ([`score_complexity`](../files/src/local_deepwiki/generators/analysis/health_scoring.md), [`score_coupling`](../files/src/local_deepwiki/generators/analysis/health_scoring.md), [`score_smells`](../files/src/local_deepwiki/generators/analysis/health_scoring.md), [`score_layers`](../files/src/local_deepwiki/generators/analysis/health_scoring.md)) process specific aspects of code quality
2. Each function normalizes its input data to a 0.0-1.0 range
3. The [`compute_overall`](../files/src/local_deepwiki/generators/analysis/health_scoring.md) function aggregates these normalized scores into a final health assessment
4. The [`letter_grade`](../files/src/local_deepwiki/generators/analysis/health_scoring.md) function converts the final numerical score into a readable letter grade

The module is designed to accept output from other analysis modules (like the coupling analysis and complexity analysis) and transform them into meaningful health metrics.

## Usage Examples

```python
from local_deepwiki.generators.analysis.health_scoring import compute_overall, letter_grade

# Example usage with sample data
complexity_score = 0.75
coupling_data = {
    "total_modules": 10,
    "avg_instability": 0.45,
    "avg_abstractness": 0.30
}
smells = [
    {"type": "cyclomatic_complexity", "count": 2},
    {"type": "long_function", "count": 1}
]
layers = {
    "layer_count": 3,
    "cross_layer_deps": 5
}

# Compute overall health score
health_result = compute_overall(
    complexity=complexity_score,
    coupling=coupling_data,
    smells=smells,
    layers=layers
)

print(f"Overall score: {health_result['overall']}")
print(f"Letter grade: {letter_grade(health_result['overall'])}")
```

## Dependencies

This module depends on:
- `typing` (for type hints)

The module is designed to work with data structures produced by other analysis modules in the `generators.analysis` package, particularly those related to complexity, coupling, code smells, and architectural layers. It does not directly depend on any other modules from the `local_deepwiki` package beyond standard typing functionality.

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/generators/analysis/coupling.py:48-90`](../files/src/local_deepwiki/generators/analysis/coupling.md)
- [`src/local_deepwiki/generators/analysis/module_dependencies.py:30-40`](../files/src/local_deepwiki/generators/analysis/module_dependencies.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:29-34`](../files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/logging.py:28-83`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:92-94`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](../files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](../files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](../files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](../files/src/local_deepwiki/error_factories.md)


*Showing 10 of 263 source files.*
