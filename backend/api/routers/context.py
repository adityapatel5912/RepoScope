"""
api/routers/context.py
`GET /api/context/pack` — deterministic context compression endpoint.

V2.5 Phase 4.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response

from context_compressor import (
    ContextError,
    build_context_pack,
    encode_json,
    encode_toon,
)

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("/pack")
async def context_pack(
    paths: str = Query(""),
    format: Literal["json", "toon"] = Query("json"),
    detail: Literal["skeleton", "full"] = Query("skeleton"),
    budget: int = Query(8000, ge=500, le=200000),
    since_hash: str | None = Query(None),
) -> Response:
    """Return a deterministic, budget-capped context pack."""
    from orchestrator import current_graph

    graph, root = current_graph()
    if root is None:
        try:
            import repo_tracker

            state = repo_tracker.load_state()
            if isinstance(state, dict):
                root = state.get("local_path")
        except Exception:
            pass

    if (not graph or not graph.get("nodes")) and not root:
        raise HTTPException(status_code=503, detail="No repository is loaded")

    try:
        pack = build_context_pack(
            graph=graph or {},
            root=root,
            paths=paths,
            detail=detail,
            budget=budget,
            since_hash=since_hash,
        )
    except ContextError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    headers: dict[str, str] = {
        "X-RepoScope-Context-Hash": pack.get("hash", ""),
    }

    if pack.get("unchanged"):
        headers["X-RepoScope-Context-Unchanged"] = "1"
        # The unchanged envelope is always JSON even if format=toon was requested
        return Response(
            content=encode_json(pack),
            media_type="application/json",
            headers=headers,
        )

    if format == "toon":
        try:
            toon_content = encode_toon(pack)
        except ContextError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e
        return Response(
            content=toon_content,
            media_type="text/toon; charset=utf-8",
            headers=headers,
        )

    return Response(
        content=encode_json(pack),
        media_type="application/json",
        headers=headers,
    )
