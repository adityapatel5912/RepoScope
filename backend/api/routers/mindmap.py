"""
api/routers/mindmap.py
`GET /api/mindmap` — the frozen hierarchical projection (Phase 1).

The endpoint reads the SAME graph as every other analysis surface:
`orchestrator.current_graph()`. It never parses the repository, never
calls an LLM, and never classifies a file in the browser.

Errors are narrow on purpose. `503` means no repository is active;
an active repository with no nodes is a valid `200` with an empty tree.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from mindmap import (
    DEFAULT_MAX_NODES,
    MAX_NODES_LIMIT,
    build_mindmap_payload,
)

router = APIRouter(prefix="/api", tags=["mindmap"])


@router.get("/mindmap")
async def mindmap(
    include_symbols: bool = Query(True),
    max_nodes: int = Query(DEFAULT_MAX_NODES, ge=1, le=MAX_NODES_LIMIT),
):
    """
    Return the root → pillar → folder → file → symbol tree.

    `max_nodes` is deterministic: the root and pillars are included
    first, then folders shallow-to-deep, then files by path, then
    symbols by line. The response states `truncated` and `omitted` so a
    client never presents a capped tree as complete.
    """
    from orchestrator import current_graph

    graph, root = current_graph()
    if not graph.get("nodes") and not root:
        raise HTTPException(status_code=503, detail="No repository is loaded")

    payload = build_mindmap_payload(
        graph,
        include_symbols=include_symbols,
        max_nodes=max_nodes,
    )
    payload["generated_at"] = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    payload["source"]["root"] = root
    return payload
