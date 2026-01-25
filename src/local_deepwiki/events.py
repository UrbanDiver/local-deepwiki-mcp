"""Event system for local-deepwiki lifecycle hooks.

Provides an event emitter pattern for subscribing to and emitting
events during indexing and wiki generation.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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

        # Or with decorator
        @emitter.on(EventType.WIKI_PAGE_COMPLETE, priority=10)
        async def on_page_complete(event: Event):
            await notify_webhook(event.data)

        # Emit events
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
    ) -> None:
        """Register an event handler.

        Args:
            event_type: The event type to listen for, or None for all events.
            handler: The handler function (sync or async).
            priority: Handler priority (higher runs first).
        """
        entry = HandlerEntry(handler=handler, priority=priority)

        if event_type is None:
            self._global_handlers.append(entry)
            self._global_handlers.sort(key=lambda e: e.priority, reverse=True)
        else:
            if isinstance(event_type, str):
                event_type = EventType(event_type)

            if event_type not in self._handlers:
                self._handlers[event_type] = []

            self._handlers[event_type].append(entry)
            self._handlers[event_type].sort(key=lambda e: e.priority, reverse=True)

        logger.debug(
            f"Registered handler for {event_type or 'all events'} "
            f"(priority={priority}, async={entry.is_async})"
        )

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
        handlers.sort(key=lambda e: e.priority, reverse=True)

        # Execute handlers
        for entry in handlers:
            try:
                if entry.is_async:
                    # Cast to async handler for type checker
                    async_handler: AsyncHandler = entry.handler  # type: ignore[assignment]
                    await async_handler(event)
                else:
                    sync_handler: SyncHandler = entry.handler  # type: ignore[assignment]
                    sync_handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")
                # Don't re-raise to allow other handlers to run

        return event

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

        # Collect handlers
        handlers = list(self._global_handlers)
        if event_type in self._handlers:
            handlers.extend(self._handlers[event_type])

        handlers.sort(key=lambda e: e.priority, reverse=True)

        for entry in handlers:
            try:
                if entry.is_async:
                    logger.warning(
                        f"Skipping async handler in sync emit for {event_type}"
                    )
                    continue
                entry.handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

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
