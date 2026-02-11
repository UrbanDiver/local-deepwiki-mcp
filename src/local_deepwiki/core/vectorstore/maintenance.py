"""Index maintenance and lazy creation."""

from __future__ import annotations

import asyncio
import math
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from local_deepwiki.config import LazyIndexConfig
from local_deepwiki.logging import get_logger

from .schema import LatencyStats

if TYPE_CHECKING:
    from .store import VectorStore

logger = get_logger(__name__)


class LazyIndexManager:
    """Manages deferred/lazy vector index creation for VectorStore.

    This class implements lazy index creation to improve initial indexing performance.
    Instead of creating vector indexes immediately when the table reaches the threshold,
    index creation is deferred to a background task or triggered on-demand when search
    latency exceeds a configured threshold.

    Attributes:
        config: Configuration for lazy index behavior.
    """

    def __init__(
        self,
        vectorstore: "VectorStore",
        config: LazyIndexConfig | None = None,
    ):
        """Initialize the lazy index manager.

        Args:
            vectorstore: The VectorStore instance to manage indexes for.
            config: Optional configuration. If None, uses default LazyIndexConfig.
        """
        self._vectorstore = vectorstore
        self.config = config if config is not None else LazyIndexConfig()
        self._index_pending = False
        self._index_task: asyncio.Task | None = None
        self._index_ready = asyncio.Event()
        self._latency_stats = LatencyStats(window_size=self.config.latency_window_size)
        self._lock = threading.RLock()
        self._creation_in_progress = False
        self._index_created = False
        # Callbacks for index ready event
        self._on_index_ready_callbacks: list[Callable[[], None]] = []

    def mark_index_pending(self) -> None:
        """Mark that vector index creation is pending.

        Called when the table reaches the minimum row threshold during initial
        indexing, to indicate that an index should be created in the background.
        """
        with self._lock:
            if not self._index_created:
                self._index_pending = True
                logger.debug("Vector index creation marked as pending")

    def mark_index_created(self) -> None:
        """Mark that vector index has been created.

        Called after successful index creation to update internal state.
        """
        with self._lock:
            self._index_pending = False
            self._index_created = True
            self._creation_in_progress = False
            self._index_ready.set()
            logger.debug("Vector index marked as created")

            # Invoke callbacks
            for callback in self._on_index_ready_callbacks:
                try:
                    callback()
                except (RuntimeError, ValueError, TypeError) as e:
                    # RuntimeError: Callback runtime errors
                    # ValueError: Invalid state during callback
                    # TypeError: Callback signature mismatch
                    logger.warning("Index ready callback failed: %s", e)

    def is_index_pending(self) -> bool:
        """Check if vector index creation is pending.

        Returns:
            True if index creation is pending but not yet started/completed.
        """
        with self._lock:
            return self._index_pending and not self._index_created

    def is_index_ready(self) -> bool:
        """Check if the vector index is ready.

        Returns:
            True if the index has been created and is ready for use.
        """
        with self._lock:
            return self._index_created

    def is_creation_in_progress(self) -> bool:
        """Check if index creation is currently in progress.

        Returns:
            True if background index creation is running.
        """
        with self._lock:
            return self._creation_in_progress

    def record_search_latency(self, latency_ms: float) -> None:
        """Record a search query latency measurement.

        Args:
            latency_ms: Search latency in milliseconds.
        """
        self._latency_stats.record(latency_ms)

    def should_create_index(self) -> bool:
        """Check if index should be created based on latency statistics.

        Returns True if:
        - Lazy indexing is enabled
        - Index hasn't been created yet
        - Index creation isn't already in progress
        - Either index is marked pending, or average latency exceeds threshold

        Returns:
            True if index creation should be triggered.
        """
        if not self.config.enabled:
            return False

        with self._lock:
            if self._index_created or self._creation_in_progress:
                return False

            # Check if explicitly pending
            if self._index_pending:
                return True

            # Check latency threshold
            avg_latency = self._latency_stats.get_average()
            if avg_latency is not None:
                # Need enough samples to make a decision
                if self._latency_stats.get_count() >= 3:
                    return avg_latency > self.config.latency_threshold_ms

            return False

    async def schedule_index_creation(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Schedule index creation as a background task.

        If index creation is already in progress or completed, this is a no-op.

        Args:
            progress_callback: Optional callback for progress updates.
                Called with status messages during index creation.
        """
        with self._lock:
            if self._index_created or self._creation_in_progress:
                logger.debug("Index already created or in progress, skipping schedule")
                return
            if self._index_task is not None and not self._index_task.done():
                logger.debug("Index creation task already scheduled")
                return

            self._creation_in_progress = True

        logger.info("Scheduling background vector index creation")

        async def _create_index_task():
            try:
                await self.create_index_now(progress_callback=progress_callback)
            except (RuntimeError, ValueError, OSError) as e:
                # RuntimeError: LanceDB table/index errors
                # ValueError: Invalid index parameters
                # OSError: File system or resource errors
                logger.error("Background index creation failed: %s", e)
                with self._lock:
                    self._creation_in_progress = False
                raise

        self._index_task = asyncio.create_task(_create_index_task())

    async def wait_for_index(self, timeout: float | None = None) -> bool:
        """Wait for the index to be ready.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if index is ready, False if timeout occurred.
        """
        if self.is_index_ready():
            return True

        try:
            await asyncio.wait_for(self._index_ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def create_index_now(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Force immediate index creation.

        Creates the vector index synchronously (within an async context).
        This is useful when you need the index to be ready before proceeding.

        Args:
            progress_callback: Optional callback for progress updates.

        Raises:
            RuntimeError: If table doesn't exist or has insufficient rows.
        """
        table = self._vectorstore._get_table()
        if table is None:
            raise RuntimeError("Cannot create index: table does not exist")

        with self._lock:
            if self._index_created:
                logger.debug("Index already created, skipping")
                return
            self._creation_in_progress = True

        try:
            num_rows = table.count_rows()
            if num_rows < self.config.min_rows:
                logger.debug(
                    f"Skipping index creation: {num_rows} rows < {self.config.min_rows} threshold"
                )
                return

            if progress_callback:
                progress_callback(f"Creating vector index for {num_rows} rows...")

            logger.info("Creating vector index for %s rows", num_rows)

            # Calculate optimal number of partitions
            num_partitions = min(max(int(math.sqrt(num_rows)), 16), 256)

            # Run the actual index creation
            # This is CPU-bound, so we run it in an executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: table.create_index(
                    metric="L2",
                    num_partitions=num_partitions,
                    num_sub_vectors=16,
                ),
            )

            if progress_callback:
                progress_callback("Vector index created successfully")

            logger.info(
                f"Created vector index with {num_partitions} partitions for {num_rows} vectors"
            )

            self.mark_index_created()

        except (ValueError, RuntimeError, OSError) as e:
            logger.warning("Could not create vector index: %s", e)
            with self._lock:
                self._creation_in_progress = False
            raise

    def on_index_ready(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when the index is ready.

        If the index is already ready, the callback is invoked immediately.

        Args:
            callback: Function to call when index is ready.
        """
        with self._lock:
            if self._index_created:
                # Already ready, invoke immediately
                try:
                    callback()
                except (RuntimeError, ValueError, TypeError) as e:
                    # RuntimeError: Callback runtime errors
                    # ValueError: Invalid state during callback
                    # TypeError: Callback signature mismatch
                    logger.warning("Index ready callback failed: %s", e)
            else:
                self._on_index_ready_callbacks.append(callback)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the lazy index manager.

        Returns:
            Dictionary with manager statistics.
        """
        with self._lock:
            avg_latency = self._latency_stats.get_average()
            return {
                "enabled": self.config.enabled,
                "index_pending": self._index_pending,
                "index_created": self._index_created,
                "creation_in_progress": self._creation_in_progress,
                "latency_threshold_ms": self.config.latency_threshold_ms,
                "min_rows": self.config.min_rows,
                "average_latency_ms": avg_latency,
                "latency_samples": self._latency_stats.get_count(),
                "should_create_index": self.should_create_index(),
            }

    def reset(self) -> None:
        """Reset the manager state.

        Clears all state including pending flag, created flag, and latency stats.
        Useful for testing or when re-indexing from scratch.
        """
        with self._lock:
            self._index_pending = False
            self._index_created = False
            self._creation_in_progress = False
            self._index_ready.clear()
            self._latency_stats.clear()
            self._on_index_ready_callbacks.clear()
            if self._index_task is not None and not self._index_task.done():
                self._index_task.cancel()
            self._index_task = None
