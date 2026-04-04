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
