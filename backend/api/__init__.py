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

from api.routers import analysis, arch


def register_routers(app: FastAPI) -> None:
    """Mount every router onto the application."""
    app.include_router(arch.router)
    app.include_router(analysis.router)

    # QA-only routes exist so the browser-QA harness can reach a known state
    # without touching the network. They are mounted ONLY in QA mode, so a
    # normal deployment does not expose them at all.
    if os.getenv("REPOSCOPE_QA") == "1":
        from api.routers import qa

        app.include_router(qa.router)


__all__ = ["register_routers"]
