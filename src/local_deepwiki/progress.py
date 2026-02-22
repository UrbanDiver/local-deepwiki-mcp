"""Progress management for MCP operations with ETA calculation and buffered notifications.

This module provides progress tracking infrastructure for long-running MCP operations
with support for both push (notifications) and pull (polling) models.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from local_deepwiki.logging import get_logger

__all__ = [
    "GetOperationProgressArgs",
    "OperationProgressRegistry",
    "OperationProgressResponse",
    "OperationType",
    "ProgressBuffer",
    "ProgressManager",
    "ProgressPhase",
    "ProgressUpdate",
    "get_progress_registry",
]

logger = get_logger(__name__)


class OperationType(StrEnum):
    """Types of operations that can be tracked."""

    INDEX_REPOSITORY = "index_repository"
    DEEP_RESEARCH = "deep_research"
    EXPORT_HTML = "export_html"
    EXPORT_PDF = "export_pdf"
    ASK_QUESTION = "ask_question"


class ProgressPhase(StrEnum):
    """Phases within an operation."""

    # Indexing phases
    SCANNING = "scanning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    STORING = "storing"
    WIKI_GENERATION = "wiki_generation"

    # Research phases
    DECOMPOSITION = "decomposition"
    RETRIEVAL = "retrieval"
    GAP_ANALYSIS = "gap_analysis"
    SYNTHESIS = "synthesis"

    # Export phases
    RENDERING = "rendering"
    WRITING = "writing"

    # Generic
    PROCESSING = "processing"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    """A single progress update."""

    operation_id: str
    operation_type: OperationType
    phase: ProgressPhase
    current: int
    total: int | None
    message: str
    timestamp: float = field(default_factory=time.time)
    eta_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "phase": self.phase.value,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "timestamp": self.timestamp,
            "eta_seconds": self.eta_seconds,
            "percent_complete": (
                round(self.current / self.total * 100, 1)
                if self.total and self.total > 0
                else None
            ),
            "metadata": self.metadata,
        }


class ProgressManager:
    """Manages progress tracking for a single operation.

    Supports ETA calculation based on historical performance data
    and current progress rate.
    """

    def __init__(
        self,
        operation_id: str,
        operation_type: OperationType,
        total: int | None = None,
        historical_data: dict[str, Any] | None = None,
    ):
        """Initialize the progress manager.

        Args:
            operation_id: Unique identifier for this operation.
            operation_type: Type of operation being tracked.
            total: Total number of items to process (None if unknown).
            historical_data: Historical timing data for ETA prediction.
        """
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.total = total
        self.current = 0
        self.started_at = time.time()
        self.phase = ProgressPhase.PROCESSING
        self.message = ""

        # Historical data for better ETA prediction
        self._historical_data = historical_data or {}

        # Timing data
        self._phase_start_times: dict[ProgressPhase, float] = {}
        self._phase_durations: dict[ProgressPhase, float] = {}

        # Callbacks
        self._callbacks: list[Callable[[ProgressUpdate], None]] = []

        # Rate tracking for ETA
        self._rate_samples: list[tuple[float, int]] = []  # (timestamp, progress)
        self._last_progress_time = self.started_at

    def update(
        self,
        current: int | None = None,
        total: int | None = None,
        message: str = "",
        phase: ProgressPhase | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProgressUpdate:
        """Update progress and notify callbacks.

        Args:
            current: Current progress value.
            total: Total items (updates if different from initial).
            message: Human-readable progress message.
            phase: Current phase of operation.
            metadata: Additional metadata to include.

        Returns:
            The progress update that was created.
        """
        now = time.time()

        if current is not None:
            self.current = current
        if total is not None:
            self.total = total
        if message:
            self.message = message
        if phase is not None:
            # Track phase transitions
            if phase != self.phase and self.phase in self._phase_start_times:
                self._phase_durations[self.phase] = (
                    now - self._phase_start_times[self.phase]
                )
            if phase not in self._phase_start_times:
                self._phase_start_times[phase] = now
            self.phase = phase

        # Track rate samples for ETA calculation (keep last 10)
        self._rate_samples.append((now, self.current))
        if len(self._rate_samples) > 10:
            self._rate_samples.pop(0)
        self._last_progress_time = now

        # Calculate ETA
        eta = self.get_eta()

        # Create progress update
        update = ProgressUpdate(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            phase=self.phase,
            current=self.current,
            total=self.total,
            message=self.message,
            timestamp=now,
            eta_seconds=eta,
            metadata=metadata or {},
        )

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(update)
            except (RuntimeError, ValueError, TypeError) as e:
                # RuntimeError: Callback runtime failures
                # ValueError: Invalid callback state
                # TypeError: Callback signature mismatch
                logger.warning("Progress callback failed: %s", e)

        return update

    def get_eta(self) -> float | None:
        """Calculate estimated time remaining.

        Uses a combination of:
        1. Current rate of progress (weighted more heavily)
        2. Historical data for this operation type (if available)

        Returns:
            Estimated seconds remaining, or None if cannot estimate.
        """
        if self.total is None or self.total <= 0:
            return None

        remaining = self.total - self.current
        if remaining <= 0:
            return 0.0

        # Calculate current rate from recent samples
        current_rate = self._calculate_current_rate()

        # Get historical rate if available
        historical_rate = self._get_historical_rate()

        # Combine rates with weighting (current rate weighted 70%, historical 30%)
        if current_rate is not None and historical_rate is not None:
            rate = current_rate * 0.7 + historical_rate * 0.3
        elif current_rate is not None:
            rate = current_rate
        elif historical_rate is not None:
            rate = historical_rate
        else:
            return None

        if rate <= 0:
            return None

        return remaining / rate

    def _calculate_current_rate(self) -> float | None:
        """Calculate items per second from recent progress."""
        if len(self._rate_samples) < 2:
            return None

        # Use first and last samples for rate calculation
        first_time, first_progress = self._rate_samples[0]
        last_time, last_progress = self._rate_samples[-1]

        time_diff = last_time - first_time
        progress_diff = last_progress - first_progress

        if time_diff <= 0 or progress_diff <= 0:
            return None

        return progress_diff / time_diff

    def _get_historical_rate(self) -> float | None:
        """Get historical rate from past operations."""
        key = f"{self.operation_type.value}_rate"
        return self._historical_data.get(key)

    def get_progress_dict(self) -> dict[str, Any]:
        """Return progress as dict for serialization.

        Returns:
            Dictionary with current progress state.
        """
        elapsed = time.time() - self.started_at
        eta = self.get_eta()

        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "phase": self.phase.value,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "percent_complete": (
                round(self.current / self.total * 100, 1)
                if self.total and self.total > 0
                else None
            ),
            "elapsed_seconds": round(elapsed, 2),
            "eta_seconds": round(eta, 2) if eta is not None else None,
            "started_at": self.started_at,
            "phase_durations": {
                k.value: round(v, 2) for k, v in self._phase_durations.items()
            },
        }

    def add_callback(self, callback: Callable[[ProgressUpdate], None]) -> None:
        """Add progress callback.

        Args:
            callback: Function to call on progress updates.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ProgressUpdate], None]) -> None:
        """Remove progress callback.

        Args:
            callback: Function to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def complete(self, message: str = "Complete") -> ProgressUpdate:
        """Mark operation as complete.

        Args:
            message: Completion message.

        Returns:
            Final progress update.
        """
        if self.total is not None:
            self.current = self.total
        return self.update(
            phase=ProgressPhase.COMPLETE,
            message=message,
        )


class ProgressBuffer:
    """Buffers progress updates for batched notifications.

    Helps reduce notification spam by batching rapid progress updates
    and only flushing at configured intervals.
    """

    def __init__(
        self,
        flush_interval: float = 0.5,
        max_buffer_size: int = 100,
    ):
        """Initialize the buffer.

        Args:
            flush_interval: Minimum seconds between flushes.
            max_buffer_size: Maximum buffered updates before forced flush.
        """
        self._buffer: list[ProgressUpdate] = []
        self._flush_interval = flush_interval
        self._max_buffer_size = max_buffer_size
        self._last_flush = time.time()  # Initialize to current time

    def add(self, update: ProgressUpdate) -> list[ProgressUpdate] | None:
        """Add update to buffer, return buffered updates if flush needed.

        Args:
            update: Progress update to buffer.

        Returns:
            List of buffered updates if flush triggered, None otherwise.
        """
        self._buffer.append(update)

        now = time.time()
        should_flush = (
            now - self._last_flush >= self._flush_interval
            or len(self._buffer) >= self._max_buffer_size
            or update.phase == ProgressPhase.COMPLETE
        )

        if should_flush:
            return self.flush()
        return None

    def flush(self) -> list[ProgressUpdate]:
        """Force flush all buffered updates.

        Returns:
            List of all buffered updates (may be empty).
        """
        updates = self._buffer
        self._buffer = []
        self._last_flush = time.time()
        return updates

    @property
    def buffered_count(self) -> int:
        """Number of currently buffered updates."""
        return len(self._buffer)


class OperationProgressRegistry:
    """Registry for tracking active operations and their progress.

    Provides a central place to store and retrieve progress for all
    active operations, supporting the pull-based progress model.
    """

    def __init__(self):
        """Initialize the registry."""
        self._operations: dict[str, ProgressManager] = {}
        self._historical_data: dict[str, dict[str, Any]] = {}
        self._data_path: Path | None = None

    def set_data_path(self, path: Path) -> None:
        """Set the path for persisting historical data.

        Args:
            path: Path to store historical timing data.
        """
        self._data_path = path
        self._load_historical_data()

    def _load_historical_data(self) -> None:
        """Load historical timing data from disk."""
        if self._data_path and self._data_path.exists():
            try:
                data = json.loads(self._data_path.read_text())
                self._historical_data = data
                logger.debug("Loaded historical progress data from %s", self._data_path)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                # json.JSONDecodeError: Invalid JSON format
                # OSError: File system or file access errors
                # ValueError: Invalid data structure
                logger.warning("Failed to load historical progress data: %s", e)

    def _save_historical_data(self) -> None:
        """Save historical timing data to disk."""
        if self._data_path:
            try:
                self._data_path.parent.mkdir(parents=True, exist_ok=True)
                self._data_path.write_text(json.dumps(self._historical_data, indent=2))
            except OSError as e:
                logger.warning("Failed to save historical progress data: %s", e)

    def start_operation(
        self,
        operation_id: str,
        operation_type: OperationType,
        total: int | None = None,
    ) -> ProgressManager:
        """Start tracking a new operation.

        Args:
            operation_id: Unique identifier for this operation.
            operation_type: Type of operation.
            total: Total items to process.

        Returns:
            ProgressManager for the operation.
        """
        historical = self._historical_data.get(operation_type.value, {})
        manager = ProgressManager(
            operation_id=operation_id,
            operation_type=operation_type,
            total=total,
            historical_data=historical,
        )
        self._operations[operation_id] = manager
        logger.debug(
            "Started tracking operation %s (%s)", operation_id, operation_type.value
        )
        return manager

    def get_operation(self, operation_id: str) -> ProgressManager | None:
        """Get progress manager for an operation.

        Args:
            operation_id: Operation identifier.

        Returns:
            ProgressManager or None if not found.
        """
        return self._operations.get(operation_id)

    def complete_operation(
        self,
        operation_id: str,
        record_timing: bool = True,
    ) -> dict[str, Any] | None:
        """Complete and remove an operation.

        Args:
            operation_id: Operation to complete.
            record_timing: Whether to record timing for future ETA predictions.

        Returns:
            Final progress dict, or None if operation not found.
        """
        manager = self._operations.pop(operation_id, None)
        if not manager:
            return None

        final_progress = manager.get_progress_dict()

        # Record timing data for future ETA predictions
        if record_timing and manager.total and manager.total > 0:
            elapsed = time.time() - manager.started_at
            rate = manager.total / elapsed if elapsed > 0 else 0

            op_type = manager.operation_type.value
            if op_type not in self._historical_data:
                self._historical_data[op_type] = {}

            # Update rolling average rate
            old_rate = self._historical_data[op_type].get(f"{op_type}_rate", rate)
            new_rate = old_rate * 0.7 + rate * 0.3  # Exponential moving average
            self._historical_data[op_type][f"{op_type}_rate"] = new_rate
            self._historical_data[op_type]["last_total"] = manager.total
            self._historical_data[op_type]["last_duration"] = elapsed

            self._save_historical_data()

        logger.debug("Completed operation %s", operation_id)
        return final_progress

    def list_operations(self) -> list[dict[str, Any]]:
        """List all active operations with their progress.

        Returns:
            List of progress dicts for all active operations.
        """
        return [manager.get_progress_dict() for manager in self._operations.values()]

    def get_operation_progress(self, operation_id: str) -> dict[str, Any] | None:
        """Get current progress for an operation.

        Args:
            operation_id: Operation identifier.

        Returns:
            Progress dict or None if not found.
        """
        manager = self._operations.get(operation_id)
        if manager:
            return manager.get_progress_dict()
        return None


# Global registry for operation progress
_progress_registry = OperationProgressRegistry()


def get_progress_registry() -> OperationProgressRegistry:
    """Get the global progress registry.

    Returns:
        The global OperationProgressRegistry instance.
    """
    return _progress_registry


# Pydantic model for MCP tool response
class OperationProgressResponse(BaseModel):
    """Response model for get_operation_progress tool."""

    operation_id: str = Field(description="Operation identifier")
    operation_type: str = Field(description="Type of operation")
    phase: str = Field(description="Current phase")
    current: int = Field(description="Current progress value")
    total: int | None = Field(default=None, description="Total items")
    percent_complete: float | None = Field(
        default=None, description="Percentage complete"
    )
    message: str = Field(default="", description="Status message")
    elapsed_seconds: float = Field(description="Time elapsed")
    eta_seconds: float | None = Field(
        default=None, description="Estimated time remaining"
    )
    phase_durations: dict[str, float] = Field(
        default_factory=dict, description="Duration of each completed phase"
    )


class GetOperationProgressArgs(BaseModel):
    """Arguments for the get_operation_progress tool."""

    operation_id: str | None = Field(
        default=None,
        description="Specific operation ID to get progress for. If not provided, returns all active operations.",
    )
