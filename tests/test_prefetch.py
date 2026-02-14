"""Tests for the prefetch queue and priority LLM slot management."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from local_deepwiki.generators.prefetch import (
    DrainStatus,
    PrefetchQueue,
    PriorityLLMSlot,
)


# ---------------------------------------------------------------------------
# TestDrainStatus
# ---------------------------------------------------------------------------


class TestDrainStatus:
    def test_initial_state(self) -> None:
        ds = DrainStatus()
        assert ds.enabled is False
        assert ds.started is False
        assert ds.total_pages == 0
        assert ds.pages_remaining == 0
        assert ds.current_page is None

    def test_finished_property_not_started(self) -> None:
        ds = DrainStatus(started=False, pages_remaining=0)
        assert ds.finished is False

    def test_finished_property_started_remaining(self) -> None:
        ds = DrainStatus(started=True, pages_remaining=5)
        assert ds.finished is False

    def test_finished_property_started_done(self) -> None:
        ds = DrainStatus(started=True, pages_remaining=0)
        assert ds.finished is True

    def test_elapsed_seconds_not_started(self) -> None:
        ds = DrainStatus()
        assert ds.elapsed_seconds is None

    def test_elapsed_seconds_running(self) -> None:
        ds = DrainStatus(started_at=time.time() - 10.0)
        elapsed = ds.elapsed_seconds
        assert elapsed is not None
        assert elapsed >= 9.5

    def test_elapsed_seconds_completed(self) -> None:
        start = time.time() - 30.0
        end = start + 20.0
        ds = DrainStatus(started_at=start, completed_at=end)
        assert ds.elapsed_seconds == 20.0

    def test_to_dict_disabled(self) -> None:
        ds = DrainStatus(enabled=False)
        d = ds.to_dict()
        assert d["state"] == "disabled"
        assert d["enabled"] is False

    def test_to_dict_waiting(self) -> None:
        ds = DrainStatus(enabled=True, started=False)
        d = ds.to_dict()
        assert d["state"] == "waiting"

    def test_to_dict_draining(self) -> None:
        ds = DrainStatus(
            enabled=True, started=True, pages_remaining=5, started_at=time.time()
        )
        d = ds.to_dict()
        assert d["state"] == "draining"

    def test_to_dict_finished(self) -> None:
        ds = DrainStatus(
            enabled=True,
            started=True,
            pages_remaining=0,
            started_at=time.time() - 5,
            completed_at=time.time(),
        )
        d = ds.to_dict()
        assert d["state"] == "finished"

    def test_to_dict_truncates_errors(self) -> None:
        ds = DrainStatus(errors=[f"error-{i}" for i in range(10)])
        d = ds.to_dict()
        assert len(d["errors"]) == 5


# ---------------------------------------------------------------------------
# TestPriorityLLMSlot
# ---------------------------------------------------------------------------


class TestPriorityLLMSlot:
    async def test_foreground_acquires_immediately(self) -> None:
        sem = asyncio.Semaphore(1)
        slot = PriorityLLMSlot(sem)

        await slot.acquire_foreground()
        slot.release()

    async def test_background_yields_to_foreground(self) -> None:
        sem = asyncio.Semaphore(1)
        slot = PriorityLLMSlot(sem)

        acquired = False

        async def background_task() -> None:
            nonlocal acquired
            await slot.acquire_background()
            acquired = True
            slot.release()

        slot._fg_waiting = 1

        bg = asyncio.create_task(background_task())
        await asyncio.sleep(0.15)
        assert not acquired

        slot._fg_waiting = 0
        await asyncio.wait_for(bg, timeout=2.0)
        assert acquired

    async def test_foreground_counter_management(self) -> None:
        sem = asyncio.Semaphore(1)
        slot = PriorityLLMSlot(sem)

        assert slot._fg_waiting == 0
        await slot.acquire_foreground()
        assert slot._fg_waiting == 0
        slot.release()


# ---------------------------------------------------------------------------
# TestPrefetchQueue
# ---------------------------------------------------------------------------


class TestPrefetchQueue:
    def _make_generator(self) -> MagicMock:
        gen = MagicMock()
        gen.warm_page = AsyncMock()
        gen._read_cached = MagicMock(return_value=None)
        gen.get_virtual_structure = MagicMock(
            return_value={
                "pages": [{"path": "index.md"}, {"path": "architecture.md"}],
                "sections": {
                    "files": [{"path": "files/main.md"}, {"path": "files/utils.md"}]
                },
            }
        )
        return gen

    async def test_enqueue_predictions_skips_generated(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(gen, max_workers=0, max_queue=20, drain_enabled=False)
        pq._generated.add("files/cached.md")

        await pq.enqueue_predictions("index.md", ["files/cached.md"], [])

        assert pq._queue.empty()

    async def test_enqueue_predictions_adds_items(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(gen, max_workers=0, max_queue=20, drain_enabled=False)

        await pq.enqueue_predictions(
            "index.md",
            ["files/target1.md"],
            ["modules/sibling1.md"],
        )

        items = []
        while not pq._queue.empty():
            items.append(pq._queue.get_nowait())
        assert len(items) == 2
        priorities = {p for p, _ in items}
        assert 2 in priorities
        assert 3 in priorities

    async def test_worker_generates_page(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(gen, max_workers=1, max_queue=20, drain_enabled=False)

        pq._queue.put_nowait((2, "files/test.md"))

        pq._started = True
        worker = asyncio.create_task(pq._worker(0))
        await asyncio.sleep(0.2)
        pq._started = False
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

        gen.warm_page.assert_awaited_with("files/test.md")
        assert "files/test.md" in pq._generated

    async def test_worker_handles_failure(self) -> None:
        gen = self._make_generator()
        gen.warm_page = AsyncMock(side_effect=RuntimeError("LLM failed"))
        pq = PrefetchQueue(gen, max_workers=1, max_queue=20, drain_enabled=True)
        pq._drain_started = True
        pq.drain_status.pages_remaining = 1

        pq._queue.put_nowait((2, "files/broken.md"))

        pq._started = True
        worker = asyncio.create_task(pq._worker(0))
        await asyncio.sleep(0.2)
        pq._started = False
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

        assert pq.drain_status.pages_failed == 1
        assert pq.drain_status.pages_remaining == 0
        assert len(pq.drain_status.errors) == 1

    async def test_drain_enqueues_all_uncached_pages(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(
            gen,
            max_workers=0,
            max_queue=50,
            drain_enabled=True,
            drain_idle_seconds=0,
        )

        await pq._maybe_start_drain()

        assert pq._drain_started is True
        assert pq.drain_status.started is True
        assert pq.drain_status.total_pages > 0

    async def test_drain_skips_cached_pages(self) -> None:
        gen = self._make_generator()
        gen._read_cached = MagicMock(
            side_effect=lambda p: "cached" if p == "index.md" else None
        )
        pq = PrefetchQueue(
            gen,
            max_workers=0,
            max_queue=50,
            drain_enabled=True,
            drain_idle_seconds=0,
        )

        await pq._maybe_start_drain()

        assert pq.drain_status.pages_cached >= 1
        assert "index.md" in pq._generated

    async def test_stop_cancels_workers(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(gen, max_workers=2, max_queue=20, drain_enabled=False)
        pq.start()
        assert len(pq._workers) == 2

        await pq.stop()
        assert pq._started is False

    def test_kickstart_drain_noop_when_disabled(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(gen, max_workers=0, max_queue=20, drain_enabled=False)
        pq.kickstart_drain()

    def test_kickstart_drain_noop_when_already_started(self) -> None:
        gen = self._make_generator()
        pq = PrefetchQueue(gen, max_workers=0, max_queue=20, drain_enabled=True)
        pq._drain_started = True
        pq.kickstart_drain()
