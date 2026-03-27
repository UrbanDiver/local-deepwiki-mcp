"""Append-only JSONL storage for architecture health snapshots.

Stores timestamped health scores alongside git refs so that health
trends can be tracked over time.  The storage format is one JSON
object per line (JSONL), which is safe for concurrent appends and
trivial to parse incrementally.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

HISTORY_FILENAME = "health-history.jsonl"
GIT_REV_PARSE_TIMEOUT = 5


def _get_short_git_ref(wiki_path: Path) -> str:
    """Return the short HEAD ref for the repo containing *wiki_path*.

    Falls back to ``"unknown"`` when git is unavailable or the path is
    not inside a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(wiki_path),
            timeout=GIT_REV_PARSE_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Could not determine git ref: %s", exc)
    return "unknown"


def save_snapshot(wiki_path: Path, health_data: dict) -> None:
    """Persist a health snapshot as a single JSONL line.

    Extracts the overall score, grade, and per-dimension scores from
    *health_data* (stripping verbose ``factors`` / ``weights`` keys)
    and appends the result to ``wiki_path / HISTORY_FILENAME``.

    No-op when *health_data* lacks an ``"overall"`` key.
    """
    overall = health_data.get("overall")
    if overall is None:
        return

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_ref": _get_short_git_ref(wiki_path),
        "score": overall["score"],
        "grade": overall["grade"],
        "dimensions": {
            name: {"score": dim["score"], "grade": dim["grade"]}
            for name, dim in overall.get("dimensions", {}).items()
        },
    }

    wiki_path.mkdir(parents=True, exist_ok=True)
    history_file = wiki_path / HISTORY_FILENAME

    with open(history_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot) + "\n")


def load_snapshots(
    wiki_path: Path,
    *,
    since: str | None = None,
) -> list[dict]:
    """Load snapshots from the JSONL history file.

    Args:
        wiki_path: Directory containing the history file.
        since: Optional ISO-8601 timestamp string.  Only snapshots
            whose ``timestamp`` is >= *since* are returned.  Works via
            lexicographic comparison (ISO-8601 sorts correctly).

    Returns:
        A list of snapshot dicts sorted by timestamp ascending.
        Returns an empty list when the history file does not exist.
    """
    history_file = wiki_path / HISTORY_FILENAME
    if not history_file.exists():
        return []

    snapshots: list[dict] = []
    with open(history_file, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                logger.debug("Skipping malformed JSONL line: %s", stripped)
                continue

            if since is not None and entry.get("timestamp", "") < since:
                continue
            snapshots.append(entry)

    return sorted(snapshots, key=lambda s: s.get("timestamp", ""))


def get_latest(wiki_path: Path) -> dict | None:
    """Return the most recent snapshot, or ``None`` if no history exists."""
    snapshots = load_snapshots(wiki_path)
    if not snapshots:
        return None
    return snapshots[-1]
