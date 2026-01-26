"""Tests for the event system."""

import asyncio
import gc
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import pytest

from local_deepwiki.events import (
    Event,
    EventEmitter,
    EventType,
    HandlerEntry,
    HandlerLifecycle,
    HandlerStats,
    HookRunner,
    get_event_emitter,
    reset_event_emitter,
    set_global_lifecycle,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_index_events_exist(self):
        """Test index-related events exist."""
        assert EventType.INDEX_START.value == "index.start"
        assert EventType.INDEX_FILE.value == "index.file"
        assert EventType.INDEX_CHUNK.value == "index.chunk"
        assert EventType.INDEX_COMPLETE.value == "index.complete"
        assert EventType.INDEX_ERROR.value == "index.error"

    def test_wiki_events_exist(self):
        """Test wiki-related events exist."""
        assert EventType.WIKI_START.value == "wiki.start"
        assert EventType.WIKI_PAGE_START.value == "wiki.page.start"
        assert EventType.WIKI_PAGE_COMPLETE.value == "wiki.page.complete"
        assert EventType.WIKI_COMPLETE.value == "wiki.complete"
        assert EventType.WIKI_ERROR.value == "wiki.error"

    def test_research_events_exist(self):
        """Test research-related events exist."""
        assert EventType.RESEARCH_START.value == "research.start"
        assert EventType.RESEARCH_QUERY.value == "research.query"
        assert EventType.RESEARCH_COMPLETE.value == "research.complete"

    def test_general_events_exist(self):
        """Test general events exist."""
        assert EventType.ERROR.value == "error"
        assert EventType.WARNING.value == "warning"


class TestEvent:
    """Tests for Event dataclass."""

    def test_create_event(self):
        """Test creating an event."""
        event = Event(type=EventType.INDEX_START, data={"repo": "/path"})
        assert event.type == EventType.INDEX_START
        assert event.data == {"repo": "/path"}
        assert event.timestamp > 0

    def test_create_event_with_string_type(self):
        """Test creating event with string type converts to enum."""
        event = Event(type="index.start", data={})  # type: ignore[arg-type]
        assert event.type == EventType.INDEX_START

    def test_event_default_data(self):
        """Test event has empty dict as default data."""
        event = Event(type=EventType.INDEX_START)
        assert event.data == {}

    def test_event_timestamp_auto_generated(self):
        """Test event timestamp is auto-generated."""
        event = Event(type=EventType.INDEX_START)
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0


class TestHandlerEntry:
    """Tests for HandlerEntry dataclass."""

    def test_sync_handler_detection(self):
        """Test sync handler is detected."""

        def sync_handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=sync_handler, priority=0)
        assert entry.is_async is False

    def test_async_handler_detection(self):
        """Test async handler is detected."""

        async def async_handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=async_handler, priority=0)
        assert entry.is_async is True

    def test_priority_default(self):
        """Test default priority is 0."""

        def handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=handler)
        assert entry.priority == 0


class TestEventEmitter:
    """Tests for EventEmitter."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter for each test."""
        return EventEmitter()

    def test_empty_emitter(self, emitter: EventEmitter):
        """Test empty emitter has no handlers."""
        assert emitter.handler_count() == 0

    def test_add_handler(self, emitter: EventEmitter):
        """Test adding a handler."""
        called = []

        def handler(event: Event) -> None:
            called.append(event)

        emitter.add_handler(EventType.INDEX_START, handler)
        assert emitter.handler_count(EventType.INDEX_START) == 1

    def test_on_decorator(self, emitter: EventEmitter):
        """Test @on decorator for registering handlers."""
        called: list[Event] = []

        @emitter.on(EventType.INDEX_FILE)
        def handler(event: Event) -> None:
            called.append(event)

        # Verify handler is registered (actual calling tested elsewhere)
        _ = handler  # Keep reference
        assert emitter.handler_count(EventType.INDEX_FILE) == 1

    def test_on_decorator_with_priority(self, emitter: EventEmitter):
        """Test @on decorator with priority."""
        @emitter.on(EventType.INDEX_START, priority=10)
        def handler(_event: Event) -> None:
            pass

        _ = handler  # Keep reference
        handlers = emitter.list_handlers(EventType.INDEX_START)
        assert len(handlers) == 1
        assert handlers[0].priority == 10

    async def test_emit_calls_handler(self, emitter: EventEmitter):
        """Test emit calls registered handlers."""
        called: list[Event] = []

        def handler(event: Event) -> None:
            called.append(event)

        emitter.add_handler(EventType.INDEX_START, handler)
        event = await emitter.emit(EventType.INDEX_START, {"test": True})

        assert len(called) == 1
        assert called[0] is event
        assert called[0].data == {"test": True}

    async def test_emit_async_handler(self, emitter: EventEmitter):
        """Test emit calls async handlers."""
        called: list[Event] = []

        async def async_handler(event: Event) -> None:
            await asyncio.sleep(0.001)
            called.append(event)

        emitter.add_handler(EventType.INDEX_START, async_handler)
        await emitter.emit(EventType.INDEX_START)

        assert len(called) == 1

    async def test_emit_priority_order(self, emitter: EventEmitter):
        """Test handlers are called in priority order (highest first)."""
        order: list[int] = []

        def make_handler(priority: int):
            def handler(event: Event) -> None:
                order.append(priority)

            return handler

        emitter.add_handler(EventType.INDEX_START, make_handler(1), priority=1)
        emitter.add_handler(EventType.INDEX_START, make_handler(10), priority=10)
        emitter.add_handler(EventType.INDEX_START, make_handler(5), priority=5)

        await emitter.emit(EventType.INDEX_START)

        assert order == [10, 5, 1]

    async def test_emit_string_type(self, emitter: EventEmitter):
        """Test emit with string event type."""
        called = []

        def handler(event: Event) -> None:
            called.append(event)

        emitter.add_handler("index.start", handler)
        await emitter.emit("index.start")

        assert len(called) == 1
        assert called[0].type == EventType.INDEX_START

    async def test_emit_handler_error_doesnt_stop_others(self, emitter: EventEmitter):
        """Test handler errors don't prevent other handlers from running."""
        called: list[str] = []

        def failing_handler(_event: Event) -> None:
            raise ValueError("Test error")

        def working_handler(_event: Event) -> None:
            called.append("worked")

        emitter.add_handler(EventType.INDEX_START, failing_handler, priority=10)
        emitter.add_handler(EventType.INDEX_START, working_handler, priority=1)

        await emitter.emit(EventType.INDEX_START)

        assert called == ["worked"]

    async def test_global_handler(self, emitter: EventEmitter):
        """Test global handler receives all events."""
        events: list[Event] = []

        def global_handler(event: Event) -> None:
            events.append(event)

        emitter.add_handler(None, global_handler)

        await emitter.emit(EventType.INDEX_START)
        await emitter.emit(EventType.WIKI_COMPLETE)

        assert len(events) == 2
        assert events[0].type == EventType.INDEX_START
        assert events[1].type == EventType.WIKI_COMPLETE

    def test_emit_sync(self, emitter: EventEmitter):
        """Test synchronous emit."""
        called: list[Event] = []

        def handler(event: Event) -> None:
            called.append(event)

        emitter.add_handler(EventType.INDEX_START, handler)
        event = emitter.emit_sync(EventType.INDEX_START, {"sync": True})

        assert len(called) == 1
        assert called[0].data == {"sync": True}

    def test_emit_sync_skips_async_handlers(self, emitter: EventEmitter):
        """Test sync emit skips async handlers."""
        sync_called: list[Event] = []
        async_called: list[Event] = []

        def sync_handler(event: Event) -> None:
            sync_called.append(event)

        async def async_handler(event: Event) -> None:
            async_called.append(event)

        emitter.add_handler(EventType.INDEX_START, sync_handler)
        emitter.add_handler(EventType.INDEX_START, async_handler)

        emitter.emit_sync(EventType.INDEX_START)

        assert len(sync_called) == 1
        assert len(async_called) == 0

    def test_remove_handler(self, emitter: EventEmitter):
        """Test removing a handler."""

        def handler(event: Event) -> None:
            pass

        emitter.add_handler(EventType.INDEX_START, handler)
        assert emitter.handler_count(EventType.INDEX_START) == 1

        result = emitter.remove_handler(EventType.INDEX_START, handler)
        assert result is True
        assert emitter.handler_count(EventType.INDEX_START) == 0

    def test_remove_handler_not_found(self, emitter: EventEmitter):
        """Test removing non-existent handler returns False."""

        def handler(event: Event) -> None:
            pass

        result = emitter.remove_handler(EventType.INDEX_START, handler)
        assert result is False

    def test_remove_global_handler(self, emitter: EventEmitter):
        """Test removing global handler."""

        def handler(event: Event) -> None:
            pass

        emitter.add_handler(None, handler)
        assert emitter.handler_count() == 1

        result = emitter.remove_handler(None, handler)
        assert result is True
        assert emitter.handler_count() == 0

    def test_clear_handlers_specific_type(self, emitter: EventEmitter):
        """Test clearing handlers for specific type."""

        def handler(event: Event) -> None:
            pass

        emitter.add_handler(EventType.INDEX_START, handler)
        emitter.add_handler(EventType.WIKI_START, handler)

        emitter.clear_handlers(EventType.INDEX_START)

        assert emitter.handler_count(EventType.INDEX_START) == 0
        assert emitter.handler_count(EventType.WIKI_START) == 1

    def test_clear_all_handlers(self, emitter: EventEmitter):
        """Test clearing all handlers."""

        def handler(event: Event) -> None:
            pass

        emitter.add_handler(EventType.INDEX_START, handler)
        emitter.add_handler(EventType.WIKI_START, handler)
        emitter.add_handler(None, handler)  # global

        emitter.clear_handlers()

        assert emitter.handler_count() == 0

    def test_list_handlers(self, emitter: EventEmitter):
        """Test listing handlers for event type."""

        def handler1(event: Event) -> None:
            pass

        def handler2(event: Event) -> None:
            pass

        emitter.add_handler(EventType.INDEX_START, handler1, priority=5)
        emitter.add_handler(EventType.INDEX_START, handler2, priority=10)

        handlers = emitter.list_handlers(EventType.INDEX_START)

        assert len(handlers) == 2
        # Should be sorted by priority (highest first)
        assert handlers[0].priority == 10
        assert handlers[1].priority == 5

    def test_list_global_handlers(self, emitter: EventEmitter):
        """Test listing global handlers."""

        def handler(event: Event) -> None:
            pass

        emitter.add_handler(None, handler)
        handlers = emitter.list_handlers(None)

        assert len(handlers) == 1


class TestHookRunner:
    """Tests for HookRunner."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter."""
        return EventEmitter()

    @pytest.fixture
    def runner(self, emitter: EventEmitter):
        """Create a hook runner with emitter."""
        return HookRunner(emitter)

    def test_register_script(self, runner: HookRunner):
        """Test registering a script."""
        runner.register_script(EventType.INDEX_COMPLETE, "/path/to/script.sh")
        scripts = runner.list_scripts(EventType.INDEX_COMPLETE)

        assert EventType.INDEX_COMPLETE in scripts
        assert Path("/path/to/script.sh") in scripts[EventType.INDEX_COMPLETE]

    def test_register_multiple_scripts(self, runner: HookRunner):
        """Test registering multiple scripts for same event."""
        runner.register_script(EventType.INDEX_COMPLETE, "script1.sh")
        runner.register_script(EventType.INDEX_COMPLETE, "script2.py")

        scripts = runner.list_scripts(EventType.INDEX_COMPLETE)
        assert len(scripts[EventType.INDEX_COMPLETE]) == 2

    def test_unregister_script(self, runner: HookRunner):
        """Test unregistering a script."""
        runner.register_script(EventType.INDEX_COMPLETE, "script.sh")
        result = runner.unregister_script(EventType.INDEX_COMPLETE, "script.sh")

        assert result is True
        scripts = runner.list_scripts(EventType.INDEX_COMPLETE)
        assert len(scripts[EventType.INDEX_COMPLETE]) == 0

    def test_unregister_nonexistent_script(self, runner: HookRunner):
        """Test unregistering non-existent script returns False."""
        result = runner.unregister_script(EventType.INDEX_COMPLETE, "nonexistent.sh")
        assert result is False

    def test_list_all_scripts(self, runner: HookRunner):
        """Test listing all registered scripts."""
        runner.register_script(EventType.INDEX_COMPLETE, "index.sh")
        runner.register_script(EventType.WIKI_COMPLETE, "wiki.sh")

        all_scripts = runner.list_scripts()

        assert EventType.INDEX_COMPLETE in all_scripts
        assert EventType.WIKI_COMPLETE in all_scripts

    async def test_script_execution(
        self, emitter: EventEmitter, runner: HookRunner, tmp_path: Path
    ):
        """Test script is executed on event."""
        # Create a simple script that writes to a file
        marker_file = tmp_path / "marker.txt"
        script = tmp_path / "hook.sh"
        script.write_text(f"#!/bin/bash\necho 'executed' > {marker_file}")
        script.chmod(0o755)

        runner.register_script(EventType.INDEX_COMPLETE, script)
        await emitter.emit(EventType.INDEX_COMPLETE, {"test": True})

        # Give script time to execute
        await asyncio.sleep(0.1)

        assert marker_file.exists()
        assert marker_file.read_text().strip() == "executed"

    async def test_script_receives_env_vars(
        self, emitter: EventEmitter, runner: HookRunner, tmp_path: Path
    ):
        """Test script receives event data as environment variables."""
        output_file = tmp_path / "output.txt"
        script = tmp_path / "hook.sh"
        script.write_text(
            f"#!/bin/bash\necho $DEEPWIKI_EVENT_TYPE > {output_file}"
        )
        script.chmod(0o755)

        runner.register_script(EventType.INDEX_COMPLETE, script)
        await emitter.emit(EventType.INDEX_COMPLETE)

        await asyncio.sleep(0.1)

        assert output_file.exists()
        assert "index.complete" in output_file.read_text()

    async def test_missing_script_doesnt_crash(
        self, emitter: EventEmitter, runner: HookRunner
    ):
        """Test missing script file doesn't crash emit."""
        runner.register_script(EventType.INDEX_COMPLETE, "/nonexistent/script.sh")

        # Should not raise
        await emitter.emit(EventType.INDEX_COMPLETE)


class TestGlobalEventEmitter:
    """Tests for global emitter singleton."""

    def test_get_event_emitter_returns_singleton(self):
        """Test get_event_emitter returns same instance."""
        reset_event_emitter()
        em1 = get_event_emitter()
        em2 = get_event_emitter()
        assert em1 is em2

    def test_reset_event_emitter(self):
        """Test reset creates new instance."""
        reset_event_emitter()
        em1 = get_event_emitter()
        em1.add_handler(EventType.INDEX_START, lambda e: None)

        reset_event_emitter()
        em2 = get_event_emitter()

        assert em1 is not em2
        assert em2.handler_count() == 0


class TestHooksConfig:
    """Tests for HooksConfig in config module."""

    def test_hooks_config_defaults(self):
        """Test HooksConfig has correct defaults."""
        from local_deepwiki.config import HooksConfig

        config = HooksConfig()
        assert config.enabled is True
        assert config.scripts_dir is None
        assert config.timeout_seconds == 30

    def test_hooks_config_in_main_config(self):
        """Test hooks is in main Config."""
        from local_deepwiki.config import Config

        config = Config()
        assert hasattr(config, "hooks")
        assert config.hooks.enabled is True

    def test_hooks_config_from_dict(self):
        """Test creating HooksConfig from dict."""
        from local_deepwiki.config import HooksConfig

        config = HooksConfig(
            enabled=False,
            scripts_dir="/custom/hooks",
            timeout_seconds=60,
        )
        assert config.enabled is False
        assert config.scripts_dir == "/custom/hooks"
        assert config.timeout_seconds == 60


class TestHandlerStats:
    """Tests for HandlerStats dataclass."""

    def test_handler_stats_defaults(self):
        """Test HandlerStats has correct defaults."""
        stats = HandlerStats(handler_id="test-123")
        assert stats.handler_id == "test-123"
        assert stats.success_count == 0
        assert stats.error_count == 0
        assert stats.consecutive_errors == 0
        assert stats.last_error is None
        assert stats.last_error_time is None
        assert stats.registered_at > 0

    def test_handler_stats_tracks_values(self):
        """Test HandlerStats can track values."""
        import time

        stats = HandlerStats(
            handler_id="test-456",
            success_count=10,
            error_count=2,
            consecutive_errors=1,
            last_error="Test error",
            last_error_time=time.time(),
        )
        assert stats.success_count == 10
        assert stats.error_count == 2
        assert stats.consecutive_errors == 1
        assert stats.last_error == "Test error"


class TestHandlerLifecycle:
    """Tests for HandlerLifecycle dataclass."""

    def test_lifecycle_defaults_to_none(self):
        """Test HandlerLifecycle has None defaults."""
        lifecycle = HandlerLifecycle()
        assert lifecycle.on_register is None
        assert lifecycle.on_success is None
        assert lifecycle.on_error is None
        assert lifecycle.on_deregister is None

    def test_lifecycle_with_callbacks(self):
        """Test HandlerLifecycle accepts callbacks."""
        called: list[str] = []

        def on_reg(event: str, hid: str) -> None:
            called.append(f"register:{event}:{hid}")

        def on_dereg(event: str, hid: str, reason: str) -> None:
            called.append(f"deregister:{event}:{hid}:{reason}")

        lifecycle = HandlerLifecycle(on_register=on_reg, on_deregister=on_dereg)
        assert lifecycle.on_register is on_reg
        assert lifecycle.on_deregister is on_dereg


class TestAutoDeregistration:
    """Tests for auto-deregistration after consecutive errors."""

    @pytest.fixture
    def emitter(self):
        """Create emitter with low error threshold for testing."""
        return EventEmitter(max_consecutive_errors=2)

    async def test_handler_auto_deregistered_after_errors(self, emitter: EventEmitter):
        """Test handler is removed after consecutive errors."""
        error_count = 0

        def failing_handler(_event: Event) -> None:
            nonlocal error_count
            error_count += 1
            raise ValueError("Always fails")

        handler_id = emitter.add_handler(EventType.INDEX_START, failing_handler)
        assert emitter.handler_count(EventType.INDEX_START) == 1

        # First error
        await emitter.emit(EventType.INDEX_START)
        assert emitter.handler_count(EventType.INDEX_START) == 1

        # Second error - should trigger deregistration
        await emitter.emit(EventType.INDEX_START)
        assert emitter.handler_count(EventType.INDEX_START) == 0

    async def test_success_resets_consecutive_errors(self, emitter: EventEmitter):
        """Test success resets consecutive error count."""
        call_count = 0

        def sometimes_failing_handler(_event: Event) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            # Subsequent calls succeed

        handler_id = emitter.add_handler(EventType.INDEX_START, sometimes_failing_handler)

        # First call - error
        await emitter.emit(EventType.INDEX_START)
        stats = emitter.get_handler_stats_by_id(handler_id)
        assert stats is not None
        assert stats.consecutive_errors == 1

        # Second call - success (resets consecutive errors)
        await emitter.emit(EventType.INDEX_START)
        stats = emitter.get_handler_stats_by_id(handler_id)
        assert stats is not None
        assert stats.consecutive_errors == 0

        # Handler still registered
        assert emitter.handler_count(EventType.INDEX_START) == 1

    async def test_handler_stats_tracked(self, emitter: EventEmitter):
        """Test handler stats are tracked correctly."""
        call_count = 0

        def mixed_handler(_event: Event) -> None:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ValueError("Even calls fail")

        handler_id = emitter.add_handler(EventType.INDEX_START, mixed_handler)

        # Call 1: success
        await emitter.emit(EventType.INDEX_START)
        # Call 2: fail
        await emitter.emit(EventType.INDEX_START)
        # Call 3: success (but handler was deregistered)
        # Wait - handler should still be there since consecutive_errors is only 1
        stats = emitter.get_handler_stats_by_id(handler_id)
        assert stats is not None
        assert stats.success_count == 1
        assert stats.error_count == 1

    def test_sync_emit_auto_deregistration(self):
        """Test sync emit also triggers auto-deregistration."""
        emitter = EventEmitter(max_consecutive_errors=2)

        def failing_handler(_event: Event) -> None:
            raise ValueError("Always fails")

        emitter.add_handler(EventType.INDEX_START, failing_handler)
        assert emitter.handler_count(EventType.INDEX_START) == 1

        # First error
        emitter.emit_sync(EventType.INDEX_START)
        assert emitter.handler_count(EventType.INDEX_START) == 1

        # Second error - should trigger deregistration
        emitter.emit_sync(EventType.INDEX_START)
        assert emitter.handler_count(EventType.INDEX_START) == 0


class TestWeakReferences:
    """Tests for weak reference handler support."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter."""
        return EventEmitter()

    def test_weak_handler_entry_is_alive_direct_weakref(self):
        """Test is_alive for weak handler entries with direct weakref."""

        class MyObj:
            pass

        obj = MyObj()

        def handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=handler, is_weak=True)
        entry._weak_ref = weakref.ref(obj)

        assert entry.is_alive() is True

        del obj
        gc.collect()

        assert entry.is_alive() is False

    def test_non_weak_handler_always_alive(self):
        """Test non-weak handlers are always alive."""

        def handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=handler, is_weak=False)
        assert entry.is_alive() is True

    def test_weak_handler_with_no_weakref_is_alive(self):
        """Test weak handler with no weakref set is alive."""

        def handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=handler, is_weak=True)
        # No _weak_ref set
        assert entry.is_alive() is True

    async def test_weak_handler_manual_cleanup(self, emitter: EventEmitter):
        """Test handlers can be manually cleaned up via off()."""
        events_received: list[Event] = []

        def handler(event: Event) -> None:
            events_received.append(event)

        handler_id = emitter.add_handler(EventType.INDEX_START, handler, weak=True)

        # Emit while handler is registered
        await emitter.emit(EventType.INDEX_START, {"test": 1})
        assert len(events_received) == 1
        assert emitter.handler_count(EventType.INDEX_START) == 1

        # Manually remove handler
        emitter.off(EventType.INDEX_START, handler_id)

        # Handler should be cleaned up
        assert emitter.handler_count(EventType.INDEX_START) == 0

        # Emit again - should not be received
        await emitter.emit(EventType.INDEX_START, {"test": 2})
        assert len(events_received) == 1

    async def test_dead_weakref_cleaned_on_emit(self, emitter: EventEmitter):
        """Test that dead weak references are cleaned up during emit."""

        class Container:
            pass

        container = Container()

        def handler(_event: Event) -> None:
            pass

        # Register handler and manually set weak ref to container
        handler_id = emitter.add_handler(EventType.INDEX_START, handler, weak=True)

        # Manually set the weak ref to point to container
        handlers = emitter.list_handlers(EventType.INDEX_START)
        handlers[0]._weak_ref = weakref.ref(container)

        assert emitter.handler_count(EventType.INDEX_START) == 1

        # Delete container
        del container
        gc.collect()

        # Emit - should trigger cleanup
        await emitter.emit(EventType.INDEX_START)

        # Handler should be cleaned up because weakref is dead
        assert emitter.handler_count(EventType.INDEX_START) == 0


class TestScopedHandlers:
    """Tests for scoped handler context manager."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter."""
        return EventEmitter()

    async def test_scoped_handler_cleanup(self, emitter: EventEmitter):
        """Test scoped handler is cleaned up after context."""
        events: list[Event] = []

        def handler(event: Event) -> None:
            events.append(event)

        with emitter.scoped_handler(EventType.INDEX_START, handler) as handler_id:
            assert emitter.handler_count(EventType.INDEX_START) == 1
            await emitter.emit(EventType.INDEX_START, {"inside": True})

        # Handler should be removed after context
        assert emitter.handler_count(EventType.INDEX_START) == 0
        assert len(events) == 1
        assert events[0].data == {"inside": True}

    async def test_scoped_handler_cleanup_on_exception(self, emitter: EventEmitter):
        """Test scoped handler is cleaned up even on exception."""
        events: list[Event] = []

        def handler(event: Event) -> None:
            events.append(event)

        try:
            with emitter.scoped_handler(EventType.INDEX_START, handler):
                assert emitter.handler_count(EventType.INDEX_START) == 1
                raise RuntimeError("Test exception")
        except RuntimeError:
            pass

        # Handler should still be removed
        assert emitter.handler_count(EventType.INDEX_START) == 0

    def test_scoped_handler_returns_id(self, emitter: EventEmitter):
        """Test scoped handler yields the handler ID."""
        def handler(_event: Event) -> None:
            pass

        with emitter.scoped_handler(EventType.INDEX_START, handler) as handler_id:
            assert isinstance(handler_id, str)
            assert len(handler_id) > 0
            # Should be able to get stats by this ID
            stats = emitter.get_handler_stats_by_id(handler_id)
            assert stats is not None


class TestHandlerStatistics:
    """Tests for handler statistics and health monitoring."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter."""
        return EventEmitter()

    async def test_get_handler_stats(self, emitter: EventEmitter):
        """Test getting stats for all handlers."""
        def handler1(_event: Event) -> None:
            pass

        def handler2(_event: Event) -> None:
            pass

        id1 = emitter.add_handler(EventType.INDEX_START, handler1)
        id2 = emitter.add_handler(EventType.WIKI_START, handler2)

        stats = emitter.get_handler_stats()
        assert id1 in stats
        assert id2 in stats
        assert stats[id1].handler_id == id1
        assert stats[id2].handler_id == id2

    async def test_get_unhealthy_handlers(self, emitter: EventEmitter):
        """Test getting handlers with high error rates."""
        def good_handler(_event: Event) -> None:
            pass

        def bad_handler(_event: Event) -> None:
            raise ValueError("Always fails")

        id_good = emitter.add_handler(EventType.INDEX_START, good_handler)
        id_bad = emitter.add_handler(EventType.INDEX_START, bad_handler, priority=10)

        # Emit events
        await emitter.emit(EventType.INDEX_START)
        await emitter.emit(EventType.INDEX_START)

        # Get unhealthy handlers (threshold=1)
        unhealthy = emitter.get_unhealthy_handlers(error_threshold=1)
        assert id_bad in unhealthy
        assert id_good not in unhealthy

    def test_reset_handler_stats(self, emitter: EventEmitter):
        """Test resetting handler statistics."""
        def handler(_event: Event) -> None:
            raise ValueError("Fails")

        handler_id = emitter.add_handler(EventType.INDEX_START, handler)

        # Generate some errors
        emitter.emit_sync(EventType.INDEX_START)

        stats = emitter.get_handler_stats_by_id(handler_id)
        assert stats is not None
        assert stats.error_count == 1
        assert stats.consecutive_errors == 1

        # Reset stats
        result = emitter.reset_handler_stats(handler_id)
        assert result is True

        stats = emitter.get_handler_stats_by_id(handler_id)
        assert stats is not None
        assert stats.error_count == 0
        assert stats.consecutive_errors == 0

    def test_reset_stats_nonexistent_handler(self, emitter: EventEmitter):
        """Test resetting stats for non-existent handler."""
        result = emitter.reset_handler_stats("nonexistent-id")
        assert result is False


class TestLifecycleHooks:
    """Tests for handler lifecycle hooks."""

    @pytest.fixture
    def lifecycle_events(self):
        """Track lifecycle events."""
        return []

    @pytest.fixture
    def lifecycle(self, lifecycle_events: list):
        """Create lifecycle with tracking callbacks."""
        def on_register(event: str, hid: str) -> None:
            lifecycle_events.append(("register", event, hid))

        def on_success(event: str, hid: str) -> None:
            lifecycle_events.append(("success", event, hid))

        def on_error(event: str, hid: str, exc: Exception) -> None:
            lifecycle_events.append(("error", event, hid, str(exc)))

        def on_deregister(event: str, hid: str, reason: str) -> None:
            lifecycle_events.append(("deregister", event, hid, reason))

        return HandlerLifecycle(
            on_register=on_register,
            on_success=on_success,
            on_error=on_error,
            on_deregister=on_deregister,
        )

    @pytest.fixture
    def emitter(self, lifecycle: HandlerLifecycle):
        """Create emitter with lifecycle hooks."""
        return EventEmitter(max_consecutive_errors=2, lifecycle=lifecycle)

    async def test_on_register_called(
        self, emitter: EventEmitter, lifecycle_events: list
    ):
        """Test on_register lifecycle hook is called."""
        def handler(_event: Event) -> None:
            pass

        handler_id = emitter.add_handler(EventType.INDEX_START, handler)

        assert len(lifecycle_events) == 1
        assert lifecycle_events[0][0] == "register"
        assert lifecycle_events[0][1] == "index.start"
        assert lifecycle_events[0][2] == handler_id

    async def test_on_success_called(
        self, emitter: EventEmitter, lifecycle_events: list
    ):
        """Test on_success lifecycle hook is called."""
        def handler(_event: Event) -> None:
            pass

        handler_id = emitter.add_handler(EventType.INDEX_START, handler)
        lifecycle_events.clear()

        await emitter.emit(EventType.INDEX_START)

        success_events = [e for e in lifecycle_events if e[0] == "success"]
        assert len(success_events) == 1
        assert success_events[0][1] == "index.start"
        assert success_events[0][2] == handler_id

    async def test_on_error_called(
        self, emitter: EventEmitter, lifecycle_events: list
    ):
        """Test on_error lifecycle hook is called."""
        def failing_handler(_event: Event) -> None:
            raise ValueError("Test error")

        handler_id = emitter.add_handler(EventType.INDEX_START, failing_handler)
        lifecycle_events.clear()

        await emitter.emit(EventType.INDEX_START)

        error_events = [e for e in lifecycle_events if e[0] == "error"]
        assert len(error_events) == 1
        assert error_events[0][1] == "index.start"
        assert error_events[0][2] == handler_id
        assert "Test error" in error_events[0][3]

    async def test_on_deregister_called(
        self, emitter: EventEmitter, lifecycle_events: list
    ):
        """Test on_deregister lifecycle hook is called."""
        def failing_handler(_event: Event) -> None:
            raise ValueError("Always fails")

        handler_id = emitter.add_handler(EventType.INDEX_START, failing_handler)
        lifecycle_events.clear()

        # Trigger 2 errors to cause deregistration
        await emitter.emit(EventType.INDEX_START)
        await emitter.emit(EventType.INDEX_START)

        deregister_events = [e for e in lifecycle_events if e[0] == "deregister"]
        assert len(deregister_events) == 1
        assert deregister_events[0][1] == "index.start"
        assert deregister_events[0][2] == handler_id
        assert deregister_events[0][3] == "consecutive_errors"


class TestOffMethod:
    """Tests for the off() method."""

    @pytest.fixture
    def emitter(self):
        """Create a fresh emitter."""
        return EventEmitter()

    def test_off_removes_handler_by_id(self, emitter: EventEmitter):
        """Test off() removes handler by ID."""
        def handler(_event: Event) -> None:
            pass

        handler_id = emitter.add_handler(EventType.INDEX_START, handler)
        assert emitter.handler_count(EventType.INDEX_START) == 1

        result = emitter.off(EventType.INDEX_START, handler_id)
        assert result is True
        assert emitter.handler_count(EventType.INDEX_START) == 0

    def test_off_cleans_up_stats(self, emitter: EventEmitter):
        """Test off() cleans up handler stats."""
        def handler(_event: Event) -> None:
            pass

        handler_id = emitter.add_handler(EventType.INDEX_START, handler)
        assert emitter.get_handler_stats_by_id(handler_id) is not None

        emitter.off(EventType.INDEX_START, handler_id)
        assert emitter.get_handler_stats_by_id(handler_id) is None

    def test_off_nonexistent_handler(self, emitter: EventEmitter):
        """Test off() returns False for non-existent handler."""
        result = emitter.off(EventType.INDEX_START, "nonexistent-id")
        assert result is False


class TestGlobalLifecycle:
    """Tests for global lifecycle management."""

    def test_set_global_lifecycle_on_existing_emitter(self):
        """Test setting global lifecycle hooks on existing emitter."""
        reset_event_emitter()
        called: list[str] = []

        # First get the emitter (creates it)
        emitter = get_event_emitter()

        # Then set lifecycle
        lifecycle = HandlerLifecycle(
            on_register=lambda e, h: called.append(f"register:{e}")
        )
        set_global_lifecycle(lifecycle)

        # Now add handler - lifecycle should be called
        emitter.add_handler(EventType.INDEX_START, lambda e: None)

        assert "register:index.start" in called

        # Cleanup
        reset_event_emitter()

    def test_get_event_emitter_with_lifecycle(self):
        """Test creating global emitter with lifecycle."""
        reset_event_emitter()
        called: list[str] = []

        lifecycle = HandlerLifecycle(
            on_register=lambda e, h: called.append(f"register:{e}")
        )

        emitter = get_event_emitter(lifecycle=lifecycle)
        emitter.add_handler(EventType.INDEX_START, lambda e: None)

        assert "register:index.start" in called

        # Cleanup
        reset_event_emitter()

    def test_set_global_lifecycle_before_emitter(self):
        """Test setting lifecycle before emitter is created."""
        reset_event_emitter()
        called: list[str] = []

        # Set lifecycle first (emitter doesn't exist yet)
        lifecycle = HandlerLifecycle(
            on_register=lambda e, h: called.append(f"register:{e}")
        )
        set_global_lifecycle(lifecycle)

        # Now create emitter with lifecycle
        emitter = get_event_emitter(lifecycle=lifecycle)
        emitter.add_handler(EventType.INDEX_START, lambda e: None)

        assert "register:index.start" in called

        # Cleanup
        reset_event_emitter()
