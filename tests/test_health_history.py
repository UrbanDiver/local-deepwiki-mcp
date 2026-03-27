"""Tests for health history JSONL storage layer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.core.health_history import (
    HISTORY_FILENAME,
    get_latest,
    load_snapshots,
    save_snapshot,
)


def _make_health_data(score: float, grade: str) -> dict:
    """Build a dict matching ``analyze_architecture_health`` output shape.

    Includes ``factors`` and ``weights`` inside dimensions that should
    be stripped by ``save_snapshot``.
    """
    return {
        "overall": {
            "score": score,
            "grade": grade,
            "dimensions": {
                "complexity": {
                    "score": score + 1,
                    "grade": grade,
                    "factors": [{"name": "avg_complexity", "value": 3.2}],
                    "weights": {"cyclomatic": 0.5, "nesting": 0.5},
                },
                "coupling": {
                    "score": score - 1,
                    "grade": grade,
                    "factors": [{"name": "afferent", "value": 2.0}],
                    "weights": {"afferent": 0.5, "efferent": 0.5},
                },
            },
        },
    }


@patch("local_deepwiki.core.health_history._get_short_git_ref", return_value="abc1234")
class TestSaveSnapshot:
    """Tests for save_snapshot."""

    def test_save_snapshot_creates_file(self, _mock_ref, tmp_path: Path) -> None:
        """Creates JSONL file with correct shape, factors stripped."""
        wiki_path = tmp_path / "wiki"
        health_data = _make_health_data(75.0, "B")

        save_snapshot(wiki_path, health_data)

        history_file = wiki_path / HISTORY_FILENAME
        assert history_file.exists()

        lines = history_file.read_text().strip().splitlines()
        assert len(lines) == 1

        snapshot = json.loads(lines[0])
        assert snapshot["score"] == 75.0
        assert snapshot["grade"] == "B"
        assert snapshot["git_ref"] == "abc1234"
        assert "timestamp" in snapshot

        # Dimensions preserved with score/grade only
        assert "complexity" in snapshot["dimensions"]
        assert snapshot["dimensions"]["complexity"]["score"] == 76.0
        assert snapshot["dimensions"]["complexity"]["grade"] == "B"

        # factors and weights must be stripped
        assert "factors" not in snapshot["dimensions"]["complexity"]
        assert "weights" not in snapshot["dimensions"]["complexity"]
        assert "factors" not in snapshot["dimensions"]["coupling"]
        assert "weights" not in snapshot["dimensions"]["coupling"]

    def test_save_snapshot_appends(self, _mock_ref, tmp_path: Path) -> None:
        """Two saves produce two JSONL lines."""
        wiki_path = tmp_path / "wiki"
        save_snapshot(wiki_path, _make_health_data(70.0, "C"))
        save_snapshot(wiki_path, _make_health_data(80.0, "B"))

        lines = (wiki_path / HISTORY_FILENAME).read_text().strip().splitlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["score"] == 70.0
        assert second["score"] == 80.0

    def test_save_snapshot_missing_overall(self, _mock_ref, tmp_path: Path) -> None:
        """No-op when health_data lacks 'overall' key."""
        wiki_path = tmp_path / "wiki"
        save_snapshot(wiki_path, {"status": "error"})

        history_file = wiki_path / HISTORY_FILENAME
        assert not history_file.exists()


class TestLoadSnapshots:
    """Tests for load_snapshots."""

    def test_load_snapshots_empty(self, tmp_path: Path) -> None:
        """Returns empty list when no history file exists."""
        result = load_snapshots(tmp_path / "nonexistent")
        assert result == []

    def test_load_snapshots_returns_all(self, tmp_path: Path) -> None:
        """Returns all snapshots in chronological order."""
        history_file = tmp_path / HISTORY_FILENAME
        entries = [
            {"timestamp": "2026-03-01T00:00:00+00:00", "score": 60.0, "grade": "C"},
            {"timestamp": "2026-03-02T00:00:00+00:00", "score": 70.0, "grade": "B"},
            {"timestamp": "2026-03-03T00:00:00+00:00", "score": 80.0, "grade": "A"},
        ]
        history_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = load_snapshots(tmp_path)
        assert len(result) == 3
        assert result[0]["score"] == 60.0
        assert result[1]["score"] == 70.0
        assert result[2]["score"] == 80.0

    def test_load_snapshots_since_filter(self, tmp_path: Path) -> None:
        """Filters snapshots by ISO date string."""
        history_file = tmp_path / HISTORY_FILENAME
        entries = [
            {"timestamp": "2026-03-01T00:00:00+00:00", "score": 60.0},
            {"timestamp": "2026-03-15T00:00:00+00:00", "score": 70.0},
            {"timestamp": "2026-03-20T00:00:00+00:00", "score": 80.0},
        ]
        history_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = load_snapshots(tmp_path, since="2026-03-15T00:00:00+00:00")
        assert len(result) == 2
        assert result[0]["score"] == 70.0
        assert result[1]["score"] == 80.0

    def test_load_snapshots_skips_malformed(self, tmp_path: Path) -> None:
        """Skips bad JSON lines and returns valid ones."""
        history_file = tmp_path / HISTORY_FILENAME
        content = (
            '{"timestamp": "2026-03-01T00:00:00+00:00", "score": 60.0}\n'
            "not valid json\n"
            '{"timestamp": "2026-03-02T00:00:00+00:00", "score": 70.0}\n'
        )
        history_file.write_text(content)

        result = load_snapshots(tmp_path)
        assert len(result) == 2
        assert result[0]["score"] == 60.0
        assert result[1]["score"] == 70.0


class TestGetLatest:
    """Tests for get_latest."""

    def test_get_latest(self, tmp_path: Path) -> None:
        """Returns the most recent snapshot."""
        history_file = tmp_path / HISTORY_FILENAME
        entries = [
            {"timestamp": "2026-03-01T00:00:00+00:00", "score": 60.0, "grade": "C"},
            {"timestamp": "2026-03-10T00:00:00+00:00", "score": 80.0, "grade": "B"},
        ]
        history_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = get_latest(tmp_path)
        assert result is not None
        assert result["score"] == 80.0
        assert result["grade"] == "B"

    def test_get_latest_no_history(self, tmp_path: Path) -> None:
        """Returns None when no history exists."""
        result = get_latest(tmp_path / "nonexistent")
        assert result is None
