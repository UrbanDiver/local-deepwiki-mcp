"""Background page prefetch with priority-aware LLM slot management."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from local_deepwiki.generators.lazy_generator import LazyPageGenerator

logger = get_logger(__name__)


@dataclass
class DrainStatus:
    """Observable drain state."""

    enabled: bool = False
    started: bool = False
    started_at: float | None = None
    completed_at: float | None = None
    total_pages: int = 0
    pages_generated: int = 0
    pages_cached: int = 0
    pages_failed: int = 0
    pages_remaining: int = 0
    current_page: str | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        return self.started and self.pages_remaining == 0

    @property
    def elapsed_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return round(end - self.started_at, 1)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "state": (
                "finished" if self.finished
                else "draining" if self.started
                else "waiting" if self.enabled
                else "disabled"
            ),
            "started_at": self.started_at,
            "elapsed_seconds": self.elapsed_seconds,
            "total_pages": self.total_pages,
            "pages_generated": self.pages_generated,
            "pages_cached": self.pages_cached,
            "pages_failed": self.pages_failed,
            "pages_remaining": self.pages_remaining,
            "current_page": self.current_page,
            "errors": self.errors[-5:] if self.errors else [],
        }


class PriorityLLMSlot:
    """Wraps an asyncio.Semaphore with foreground/background priority."""

    def __init__(self, semaphore: asyncio.Semaphore) -> None:
        self._sem = semaphore
        self._fg_waiting = 0

    async def acquire_foreground(self) -> None:
        self._fg_waiting += 1
        try:
            await self._sem.acquire()
        finally:
            self._fg_waiting -= 1

    async def acquire_background(self) -> None:
        while self._fg_waiting > 0:
            await asyncio.sleep(0.05)
        await self._sem.acquire()

    def release(self) -> None:
        self._sem.release()


class PrefetchQueue:
    """Background page generator driven by prediction signals."""

    def __init__(
        self,
        generator: LazyPageGenerator,
        max_workers: int = 2,
        max_queue: int = 20,
        drain_enabled: bool = False,
        drain_idle_seconds: int = 30,
    ) -> None:
        self._generator = generator
        self._queue: asyncio.PriorityQueue[tuple[int, str]] = asyncio.PriorityQueue(
            maxsize=max_queue
        )
        self._in_flight: set[str] = set()
        self._generated: set[str] = set()
        self._workers: list[asyncio.Task[None]] = []
        self._max_workers = max_workers
        self._started = False

        self._drain_enabled = drain_enabled
        self._drain_idle_seconds = drain_idle_seconds
        self._drain_started = False
        self._drain_task: asyncio.Task[None] | None = None
        self.drain_status = DrainStatus(enabled=drain_enabled)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self._max_workers):
            self._workers.append(asyncio.create_task(self._worker(i)))

    async def stop(self) -> None:
        self._started = False
        if self._drain_task:
            self._drain_task.cancel()
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue_predictions(
        self,
        source_page: str,
        cross_link_targets: list[str],
        module_siblings: list[str],
    ) -> None:
        scored: list[tuple[int, str]] = []
        for target in cross_link_targets:
            scored.append((2, target))
        for sibling in module_siblings:
            scored.append((3, sibling))

        for priority, page_path in scored:
            if page_path in self._generated or page_path in self._in_flight:
                continue
            if self._queue.full():
                break
            try:
                self._queue.put_nowait((priority, page_path))
            except asyncio.QueueFull:
                break

        if self._drain_enabled:
            if self._drain_task:
                self._drain_task.cancel()
            self._drain_started = False
            self._drain_task = asyncio.create_task(self._maybe_start_drain())

    def kickstart_drain(self) -> None:
        if not self._drain_enabled or self._drain_started:
            return
        if self._drain_task:
            self._drain_task.cancel()
        self._drain_task = asyncio.create_task(self._maybe_start_drain())

    async def _worker(self, worker_id: int) -> None:
        while self._started:
            try:
                priority, page_path = await asyncio.wait_for(
                    self._queue.get(), timeout=5.0
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if not self._started:
                    break
                continue

            if page_path in self._generated:
                self._queue.task_done()
                continue

            self._in_flight.add(page_path)
            self.drain_status.current_page = page_path
            try:
                await self._generator.warm_page(page_path)
                self._generated.add(page_path)
                if self._drain_started:
                    self.drain_status.pages_generated += 1
                    self.drain_status.pages_remaining = max(0, self.drain_status.pages_remaining - 1)
                    if self.drain_status.pages_generated % 10 == 0 or self.drain_status.pages_remaining == 0:
                        logger.info(
                            "Drain progress: %d/%d generated (%d cached, %d failed)",
                            self.drain_status.pages_generated,
                            self.drain_status.total_pages,
                            self.drain_status.pages_cached,
                            self.drain_status.pages_failed,
                        )
            except Exception as exc:
                logger.debug(
                    "Prefetch worker %d failed for %s",
                    worker_id,
                    page_path,
                    exc_info=True,
                )
                if self._drain_started:
                    self.drain_status.pages_failed += 1
                    self.drain_status.pages_remaining = max(0, self.drain_status.pages_remaining - 1)
                    self.drain_status.errors.append(f"{page_path}: {exc}")
            finally:
                self._in_flight.discard(page_path)
                self.drain_status.current_page = None
                self._queue.task_done()

    async def _maybe_start_drain(self) -> None:
        if not self._drain_enabled or self._drain_started:
            return
        logger.info(
            "Drain mode: waiting %ds for idle before backfilling...",
            self._drain_idle_seconds,
        )
        await asyncio.sleep(self._drain_idle_seconds)
        if not self._queue.empty():
            return
        self._drain_started = True
        self.drain_status.started = True
        self.drain_status.started_at = time.time()

        virtual = self._generator.get_virtual_structure()
        all_pages: set[str] = set()
        for p in virtual.get("pages", []):
            all_pages.add(p["path"])
        for section_pages in virtual.get("sections", {}).values():
            for p in section_pages:
                all_pages.add(p["path"])

        enqueued = 0
        cached = 0
        for page_path in sorted(all_pages):
            if page_path in self._generated:
                continue
            if self._generator._read_cached(page_path) is not None:
                self._generated.add(page_path)
                cached += 1
                continue
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                self._queue.put_nowait((99, page_path))
                enqueued += 1
            except asyncio.QueueFull:
                break

        self.drain_status.pages_cached = cached
        self.drain_status.total_pages = enqueued + cached
        self.drain_status.pages_remaining = enqueued

        logger.info(
            "Drain started: %d pages to generate, %d already cached",
            enqueued, cached,
        )
        if enqueued == 0:
            self.drain_status.completed_at = time.time()
            logger.info("Drain complete: all pages already cached")
