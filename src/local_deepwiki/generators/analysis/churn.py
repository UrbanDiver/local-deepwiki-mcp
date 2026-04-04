"""Change-based metrics: file churn, co-change coupling, churn x complexity.

Shells out to ``git log --numstat`` and computes per-file commit counts,
co-change pairs (Jaccard similarity), and composite churn x complexity scores.
No LLM calls — pure computation on git history.
"""

from __future__ import annotations

import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from local_deepwiki.core.git_utils import GIT_LOG_TIMEOUT, _validate_repo_path
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

DEFAULT_WINDOW_DAYS = 90
_GIT_LOG_CHURN_TIMEOUT = 30


def parse_git_log_numstat(raw: str) -> list[tuple[str, list[str]]]:
    """Parse ``git log --format='%H' --numstat`` output.

    Returns a list of (commit_hash, [file_paths]) tuples.
    Binary files (shown as ``-\\t-\\tpath``) are skipped.
    Commits with no tracked files after filtering are omitted.
    """
    result: list[tuple[str, list[str]]] = []
    current_hash: str | None = None
    current_files: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            # Blank line separates commits — flush current
            if current_hash is not None and current_files:
                result.append((current_hash, current_files))
                current_hash = None
                current_files = []
            continue

        parts = stripped.split("\t")
        if len(parts) == 3:
            added, deleted, filepath = parts
            # Skip binary files (git shows "-\t-\tpath")
            if added == "-" and deleted == "-":
                continue
            current_files.append(filepath)
        elif len(parts) == 1 and current_hash is None:
            # This is a commit hash line
            current_hash = stripped
        elif len(parts) == 1 and current_hash is not None:
            # New commit hash — flush previous
            if current_files:
                result.append((current_hash, current_files))
            current_hash = stripped
            current_files = []

    # Flush last commit
    if current_hash is not None and current_files:
        result.append((current_hash, current_files))

    return result


def compute_file_churn(
    commits: list[tuple[str, list[str]]],
) -> dict[str, int]:
    """Count commits per file from parsed git log.

    Returns a dict sorted by count descending.
    """
    counter: Counter[str] = Counter()
    for _hash, files in commits:
        counter.update(files)
    return dict(counter.most_common())


def compute_co_change(
    commits: list[tuple[str, list[str]]],
    *,
    min_shared: int = 2,
) -> list[dict[str, Any]]:
    """Compute Jaccard similarity for file pairs co-occurring in commits.

    Args:
        commits: Parsed git log from :func:`parse_git_log_numstat`.
        min_shared: Minimum number of shared commits to include a pair.

    Returns:
        List of dicts sorted by jaccard descending, each with keys:
        ``pair``, ``shared_commits``, ``union_commits``, ``jaccard``.
    """
    if not commits:
        return []

    # Build per-file commit sets
    file_commits: defaultdict[str, set[str]] = defaultdict(set)
    for commit_hash, files in commits:
        for f in files:
            file_commits[f].add(commit_hash)

    # Count co-occurrences via pair combinations within each commit
    pair_shared: Counter[tuple[str, str]] = Counter()
    for _hash, files in commits:
        for pair in combinations(sorted(set(files)), 2):
            pair_shared[pair] += 1

    # Build results with Jaccard
    results: list[dict[str, Any]] = []
    for (f1, f2), shared in pair_shared.items():
        if shared < min_shared:
            continue
        union = len(file_commits[f1] | file_commits[f2])
        jaccard = round(shared / union, 4)
        results.append(
            {
                "pair": [f1, f2],
                "shared_commits": shared,
                "union_commits": union,
                "jaccard": jaccard,
            }
        )

    results.sort(key=lambda r: r["jaccard"], reverse=True)
    return results


def compute_churn_complexity(
    churn: dict[str, int],
    complexity: dict[str, float],
) -> list[dict[str, Any]]:
    """Compute composite risk score per file (normalized churn * complexity).

    Both churn (commit count) and complexity (max cyclomatic complexity) are
    normalized to [0, 1] before multiplying.  Files absent from *complexity*
    receive complexity=0 (and therefore composite=0).

    Returns a list sorted by ``composite`` descending.
    """
    if not churn:
        return []

    max_churn = max(churn.values()) or 1
    max_cc = max(complexity.values()) if complexity else 1
    max_cc = max_cc or 1

    rows: list[dict[str, Any]] = []
    for filepath, commits in churn.items():
        cc = complexity.get(filepath, 0)
        norm_churn = commits / max_churn
        norm_cc = cc / max_cc
        composite = round(norm_churn * norm_cc, 4)
        rows.append(
            {
                "file": filepath,
                "churn": commits,
                "complexity": cc,
                "composite": composite,
            }
        )

    rows.sort(key=lambda r: r["composite"], reverse=True)
    return rows


def _compute_gini(values: list[int]) -> float:
    """Compute Gini coefficient measuring churn concentration across files.

    Returns 0.0 for empty or all-zero input.
    Range: 0 (perfectly even) to approaching 1 (all churn in one file).
    """
    if not values:
        return 0.0

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0

    return sum((2 * i - n + 1) * v for i, v in enumerate(sorted_vals)) / (n * total)


def _get_file_max_complexity(repo_path: Path) -> dict[str, float]:
    """Get max cyclomatic complexity per file using the hotspots module.

    Returns a dict of file path -> max CC value.
    """
    from local_deepwiki.generators.analysis.hotspots import analyze_hotspots

    result = analyze_hotspots(repo_path, metric="complexity", top_n=500)
    file_max: dict[str, float] = {}
    for hotspot in result.get("hotspots", []):
        filepath = hotspot["file"]
        cc = hotspot["metric_value"]
        if filepath not in file_max or cc > file_max[filepath]:
            file_max[filepath] = cc
    return file_max


def analyze_churn(
    repo_path: str | Path,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    top_n: int = 20,
    min_co_change: int = 2,
    include_complexity: bool = True,
) -> dict[str, Any]:
    """Full churn analysis orchestrator.

    Runs ``git log --numstat`` over *window_days*, computes per-file churn,
    co-change coupling, optionally churn x complexity composite, and Gini
    coefficient.

    Returns a dict with ``status``, ``file_churn``, ``co_change``,
    ``composite``, and ``stats`` keys.
    """
    repo = _validate_repo_path(repo_path)

    # Run git log
    cmd = [
        "git",
        "log",
        f"--since={window_days} days ago",
        "--format=%H",
        "--numstat",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=_GIT_LOG_CHURN_TIMEOUT,
        )
        raw = proc.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git log failed: %s", exc)
        raw = ""

    # Parse and compute
    commits = parse_git_log_numstat(raw)
    file_churn = compute_file_churn(commits)
    co_change = compute_co_change(commits, min_shared=min_co_change)

    # Churn x complexity composite
    composite: list[dict[str, Any]] = []
    if include_complexity and file_churn:
        try:
            complexity = _get_file_max_complexity(repo)
            composite = compute_churn_complexity(file_churn, complexity)[:top_n]
        except Exception as exc:
            logger.warning("Complexity analysis failed: %s", exc)

    # Gini coefficient
    gini = _compute_gini(list(file_churn.values()))

    # Build file_churn list (top_n)
    file_churn_list = [{"file": f, "commits": c} for f, c in list(file_churn.items())[:top_n]]

    return {
        "status": "success",
        "file_churn": file_churn_list,
        "co_change": co_change,
        "composite": composite,
        "stats": {
            "total_commits": len(commits),
            "total_files": len(file_churn),
            "window_days": window_days,
            "gini_coefficient": round(gini, 4),
        },
    }
