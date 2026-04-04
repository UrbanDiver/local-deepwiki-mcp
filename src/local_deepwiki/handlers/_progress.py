"""Progress notification helpers for MCP operations."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from mcp.server import Server

from local_deepwiki.logging import get_logger
from local_deepwiki.progress import (
    OperationType,
    ProgressBuffer,
    ProgressManager,
    ProgressPhase,
    ProgressUpdate,
    get_progress_registry,
)

if TYPE_CHECKING:
    from local_deepwiki.models import IndexingProgressType

logger = get_logger(__name__)


class ProgressNotifier:
    """Helper class for sending buffered MCP progress notifications.

    Integrates ProgressManager with MCP server notifications,
    handling buffering and async notification delivery.
    """

    def __init__(
        self,
        progress_manager: ProgressManager,
        server: Server | None,
        progress_token: str | int | None,
        buffer_interval: float = 0.5,
    ):
        """Initialize the notifier.

        Args:
            progress_manager: The ProgressManager to use for tracking.
            server: MCP server instance.
            progress_token: Progress token from MCP request.
            buffer_interval: Minimum seconds between notifications.
        """
        self.progress_manager = progress_manager
        self.server = server
        self.progress_token = progress_token
        self.buffer = ProgressBuffer(flush_interval=buffer_interval)
        self._messages: list[str] = []

    async def update(
        self,
        current: int | None = None,
        total: int | None = None,
        message: str = "",
        phase: ProgressPhase | None = None,
        step_type: "IndexingProgressType | None" = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update progress and send buffered notification.

        Args:
            current: Current progress value.
            total: Total items.
            message: Status message.
            phase: Current phase.
            step_type: IndexingProgressType for backward compatibility.
            metadata: Additional metadata.
        """
        # Track message history
        if message:
            self._messages.append(message)

        # Update progress manager
        update = self.progress_manager.update(
            current=current,
            total=total,
            message=message,
            phase=phase,
            metadata=metadata,
        )

        # Add to buffer
        updates_to_send = self.buffer.add(update)

        # Send notifications if buffer flushed
        if updates_to_send:
            await self._send_notifications(updates_to_send)

    async def flush(self) -> None:
        """Flush any pending notifications."""
        updates = self.buffer.flush()
        if updates:
            await self._send_notifications(updates)

    async def _send_notifications(self, updates: list[ProgressUpdate]) -> None:
        """Send MCP progress notifications.

        Args:
            updates: List of progress updates to send.
        """
        if not self.progress_token or not self.server:
            return

        # Send the most recent update (MCP expects single progress per notification)
        latest = updates[-1]

        try:
            request_ctx = self.server.request_context

            # Build backward-compatible progress message
            progress_data = {
                "step": latest.current,
                "total_steps": latest.total or 0,
                "step_type": latest.phase.value,
                "message": latest.message,
                "eta_seconds": latest.eta_seconds,
                **latest.metadata,
            }

            await request_ctx.session.send_progress_notification(
                progress_token=self.progress_token,
                progress=float(latest.current),
                total=float(latest.total) if latest.total else None,
                message=json.dumps(progress_data),
            )
        except (RuntimeError, OSError, AttributeError, LookupError) as e:
            logger.warning("Failed to send progress notification: %s", e)

    def sync_notify(
        self,
        current: int | None = None,
        total: int | None = None,
        message: str = "",
        phase: ProgressPhase | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Fire-and-forget progress update from synchronous code.

        Schedules the async ``update`` on the running event loop without
        blocking the caller.  Safe to call from sync callbacks invoked
        inside an async context (e.g. wiki-generation progress hooks).
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No event loop — nothing to schedule on
        loop.create_task(
            self.update(
                current=current,
                total=total,
                message=message,
                phase=phase,
                metadata=metadata,
            )
        )

    @property
    def messages(self) -> list[str]:
        """Get accumulated progress messages."""
        return self._messages


def create_progress_notifier(
    operation_type: OperationType,
    server: Server | None,
    total: int | None = None,
) -> tuple[ProgressNotifier | None, str]:
    """Create a ProgressNotifier for an MCP operation.

    Args:
        operation_type: Type of operation.
        server: MCP server instance.
        total: Total items to process.

    Returns:
        Tuple of (ProgressNotifier or None, operation_id).
    """
    operation_id = str(uuid.uuid4())
    registry = get_progress_registry()

    # Extract progress token from MCP request context
    progress_token: str | int | None = None
    if server is not None:
        try:
            request_ctx = server.request_context
            if request_ctx.meta and request_ctx.meta.progressToken:
                progress_token = request_ctx.meta.progressToken
        except LookupError:
            logger.debug(
                "No MCP request context available for progress token extraction"
            )

    # Create progress manager
    progress_manager = registry.start_operation(
        operation_id=operation_id,
        operation_type=operation_type,
        total=total,
    )

    # Create notifier
    notifier = ProgressNotifier(
        progress_manager=progress_manager,
        server=server,
        progress_token=progress_token,
    )

    return notifier, operation_id
