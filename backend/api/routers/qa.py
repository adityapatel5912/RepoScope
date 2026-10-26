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
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from repo_loader import load_local_repo
from watcher import session

router = APIRouter(prefix="/api/qa", tags=["qa"])

#: The fixture repositories shipped with the test suite.
FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

#: Where writable copies of a fixture are placed. A QA journey that edits
#: a file must not edit the COMMITTED fixture — the next run would then
#: start from a different repository than the snapshot expects, and the
#: failure would look like a product bug.
COPY_DIR = Path(tempfile.gettempdir()) / "reposcope-qa"


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
async def load_fixture(name: str = "multilang", copy: bool = False, watch: bool = False):
    """
    Load a fixture repository as the active repository.

    This is the hermetic entry point: it sets the same repo state that
    `load_repo` would set after a clone, so the graph, the file tree, the
    impact analysis, and the tour all exercise their real code paths
    against real (small) source code.

    `copy=true` loads a WRITABLE copy in the temp directory. The
    live-update journey needs to edit a file; editing the committed
    fixture would corrupt it for every later run.

    `watch=true` starts the file watcher, which is what makes the
    live-update journey possible.
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

    if copy:
        COPY_DIR.mkdir(parents=True, exist_ok=True)
        target = COPY_DIR / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(FIXTURES_DIR / name, target)

    try:
        info = load_local_repo(str(target))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    graph_summary = ""
    node_count = 0
    edge_count = 0
    if watch:
        from live_events import bus

        try:
            bus.bind_loop()
        except RuntimeError:
            pass  # no running loop — the bus falls back to inline delivery
        graph = session.attach(str(target), watch=True)
        graph_summary = graph.get("summary", "")
        node_count = len(graph.get("nodes", []) or [])
        edge_count = len(graph.get("edges", []) or [])

    return {
        **info,
        "copy": str(target) if copy else None,
        "graph_summary": graph_summary,
        "node_count": node_count,
        "edge_count": edge_count,
        "watching": session.status().get("watching", False),
    }
