"""Architecture quality gate for local-deepwiki.

Runs health analysis, compares against thresholds from pyproject.toml,
and exits with appropriate status code:

    deepwiki check [REPO_PATH] [--json]

Exit codes:
    0 = all thresholds pass (or no thresholds configured)
    1 = one or more threshold violations
    2 = infrastructure error (missing repo, analysis failure)
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from local_deepwiki.core.health_history import save_snapshot
from local_deepwiki.generators.analysis.architecture_health import (
    analyze_architecture_health,
)
from local_deepwiki.generators.manifest import get_cached_manifest

# Grade ordinal mapping: higher is better
_GRADE_VALUES: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def _grade_passes(actual: str, min_grade: str) -> bool:
    """Return True if *actual* grade meets or exceeds *min_grade*.

    Grade order: A=4, B=3, C=2, D=1, F=0.
    """
    return _GRADE_VALUES.get(actual, 0) >= _GRADE_VALUES.get(min_grade, 0)


def _load_thresholds(repo_path: Path) -> dict[str, Any]:
    """Read ``[tool.deepwiki.check]`` from *repo_path*/pyproject.toml.

    Returns an empty dict when the file or section is missing.
    """
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        return {}

    try:
        with open(pyproject, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}

    return data.get("tool", {}).get("deepwiki", {}).get("check", {})


def _check_thresholds(
    health_data: dict[str, Any],
    thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare *health_data* against *thresholds*, returning violations.

    Each violation is a dict with keys: ``field``, ``actual``, ``threshold``,
    ``message``.
    """
    violations: list[dict[str, Any]] = []
    overall = health_data.get("overall", {})

    # Overall grade check
    min_grade = thresholds.get("min_grade")
    if min_grade is not None:
        actual_grade = overall.get("grade", "F")
        if not _grade_passes(actual_grade, min_grade):
            violations.append(
                {
                    "field": "grade",
                    "actual": actual_grade,
                    "threshold": min_grade,
                    "message": (f"Grade {actual_grade} is below minimum {min_grade}"),
                }
            )

    # Overall score check
    min_score = thresholds.get("min_score")
    if min_score is not None:
        actual_score = overall.get("score", 0)
        if actual_score < min_score:
            violations.append(
                {
                    "field": "score",
                    "actual": actual_score,
                    "threshold": min_score,
                    "message": (f"Score {actual_score} is below minimum {min_score}"),
                }
            )

    # Per-dimension score checks
    dimensions = overall.get("dimensions", {})
    dimension_keys = ("complexity", "coupling", "smells", "layers")
    for dim in dimension_keys:
        threshold_key = f"min_{dim}"
        min_dim = thresholds.get(threshold_key)
        if min_dim is not None:
            actual_dim_score = dimensions.get(dim, {}).get("score", 0)
            if actual_dim_score < min_dim:
                violations.append(
                    {
                        "field": threshold_key,
                        "actual": actual_dim_score,
                        "threshold": min_dim,
                        "message": (
                            f"{dim.capitalize()} score {actual_dim_score} "
                            f"is below minimum {min_dim}"
                        ),
                    }
                )

    return violations


def _format_json_output(
    overall: dict[str, Any],
    thresholds: dict[str, Any],
    violations: list[dict[str, Any]],
    console: Console,
) -> None:
    """Format and print check results as JSON."""
    output = {
        "grade": overall.get("grade", "F"),
        "score": overall.get("score", 0),
        "dimensions": {
            name: dim_data.get("score", 0)
            for name, dim_data in overall.get("dimensions", {}).items()
        },
        "thresholds": thresholds,
        "violations": violations,
        "passed": len(violations) == 0,
    }
    console.print(json.dumps(output, indent=2))


def _pass_fail(passed: bool) -> str:
    """Return a Rich-coloured PASS or FAIL status string."""
    return "[green]PASS[/green]" if passed else "[red]FAIL[/red]"


def _threshold_str(value: Any) -> str:
    """Return the threshold value as a string, or '-' when unset."""
    return str(value) if value is not None else "-"


def _add_grade_row(
    table: Table, grade: str, min_grade: str | None, thresholds: dict[str, Any]
) -> None:
    """Add the grade row to the health table."""
    passes = min_grade is None or _grade_passes(grade, min_grade)
    table.add_row("Grade", grade, _threshold_str(min_grade), _pass_fail(passes))


def _add_score_row(table: Table, score: float, min_score: float | None) -> None:
    """Add the overall score row to the health table."""
    passes = min_score is None or score >= min_score
    table.add_row("Score", str(score), _threshold_str(min_score), _pass_fail(passes))


def _add_dimension_rows(
    table: Table, overall: dict[str, Any], thresholds: dict[str, Any]
) -> None:
    """Add one row per architecture dimension to the health table."""
    for dim in ("complexity", "coupling", "smells", "layers"):
        dim_score = overall.get("dimensions", {}).get(dim, {}).get("score", 0)
        min_dim = thresholds.get(f"min_{dim}")
        passes = min_dim is None or dim_score >= min_dim
        table.add_row(
            dim.capitalize(),
            str(dim_score),
            _threshold_str(min_dim),
            _pass_fail(passes),
        )


def _print_violations(violations: list[dict[str, Any]], console: Console) -> None:
    """Print violation messages or an all-passed confirmation."""
    if violations:
        console.print(f"\n[red]{len(violations)} violation(s) found.[/red]")
        for v in violations:
            console.print(f"  [red]- {v['message']}[/red]")
    else:
        console.print("\n[green]All checks passed.[/green]")


def _format_rich_table(
    overall: dict[str, Any],
    thresholds: dict[str, Any],
    violations: list[dict[str, Any]],
    project_name: str,
    console: Console,
) -> None:
    """Format and print check results as a Rich table."""
    table = Table(
        title=f"Architecture Health: {project_name}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status", justify="center")

    _add_grade_row(
        table, overall.get("grade", "F"), thresholds.get("min_grade"), thresholds
    )
    _add_score_row(table, overall.get("score", 0), thresholds.get("min_score"))
    _add_dimension_rows(table, overall, thresholds)

    console.print(table)
    _print_violations(violations, console)


def _resolve_project_name(repo_path: Path) -> str:
    """Return the project name from the manifest, falling back to repo dir name."""
    try:
        manifest = get_cached_manifest(repo_path)
        return manifest.name or repo_path.name
    except Exception:
        return repo_path.name


def _save_health_snapshot(repo_path: Path, health_data: dict[str, Any]) -> None:
    """Persist the health snapshot; silently ignore errors."""
    try:
        save_snapshot(repo_path / ".deepwiki", health_data)
    except Exception:
        pass


def run_check(
    repo_path: Path,
    *,
    json_output: bool = False,
    console: Console | None = None,
) -> int:
    """Run the architecture quality gate.

    Returns:
        0 if all thresholds pass (or none configured).
        1 if any threshold is violated.
        2 on infrastructure error (missing repo, analysis failure).
    """
    if console is None:
        console = Console()

    if not repo_path.exists() or not repo_path.is_dir():
        console.print(f"[red]Repository not found: {repo_path}[/red]")
        return 2

    thresholds = _load_thresholds(repo_path)
    project_name = _resolve_project_name(repo_path)

    try:
        health_data = analyze_architecture_health(repo_path, project_name)
    except Exception as exc:
        console.print(f"[red]Analysis failed: {exc}[/red]")
        return 2

    _save_health_snapshot(repo_path, health_data)

    violations = _check_thresholds(health_data, thresholds)
    overall = health_data.get("overall", {})

    if json_output:
        _format_json_output(overall, thresholds, violations, console)
    else:
        _format_rich_table(overall, thresholds, violations, project_name, console)

    return 1 if violations else 0


def main() -> int:
    """CLI entry point for ``deepwiki check``."""
    parser = argparse.ArgumentParser(
        prog="deepwiki check",
        description="Run architecture quality gate",
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the repository (default: current directory)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()
    repo_path = Path(args.repo_path).resolve()

    return run_check(repo_path, json_output=args.json_output)


if __name__ == "__main__":
    sys.exit(main())
