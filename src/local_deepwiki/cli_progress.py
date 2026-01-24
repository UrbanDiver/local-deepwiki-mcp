"""Rich CLI progress bars for long-running operations.

This module provides consistent, beautiful progress bars for CLI operations
using the rich library. Progress bars are automatically disabled in non-interactive
terminals or when --no-progress is specified.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def is_interactive() -> bool:
    """Check if the terminal is interactive.

    Returns:
        True if running in an interactive terminal, False otherwise.
    """
    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False

    # Check common environment variables that indicate non-interactive mode
    if os.environ.get("CI"):
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False

    return True


def create_progress(
    *,
    disable: bool = False,
    console: Console | None = None,
) -> Progress:
    """Create a configured rich Progress instance.

    Args:
        disable: If True, disable progress display entirely.
        console: Optional console instance to use.

    Returns:
        Configured Progress instance.
    """
    # Auto-disable if not interactive
    if not is_interactive():
        disable = True

    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console or Console(),
        disable=disable,
        transient=False,
    )


def create_indeterminate_progress(
    *,
    disable: bool = False,
    console: Console | None = None,
) -> Progress:
    """Create a progress bar for operations without known total.

    Args:
        disable: If True, disable progress display entirely.
        console: Optional console instance to use.

    Returns:
        Configured Progress instance for indeterminate operations.
    """
    if not is_interactive():
        disable = True

    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        TimeElapsedColumn(),
        console=console or Console(),
        disable=disable,
        transient=False,
    )


@contextmanager
def file_progress(
    files: Iterable[Path],
    description: str = "Processing",
    *,
    disable: bool = False,
    console: Console | None = None,
) -> Iterator[tuple[Progress, TaskID, list[Path]]]:
    """Context manager for tracking progress over a list of files.

    Args:
        files: Iterable of file paths to process.
        description: Description to show in progress bar.
        disable: If True, disable progress display.
        console: Optional console instance.

    Yields:
        Tuple of (progress instance, task ID, list of files).

    Example:
        >>> with file_progress(md_files, "Exporting") as (progress, task, files):
        ...     for f in files:
        ...         process_file(f)
        ...         progress.update(task, advance=1)
    """
    file_list = list(files)
    total = len(file_list)

    with create_progress(disable=disable, console=console) as progress:
        task = progress.add_task(description, total=total)
        yield progress, task, file_list


class ProgressCallback:
    """Adapter to use rich progress bars with ProgressCallback protocol.

    This class bridges the existing ProgressCallback protocol used throughout
    the codebase with rich progress bars for CLI display.
    """

    def __init__(
        self,
        progress: Progress,
        task_id: TaskID,
        *,
        show_message: bool = True,
    ):
        """Initialize the callback adapter.

        Args:
            progress: Rich Progress instance.
            task_id: Task ID for the progress bar.
            show_message: Whether to update description with messages.
        """
        self.progress = progress
        self.task_id = task_id
        self.show_message = show_message
        self._last_current = 0

    def __call__(self, msg: str, current: int, total: int) -> None:
        """Handle progress callback.

        Args:
            msg: Description of current operation.
            current: Current step number.
            total: Total number of steps.
        """
        # Update total if it changed
        if total > 0:
            self.progress.update(self.task_id, total=total)

        # Calculate advance from last position
        advance = current - self._last_current
        if advance > 0:
            self.progress.update(self.task_id, advance=advance)
        elif current < self._last_current:
            # Reset happened (new phase), reset to current position
            self.progress.update(self.task_id, completed=current)

        self._last_current = current

        # Update description if requested
        if self.show_message and msg:
            # Truncate long messages
            display_msg = msg[:50] + "..." if len(msg) > 50 else msg
            self.progress.update(self.task_id, description=display_msg)


class MultiPhaseProgress:
    """Progress tracker for multi-phase operations.

    Provides a clean interface for tracking progress across multiple phases
    of a long-running operation (e.g., indexing -> parsing -> generating).
    """

    def __init__(
        self,
        *,
        disable: bool = False,
        console: Console | None = None,
    ):
        """Initialize multi-phase progress tracker.

        Args:
            disable: If True, disable progress display.
            console: Optional console instance.
        """
        self._disable = disable or not is_interactive()
        self._console = console or Console()
        self._progress: Progress | None = None
        self._tasks: dict[str, TaskID] = {}
        self._active = False

    def __enter__(self) -> MultiPhaseProgress:
        """Start progress tracking."""
        self._progress = create_progress(
            disable=self._disable,
            console=self._console,
        )
        self._progress.__enter__()
        self._active = True
        return self

    def __exit__(self, *args: object) -> None:
        """Stop progress tracking."""
        if self._progress:
            self._progress.__exit__(*args)
        self._active = False

    def add_phase(
        self,
        name: str,
        description: str,
        total: int | None = None,
    ) -> TaskID:
        """Add a new phase to track.

        Args:
            name: Unique name for this phase.
            description: Description to display.
            total: Total items in this phase (None for indeterminate).

        Returns:
            Task ID for the phase.
        """
        if not self._progress or not self._active:
            raise RuntimeError("Progress tracker not started. Use 'with' statement.")

        task_id = self._progress.add_task(
            description,
            total=total if total is not None else 0,
            start=total is not None,
        )
        self._tasks[name] = task_id
        return task_id

    def update(
        self,
        name: str,
        *,
        advance: int = 0,
        completed: int | None = None,
        description: str | None = None,
        total: int | None = None,
    ) -> None:
        """Update a phase's progress.

        Args:
            name: Name of the phase to update.
            advance: Amount to advance progress.
            completed: Set absolute completion count.
            description: Update description text.
            total: Update total count.
        """
        if not self._progress or not self._active:
            return

        task_id = self._tasks.get(name)
        if task_id is None:
            return

        kwargs: dict[str, object] = {}
        if advance:
            kwargs["advance"] = advance
        if completed is not None:
            kwargs["completed"] = completed
        if description is not None:
            kwargs["description"] = description
        if total is not None:
            kwargs["total"] = total

        if kwargs:
            self._progress.update(task_id, **kwargs)

    def complete_phase(self, name: str) -> None:
        """Mark a phase as complete.

        Args:
            name: Name of the phase to complete.
        """
        if not self._progress or not self._active:
            return

        task_id = self._tasks.get(name)
        if task_id is None:
            return

        # Get current total and mark as fully complete
        task = self._progress._tasks.get(task_id)
        if task:
            self._progress.update(task_id, completed=task.total or 0)

    def get_callback(self, name: str) -> ProgressCallback | None:
        """Get a ProgressCallback adapter for a phase.

        Args:
            name: Name of the phase.

        Returns:
            ProgressCallback adapter or None if phase doesn't exist.
        """
        if not self._progress or not self._active:
            return None

        task_id = self._tasks.get(name)
        if task_id is None:
            return None

        return ProgressCallback(self._progress, task_id)
