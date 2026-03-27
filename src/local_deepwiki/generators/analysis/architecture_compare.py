"""Architecture comparison between two git refs.

Uses git worktree to safely analyze a base ref without modifying
the current working tree. Returns metric deltas and new/resolved findings.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from local_deepwiki.generators.analysis.architecture_health import (
    analyze_architecture_health,
)
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

_GIT_TIMEOUT = 30


def _create_worktree(repo_path: Path, ref: str, target_dir: Path) -> bool:
    """Create a detached git worktree at *ref* in *target_dir*."""
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(target_dir), ref],
            cwd=str(repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=True,
        )
        return True
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as e:
        logger.warning("Failed to create worktree for %s: %s", ref, e)
        return False


def _remove_worktree(repo_path: Path, target_dir: Path) -> None:
    """Remove a git worktree and clean up."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(target_dir)],
            cwd=str(repo_path),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # Belt and suspenders: remove directory if worktree removal failed
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)


def _resolve_ref(repo_path: Path, ref: str) -> str | None:
    """Resolve a git ref to a short SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", ref],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=True,
        )
        return result.stdout.strip()
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return None


def _compute_deltas(
    base: dict[str, Any],
    head: dict[str, Any],
) -> dict[str, Any]:
    """Compute metric deltas between base and head health reports."""
    base_overall = base.get("overall", {})
    head_overall = head.get("overall", {})

    dimension_deltas: dict[str, Any] = {}
    for dim in ("complexity", "coupling", "smells", "layers"):
        base_score = base_overall.get("dimensions", {}).get(dim, {}).get("score", 0)
        head_score = head_overall.get("dimensions", {}).get(dim, {}).get("score", 0)
        delta = round(head_score - base_score, 1)
        dimension_deltas[dim] = {
            "base_score": base_score,
            "head_score": head_score,
            "delta": delta,
            "trend": (
                "improved" if delta > 0 else "degraded" if delta < 0 else "unchanged"
            ),
        }

    # New and resolved smells (tracked by file + line + type identity)
    base_smells = {
        (s.get("file"), s.get("line"), s.get("type"))
        for s in base.get("top_findings", {}).get("high_severity_smells", [])
    }
    head_smells = {
        (s.get("file"), s.get("line"), s.get("type"))
        for s in head.get("top_findings", {}).get("high_severity_smells", [])
    }
    new_smell_keys = head_smells - base_smells
    resolved_smell_keys = base_smells - head_smells

    return {
        "overall_delta": round(
            head_overall.get("score", 0) - base_overall.get("score", 0), 1
        ),
        "base_grade": base_overall.get("grade", "?"),
        "head_grade": head_overall.get("grade", "?"),
        "dimensions": dimension_deltas,
        "new_high_smells": len(new_smell_keys),
        "resolved_high_smells": len(resolved_smell_keys),
    }


_VERDICT_THRESHOLD = 2.0


def _compute_verdict(deltas: dict[str, Any]) -> dict[str, Any]:
    """Compute architecture verdict from deltas."""
    overall_delta = deltas.get("overall_delta", 0)
    dims = deltas.get("dimensions", {})

    improved: list[str] = []
    degraded: list[str] = []
    unchanged: list[str] = []

    for dim_name, dim_data in dims.items():
        delta = dim_data.get("delta", 0)
        if delta > _VERDICT_THRESHOLD:
            improved.append(dim_name)
        elif delta < -_VERDICT_THRESHOLD:
            degraded.append(dim_name)
        else:
            unchanged.append(dim_name)

    if overall_delta > _VERDICT_THRESHOLD:
        summary = f"Architecture improved (+{overall_delta})"
    elif overall_delta < -_VERDICT_THRESHOLD:
        summary = f"Architecture degraded ({overall_delta})"
    else:
        summary = f"No significant change ({overall_delta:+.1f})"

    return {
        "summary": summary,
        "improved": improved,
        "degraded": degraded,
        "unchanged": unchanged,
    }


def compare_architecture(
    repo_path: Path,
    project_name: str,
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
) -> dict[str, Any]:
    """Compare architecture health between two git refs.

    Args:
        repo_path: Repository root (must be a git repo).
        project_name: Project name for display.
        base_ref: Git ref for the baseline (default: HEAD~1).
        head_ref: Git ref for the comparison target (default: HEAD).

    Returns:
        Dict with base/head scores, deltas, and trend indicators.
    """
    base_sha = _resolve_ref(repo_path, base_ref)
    head_sha = _resolve_ref(repo_path, head_ref)

    if not base_sha:
        return {
            "status": "error",
            "message": f"Could not resolve git ref: {base_ref}",
        }
    if not head_sha:
        return {
            "status": "error",
            "message": f"Could not resolve git ref: {head_ref}",
        }

    # Analyze HEAD (current working tree or specified ref)
    if head_ref == "HEAD":
        head_health = analyze_architecture_health(repo_path, project_name)
    else:
        tmp_head = Path(tempfile.mkdtemp(prefix="deepwiki_head_"))
        try:
            if not _create_worktree(repo_path, head_ref, tmp_head):
                return {
                    "status": "error",
                    "message": f"Cannot create worktree for {head_ref}",
                }
            head_health = analyze_architecture_health(tmp_head, project_name)
        finally:
            _remove_worktree(repo_path, tmp_head)

    # Analyze base ref via worktree
    tmp_base = Path(tempfile.mkdtemp(prefix="deepwiki_base_"))
    try:
        if not _create_worktree(repo_path, base_ref, tmp_base):
            return {
                "status": "error",
                "message": (
                    f"Cannot create worktree for {base_ref}. Is this a shallow clone?"
                ),
            }
        base_health = analyze_architecture_health(tmp_base, project_name)
    finally:
        _remove_worktree(repo_path, tmp_base)

    deltas = _compute_deltas(base_health, head_health)
    verdict = _compute_verdict(deltas)

    logger.info(
        "Architecture comparison %s..%s: %s -> %s (delta: %+.1f)",
        base_sha,
        head_sha,
        deltas["base_grade"],
        deltas["head_grade"],
        deltas["overall_delta"],
    )

    return {
        "status": "success",
        "project_name": project_name,
        "base_ref": {"ref": base_ref, "sha": base_sha},
        "head_ref": {"ref": head_ref, "sha": head_sha},
        "deltas": deltas,
        "verdict": verdict,
        "base_health": base_health.get("overall", {}),
        "head_health": head_health.get("overall", {}),
    }
