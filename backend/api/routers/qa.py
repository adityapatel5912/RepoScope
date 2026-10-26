"""
api/routers/qa.py
QA-only endpoints. Mounted ONLY when REPOSCOPE_QA=1.

These exist so the browser-QA harness can put the app into a known state
without touching the network. A QA run that clones a repository from GitHub
fails for the wrong reason — rate limits, auth, connectivity — and a
failure you cannot distinguish from a product bug is worse than no gate.

Mounting is gated in api/__init__.py, so in a normal deployment this router
does not exist at all.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException

from repo_loader import load_local_repo

router = APIRouter(prefix="/api/qa", tags=["qa"])

#: The fixture repositories shipped with the test suite.
FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"


@router.get("/fixtures")
async def list_fixtures():
    """List the fixture repositories available to a QA run."""
    if not FIXTURES_DIR.is_dir():
        return {"fixtures": []}
    names = sorted(
        p.name for p in FIXTURES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_")
    )
    return {"fixtures": names, "path": str(FIXTURES_DIR)}


@router.post("/load-fixture")
async def load_fixture(name: str = "multilang"):
    """
    Load a fixture repository as the active repository.

    This is the hermetic entry point: it sets the same repo state that
    `load_repo` would set after a clone, so the graph, the file tree, the
    impact analysis, and the tour all exercise their real code paths
    against real (small) source code.
    """
    if not FIXTURES_DIR.is_dir():
        raise HTTPException(status_code=500, detail="Fixtures directory not found")

    target = FIXTURES_DIR / name
    if not target.is_dir():
        available = [
            p.name for p in FIXTURES_DIR.iterdir()
            if p.is_dir() and not p.name.startswith("_")
        ]
        raise HTTPException(
            status_code=404,
            detail=f"Unknown fixture '{name}'. Available: {', '.join(sorted(available))}",
        )

    try:
        return load_local_repo(str(target))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
