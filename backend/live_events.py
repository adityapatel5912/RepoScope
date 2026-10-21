"""
live_events.py
A tiny publish/subscribe bus for server-pushed events.

Milestone 2.2 — the live graph. When the watcher notices that a file
changed, it re-indexes the affected subgraph and publishes the new graph.
The browser subscribes and redraws. No polling, no page reload.

The bus is deliberately minimal:

    * it is thread-safe, because the file watcher runs in a watchdog
      thread while the subscribers live on the asyncio event loop;
    * it keeps only the LATEST payload per subscriber. A graph is a
      snapshot, not a stream of deltas — if three edits land while the
      browser is busy, only the newest snapshot matters. Dropping the
      stale ones keeps the browser from rendering a state that no longer
      exists;
    * it never blocks the publisher. A slow consumer must not stall the
      watcher.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

log = logging.getLogger("reposcope.live_events")

#: How many payloads a subscriber may fall behind by before the oldest is
#: dropped. One is enough for a graph snapshot; a small buffer absorbs a
#: burst of edits without letting the queue grow without bound.
QUEUE_SIZE = 4


class EventBus:
    """Fan-out from one publisher to many async subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.published = 0

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """
        Remember the event loop so `publish` can be called from another
        thread safely.
        """
        self._loop = loop or asyncio.get_running_loop()

    # ── Subscribing ─────────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber and return the queue it reads from."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        with self._lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Deregister a subscriber."""
        with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    # ── Publishing ──────────────────────────────────────────────────────────

    def publish(self, payload: dict[str, Any]) -> None:
        """
        Publish a payload to every subscriber.

        Safe to call from any thread. When the bus is bound to a running
        event loop the delivery is scheduled onto that loop; otherwise the
        payload is delivered inline (the same-thread case).
        """
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(self._deliver, payload)
                return
            except RuntimeError:
                # The loop closed between the check and the call.
                log.debug("Event loop closed — dropping payload")
                return
        self._deliver(payload)

    def _deliver(self, payload: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            if queue.full():
                # Drop the OLDEST payload. The newest snapshot is the only
                # one that describes the current state of the repository.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:  # pragma: no cover - race
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:  # pragma: no cover - race
                pass
        self.published += 1


#: The process-wide bus. There is one repository loaded at a time, so
#: there is one graph to push.
bus = EventBus()
