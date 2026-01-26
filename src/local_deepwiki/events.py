"""Event system for local-deepwiki lifecycle hooks.

Provides an event emitter pattern for subscribing to and emitting
events during indexing and wiki generation.
"""

import asyncio
import time
import uuid
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Iterator

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
class HandlerStats:
    """Statistics for a registered handler."""

    handler_id: str
    success_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    last_error: str | None = None
    last_error_time: float | None = None
    registered_at: float = field(default_factory=time.time)


@dataclass
class HandlerLifecycle:
    """Lifecycle hooks for handler events."""

    on_register: Callable[[str, str], None] | None = None  # event_type, handler_id
    on_success: Callable[[str, str], None] | None = None  # event_type, handler_id
    on_error: Callable[[str, str, Exception], None] | None = None  # event_type, handler_id, exception
    on_deregister: Callable[[str, str, str], None] | None = None  # event_type, handler_id, reason


@dataclass
class HandlerEntry:
    """A registered event handler with priority."""

    handler: Handler
    priority: int = 0
    is_async: bool = False
    handler_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_weak: bool = False
    _weak_ref: weakref.ref | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Detect if handler is async."""
        self.is_async = asyncio.iscoroutinefunction(self.handler)

    def get_handler(self) -> Handler | None:
        """Get the handler, resolving weak reference if needed.

        Returns:
            The handler if still alive, or None if weak ref was collected.
        """
        if self.is_weak and self._weak_ref is not None:
            obj = self._weak_ref()
            if obj is None:
                return None
            # For bound methods, we stored the object; return the original handler
            return self.handler
        return self.handler

    def is_alive(self) -> bool:
        """Check if the handler is still valid (for weak refs).

        Returns:
            True if handler is alive or not a weak ref.
        """
        if self.is_weak and self._weak_ref is not None:
            return self._weak_ref() is not None
        return True


class EventEmitter:
    """Event emitter for subscribing to and emitting events.

    Supports both synchronous and asynchronous handlers with priority ordering.
    Includes automatic handler cleanup after consecutive errors and weak reference support.

    Example:
        emitter = EventEmitter()

        @emitter.on(EventType.INDEX_FILE)
        def on_file_indexed(event: Event):
            print(f"Indexed: {event.data['file_path']}")

        # Or with decorator
        @emitter.on(EventType.WIKI_PAGE_COMPLETE, priority=10)
        async def on_page_complete(event: Event):
            await notify_webhook(event.data)

        # Emit events
        await emitter.emit(EventType.INDEX_FILE, {"file_path": "/src/main.py"})

        # Use scoped handlers for automatic cleanup
        with emitter.scoped_handler(EventType.INDEX_FILE, my_handler):
            await emitter.emit(EventType.INDEX_FILE, {"file": "test.py"})
        # Handler automatically removed after context
    """

    def __init__(
        self,
        max_consecutive_errors: int = 3,
        lifecycle: HandlerLifecycle | None = None,
    ) -> None:
        """Initialize the event emitter.

        Args:
            max_consecutive_errors: Number of consecutive errors before auto-deregistration.
            lifecycle: Optional lifecycle hooks for handler events.
        """
        self._handlers: dict[EventType, list[HandlerEntry]] = {}
        self._global_handlers: list[HandlerEntry] = []
        self._max_consecutive_errors = max_consecutive_errors
        self._handler_stats: dict[str, HandlerStats] = {}
        self._handler_event_map: dict[str, EventType | None] = {}  # handler_id -> event_type
        self._lifecycle = lifecycle or HandlerLifecycle()

    def on(
        self,
        event_type: EventType | str | None = None,
        priority: int = 0,
        weak: bool = False,
    ) -> Callable[[Handler], Handler]:
        """Decorator to register an event handler.

        Args:
            event_type: The event type to listen for, or None for all events.
            priority: Handler priority (higher runs first).
            weak: If True, use weak reference for bound methods.

        Returns:
            Decorator function.

        Example:
            @emitter.on(EventType.INDEX_FILE)
            def handler(event):
                print(event.data)

            # With weak reference (for bound methods)
            @emitter.on(EventType.INDEX_FILE, weak=True)
            def handler(event):
                print(event.data)
        """

        def decorator(handler: Handler) -> Handler:
            self.add_handler(event_type, handler, priority, weak=weak)
            return handler

        return decorator

    def add_handler(
        self,
        event_type: EventType | str | None,
        handler: Handler,
        priority: int = 0,
        weak: bool = False,
    ) -> str:
        """Register an event handler.

        Args:
            event_type: The event type to listen for, or None for all events.
            handler: The handler function (sync or async).
            priority: Handler priority (higher runs first).
            weak: If True, use weak reference for bound methods.

        Returns:
            The handler ID for later removal.
        """
        entry = HandlerEntry(handler=handler, priority=priority, is_weak=weak)

        # Set up weak reference if requested
        if weak:
            # For bound methods, create weak ref to the object
            if hasattr(handler, "__self__"):
                entry._weak_ref = weakref.ref(handler.__self__)
            else:
                # For regular functions, we can't use weak refs effectively
                # but we'll still mark it for consistency
                logger.warning(
                    f"Weak reference requested for non-bound method; "
                    f"weak behavior may not work as expected"
                )

        # Initialize stats for this handler
        self._handler_stats[entry.handler_id] = HandlerStats(handler_id=entry.handler_id)

        if event_type is None:
            self._global_handlers.append(entry)
            self._global_handlers.sort(key=lambda e: e.priority, reverse=True)
            self._handler_event_map[entry.handler_id] = None
        else:
            if isinstance(event_type, str):
                event_type = EventType(event_type)

            if event_type not in self._handlers:
                self._handlers[event_type] = []

            self._handlers[event_type].append(entry)
            self._handlers[event_type].sort(key=lambda e: e.priority, reverse=True)
            self._handler_event_map[entry.handler_id] = event_type

        logger.debug(
            f"Registered handler {entry.handler_id} for {event_type or 'all events'} "
            f"(priority={priority}, async={entry.is_async}, weak={weak})"
        )

        # Call lifecycle hook
        if self._lifecycle.on_register:
            try:
                event_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
                self._lifecycle.on_register(event_str, entry.handler_id)
            except Exception as e:
                logger.error(f"Error in on_register lifecycle hook: {e}")

        return entry.handler_id

    def _track_handler_result(
        self,
        handler_id: str,
        event_type: EventType,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Track handler execution result.

        Args:
            handler_id: The handler's unique ID.
            event_type: The event type that was being handled.
            success: Whether the handler executed successfully.
            error: Error message if failed.
        """
        if handler_id not in self._handler_stats:
            return

        stats = self._handler_stats[handler_id]
        if success:
            stats.success_count += 1
            stats.consecutive_errors = 0
            if self._lifecycle.on_success:
                try:
                    self._lifecycle.on_success(event_type.value, handler_id)
                except Exception as e:
                    logger.error(f"Error in on_success lifecycle hook: {e}")
        else:
            stats.error_count += 1
            stats.consecutive_errors += 1
            stats.last_error = error
            stats.last_error_time = time.time()

    def _should_deregister(self, handler_id: str) -> bool:
        """Check if handler should be auto-deregistered.

        Args:
            handler_id: The handler's unique ID.

        Returns:
            True if handler has exceeded max consecutive errors.
        """
        if handler_id not in self._handler_stats:
            return False

        stats = self._handler_stats[handler_id]
        return stats.consecutive_errors >= self._max_consecutive_errors

    def _deregister_handler_by_id(
        self,
        handler_id: str,
        reason: str = "manual",
    ) -> bool:
        """Remove a handler by its ID.

        Args:
            handler_id: The handler's unique ID.
            reason: The reason for deregistration.

        Returns:
            True if handler was found and removed.
        """
        event_type = self._handler_event_map.get(handler_id)

        # Search in appropriate list
        if event_type is None:
            # Global handler
            for i, entry in enumerate(self._global_handlers):
                if entry.handler_id == handler_id:
                    self._global_handlers.pop(i)
                    self._cleanup_handler_stats(handler_id, "global", reason)
                    return True
        else:
            # Specific event handler
            if event_type in self._handlers:
                for i, entry in enumerate(self._handlers[event_type]):
                    if entry.handler_id == handler_id:
                        self._handlers[event_type].pop(i)
                        self._cleanup_handler_stats(handler_id, event_type.value, reason)
                        return True

        return False

    def _cleanup_handler_stats(
        self,
        handler_id: str,
        event_type_str: str,
        reason: str,
    ) -> None:
        """Clean up handler stats and call lifecycle hook.

        Args:
            handler_id: The handler's unique ID.
            event_type_str: String representation of the event type.
            reason: The reason for deregistration.
        """
        self._handler_stats.pop(handler_id, None)
        self._handler_event_map.pop(handler_id, None)

        if self._lifecycle.on_deregister:
            try:
                self._lifecycle.on_deregister(event_type_str, handler_id, reason)
            except Exception as e:
                logger.error(f"Error in on_deregister lifecycle hook: {e}")

    def off(self, event_type: EventType | str | None, handler_id: str) -> bool:
        """Remove a handler by its ID.

        Args:
            event_type: The event type (for validation), or None for global.
            handler_id: The handler's unique ID.

        Returns:
            True if handler was found and removed.
        """
        return self._deregister_handler_by_id(handler_id, reason="manual")

    def remove_handler(
        self,
        event_type: EventType | str | None,
        handler: Handler,
    ) -> bool:
        """Remove an event handler.

        Args:
            event_type: The event type, or None for global handlers.
            handler: The handler to remove.

        Returns:
            True if handler was found and removed.
        """
        if event_type is None:
            for i, entry in enumerate(self._global_handlers):
                if entry.handler is handler:
                    handler_id = entry.handler_id
                    self._global_handlers.pop(i)
                    self._cleanup_handler_stats(handler_id, "global", "manual")
                    return True
            return False

        if isinstance(event_type, str):
            event_type = EventType(event_type)

        if event_type not in self._handlers:
            return False

        for i, entry in enumerate(self._handlers[event_type]):
            if entry.handler is handler:
                handler_id = entry.handler_id
                self._handlers[event_type].pop(i)
                self._cleanup_handler_stats(handler_id, event_type.value, "manual")
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
            self._handler_stats.clear()
            self._handler_event_map.clear()
        else:
            if isinstance(event_type, str):
                event_type = EventType(event_type)
            # Clean up stats for handlers being removed
            if event_type in self._handlers:
                for entry in self._handlers[event_type]:
                    self._handler_stats.pop(entry.handler_id, None)
                    self._handler_event_map.pop(entry.handler_id, None)
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

        # Clean up dead weak references first
        self._cleanup_dead_handlers()

        # Collect handlers (global + specific)
        handlers = list(self._global_handlers)
        if event_type in self._handlers:
            handlers.extend(self._handlers[event_type])

        # Sort by priority
        handlers.sort(key=lambda e: e.priority, reverse=True)

        # Track handlers to deregister after iteration
        handlers_to_deregister: list[str] = []

        # Execute handlers
        for entry in handlers:
            # Skip dead weak references
            if not entry.is_alive():
                handlers_to_deregister.append(entry.handler_id)
                continue

            handler = entry.get_handler()
            if handler is None:
                handlers_to_deregister.append(entry.handler_id)
                continue

            try:
                if entry.is_async:
                    # Cast to async handler for type checker
                    async_handler: AsyncHandler = handler  # type: ignore[assignment]
                    await async_handler(event)
                else:
                    sync_handler: SyncHandler = handler  # type: ignore[assignment]
                    sync_handler(event)

                # Track success
                self._track_handler_result(entry.handler_id, event_type, success=True)

            except Exception as e:
                logger.error(f"Error in event handler {entry.handler_id} for {event_type}: {e}")
                # Track error
                self._track_handler_result(
                    entry.handler_id, event_type, success=False, error=str(e)
                )

                # Call error lifecycle hook
                if self._lifecycle.on_error:
                    try:
                        self._lifecycle.on_error(event_type.value, entry.handler_id, e)
                    except Exception as hook_error:
                        logger.error(f"Error in on_error lifecycle hook: {hook_error}")

                # Check if should auto-deregister
                if self._should_deregister(entry.handler_id):
                    handlers_to_deregister.append(entry.handler_id)
                    logger.warning(
                        f"Auto-deregistering handler {entry.handler_id} after "
                        f"{self._max_consecutive_errors} consecutive errors"
                    )

        # Deregister handlers marked for removal
        for handler_id in handlers_to_deregister:
            reason = "consecutive_errors" if self._should_deregister(handler_id) else "weak_ref_collected"
            self._deregister_handler_by_id(handler_id, reason=reason)

        return event

    def _cleanup_dead_handlers(self) -> None:
        """Remove handlers with dead weak references."""
        # Check global handlers
        dead_global = [
            entry.handler_id for entry in self._global_handlers if not entry.is_alive()
        ]
        for handler_id in dead_global:
            self._deregister_handler_by_id(handler_id, reason="weak_ref_collected")

        # Check event-specific handlers
        for event_type in list(self._handlers.keys()):
            dead_handlers = [
                entry.handler_id
                for entry in self._handlers[event_type]
                if not entry.is_alive()
            ]
            for handler_id in dead_handlers:
                self._deregister_handler_by_id(handler_id, reason="weak_ref_collected")

    def emit_sync(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
    ) -> Event:
        """Emit an event synchronously (only runs sync handlers).

        Args:
            event_type: The event type to emit.
            data: Optional event data.

        Returns:
            The emitted event.

        Note:
            Async handlers will be skipped with a warning.
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        event = Event(type=event_type, data=data or {})

        # Clean up dead weak references first
        self._cleanup_dead_handlers()

        # Collect handlers
        handlers = list(self._global_handlers)
        if event_type in self._handlers:
            handlers.extend(self._handlers[event_type])

        handlers.sort(key=lambda e: e.priority, reverse=True)

        # Track handlers to deregister after iteration
        handlers_to_deregister: list[str] = []

        for entry in handlers:
            # Skip dead weak references
            if not entry.is_alive():
                handlers_to_deregister.append(entry.handler_id)
                continue

            handler = entry.get_handler()
            if handler is None:
                handlers_to_deregister.append(entry.handler_id)
                continue

            try:
                if entry.is_async:
                    logger.warning(
                        f"Skipping async handler in sync emit for {event_type}"
                    )
                    continue

                sync_handler: SyncHandler = handler  # type: ignore[assignment]
                sync_handler(event)

                # Track success
                self._track_handler_result(entry.handler_id, event_type, success=True)

            except Exception as e:
                logger.error(f"Error in event handler {entry.handler_id} for {event_type}: {e}")
                # Track error
                self._track_handler_result(
                    entry.handler_id, event_type, success=False, error=str(e)
                )

                # Call error lifecycle hook
                if self._lifecycle.on_error:
                    try:
                        self._lifecycle.on_error(event_type.value, entry.handler_id, e)
                    except Exception as hook_error:
                        logger.error(f"Error in on_error lifecycle hook: {hook_error}")

                # Check if should auto-deregister
                if self._should_deregister(entry.handler_id):
                    handlers_to_deregister.append(entry.handler_id)
                    logger.warning(
                        f"Auto-deregistering handler {entry.handler_id} after "
                        f"{self._max_consecutive_errors} consecutive errors"
                    )

        # Deregister handlers marked for removal
        for handler_id in handlers_to_deregister:
            reason = "consecutive_errors" if self._should_deregister(handler_id) else "weak_ref_collected"
            self._deregister_handler_by_id(handler_id, reason=reason)

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

    def get_handler_stats(self) -> dict[str, HandlerStats]:
        """Get statistics for all handlers.

        Returns:
            Dict mapping handler IDs to their statistics.
        """
        return dict(self._handler_stats)

    def get_handler_stats_by_id(self, handler_id: str) -> HandlerStats | None:
        """Get statistics for a specific handler.

        Args:
            handler_id: The handler's unique ID.

        Returns:
            Handler statistics or None if not found.
        """
        return self._handler_stats.get(handler_id)

    def get_unhealthy_handlers(self, error_threshold: int = 1) -> list[str]:
        """Get handlers with high error rates.

        Args:
            error_threshold: Minimum consecutive errors to be considered unhealthy.

        Returns:
            List of handler IDs with high error rates.
        """
        unhealthy = []
        for handler_id, stats in self._handler_stats.items():
            if stats.consecutive_errors >= error_threshold:
                unhealthy.append(handler_id)
        return unhealthy

    def reset_handler_stats(self, handler_id: str) -> bool:
        """Reset statistics for a handler.

        Args:
            handler_id: The handler's unique ID.

        Returns:
            True if handler was found and stats were reset.
        """
        if handler_id not in self._handler_stats:
            return False

        stats = self._handler_stats[handler_id]
        stats.success_count = 0
        stats.error_count = 0
        stats.consecutive_errors = 0
        stats.last_error = None
        stats.last_error_time = None
        return True

    @contextmanager
    def scoped_handler(
        self,
        event_type: EventType | str,
        handler: Handler,
        priority: int = 0,
    ) -> Iterator[str]:
        """Context manager for automatic handler cleanup.

        Args:
            event_type: The event type to listen for.
            handler: The handler function.
            priority: Handler priority.

        Yields:
            The handler ID.

        Example:
            with emitter.scoped_handler(EventType.INDEX_FILE, my_handler) as hid:
                await emitter.emit(EventType.INDEX_FILE, {"test": True})
            # Handler automatically removed
        """
        handler_id = self.add_handler(event_type, handler, priority)
        try:
            yield handler_id
        finally:
            self.off(event_type, handler_id)


class HookRunner:
    """Runner for external hook scripts.

    Allows registering shell commands or Python scripts to run on events.

    Example:
        runner = HookRunner(emitter)
        runner.register_script(EventType.INDEX_COMPLETE, "notify.sh")
        runner.register_script(EventType.WIKI_COMPLETE, "deploy.py")
    """

    def __init__(self, emitter: EventEmitter) -> None:
        """Initialize the hook runner.

        Args:
            emitter: The event emitter to subscribe to.
        """
        self._emitter = emitter
        self._scripts: dict[EventType, list[Path]] = {}

    def register_script(
        self,
        event_type: EventType | str,
        script_path: str | Path,
        priority: int = -100,
    ) -> None:
        """Register a script to run on an event.

        Args:
            event_type: The event type to trigger the script.
            script_path: Path to the script file.
            priority: Handler priority (default -100, runs after other handlers).
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        path = Path(script_path)

        if event_type not in self._scripts:
            self._scripts[event_type] = []

            # Register the handler once per event type
            async def run_scripts(event: Event) -> None:
                await self._run_scripts_for_event(event)

            self._emitter.add_handler(event_type, run_scripts, priority)

        self._scripts[event_type].append(path)
        logger.info(f"Registered hook script for {event_type}: {path}")

    async def _run_scripts_for_event(self, event: Event) -> None:
        """Run all scripts registered for an event.

        Args:
            event: The event that was emitted.
        """
        scripts = self._scripts.get(event.type, [])

        for script_path in scripts:
            if not script_path.exists():
                logger.warning(f"Hook script not found: {script_path}")
                continue

            try:
                await self._execute_script(script_path, event)
            except Exception as e:
                logger.error(f"Error running hook script {script_path}: {e}")

    async def _execute_script(self, script_path: Path, event: Event) -> None:
        """Execute a script with event data as environment variables.

        Args:
            script_path: Path to the script.
            event: The event data.
        """
        import json
        import os

        # Prepare environment with event data
        env = os.environ.copy()
        env["DEEPWIKI_EVENT_TYPE"] = event.type.value
        env["DEEPWIKI_EVENT_TIMESTAMP"] = str(event.timestamp)
        env["DEEPWIKI_EVENT_DATA"] = json.dumps(event.data)

        # Add individual data fields as env vars
        for key, value in event.data.items():
            env_key = f"DEEPWIKI_{key.upper()}"
            if isinstance(value, (str, int, float, bool)):
                env[env_key] = str(value)

        # Determine how to run the script
        suffix = script_path.suffix.lower()

        if suffix == ".py":
            cmd = ["python", str(script_path)]
        elif suffix == ".sh":
            cmd = ["bash", str(script_path)]
        else:
            # Try to execute directly
            cmd = [str(script_path)]

        logger.debug(f"Running hook script: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.warning(
                f"Hook script {script_path} exited with code {proc.returncode}: "
                f"{stderr.decode()}"
            )
        elif stdout:
            logger.debug(f"Hook script output: {stdout.decode()}")

    def unregister_script(
        self,
        event_type: EventType | str,
        script_path: str | Path,
    ) -> bool:
        """Unregister a script from an event.

        Args:
            event_type: The event type.
            script_path: Path to the script.

        Returns:
            True if script was found and removed.
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        path = Path(script_path)

        if event_type not in self._scripts:
            return False

        try:
            self._scripts[event_type].remove(path)
            return True
        except ValueError:
            return False

    def list_scripts(
        self, event_type: EventType | str | None = None
    ) -> dict[EventType, list[Path]]:
        """List registered scripts.

        Args:
            event_type: Filter by event type, or None for all.

        Returns:
            Dict mapping event types to script paths.
        """
        if event_type is None:
            return {k: list(v) for k, v in self._scripts.items()}

        if isinstance(event_type, str):
            event_type = EventType(event_type)

        return {event_type: list(self._scripts.get(event_type, []))}


# Global event emitter singleton
_emitter: EventEmitter | None = None
_emitter_lifecycle: HandlerLifecycle | None = None


def get_event_emitter(
    max_consecutive_errors: int = 3,
    lifecycle: HandlerLifecycle | None = None,
) -> EventEmitter:
    """Get the global event emitter instance.

    Args:
        max_consecutive_errors: Number of consecutive errors before auto-deregistration.
        lifecycle: Optional lifecycle hooks (only used on first call).

    Returns:
        The global EventEmitter singleton.
    """
    global _emitter, _emitter_lifecycle
    if _emitter is None:
        _emitter_lifecycle = lifecycle
        _emitter = EventEmitter(
            max_consecutive_errors=max_consecutive_errors,
            lifecycle=lifecycle,
        )
    return _emitter


def set_global_lifecycle(lifecycle: HandlerLifecycle) -> None:
    """Set lifecycle hooks for the global emitter.

    Args:
        lifecycle: The lifecycle hooks to set.

    Note:
        Must be called before get_event_emitter() or after reset_event_emitter().
    """
    global _emitter_lifecycle, _emitter
    _emitter_lifecycle = lifecycle
    if _emitter is not None:
        _emitter._lifecycle = lifecycle


def reset_event_emitter() -> None:
    """Reset the global event emitter.

    Useful for testing.
    """
    global _emitter, _emitter_lifecycle
    if _emitter is not None:
        _emitter.clear_handlers()
    _emitter = None
    _emitter_lifecycle = None
