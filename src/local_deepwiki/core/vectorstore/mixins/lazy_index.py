"""LazyIndexMixin — lazy vector index lifecycle management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from local_deepwiki.logging import get_logger
from local_deepwiki.models.foundation import LogCallback

from ..maintenance import LazyIndexManager

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore.store import VectorStore

logger = get_logger(__name__)


class LazyIndexMixin:
    """Mixin providing lazy vector index management methods."""

    # -- Type stubs so IDEs know about attributes set by VectorStore.__init__ --
    if TYPE_CHECKING:
        _lazy_index_manager: LazyIndexManager

    @property
    def lazy_index_manager(self) -> LazyIndexManager:
        """Get the lazy index manager.

        Returns:
            The LazyIndexManager instance for this vector store.
        """
        return self._lazy_index_manager

    @property
    def lazy_index_stats(self) -> dict[str, Any]:
        """Get statistics about lazy index creation.

        Returns:
            Dictionary with lazy index statistics including:
            - enabled: Whether lazy indexing is enabled
            - index_pending: Whether index creation is pending
            - index_created: Whether index has been created
            - creation_in_progress: Whether creation is currently running
            - latency_threshold_ms: Latency threshold for triggering creation
            - min_rows: Minimum rows for index creation
            - average_latency_ms: Average search latency
            - latency_samples: Number of latency samples
            - should_create_index: Whether index should be created now
        """
        return self._lazy_index_manager.get_stats()

    async def schedule_lazy_index_creation(
        self,
        progress_callback: LogCallback | None = None,
    ) -> None:
        """Schedule vector index creation as a background task.

        This is useful for triggering index creation after initial indexing
        completes. If index creation is already in progress or completed,
        this is a no-op.

        Args:
            progress_callback: Optional callback for progress updates.
        """
        await self._lazy_index_manager.schedule_index_creation(progress_callback)

    async def wait_for_vector_index(self, timeout: float | None = None) -> bool:
        """Wait for the vector index to be ready.

        Useful when you need to ensure the index is available before
        performing searches that require it.

        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.

        Returns:
            True if index is ready, False if timeout occurred.
        """
        return await self._lazy_index_manager.wait_for_index(timeout)

    async def create_vector_index_now(
        self,
        progress_callback: LogCallback | None = None,
    ) -> None:
        """Force immediate vector index creation.

        Creates the vector index synchronously. This is useful when you
        need the index to be ready before proceeding with searches.

        Args:
            progress_callback: Optional callback for progress updates.

        Raises:
            RuntimeError: If table doesn't exist or has insufficient rows.
        """
        await self._lazy_index_manager.create_index_now(progress_callback)

    def is_vector_index_ready(self) -> bool:
        """Check if the vector index is ready.

        Returns:
            True if the index has been created and is ready for use.
        """
        return self._lazy_index_manager.is_index_ready()

    def on_vector_index_ready(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when the vector index is ready.

        If the index is already ready, the callback is invoked immediately.

        Args:
            callback: Function to call when index is ready.
        """
        self._lazy_index_manager.on_index_ready(callback)
