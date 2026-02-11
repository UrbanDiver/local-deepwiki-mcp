"""Checkpoint management for deep research sessions.

Provides persistence of research state to allow resumption of interrupted
or cancelled research operations. Checkpoints are stored as JSON files
in the .deepwiki/research_checkpoints directory within each repository.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from local_deepwiki.logging import get_logger
from local_deepwiki.models import ResearchCheckpoint, ResearchCheckpointStep

logger = get_logger(__name__)


class CheckpointManager:
    """Manages saving and loading research checkpoints.

    Checkpoints are stored as JSON files in the .deepwiki/research_checkpoints
    directory within each repository.
    """

    def __init__(self, repo_path: Path):
        """Initialize the checkpoint manager.

        Args:
            repo_path: Path to the repository.
        """
        self.repo_path = repo_path
        self.checkpoint_dir = repo_path / ".deepwiki" / "research_checkpoints"

    def _ensure_dir(self) -> None:
        """Ensure the checkpoint directory exists."""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, research_id: str) -> Path:
        """Get the path to a checkpoint file.

        Args:
            research_id: The research session ID.

        Returns:
            Path to the checkpoint JSON file.
        """
        return self.checkpoint_dir / f"{research_id}.json"

    def save_checkpoint(self, checkpoint: ResearchCheckpoint) -> None:
        """Save a checkpoint to disk.

        Args:
            checkpoint: The checkpoint to save.
        """
        self._ensure_dir()
        checkpoint_path = self._checkpoint_path(checkpoint.research_id)
        checkpoint_path.write_text(checkpoint.model_dump_json(indent=2))
        logger.debug(
            f"Saved checkpoint {checkpoint.research_id} at step {checkpoint.current_step}"
        )

    def load_checkpoint(self, research_id: str) -> ResearchCheckpoint | None:
        """Load a checkpoint from disk.

        Args:
            research_id: The research session ID.

        Returns:
            The loaded checkpoint, or None if not found.
        """
        checkpoint_path = self._checkpoint_path(research_id)
        if not checkpoint_path.exists():
            return None

        try:
            data = json.loads(checkpoint_path.read_text())
            return ResearchCheckpoint.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to load checkpoint {research_id}: {e}")
            return None

    def list_checkpoints(self) -> list[ResearchCheckpoint]:
        """List all checkpoints for this repository.

        Returns:
            List of checkpoints, sorted by updated_at descending.
        """
        if not self.checkpoint_dir.exists():
            return []

        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                checkpoint = ResearchCheckpoint.model_validate(data)
                checkpoints.append(checkpoint)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to load checkpoint {path.name}: {e}")
                continue

        # Sort by updated_at descending (most recent first)
        return sorted(checkpoints, key=lambda c: c.updated_at, reverse=True)

    def delete_checkpoint(self, research_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            research_id: The research session ID.

        Returns:
            True if deleted, False if not found.
        """
        checkpoint_path = self._checkpoint_path(research_id)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.debug(f"Deleted checkpoint {research_id}")
            return True
        return False

    def get_incomplete_checkpoints(self) -> list[ResearchCheckpoint]:
        """Get all incomplete (non-complete, non-error) checkpoints.

        Returns:
            List of incomplete checkpoints.
        """
        return [
            c
            for c in self.list_checkpoints()
            if c.current_step
            not in (
                ResearchCheckpointStep.COMPLETE,
                ResearchCheckpointStep.ERROR,
            )
        ]


def cancel_research(repo_path: Path, research_id: str) -> ResearchCheckpoint | None:
    """Cancel a research operation and save its checkpoint.

    This is a synchronous utility function that can be called to mark
    a research session as cancelled. The checkpoint will be preserved
    for potential resumption later.

    Args:
        repo_path: Path to the repository.
        research_id: The research session ID to cancel.

    Returns:
        The cancelled checkpoint, or None if not found.
    """
    manager = CheckpointManager(repo_path)
    checkpoint = manager.load_checkpoint(research_id)

    if not checkpoint:
        return None

    # Mark as cancelled
    checkpoint.current_step = ResearchCheckpointStep.CANCELLED
    checkpoint.updated_at = time.time()
    checkpoint.error = "Research was cancelled by user"

    manager.save_checkpoint(checkpoint)
    logger.info(f"Cancelled research {research_id}")

    return checkpoint


def list_research_checkpoints(repo_path: Path) -> list[ResearchCheckpoint]:
    """List all research checkpoints for a repository.

    Args:
        repo_path: Path to the repository.

    Returns:
        List of checkpoints, sorted by updated_at descending.
    """
    manager = CheckpointManager(repo_path)
    return manager.list_checkpoints()


def get_research_checkpoint(
    repo_path: Path, research_id: str
) -> ResearchCheckpoint | None:
    """Get a specific research checkpoint.

    Args:
        repo_path: Path to the repository.
        research_id: The research session ID.

    Returns:
        The checkpoint, or None if not found.
    """
    manager = CheckpointManager(repo_path)
    return manager.load_checkpoint(research_id)


def delete_research_checkpoint(repo_path: Path, research_id: str) -> bool:
    """Delete a research checkpoint.

    Args:
        repo_path: Path to the repository.
        research_id: The research session ID.

    Returns:
        True if deleted, False if not found.
    """
    manager = CheckpointManager(repo_path)
    return manager.delete_checkpoint(research_id)
