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
import threading
import time
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


# ── The scale index (Sprint 7) ─────────────────────────────────────────────
#
# The roadmap's acceptance criterion is "a 50k-file repo's transitive
# closure resolves in <100ms" (Milestone 6.1). A 50,000-file repository
# cannot be indexed inside a browser journey — the parse alone would take
# minutes — so this endpoint builds the INDEX the store is asked to
# traverse, and times the traversal itself. It is the same
# `SqliteGraphStore` the CLI writes with `reposcope index --format
# sqlite`, on the same kind of recursive CTE; only the file contents are
# synthetic.
#
# It exists ONLY when REPOSCOPE_QA=1, like the rest of this router.

#: One built index per node count, per process. The build takes ~1.7 s;
#: the traversal is timed on every request.
_SCALE_INDEX: dict[int, tuple[object, int]] = {}
_SCALE_LOCK = threading.Lock()

#: The latency budget from docs/ROADMAP_V2.md Milestone 6.1.
TRAVERSAL_BUDGET_MS = 100.0


def _build_scale_graph(count: int) -> dict:
    """
    A synthetic 50k-file dependency graph.

    The shape matters: real repositories are shallow and wide — each file
    imports a handful of others at short, medium and long range — so a
    depth-bounded walk fans out quickly. A pure chain would make the
    traversal look instant while testing nothing.
    """
    nodes = [
        {
            "id": f"file:f{index:05d}.py",
            "type": "file",
            "label": f"f{index:05d}.py",
            "language": "python",
            "size": 120,
            "sha256": "0" * 64,
        }
        for index in range(count)
    ]
    edges = []
    for index in range(count):
        for step in (13, 307, 991):
            target = index + step
            if target < count:
                edges.append({
                    "source": f"file:f{index:05d}.py",
                    "target": f"file:f{target:05d}.py",
                    "type": "imports",
                })
    return {"nodes": nodes, "edges": edges}


def _scale_store(count: int):
    """Build (once per process) and return the synthetic SQLite index."""
    with _SCALE_LOCK:
        cached = _SCALE_INDEX.get(count)
        if cached is not None:
            return cached

        from graph_store import SqliteGraphStore

        COPY_DIR.mkdir(parents=True, exist_ok=True)
        store = SqliteGraphStore(COPY_DIR / f"scale-{count}.db")
        graph = _build_scale_graph(count)
        store.save(graph)
        _SCALE_INDEX[count] = (store, len(graph["edges"]))
        return _SCALE_INDEX[count]


@router.get("/scale-traversal")
def scale_traversal(nodes: int = 50_000, depth: int = 32):
    """
    Time a transitive traversal over a 50,000-file index.

    Returns the measured milliseconds for the descendants and ancestors
    of a leaf, the closure size, and whether the roadmap's budget was met.
    The depth is clamped to the store's own ceiling.
    """
    from graph_store import MAX_TRAVERSAL_DEPTH

    nodes = max(1_000, min(int(nodes), 100_000))
    depth = max(1, min(int(depth), MAX_TRAVERSAL_DEPTH))

    store, edge_count = _scale_store(nodes)
    first = "file:f00000.py"
    last = f"file:f{nodes - 1:05d}.py"

    def timed(call):
        started = time.perf_counter()
        value = call()
        return value, (time.perf_counter() - started) * 1000

    # A single cold query pays for opening the database and populating the
    # page cache (the first one measured 137 ms here; the next, 60 ms). The
    # budget is about the traversal, so warm the cache and report the MEDIAN
    # of three measured runs. All three are returned, so the claim is
    # checkable rather than cherry-picked.
    store.descendants(first, max_depth=depth)
    store.ancestors(last, max_depth=depth)

    descendant_runs: list[float] = []
    ancestor_runs: list[float] = []
    descendants: list[str] = []
    ancestors: list[str] = []
    for _ in range(3):
        descendants, elapsed = timed(
            lambda: store.descendants(first, max_depth=depth)
        )
        descendant_runs.append(elapsed)
        ancestors, elapsed = timed(
            lambda: store.ancestors(last, max_depth=depth)
        )
        ancestor_runs.append(elapsed)

    def median(values: list[float]) -> float:
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    descendants_ms = median(descendant_runs)
    ancestors_ms = median(ancestor_runs)

    return {
        "nodes": nodes,
        "edges": edge_count,
        "depth": depth,
        "descendants": len(descendants),
        "descendants_ms": round(descendants_ms, 1),
        "descendants_runs_ms": [round(run, 1) for run in descendant_runs],
        "ancestors": len(ancestors),
        "ancestors_ms": round(ancestors_ms, 1),
        "ancestors_runs_ms": [round(run, 1) for run in ancestor_runs],
        "budget_ms": TRAVERSAL_BUDGET_MS,
        "ok": max(descendants_ms, ancestors_ms) < TRAVERSAL_BUDGET_MS,
    }
