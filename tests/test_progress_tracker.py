"""Tests for progress tracking functionality."""

import json
import time
from pathlib import Path

import pytest

from local_deepwiki.generators.progress_tracker import (
    GenerationProgress,
    PhaseStats,
    _format_duration,
)


class TestFormatDuration:
    """Tests for _format_duration helper function."""

    def test_format_seconds_under_minute(self):
        """Test formatting durations under 60 seconds."""
        assert _format_duration(0.5) == "0.5s"
        assert _format_duration(1.0) == "1.0s"
        assert _format_duration(45.2) == "45.2s"
        assert _format_duration(59.9) == "59.9s"

    def test_format_minutes_under_hour(self):
        """Test formatting durations between 1-60 minutes."""
        assert _format_duration(60) == "1m 0s"
        assert _format_duration(90) == "1m 30s"
        assert _format_duration(125) == "2m 5s"
        assert _format_duration(3599) == "59m 59s"

    def test_format_hours(self):
        """Test formatting durations over 1 hour."""
        assert _format_duration(3600) == "1h 0m"
        assert _format_duration(3660) == "1h 1m"
        assert _format_duration(7200) == "2h 0m"
        assert _format_duration(5400) == "1h 30m"

    def test_format_zero(self):
        """Test formatting zero seconds."""
        assert _format_duration(0) == "0.0s"


class TestPhaseStats:
    """Tests for PhaseStats dataclass."""

    def test_phase_stats_creation(self):
        """Test creating a PhaseStats instance."""
        now = time.time()
        stats = PhaseStats(
            name="indexing",
            started_at=now,
            items_completed=10,
            items_total=20,
        )
        assert stats.name == "indexing"
        assert stats.started_at == now
        assert stats.items_completed == 10
        assert stats.items_total == 20
        assert stats.ended_at is None

    def test_phase_stats_duration_in_progress(self):
        """Test duration calculation while phase is still in progress."""
        start = time.time() - 5.0
        stats = PhaseStats(name="test", started_at=start)
        duration = stats.duration_seconds
        assert 4.9 <= duration <= 6.0

    def test_phase_stats_duration_completed(self):
        """Test duration calculation for completed phase."""
        stats = PhaseStats(name="test", started_at=1000.0, ended_at=1010.0)
        assert stats.duration_seconds == 10.0

    def test_phase_stats_rate_with_completions(self):
        """Test rate calculation with completed items."""
        stats = PhaseStats(
            name="test", started_at=0.0, ended_at=60.0, items_completed=30, items_total=30
        )
        assert stats.rate_per_minute == 30.0

    def test_phase_stats_rate_no_completions(self):
        """Test rate calculation with no completed items."""
        stats = PhaseStats(
            name="test", started_at=0.0, ended_at=60.0, items_completed=0, items_total=10
        )
        assert stats.rate_per_minute is None

    def test_phase_stats_rate_zero_duration(self):
        """Test rate calculation with zero duration."""
        stats = PhaseStats(
            name="test", started_at=100.0, ended_at=100.0, items_completed=10, items_total=10
        )
        assert stats.rate_per_minute is None


class TestGenerationProgress:
    """Tests for GenerationProgress class."""

    def test_creation(self, tmp_path):
        """Test creating a GenerationProgress instance."""
        progress = GenerationProgress(wiki_path=tmp_path)
        assert progress.wiki_path == tmp_path
        assert progress.total_files == 0
        assert progress.completed_files == 0
        assert progress.phase == "initializing"
        assert progress.current_file is None

    def test_creates_wiki_directory(self, tmp_path):
        """Test that progress tracker creates wiki directory."""
        wiki_path = tmp_path / "wiki"
        assert not wiki_path.exists()
        progress = GenerationProgress(wiki_path=wiki_path)
        assert wiki_path.exists()
        progress.finalize()

    def test_creates_log_file(self, tmp_path):
        """Test that progress tracker creates log file."""
        progress = GenerationProgress(wiki_path=tmp_path)
        log_file = tmp_path / "generation.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "Wiki generation started" in content
        progress.finalize()

    def test_start_phase(self, tmp_path):
        """Test starting a new phase."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=50)
        assert progress.phase == "file_docs"
        assert progress.total_files == 50
        assert progress.completed_files == 0
        assert "file_docs" in progress._phase_stats
        progress.finalize()

    def test_start_file(self, tmp_path):
        """Test marking a file as being processed."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=10)
        progress.start_file("src/main.py")
        assert progress.current_file == "src/main.py"
        progress.finalize()

    def test_complete_file(self, tmp_path):
        """Test marking a file as completed."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=10)
        progress.start_file("src/main.py")
        progress.complete_file("src/main.py")
        assert progress.completed_files == 1
        assert progress.current_file == "src/main.py"
        progress.finalize()

    def test_complete_file_without_path(self, tmp_path):
        """Test completing a file without specifying path."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=10)
        progress.start_file("src/main.py")
        progress.complete_file()
        assert progress.completed_files == 1
        assert progress.current_file == "src/main.py"
        progress.finalize()

    def test_multiple_file_completions(self, tmp_path):
        """Test completing multiple files updates rate calculation."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=5)
        for i in range(5):
            progress.start_file(f"src/file{i}.py")
            progress.complete_file(f"src/file{i}.py")
        assert progress.completed_files == 5
        assert len(progress._completion_times) == 5
        progress.finalize()

    def test_complete_phase(self, tmp_path):
        """Test completing a phase."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=3)
        for i in range(3):
            progress.complete_file(f"file{i}.py")
        progress.complete_phase()
        assert progress.current_file is None
        assert progress._phase_stats["file_docs"].ended_at is not None
        progress.finalize()

    def test_to_dict(self, tmp_path):
        """Test converting progress to dictionary."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=10)
        progress.complete_file("file1.py")
        progress.complete_file("file2.py")
        data = progress.to_dict()
        assert data["phase"] == "file_docs"
        assert data["completed"] == 2
        assert data["total"] == 10
        assert data["percent"] == 20.0
        assert "current_file" in data
        assert "rate_per_minute" in data
        assert "eta_minutes" in data
        progress.finalize()

    def test_to_dict_empty_total(self, tmp_path):
        """Test to_dict with zero total files."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("empty", total=0)
        data = progress.to_dict()
        assert data["percent"] == 0
        assert data["total"] == 0
        progress.finalize()

    def test_writes_status_file(self, tmp_path):
        """Test that status file is written on updates."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=10)
        progress.complete_file("test.py")
        status_file = tmp_path / "generation_status.json"
        assert status_file.exists()
        with open(status_file) as f:
            data = json.load(f)
        assert data["phase"] == "file_docs"
        assert data["completed"] == 1
        progress.finalize()

    def test_get_summary(self, tmp_path):
        """Test generating summary string."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("indexing", total=5)
        for i in range(5):
            progress.complete_file(f"file{i}.py")
        progress.complete_phase()
        progress.start_phase("file_docs", total=3)
        for i in range(3):
            progress.complete_file(f"doc{i}.md")
        progress.complete_phase()
        summary = progress.get_summary()
        assert "Wiki Generation Complete" in summary
        assert "indexing" in summary
        assert "file_docs" in summary
        progress.finalize()

    def test_finalize_success(self, tmp_path):
        """Test finalizing with success."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=2)
        progress.complete_file("test1.py")
        progress.complete_file("test2.py")
        summary = progress.finalize(success=True)
        assert "Wiki Generation Complete" in summary
        assert progress.phase == "complete"
        status_file = tmp_path / "generation_status.json"
        with open(status_file) as f:
            data = json.load(f)
        assert data["success"] is True
        assert "completed_at_iso" in data
        assert "phases" in data

    def test_finalize_failure(self, tmp_path):
        """Test finalizing with failure."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("file_docs", total=10)
        summary = progress.finalize(success=False)
        assert progress.phase == "failed"
        status_file = tmp_path / "generation_status.json"
        with open(status_file) as f:
            data = json.load(f)
        assert data["success"] is False

    def test_phase_transitions(self, tmp_path):
        """Test transitioning between phases."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("phase1", total=5)
        for _ in range(5):
            progress.complete_file()
        progress.start_phase("phase2", total=3)
        assert progress._phase_stats["phase1"].ended_at is not None
        assert progress._phase_stats["phase1"].items_completed == 5
        progress.finalize()

    def test_calculate_rate_empty(self, tmp_path):
        """Test rate calculation with no completions."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=10)
        rate = progress._calculate_rate()
        assert rate == 0.0
        progress.finalize()

    def test_calculate_eta_completed(self, tmp_path):
        """Test ETA calculation when all files completed."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=2)
        progress.complete_file()
        progress.complete_file()
        eta = progress._calculate_eta_minutes()
        assert eta == 0.0
        progress.finalize()

    def test_calculate_eta_no_rate(self, tmp_path):
        """Test ETA calculation with no rate established."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=10)
        eta = progress._calculate_eta_minutes()
        assert eta is None
        progress.finalize()

    def test_log_file_write_failure_handled(self, tmp_path):
        """Test that log file write failures are handled gracefully."""
        progress = GenerationProgress(wiki_path=tmp_path)
        # Set log file to None to simulate it not being available
        progress._log_file = None
        # Should not raise even with no log file
        progress._log("Test message")

    def test_status_write_failure_handled(self, tmp_path):
        """Test that status file write failures are handled gracefully."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress._write_status()
        progress.finalize()

    def test_rolling_window_limit(self, tmp_path):
        """Test that completion times respect the rolling window limit."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=30)
        for i in range(25):
            progress.complete_file(f"file{i}.py")
        assert len(progress._completion_times) == 20
        progress.finalize()

    def test_log_file_init_failure(self, tmp_path):
        """Test handling of log file initialization failure."""
        blocking_file = tmp_path / "blocked_wiki"
        blocking_file.write_text("blocking")
        progress = GenerationProgress(wiki_path=blocking_file)
        assert progress._log_file is None

    def test_completion_time_tracking(self, tmp_path):
        """Test that completion times are tracked correctly."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=3)
        for i in range(3):
            progress.complete_file(f"file{i}.py")
        assert len(progress._completion_times) == 3
        assert all(t >= 0 for t in progress._completion_times)
        progress.finalize()

    def test_phase_stats_in_final_status(self, tmp_path):
        """Test that phase stats are included in final status."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("indexing", total=5)
        for _ in range(5):
            progress.complete_file()
        progress.complete_phase()
        progress.finalize()
        status_file = tmp_path / "generation_status.json"
        with open(status_file) as f:
            data = json.load(f)
        assert "phases" in data
        assert "indexing" in data["phases"]
        assert data["phases"]["indexing"]["items_completed"] == 5

    def test_log_write_oserror_handled(self, tmp_path):
        """Test that OSError during log write is caught gracefully (lines 102-103)."""
        progress = GenerationProgress(wiki_path=tmp_path)

        class FailingWrite:
            """Mock file object that raises OSError on write."""
            def write(self, msg):
                raise OSError("Simulated write failure")
            def close(self):
                pass

        progress._log_file = FailingWrite()
        # This should not raise - OSError is caught
        progress._log("Test message that triggers OSError")
        # Verify we can still finalize
        progress._log_file = None  # Prevent issues in finalize
        progress.finalize()

    def test_calculate_rate_zero_avg_time(self, tmp_path):
        """Test rate calculation when average time is zero (line 194)."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=10)
        # Manually add zero completion times to trigger avg_time <= 0 branch
        progress._completion_times.append(0.0)
        progress._completion_times.append(0.0)
        rate = progress._calculate_rate()
        assert rate == 0.0
        progress.finalize()

    def test_write_status_oserror_handled(self, tmp_path):
        """Test that OSError during status write is caught gracefully (lines 237-238)."""
        # Create a wiki path that is a file, not a directory
        # This will cause mkdir to fail with OSError when _write_status tries to ensure directory exists
        blocking_file = tmp_path / "blocked_wiki_for_status"
        blocking_file.write_text("blocking")
        progress = GenerationProgress(wiki_path=blocking_file)
        # The _write_status call should not raise - OSError is caught
        progress._write_status()
        # Verify log_file is None (init also failed)
        assert progress._log_file is None

    def test_get_summary_sets_ended_at_for_incomplete_phase(self, tmp_path):
        """Test that get_summary sets ended_at for phases that haven't ended (line 262)."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("incomplete_phase", total=10)
        progress.complete_file("file1.py")
        # Don't call complete_phase - leave it incomplete
        assert progress._phase_stats["incomplete_phase"].ended_at is None
        # get_summary should set ended_at for the incomplete phase
        summary = progress.get_summary()
        assert progress._phase_stats["incomplete_phase"].ended_at is not None
        assert "incomplete_phase" in summary
        progress.finalize()

    def test_finalize_status_write_oserror_handled(self, tmp_path):
        """Test that OSError during finalize status write is caught (lines 321-322)."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=2)
        progress.complete_file("file1.py")
        # Remove status file and replace with a directory to cause OSError on write
        status_path = tmp_path / "generation_status.json"
        if status_path.exists():
            status_path.unlink()
        status_path.mkdir(parents=True, exist_ok=True)
        # This should not raise - OSError is caught
        summary = progress.finalize(success=True)
        assert "Wiki Generation Complete" in summary
        # Clean up
        status_path.rmdir()

    def test_finalize_log_close_oserror_handled(self, tmp_path):
        """Test that OSError during log file close is caught (lines 328-329)."""
        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=2)
        progress.complete_file("file1.py")

        class FailingClose:
            """Mock file object that raises OSError on close."""
            def write(self, msg):
                pass
            def close(self):
                raise OSError("Simulated close failure")

        progress._log_file = FailingClose()
        # This should not raise - OSError is caught
        summary = progress.finalize(success=True)
        assert "Wiki Generation Complete" in summary
