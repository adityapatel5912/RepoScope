"""
api/routers/local.py
Local-mode endpoints — the HTTP surface of `reposcope run .`

Milestone 2.2 (Sprint 3). Decision D1 assigns the local-mode and
repo-status endpoints to this router.

Three things live here:

    GET  /api/repo/status   the loaded repository's state (moved here
                             from main.py, unchanged in shape)
    GET  /api/local/status   the live session: is it watching? what did
                             the last re-index change?
    POST /api/local/load     point the session at a directory on disk
    GET  /api/local/events   the SSE stream the browser subscribes to

The last one is what makes "editing a file updates the graph without a
page reload" true. The browser opens an EventSource; the watcher
re-indexes and publishes; the browser redraws.

**Guardrail.** Nothing here ever makes an outbound request. A local
repository is analysed entirely on the machine that holds it. That is the
promise the LOCAL MODE badge makes to the user, so it is enforced here:
there is no code path in this router that talks to GitHub.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from live_events import bus
from repo_loader import load_local_repo
from repo_tracker import load_state
from sse import sse_frame
from watcher import session

log = logging.getLogger("reposcope.api.local")

router = APIRouter(tags=["local"])


class LocalLoadRequest(BaseModel):
    """A request to analyse a directory that is already on disk."""

    path: str
    watch: bool = True


@router.get("/api/repo/status")
async def repo_status():
    """
    The loaded repository's state.

    Migrated from main.py under decision D1 — the path and the response
    shape are unchanged, so no client had to be touched.
    """
    return load_state()


@router.get("/api/local/status")
async def local_status():
    """The live local-mode session."""
    status = session.status()
    status["is_local"] = bool(load_state().get("is_local"))
    return status


@router.post("/api/local/load")
async def local_load(req: LocalLoadRequest):
    """
    Analyse a local directory and start watching it.

    This is what the CLI calls during `reposcope run .`, and what the
    "open a local folder" flow in the UI would call.
    """
    root = Path(req.path).expanduser()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")

    try:
        info = load_local_repo(str(root))
        graph = session.attach(str(root), watch=req.watch)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - report, do not 500 opaquely
        log.exception("Local load failed")
        raise HTTPException(status_code=500, detail=f"Could not index {root}: {exc}") from exc

    return {
        "ok": True,
        **info,
        "graph_summary": graph.get("summary", ""),
        "node_count": len(graph.get("nodes", []) or []),
        "edge_count": len(graph.get("edges", []) or []),
        "watching": session.status().get("watching", False),
    }


@router.get("/api/local/events")
async def local_events(request: Request):
    """
    The live-graph stream.

    Emits a `context` event — the same event name and the same payload
    shape the chat stream uses — every time the watcher re-indexes. The
    frontend already knows how to render a `context` event, so the live
    graph needed no new frontend code path.
    """
    queue = bus.subscribe()

    async def event_generator():
        try:
            # Tell the client the stream is alive before the first change.
            yield sse_frame("ready", {"ok": True, "watching": session.status().get("watching", False)})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # A keep-alive comment keeps proxies from closing an
                    # idle connection.
                    yield ": keep-alive\n\n"
                    continue
                yield sse_frame("context", payload)
        except asyncio.CancelledError:  # pragma: no cover - client hang-up
            raise
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
