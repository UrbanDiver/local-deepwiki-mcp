"""Event system for local-deepwiki lifecycle hooks.

Provides a basic pub-sub event emitter for subscribing to and emitting
events during indexing and wiki generation.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from operator import attrgetter
from typing import Any, Callable, Coroutine

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Event types emitted during operations."""

    # Indexing events
    INDEX_START = "index.start"
    INDEX_FILE = "index.file"
    INDEX_CHUNK = "index.chunk"
    INDEX_COMPLETE = "index.complete"
    INDEX_ERROR = "index.error"

    # Wiki generation events
    WIKI_START = "wiki.start"
    WIKI_PAGE_START = "wiki.page.start"
    WIKI_PAGE_COMPLETE = "wiki.page.complete"
    WIKI_COMPLETE = "wiki.complete"
    WIKI_ERROR = "wiki.error"

    # Research events (deep research)
    RESEARCH_START = "research.start"
    RESEARCH_QUERY = "research.query"
    RESEARCH_COMPLETE = "research.complete"

    # General events
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Event:
    """An event with type and associated data."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def __post_init__(self) -> None:
        """Convert string type to EventType if needed."""
        if isinstance(self.type, str):
            self.type = EventType(self.type)


# Type aliases for handlers
SyncHandler = Callable[[Event], None]
AsyncHandler = Callable[[Event], Coroutine[Any, Any, None]]
Handler = SyncHandler | AsyncHandler


@dataclass
class HandlerEntry:
    """A registered event handler with priority."""

    handler: Handler
    priority: int = 0
    is_async: bool = False
    handler_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        """Detect if handler is async."""
        self.is_async = asyncio.iscoroutinefunction(self.handler)


class EventEmitter:
    """Event emitter for subscribing to and emitting events.

    Supports both synchronous and asynchronous handlers with priority ordering.

    Example:
        emitter = EventEmitter()

        @emitter.on(EventType.INDEX_FILE)
        def on_file_indexed(event: Event):
            print(f"Indexed: {event.data['file_path']}")

        @emitter.on(EventType.WIKI_PAGE_COMPLETE, priority=10)
        async def on_page_complete(event: Event):
            await notify_webhook(event.data)

        await emitter.emit(EventType.INDEX_FILE, {"file_path": "/src/main.py"})
    """

    def __init__(self) -> None:
        """Initialize the event emitter."""
        self._handlers: dict[EventType, list[HandlerEntry]] = {}
        self._global_handlers: list[HandlerEntry] = []

    def on(
        self,
        event_type: EventType | str | None = None,
        priority: int = 0,
    ) -> Callable[[Handler], Handler]:
        """Decorator to register an event handler.

        Args:
            event_type: The event type to listen for, or None for all events.
            priority: Handler priority (higher runs first).

        Returns:
            Decorator function.

        Example:
            @emitter.on(EventType.INDEX_FILE)
            def handler(event):
                print(event.data)
        """

        def decorator(handler: Handler) -> Handler:
            self.add_handler(event_type, handler, priority)
            return handler

        return decorator

    def add_handler(
        self,
        event_type: EventType | str | None,
        handler: Handler,
        priority: int = 0,
    ) -> str:
        """Register an event handler.

        Args:
            event_type: The event type to listen for, or None for all events.
            handler: The handler function (sync or async).
            priority: Handler priority (higher runs first).

        Returns:
            The handler ID for later removal.
        """
        entry = HandlerEntry(handler=handler, priority=priority)

        if event_type is None:
            self._global_handlers.append(entry)
            self._global_handlers.sort(key=attrgetter("priority"), reverse=True)
        else:
            if isinstance(event_type, str):
                event_type = EventType(event_type)

            if event_type not in self._handlers:
                self._handlers[event_type] = []

            self._handlers[event_type].append(entry)
            self._handlers[event_type].sort(key=attrgetter("priority"), reverse=True)

        logger.debug(
            f"Registered handler {entry.handler_id} for {event_type or 'all events'} "
            f"(priority={priority}, async={entry.is_async})"
        )

        return entry.handler_id

    def off(self, event_type: EventType | str | None, handler_id: str) -> bool:
        """Remove a handler by its ID.

        Args:
            event_type: The event type (unused, kept for API compatibility).
            handler_id: The handler's unique ID.

        Returns:
            True if handler was found and removed.
        """
        # Search global handlers
        for i, entry in enumerate(self._global_handlers):
            if entry.handler_id == handler_id:
                self._global_handlers.pop(i)
                return True

        # Search event-specific handlers
        for evt_type, handlers in self._handlers.items():
            for i, entry in enumerate(handlers):
                if entry.handler_id == handler_id:
                    handlers.pop(i)
                    return True

        return False

    def remove_handler(
        self,
        event_type: EventType | str | None,
        handler: Handler,
    ) -> bool:
        """Remove an event handler by reference.

        Args:
            event_type: The event type, or None for global handlers.
            handler: The handler to remove.

        Returns:
            True if handler was found and removed.
        """
        if event_type is None:
            for i, entry in enumerate(self._global_handlers):
                if entry.handler is handler:
                    self._global_handlers.pop(i)
                    return True
            return False

        if isinstance(event_type, str):
            event_type = EventType(event_type)

        if event_type not in self._handlers:
            return False

        for i, entry in enumerate(self._handlers[event_type]):
            if entry.handler is handler:
                self._handlers[event_type].pop(i)
                return True

        return False

    def clear_handlers(self, event_type: EventType | str | None = None) -> None:
        """Clear all handlers for an event type or all handlers.

        Args:
            event_type: The event type to clear, or None to clear all.
        """
        if event_type is None:
            self._handlers.clear()
            self._global_handlers.clear()
        else:
            if isinstance(event_type, str):
                event_type = EventType(event_type)
            self._handlers.pop(event_type, None)

    async def emit(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
    ) -> Event:
        """Emit an event to all registered handlers.

        Args:
            event_type: The event type to emit.
            data: Optional event data.

        Returns:
            The emitted event.
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        event = Event(type=event_type, data=data or {})

        # Collect handlers (global + specific)
        handlers = list(self._global_handlers)
        if event_type in self._handlers:
            handlers.extend(self._handlers[event_type])

        # Sort by priority
        handlers.sort(key=attrgetter("priority"), reverse=True)

        # Execute handlers
        for entry in handlers:
            try:
                if entry.is_async:
                    async_handler: AsyncHandler = entry.handler  # type: ignore[assignment]
                    await async_handler(event)
                else:
                    sync_handler: SyncHandler = entry.handler  # type: ignore[assignment]
                    sync_handler(event)
            except Exception as e:
                # Broad catch justified: event handlers are user-provided callbacks; we must isolate failures
                logger.error(
                    f"Error in event handler {entry.handler_id} for {event_type}: {e}"
                )

        return event

    def handler_count(self, event_type: EventType | str | None = None) -> int:
        """Get the number of handlers for an event type.

        Args:
            event_type: The event type, or None for total count.

        Returns:
            Number of handlers.
        """
        if event_type is None:
            total = len(self._global_handlers)
            for handlers in self._handlers.values():
                total += len(handlers)
            return total

        if isinstance(event_type, str):
            event_type = EventType(event_type)

        return len(self._handlers.get(event_type, []))

    def list_handlers(
        self, event_type: EventType | str | None = None
    ) -> list[HandlerEntry]:
        """List handlers for an event type.

        Args:
            event_type: The event type, or None for global handlers.

        Returns:
            List of handler entries.
        """
        if event_type is None:
            return list(self._global_handlers)

        if isinstance(event_type, str):
            event_type = EventType(event_type)

        return list(self._handlers.get(event_type, []))


# Global event emitter singleton
_emitter: EventEmitter | None = None


def get_event_emitter() -> EventEmitter:
    """Get the global event emitter instance.

    Returns:
        The global EventEmitter singleton.
    """
    global _emitter
    if _emitter is None:
        _emitter = EventEmitter()
    return _emitter


def reset_event_emitter() -> None:
    """Reset the global event emitter.

    Useful for testing.
    """
    global _emitter
    if _emitter is not None:
        _emitter.clear_handlers()
    _emitter = None
