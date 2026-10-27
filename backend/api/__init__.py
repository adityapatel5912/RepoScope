"""
api/__init__.py
Router package for RepoScope's HTTP API.

Correction C9: backend/main.py was 1,115 lines and six milestones of
endpoints were about to land on top of it. New endpoints go in
backend/api/routers/ instead, and main.py stays a thin composition root.

Decision D1 (Sprint 0): existing endpoints are NOT migrated here. Each
router adopts the endpoints it owns as the feature that owns them ships.
"""
import os

from fastapi import FastAPI

from api.routers import analysis, arch, context, harness, local, mindmap, pr_chat


def register_routers(app: FastAPI) -> None:
    """Mount every router onto the application."""
    app.include_router(arch.router)
    app.include_router(analysis.router)
    # Phase 1 (schema v2): the frozen mind-map projection. It reads the
    # active graph; it does not own a parser or a classifier of its own.
    app.include_router(mindmap.router)
    # Sprint 3 (decision D1): the local-mode and repo-status endpoints
    # move here. `/api/repo/status` keeps its path and its response
    # shape, so no client had to change.
    app.include_router(local.router)
    # Sprint 6 (decision D1): the PR bot's conversational endpoint and
    # the SARIF output.
    app.include_router(pr_chat.router)
    # Phase 3: the nine-agent harness configurator. Preview is always
    # side-effect-free; writes require REPOSCOPE_HARNESS_APPLY=1.
    app.include_router(harness.router)
    # Phase 4: deterministic context compressor and context pack endpoint.
    app.include_router(context.router)

    # QA-only routes exist so the browser-QA harness can reach a known state
    # without touching the network. They are mounted ONLY in QA mode, so a
    # normal deployment does not expose them at all.
    if os.getenv("REPOSCOPE_QA") == "1":
        from api.routers import qa

        app.include_router(qa.router)


__all__ = ["register_routers"]
