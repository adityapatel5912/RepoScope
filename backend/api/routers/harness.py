"""
api/routers/harness.py
The nine-agent harness configurator (Phase 3).

Four endpoints, all thin wrappers around `harness_generator`:

    GET  /api/harness/agents   the frozen registry for the modal
    GET  /api/harness/config    the exact files a preview would write
    POST /api/harness/apply     a dry run by default; writes only when
                               REPOSCOPE_HARNESS_APPLY=1 and force allows it
    GET  /api/harness/skills    the five Phase 4 skill descriptors

The browser never writes files. Preview is guaranteed side-effect-free:
`build_preview` only reads. Apply is refused with 403 when the server
flag is off, and with 409 when it would replace a changed existing file
without `force: true`.

Every path is resolved against the repository root by the generator. A
relative or missing root is a 400, never an implicit current directory.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from harness_generator import (
    AGENTS,
    HarnessError,
    apply_config,
    build_preview,
    list_agents,
    list_skills,
)

router = APIRouter(prefix="/api/harness", tags=["harness"])


class ApplyRequest(BaseModel):
    """The only body the wizard sends when the user clicks Apply."""

    agent: str = Field(..., min_length=1)
    # Deliberately a plain string: the generator owns the transport
    # registry, so an unknown transport is a precise 400 from it rather
    # than a second, divergent validation rule here.
    transport: str = "stdio"
    root: str | None = None
    apply: bool = False
    force: bool = False


def _http_error(exc: HarnessError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/agents")
async def agents() -> dict:
    """The nine targets, their paths, transports, and provenance."""
    return list_agents()


@router.get("/config")
async def config(
    agent: str = Query(..., min_length=1),
    transport: str = Query("stdio"),
    root: str | None = Query(
        None,
        description=(
            "Absolute repository root. Defaults to the loaded local "
            "repository; there is no implicit cwd fallback."
        ),
    ),
) -> dict:
    """Preview the files, diff, and command for one agent. Never writes."""
    try:
        return build_preview(agent, transport, root)
    except HarnessError as exc:
        raise _http_error(exc) from exc


@router.post("/apply")
async def apply(body: ApplyRequest) -> dict:
    """
    Dry run by default; write the previewed files when enabled.

    `apply: false` is a preview and returns `applied: []`. `apply: true`
    requires the server flag and, for an existing file that would change,
    `force: true`.
    """
    try:
        return apply_config(
            body.agent,
            body.transport,
            body.root,
            apply=body.apply,
            force=body.force,
        )
    except HarnessError as exc:
        raise _http_error(exc) from exc


@router.get("/skills")
async def skills() -> dict:
    """
    The five skill descriptors.

    Bodies are deliberately absent in Phase 3: `content_available` is
    false for every entry until Phase 4 ships the SKILL.md files.
    """
    return list_skills()


__all__ = ["router", "AGENTS"]
