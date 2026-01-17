"""Live progress tracking for wiki generation."""

import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "1h 23m 45s" or "45.2s".
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


@dataclass
class PhaseStats:
    """Statistics for a single generation phase."""

    name: str
    started_at: float
    ended_at: float | None = None
    items_completed: int = 0
    items_total: int = 0

    @property
    def duration_seconds(self) -> float:
        """Get phase duration in seconds."""
        end = self.ended_at or time.time()
        return end - self.started_at

    @property
    def rate_per_minute(self) -> float | None:
        """Get items per minute rate."""
        if self.items_completed == 0 or self.duration_seconds == 0:
            return None
        return (self.items_completed / self.duration_seconds) * 60


@dataclass
class GenerationProgress:
    """Tracks wiki generation progress with timing statistics."""

    wiki_path: Path
    total_files: int = 0
    completed_files: int = 0
    phase: str = "initializing"
    current_file: str | None = None
    started_at: float = field(default_factory=time.time)
    phase_started_at: float = field(default_factory=time.time)

    # Rolling window for rate calculation (last N completion times)
    _completion_times: deque = field(default_factory=lambda: deque(maxlen=20))
    _last_completion_time: float = field(default_factory=time.time)

    # Phase statistics for summary
    _phase_stats: dict[str, PhaseStats] = field(default_factory=dict)

    # Log file handle
    _log_file: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize log file."""
        self._init_log_file()

    def _init_log_file(self) -> None:
        """Initialize the log file for appending."""
        try:
            self.wiki_path.mkdir(parents=True, exist_ok=True)
            log_path = self.wiki_path / "generation.log"
            self._log_file = open(log_path, "a", buffering=1)  # Line buffered
            self._log(f"=== Wiki generation started ===")
        except OSError:
            self._log_file = None

    def _log(self, message: str) -> None:
        """Append a timestamped message to the log file.

        Args:
            message: Message to log.
        """
        if self._log_file:
            try:
                timestamp = time.strftime("%H:%M:%S")
                self._log_file.write(f"{timestamp} {message}\n")
            except OSError:
                pass

    def start_phase(self, phase: str, total: int = 0) -> None:
        """Start a new generation phase.

        Args:
            phase: Name of the phase (e.g., "indexing", "modules", "file_docs").
            total: Total items to process in this phase.
        """
        # End previous phase if any
        if self.phase in self._phase_stats:
            self._phase_stats[self.phase].ended_at = time.time()

        self.phase = phase
        self.total_files = total
        self.completed_files = 0
        self.current_file = None
        self.phase_started_at = time.time()
        self._completion_times.clear()
        self._last_completion_time = time.time()

        # Track phase stats
        self._phase_stats[phase] = PhaseStats(
            name=phase,
            started_at=self.phase_started_at,
            items_total=total,
        )

        self._log(f"[{phase}] Started (total: {total})")
        self._write_status()

    def start_file(self, file_path: str) -> None:
        """Mark a file as being processed.

        Args:
            file_path: Path to the file being processed.
        """
        self.current_file = file_path
        self._write_status()

    def complete_file(self, file_path: str | None = None) -> None:
        """Mark a file as completed.

        Args:
            file_path: Optional path to update current_file display.
        """
        now = time.time()
        elapsed = now - self._last_completion_time
        self._completion_times.append(elapsed)
        self._last_completion_time = now

        self.completed_files += 1
        if file_path:
            self.current_file = file_path

        # Update phase stats
        if self.phase in self._phase_stats:
            self._phase_stats[self.phase].items_completed = self.completed_files

        # Log completion
        elapsed_str = f"{elapsed:.1f}s" if elapsed < 60 else _format_duration(elapsed)
        rate = self._calculate_rate()
        eta = self._calculate_eta_minutes()
        eta_str = f", ETA: {_format_duration(eta * 60)}" if eta and eta > 0 else ""
        self._log(
            f"[{self.completed_files}/{self.total_files}] "
            f"Completed: {file_path or 'unknown'} ({elapsed_str}, {rate:.1f}/min{eta_str})"
        )

        self._write_status()

    def complete_phase(self) -> None:
        """Mark the current phase as complete."""
        now = time.time()
        if self.phase in self._phase_stats:
            stats = self._phase_stats[self.phase]
            stats.ended_at = now
            duration = _format_duration(stats.duration_seconds)
            rate = stats.rate_per_minute
            rate_str = f", {rate:.1f}/min" if rate else ""
            self._log(f"[{self.phase}] Complete ({stats.items_completed} items, {duration}{rate_str})")

        self.current_file = None
        self._write_status()

    def _calculate_rate(self) -> float:
        """Calculate files per minute based on recent completions."""
        if not self._completion_times:
            return 0.0
        avg_time = sum(self._completion_times) / len(self._completion_times)
        if avg_time <= 0:
            return 0.0
        return 60.0 / avg_time  # files per minute

    def _calculate_eta_minutes(self) -> float | None:
        """Calculate estimated time remaining in minutes."""
        remaining = self.total_files - self.completed_files
        if remaining <= 0:
            return 0.0

        rate = self._calculate_rate()
        if rate <= 0:
            return None

        return remaining / rate

    def to_dict(self) -> dict[str, Any]:
        """Convert progress to dictionary for JSON serialization."""
        now = time.time()
        elapsed_total = now - self.started_at
        elapsed_phase = now - self.phase_started_at
        rate = self._calculate_rate()
        eta = self._calculate_eta_minutes()

        return {
            "phase": self.phase,
            "completed": self.completed_files,
            "total": self.total_files,
            "percent": round(100 * self.completed_files / self.total_files, 1) if self.total_files > 0 else 0,
            "current_file": self.current_file,
            "rate_per_minute": round(rate, 2) if rate > 0 else None,
            "eta_minutes": round(eta, 1) if eta is not None else None,
            "elapsed_phase_seconds": round(elapsed_phase, 1),
            "elapsed_total_seconds": round(elapsed_total, 1),
            "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.started_at)),
        }

    def _write_status(self) -> None:
        """Write current status to the status file."""
        status_path = self.wiki_path / "generation_status.json"
        try:
            self.wiki_path.mkdir(parents=True, exist_ok=True)
            with open(status_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except OSError:
            pass  # Don't fail generation if status write fails

    def get_summary(self) -> str:
        """Generate a summary of the generation run.

        Returns:
            Formatted summary string.
        """
        now = time.time()
        total_duration = now - self.started_at

        lines = [
            "",
            "=" * 50,
            "  Wiki Generation Complete",
            "=" * 50,
            f"  Total time: {_format_duration(total_duration)}",
            "",
        ]

        # Phase breakdown
        total_items = 0
        for phase_name, stats in self._phase_stats.items():
            if stats.ended_at is None:
                stats.ended_at = now
            duration = _format_duration(stats.duration_seconds)
            rate = stats.rate_per_minute
            rate_str = f", {rate:.1f}/min" if rate and rate < 1000 else ""
            items_str = f" ({stats.items_completed} pages{rate_str})" if stats.items_completed > 0 else ""
            lines.append(f"  - {phase_name}: {duration}{items_str}")
            total_items += stats.items_completed

        lines.extend([
            "",
            f"  Total pages: {total_items}",
            "=" * 50,
            "",
        ])

        return "\n".join(lines)

    def finalize(self, success: bool = True) -> str:
        """Mark generation as complete and write final status.

        Args:
            success: Whether generation completed successfully.

        Returns:
            Summary string for display.
        """
        # End current phase
        if self.phase in self._phase_stats:
            self._phase_stats[self.phase].ended_at = time.time()

        self.phase = "complete" if success else "failed"
        self.current_file = None

        # Generate summary
        summary = self.get_summary()

        # Log summary
        for line in summary.strip().split("\n"):
            self._log(line)

        # Write final status
        status = self.to_dict()
        status["success"] = success
        status["completed_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

        # Add phase stats to final status
        status["phases"] = {
            name: {
                "duration_seconds": round(stats.duration_seconds, 1),
                "items_completed": stats.items_completed,
                "rate_per_minute": round(stats.rate_per_minute, 2) if stats.rate_per_minute else None,
            }
            for name, stats in self._phase_stats.items()
        }

        status_path = self.wiki_path / "generation_status.json"
        try:
            with open(status_path, "w") as f:
                json.dump(status, f, indent=2)
        except OSError:
            pass

        # Close log file
        if self._log_file:
            try:
                self._log_file.close()
            except OSError:
                pass

        return summary
