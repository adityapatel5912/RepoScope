"""
api/routers/analysis.py
Serves the graph-intelligence endpoints (Milestones 7.1, 7.2, 7.3, 1.3).

Four things the UI could not previously see:

  GET /api/analysis/hotspots   git churn and the churn x centrality blend
  GET /api/analysis/cycles     dependency cycles, at file and symbol level
  GET /api/analysis/unreachable symbols that no entry point can reach
  GET /api/analysis/hubs       the most central nodes, by PageRank

Every endpoint degrades gracefully: no git repository, an empty graph, or
a failure inside the analysis all produce a well-formed "not available"
payload rather than an error.
"""
import asyncio

from fastapi import APIRouter, HTTPException

from git_history import collect_churn, churn_to_api
from graph_analysis import (
    cycle_details,
    entry_points,
    pagerank_scores,
    top_hubs,
    unreachable_nodes,
)
from repo_tracker import load_state

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _current_graph() -> dict:
    """The cached graph for the loaded repository."""
    from orchestrator import get_cached_graph

    graph = get_cached_graph()
    if graph.get("nodes"):
        return graph

    # The graph is built lazily — build it now if a repository is loaded.
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        return {}

    from graph_builder import build_graph_from_repo

    try:
        built = build_graph_from_repo(local_path)
    except Exception:  # noqa: BLE001 - never fail an analysis endpoint
        return {}

    from orchestrator import _graph_cache

    _graph_cache.update(built)
    return built


@router.get("/hotspots")
async def hotspots(window_days: int = 90):
    """
    Git churn for the loaded repository, with a hotspot score per file.

    The hotspot score blends churn with the file's centrality: a file
    that changes often AND is widely depended upon is where regressions
    actually happen.
    """
    state = load_state()
    local_path = state.get("local_path")
    if not local_path:
        return {
            "available": False,
            "reason": "no repository loaded",
            "window_days": window_days,
            "files": [],
            "total_files": 0,
        }

    graph = await asyncio.to_thread(_current_graph)
    report = await asyncio.to_thread(collect_churn, local_path, window_days)
    return churn_to_api(report, graph)


@router.get("/cycles")
async def cycles():
    """Dependency cycles — at file level and at symbol level."""
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "cycles": [], "total": 0}

    details = cycle_details(graph)
    file_cycles = [c for c in details if c["members"][0].startswith("file:")]
    symbol_cycles = [c for c in details if not c["members"][0].startswith("file:")]

    return {
        "available": True,
        "cycles": details,
        "file_cycles": len(file_cycles),
        "symbol_cycles": len(symbol_cycles),
        "total": len(details),
        "cross_layer_count": sum(1 for c in details if c["crosses_layers"]),
    }


@router.get("/unreachable")
async def unreachable():
    """
    Symbols that no entry point can reach.

    This is a STATIC ESTIMATE. Dynamic dispatch, reflection and plugin
    registration are invisible to static analysis, so the UI must label
    it as an estimate rather than as proof of dead code.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {
            "available": False,
            "reason": "no graph",
            "entry_points": [],
            "unreachable": [],
            "total": 0,
        }

    roots = entry_points(graph)
    orphans = unreachable_nodes(graph)

    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    return {
        "available": True,
        "estimate": True,
        "entry_points": roots[:50],
        "entry_point_count": len(roots),
        "unreachable": [
            {
                "id": node_id,
                "label": nodes_by_id.get(node_id, {}).get("label", node_id),
                "file": nodes_by_id.get(node_id, {}).get("file", ""),
                "type": nodes_by_id.get(node_id, {}).get("type", ""),
            }
            for node_id in orphans[:200]
        ],
        "total": len(orphans),
    }


@router.get("/hubs")
async def hubs(limit: int = 15):
    """
    The most central nodes in the graph, by PageRank.

    Unlike the old `incoming x 2 + outgoing` heuristic, PageRank
    distinguishes a widely-imported leaf from a genuine hub.
    """
    graph = await asyncio.to_thread(_current_graph)
    if not graph:
        return {"available": False, "reason": "no graph", "hubs": []}

    scores = pagerank_scores(graph)
    return {
        "available": True,
        "hubs": top_hubs(graph, limit=max(1, min(limit, 100))),
        "total_nodes": len(scores),
    }
