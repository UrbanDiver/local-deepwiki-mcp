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


_HIGH_DISTANCE_THRESHOLD = 0.7

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


def _compute_coupling_diff(
    base_metrics: list[dict[str, Any]],
    head_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Diff high-distance modules between base and head coupling metrics."""
    base_high = {
        m["module"]: m["distance"]
        for m in base_metrics
        if m.get("distance", 0) > _HIGH_DISTANCE_THRESHOLD
    }
    head_high = {
        m["module"]: m["distance"]
        for m in head_metrics
        if m.get("distance", 0) > _HIGH_DISTANCE_THRESHOLD
    }
    new_high = [
        {"module": mod, "distance": dist}
        for mod, dist in head_high.items()
        if mod not in base_high
    ]
    resolved_high = [
        {"module": mod, "distance": dist}
        for mod, dist in base_high.items()
        if mod not in head_high
    ]
    return {
        "base_modules": len(base_metrics),
        "head_modules": len(head_metrics),
        "new_high_distance": new_high,
        "resolved_high_distance": resolved_high,
    }


def _compute_smell_diff(
    base_health: dict[str, Any],
    head_health: dict[str, Any],
) -> dict[str, Any]:
    """Diff high-severity smells between base and head health reports."""

    def _smell_key(s: dict[str, Any]) -> tuple[str, str, str]:
        return (s.get("type", ""), s.get("file", ""), s.get("entity", ""))

    base_smells = base_health.get("top_findings", {}).get("high_severity_smells", [])
    head_smells = head_health.get("top_findings", {}).get("high_severity_smells", [])
    base_keys = {_smell_key(s) for s in base_smells}
    head_keys = {_smell_key(s) for s in head_smells}
    new_keys = head_keys - base_keys
    resolved_keys = base_keys - head_keys
    new_smells = [
        {"type": s.get("type"), "file": s.get("file"), "entity": s.get("entity")}
        for s in head_smells
        if _smell_key(s) in new_keys
    ]
    resolved_smells = [
        {"type": s.get("type"), "file": s.get("file"), "entity": s.get("entity")}
        for s in base_smells
        if _smell_key(s) in resolved_keys
    ]
    return {"new_smells": new_smells, "resolved_smells": resolved_smells}


def _analyze_ref_health(
    repo_path: Path,
    project_name: str,
    git_ref: str,
    tmp_prefix: str,
    error_msg_prefix: str,
) -> dict[str, Any] | str:
    """Analyze architecture health for a git ref via a temporary worktree.

    Returns the health dict on success, or an error message string on failure.
    Uses the working tree directly when ``git_ref == "HEAD"``.
    """
    if git_ref == "HEAD":
        return analyze_architecture_health(repo_path, project_name)
    tmp = Path(tempfile.mkdtemp(prefix=tmp_prefix))
    try:
        if not _create_worktree(repo_path, git_ref, tmp):
            return f"{error_msg_prefix}{git_ref}"
        return analyze_architecture_health(tmp, project_name)
    finally:
        _remove_worktree(repo_path, tmp)


def _build_full_detail_addons(
    repo_path: Path,
    base_ref: str,
    base_health: dict[str, Any],
    head_health: dict[str, Any],
) -> dict[str, Any]:
    """Compute coupling diff and smell diff for ``detail_level='full'``."""
    from local_deepwiki.generators.analysis.coupling import analyze_coupling_metrics

    head_coupling = analyze_coupling_metrics(repo_path).get("metrics", [])
    tmp_base = Path(tempfile.mkdtemp(prefix="deepwiki_coupling_"))
    try:
        if _create_worktree(repo_path, base_ref, tmp_base):
            base_coupling = analyze_coupling_metrics(tmp_base).get("metrics", [])
        else:
            base_coupling = []
    finally:
        _remove_worktree(repo_path, tmp_base)
    return {
        "coupling_changes": _compute_coupling_diff(base_coupling, head_coupling),
        "smell_diff": _compute_smell_diff(base_health, head_health),
    }


def compare_architecture(
    repo_path: Path,
    project_name: str,
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
    *,
    detail_level: str = "standard",
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
        return {"status": "error", "message": f"Could not resolve git ref: {base_ref}"}
    if not head_sha:
        return {"status": "error", "message": f"Could not resolve git ref: {head_ref}"}

    head_result = _analyze_ref_health(
        repo_path,
        project_name,
        head_ref,
        "deepwiki_head_",
        "Cannot create worktree for ",
    )
    if isinstance(head_result, str):
        return {"status": "error", "message": head_result}
    head_health = head_result

    base_result = _analyze_ref_health(
        repo_path,
        project_name,
        base_ref,
        "deepwiki_base_",
        f"Cannot create worktree for {base_ref}. Is this a shallow clone? ref=",
    )
    if isinstance(base_result, str):
        return {"status": "error", "message": base_result}
    base_health = base_result

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

    result: dict[str, Any] = {
        "status": "success",
        "project_name": project_name,
        "base_ref": {"ref": base_ref, "sha": base_sha},
        "head_ref": {"ref": head_ref, "sha": head_sha},
        "deltas": deltas,
        "verdict": verdict,
        "base_health": base_health.get("overall", {}),
        "head_health": head_health.get("overall", {}),
    }

    if detail_level == "full":
        result = {
            **result,
            **_build_full_detail_addons(repo_path, base_ref, base_health, head_health),
        }

    return result
