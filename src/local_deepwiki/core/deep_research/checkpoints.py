"""Checkpoint management for deep research sessions.

Provides persistence of research state to allow resumption of interrupted
or cancelled research operations. Checkpoints are stored as JSON files
in the .deepwiki/research_checkpoints directory within each repository.
"""

from __future__ import annotations

import json
import time
import uuid
from itertools import chain
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger
from local_deepwiki.models import (
    ResearchCheckpoint,
    ResearchCheckpointStep,
    SearchResult,
)

from .serialization import dict_to_search_result, search_result_to_dict

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
            "Saved checkpoint %s at step %s",
            checkpoint.research_id,
            checkpoint.current_step,
        )

    def load_checkpoint(self, research_id: str) -> ResearchCheckpoint | None:
        """Load a checkpoint from disk.

        Args:
            research_id: The research session ID.

        Returns:
            The loaded checkpoint, or None if not found.

        Raises:
            ValueError: If the checkpoint has an incompatible schema version.
        """
        checkpoint_path = self._checkpoint_path(research_id)
        if not checkpoint_path.exists():
            return None

        try:
            data = json.loads(checkpoint_path.read_text())
            version = data.get("schema_version", 1)
            if version != 1:
                raise ValueError("incompatible checkpoint version")
            return ResearchCheckpoint.model_validate(data)
        except json.JSONDecodeError as e:
            logger.warning("Failed to load checkpoint %s: %s", research_id, e)
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
                version = data.get("schema_version", 1)
                if version != 1:
                    logger.warning(
                        "Skipping checkpoint %s: incompatible schema version %s",
                        path.name,
                        version,
                    )
                    continue
                checkpoint = ResearchCheckpoint.model_validate(data)
                checkpoints.append(checkpoint)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to load checkpoint %s: %s", path.name, e)
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
            logger.debug("Deleted checkpoint %s", research_id)
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

    def create_checkpoint(self, question: str) -> ResearchCheckpoint:
        """Create a new checkpoint for a research session.

        Args:
            question: The research question.

        Returns:
            A new ResearchCheckpoint object.
        """
        now = time.time()
        return ResearchCheckpoint(
            research_id=str(uuid.uuid4()),
            question=question,
            repo_path=str(self.repo_path),
            started_at=now,
            updated_at=now,
            current_step=ResearchCheckpointStep.DECOMPOSITION,
            completed_steps=[],
        )

    def update_checkpoint(
        self,
        checkpoint: ResearchCheckpoint,
        data: Any,
    ) -> None:
        """Update a checkpoint with new data and persist it.

        ``data`` is expected to be a :class:`CheckpointData` instance (imported
        at the call-site to avoid circular imports).  The function reads its
        attributes duck-type-style so it does not need to import the class.

        Args:
            checkpoint: The checkpoint to update.
            data: A CheckpointData instance with fields to apply.
        """
        checkpoint.current_step = data.step
        checkpoint.updated_at = time.time()

        if data.sub_questions is not None:
            checkpoint.sub_questions = data.sub_questions
        if data.retrieved_contexts is not None:
            checkpoint.retrieved_contexts = data.retrieved_contexts
        if data.follow_up_queries is not None:
            checkpoint.follow_up_queries = data.follow_up_queries
        if data.follow_up_contexts is not None:
            checkpoint.follow_up_contexts = data.follow_up_contexts
        if data.partial_synthesis is not None:
            checkpoint.partial_synthesis = data.partial_synthesis
        if data.error is not None:
            checkpoint.error = data.error
        if (
            data.completed_step
            and data.completed_step not in checkpoint.completed_steps
        ):
            checkpoint.completed_steps.append(data.completed_step)

        self.save_checkpoint(checkpoint)

    def init_or_restore(
        self,
        question: str,
        resume_id: str | None,
    ) -> ResearchCheckpoint | None:
        """Initialize or restore a checkpoint for a research run.

        When *resume_id* is provided the corresponding checkpoint is loaded;
        otherwise a fresh one is created.

        Args:
            question: The research question (used when creating a new checkpoint).
            resume_id: Optional checkpoint ID to resume from.

        Returns:
            The active checkpoint (new or restored).
        """
        if resume_id:
            checkpoint = self.load_checkpoint(resume_id)
            if checkpoint:
                logger.info(
                    "Resuming research %s from step %s",
                    resume_id,
                    checkpoint.current_step,
                )
                return checkpoint
            logger.warning("Checkpoint %s not found, starting fresh", resume_id)

        return self.create_checkpoint(question)


def results_to_checkpoint_format(
    results: list[SearchResult],
    key: str = "default",
) -> dict[str, list[dict[str, Any]]]:
    """Convert search results to checkpoint-serializable format.

    Args:
        results: List of search results.
        key: Key to use in the dictionary.

    Returns:
        Dictionary mapping key to list of serialized results.
    """
    return {key: [search_result_to_dict(r) for r in results]}


def checkpoint_to_results(
    contexts: dict[str, list[dict[str, Any]]] | None,
) -> list[SearchResult]:
    """Convert checkpoint context data back to SearchResults.

    Args:
        contexts: Dictionary of serialized contexts from checkpoint.

    Returns:
        List of reconstructed SearchResult objects.
    """
    if not contexts:
        return []

    results: list[SearchResult] = []
    for data in chain.from_iterable(contexts.values()):
        try:
            results.append(dict_to_search_result(data))
        except (KeyError, ValueError) as e:
            logger.warning("Failed to restore search result: %s", e)
            continue
    return results


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
    logger.info("Cancelled research %s", research_id)

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
