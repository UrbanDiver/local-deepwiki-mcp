"""Tests for the event system."""

import asyncio

import pytest

from local_deepwiki.events import (
    Event,
    EventEmitter,
    EventType,
    HandlerEntry,
    get_event_emitter,
    reset_event_emitter,
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
        event = Event.create(type=EventType.INDEX_START, data={"repo": "/path"})
        assert event.type == EventType.INDEX_START
        assert event.data == {"repo": "/path"}
        assert event.timestamp > 0

    def test_create_event_with_string_type(self):
        """Test creating event with string type converts to enum."""
        event = Event.create(type="index.start", data={})
        assert event.type == EventType.INDEX_START

    def test_event_default_data(self):
        """Test event has empty dict as default data."""
        event = Event.create(type=EventType.INDEX_START)
        assert event.data == {}

    def test_event_timestamp_auto_generated(self):
        """Test event timestamp is auto-generated."""
        event = Event.create(type=EventType.INDEX_START)
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0

    def test_event_is_frozen(self):
        """Test that Event is immutable."""
        event = Event.create(type=EventType.INDEX_START, data={"key": "value"})
        with pytest.raises(AttributeError):
            event.type = EventType.WIKI_START  # type: ignore[misc]


class TestHandlerEntry:
    """Tests for HandlerEntry dataclass."""

    def test_sync_handler_detection(self):
        """Test sync handler is detected."""

        def sync_handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(
            handler=sync_handler,
            is_async=asyncio.iscoroutinefunction(sync_handler),
            priority=0,
        )
        assert entry.is_async is False

    def test_async_handler_detection(self):
        """Test async handler is detected."""

        async def async_handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(
            handler=async_handler,
            is_async=asyncio.iscoroutinefunction(async_handler),
            priority=0,
        )
        assert entry.is_async is True

    def test_priority_default(self):
        """Test default priority is 0."""

        def handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(
            handler=handler,
            is_async=asyncio.iscoroutinefunction(handler),
        )
        assert entry.priority == 0

    def test_handler_entry_is_frozen(self):
        """Test that HandlerEntry is immutable."""

        def handler(_event: Event) -> None:
            pass

        entry = HandlerEntry(handler=handler, is_async=False)
        with pytest.raises(AttributeError):
            entry.priority = 99  # type: ignore[misc]


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

    def test_off_nonexistent_handler(self, emitter: EventEmitter):
        """Test off() returns False for non-existent handler."""
        result = emitter.off(EventType.INDEX_START, "nonexistent-id")
        assert result is False


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
