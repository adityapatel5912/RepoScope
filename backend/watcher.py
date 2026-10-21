"""
watcher.py
Live re-indexing: the repository is watched, and an edit updates the
graph without a page reload.

Milestone 2.2 (Sprint 3) and Milestone 6.2.

How it fits together:

    watchdog  ──file event──▶  debounce (500 ms)
                                        │
                                        ▼
                          GraphIndexer.apply(changed, removed)
                                        │
                                        ▼
                              EventBus.publish(graph)
                                        │
                                        ▼
                          GET /api/local/events  (SSE)
                                        │
                                        ▼
                              the browser redraws the graph

Two decisions worth stating:

**Debounce.** An editor that saves a file often writes it more than once,
and a `git checkout` touches dozens of files in a burst. Without a
debounce the indexer would re-parse the same content repeatedly. The
debounce is 500 ms — long enough to swallow a save burst, short enough
that a human still perceives the update as instant.

**Incremental, not full.** The watcher does NOT rebuild the graph. It
re-parses the changed files and patches the edges that the change can
affect. `GraphIndexer` owns that logic.

The watcher is only started for a LOCAL repository. A repository cloned
from GitHub is a snapshot in a temp directory; watching it would be
pointless, and the guard is what keeps a local-mode session from making
outbound requests of any kind.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from graph_builder import GraphIndexer
from live_events import EventBus, bus as default_bus
from parse_cache import ParseCache, default_cache_path

log = logging.getLogger("reposcope.watcher")

#: How long to wait after the last file event before re-indexing.
DEFAULT_DEBOUNCE_MS = 500

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:  # pragma: no cover - watchdog is a declared dependency
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    Observer = None  # type: ignore[assignment]
    WATCHDOG_AVAILABLE = False


class _Handler(FileSystemEventHandler):  # type: ignore[misc]
    """Collects the paths that changed, for the debouncer to consume."""

    def __init__(self, on_event: Callable[[str, str], None]) -> None:
        super().__init__()
        self._on_event = on_event

    def on_any_event(self, event) -> None:  # noqa: ANN001 - watchdog's API
        if event.is_directory:
            return
        event_type = event.event_type
        if event_type == "opened" or event_type == "closed":
            # These fire on every read; they say nothing about content.
            return
        self._on_event(event.src_path, event_type)


class RepoWatcher:
    """
    Watches a directory and calls back when files change.

    The callback receives the repo-relative paths that were created or
    modified, and the ones that were deleted.
    """

    def __init__(
        self,
        root: str | Path,
        on_change: Callable[[list[str], list[str]], None],
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
        ignore_dirs: Iterable[str] = (),
    ):
        self.root = Path(root)
        self.on_change = on_change
        self.debounce_ms = debounce_ms
        self.ignore_dirs = {
            ".git", "node_modules", "__pycache__", ".reposcope",
            "dist", "build", ".venv", "venv", ".pytest_cache", ".mypy_cache",
            *ignore_dirs,
        }

        self._observer = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._changed: set[str] = set()
        self._removed: set[str] = set()
        self._running = False
        self.change_count = 0

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Begin watching. Returns False when watchdog is unavailable."""
        if self._running:
            return True
        if not WATCHDOG_AVAILABLE:
            log.warning("watchdog is not installed — live updates are disabled")
            return False
        try:
            self._observer = Observer()
            self._observer.schedule(
                _Handler(self._handle_event),
                str(self.root),
                recursive=True,
            )
            self._observer.start()
        except Exception as exc:  # noqa: BLE001 - a watcher failure is not fatal
            log.warning("Could not start the file watcher: %s", exc)
            self._observer = None
            return False
        self._running = True
        log.info("Watching %s for changes", self.root)
        return True

    def stop(self) -> None:
        """Stop watching and release the observer."""
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        observer = self._observer
        self._observer = None
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=5)
            except Exception:  # noqa: BLE001 - best effort
                pass

    @property
    def running(self) -> bool:
        return self._running

    # ── Event handling ──────────────────────────────────────────────────────

    def _handle_event(self, src_path: str, event_type: str) -> None:
        path = Path(src_path)
        try:
            rel = str(path.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return
        if not rel or rel.split("/")[0] in self.ignore_dirs:
            return

        with self._lock:
            if event_type == "deleted" or event_type == "moved":
                self._removed.add(rel)
                self._changed.discard(rel)
            else:
                self._changed.add(rel)
                self._removed.discard(rel)
            self._schedule_locked()

    def _schedule_locked(self) -> None:
        """(Re)start the debounce timer. Must be called with the lock held."""
        if self._timer is not None:
            self._timer.cancel()
        timer = threading.Timer(self.debounce_ms / 1000.0, self._flush)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def _flush(self) -> None:
        """The debounce fired — hand the accumulated changes to the callback."""
        with self._lock:
            changed = sorted(self._changed)
            removed = sorted(self._removed)
            self._changed.clear()
            self._removed.clear()
            self._timer = None
        if not changed and not removed:
            return
        self.change_count += 1
        log.info("Watcher saw %d changed, %d removed", len(changed), len(removed))
        try:
            self.on_change(changed, removed)
        except Exception as exc:  # noqa: BLE001 - a failed re-index must not kill the watcher
            log.exception("Re-index failed: %s", exc)


class LocalSession:
    """
    The live local-mode session: an index, a watcher, and a bus.

    One repository is watched at a time. Attaching a new one replaces the
    old, because the graph on screen describes exactly one codebase.
    """

    def __init__(self, bus: EventBus | None = None):
        self.bus = bus or default_bus
        self.indexer: GraphIndexer | None = None
        self.watcher: RepoWatcher | None = None
        self.root: str | None = None
        self.cache: ParseCache | None = None
        self.last_update: dict = {}
        self.change_count = 0

    # ── Attaching ───────────────────────────────────────────────────────────

    def attach(self, root: str | Path, watch: bool = True) -> dict:
        """Index `root` and start watching it."""
        root_path = Path(root).resolve()
        self.detach()

        self.root = str(root_path)
        self.cache = ParseCache(default_cache_path(root_path))
        self.cache.load()

        self.indexer = GraphIndexer(root_path, self.cache)
        graph = self.indexer.index()
        self.cache.save()

        if watch:
            self.watcher = RepoWatcher(root_path, self._on_change)
            self.watcher.start()

        log.info(
            "Local session attached to %s: %s", root_path, graph.get("summary"),
        )
        return graph

    def detach(self) -> None:
        """Stop watching and release everything."""
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None
        self.indexer = None
        self.root = None
        self.cache = None
        self.last_update = {}

    # ── Updating ────────────────────────────────────────────────────────────

    def _on_change(self, changed: list[str], removed: list[str]) -> None:
        """The watcher's callback: re-index and publish."""
        if self.indexer is None:
            return
        graph = self.indexer.apply(changed, removed)
        self.change_count += 1
        self.last_update = dict(getattr(self.indexer, "last_update", {}))
        if self.cache is not None:
            self.cache.save()
        self.publish(graph)

    def publish(self, graph: dict) -> None:
        """Push the current graph to every subscriber."""
        payload = {
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "graph_summary": graph.get("summary", ""),
            "node_count": len(graph.get("nodes", []) or []),
            "edge_count": len(graph.get("edges", []) or []),
            "changed": self.last_update.get("changed", []),
            "removed": self.last_update.get("removed", []),
            "duration_ms": self.last_update.get("duration_ms", 0),
            "timestamp": time.time(),
        }
        self.bus.publish(payload)

    # ── Introspection ───────────────────────────────────────────────────────

    def status(self) -> dict:
        """A snapshot of the session, for the status endpoint."""
        watching = bool(self.watcher and self.watcher.running)
        graph = self.indexer.graph if self.indexer else {}
        return {
            "attached": self.indexer is not None,
            "root": self.root,
            "watching": watching,
            "watchdog_available": WATCHDOG_AVAILABLE,
            "graph_summary": graph.get("summary", ""),
            "node_count": len(graph.get("nodes", []) or []),
            "edge_count": len(graph.get("edges", []) or []),
            "change_count": self.change_count,
            "last_update": self.last_update,
            "subscribers": self.bus.subscriber_count,
        }


#: The process-wide local session.
session = LocalSession()


def attach_local_session(root: str | Path, watch: bool = True) -> dict:
    """Index a local repository and start watching it."""
    return session.attach(root, watch=watch)


def local_session_status() -> dict:
    """The current local-mode status."""
    return session.status()
